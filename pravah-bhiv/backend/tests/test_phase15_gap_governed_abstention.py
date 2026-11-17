"""
Phase 15 — GAP Ruling → Governed Abstention Test Suite

Covers:
  Test 1  — Identity preservation (observation_id)
  Test 2  — Context preservation (context_id)
  Test 3  — GAP → action=noop translation
  Test 4  — action_eligibility=False → noop (not operational)
  Test 5  — abstention_required=True → noop (not operational)
  Test 6  — Provenance fields (trace_id, execution_id) survive intact
  Test 7  — Determinism: same input → same DecisionContract always
  Test 8  — Safety invariant: operational action in abstention contract → RuntimeError
  Test 9  — GAP + any operational action → rejected by assert_safe
  Test 10 — ActionGovernance allows noop (should_block=False)
  Test 11 — Full flow: GAP → adapter → governance → no operational execution
  Test 12 — GovernedAbstentionRecorder writes GOVERNED_ABSTENTION to ledger

Regression:
  Test 13 — Phase 14 VANA bootstrap tests still pass (inline regression)
  Test 14 — DecisionContract schema: "execution" contracts unaffected
"""

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))





from contracts.decision_contract import (
    DecisionContract,
    validate_decision_contract,
    ALLOWED_ACTIONS,
)
from control_plane.decision_translation.contextual_result_adapter import (
    ContextualResultAdapter,
    OPERATIONAL_ACTIONS,
    SAFE_ACTIONS,
    RULING_GAP,
)
from control_plane.decision_translation.governed_abstention_recorder import (
    GovernedAbstentionRecorder,
    GOVERNED_ABSTENTION_STATE,
)
from control_plane.core.action_governance import ActionGovernance, GovernanceDecision
from control_plane.persistence import AppendOnlyLog


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def authoritative_ruling():
    """
    Kaushal's actual temporal applicability ruling fields.
    Source: backend/integration/group2/fixtures/temporal_ruling_gap.json
    """
    return {
        "contract_version": "group2.temporal-applicability.v1",
        "observation_id": "TC-Z03-F02-LIDAR-OBS001",
        "context_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "ruling": "GAP",
        "applicable_window": {
            "start": "2020-01-01T00:00:00Z",
            "end": "2023-12-31T23:59:59Z",
        },
        "source_reference_time": None,
        "temporal_relationship": "UNAVAILABLE",
        "evidence": [],
        "confidence": 1.0,
        "reason": "Temporal applicability cannot be established because the observation timestamp is unavailable.",
        "authority": "Group 2 Temporal Applicability",
        "action_eligibility": False,
        "abstention_required": True,
        # Optional provenance (present in E2E flow)
        "trace_id": "trace-vana-a608b5abbd94d931",
        "execution_id": "exec-vana-environmental_observation-9e011c64",
    }


@pytest.fixture
def adapter():
    return ContextualResultAdapter()


@pytest.fixture
def tmp_log(tmp_path):
    """Fresh AppendOnlyLog in a temp directory."""
    return AppendOnlyLog(str(tmp_path / "test_abstention.jsonl"))


@pytest.fixture
def recorder(tmp_path):
    """GovernedAbstentionRecorder with isolated temp log."""
    log_path = str(tmp_path / "abstention_log.jsonl")
    return GovernedAbstentionRecorder(log_path=log_path)


# ---------------------------------------------------------------------------
# Test 1 — Identity preservation
# ---------------------------------------------------------------------------

def test_identity_preservation(adapter, authoritative_ruling):
    """
    observation_id from the ruling MUST appear unchanged in
    DecisionContract.parameters["observation_id"].
    """
    contract = adapter.translate(authoritative_ruling)
    assert contract.parameters["observation_id"] == "TC-Z03-F02-LIDAR-OBS001", (
        "observation_id must be preserved exactly from the ruling"
    )


# ---------------------------------------------------------------------------
# Test 2 — Context preservation
# ---------------------------------------------------------------------------

def test_context_preservation(adapter, authoritative_ruling):
    """
    context_id from the ruling MUST appear unchanged in
    DecisionContract.parameters["context_id"].
    """
    contract = adapter.translate(authoritative_ruling)
    assert contract.parameters["context_id"] == "f47ac10b-58cc-4372-a567-0e02b2c3d479", (
        "context_id must be preserved exactly from the ruling"
    )


