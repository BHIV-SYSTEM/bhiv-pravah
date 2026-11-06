from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from contracts.decision_contract import DecisionContract, validate_decision_contract
from control_plane.core.execution_lineage import append_lineage_event
from contracts.policy_snapshot import PolicySnapshot
from contracts.runtime_attestation import RuntimeAttestation
from contracts.execution_state import ExecutionState
from contracts.semantic_transition_validator import validate_semantic_transition_with_context


LEGAL_STATE_TRANSITIONS: Dict[str, set[str]] = {
    "CREATED": {"APPROVED", "FAILED"},
    "APPROVED": {"EXECUTED", "FAILED"},
    "EXECUTED": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
}

TERMINAL_EXECUTION_STATES = {"COMPLETED", "FAILED"}


def validate_state_transition(current_state: ExecutionState, next_state: ExecutionState) -> None:
    allowed_states = LEGAL_STATE_TRANSITIONS.get(current_state)
    if allowed_states is None or next_state not in allowed_states:
        raise ValueError(f"Illegal state transition: {current_state} -> {next_state}")


def validate_execution_state_history(history: tuple[ExecutionState, ...]) -> None:
    if not history:
        raise ValueError("Execution state history cannot be empty")

    if history[0] != "CREATED":
        raise ValueError("Execution state history must start with CREATED")

    for previous_state, next_state in zip(history, history[1:]):
        validate_state_transition(previous_state, next_state)


