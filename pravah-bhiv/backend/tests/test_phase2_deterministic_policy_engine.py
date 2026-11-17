import pytest

from contracts.decision_contract import validate_decision_contract
from contracts.execution_contract import build_execution_contract
from control_plane.core.action_governance import ActionGovernance
from control_plane.security.deterministic_policy_engine import (
    AdmissionState,
    DeterministicExecutionRejection,
    DeterministicPolicyEngine,
    PolicyAdmissionRequest,
    RejectionCode,
)


def _decision(action: str = "restart", version: str = "v1"):
    return validate_decision_contract(
        {
            "decision_type": "execution",
            "action": action,
            "parameters": {"service_id": "svc-1"},
            "version": version,
        }
    )


def _engine(tmp_path):
    return DeterministicPolicyEngine(
        policy_id="action_governance_v1",
        runtime_policy_version="v1",
        policy_definition={
            "env": "dev",
            "cooldown_periods": {"restart": 0, "noop": 0},
            "repetition_limit": 3,
            "repetition_window": 300,
            "eligibility_rules": ["restart", "noop"],
            "allowed_actions": ["restart", "noop"],
            "allowed_environments": ["dev"],
        },
        log_path=tmp_path / "policy_enforcement.jsonl",
    )


def test_policy_engine_approves_signed_governance_contract(tmp_path):
    engine = _engine(tmp_path)
    decision_contract = _decision()
    governance_contract = engine.build_governance_contract(
        governance_approver="sarathi",
        constraints=engine.policy_definition,
    )

    admission = engine.admit(
        PolicyAdmissionRequest(
            action=decision_contract.action,
            context={"env": "dev", "service_id": "svc-1"},
            policy_version="v1",
            runtime_policy_version="v1",
            governance_contract=governance_contract,
            decision_contract=decision_contract,
            policy_id="action_governance_v1",
        )
    )

    assert admission.allowed is True
    assert admission.state is AdmissionState.POLICY_APPROVED
    assert admission.rejection_code is None


def test_policy_engine_rejects_version_mismatch(tmp_path):
    engine = _engine(tmp_path)
    decision_contract = _decision()
    governance_contract = engine.build_governance_contract(
        governance_approver="sarathi",
        constraints=engine.policy_definition,
    )

    admission = engine.admit(
        PolicyAdmissionRequest(
            action=decision_contract.action,
            context={"env": "dev", "service_id": "svc-1"},
            policy_version="v2",
            runtime_policy_version="v1",
            governance_contract=governance_contract,
            decision_contract=decision_contract,
            policy_id="action_governance_v1",
        )
    )

    assert admission.allowed is False
    assert admission.state is AdmissionState.POLICY_VERSION_MISMATCH
    assert admission.rejection_code is RejectionCode.POLICY_VERSION_MISMATCH


def test_policy_engine_rejects_missing_governance_contract(tmp_path):
    engine = _engine(tmp_path)
    decision_contract = _decision()

    admission = engine.admit(
        PolicyAdmissionRequest(
            action=decision_contract.action,
            context={"env": "dev", "service_id": "svc-1"},
            policy_version="v1",
            runtime_policy_version="v1",
            governance_contract=None,
            decision_contract=decision_contract,
            policy_id="action_governance_v1",
        )
    )

    assert admission.allowed is False
    assert admission.state is AdmissionState.GOVERNANCE_REQUIRED
    assert admission.rejection_code is RejectionCode.POLICY_MISSING


def test_policy_engine_rejects_invalid_signature(tmp_path):
    engine = _engine(tmp_path)
    decision_contract = _decision()
    governance_contract = engine.build_governance_contract(
        governance_approver="sarathi",
        constraints=engine.policy_definition,
    )
    tampered_contract = {**governance_contract.__dict__, "signature": "broken"}

    admission = engine.admit(
        PolicyAdmissionRequest(
            action=decision_contract.action,
            context={"env": "dev", "service_id": "svc-1"},
            policy_version="v1",
            runtime_policy_version="v1",
            governance_contract=tampered_contract,
            decision_contract=decision_contract,
            policy_id="action_governance_v1",
        )
    )

    assert admission.allowed is False
    assert admission.state is AdmissionState.POLICY_SIGNATURE_INVALID
    assert admission.rejection_code is RejectionCode.INVALID_SIGNATURE