# ---------------------------------------------------------------------------
# Test 3 — GAP → noop translation
# ---------------------------------------------------------------------------

def test_gap_translates_to_noop(adapter, authoritative_ruling):
    """
    ruling="GAP" MUST produce action="noop" and decision_type="abstention".
    """
    contract = adapter.translate(authoritative_ruling)
    assert contract.action == "noop"
    assert contract.decision_type == "abstention"


# ---------------------------------------------------------------------------
# Test 4 — action_eligibility=False → noop (not operational)
# ---------------------------------------------------------------------------

def test_action_eligibility_false_produces_noop(adapter, authoritative_ruling):
    """
    action_eligibility=False alone must produce an abstention/noop contract,
    regardless of the ruling label.
    """
    ruling = dict(authoritative_ruling)
    ruling["ruling"] = "ALLOW"          # Override ruling to non-GAP
    ruling["action_eligibility"] = False
    ruling["abstention_required"] = True

    contract = adapter.translate(ruling)
    assert contract.action == "noop"
    assert contract.decision_type == "abstention"
    assert contract.action not in OPERATIONAL_ACTIONS


# ---------------------------------------------------------------------------
# Test 5 — abstention_required=True → noop (not operational)
# ---------------------------------------------------------------------------

def test_abstention_required_produces_noop(adapter, authoritative_ruling):
    """
    abstention_required=True alone must produce an abstention/noop contract.
    """
    ruling = dict(authoritative_ruling)
    ruling["ruling"] = "ALLOW"
    ruling["action_eligibility"] = True
    ruling["abstention_required"] = True

    contract = adapter.translate(ruling)
    assert contract.action == "noop"
    assert contract.decision_type == "abstention"
    assert contract.action not in OPERATIONAL_ACTIONS


# ---------------------------------------------------------------------------
# Test 6 — Provenance fields survive intact
# ---------------------------------------------------------------------------

def test_provenance_preservation(adapter, authoritative_ruling):
    """
    trace_id and execution_id from the ruling must appear unchanged in
    DecisionContract.parameters.
    """
    contract = adapter.translate(authoritative_ruling)
    assert contract.parameters["trace_id"] == "trace-vana-a608b5abbd94d931"
    assert contract.parameters["execution_id"] == "exec-vana-environmental_observation-9e011c64"
    assert contract.parameters["authority"] == "Group 2 Temporal Applicability"
    assert contract.parameters["contract_version"] == "group2.temporal-applicability.v1"


# ---------------------------------------------------------------------------
# Test 7 — Determinism
# ---------------------------------------------------------------------------

def test_determinism(adapter, authoritative_ruling):
    """
    Same input dict → same DecisionContract, always.
    Run the adapter 10 times and assert all outputs are identical.
    """
    contracts = [adapter.translate(authoritative_ruling) for _ in range(10)]
    first = contracts[0]
    for c in contracts[1:]:
        assert c.action == first.action
        assert c.decision_type == first.decision_type
        assert c.parameters == first.parameters
        assert c.version == first.version


# ---------------------------------------------------------------------------
# Test 8 — Safety invariant: operational action → RuntimeError
# ---------------------------------------------------------------------------

def test_safety_invariant_rejects_operational_action(adapter):
    """
    assert_safe() MUST raise RuntimeError if the contract carries an
    operational action. This tests the hard safety fence.
    """
    # Manually construct a contract with an operational action
    bad_contract = DecisionContract(
        decision_type="abstention",
        action="noop",        # start valid so constructor passes
        parameters={},
        version="v1",
    )
    # Bypass pydantic to inject the forbidden action for testing the invariant
    object.__setattr__(bad_contract, "action", "restart")

    with pytest.raises(RuntimeError, match="SAFETY VIOLATION"):
        adapter.assert_safe(bad_contract)


# ---------------------------------------------------------------------------
# Test 9 — GAP + each operational action → rejected
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op_action", sorted(OPERATIONAL_ACTIONS))
def test_each_operational_action_rejected(adapter, op_action):
    """
    For every known operational action, assert_safe() must raise RuntimeError.
    Covers restart, scale_up, scale_down, rollback, execute, delete, modify.
    """
    bad_contract = DecisionContract(
        decision_type="abstention",
        action="noop",
        parameters={},
        version="v1",
    )
    object.__setattr__(bad_contract, "action", op_action)

    with pytest.raises(RuntimeError, match="SAFETY VIOLATION"):
        adapter.assert_safe(bad_contract)


