"""
Phase 15 — ContextualResultAdapter

Deterministic translation boundary between Group 2 contextual_result
(temporal applicability ruling) and a DecisionContract candidate.

Responsibilities (ONLY):
  1. Validate that all required fields are present in the ruling.
  2. Apply deterministic translation rules (GAP → abstention/noop).
  3. Preserve provenance fields (observation_id, context_id, trace_id,
     execution_id) unchanged into DecisionContract.parameters.
  4. Enforce the hard safety invariant: GAP rulings MUST NOT produce
     operational actions.

This module does NOT:
  - Call ActionGovernance
  - Write to any log or database
  - Generate new IDs to replace existing ones
  - Interpret the scientific context artifact (TC-Z03-F02-LIDAR-OBS001.json)
    — it only reads the ruling artifact (temporal_applicability_ruling.json)

Contract reference (Kaushal's actual field names):
  backend/integration/group2/temporal_applicability_ruling.json
    ruling           → "GAP" | "ALLOW" | "ADAPT"
    action_eligibility → bool
    abstention_required → bool
    observation_id   → str
    context_id       → str
"""

import sys
from pathlib import Path

# Resolve backend root so this module can import contracts regardless of cwd
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from contracts.decision_contract import DecisionContract

# ---------------------------------------------------------------------------
# Constants — derived from Kaushal's ruling schema
# ---------------------------------------------------------------------------

RULING_GAP = "GAP"
RULING_ALLOW = "ALLOW"
RULING_ADAPT = "ADAPT"

# Actions that are safe for an abstention contract
SAFE_ACTIONS = {"noop", "abstain"}

# Actions that represent operational state changes — forbidden for GAP rulings
OPERATIONAL_ACTIONS = {
    "restart",
    "scale_up",
    "scale_down",
    "rollback",
    "execute",
    "delete",
    "modify",
}

# Fields that MUST be present in every temporal applicability ruling
REQUIRED_FIELDS = {
    "ruling",
    "action_eligibility",
    "abstention_required",
    "observation_id",
    "context_id",
}

DECISION_VERSION = "v1"


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class ContextualResultAdapter:
    """
    Translates a Group 2 temporal applicability ruling dict into a
    DecisionContract candidate.

    This is a pure, stateless, deterministic transformer.
    Same input → same output, always.
    """

    def translate(self, contextual_result: dict) -> DecisionContract:
        """
        Translate the ruling into a DecisionContract.

        Args:
            contextual_result: The temporal applicability ruling dict produced
                by Group 2. Must conform to:
                  backend/integration/group2/temporal_applicability_ruling.json

        Returns:
            DecisionContract with decision_type="abstention" and action="noop"
            when GAP, action_eligibility=False, or abstention_required=True.

        Raises:
            ValueError: If required fields are missing or no translation rule
                        matches the ruling.
            RuntimeError: (from assert_safe) If the produced contract carries
                          an operational action — hard safety invariant.
        """
        self._validate(contextual_result)

        ruling = contextual_result["ruling"]
        action_eligibility = contextual_result["action_eligibility"]
        abstention_required = contextual_result["abstention_required"]

        # Deterministic translation rule:
        # ANY of these three conditions alone is sufficient to mandate abstention.
        if (
            ruling == RULING_GAP
            or not action_eligibility
            or abstention_required
        ):
            contract = DecisionContract(
                decision_type="abstention",
                action="noop",
                parameters={
                    # Ruling fields
                    "reason": "TEMPORAL_GAP",
                    "ruling": ruling,
                    "action_eligibility": action_eligibility,
                    "abstention_required": abstention_required,
                    # Identity / provenance — passed through unchanged
                    "observation_id": contextual_result["observation_id"],
                    "context_id": contextual_result["context_id"],
                    # Optional provenance fields — preserved if present
                    "canonical_record_id": contextual_result.get("canonical_record_id"),
                    "trace_id": contextual_result.get("trace_id"),
                    "execution_id": contextual_result.get("execution_id"),
                    # Source authority metadata
                    "contract_version": contextual_result.get("contract_version"),
                    "authority": contextual_result.get("authority"),
                },
                version=DECISION_VERSION,
            )
            self.assert_safe(contract)
            return contract

        # Phase 16: ALLOW
        if ruling == RULING_ALLOW and action_eligibility and not abstention_required:
            if "canonical_record_id" not in contextual_result:
                raise ValueError(
                    f"canonical_record_id is missing from the Group 2 handoff. "
                    f"It must not be invented or derived."
                )
            
            return DecisionContract(
                decision_type="action_request_eligible",
                action="noop",
                parameters={
                    "reason": "TEMPORAL_ALLOW",
                    "ruling": ruling,
                    "action_eligibility": action_eligibility,
                    "abstention_required": abstention_required,
                    "observation_id": contextual_result["observation_id"],
                    "canonical_record_id": contextual_result["canonical_record_id"],
                    "context_id": contextual_result["context_id"],
                    "trace_id": contextual_result.get("trace_id"),
                    "execution_id": contextual_result.get("execution_id"),
                    "contract_version": contextual_result.get("contract_version"),
                    "authority": contextual_result.get("authority"),
                    "evidence": contextual_result.get("evidence"),
                },
                version=DECISION_VERSION,
            )

        # Future: ADAPT rules would go here.
        raise ValueError(
            f"No translation rule defined for ruling={ruling!r} "
            f"with action_eligibility={action_eligibility}, "
            f"abstention_required={abstention_required}. "
            f"Currently handles GAP and ALLOW rulings."
        )

    def _validate(self, result: dict) -> None:
        """
        Verify that all required fields are present in the ruling dict.

        Raises:
            ValueError: With the list of missing field names.
        """
        if not isinstance(result, dict):
            raise ValueError(
                f"contextual_result must be a dict, got {type(result).__name__!r}"
            )
        missing = REQUIRED_FIELDS - result.keys()
        if missing:
            raise ValueError(
                f"contextual_result is missing required fields: {sorted(missing)}"
            )

    def assert_safe(self, contract: DecisionContract) -> None:
        """
        Hard safety invariant: the produced DecisionContract must NOT carry
        any operational action.

        This is a second line of defence after the translation rule itself
        already produces "noop". It guards against future code changes that
        might accidentally route an operational action through this path.

        Raises:
            RuntimeError: If the contract action is operational — this is a
                          programming error and must never be silently swallowed.
        """
        if contract.action in OPERATIONAL_ACTIONS:
            raise RuntimeError(
                f"SAFETY VIOLATION: A GAP / abstention ruling produced an "
                f"operational action '{contract.action}'. This is forbidden. "
                f"Operational actions must not be generated from a GAP ruling. "
                f"decision_type={contract.decision_type!r}"
            )
        if contract.action not in SAFE_ACTIONS:
            raise RuntimeError(
                f"SAFETY VIOLATION: Unexpected action '{contract.action}' "
                f"in abstention DecisionContract. "
                f"Only {sorted(SAFE_ACTIONS)} are permitted."
            )
