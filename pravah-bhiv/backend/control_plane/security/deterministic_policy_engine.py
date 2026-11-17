from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from contracts.decision_contract import DecisionContract, validate_decision_contract
from contracts.execution_contract import ExecutionContract, validate_execution_contract
from contracts.policy_snapshot import PolicySnapshot, compute_policy_hash


DEFAULT_POLICY_SIGNING_KEY = os.getenv(
    "POLICY_SIGNING_KEY",
    "pravah-deterministic-policy-key",
).encode("utf-8")


class RejectionCode(Enum):
    POLICY_MISSING = "POLICY_MISSING"
    POLICY_VERSION_MISMATCH = "POLICY_VERSION_MISMATCH"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
    GOVERNANCE_REJECTED = "GOVERNANCE_REJECTED"
    EXECUTION_NOT_PERMITTED = "EXECUTION_NOT_PERMITTED"


class AdmissionState(Enum):
    POLICY_APPROVED = "POLICY_APPROVED"
    POLICY_REJECTED = "POLICY_REJECTED"
    POLICY_VERSION_MISMATCH = "POLICY_VERSION_MISMATCH"
    POLICY_SIGNATURE_INVALID = "POLICY_SIGNATURE_INVALID"
    GOVERNANCE_REQUIRED = "GOVERNANCE_REQUIRED"
    EXECUTION_DENIED = "EXECUTION_DENIED"


