# Phase 4: Semantic Guard Engine Architecture

## Executive Summary

Phase 4 implements comprehensive semantic validation that prevents **logically impossible but syntactically valid state transitions**. It answers the question: *Does this transition make sense from a business logic perspective?*

**Key Innovation:** Anti-hidden-state checks detect when states are missing from the recorded lineage, preventing silent state injection.

---

## The Four Phases: Layered Validation

```
┌─────────────────────────────────────────────────────────────┐
│           State Transition Attempt                           │
└────────────────────────┬────────────────────────────────────┘
                         ↓
        ┌────────────────────────────────────────┐
        │ Phase 1: Terminal State Lock           │
        │ Execution Lineage                      │
        │ Prevents transitions FROM COMPLETED/   │
        │ FAILED                                 │
        └────────────┬───────────────────────────┘
                     ↓ Pass
        ┌────────────────────────────────────────┐
        │ Phase 2-3: FSM Structure & Governance  │
        │ Execution Contract                     │
        │ Is transition in FSM table?            │
        │ Is transition authorized?              │
        │ Is contract immutable?                 │
        └────────────┬───────────────────────────┘
                     ↓ Pass
        ┌────────────────────────────────────────┐
        │ Phase 4: Semantic Guard Engine (NEW)   │
        │ Does history have prerequisites?       │
        │ Are all states recorded in lineage?    │
        │ Is governance state sufficient?        │
        │ Are hidden states detected?            │
        └────────────┬───────────────────────────┘
                     ↓ Pass
        ┌────────────────────────────────────────┐
        │ Execution State Advanced               │
        │ Lineage event appended                 │
        │ History immutably updated              │
        └────────────────────────────────────────┘
```

---

## Component 1: Semantic FSM

Defines the business logic meaning of state transitions.

### Allowed Transitions (Semantic)

```python
ALLOWED_TRANSITIONS = {
    "CREATED": {"APPROVED", "FAILED"},
    "APPROVED": {"EXECUTING", "FAILED"},
    "EXECUTING": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),     # Terminal
    "FAILED": set(),        # Terminal
}
```

**What This Means:**
- Work must be approved before execution
- Approval leads to execution or failure
- Execution can complete or fail
- Completion and failure are terminal (no exits)

### Transition Prerequisites (Bounded Constraints)

```python
TRANSITION_PREREQUISITES = {
    "CREATED": set(),
    "APPROVED": {"CREATED"},
    "EXECUTING": {"CREATED", "APPROVED"},
    "COMPLETED": {"CREATED", "APPROVED", "EXECUTING"},
    "FAILED": {"CREATED"},
}
```

**What This Means:**
- Every state requires certain prior states to have been reached
- `COMPLETED` requires the full path: creation → approval → execution
- `EXECUTING` cannot be reached without approval first
- `COMPLETED` cannot be reached from `APPROVED` directly

### Example: Why CREATED → COMPLETED is Invalid

```
Attempted: CREATED → COMPLETED
Prerequisites for COMPLETED: {CREATED, APPROVED, EXECUTING}
Present in history: {CREATED}
Missing: {APPROVED, EXECUTING}
Result: REJECTED
```

---

## Component 2: Semantic Guard Engine

**Location:** `control_plane/security/semantic_guard_engine.py`

### Core Validations

#### 1. Terminal State Lock
```python
# Prevents transitions FROM terminal states
if fsm.is_terminal(current_state):
    reject transition
```

#### 2. FSM Structural Check
```python
# Verifies transition exists in semantic FSM
if next_state not in ALLOWED_TRANSITIONS[current_state]:
    reject transition
```

#### 3. Prerequisite Validation
```python
# Ensures all prerequisite states exist in history
required = TRANSITION_PREREQUISITES[next_state]
present = set(history)
missing = required - present
if missing:
    reject transition with "missing states: {missing}"
```

#### 4. Anti-Hidden-State Check (Most Critical)
```python
# Detects states that were synthesized or silently injected
for event in lineage_events:
    if event.state not in history:
        flag as "missing_in_lineage"
        
for state in history:
    if state not in lineage_events:
        flag as "hidden_state"
        reject with "SYNTHETIC_STATE_INJECTED"
```

