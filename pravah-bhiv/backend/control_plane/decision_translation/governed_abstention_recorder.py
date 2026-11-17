"""
Phase 15 — GovernedAbstentionRecorder

Records a GOVERNED_ABSTENTION event into the AppendOnlyLog (hash-chained,
deterministic, append-only evidence ledger).

Identity design:
  Two distinct identifiers are maintained:

  abstention_record_id — DETERMINISTIC correlation identity.
      Derived from: sha256(canonical_json({scheme, observation_id, context_id, ruling})).
      Stable across ANY replay regardless of execution_id or trace_id.
      Use this when Group 3 needs a stable fourth correlation reference.

  event_id — UNIQUE ledger event identity.
      Random UUID generated at record time.
      Unique per write; two replays of the same ruling produce different event_ids.
      Use this to look up the specific immutable ledger entry.

Responsibilities (ONLY):
  - Accept a DecisionContract (action=noop/abstain, decision_type=abstention)
    and a GovernanceDecision (should_block=False) as inputs.
  - Build the canonical event payload.
  - Compute its hash via HashLineageVerifier._compute_event_hash.
  - Append it to the existing AppendOnlyLog with source="governed_abstention".
  - Return the written event as a plain dict for caller inspection / testing.

This module does NOT:
  - Trigger any operational execution
  - Call ActionGovernance.evaluate_contract (caller already did that)
  - Generate new observation_id or context_id values
"""

import sys
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Resolve backend root
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from contracts.decision_contract import DecisionContract
from control_plane.core.action_governance import GovernanceDecision
from control_plane.persistence import AppendOnlyLog
from control_plane.persistence.hash_lineage_verifier import HashLineageVerifier

# Event type written to the ledger
GOVERNED_ABSTENTION_STATE = "GOVERNED_ABSTENTION"
RECORDER_SOURCE = "governed_abstention"

# Default log path — same journal as ActionGovernance
DEFAULT_LOG_PATH = "logs/control_plane/append_only_log.jsonl"

# Versioned scheme tag for canonical identity serialization.
# Changing this value produces different abstention_record_ids — do not change
# without a migration plan.
ABSTENTION_ID_SCHEME = "bhiv.governed_abstention.v1"

# Prefix for deterministic abstention_record_id
ABSTENTION_ID_PREFIX = "abstention-"
# Number of hex chars to use from the sha256 digest (24 = 96 bits, collision-safe)
ABSTENTION_ID_DIGEST_LEN = 24