class DeterministicExecutionRejection(Exception):
    def __init__(self, code: RejectionCode, state: AdmissionState, reason: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(reason)
        self.code = code
        self.state = state
        self.reason = reason
        self.details = details or {}


@dataclass(frozen=True)
class GovernanceContract:
    policy_id: str
    policy_version: str
    governance_approver: str
    constraints: Dict[str, Any]
    signature: str
    signer: str
    immutable: bool = True


from control_plane.security.legitimacy_doctrine import LegitimacyDoctrine, LegitimacyStatus, DependencyCondition

@dataclass(frozen=True)
class PolicyAdmissionRequest:
    action: str
    context: Dict[str, Any]
    policy_version: str
    runtime_policy_version: str
    governance_contract: GovernanceContract | Dict[str, Any] | None = None
    decision_contract: DecisionContract | Dict[str, Any] | None = None
    execution_contract: ExecutionContract | Dict[str, Any] | None = None
    policy_id: Optional[str] = None
    sig_valid: bool = True
    trace_valid: bool = True
    schema_valid: bool = True
    nonce_valid: bool = True

@dataclass(frozen=True)
class PolicyAdmissionDecision:
    allowed: bool
    state: AdmissionState
    rejection_code: Optional[RejectionCode]
    reason: str
    details: Dict[str, Any]
    policy_snapshot: Dict[str, Any]
    governance_contract: Optional[Dict[str, Any]] = None
    execution_contract: Optional[Dict[str, Any]] = None
    legitimacy: Optional[str] = None
    doctrine_inputs: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "state": self.state.value,
            "rejection_code": self.rejection_code.value if self.rejection_code else None,
            "reason": self.reason,
            "details": self.details,
            "policy_snapshot": self.policy_snapshot,
            "governance_contract": self.governance_contract,
            "execution_contract": self.execution_contract,
            "legitimacy": self.legitimacy,
            "doctrine_inputs": self.doctrine_inputs,
        }


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_payload(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _coerce_dict(value: Any) -> Dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("Value must be a mapping or dataclass")


class DeterministicPolicyEngine:
    def __init__(
        self,
        policy_id: str,
        runtime_policy_version: str,
        policy_definition: Dict[str, Any],
        *,
        signing_key: bytes | None = None,
        trusted_signers: Optional[set[str]] = None,
        log_path: Path | None = None,
    ):
        self.policy_id = policy_id
        self.runtime_policy_version = runtime_policy_version
        self.policy_definition = dict(policy_definition)
        self.policy_hash = compute_policy_hash(self.policy_definition)
        self.signing_key = signing_key or DEFAULT_POLICY_SIGNING_KEY
        self.trusted_signers = trusted_signers or {
            "sarathi",
            "governance",
            "policy-authority",
        }
        self.log_path = log_path or Path("logs") / "control_plane" / "policy_enforcement.jsonl"
        self._log_lock = threading.Lock()

    @staticmethod
    def rejection_taxonomy() -> Dict[str, Dict[str, str]]:
        return {
            RejectionCode.POLICY_MISSING.value: {"state": AdmissionState.GOVERNANCE_REQUIRED.value},
            RejectionCode.POLICY_VERSION_MISMATCH.value: {"state": AdmissionState.POLICY_VERSION_MISMATCH.value},
            RejectionCode.INVALID_SIGNATURE.value: {"state": AdmissionState.POLICY_SIGNATURE_INVALID.value},
            RejectionCode.CONTRACT_VIOLATION.value: {"state": AdmissionState.POLICY_REJECTED.value},
            RejectionCode.GOVERNANCE_REJECTED.value: {"state": AdmissionState.POLICY_REJECTED.value},
            RejectionCode.EXECUTION_NOT_PERMITTED.value: {"state": AdmissionState.EXECUTION_DENIED.value},
        }

    def build_governance_contract(
        self,
        governance_approver: str,
        constraints: Dict[str, Any] | None = None,
        *,
        signer: str | None = None,
        immutable: bool = True,
    ) -> GovernanceContract:
        resolved_constraints = dict(constraints or self.policy_definition)
        signer_name = signer or governance_approver
        material = {
            "policy_id": self.policy_id,
            "policy_version": self.runtime_policy_version,
            "governance_approver": governance_approver,
            "constraints": resolved_constraints,
            "immutable": immutable,
            "signer": signer_name,
        }
        signature = hmac.new(
            self.signing_key,
            _canonical_json(material).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return GovernanceContract(
            policy_id=self.policy_id,
            policy_version=self.runtime_policy_version,
            governance_approver=governance_approver,
            constraints=resolved_constraints,
            signature=signature,
            signer=signer_name,
            immutable=immutable,
        )

    def _coerce_request(self, request: PolicyAdmissionRequest | Dict[str, Any]) -> PolicyAdmissionRequest:
        if isinstance(request, PolicyAdmissionRequest):
            return request
        if not _is_mapping(request):
            raise TypeError("Policy admission request must be a mapping or PolicyAdmissionRequest")

        payload = dict(request)
        decision_contract = payload.get("decision_contract")
        if decision_contract is not None and not isinstance(decision_contract, DecisionContract):
            decision_contract = validate_decision_contract(decision_contract)

        governance_contract = payload.get("governance_contract")
        if governance_contract is not None and not isinstance(governance_contract, GovernanceContract):
            governance_contract = GovernanceContract(**governance_contract)

        execution_contract = payload.get("execution_contract")
        if execution_contract is not None and not isinstance(execution_contract, ExecutionContract):
            execution_contract = validate_execution_contract(execution_contract)

        context = payload.get("context") or {}
        if not isinstance(context, dict):
            raise TypeError("Policy admission request context must be a dictionary")

        return PolicyAdmissionRequest(
            action=payload["action"],
            context=context,
            policy_version=payload["policy_version"],
            runtime_policy_version=payload.get("runtime_policy_version", self.runtime_policy_version),
            governance_contract=governance_contract,
            decision_contract=decision_contract,
            execution_contract=execution_contract,
            policy_id=payload.get("policy_id", self.policy_id),
            sig_valid=payload.get("sig_valid", True),
            trace_valid=payload.get("trace_valid", True),
            schema_valid=payload.get("schema_valid", True),
            nonce_valid=payload.get("nonce_valid", True),
        )

    def _coerce_governance_contract(self, contract: GovernanceContract | Dict[str, Any] | None) -> GovernanceContract | None:
        if contract is None:
            return None
        if isinstance(contract, GovernanceContract):
            return contract
        if not isinstance(contract, Mapping):
            raise TypeError("Governance contract must be a mapping or GovernanceContract")
        return GovernanceContract(**dict(contract))

    def _coerce_decision_contract(self, request: PolicyAdmissionRequest) -> DecisionContract:
        if request.decision_contract is None:
            raise DeterministicExecutionRejection(
                RejectionCode.POLICY_MISSING,
                AdmissionState.GOVERNANCE_REQUIRED,
                "Policy decision contract is required",
                {"action": request.action},
            )
        if isinstance(request.decision_contract, DecisionContract):
            return request.decision_contract
        return validate_decision_contract(request.decision_contract)

    def _canonical_contract_material(self, contract: GovernanceContract) -> Dict[str, Any]:
        return {
            "policy_id": contract.policy_id,
            "policy_version": contract.policy_version,
            "governance_approver": contract.governance_approver,
            "constraints": contract.constraints,
            "immutable": contract.immutable,
            "signer": contract.signer,
        }

    def _verify_governance_contract(self, request: PolicyAdmissionRequest, decision_contract: DecisionContract, contract: GovernanceContract) -> None:
        if not contract.signature:
            raise DeterministicExecutionRejection(
                RejectionCode.INVALID_SIGNATURE,
                AdmissionState.POLICY_SIGNATURE_INVALID,
                "Signed governance contract is required",
                {"policy_id": contract.policy_id},
            )

        if not contract.immutable:
            raise DeterministicExecutionRejection(
                RejectionCode.CONTRACT_VIOLATION,
                AdmissionState.POLICY_REJECTED,
                "Governance contract must be immutable",
                {"policy_id": contract.policy_id},
            )

        if contract.policy_id != self.policy_id:
            raise DeterministicExecutionRejection(
                RejectionCode.GOVERNANCE_REJECTED,
                AdmissionState.POLICY_REJECTED,
                "Governance policy_id does not match runtime policy",
                {"policy_id": contract.policy_id, "runtime_policy_id": self.policy_id},
            )

        if contract.policy_version != self.runtime_policy_version:
            raise DeterministicExecutionRejection(
                RejectionCode.POLICY_VERSION_MISMATCH,
                AdmissionState.POLICY_VERSION_MISMATCH,
                "Governance policy_version does not match runtime policy",
                {"policy_version": contract.policy_version, "runtime_policy_version": self.runtime_policy_version},
            )

        if contract.governance_approver not in self.trusted_signers:
            raise DeterministicExecutionRejection(
                RejectionCode.GOVERNANCE_REJECTED,
                AdmissionState.POLICY_REJECTED,
                "Governance approver is not trusted",
                {"governance_approver": contract.governance_approver},
            )

        material = self._canonical_contract_material(contract)
        expected_signature = hmac.new(
            self.signing_key,
            _canonical_json(material).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, contract.signature):
            raise DeterministicExecutionRejection(
                RejectionCode.INVALID_SIGNATURE,
                AdmissionState.POLICY_SIGNATURE_INVALID,
                "Governance contract signature invalid",
                {"policy_id": contract.policy_id},
            )

        if contract.signer not in self.trusted_signers:
            raise DeterministicExecutionRejection(
                RejectionCode.GOVERNANCE_REJECTED,
                AdmissionState.POLICY_REJECTED,
                "Governance signer is not trusted",
                {"signer": contract.signer},
            )

        if decision_contract.version != self.runtime_policy_version:
            raise DeterministicExecutionRejection(
                RejectionCode.POLICY_VERSION_MISMATCH,
                AdmissionState.POLICY_VERSION_MISMATCH,
                "Decision contract version does not match runtime policy",
                {"decision_version": decision_contract.version, "runtime_policy_version": self.runtime_policy_version},
            )

        eligibility_rules = contract.constraints.get("eligibility_rules")
        if isinstance(eligibility_rules, list) and decision_contract.action not in eligibility_rules:
            raise DeterministicExecutionRejection(
                RejectionCode.EXECUTION_NOT_PERMITTED,
                AdmissionState.EXECUTION_DENIED,
                "Action is not permitted by governance contract",
                {"action": decision_contract.action, "env": request.context.get("env", "dev")},
            )
        if isinstance(eligibility_rules, dict):
            env_name = request.context.get("env", "dev")
            allowed_actions = eligibility_rules.get(env_name, eligibility_rules.get("dev", []))
            if allowed_actions and decision_contract.action not in allowed_actions:
                raise DeterministicExecutionRejection(
                    RejectionCode.EXECUTION_NOT_PERMITTED,
                    AdmissionState.EXECUTION_DENIED,
                    "Action is not permitted by governance contract",
                    {"action": decision_contract.action, "env": env_name, "allowed_actions": allowed_actions},
                )

        allowed_actions = contract.constraints.get("allowed_actions")
        if allowed_actions and decision_contract.action not in allowed_actions:
            raise DeterministicExecutionRejection(
                RejectionCode.EXECUTION_NOT_PERMITTED,
                AdmissionState.EXECUTION_DENIED,
                "Action is not permitted by governance constraints",
                {"action": decision_contract.action, "allowed_actions": allowed_actions},
            )

        allowed_environments = contract.constraints.get("allowed_environments")
        if allowed_environments and request.context.get("env") not in allowed_environments:
            raise DeterministicExecutionRejection(
                RejectionCode.EXECUTION_NOT_PERMITTED,
                AdmissionState.EXECUTION_DENIED,
                "Environment is not permitted by governance constraints",
                {"env": request.context.get("env"), "allowed_environments": allowed_environments},
            )

    def _verify_execution_contract(self, request: PolicyAdmissionRequest, decision_contract: DecisionContract) -> Optional[Dict[str, Any]]:
        if request.execution_contract is None:
            return None

        execution_contract = request.execution_contract
        execution_payload = request.context.get("execution_payload")
        if execution_payload is None:
            execution_payload = {
                key: value
                for key, value in request.context.items()
                if key not in {
                    "env",
                    "policy_id",
                    "policy_version",
                    "runtime_policy_version",
                    "decision_type",
                    "decision_version",
                    "decision_parameters",
                    "governance_contract",
                    "execution_contract",
                    "source",
                }
            }

        execution_contract = validate_execution_contract(execution_contract, execution_payload)

        if execution_contract.decision_contract.action != decision_contract.action:
            raise DeterministicExecutionRejection(
                RejectionCode.CONTRACT_VIOLATION,
                AdmissionState.POLICY_REJECTED,
                "Execution contract action does not match policy decision",
                {"action": execution_contract.decision_contract.action, "expected_action": decision_contract.action},
            )

        if execution_contract.decision_contract.version != self.runtime_policy_version:
            raise DeterministicExecutionRejection(
                RejectionCode.POLICY_VERSION_MISMATCH,
                AdmissionState.POLICY_VERSION_MISMATCH,
                "Execution contract version does not match runtime policy",
                {"version": execution_contract.decision_contract.version, "runtime_policy_version": self.runtime_policy_version},
            )

        return execution_contract.model_dump(mode="json")

    def _build_policy_snapshot(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.runtime_policy_version,
            "policy_hash": self.policy_hash,
        }

    def _log_decision(self, decision: PolicyAdmissionDecision, request: PolicyAdmissionRequest) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "policy_id": self.policy_id,
            "policy_version": self.runtime_policy_version,
            "action": request.action,
            "request": {
                "action": request.action,
                "policy_version": request.policy_version,
                "runtime_policy_version": request.runtime_policy_version,
                "policy_id": request.policy_id,
            },
            "decision": decision.to_dict(),
        }
        with self._log_lock:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(_canonical_json(record) + "\n")

    def admit(self, request: PolicyAdmissionRequest | Dict[str, Any]) -> PolicyAdmissionDecision:
        coerced_request = self._coerce_request(request)

        # Resolve overrides
        sig_valid = coerced_request.sig_valid and coerced_request.nonce_valid
        trace_valid = coerced_request.trace_valid
        schema_valid = coerced_request.schema_valid
        
        # Resolve key dependencies from context using DependencyCondition enum
        key_deps_str = coerced_request.context.get("dependency_status", "ALL_AVAILABLE")
        if isinstance(key_deps_str, DependencyCondition):
            key_deps = key_deps_str
        else:
            try:
                key_deps = DependencyCondition[key_deps_str]
            except KeyError:
                key_deps = DependencyCondition.ALL_AVAILABLE

        # Handle early overrides failure
        if not sig_valid or not trace_valid or not schema_valid:
            legitimacy, state_val, action_val = LegitimacyDoctrine.compute(
                sig_valid=sig_valid,
                trace_valid=trace_valid,
                schema_valid=schema_valid,
                key_deps=key_deps
            )
            doctrine_inputs = {
                "sig_valid": sig_valid,
                "trace_valid": trace_valid,
                "schema_valid": schema_valid,
                "dependency_condition": key_deps.name
            }
            decision = PolicyAdmissionDecision(
                allowed=False,
                state=AdmissionState.POLICY_SIGNATURE_INVALID if not sig_valid else (AdmissionState.POLICY_REJECTED if not trace_valid else AdmissionState.POLICY_VERSION_MISMATCH),
                rejection_code=RejectionCode.INVALID_SIGNATURE if not sig_valid else (RejectionCode.CONTRACT_VIOLATION if not trace_valid else RejectionCode.POLICY_VERSION_MISMATCH),
                reason="Request validation override failed",
                details={
                    "sig_valid": coerced_request.sig_valid,
                    "nonce_valid": coerced_request.nonce_valid,
                    "trace_valid": coerced_request.trace_valid,
                    "schema_valid": coerced_request.schema_valid,
                },
                policy_snapshot=self._build_policy_snapshot(),
                legitimacy=legitimacy,
                doctrine_inputs=doctrine_inputs,
            )
            self._log_decision(decision, coerced_request)
            return decision

        try:
            decision_contract = self._coerce_decision_contract(coerced_request)
        except DeterministicExecutionRejection as rejection:
            sig_valid_local = sig_valid and (rejection.code != RejectionCode.INVALID_SIGNATURE)
            schema_valid_local = schema_valid and (rejection.state != AdmissionState.POLICY_VERSION_MISMATCH)
            legitimacy, _, _ = LegitimacyDoctrine.compute(sig_valid=sig_valid_local, trace_valid=trace_valid, schema_valid=schema_valid_local, key_deps=key_deps)
            doctrine_inputs = {
                "sig_valid": sig_valid_local,
                "trace_valid": trace_valid,
                "schema_valid": schema_valid_local,
                "dependency_condition": key_deps.name
            }
            decision = PolicyAdmissionDecision(
                allowed=False,
                state=rejection.state,
                rejection_code=rejection.code,
                reason=rejection.reason,
                details=rejection.details,
                policy_snapshot=self._build_policy_snapshot(),
                legitimacy=legitimacy,
                doctrine_inputs=doctrine_inputs,
            )
            self._log_decision(decision, coerced_request)
            return decision
        except Exception as exc:
            legitimacy, _, _ = LegitimacyDoctrine.compute(sig_valid=True, trace_valid=True, schema_valid=False, key_deps=key_deps)
            doctrine_inputs = {
                "sig_valid": True,
                "trace_valid": True,
                "schema_valid": False,
                "dependency_condition": key_deps.name
            }
            decision = PolicyAdmissionDecision(
                allowed=False,
                state=AdmissionState.POLICY_REJECTED,
                rejection_code=RejectionCode.CONTRACT_VIOLATION,
                reason=str(exc),
                details={"validation_error": str(exc)},
                policy_snapshot=self._build_policy_snapshot(),
                legitimacy=legitimacy,
                doctrine_inputs=doctrine_inputs,
            )
            self._log_decision(decision, coerced_request)
            return decision

        governance_contract = self._coerce_governance_contract(coerced_request.governance_contract)
        if governance_contract is None:
            legitimacy, _, _ = LegitimacyDoctrine.compute(sig_valid=True, trace_valid=True, schema_valid=False, key_deps=key_deps)
            doctrine_inputs = {
                "sig_valid": True,
                "trace_valid": True,
                "schema_valid": False,
                "dependency_condition": key_deps.name
            }
            decision = PolicyAdmissionDecision(
                allowed=False,
                state=AdmissionState.GOVERNANCE_REQUIRED,
                rejection_code=RejectionCode.POLICY_MISSING,
                reason="Governance contract is required",
                details={"action": coerced_request.action},
                policy_snapshot=self._build_policy_snapshot(),
                legitimacy=legitimacy,
                doctrine_inputs=doctrine_inputs,
            )
            self._log_decision(decision, coerced_request)
            return decision

        if coerced_request.policy_version != coerced_request.runtime_policy_version:
            legitimacy, _, _ = LegitimacyDoctrine.compute(sig_valid=True, trace_valid=True, schema_valid=False, key_deps=key_deps)
            doctrine_inputs = {
                "sig_valid": True,
                "trace_valid": True,
                "schema_valid": False,
                "dependency_condition": key_deps.name
            }
            decision = PolicyAdmissionDecision(
                allowed=False,
                state=AdmissionState.POLICY_VERSION_MISMATCH,
                rejection_code=RejectionCode.POLICY_VERSION_MISMATCH,
                reason="Request policy_version does not match runtime policy_version",
                details={
                    "request_policy_version": coerced_request.policy_version,
                    "runtime_policy_version": coerced_request.runtime_policy_version,
                },
                policy_snapshot=self._build_policy_snapshot(),
                governance_contract=asdict(governance_contract),
                legitimacy=legitimacy,
                doctrine_inputs=doctrine_inputs,
            )
            self._log_decision(decision, coerced_request)
            return decision

        try:
            self._verify_governance_contract(coerced_request, decision_contract, governance_contract)
            execution_contract = self._verify_execution_contract(coerced_request, decision_contract)
        except DeterministicExecutionRejection as rejection:
            sig_valid_local = sig_valid and (rejection.code != RejectionCode.INVALID_SIGNATURE)
            schema_valid_local = schema_valid and (rejection.state != AdmissionState.POLICY_VERSION_MISMATCH)
            legitimacy, _, _ = LegitimacyDoctrine.compute(sig_valid=sig_valid_local, trace_valid=trace_valid, schema_valid=schema_valid_local, key_deps=key_deps)
            doctrine_inputs = {
                "sig_valid": sig_valid_local,
                "trace_valid": trace_valid,
                "schema_valid": schema_valid_local,
                "dependency_condition": key_deps.name
            }
            decision = PolicyAdmissionDecision(
                allowed=False,
                state=rejection.state,
                rejection_code=rejection.code,
                reason=rejection.reason,
                details=rejection.details,
                policy_snapshot=self._build_policy_snapshot(),
                governance_contract=asdict(governance_contract),
                execution_contract=execution_contract if 'execution_contract' in locals() else None,
                legitimacy=legitimacy,
                doctrine_inputs=doctrine_inputs,
            )
            self._log_decision(decision, coerced_request)
            return decision
        except Exception as exc:
            legitimacy, _, _ = LegitimacyDoctrine.compute(sig_valid=True, trace_valid=True, schema_valid=False, key_deps=key_deps)
            doctrine_inputs = {
                "sig_valid": True,
                "trace_valid": True,
                "schema_valid": False,
                "dependency_condition": key_deps.name
            }
            decision = PolicyAdmissionDecision(
                allowed=False,
                state=AdmissionState.POLICY_REJECTED,
                rejection_code=RejectionCode.CONTRACT_VIOLATION,
                reason=str(exc),
                details={"validation_error": str(exc)},
                policy_snapshot=self._build_policy_snapshot(),
                governance_contract=asdict(governance_contract),
                legitimacy=legitimacy,
                doctrine_inputs=doctrine_inputs,
            )
            self._log_decision(decision, coerced_request)
            return decision

        legitimacy, _, _ = LegitimacyDoctrine.compute(sig_valid=True, trace_valid=True, schema_valid=True, key_deps=key_deps)
        doctrine_inputs = {
            "sig_valid": True,
            "trace_valid": True,
            "schema_valid": True,
            "dependency_condition": key_deps.name
        }
        decision = PolicyAdmissionDecision(
            allowed=True,
            state=AdmissionState.POLICY_APPROVED,
            rejection_code=None,
            reason="Policy admission approved",
            details={
                "action": decision_contract.action,
                "policy_id": self.policy_id,
                "policy_version": self.runtime_policy_version,
            },
            policy_snapshot=self._build_policy_snapshot(),
            governance_contract=asdict(governance_contract),
            execution_contract=execution_contract,
            legitimacy=legitimacy,
            doctrine_inputs=doctrine_inputs,
        )
        self._log_decision(decision, coerced_request)
        return decision

    def enforce(self, request: PolicyAdmissionRequest | Dict[str, Any]) -> PolicyAdmissionDecision:
        decision = self.admit(request)
        if not decision.allowed:
            raise DeterministicExecutionRejection(
                RejectionCode(decision.rejection_code.value) if decision.rejection_code else RejectionCode.CONTRACT_VIOLATION,
                decision.state,
                decision.reason,
                decision.details,
            )
        return decision