#### 5. Governance State Coupling
```python
# Governance state must be sufficient for execution state
execution_precedence = {"CREATED": 0, "APPROVED": 1, "EXECUTING": 2, "COMPLETED": 3}
if governance_precedence < execution_precedence - 1:
    reject with "GOVERNANCE_STATE_VIOLATION"
```

---

## Component 3: Rejection Taxonomy

Specific error codes for each violation type:

| Violation | Code | Meaning | Example |
|-----------|------|---------|---------|
| **SEMANTIC_TRANSITION_INVALID** | Core | Transition not in semantic FSM | EXECUTING → CREATED |
| **STATE_PREREQUISITE_MISSING** | Core | History lacks prerequisites | CREATED → COMPLETED (no APPROVED/EXECUTING) |
| **TRANSITION_BOUNDARY_VIOLATION** | Core | Violates state boundaries | COMPLETED → FAILED (from terminal) |
| **HIDDEN_STATE_DETECTED** | Anti-HS | State in history but not in lineage | CREATED → [gap] → EXECUTING |
| **STATE_SKIPPED_IN_LINEAGE** | Anti-HS | Invalid transition recorded | CREATED → [invalid] → APPROVED |
| **SYNTHETIC_STATE_INJECTED** | Anti-HS | State appears without prerequisites | EXECUTING without APPROVED in history |
| **MISSING_LINEAGE_EVENT** | Anti-HS | Lineage event missing for state | EXECUTING in history, no lineage event |
| **GOVERNANCE_STATE_VIOLATION** | Gov | Governance insufficient | EXECUTING without APPROVED governance |
| **GOVERNANCE_STATE_MISMATCH** | Gov | Governance doesn't match execution | Mismatch between contract states |

---

## Component 4: Validation APIs

### High-Level: Public Functions

```python
# Validate single transition
validate_state_transition(
    execution_id="exec_123",
    current_state="CREATED",
    next_state="APPROVED",
    history=("CREATED",),
    governance_state=None,  # Optional
) # Raises ValueError if invalid

# Validate entire history (anti-hidden-state)
validate_state_history(
    execution_id="exec_123",
    history=("CREATED", "APPROVED", "EXECUTING"),
    lineage_events=[...],  # Optional
) # Raises ValueError if invalid

# Validate replay chain from lineage
validate_replay_chain(
    execution_id="exec_123",
    replay_events=[
        {"state": "CREATED", ...},
        {"state": "APPROVED", ...},
        ...
    ],
) # Raises ValueError if invalid
```

### Low-Level: Engine Methods

```python
engine = SemanticGuardEngine()

# Get violation report (doesn't raise)
report = engine.validate_transition(...)
if report:
    print(f"Violation: {report.violation_type}")
    print(engine.explain_violation(report))

# Detailed history check
report = engine.validate_state_history(...)

# Replay chain check
report = engine.validate_replay_chain(...)
```

---

## Component 5: Integration Points

### In Execution Contract

**File:** `contracts/execution_contract.py`

```python
def advance_execution_state(
    contract,
    new_state,
    source="runtime",
    details=None,
    governance_state=None,  # NEW: optional governance coupling
):
    # Phase 1: Terminal lock
    _validate_terminal_state_lock(contract, new_state)
    
    # Phase 2-3: FSM structure
    validate_state_transition(contract.execution_state, new_state)
    
    # Phase 4: Semantic validation (simple version)
    validate_semantic_transition_with_context(
        current_state=contract.execution_state,
        next_state=new_state,
        history=contract.execution_state_history,
        execution_id=contract.execution_id,
    )
    
    # Phase 4: Comprehensive semantic + anti-hidden-state
    try:
        validate_semantic_transition(
            execution_id=contract.execution_id,
            current_state=contract.execution_state,
            next_state=new_state,
            history=contract.execution_state_history,
            governance_state=governance_state,  # NEW
        )
    except ValueError as e:
        raise ValueError(f"[{contract.execution_id}] Semantic guard violation: {str(e)}") from e
    
    # Advance state if all validations pass
    history = tuple(contract.execution_state_history) + (new_state,)
    ...
```

### In Lineage Verification

**File:** `control_plane/core/execution_lineage.py` (future)