def test_policy_engine_rejects_disallowed_action(tmp_path):
    engine = _engine(tmp_path)
    disallowing_contract = engine.build_governance_contract(
        governance_approver="sarathi",
        constraints={
            **engine.policy_definition,
            "allowed_actions": ["noop"],
        },
    )
    decision_contract = _decision(action="restart")

    admission = engine.admit(
        PolicyAdmissionRequest(
            action=decision_contract.action,
            context={"env": "dev", "service_id": "svc-1"},
            policy_version="v1",
            runtime_policy_version="v1",
            governance_contract=disallowing_contract,
            decision_contract=decision_contract,
            policy_id="action_governance_v1",
        )
    )

    assert admission.allowed is False
    assert admission.state is AdmissionState.EXECUTION_DENIED
    assert admission.rejection_code is RejectionCode.EXECUTION_NOT_PERMITTED


def test_policy_engine_validates_execution_contract(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    decision_contract = _decision()
    governance_contract = engine.build_governance_contract(
        governance_approver="sarathi",
        constraints=engine.policy_definition,
    )

    from control_plane.core import execution_lineage as lineage_module

    lineage_log = tmp_path / "execution_lineage.jsonl"
    monkeypatch.setattr(lineage_module, "get_lineage_log_path", lambda: lineage_log)
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX", {})
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX_LOADED", False)

    execution_contract = build_execution_contract(
        decision_contract=decision_contract,
        execution_payload={
            "service_id": "svc-1",
            "action": decision_contract.action,
            "execution_id": "execution-1",
        },
        approved_by="sarathi",
        policy_snapshot={
            "policy_id": "action_governance_v1",
            "policy_version": "v1",
            "policy_hash": engine.policy_hash,
        },
    )

    admission = engine.admit(
        PolicyAdmissionRequest(
            action=decision_contract.action,
            context={
                "env": "dev",
                "service_id": "svc-1",
                "action": decision_contract.action,
                "execution_payload": execution_contract.execution_payload,
            },
            policy_version="v1",
            runtime_policy_version="v1",
            governance_contract=governance_contract,
            decision_contract=decision_contract,
            execution_contract=execution_contract,
            policy_id="action_governance_v1",
        )
    )

    assert admission.allowed is True
    assert admission.execution_contract is not None

    tampered_admission = engine.admit(
        PolicyAdmissionRequest(
            action=decision_contract.action,
            context={
                "env": "dev",
                "service_id": "different-service",
                "action": decision_contract.action,
                "execution_payload": execution_contract.execution_payload,
            },
            policy_version="v1",
            runtime_policy_version="v1",
            governance_contract=governance_contract,
            decision_contract=decision_contract,
            execution_contract=execution_contract.model_copy(
                update={
                    "execution_hash": "broken",
                }
            ),
            policy_id="action_governance_v1",
        )
    )

    assert tampered_admission.allowed is False
    assert tampered_admission.rejection_code is RejectionCode.CONTRACT_VIOLATION


def test_action_governance_wraps_rejection_metadata(tmp_path):
    governance = ActionGovernance(env="prod")
    governance._policy_engine.log_path = tmp_path / "policy_enforcement.jsonl"

    decision = _decision(action="scale_up")
    result = governance.evaluate_contract(
        decision,
        context={"env": "prod", "service_id": "svc-1"},
        source="tester",
    )

    assert result.should_block is True
    assert result.admission_state in {AdmissionState.POLICY_REJECTED.value, AdmissionState.EXECUTION_DENIED.value}
    assert result.rejection_code in {
        RejectionCode.EXECUTION_NOT_PERMITTED.value,
        RejectionCode.GOVERNANCE_REJECTED.value,
    }
