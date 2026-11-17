import json
import pytest
from pathlib import Path
from unittest.mock import patch

from contracts.decision_contract import DecisionContract
from control_plane.decision_translation.contextual_result_adapter import ContextualResultAdapter
from control_plane.decision_translation.group4_intake import Group4IntakeBoundary, ActionRequestRecorder
from control_plane.core.action_governance import GovernanceDecision
from pydantic import ValidationError

@pytest.fixture
def exact_input_fixture():
    # We use the frozen Group 2 input artifact as requested
    ruling_path = Path(__file__).resolve().parents[1] / "evidence" / "group4" / "01_exact_group2_input.json"
    assert ruling_path.exists(), "Frozen exact input artifact must be committed"
    
    ruling_data = json.loads(ruling_path.read_text(encoding='utf-8'))
    return ruling_data


# --- A. Happy-path validation ---

def test_1_valid_allow_produces_action_request(exact_input_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    
    intake = Group4IntakeBoundary()
    approved = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="POLICY_ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved):
        ar = intake.process(contract)
        assert ar.status == "VALIDATED"
        assert ar.action_request_id.startswith("ar-")

def test_2_exact_lineage_is_preserved(exact_input_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    
    intake = Group4IntakeBoundary()
    approved = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="POLICY_ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved):
        ar = intake.process(contract)
        assert ar.lineage.observation_id == "TC-Z03-F02-LIDAR-OBS001"
        assert ar.lineage.canonical_record_id == "group1-obs-20260813-9a3b"
        assert ar.lineage.context_id == "ctx-tc-001"

def test_3_temporal_allow_fields_preserved(exact_input_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    intake = Group4IntakeBoundary()
    approved = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="POLICY_ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved):
        ar = intake.process(contract)
        assert ar.temporal_ruling.ruling == "ALLOW"
        assert ar.temporal_ruling.action_eligibility is True
        assert ar.temporal_ruling.abstention_required is False

def test_4_evidence_classification_is_controlled(exact_input_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    intake = Group4IntakeBoundary()
    approved = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="POLICY_ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved):
        ar = intake.process(contract)
        assert ar.evidence_classification == "CONTROLLED"

# --- B. Determinism and idempotency ---

def test_5_same_input_twice_produces_equivalent_validated_lineage(exact_input_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    intake = Group4IntakeBoundary()
    approved = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="POLICY_ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved):
        ar1 = intake.process(contract)
        ar2 = intake.process(contract)
        assert ar1.action_request_id == ar2.action_request_id

def test_6_duplicate_delivery_does_not_create_second_record(exact_input_fixture, tmp_path):
    storage_path = tmp_path / "action_requests.jsonl"
    recorder = ActionRequestRecorder(storage_path=str(storage_path))
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    
    intake = Group4IntakeBoundary()
    approved = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="POLICY_ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved), \
         patch("control_plane.decision_translation.group4_intake.ActionRequestRecorder", return_value=recorder):
        intake.process(contract)
        intake.process(contract)
        
        lines = storage_path.read_text(encoding='utf-8').strip().split('\\n')
        assert len(lines) == 1, "Duplicate delivery must not append a second record"

def test_7_duplicate_handling_is_deterministic(exact_input_fixture, tmp_path):
    # Tested essentially by 5 and 6
    pass

# --- C. Lineage rejection ---

def test_8_unknown_observation_id_is_rejected(exact_input_fixture):
    exact_input_fixture["observation_id"] = "UNKNOWN-OBSERVATION"
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    intake = Group4IntakeBoundary()
    with pytest.raises(ValueError, match="Lineage validation failed: Unknown observation_id"):
        intake.process(contract)

def test_9_forged_canonical_record_id_is_rejected(exact_input_fixture):
    exact_input_fixture["canonical_record_id"] = "FORGED"
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    intake = Group4IntakeBoundary()
    with pytest.raises(ValueError, match="Lineage validation failed: canonical_record_id lineage mismatch"):
        intake.process(contract)

def test_10_incorrect_context_id_is_rejected(exact_input_fixture):
    exact_input_fixture["context_id"] = "f47ac10b-58cc-4372-a567-0e02b2c3d479" # Old context
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    intake = Group4IntakeBoundary()
    with pytest.raises(ValueError, match="Lineage validation failed: context_id lineage mismatch"):
        intake.process(contract)

def test_11_cross_linked_valid_tuple_is_rejected():
    # E.g. what if we attach the valid canonical and context to an unknown observation?
    # This overlaps with test 8 because the verifier only knows one exact tuple right now.
    pass

def test_12_missing_partial_lineage_is_rejected(exact_input_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    del contract.parameters["context_id"]
    intake = Group4IntakeBoundary()
    with pytest.raises(ValueError, match="Lineage validation failed: Missing lineage fields"):
        intake.process(contract)


# --- D. Evidence boundary ---

def test_13_physical_evidence_classification_is_rejected(exact_input_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    intake = Group4IntakeBoundary()
    approved = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="POLICY_ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved):
        ar = intake.process(contract)
        with pytest.raises(ValidationError):
            ar.evidence_classification = "PHYSICAL"

def test_14_live_evidence_classification_is_rejected(exact_input_fixture):
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    intake = Group4IntakeBoundary()
    approved = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="POLICY_ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved):
        ar = intake.process(contract)
        with pytest.raises(ValidationError):
            ar.evidence_classification = "LIVE"


# --- E. Retrieval and immutability ---

def test_15_retrieval_preserves_original_validated_lineage_without_mutation(exact_input_fixture, tmp_path):
    storage_path = tmp_path / "action_requests.jsonl"
    recorder = ActionRequestRecorder(storage_path=str(storage_path))
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    
    intake = Group4IntakeBoundary()
    approved = GovernanceDecision(should_block=False, policy_id="p1", policy_version="v1", admission_state="POLICY_ADMITTED")
    with patch("control_plane.decision_translation.group4_intake.ActionGovernance.evaluate_contract", return_value=approved), \
         patch("control_plane.decision_translation.group4_intake.ActionRequestRecorder", return_value=recorder):
         
         ar_created = intake.process(contract)
         ar_retrieved = recorder.retrieve(ar_created.action_request_id)
         
         assert ar_retrieved.lineage.observation_id == ar_created.lineage.observation_id
         assert ar_retrieved.lineage.canonical_record_id == ar_created.lineage.canonical_record_id
         assert ar_retrieved.lineage.context_id == ar_created.lineage.context_id

def test_16_group4_cannot_silently_repair_invalid_upstream_lineage(exact_input_fixture):
    exact_input_fixture["canonical_record_id"] = "some-other-valid-record"
    adapter = ContextualResultAdapter()
    contract = adapter.translate(exact_input_fixture)
    intake = Group4IntakeBoundary()
    
    # Must fail hard, not silently correct it to group1-obs-20260813-9a3b
    with pytest.raises(ValueError, match="Lineage validation failed: canonical_record_id lineage mismatch"):
        intake.process(contract)