def _validate_terminal_state_lock(contract: ExecutionContract, new_state: ExecutionState) -> None:
    if contract.execution_state in TERMINAL_EXECUTION_STATES and new_state != contract.execution_state:
        raise ValueError(f"Illegal state transition: {contract.execution_state} -> {new_state}")


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("execution_contract", None)
    normalized.pop("verified_service_id", None)
    return normalized


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_payload(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _snapshot_payload(snapshot: Any) -> Dict[str, Any] | None:
    if snapshot is None:
        return None
    if hasattr(snapshot, "model_dump"):
        return snapshot.model_dump()
    return dict(snapshot)


class ExecutionContract(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    execution_id: str
    decision_contract: DecisionContract
    execution_payload: Dict[str, Any]
    execution_hash: str
    approved_at: int
    approved_by: str
    policy_snapshot: PolicySnapshot | None = None
    runtime_attestation: RuntimeAttestation | None = None
    immutable: bool = True
    execution_state: ExecutionState = "APPROVED"
    execution_state_history: tuple[ExecutionState, ...] = ("CREATED", "APPROVED")

    @field_validator("execution_id", "approved_by", "execution_hash")
    @classmethod
    def validate_required_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("Execution contract field cannot be empty")
        return value

    @field_validator("policy_snapshot", mode="before")
    @classmethod
    def validate_policy_snapshot(cls, value: Any) -> PolicySnapshot | None:
        if value is None:
            return None
        if isinstance(value, PolicySnapshot):
            if not (
                isinstance(value.get("policy_id"), str) and value.get("policy_id")
                and isinstance(value.get("policy_version"), str) and value.get("policy_version")
                and isinstance(value.get("policy_hash"), str) and value.get("policy_hash")
            ):
                raise ValueError("Malformed policy_snapshot: missing or invalid required string fields ('policy_id', 'policy_version', 'policy_hash')")
            return value
        if isinstance(value, dict):
            p_id = value.get("policy_id")
            p_ver = value.get("policy_version")
            p_hash = value.get("policy_hash")
            if not (
                isinstance(p_id, str) and p_id
                and isinstance(p_ver, str) and p_ver
                and isinstance(p_hash, str) and p_hash
            ):
                raise ValueError("Malformed policy_snapshot: missing or invalid required string fields ('policy_id', 'policy_version', 'policy_hash')")
            return PolicySnapshot(p_id, p_ver, p_hash)
        raise ValueError(f"Malformed policy_snapshot: expected dict or PolicySnapshot, got {type(value).__name__}")


def compute_execution_hash(
    decision_contract: DecisionContract,
    execution_payload: Dict[str, Any],
    execution_id: str,
    approved_at: int,
    approved_by: str,
    immutable: bool = True,
    policy_snapshot: Dict[str, Any] | None = None,
    runtime_attestation: Dict[str, Any] | None = None,
) -> str:
    canonical_payload = {
        "decision_contract": decision_contract.model_dump(mode="json"),
        "execution_payload": _normalize_payload(execution_payload),
        "execution_id": execution_id,
        "approved_at": approved_at,
        "approved_by": approved_by,
        "immutable": immutable,
        "policy_snapshot": policy_snapshot,
        "runtime_attestation": runtime_attestation,
    }
    return _hash_payload(canonical_payload)


def build_execution_contract(
    decision_contract: DecisionContract | dict,
    execution_payload: Dict[str, Any],
    approved_by: str = "sarathi",
    execution_id: str | None = None,
    approved_at: int | None = None,
    execution_state: ExecutionState = "APPROVED",
    execution_state_history: tuple[ExecutionState, ...] = ("CREATED", "APPROVED"),
    policy_snapshot: Dict[str, Any] | None = None,
    runtime_attestation: Dict[str, Any] | None = None,
) -> ExecutionContract:
    if not isinstance(decision_contract, DecisionContract):
        decision_contract = validate_decision_contract(decision_contract)

    normalized_payload = _normalize_payload(execution_payload)
    payload_execution_id = normalized_payload.get("execution_id") or execution_id or str(uuid.uuid4())
    normalized_payload["execution_id"] = payload_execution_id

    approval_timestamp = approved_at or int(datetime.now(timezone.utc).timestamp())
    validate_execution_state_history(execution_state_history)
    if execution_state_history[-1] != execution_state:
        raise ValueError("Execution state must match the last entry in execution_state_history")

    # Validate and coerce policy_snapshot dicts into PolicySnapshot instances for model validation
    if policy_snapshot is not None:
        if isinstance(policy_snapshot, PolicySnapshot):
            if not (
                isinstance(policy_snapshot.get("policy_id"), str) and policy_snapshot.get("policy_id")
                and isinstance(policy_snapshot.get("policy_version"), str) and policy_snapshot.get("policy_version")
                and isinstance(policy_snapshot.get("policy_hash"), str) and policy_snapshot.get("policy_hash")
            ):
                raise ValueError("Malformed policy_snapshot: missing or invalid required string fields ('policy_id', 'policy_version', 'policy_hash')")
        elif isinstance(policy_snapshot, dict):
            p_id = policy_snapshot.get("policy_id")
            p_ver = policy_snapshot.get("policy_version")
            p_hash = policy_snapshot.get("policy_hash")
            if not (
                isinstance(p_id, str) and p_id
                and isinstance(p_ver, str) and p_ver
                and isinstance(p_hash, str) and p_hash
            ):
                raise ValueError("Malformed policy_snapshot: missing or invalid required string fields ('policy_id', 'policy_version', 'policy_hash')")
            policy_snapshot = PolicySnapshot(p_id, p_ver, p_hash)
        else:
            raise ValueError(f"Malformed policy_snapshot: expected dict or PolicySnapshot, got {type(policy_snapshot).__name__}")
    execution_hash = compute_execution_hash(
        decision_contract=decision_contract,
        execution_payload=normalized_payload,
        execution_id=payload_execution_id,
        approved_at=approval_timestamp,
        approved_by=approved_by,
        immutable=True,
        policy_snapshot=policy_snapshot,
        runtime_attestation=runtime_attestation,
    )

    contract = ExecutionContract(
        execution_id=payload_execution_id,
        decision_contract=decision_contract,
        execution_payload=normalized_payload,
        execution_hash=execution_hash,
        approved_at=approval_timestamp,
        approved_by=approved_by,
        immutable=True,
        policy_snapshot=policy_snapshot,
        runtime_attestation=runtime_attestation,
        execution_state=execution_state,
        execution_state_history=execution_state_history,
    )

    append_lineage_event(
        execution_id=contract.execution_id,
        state="CREATED",
        execution_hash=contract.execution_hash,
        source="governance",
        details={
            "approved_by": contract.approved_by,
            "approved_at": contract.approved_at,
            "stage": "contract_created",
        },
    )
    append_lineage_event(
        execution_id=contract.execution_id,
        state="APPROVED",
        execution_hash=contract.execution_hash,
        source="governance",
        details={
            "approved_by": contract.approved_by,
            "approved_at": contract.approved_at,
            "stage": "contract_approved",
            "policy_snapshot": dict(policy_snapshot) if policy_snapshot is not None else None,
            "runtime_attestation": dict(runtime_attestation) if runtime_attestation is not None else None,
        },
    )

    return contract


def validate_execution_contract(
    contract: ExecutionContract | dict,
    current_payload: Dict[str, Any] | None = None,
) -> ExecutionContract:
    if not isinstance(contract, ExecutionContract):
        contract = ExecutionContract(**contract)

    payload_to_check = _normalize_payload(current_payload or contract.execution_payload)

    expected_hash = compute_execution_hash(
        decision_contract=contract.decision_contract,
        execution_payload=payload_to_check,
        execution_id=contract.execution_id,
        approved_at=contract.approved_at,
        approved_by=contract.approved_by,
        immutable=contract.immutable,
        policy_snapshot=_snapshot_payload(getattr(contract, 'policy_snapshot', None)),
        runtime_attestation=_snapshot_payload(getattr(contract, 'runtime_attestation', None)),
    )

    if contract.execution_hash != expected_hash:
        raise ValueError("Execution contract hash mismatch")

    if payload_to_check.get("execution_id") not in {None, contract.execution_id}:
        raise ValueError("Execution payload execution_id mismatch")

    return contract


def advance_execution_state(
    contract: ExecutionContract | dict,
    new_state: ExecutionState,
    *,
    source: str = "runtime",
    details: Dict[str, Any] | None = None,
    governance_state: ExecutionState | None = None,
) -> ExecutionContract:
    if not isinstance(contract, ExecutionContract):
        contract = validate_execution_contract(contract)

    _validate_terminal_state_lock(contract, new_state)
    validate_state_transition(contract.execution_state, new_state)

    # Phase 4: Semantic validation - check meaning and prevent hidden states
    validate_semantic_transition_with_context(
        current_state=contract.execution_state,
        next_state=new_state,
        history=contract.execution_state_history,
        execution_id=contract.execution_id,
    )

    # Phase 4: Semantic guard engine - comprehensive semantic + governance validation
    try:
        # Import here to avoid circular import at module import time
        from control_plane.security.semantic_guard_engine import (
            validate_state_transition as validate_semantic_transition,
        )
    except Exception as exc:
        raise RuntimeError(
            f"[{contract.execution_id}] CRITICAL: Semantic guard engine unavailable: {exc}"
        ) from exc

    try:
        validate_semantic_transition(
            execution_id=contract.execution_id,
            current_state=contract.execution_state,
            next_state=new_state,
            history=contract.execution_state_history,
            governance_state=governance_state,
        )
    except ValueError as e:
        # Re-raise with execution context
        raise ValueError(f"[{contract.execution_id}] Semantic guard violation: {str(e)}") from e

    history = tuple(contract.execution_state_history)
    history = history + (new_state,)

    updated_contract = contract.model_copy(
        update={
            "execution_state": new_state,
            "execution_state_history": history,
        }
    )

    append_lineage_event(
        execution_id=updated_contract.execution_id,
        state=new_state,
        execution_hash=updated_contract.execution_hash,
        source=source,
        details=details,
    )

    return updated_contract


# Canonical alias matching forensic contract terminology
transition_contract_state = advance_execution_state
