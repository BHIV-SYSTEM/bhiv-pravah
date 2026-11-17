# Phase 4: Semantic Transition Validation

## Overview

Phase 4 protects **meaning** in state transitions. While Phases 1-3 protect technical integrity (replay, governance, persistence), Phase 4 prevents **semantically invalid transitions** that are technically allowed by the FSM.

## The Problem: Syntactic vs Semantic Validity

### Syntactic Validity (Phases 1-3)
A transition is **syntactically valid** if:
- It exists in the legal transitions table
- No guard condition blocks it
- The contract hash is correct
- The history can be replayed

### Semantic Validity (Phase 4)
A transition is **semantically valid** if:
- It is syntactically valid AND
- The execution history contains all prerequisite states required by business logic

## Examples

### Valid Semantic Path
```
CREATED → APPROVED → EXECUTING → COMPLETED
```

Every transition respects prerequisites:
- CREATED: Initial state, no prerequisites ✓
- APPROVED: Requires CREATED (in history) ✓
- EXECUTED: Requires CREATED + APPROVED (in history) ✓
- COMPLETED: Requires CREATED + APPROVED + EXECUTED (in history) ✓

### Invalid Semantic Paths

#### Example 1: Skipping Approval
```
CREATED → EXECUTED ❌
```
**Why invalid:** EXECUTED requires APPROVED in the execution history.
- Missing prerequisite: APPROVED
- Business meaning: You cannot execute without approval

#### Example 2: Skipping Execution
```
CREATED → APPROVED → COMPLETED ❌
```
**Why invalid:** COMPLETED requires that work was actually EXECUTED.
- Missing prerequisite: EXECUTED
- Business meaning: You cannot mark work complete without executing it

#### Example 3: Jumping to Complete
```
CREATED → COMPLETED ❌
```
**Why invalid:** COMPLETED requires the full execution path.
- Missing prerequisites: APPROVED, EXECUTED
- Business meaning: Completion requires approval + execution

## Semantic Prerequisites by State

### CREATED
- **Prerequisites:** None (initial state)
- **Meaning:** The execution has been initiated
- **Can transition to:**
  - APPROVED (normal flow)
  - FAILED (creation error)

### APPROVED
- **Prerequisites:** CREATED
- **Meaning:** The execution was reviewed and authorized
- **Can transition to:**
  - EXECUTED (proceed with work)
  - FAILED (approval error)

### EXECUTED
- **Prerequisites:** CREATED, APPROVED
- **Meaning:** The work has been performed
- **Validates:**
  - Authorization (APPROVED) happened
  - Initiative (CREATED) was established
- **Can transition to:**
  - COMPLETED (mark as done)
  - FAILED (execution error)

### COMPLETED
- **Prerequisites:** CREATED, APPROVED, EXECUTED
- **Meaning:** The execution path was fully traversed and work is done
- **Validates:**
  - Full governance chain: creation → approval → execution
  - No shortcuts were taken
  - Business logic was respected
- **Terminal state:** No further transitions allowed

### FAILED
- **Prerequisites:** CREATED
- **Meaning:** An error occurred after initialization
- **Can occur from:**
  - CREATED (creation failed)
  - APPROVED (approval failed)
  - EXECUTED (execution failed)
- **Terminal state:** No further transitions allowed

## Implementation Details

### Location
- **Validator:** `contracts/semantic_transition_validator.py`
- **Integration:** `contracts/execution_contract.py` → `advance_execution_state()`
- **Tests:** `tests/test_semantic_transition_validator.py`

### Validation Flow

When `advance_execution_state()` is called:

```python
def advance_execution_state(contract, new_state, ...):
    # Phase 1: Terminal state lock (prevent transitions from COMPLETED/FAILED)
    _validate_terminal_state_lock(contract, new_state)
    
    # Phase 2/3: Syntactic validity (is transition in FSM table?)
    validate_state_transition(contract.execution_state, new_state)
    
    # Phase 4: Semantic validity (does history have prerequisites?)
    validate_semantic_transition_with_context(
        current_state=contract.execution_state,
        next_state=new_state,
        history=contract.execution_state_history,
        execution_id=contract.execution_id,
    )
    
    # If all validations pass, advance state
    history = tuple(contract.execution_state_history) + (new_state,)
    ...
```

### Error Messages

When a semantic transition is invalid, the error message includes:

1. **What failed:** The specific transition attempted
2. **Why it failed:** Missing prerequisite states
3. **What's needed:** The states required in history
4. **Execution history:** The actual path taken so far
5. **Business meaning:** Why the missing states matter

Example error:
```
[exec_123] Semantic transition invalid: CREATED → COMPLETED.
Missing prerequisite states in history: APPROVED, EXECUTED.
History: CREATED.
Meaning: COMPLETED requires that execution has gone through APPROVED, EXECUTED before reaching this state.
```

## Semantic Transition Table

