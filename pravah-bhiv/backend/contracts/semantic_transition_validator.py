"""
Phase 4: Semantic Transition Validation

Protects the "meaning" of state transitions.

While Phases 1-3 protect:
- Replay integrity (Execution Lineage)
- Governance authority (Authorization contracts)  
- Persistence integrity (Execution contracts)

Phase 4 prevents transitions that are syntactically valid but semantically invalid.

SEMANTIC RULES:
==============

A transition is semantically valid only if the execution history contains all
required prerequisite states. The FSM structure allows certain transitions, but
business logic requires that certain transitions only make sense if previous
states have been reached.

Valid path:     CREATED → APPROVED → EXECUTED → COMPLETED
Invalid path:   CREATED → COMPLETED (missing APPROVED and EXECUTED)

SEMANTIC PREREQUISITES BY STATE:
"""

from __future__ import annotations

from typing import Dict, Literal, Set

from contracts.execution_state import ExecutionState


def _normalize_state(state: ExecutionState) -> ExecutionState:
    return state

# Semantic prerequisites: each state requires certain prior states in history
SEMANTIC_PREREQUISITES: Dict[ExecutionState, Set[ExecutionState]] = {
    # CREATED is the initial state - no prerequisites
    "CREATED": set(),
    
    # APPROVED can follow CREATED directly (CREATED is already in initial history)
    # Prerequisite: Must have CREATED in history
    "APPROVED": {"CREATED"},
    
    # EXECUTED requires approval - must have gone through APPROVED state
    # Prerequisite: Must have CREATED and APPROVED in history
    "EXECUTED": {"CREATED", "APPROVED"},
    
    # COMPLETED is terminal and requires full execution path
    # Prerequisite: Must have CREATED, APPROVED, and EXECUTED in history
    "COMPLETED": {"CREATED", "APPROVED", "EXECUTED"},
    
    # FAILED can occur from any non-terminal state, but must have started
    # Prerequisite: Must have CREATED (so it started properly)
    "FAILED": {"CREATED"},
}


def validate_semantic_transition(
    current_state: ExecutionState,
    next_state: ExecutionState,
    history: tuple[ExecutionState, ...],
) -> None:
    """
    Validate that a state transition is semantically valid.
    
    A transition is semantically valid if:
    1. The next_state has all its semantic prerequisites in the history
    
    Args:
        current_state: Current execution state
        next_state: Target execution state
        history: Complete execution state history up to current_state
        
    Raises:
        ValueError: If transition violates semantic rules
    """
    if not history:
        raise ValueError("Execution state history cannot be empty")
    
    current_state = _normalize_state(current_state)
    next_state = _normalize_state(next_state)
    history = tuple(_normalize_state(state) for state in history)

    # Get prerequisites for the target state
    prerequisites = SEMANTIC_PREREQUISITES.get(next_state, set())
    
    # Convert history to set for membership checking
    history_set = set(history)
    
    # Check if all prerequisites are in history
    missing_prerequisites = prerequisites - history_set
    
    if missing_prerequisites:
        raise ValueError(
            f"Semantic transition invalid: {current_state} → {next_state}. "
            f"Missing prerequisite states in history: {', '.join(sorted(missing_prerequisites))}. "
            f"History: {' → '.join(history)}. "
            f"Meaning: {next_state} requires that execution has gone through "
            f"{', '.join(sorted(prerequisites))} before reaching this state."
        )


def validate_semantic_transition_with_context(
    current_state: ExecutionState,
    next_state: ExecutionState,
    history: tuple[ExecutionState, ...],
    execution_id: str = "",
) -> None:
    """
    Validate semantic transition with additional context for error reporting.
    
    Args:
        current_state: Current execution state
        next_state: Target execution state
        history: Complete execution state history
        execution_id: Optional execution ID for error context
        
    Raises:
        ValueError: If transition violates semantic rules
    """
    try:
        validate_semantic_transition(current_state, next_state, history)
    except ValueError as e:
        # Enhance error message with execution context if available
        if execution_id:
            raise ValueError(f"[{execution_id}] {str(e)}") from e
        raise


def explain_semantic_rules() -> str:
    """
    Return human-readable explanation of semantic rules.
    
    Returns:
        String explaining Phase 4 semantic transition rules
    """
    rules = ["PHASE 4 SEMANTIC TRANSITION RULES"]
    rules.append("=" * 50)
    rules.append("")
    
    for state, prerequisites in sorted(SEMANTIC_PREREQUISITES.items()):
        if prerequisites:
            prereq_str = " → ".join(sorted(prerequisites))
            rules.append(f"{state}:")
            rules.append(f"  Requires prior passage through: {prereq_str}")
        else:
            rules.append(f"{state}: (initial state, no prerequisites)")
        rules.append("")
    
    rules.append("INVALID TRANSITIONS (Examples):")
    rules.append("-" * 50)
    rules.append("CREATED → COMPLETED (missing APPROVED, EXECUTED)")
    rules.append("CREATED → EXECUTED (missing APPROVED)")
    rules.append("APPROVED → COMPLETED (missing EXECUTED)")
    rules.append("")
    rules.append("VALID TRANSITIONS (Full Path):")
    rules.append("-" * 50)
    rules.append("CREATED → APPROVED → EXECUTED → COMPLETED")
    rules.append("CREATED → APPROVED → EXECUTED → FAILED")
    rules.append("CREATED → APPROVED → FAILED")
    rules.append("CREATED → FAILED (only on creation errors)")
    
    return "\n".join(rules)


if __name__ == "__main__":
    print(explain_semantic_rules())