class GovernedAbstentionRecorder:
    """
    Writes a GOVERNED_ABSTENTION event to the append-only execution ledger.

    Each call to record() appends exactly one immutable event. The event
    carries the full provenance chain:
      observation_id, context_id, ruling, trace_id, execution_id

    No operational execution is triggered, expected, or possible from this
    recorder.
    """

    def __init__(self, log_path: Optional[str] = None):
        """
        Args:
            log_path: Override the append-only log file path. Defaults to
                      the same journal used by ActionGovernance.
        """
        self._log = AppendOnlyLog(log_path or DEFAULT_LOG_PATH)

    def record(
        self,
        contract: DecisionContract,
        governance_decision: GovernanceDecision,
    ) -> Dict[str, Any]:
        """
        Append a GOVERNED_ABSTENTION event to the ledger.

        Args:
            contract: DecisionContract produced by ContextualResultAdapter.
                      Must have decision_type="abstention" and action in
                      {"noop", "abstain"}.
            governance_decision: Result from ActionGovernance.evaluate_contract.
                                 Must have should_block=False (noop is always
                                 allowed by governance eligibility rules).

        Returns:
            A plain dict describing the written evidence record. This is safe
            to log, assert against in tests, or forward to a bucket/ledger.

        Raises:
            ValueError: If the contract is not an abstention type.
            RuntimeError: If governance_decision.should_block is True — this
                          indicates a contract/governance mismatch that must
                          not be silently swallowed.
        """
        if contract.decision_type != "abstention":
            raise ValueError(
                f"GovernedAbstentionRecorder requires decision_type='abstention', "
                f"got {contract.decision_type!r}"
            )
        if governance_decision.should_block:
            raise RuntimeError(
                f"GovernedAbstentionRecorder: governance blocked the abstention "
                f"contract (reason={governance_decision.reason!r}). "
                f"A noop action should never be blocked by governance."
            )

        params = contract.parameters
        execution_id = params.get("execution_id") or f"exec-abstention-{uuid.uuid4().hex[:16]}"
        event_id = str(uuid.uuid4())
        timestamp_int = int(datetime.now(timezone.utc).timestamp())

        # Deterministic correlation identity — derived ONLY from the business
        # identity triple (observation_id, context_id, ruling).
        # execution_id and trace_id are runtime-owned and MUST NOT participate.
        abstention_record_id = self._compute_abstention_record_id(
            observation_id=params.get("observation_id", ""),
            context_id=params.get("context_id", ""),
            ruling=params.get("ruling", ""),
        )

        details: Dict[str, Any] = {
            # Core provenance
            "event_type": GOVERNED_ABSTENTION_STATE,
            "observation_id": params.get("observation_id"),
            "context_id": params.get("context_id"),
            "ruling": params.get("ruling"),
            "reason": params.get("reason", "TEMPORAL_GAP"),
            "action_eligibility": params.get("action_eligibility"),
            "abstention_required": params.get("abstention_required"),
            # Decision identity
            "decision_action": contract.action,
            "decision_type": contract.decision_type,
            "decision_version": contract.version,
            # Provenance chain
            "trace_id": params.get("trace_id"),
            "execution_id": execution_id,
            "contract_version": params.get("contract_version"),
            "authority": params.get("authority"),
            # Identity — two distinct concepts (see module docstring)
            "abstention_record_id": abstention_record_id,  # deterministic correlation ID
            "event_id": event_id,                          # unique ledger event ID
            # Governance result
            "governance_allowed": not governance_decision.should_block,
            "governance_admission_state": governance_decision.admission_state,
            "governance_policy_id": governance_decision.policy_id,
            # Wall clock
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        # Build canonical payload for hash computation
        event_payload = {
            "execution_id": execution_id,
            "event_id": event_id,
            "state": GOVERNED_ABSTENTION_STATE,
            "timestamp": timestamp_int,
            "source": RECORDER_SOURCE,
            "details": details,
        }

        event_hash = HashLineageVerifier._compute_event_hash(event_payload)
        previous_hash = self._log._execution_last_hashes.get(execution_id, "")

        self._log.append(
            execution_id=execution_id,
            event_id=event_id,
            state=GOVERNED_ABSTENTION_STATE,
            timestamp=timestamp_int,
            event_hash=event_hash,
            previous_hash=previous_hash,
            source=RECORDER_SOURCE,
            details=details,
        )

        return {
            "event_type": GOVERNED_ABSTENTION_STATE,
            # Two identity fields — see module docstring for distinction
            "abstention_record_id": abstention_record_id,  # deterministic, stable across replay
            "event_id": event_id,                          # unique per ledger write
            "execution_id": execution_id,
            "observation_id": params.get("observation_id"),
            "context_id": params.get("context_id"),
            "ruling": params.get("ruling"),
            "decision_action": contract.action,
            "governance_allowed": True,
            "recorded_at": details["recorded_at"],
        }

    @staticmethod
    def _compute_abstention_record_id(
        observation_id: str,
        context_id: str,
        ruling: str,
    ) -> str:
        """
        Compute a deterministic abstention_record_id.

        Identity semantics:
          - Derived ONLY from observation_id, context_id, and ruling.
          - execution_id and trace_id are explicitly excluded: they are
            runtime-owned and change between executions/replays.
          - Uses a versioned canonical JSON serialization (sort_keys=True,
            no whitespace) to prevent any ambiguity from field ordering.
          - The scheme tag (ABSTENTION_ID_SCHEME) versions the derivation
            so future changes can be detected and migrated.

        Args:
            observation_id: Canonical observation identifier.
            context_id:     Group 2 context identifier.
            ruling:         Temporal ruling value (e.g. "GAP").

        Returns:
            str: "abstention-" prefix + first 24 hex chars of sha256 digest.
        """
        canonical_payload = {
            "scheme": ABSTENTION_ID_SCHEME,
            "observation_id": observation_id,
            "context_id": context_id,
            "ruling": ruling,
        }
        canonical_json = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        return ABSTENTION_ID_PREFIX + digest[:ABSTENTION_ID_DIGEST_LEN]