| From | To | Valid? | Prerequisites in History | Business Meaning |
|------|-------|--------|--------------------------|------------------|
| CREATED | APPROVED | ✓ | CREATED | Authorize work |
| CREATED | EXECUTED | ✗ | CREATED, APPROVED | Cannot execute without approval |
| CREATED | COMPLETED | ✗ | CREATED, APPROVED, EXECUTED | Cannot complete without executing |
| CREATED | FAILED | ✓ | CREATED | Work creation failed |
| APPROVED | EXECUTED | ✓ | CREATED, APPROVED | Execute approved work |
| APPROVED | COMPLETED | ✗ | CREATED, APPROVED, EXECUTED | Cannot complete without executing |
| APPROVED | FAILED | ✓ | CREATED, APPROVED | Approved work failed |
| EXECUTED | COMPLETED | ✓ | CREATED, APPROVED, EXECUTED | Mark executed work complete |
| EXECUTED | FAILED | ✓ | CREATED, APPROVED, EXECUTED | Executed work failed |
| COMPLETED | * | ✗ | - | Terminal state |
| FAILED | * | ✗ | - | Terminal state |

## Testing

### Test Categories

1. **Valid Paths:** Transitions that respect all prerequisites
2. **Invalid Paths:** Transitions that skip prerequisite states
3. **Failure Cases:** Transitions to FAILED from various states
4. **Edge Cases:** Empty history, repeated states, etc.
5. **Error Messages:** Clear, actionable error reporting

### Running Tests

```bash
# Run semantic transition validation tests
pytest tests/test_semantic_transition_validator.py -v

# Run all execution contract tests
pytest tests/ -k "execution" -v

# Run with coverage
pytest tests/test_semantic_transition_validator.py --cov=contracts
```

## Phase 4 Benefits

### Prevents Logic Errors
Without Phase 4, a bug could cause:
- Skipping approval steps
- Marking work complete without executing it
- Jumping directly to terminal states

With Phase 4, these are **impossible** regardless of code bugs or edge cases.

### Ensures Audit Trail Validity
- Complete execution history is guaranteed to follow business logic
- Replayed history is not just syntactically valid but semantically sound
- Compliance audits can trust the state transitions

### Catches Configuration Errors
- If a guard is misconfigured, Phase 4 catches it
- If state advancement code is wrong, Phase 4 catches it
- If orchestration logic is flawed, Phase 4 catches it

### Makes Governance Meaningful
- Phases 1-3 ensure signatures and contracts are valid
- Phase 4 ensures those signatures actually govern a real execution flow
- No shortcuts, no workarounds, no semantic loopholes

## Integration with Other Phases

```
Phase 1: Replay Integrity
    ↓ (ensure history can be replayed)
Phase 2: Governance Authority
    ↓ (ensure transitions are authorized)
Phase 3: Persistence Integrity
    ↓ (ensure contract data is immutable)
Phase 4: Semantic Validity
    ↓ (ensure history follows business logic)
Verified Execution Lineage
```

## Configuration & Customization

### Adding New States

To add a new execution state to the system:

1. Add state to `ExecutionState` type in `execution_contract.py`
2. Add to `LEGAL_STATE_TRANSITIONS` in `execution_contract.py`
3. Define prerequisites in `SEMANTIC_PREREQUISITES` in `semantic_transition_validator.py`
4. Add test cases in `test_semantic_transition_validator.py`
5. Update this documentation

Example: Adding PAUSED state

```python
# semantic_transition_validator.py
SEMANTIC_PREREQUISITES = {
    ...
    "PAUSED": {"CREATED", "APPROVED", "EXECUTED"},  # Like COMPLETED, requires full path
    ...
}
```

### Changing Prerequisites

If business logic changes (e.g., "FAILED can only occur from EXECUTED, not from CREATED"):

```python
# semantic_transition_validator.py
SEMANTIC_PREREQUISITES = {
    ...
    "FAILED": {"CREATED", "APPROVED", "EXECUTED"},  # Stricter: require full path
    ...
}
```

**Note:** Any change requires:
- Updated tests
- Communication with governance teams
- Audit trail of the change
- Verification that existing executions comply

## Debugging Phase 4 Violations

### When a Semantic Transition is Rejected

1. **Check the error message** for missing prerequisites
2. **Verify the execution history** is what you expect
3. **Trace back where** the problematic transition was attempted
4. **Look at the source** field in lineage events
5. **Review the code** that called `advance_execution_state()`

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| CREATED → COMPLETED | Skipped APPROVED/EXECUTED | Ensure proper state transitions |
| APPROVED → COMPLETED | Skipped EXECUTED | Call execute before marking complete |
| Invalid state in history | Corrupted data | Verify lineage integrity (Phase 1) |
| Wrong prerequisites configured | Logic change | Update SEMANTIC_PREREQUISITES |

## Future Enhancements

### Phase 4+ Possibilities

1. **Temporal Constraints:** Track timing between states (e.g., min time in APPROVED)
2. **Conditional Prerequisites:** Different paths based on decision context
3. **State Attributes:** Associate metadata with states (who, when, why)
4. **Transition Metadata:** Record why each transition occurred
5. **Path Analysis:** Detect anomalous execution patterns

## References

- **Phase 1 (Replay Integrity):** `control_plane/core/execution_lineage.py`
- **Phase 2 (Governance Authority):** `contracts/decision_contract.py`
- **Phase 3 (Persistence Integrity):** `contracts/execution_contract.py`
- **Phase 4 (Semantic Validity):** `contracts/semantic_transition_validator.py`
- **Security Verifier:** `security/lineage_verifier.py`
- **Tests:** `tests/test_semantic_transition_validator.py`
