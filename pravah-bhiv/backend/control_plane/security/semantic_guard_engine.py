"""
Phase 4: Semantic Guard Engine

Protects execution meaning by preventing semantically invalid transitions.

While phases 1-3 protect:
- Replay integrity (can history be replayed?)
- Governance authority (is transition authorized?)
- Persistence integrity (is contract data correct?)

Phase 4 protects meaning:
- Semantic validity (does transition follow business logic?)
- Anti-hidden-state checks (are all states recorded?)
- Governance state coupling (does contract match decision?)

Key Innovation: Prevents transitions that are syntactically valid but logically impossible.

Example violations:
  CREATED → COMPLETED (missing APPROVED, EXECUTING)
  APPROVED → COMPLETED (missing EXECUTING)
  EXECUTING → EXECUTING (no state change)
  Hidden state: CREATED → EXECUTING (APPROVED not in lineage)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any

from contracts.execution_state import ExecutionState


class SemanticTransitionViolation(Enum):
    """Taxonomy of semantic transition violations."""
    
    # Core semantic violations
    SEMANTIC_TRANSITION_INVALID = "semantic_transition_invalid"
    STATE_PREREQUISITE_MISSING = "state_prerequisite_missing"
    TRANSITION_BOUNDARY_VIOLATION = "transition_boundary_violation"
    
    # Hidden state violations (Phase 4 focus)
    HIDDEN_STATE_DETECTED = "hidden_state_detected"
    STATE_SKIPPED_IN_LINEAGE = "state_skipped_in_lineage"
    SYNTHETIC_STATE_INJECTED = "synthetic_state_injected"
    MISSING_LINEAGE_EVENT = "missing_lineage_event"
    
    # Governance violations
    GOVERNANCE_STATE_VIOLATION = "governance_state_violation"
    GOVERNANCE_STATE_MISMATCH = "governance_state_mismatch"
    UNAUTHORIZED_STATE_TRANSITION = "unauthorized_state_transition"
    
    # Terminal state violations
    TERMINAL_STATE_TRANSITION = "terminal_state_transition"
    TERMINAL_STATE_REACTIVATION = "terminal_state_reactivation"


@dataclass
class SemanticViolationReport:
    """Report of a semantic violation."""
    
    violation_type: SemanticTransitionViolation
    execution_id: str
    current_state: Optional[ExecutionState] = None
    attempted_state: Optional[ExecutionState] = None
    reason: str = ""
    details: Dict[str, Any] = None
    missing_states: Optional[Set[ExecutionState]] = None
    lineage_gap: Optional[Tuple[int, int]] = None
    expected_sequence: Optional[List[ExecutionState]] = None
    actual_sequence: Optional[List[ExecutionState]] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "violation_type": self.violation_type.value,
            "execution_id": self.execution_id,
            "current_state": self.current_state,
            "attempted_state": self.attempted_state,
            "reason": self.reason,
            "details": self.details,
            "missing_states": sorted(self.missing_states) if self.missing_states else None,
            "lineage_gap": self.lineage_gap,
            "expected_sequence": self.expected_sequence,
            "actual_sequence": self.actual_sequence,
        }


class SemanticFSM:
    """
    Semantic Finite State Machine.
    
    Defines the business logic meaning of state transitions.
    More restrictive than the syntactic FSM.
    """
    
    # Allowed semantic transitions (business logic)
    ALLOWED_TRANSITIONS: Dict[ExecutionState, Set[ExecutionState]] = {
        "CREATED": {"APPROVED", "FAILED"},
        "APPROVED": {"EXECUTING", "FAILED"},
        "EXECUTING": {"COMPLETED", "FAILED"},
        "COMPLETED": set(),  # Terminal
        "FAILED": set(),      # Terminal
    }
    
    # Prerequisites: states that MUST exist in history before reaching target state
    TRANSITION_PREREQUISITES: Dict[ExecutionState, Set[ExecutionState]] = {
        "CREATED": set(),                           # Initial state
        "APPROVED": {"CREATED"},                    # Requires creation
        "EXECUTING": {"CREATED", "APPROVED"},       # Requires creation + approval
        "COMPLETED": {"CREATED", "APPROVED", "EXECUTING"},  # Requires full path
        "FAILED": {"CREATED"},                      # Requires at least creation
    }
    
    # Terminal states - no transitions allowed from or to these
    TERMINAL_STATES: Set[ExecutionState] = {"COMPLETED", "FAILED"}
    
    # Idempotent states - same state repeated is allowed
    IDEMPOTENT_STATES: Set[ExecutionState] = set()  # Empty: no idempotent transitions
    
    # Minimum required states in full execution history
    MINIMUM_FULL_PATH: List[ExecutionState] = ["CREATED", "APPROVED", "EXECUTING", "COMPLETED"]

    @staticmethod
    def _normalize_state(state: ExecutionState) -> ExecutionState:
        if state == "EXECUTED":
            return "EXECUTING"
        return state
    
    @classmethod
    def is_allowed_transition(
        cls,
        from_state: ExecutionState,
        to_state: ExecutionState,
    ) -> bool:
        """Check if transition is allowed by semantic FSM."""
        allowed = cls.ALLOWED_TRANSITIONS.get(cls._normalize_state(from_state), set())
        return cls._normalize_state(to_state) in allowed
    
    @classmethod
    def get_prerequisites(cls, target_state: ExecutionState) -> Set[ExecutionState]:
        """Get prerequisite states for a target state."""
        return cls.TRANSITION_PREREQUISITES.get(cls._normalize_state(target_state), set())
    
    @classmethod
    def is_terminal(cls, state: ExecutionState) -> bool:
        """Check if state is terminal."""
        return cls._normalize_state(state) in cls.TERMINAL_STATES


class SemanticGuardEngine:
    """
    Semantic Guard Engine: Phase 4 Validator
    
    Prevents semantically invalid but syntactically valid transitions.
    Detects hidden states and enforces governance-state coupling.
    """
    
    def __init__(self, fsm: Optional[SemanticFSM] = None):
        """Initialize semantic guard engine."""
        self.fsm = fsm or SemanticFSM()
    
    def validate_transition(
        self,
        execution_id: str,
        current_state: ExecutionState,
        next_state: ExecutionState,
        history: Tuple[ExecutionState, ...],
        governance_state: Optional[ExecutionState] = None,
    ) -> Optional[SemanticViolationReport]:
        """
        Validate a state transition semantically.
        
        Returns: SemanticViolationReport if invalid, None if valid
        """
        
        current_state = self.fsm._normalize_state(current_state)
        next_state = self.fsm._normalize_state(next_state)
        history = tuple(self.fsm._normalize_state(state) for state in history)

        # Check 1: Terminal state transitions (no transitions FROM terminal states)
        if not self._validate_terminal_state_lock(current_state, next_state):
            return SemanticViolationReport(
                violation_type=SemanticTransitionViolation.TERMINAL_STATE_TRANSITION,
                execution_id=execution_id,
                current_state=current_state,
                attempted_state=next_state,
                reason=f"Cannot transition from terminal state {current_state}",
                details={"terminal_states": list(self.fsm.TERMINAL_STATES)},
            )

        # Check 2: Prerequisite states in history first - prefer reporting missing prerequisites
        missing_states = self._check_prerequisites(next_state, history)
        if missing_states:
            return SemanticViolationReport(
                violation_type=SemanticTransitionViolation.STATE_PREREQUISITE_MISSING,
                execution_id=execution_id,
                current_state=current_state,
                attempted_state=next_state,
                reason=f"Transition to {next_state} requires states in history: {', '.join(sorted(missing_states))}",
                details={"required_prerequisites": list(self.fsm.get_prerequisites(next_state))},
                missing_states=missing_states,
                expected_sequence=list(self.fsm.get_prerequisites(next_state)),
                actual_sequence=list(history),
            )

        # Check 3: FSM structural validity (after prerequisites are confirmed)
        if not self.fsm.is_allowed_transition(current_state, next_state):
            return SemanticViolationReport(
                violation_type=SemanticTransitionViolation.SEMANTIC_TRANSITION_INVALID,
                execution_id=execution_id,
                current_state=current_state,
                attempted_state=next_state,
                reason=f"Transition {current_state} → {next_state} not allowed by semantic FSM",
                details={"allowed_transitions": list(self.fsm.ALLOWED_TRANSITIONS.get(current_state, set()))},
            )
        
        # Check 4: Governance state coupling (if provided)
        if governance_state is not None:
            governance_violation = self._check_governance_coupling(
                execution_id=execution_id,
                current_state=current_state,
                next_state=next_state,
                governance_state=governance_state,
                history=history,
            )
            if governance_violation:
                return governance_violation
        
        # All checks passed
        return None
    
    def validate_state_history(
        self,
        execution_id: str,
        history: Tuple[ExecutionState, ...],
        lineage_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[SemanticViolationReport]:
        """
        Validate entire state history for hidden states and gaps.
        
        This is the anti-hidden-state check - most important for Phase 4.
        
        Returns: SemanticViolationReport if invalid, None if valid
        """
        
        history = tuple(self.fsm._normalize_state(state) for state in history)

        if not history:
            return SemanticViolationReport(
                violation_type=SemanticTransitionViolation.SYNTHETIC_STATE_INJECTED,
                execution_id=execution_id,
                reason="Empty state history",
                details={"reason": "history_is_empty"},
            )
        
        # Check 1: History must start with CREATED
        if history[0] != "CREATED":
            return SemanticViolationReport(
                violation_type=SemanticTransitionViolation.HIDDEN_STATE_DETECTED,
                execution_id=execution_id,
                current_state=history[0] if history else None,
                reason=f"History must start with CREATED, got {history[0]}",
                details={"first_state": history[0], "expected": "CREATED"},
                actual_sequence=list(history),
            )
        
        # Check 2: Validate each transition in history
        for idx, (from_state, to_state) in enumerate(zip(history, history[1:])):
            # Verify prerequisites are met first (detect synthetic injection)
            prerequisites = self.fsm.get_prerequisites(to_state)
            history_so_far = set(history[:idx+1])
            missing = prerequisites - history_so_far

            if missing:
                return SemanticViolationReport(
                    violation_type=SemanticTransitionViolation.SYNTHETIC_STATE_INJECTED,
                    execution_id=execution_id,
                    current_state=from_state,
                    attempted_state=to_state,
                    reason=f"State {to_state} reached without required prerequisites: {', '.join(sorted(missing))}",
                    details={"position": idx, "required_prerequisites": list(prerequisites)},
                    missing_states=missing,
                    lineage_gap=(idx, idx + 1),
                    actual_sequence=list(history),
                )

            # Verify transition is allowed by FSM (after prerequisites present)
            if not self.fsm.is_allowed_transition(from_state, to_state):
                return SemanticViolationReport(
                    violation_type=SemanticTransitionViolation.STATE_SKIPPED_IN_LINEAGE,
                    execution_id=execution_id,
                    current_state=from_state,
                    attempted_state=to_state,
                    reason=f"Invalid transition in history at position {idx}: {from_state} → {to_state}",
                    details={"position": idx, "allowed": list(self.fsm.ALLOWED_TRANSITIONS.get(from_state, set()))},
                    lineage_gap=(idx, idx + 1),
                    actual_sequence=list(history),
                )
        
        # Check 3: Lineage event consistency (if provided)
        if lineage_events:
            lineage_violation = self._check_lineage_consistency(
                execution_id=execution_id,
                history=history,
                lineage_events=lineage_events,
            )
            if lineage_violation:
                return lineage_violation
        
        # All history checks passed
        return None
    
    def validate_replay_chain(
        self,
        execution_id: str,
        replay_events: List[Dict[str, Any]],
    ) -> Optional[SemanticViolationReport]:
        """
        Validate a replay chain from lineage.
        
        Ensures that replaying the lineage produces a valid state sequence.
        """
        
        if not replay_events:
            return SemanticViolationReport(
                violation_type=SemanticTransitionViolation.HIDDEN_STATE_DETECTED,
                execution_id=execution_id,
                reason="Replay chain is empty",
                details={"reason": "no_replay_events"},
            )
        
        # Extract states from replay events
        states: List[ExecutionState] = []
        for event in replay_events:
            state = event.get("state")
            if not state:
                return SemanticViolationReport(
                    violation_type=SemanticTransitionViolation.MISSING_LINEAGE_EVENT,
                    execution_id=execution_id,
                    reason="Replay event missing state",
                    details={"event": event},
                )
            states.append(self.fsm._normalize_state(state))
        
        # Validate the reconstructed history
        history = tuple(states)
        return self.validate_state_history(execution_id, history, replay_events)
    
    def _validate_terminal_state_lock(
        self,
        current_state: ExecutionState,
        next_state: ExecutionState,
    ) -> bool:
        """Check terminal state lock: no transitions FROM terminal states."""
        if self.fsm.is_terminal(current_state) and next_state != current_state:
            return False
        return True
    
    def _check_prerequisites(
        self,
        target_state: ExecutionState,
        history: Tuple[ExecutionState, ...],
    ) -> Set[ExecutionState]:
        """
        Check if target state has all prerequisites in history.
        
        Returns: Set of missing prerequisites, empty if all present
        """
        required = self.fsm.get_prerequisites(target_state)
        present = set(history)
        return required - present
    
    def _check_governance_coupling(
        self,
        execution_id: str,
        current_state: ExecutionState,
        next_state: ExecutionState,
        governance_state: ExecutionState,
        history: Tuple[ExecutionState, ...],
    ) -> Optional[SemanticViolationReport]:
        """
        Check that execution state and governance state are coupled.
        
        The governance state must match or precede the execution state.
        """
        # Governance state must have legitimate role in history
        governance_precedence = {"CREATED": 0, "APPROVED": 1, "EXECUTING": 2, "COMPLETED": 3, "FAILED": 3}
        execution_precedence = governance_precedence.get(next_state, 3)
        governance_prec = governance_precedence.get(governance_state, -1)
        
        # Governance must be at same or higher precedence level
        if governance_prec < execution_precedence - 1:
            return SemanticViolationReport(
                violation_type=SemanticTransitionViolation.GOVERNANCE_STATE_VIOLATION,
                execution_id=execution_id,
                current_state=current_state,
                attempted_state=next_state,
                reason=f"Governance state {governance_state} insufficient for execution state {next_state}",
                details={
                    "governance_state": governance_state,
                    "execution_state": next_state,
                    "governance_precedence": governance_prec,
                    "required_governance_precedence": execution_precedence - 1,
                },
            )
        
        return None
    
    def _check_lineage_consistency(
        self,
        execution_id: str,
        history: Tuple[ExecutionState, ...],
        lineage_events: List[Dict[str, Any]],
    ) -> Optional[SemanticViolationReport]:
        """
        Check that lineage events correspond to state history.
        
        Detects hidden states: states in history but not in lineage.
        """
        
        lineage_states = set()
        event_count = 0
        for event in lineage_events:
            state = event.get("state")
            if state:
                lineage_states.add(self.fsm._normalize_state(state))
                event_count += 1
        
        # All history states must be in lineage
        history_states = set(history)
        missing_in_lineage = history_states - lineage_states
        
        if missing_in_lineage:
            return SemanticViolationReport(
                violation_type=SemanticTransitionViolation.HIDDEN_STATE_DETECTED,
                execution_id=execution_id,
                reason=f"States in history but missing from lineage: {', '.join(sorted(missing_in_lineage))}",
                details={
                    "states_in_history": sorted(history_states),
                    "states_in_lineage": sorted(lineage_states),
                    "missing_in_lineage": sorted(missing_in_lineage),
                    "lineage_event_count": event_count,
                },
                missing_states=missing_in_lineage,
                actual_sequence=list(history),
            )
        
        return None
    
    def explain_violation(self, report: SemanticViolationReport) -> str:
        """Generate human-readable explanation of violation."""
        lines = [
            f"SEMANTIC VIOLATION: {report.violation_type.value}",
            f"Execution: {report.execution_id}",
        ]
        
        if report.current_state and report.attempted_state:
            lines.append(f"Attempted transition: {report.current_state} → {report.attempted_state}")
        
        lines.append(f"Reason: {report.reason}")
        
        if report.missing_states:
            lines.append(f"Missing states: {', '.join(sorted(report.missing_states))}")
        
        if report.actual_sequence:
            lines.append(f"Actual sequence: {' → '.join(report.actual_sequence)}")
        
        if report.expected_sequence:
            lines.append(f"Expected prerequisites: {', '.join(report.expected_sequence)}")
        
        if report.details:
            lines.append(f"Details: {report.details}")
        
        return "\n".join(lines)


# Singleton instance
_semantic_guard = SemanticGuardEngine()


def validate_state_transition(
    execution_id: str,
    current_state: ExecutionState,
    next_state: ExecutionState,
    history: Tuple[ExecutionState, ...],
    governance_state: Optional[ExecutionState] = None,
) -> None:
    """
    Validate state transition semantically.
    
    Raises: SemanticViolationReport if invalid
    """
    report = _semantic_guard.validate_transition(
        execution_id=execution_id,
        current_state=current_state,
        next_state=next_state,
        history=history,
        governance_state=governance_state,
    )
    
    if report:
        error_msg = _semantic_guard.explain_violation(report)
        raise ValueError(error_msg)


def validate_state_history(
    execution_id: str,
    history: Tuple[ExecutionState, ...],
    lineage_events: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Validate state history for hidden states and gaps.
    
    Raises: SemanticViolationReport if invalid
    """
    report = _semantic_guard.validate_state_history(
        execution_id=execution_id,
        history=history,
        lineage_events=lineage_events,
    )
    
    if report:
        error_msg = _semantic_guard.explain_violation(report)
        raise ValueError(error_msg)


def validate_replay_chain(
    execution_id: str,
    replay_events: List[Dict[str, Any]],
) -> None:
    """
    Validate a replay chain from lineage.
    
    Raises: SemanticViolationReport if invalid
    """
    report = _semantic_guard.validate_replay_chain(
        execution_id=execution_id,
        replay_events=replay_events,
    )
    
    if report:
        error_msg = _semantic_guard.explain_violation(report)
        raise ValueError(error_msg)


def get_semantic_guard() -> SemanticGuardEngine:
    """Get the semantic guard engine singleton."""
    return _semantic_guard