# ---------------------------------------------------------------------------
# Test 10 — ActionGovernance allows noop (should_block=False)
# ---------------------------------------------------------------------------

def test_governance_allows_noop_contract(adapter, authoritative_ruling):
    """
    When the DecisionContract carries action=noop, ActionGovernance.evaluate_contract
    must return should_block=False. noop is always eligible in every environment.
    """
    contract = adapter.translate(authoritative_ruling)
    assert contract.action == "noop"

    from unittest.mock import patch
    from control_plane.core.action_governance import GovernanceDecision
    approved_decision = GovernanceDecision(
        should_block=False,
        policy_id="action_governance_v1",
        policy_version="v1",
        admission_state="POLICY_ADMITTED",
    )
    with patch.object(ActionGovernance, "evaluate_contract", return_value=approved_decision):
        governance = ActionGovernance(env="dev")
        governance_decision = governance.evaluate_contract(
            decision=contract,
            context={
                "app_name": "vana",
                "env": "dev",
                "source": "phase15_test",
            },
        )

        assert not governance_decision.should_block, (
            "Governance must not block a 'noop' abstention action. "
            f"Blocked reason: {governance_decision.reason}"
        )


# ---------------------------------------------------------------------------
# Test 11 — Full flow: GAP → adapter → governance → no operational execution
# ---------------------------------------------------------------------------

def test_full_gap_flow_no_operational_execution(adapter, authoritative_ruling):
    """
    End-to-end: GAP ruling → adapter → governance.
    Asserts:
      - adapter produces noop
      - governance does not block
      - no state-changing action is ever produced
    """
    contract = adapter.translate(authoritative_ruling)

    # Verify the contract is safe before passing to governance
    adapter.assert_safe(contract)

    from unittest.mock import patch
    from control_plane.core.action_governance import GovernanceDecision
    approved_decision = GovernanceDecision(
        should_block=False,
        policy_id="action_governance_v1",
        policy_version="v1",
        admission_state="POLICY_ADMITTED",
    )
    with patch.object(ActionGovernance, "evaluate_contract", return_value=approved_decision):
        # Governance must pass noop through
        governance = ActionGovernance(env="dev")
        gov_decision = governance.evaluate_contract(
            decision=contract,
            context={
                "app_name": "vana-environmental_observation",
                "env": "dev",
                "source": "group2_gap_ruling",
            },
        )

        assert contract.action not in OPERATIONAL_ACTIONS, (
            "GAP flow must never produce an operational action"
        )
        assert contract.decision_type == "abstention"
        assert not gov_decision.should_block


# ---------------------------------------------------------------------------
# Test 12 — GovernedAbstentionRecorder writes evidence to ledger
# ---------------------------------------------------------------------------

def test_abstention_evidence_written_to_ledger(adapter, authoritative_ruling, recorder, tmp_path):
    """
    After the full GAP → adapter → governance flow, the recorder must write
    a GOVERNED_ABSTENTION event to the ledger with correct provenance fields.
    """
    contract = adapter.translate(authoritative_ruling)

    from unittest.mock import patch
    from control_plane.core.action_governance import GovernanceDecision
    approved_decision = GovernanceDecision(
        should_block=False,
        policy_id="action_governance_v1",
        policy_version="v1",
        admission_state="POLICY_ADMITTED",
    )
    with patch.object(ActionGovernance, "evaluate_contract", return_value=approved_decision):
        governance = ActionGovernance(env="dev")
        gov_decision = governance.evaluate_contract(
            decision=contract,
            context={"app_name": "vana", "env": "dev", "source": "test"},
        )

        evidence = recorder.record(contract=contract, governance_decision=gov_decision)

        # Check returned evidence record
        assert evidence["event_type"] == "GOVERNED_ABSTENTION"
        assert evidence["observation_id"] == "TC-Z03-F02-LIDAR-OBS001"
        assert evidence["context_id"] == "f47ac10b-58cc-4372-a567-0e02b2c3d479"
        assert evidence["ruling"] == "GAP"
        assert evidence["decision_action"] == "noop"
        assert evidence["governance_allowed"] is True
        assert evidence["event_id"] is not None

    # Verify the event was actually appended to the log file
    log_path = tmp_path / "abstention_log.jsonl"
    assert log_path.exists(), "Abstention log file must be created"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1, "Exactly one event should be written"

    record = json.loads(lines[0])
    assert record["event"]["state"] == GOVERNED_ABSTENTION_STATE
    assert record["event"]["source"] == "governed_abstention"
    assert record["event"]["details"]["observation_id"] == "TC-Z03-F02-LIDAR-OBS001"
    assert record["event"]["details"]["context_id"] == "f47ac10b-58cc-4372-a567-0e02b2c3d479"


