"""
PRAVAH Stream Processor
Deterministic stream processing engine with Schema v1.0 enforcement and append-only replay evidence.

Guarantees:
- Strict Schema v1.0 validation on inbound signals and outbound events
- Purely deterministic state machine transitions with semantic prerequisites
- Zero uncontrolled randomness or wall-clock drift in state calculation
- Append-only replay evidence persistence via ReplayLedger
- Structured error handling and failure state auditability
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from contracts.execution_state import ExecutionState
from contracts.semantic_transition_validator import validate_semantic_transition
from pravah.replay_ledger import ReplayLedger, compute_canonical_hash, canonical_json_dump
from pravah.schema_validator import (
    SchemaValidationError,
    SchemaValidatorV1,
    ValidationResult,
)


LEGAL_TRANSITIONS: Dict[str, set[str]] = {
    "CREATED": {"APPROVED", "FAILED"},
    "APPROVED": {"EXECUTED", "FAILED"},
    "EXECUTED": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
}

DEFAULT_STATE_MAP: Dict[str, ExecutionState] = {
    "execution": "APPROVED",
    "verification": "EXECUTED",
    "telemetry": "COMPLETED",
    "action_request": "APPROVED",
}


class StreamProcessorError(Exception):
    """Base exception for Stream Processor errors."""

    def __init__(self, message: str, error_code: str = "PROCESSING_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class InvalidStateTransitionError(StreamProcessorError):
    """Raised when an illegal or semantically invalid state transition is attempted."""

    def __init__(self, current_state: str, target_state: str, reason: str):
        super().__init__(
            message=f"Invalid state transition {current_state} -> {target_state}: {reason}",
            error_code="INVALID_STATE_TRANSITION",
            details={"current_state": current_state, "target_state": target_state, "reason": reason},
        )


class TerminalStateLockedError(StreamProcessorError):
    """Raised when an event is processed against an already terminal execution."""

    def __init__(self, execution_id: str, terminal_state: str):
        super().__init__(
            message=f"Execution {execution_id} is in terminal state '{terminal_state}' and cannot accept transitions",
            error_code="TERMINAL_STATE_LOCKED",
            details={"execution_id": execution_id, "terminal_state": terminal_state},
        )


class StreamProcessor:
    """
    Deterministic Stream Processor for PRAVAH.
    
    Processes streaming event signals, validates schema contracts (v1.0),
    enforces state transition semantics, and records append-only replay evidence.
    """

    def __init__(self, ledger: Optional[ReplayLedger] = None):
        self.ledger = ledger if ledger is not None else ReplayLedger()
        self.validator = SchemaValidatorV1()

    def _determine_target_state(self, signal: Dict[str, Any], explicit_target: Optional[str] = None) -> ExecutionState:
        """Deterministically determine the next target state."""
        if explicit_target:
            target = explicit_target.upper()
            if target not in LEGAL_TRANSITIONS:
                raise InvalidStateTransitionError("UNKNOWN", target, f"Target state '{target}' is not a valid ExecutionState")
            return target  # type: ignore

        # Look in signal payload
        payload = signal.get("payload", {})
        if isinstance(payload, dict):
            if "target_state" in payload:
                return payload["target_state"].upper()
            if "status" in payload and payload["status"].upper() in LEGAL_TRANSITIONS:
                return payload["status"].upper()

        signal_type = signal.get("signal_type", "").lower()
        if signal_type in DEFAULT_STATE_MAP:
            return DEFAULT_STATE_MAP[signal_type]

        # Default progressive transition
        return "APPROVED"

    def process_signal(
        self,
        signal: Dict[str, Any],
        target_state: Optional[str] = None,
        fail_closed: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a single inbound signal with deterministic state reduction.
        
        Steps:
        1. Strict Schema v1.0 validation.
        2. Retrieve existing execution state and history.
        3. Validate legal FSM transition and semantic prerequisites.
        4. Append event to ReplayLedger (append-only evidence).
        5. Compute deterministic cumulative state_hash.
        6. Validate outbound payload against Outbound Schema v1.0.
        7. Return verified outbound event dictionary.
        """
        # 1. Enforce inbound schema v1.0
        validated_signal = self.validator.enforce_inbound(signal)

        execution_id = validated_signal["execution_id"]
        trace_id = validated_signal["trace_id"]
        source = validated_signal["source"]
        timestamp = validated_signal["timestamp"]
        payload = validated_signal["payload"]

        # 2. Retrieve history from append-only ledger
        existing_events = self.ledger.get_events(execution_id)

        if not existing_events:
            # Genesis event for this execution must be CREATED
            current_state = "CREATED"
            history: Tuple[ExecutionState, ...] = ("CREATED",)
            # Record genesis event in ledger
            genesis_event_id = f"{execution_id}-genesis-1"
            self.ledger.record_event(
                execution_id=execution_id,
                event_id=genesis_event_id,
                state="CREATED",
                timestamp=timestamp,
                source=source,
                details={"action": "genesis_init", "initial_payload": payload},
                previous_hash="",
            )
            # Re-fetch events
            existing_events = self.ledger.get_events(execution_id)

        last_event = existing_events[-1]
        current_state = last_event.state
        history = tuple(e.state for e in existing_events)  # type: ignore

        # Check if already terminal
        if current_state in {"COMPLETED", "FAILED"}:
            raise TerminalStateLockedError(execution_id, current_state)

        # 3. Determine and validate target state transition
        next_state = self._determine_target_state(validated_signal, target_state)

        # FSM check
        allowed = LEGAL_TRANSITIONS.get(current_state, set())
        if next_state not in allowed:
            raise InvalidStateTransitionError(
                current_state=current_state,
                target_state=next_state,
                reason=f"Transition from {current_state} to {next_state} not permitted by FSM",
            )

        # Semantic prerequisites check
        try:
            validate_semantic_transition(
                current_state=current_state,
                next_state=next_state,
                history=history,
            )
        except ValueError as e:
            raise InvalidStateTransitionError(
                current_state=current_state,
                target_state=next_state,
                reason=str(e),
            ) from e

        # 4. Generate deterministic event_id and record in ledger
        seq = len(existing_events) + 1
        event_id = f"{execution_id}-evt-{seq}"
        
        event_details = {
            "trace_id": trace_id,
            "signal_type": validated_signal["signal_type"],
            "payload": payload,
            "transition": f"{current_state}->{next_state}",
        }

        recorded_event = self.ledger.record_event(
            execution_id=execution_id,
            event_id=event_id,
            state=next_state,
            timestamp=timestamp,
            source=source,
            details=event_details,
            previous_hash=last_event.event_hash,
        )

        # 5. Compute cumulative state hash
        state_hash = self.ledger.compute_state_hash(execution_id)

        # 6. Build and validate Outbound Event Schema v1.0
        outbound_data = {
            "schema_version": "1.0",
            "trace_id": trace_id,
            "execution_id": execution_id,
            "event_id": recorded_event.event_id,
            "sequence": recorded_event.sequence,
            "state": recorded_event.state,
            "event_hash": recorded_event.event_hash,
            "previous_hash": recorded_event.previous_hash,
            "state_hash": state_hash,
            "timestamp": timestamp,
            "source": recorded_event.source,
            "details": recorded_event.details,
            "sequence_hash": recorded_event.sequence_hash,
            "lineage_proof": recorded_event.lineage_proof,
        }

        validated_outbound = self.validator.enforce_outbound(outbound_data)
        return validated_outbound

    def process_stream(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deterministically process a batch/stream of signals in sequence.
        """
        results = []
        for signal in signals:
            out = self.process_signal(signal)
            results.append(out)
        return results

    def get_state(self, execution_id: str) -> Dict[str, Any]:
        """Return the current deterministic state of an execution."""
        return self.ledger.reconstruct_state(execution_id)

    def replay(self, execution_id: str) -> Dict[str, Any]:
        """Replay and verify the entire cryptographic history for execution_id."""
        return self.ledger.verify_replay(execution_id)
