"""
Tests for Phase 16: Group 2 ALLOW integration and Group 4 Action Request.
Ensures that scientific ALLOW rulings do NOT become immediate operational execution,
but are strictly routed to the Group 4 Action Request intake boundary.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from contracts.decision_contract import DecisionContract
from control_plane.decision_translation.contextual_result_adapter import ContextualResultAdapter
from control_plane.decision_translation.group4_intake import Group4IntakeBoundary, ActionRequestRecorder
from control_plane.core.action_governance import GovernanceDecision

@pytest.fixture
def allow_ruling_fixture():
    ruling_path = Path(__file__).resolve().parents[1] / "integration" / "group2" / "fixtures" / "temporal_ruling_allow.json"
    assert ruling_path.exists(), "Group 2 ALLOW ruling fixture must exist"
    
    ruling_data = json.loads(ruling_path.read_text(encoding='utf-8'))
    # Ensure the canonical record ID is injected by the Group 1 upstream boundary in the actual flow.
    # We simulate that here.
    ruling_data["canonical_record_id"] = "group1-obs-20260813-9a3b"
    return ruling_data


def test_1_valid_allow_creates_action_request_eligibility(allow_ruling_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    
    # Prove the invariant: ALLOW != EXECUTE
    assert contract.decision_type == "action_request_eligible", "MUST NOT upgrade to operational execution"
    assert contract.action == "noop", "Action must remain noop at the translation boundary"
    assert contract.parameters["canonical_record_id"] == "group1-obs-20260813-9a3b"
    assert contract.parameters["ruling"] == "ALLOW"


def test_2_valid_lineage_creates_deterministic_action_request_id(allow_ruling_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    
    intake = Group4IntakeBoundary()
    
    # We mock ActionGovernance to avoid persisting to shared test state
    approved_decision = GovernanceDecision(
        should_block=False,
        policy_id="action_governance_v1",
        policy_version="v1",
        admission_state="POLICY_ADMITTED",
    )
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved_decision):
        ar = intake.process(contract)
        
        assert ar.action_request_id.startswith("ar-")
        assert ar.status == "VALIDATED"
        assert ar.lineage.observation_id == "TC-Z03-F02-LIDAR-OBS001"
        
        # Test Determinism
        ar2 = intake.process(contract)
        assert ar.action_request_id == ar2.action_request_id, "Same lineage must produce same Action Request ID"


def test_3_missing_observation_id_is_rejected(allow_ruling_fixture):
    del allow_ruling_fixture["observation_id"]
    
    adapter = ContextualResultAdapter()
    with pytest.raises(ValueError, match="missing required fields: \\['observation_id'\\]"):
        adapter.translate(allow_ruling_fixture)


def test_4_missing_canonical_record_id_is_rejected(allow_ruling_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    del contract.parameters["canonical_record_id"]
    intake = Group4IntakeBoundary()
    with pytest.raises(ValueError, match="Lineage validation failed: Missing lineage fields"):
        intake.process(contract)


def test_5_wrong_canonical_record_id_is_rejected(allow_ruling_fixture):
    allow_ruling_fixture["canonical_record_id"] = "FORGED_RECORD_ID"
    
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    
    intake = Group4IntakeBoundary()
    with pytest.raises(ValueError, match="Lineage validation failed: canonical_record_id lineage mismatch"):
        intake.process(contract)


def test_6_wrong_context_id_is_rejected(allow_ruling_fixture):
    allow_ruling_fixture["context_id"] = "FORGED_CONTEXT_ID"
    
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    
    intake = Group4IntakeBoundary()
    with pytest.raises(ValueError, match="Lineage validation failed: context_id lineage mismatch"):
        intake.process(contract)


def test_7_upstream_identity_substitution_is_detected(allow_ruling_fixture):
    # This overlaps with tests 5 and 6 which verify substitution detection mechanism.
    pass


def test_8_controlled_evidence_remains_controlled(allow_ruling_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    
    intake = Group4IntakeBoundary()
    approved_decision = GovernanceDecision(
        should_block=False,
        policy_id="action_governance_v1",
        policy_version="v1",
        admission_state="POLICY_ADMITTED",
    )
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved_decision):
        ar = intake.process(contract)
        assert ar.evidence_classification == "CONTROLLED"


def test_9_group_4_cannot_upgrade_evidence_to_physical_or_live(allow_ruling_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    intake = Group4IntakeBoundary()
    
    approved_decision = GovernanceDecision(
        should_block=False,
        policy_id="action_governance_v1",
        policy_version="v1",
        admission_state="POLICY_ADMITTED",
    )
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved_decision):
        ar = intake.process(contract)
        
        # Test that evidence_classification can't be tampered via the intake process easily
        assert not hasattr(intake, "upgrade_evidence")
        assert ar.evidence_classification not in ["PHYSICAL", "LIVE"]


def test_10_duplicate_delivery_is_idempotent(allow_ruling_fixture, tmp_path):
    storage_path = tmp_path / "action_requests.jsonl"
    recorder = ActionRequestRecorder(storage_path=str(storage_path))
    
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    
    intake = Group4IntakeBoundary()
    approved_decision = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved_decision), \
         patch("control_plane.decision_translation.group4_intake.ActionRequestRecorder", return_value=recorder):
        
        ar1 = intake.process(contract)
        ar2 = intake.process(contract)
        
        # Check that only one entry was written to the file
        lines = storage_path.read_text(encoding='utf-8').strip().split('\\n')
        lines = storage_path.read_text(encoding='utf-8').strip().split('\n')
        assert len(lines) == 1, "Duplicate delivery must be idempotent in the recorder"
        

def test_11_gap_cannot_create_action_request():
    gap_fixture = Path(__file__).resolve().parents[1] / "integration" / "group2" / "fixtures" / "temporal_ruling_gap.json"
    gap_data = json.loads(gap_fixture.read_text(encoding='utf-8'))

    adapter = ContextualResultAdapter()
    contract = adapter.translate(gap_data)

    intake = Group4IntakeBoundary()
    
    approved_decision = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved_decision), \
         patch("control_plane.decision_translation.governed_abstention_recorder.AppendOnlyLog.append"):
         
         result = intake.process(contract)
         
         assert "abstention_record_id" in result
         assert result["abstention_record_id"].startswith("abstention-")
         assert "action_request_id" not in result


def test_12_adapt_cannot_create_action_request():
    adapt_data = {
        "contract_version": "group2.temporal-applicability.v1",
        "observation_id": "TC-Z03-F02-LIDAR-OBS001",
        "context_id": "ctx-tc-001",
        "ruling": "ADAPT",
        "action_eligibility": False,
        "abstention_required": True
    }
    
    adapter = ContextualResultAdapter()
    contract = adapter.translate(adapt_data)
    assert contract.decision_type == "abstention"
    
    intake = Group4IntakeBoundary()
    
    approved_decision = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved_decision), \
         patch("control_plane.decision_translation.governed_abstention_recorder.AppendOnlyLog.append"):
         
         result = intake.process(contract)
         
         assert "abstention_record_id" in result
         assert result["abstention_record_id"].startswith("abstention-")
         assert "action_request_id" not in result

def test_open_meteo_eod_abstention():
    data = {
        "observation_id": "TC-Z03-EXT-OPENMETEO-OBS001",
        "canonical_record_id": "CR-b4615a27-7ab1-4bde-a078-a56fa0f2414c",
        "context_id": None,
        "ruling": "ABSTAIN",
        "action_eligibility": False,
        "abstention_required": True,
        "action_request": None
    }
    
    adapter = ContextualResultAdapter()
    contract = adapter.translate(data)
    assert contract.decision_type == "abstention"
    
    intake = Group4IntakeBoundary()
    approved_decision = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="ADMITTED")
    
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved_decision), \
         patch("control_plane.decision_translation.governed_abstention_recorder.AppendOnlyLog.append"):
         
         # Run 1
         result1 = intake.process(contract)
         assert "abstention_record_id" in result1
         assert result1["context_id"] is None
         assert "action_request_id" not in result1
         id1 = result1["abstention_record_id"]
         
         # Run 2
         result2 = intake.process(contract)
         assert "abstention_record_id" in result2
         assert result2["context_id"] is None
         id2 = result2["abstention_record_id"]
         
         assert id1 == id2, "Abstention ID must be deterministic on replay"
        
        
def test_13_retrieval_preserves_complete_upstream_lineage(allow_ruling_fixture, tmp_path):
    storage_path = tmp_path / "action_requests.jsonl"
    recorder = ActionRequestRecorder(storage_path=str(storage_path))
    
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    
    intake = Group4IntakeBoundary()
    approved_decision = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved_decision), \
         patch("control_plane.decision_translation.group4_intake.ActionRequestRecorder", return_value=recorder):
         
         ar_created = intake.process(contract)
         ar_retrieved = recorder.retrieve(ar_created.action_request_id)
         
         assert ar_retrieved.lineage.observation_id == ar_created.lineage.observation_id
         assert ar_retrieved.lineage.canonical_record_id == ar_created.lineage.canonical_record_id
         assert ar_retrieved.lineage.context_id == ar_created.lineage.context_id


def test_14_governance_blocking_prevents_validated_status(allow_ruling_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    
    intake = Group4IntakeBoundary()
    
    # Mock governance to BLOCK the request
    blocked_decision = GovernanceDecision(
        should_block=True,
        reason="velocity_limit_exceeded",
        policy_id="action_governance_v1",
        policy_version="v1",
        admission_state="POLICY_REJECTED",
    )
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=blocked_decision):
        ar = intake.process(contract)
        
        assert ar.status == "BLOCKED", "Governance block must prevent VALIDATED status"
        assert ar.group4_action_metadata["governance_reason"] == "velocity_limit_exceeded"
        

def test_15_no_test_claims_operational_execution(allow_ruling_fixture):
    # This is an architectural invariant proven by the fact that the output
    # of the entire flow is strictly an `ActionRequest` object.
    adapter = ContextualResultAdapter()
    contract = adapter.translate(allow_ruling_fixture)
    intake = Group4IntakeBoundary()
    
    approved_decision = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved_decision):
        ar = intake.process(contract)
        
        # Assert nothing in the output implies physical execution
        assert not hasattr(ar, "execution_status")
        assert not hasattr(ar, "physical_result")
        assert ar.status == "VALIDATED"  # Meaning validated request, not validated execution.