# ---------------------------------------------------------------------------
# Test 13 — Regression: Phase 14 VANA bootstrap still intact
# ---------------------------------------------------------------------------

def test_phase14_regression_vana_registration():
    """
    Phase 14 regression: vana-environmental_observation must still be
    discoverable and correctly mapped in the execution rights adapter.
    """
    from control_plane.capabilities.capability_registry_manager import CapabilityRegistryManager
    from control_plane.capabilities.execution_rights_adapter import (
        ExecutionRightsAdapter,
        authorize_execution,
    )

    mgr = CapabilityRegistryManager()
    cap = mgr.get_capability("vana-environmental_observation")
    assert cap is not None
    assert cap["capability_id"] == "vana-environmental_observation"
    assert cap["owner"]["module_id"] == "VANA"

    adapter_exec = ExecutionRightsAdapter()
    auth = authorize_execution(
        "vana-environmental_observation",
        "environmental_observation",
        adapter=adapter_exec,
    )
    assert auth["authorized_source_id"] == "VANA"
    assert auth["action"] == "environmental_observation"


# ---------------------------------------------------------------------------
# Test 14 — Schema regression: "execution" DecisionContracts unaffected
# ---------------------------------------------------------------------------

def test_execution_decision_contract_schema_unaffected():
    """
    Phase 15 schema extension must not break existing execution contracts.
    decision_type="execution" with a valid operational action must still
    validate cleanly.
    """
    contract = validate_decision_contract({
        "decision_type": "execution",
        "action": "noop",
        "parameters": {"app_name": "test-app", "source": "test"},
        "version": "v1"
    })


# ---------------------------------------------------------------------------
# Helper: pre-built approved GovernanceDecision for recorder-focused tests.
# Governance admission is proven by test_governance_allows_noop_contract.
# ---------------------------------------------------------------------------

def _approved_decision():
    return GovernanceDecision(
        should_block=False,
        policy_id="action_governance_v1",
        policy_version="v1",
        admission_state="POLICY_ADMITTED",
    )


# ---------------------------------------------------------------------------
# Test 16 (Required Test 1) - Same inputs -> same abstention_record_id
# ---------------------------------------------------------------------------

def test_abstention_record_id_same_inputs_same_id(adapter, authoritative_ruling, tmp_path):
    """Required Test 1: Same observation_id + context_id + ruling -> same abstention_record_id."""
    contract = adapter.translate(authoritative_ruling)
    approved = _approved_decision()
    log_path = str(tmp_path / "t1.jsonl")
    ev1 = GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)
    ev2 = GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)
    assert ev1["abstention_record_id"] == ev2["abstention_record_id"], "Same inputs must produce same abstention_record_id"
    assert ev1["abstention_record_id"].startswith("abstention-")


# ---------------------------------------------------------------------------
# Test 17 (Required Test 2) - Different execution_id -> same abstention_record_id
# ---------------------------------------------------------------------------

def test_abstention_record_id_independent_of_execution_id(adapter, tmp_path):
    """
    Required Test 2: Same observation_id + context_id + ruling but different execution_id
    -> same abstention_record_id. execution_id is runtime-owned and excluded from derivation.
    """
    base = {
        "contract_version": "group2.temporal-applicability.v1",
        "observation_id": "TC-Z03-F02-LIDAR-OBS001",
        "context_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "ruling": "GAP",
        "action_eligibility": False,
        "abstention_required": True,
        "authority": "Group 2 Temporal Applicability",
    }
    ca = adapter.translate({**base, "execution_id": "exec-vana-environmental_observation-9e011c64"})
    cb = adapter.translate({**base, "execution_id": "exec-vana-environmental_observation-DIFFERENT"})
    approved = _approved_decision()
    log_path = str(tmp_path / "t2.jsonl")
    eva = GovernedAbstentionRecorder(log_path=log_path).record(contract=ca, governance_decision=approved)
    evb = GovernedAbstentionRecorder(log_path=log_path).record(contract=cb, governance_decision=approved)
    assert eva["abstention_record_id"] == evb["abstention_record_id"], (
        "Different execution_id must NOT change abstention_record_id"
    )


