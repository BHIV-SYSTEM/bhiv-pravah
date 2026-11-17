# Phase 4 Quick Reference

## What is Phase 4?

Phase 4 prevents **semantically invalid state transitions** - transitions that are allowed by the FSM structure but violate business logic.

## The Core Rule

**Every state requires certain prerequisite states in the execution history before it can be reached.**

## State Requirements

| State | Must Have in History | Example Invalid Path |
|-------|---------------------|----------------------|
| CREATED | - | N/A (initial) |
| APPROVED | CREATED | - |
| EXECUTED | CREATED + APPROVED | CREATED → EXECUTED ❌ |
| COMPLETED | CREATED + APPROVED + EXECUTED | CREATED → APPROVED → COMPLETED ❌ |
| FAILED | CREATED | CREATED → CREATED ❌ |

## Valid Full Path
```
CREATED → APPROVED → EXECUTED → COMPLETED
```

## Example: Why CREATED → COMPLETED is Invalid

```python
# ❌ This will be rejected:
contract = ExecutionContract(...)
contract = advance_execution_state(contract, "CREATED")      # OK: initial
contract = advance_execution_state(contract, "COMPLETED")    # REJECTED!

# Error message:
# Semantic transition invalid: CREATED → COMPLETED. 
# Missing prerequisite states: APPROVED, EXECUTED.
# Meaning: COMPLETED requires that execution has gone through APPROVED, EXECUTED
```

## Correct Approach
```python
# ✅ This will succeed:
contract = ExecutionContract(...)
contract = advance_execution_state(contract, "CREATED")      # OK
contract = advance_execution_state(contract, "APPROVED")     # OK: has CREATED
contract = advance_execution_state(contract, "EXECUTED")     # OK: has CREATED, APPROVED
contract = advance_execution_state(contract, "COMPLETED")    # OK: has CREATED, APPROVED, EXECUTED
```

## Where is Phase 4 Enforced?

**File:** `contracts/execution_contract.py`
**Function:** `advance_execution_state()`
**Validator:** `contracts/semantic_transition_validator.py`

```python
def advance_execution_state(contract, new_state, ...):
    # ... other validations ...
    
    # Phase 4: Semantic validation
    validate_semantic_transition_with_context(
        current_state=contract.execution_state,
        next_state=new_state,
        history=contract.execution_state_history,
        execution_id=contract.execution_id,
    )
    # If this raises ValueError, the transition is rejected
```

## Testing Phase 4

Run the test suite:
```bash
pytest tests/test_semantic_transition_validator.py -v
```

Key test cases:
- ✓ Valid transitions (full path)
- ✗ Invalid transitions (missing prerequisites)
- ✓ Failure paths (FAILED can occur from any state with CREATED)
- Error messages are clear and actionable

## Understanding Error Messages

When Phase 4 rejects a transition, you'll see:

```
[execution_id] Semantic transition invalid: CURRENT → NEXT.
Missing prerequisite states in history: STATE1, STATE2.
History: STATE → STATE → STATE.
Meaning: NEXT requires that execution has gone through STATE1, STATE2 before reaching this state.
```

## How to Add New States

1. Add to `ExecutionState` type in `execution_contract.py`
2. Add to `LEGAL_STATE_TRANSITIONS` in `execution_contract.py`
3. Define prerequisites in `SEMANTIC_PREREQUISITES` in `semantic_transition_validator.py`
4. Add test cases
5. Update documentation

Example:
```python
# In semantic_transition_validator.py
SEMANTIC_PREREQUISITES = {
    "CREATED": set(),
    "APPROVED": {"CREATED"},
    "EXECUTED": {"CREATED", "APPROVED"},
    "PAUSED": {"CREATED", "APPROVED"},        # ← NEW: like EXECUTED
    "COMPLETED": {"CREATED", "APPROVED", "EXECUTED"},
    "FAILED": {"CREATED"},
}
```

## Key Benefits

| Benefit | Why It Matters |
|---------|-----------------|
| **Prevents Logic Errors** | No way to skip approval or execution |
| **Ensures Audit Trail Validity** | History is guaranteed to follow business logic |
| **Catches Configuration Errors** | Invalid state advances are impossible |
| **Makes Governance Meaningful** | Signatures govern actual execution flow |

## Architecture: Four Phases of Validation

```
Phase 1: Replay Integrity (Lineage)
  ↓ Can the history be replayed?
Phase 2: Governance Authority (Contracts)
  ↓ Is this transition authorized?
Phase 3: Persistence Integrity (Immutability)
  ↓ Is the contract data correct?
Phase 4: Semantic Validity (Meaning)
  ↓ Does the history follow business logic?
     ↓
Verified Execution ✓
```

## Files Involved

| File | Role |
|------|------|
| `contracts/semantic_transition_validator.py` | Phase 4 validator implementation |
| `contracts/execution_contract.py` | Integrates Phase 4 into `advance_execution_state()` |
| `tests/test_semantic_transition_validator.py` | Comprehensive test suite |
| `PHASE4_SEMANTIC_VALIDATION.md` | Detailed documentation |

## Common Questions

**Q: Can I skip states?**
A: No. Phase 4 enforces prerequisites, so you must follow the path.

**Q: What if I need a different path?**
A: Update `SEMANTIC_PREREQUISITES` and the `LEGAL_STATE_TRANSITIONS` table, then add tests.

**Q: Does this affect existing executions?**
A: Only if their history violates Phase 4 rules. Well-formed executions are unaffected.

**Q: How is this different from Phases 1-3?**
A: Phases 1-3 protect the mechanics (integrity, authority, immutability). Phase 4 protects the meaning.