```python
def replay_execution_lineage(execution_id):
    """Replay execution from lineage."""
    events = read_lineage_events(execution_id)
    
    # Phase 4: Validate replay chain for hidden states
    validate_replay_chain(
        execution_id=execution_id,
        replay_events=events,
    )
    
    # Build state history from valid replay
    return build_history_from_replay(events)
```

---

## Test Coverage: Success Criteria

### ✓ Valid Paths (Must Pass)

```
CREATED → APPROVED → EXECUTING → COMPLETED
```
- Each transition validates successfully
- All prerequisites are in history
- Lineage events are present for each state

### ✗ Invalid Semantic Jumps (Must Fail)

```
CREATED → COMPLETED           ✗ (missing APPROVED, EXECUTING)
CREATED → EXECUTING           ✗ (missing APPROVED)
APPROVED → COMPLETED          ✗ (missing EXECUTING)
EXECUTING → APPROVED          ✗ (backwards)
COMPLETED → EXECUTING         ✗ (terminal reactivation)
FAILED → CREATING             ✗ (invalid to transition)
```

### ✗ Hidden States (Must Fail)

```
History: CREATED → EXECUTING
Lineage: CREATED → [gap] → EXECUTING
Result: REJECTED (missing APPROVED in lineage)

History: CREATED → APPROVED → EXECUTING
Lineage: CREATED → [no APPROVED] → EXECUTING
Result: REJECTED (APPROVED missing from lineage)

History: CREATED → EXECUTING
With prerequisite APPROVED missing
Result: REJECTED (synthetic state detected)
```

### ✗ Governance Violations (Must Fail)

```
Attempt: EXECUTING
Governance: CREATED
Result: REJECTED (governance insufficient)

Attempt: COMPLETED
Governance: APPROVED
Result: REJECTED (governance insufficient)
```

---

## Error Messages: Examples

### Invalid Semantic Jump

```
SEMANTIC VIOLATION: semantic_transition_invalid
Execution: exec_123
Attempted transition: CREATED → COMPLETED
Reason: Transition CREATED → COMPLETED not allowed by semantic FSM
Details: {
    "allowed_transitions": ["APPROVED", "FAILED"]
}
```

### Missing Prerequisites

```
SEMANTIC VIOLATION: state_prerequisite_missing
Execution: exec_123
Attempted transition: CREATED → COMPLETED
Reason: Transition to COMPLETED requires states in history: APPROVED, EXECUTING
Details: {
    "required_prerequisites": ["CREATED", "APPROVED", "EXECUTING"]
}
Missing states: APPROVED, EXECUTING
Actual sequence: CREATED
Expected prerequisites: CREATED, APPROVED, EXECUTING
```

### Hidden State Detection

```
SEMANTIC VIOLATION: hidden_state_detected
Execution: exec_123
Reason: States in history but missing from lineage: EXECUTING
Details: {
    "states_in_history": ["CREATED", "APPROVED", "EXECUTING"],
    "states_in_lineage": ["CREATED", "APPROVED"],
    "missing_in_lineage": ["EXECUTING"],
    "lineage_event_count": 2
}
Missing states: EXECUTING
Actual sequence: CREATED → APPROVED → EXECUTING
```

### Governance Violation

```
SEMANTIC VIOLATION: governance_state_violation
Execution: exec_123
Attempted transition: APPROVED → EXECUTING
Reason: Governance state CREATED insufficient for execution state EXECUTING
Details: {
    "governance_state": "CREATED",
    "execution_state": "EXECUTING",
    "governance_precedence": 0,
    "required_governance_precedence": 1
}
```

---

## Usage Examples

### Example 1: Valid Execution

```python
from contracts.execution_contract import ExecutionContract, advance_execution_state

# Create contract (starts at CREATED → APPROVED)
contract = ExecutionContract(
    execution_id="exec_123",
    decision_contract=...,
    execution_payload={},
    execution_hash="...",
    approved_at=...,
    approved_by="...",
)

# Advance to EXECUTING (has CREATED, APPROVED)
try:
    contract = advance_execution_state(
        contract,
        "EXECUTING",
        source="executor",
    )
    print(f"✓ Advanced to {contract.execution_state}")
except ValueError as e:
    print(f"✗ Rejected: {e}")

# Advance to COMPLETED (has all prerequisites)
try:
    contract = advance_execution_state(
        contract,
        "COMPLETED",
        source="orchestrator",
    )
    print(f"✓ Advanced to {contract.execution_state}")
except ValueError as e:
    print(f"✗ Rejected: {e}")
```