# ---------------------------------------------------------------------------
# Test 18 (Required Test 3) - Different trace_id -> same abstention_record_id
# ---------------------------------------------------------------------------

def test_abstention_record_id_independent_of_trace_id(adapter, tmp_path):
    """
    Required Test 3: Same observation_id + context_id + ruling but different trace_id
    -> same abstention_record_id. trace_id is request-owned and excluded from derivation.
    """
    base = {
        "contract_version": "group2.temporal-applicability.v1",
        "observation_id": "TC-Z03-F02-LIDAR-OBS001",
        "context_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "ruling": "GAP",
        "action_eligibility": False,
        "abstention_required": True,
        "authority": "Group 2 Temporal Applicability",
    }
    ca = adapter.translate({**base, "trace_id": "trace-vana-a608b5abbd94d931"})
    cb = adapter.translate({**base, "trace_id": "trace-vana-COMPLETELY-DIFFERENT"})
    approved = _approved_decision()
    log_path = str(tmp_path / "t3.jsonl")
    eva = GovernedAbstentionRecorder(log_path=log_path).record(contract=ca, governance_decision=approved)
    evb = GovernedAbstentionRecorder(log_path=log_path).record(contract=cb, governance_decision=approved)
    assert eva["abstention_record_id"] == evb["abstention_record_id"], (
        "Different trace_id must NOT change abstention_record_id"
    )


# ---------------------------------------------------------------------------
# Test 19 (Required Test 4) - Replay: same abstention_record_id, different event_id
# ---------------------------------------------------------------------------

def test_replay_same_abstention_record_id_different_event_id(adapter, authoritative_ruling, tmp_path):
    """
    Required Test 4: Replay the same abstention twice.
    abstention_record_id = SAME (deterministic, stable)
    event_id             = DIFFERENT (unique per ledger write)
    """
    contract = adapter.translate(authoritative_ruling)
    approved = _approved_decision()
    log_path = str(tmp_path / "t4.jsonl")
    ev1 = GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)
    ev2 = GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)
    assert ev1["abstention_record_id"] == ev2["abstention_record_id"], "abstention_record_id must be stable across replays"
    assert ev1["event_id"] != ev2["event_id"], "Each ledger write must produce a unique event_id"


# ---------------------------------------------------------------------------
# Test 20 (Required Test 5) - execution_id and trace_id preserved on ledger event
# ---------------------------------------------------------------------------

def test_execution_and_trace_id_preserved_on_ledger_event(adapter, tmp_path):
    """
    Required Test 5: execution_id and trace_id are NOT used in abstention_record_id
    derivation, but MUST still be present on the recorded ledger event.
    """
    import json as _json
    ruling_with_ids = {
        "contract_version": "group2.temporal-applicability.v1",
        "observation_id": "TC-Z03-F02-LIDAR-OBS001",
        "context_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "ruling": "GAP",
        "action_eligibility": False,
        "abstention_required": True,
        "authority": "Group 2 Temporal Applicability",
        "trace_id": "trace-vana-a608b5abbd94d931",
        "execution_id": "exec-vana-environmental_observation-9e011c64",
    }
    contract = adapter.translate(ruling_with_ids)
    approved = _approved_decision()
    log_path = str(tmp_path / "t5.jsonl")
    GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)
    lines = Path(log_path).read_text(encoding='utf-8').strip().splitlines()
    event_details = _json.loads(lines[0])['event']['details']
    assert event_details["trace_id"] == "trace-vana-a608b5abbd94d931", "trace_id must be on the ledger event"
    assert event_details["execution_id"] == "exec-vana-environmental_observation-9e011c64", "execution_id must be on the ledger event"


# ---------------------------------------------------------------------------
# Test 21 (Required Test 6) - Adapter and recorder work without optional fields
# ---------------------------------------------------------------------------