### Example 2: Semantic Jump Rejected

```python
# Attempt invalid jump
try:
    contract = advance_execution_state(
        contract,
        "COMPLETED",
        source="buggy_code",
    )
except ValueError as e:
    print(f"✗ Rejected: {e}")
    # Prints:
    # [exec_123] Semantic guard violation: 
    # Transition to COMPLETED requires states in history: APPROVED, EXECUTING
```

### Example 3: Hidden State Detection

```python
from control_plane.security.semantic_guard_engine import validate_state_history

# History has EXECUTING but skipped APPROVED
history = ("CREATED", "EXECUTING")

try:
    validate_state_history(
        execution_id="exec_123",
        history=history,
    )
except ValueError as e:
    print(f"✗ Hidden state detected: {e}")
```

---

## Architecture: Key Design Decisions

### 1. Placement in control_plane/security/

**Why?** Phase 4 is a security boundary - it prevents unauthorized state transitions at the semantic level, not just the structural level.

### 2. Layered Validations

**Why?** Each layer catches different classes of errors:
- Terminal lock: prevents obvious illegal transitions
- FSM check: enforces syntactic structure
- Prerequisite check: enforces business logic
- Anti-hidden-state: prevents injection attacks
- Governance coupling: ensures authorization

### 3. Rejection Taxonomy

**Why?** Specific error codes enable:
- Targeted logging and monitoring
- Better debugging and root cause analysis
- Compliance audit trails
- Automated recovery or escalation

### 4. Optional Governance State

**Why?** Allows Phase 4 to work with or without governance contracts. Can be progressively rolled out.

---

## Future Enhancements: Phase 4+

### Temporal Constraints
```python
# Add timing between states
MINIMUM_STATE_DURATION = {
    "APPROVED": 60,      # Min 60s in APPROVED
    "EXECUTING": 300,    # Min 5m in EXECUTING
}
```

### Conditional Prerequisites
```python
# Different paths based on context
if execution_type == "rollback":
    PREREQUISITES["COMPLETED"] = {"CREATED", "APPROVED", "EXECUTING"}
elif execution_type == "canary":
    PREREQUISITES["COMPLETED"] = {"CREATED", "APPROVED"}
```

### State Metadata
```python
@dataclass
class StateTransition:
    from_state: ExecutionState
    to_state: ExecutionState
    timestamp: float
    source: str
    reason: str
    authorized_by: str
```

### Pattern Detection
```python
# Detect anomalous patterns
detect_repeated_failures()
detect_fast_cycling()
detect_unauthorized_retries()
```

---

## Testing: Run Tests

```bash
# Run all Phase 4 tests
pytest tests/test_phase4_semantic_guards.py -v

# Run specific test class
pytest tests/test_phase4_semantic_guards.py::TestInvalidSemanticJumps -v

# Run with coverage
pytest tests/test_phase4_semantic_guards.py --cov=control_plane.security

# Run specific test
pytest tests/test_phase4_semantic_guards.py::TestHiddenStateDetection::test_hidden_state_synthetic_injection -v
```

---

## Summary: Phase 4 Benefits

| Benefit | How It Helps |
|---------|-------------|
| **Prevents Logic Errors** | No way to skip approval or execution |
| **Detects Hidden States** | Finds silently injected or missing states |
| **Ensures Audit Trail** | History guaranteed to follow business logic |
| **Catches Config Errors** | Invalid transitions impossible |
| **Makes Governance Real** | Governance contracts actually govern flow |
| **Enables Compliance** | Auditors can trust the transition path |

---

## References

- **Semantic Guard Engine:** `control_plane/security/semantic_guard_engine.py`
- **Execution Contract:** `contracts/execution_contract.py`
- **Tests:** `tests/test_phase4_semantic_guards.py`
- **Lineage System:** `control_plane/core/execution_lineage.py`
- **Security Verifier:** `security/lineage_verifier.py`