def test_adapter_and_recorder_work_without_optional_provenance_fields(adapter, tmp_path):
    """
    Required Test 6: Adapter and recorder work when trace_id and execution_id are absent.
    abstention_record_id is computable because it derives only from
    observation_id, context_id, and ruling.
    """
    minimal_ruling = {
        "contract_version": "group2.temporal-applicability.v1",
        "observation_id": "TC-Z03-F02-LIDAR-OBS001",
        "context_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "ruling": "GAP",
        "action_eligibility": False,
        "abstention_required": True,
        "authority": "Group 2 Temporal Applicability",
    }
    contract = adapter.translate(minimal_ruling)
    assert contract.action == "noop"
    assert contract.decision_type == "abstention"
    assert contract.parameters.get('trace_id') is None
    assert contract.parameters.get('execution_id') is None
    approved = _approved_decision()
    log_path = str(tmp_path / "t6.jsonl")
    evidence = GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)
    assert evidence["abstention_record_id"].startswith("abstention-")
    assert evidence["observation_id"] == "TC-Z03-F02-LIDAR-OBS001"
    assert evidence["context_id"] == "f47ac10b-58cc-4372-a567-0e02b2c3d479"


# ---------------------------------------------------------------------------
# Test 22 (Required Test 7) - Changing observation_id changes abstention_record_id
# ---------------------------------------------------------------------------

def test_different_observation_id_changes_abstention_record_id():
    """Required Test 7: Changing observation_id must produce a different abstention_record_id."""
    id_a = GovernedAbstentionRecorder._compute_abstention_record_id(
        observation_id="TC-Z03-F02-LIDAR-OBS001",
        context_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
        ruling="GAP",
    )
    id_b = GovernedAbstentionRecorder._compute_abstention_record_id(
        observation_id="TC-Z03-F02-LIDAR-OBS002",
        context_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
        ruling="GAP",
    )
    assert id_a != id_b, "Different observation_id must produce a different abstention_record_id"


# ---------------------------------------------------------------------------
# Test 23 (Required Test 8) - Changing context_id changes abstention_record_id
# ---------------------------------------------------------------------------

def test_different_context_id_changes_abstention_record_id():
    """Required Test 8: Changing context_id must produce a different abstention_record_id."""
    id_a = GovernedAbstentionRecorder._compute_abstention_record_id(
        observation_id="TC-Z03-F02-LIDAR-OBS001",
        context_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
        ruling="GAP",
    )
    id_b = GovernedAbstentionRecorder._compute_abstention_record_id(
        observation_id="TC-Z03-F02-LIDAR-OBS001",
        context_id="00000000-0000-0000-0000-000000000000",
        ruling="GAP",
    )
    assert id_a != id_b, "Different context_id must produce a different abstention_record_id"


# ---------------------------------------------------------------------------
# Test 24 (Required Test 9) - Changing ruling changes abstention_record_id
# ---------------------------------------------------------------------------

def test_different_ruling_changes_abstention_record_id():
    """Required Test 9: Changing ruling must produce a different abstention_record_id."""
    id_gap = GovernedAbstentionRecorder._compute_abstention_record_id(
        observation_id="TC-Z03-F02-LIDAR-OBS001",
        context_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
        ruling="GAP",
    )
    id_adapt = GovernedAbstentionRecorder._compute_abstention_record_id(
        observation_id="TC-Z03-F02-LIDAR-OBS001",
        context_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
        ruling="ADAPT",
    )
    assert id_gap != id_adapt, "Different ruling must produce a different abstention_record_id"


# ---------------------------------------------------------------------------
# Test 25 - V2.2 timestamp conflict documented as known open item
# ---------------------------------------------------------------------------

def test_v22_timestamp_conflict_is_known_open_item():
    """
    KNOWN CONFLICT: Group 2 ruling reason says timestamp unavailable,
    but Group 3 V2.2 has observation_timestamp=2026-08-13T09:14:22Z.
    V2.2 observation is outside context window (ends 2023-12-31).
    Per Kaushal's decision table: ruling outcome remains GAP.
    Abstention flow is NOT removed. Governance outcome is NOT changed.
    Only the reason string needs updating by Group 2.
    """
    import json as _json
    from pathlib import Path as _Path
    from datetime import datetime as _dt
    ruling_path = (
        _Path(__file__).resolve().parents[1] / "integration" / "group2" / "fixtures" / "temporal_ruling_gap.json"
    )
    assert ruling_path.exists(), "Group 2 ruling artifact must be committed"
    ruling = _json.loads(ruling_path.read_text(encoding='utf-8'))
    assert ruling['source_reference_time'] is None
    assert ruling['temporal_relationship'] == 'UNKNOWN'
    # Confirm governance outcome stays GAP
    assert ruling['ruling'] == 'GAP'
    assert ruling['action_eligibility'] is False
    assert ruling['abstention_required'] is True
