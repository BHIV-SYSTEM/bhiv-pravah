# Phase 4 Semantic Guard - Developer Cheat Sheet

## What Is Phase 4?

Phase 4 prevents **semantically invalid state transitions** - transitions that are structurally allowed but logically impossible.

## Core Rules: One-Liner Format

```
CREATED    → Can go to: APPROVED, FAILED
APPROVED   → Can go to: EXECUTING, FAILED
EXECUTING  → Can go to: COMPLETED, FAILED
COMPLETED  → Terminal (no further transitions)
FAILED     → Terminal (no further transitions)

COMPLETED requires in history: CREATED + APPROVED + EXECUTING (ALL three)
EXECUTING requires in history: CREATED + APPROVED (both)
APPROVED  requires in history: CREATED (at least)
FAILED    requires in history: CREATED (at least)
```

## Invalid Transitions (Blocked by Phase 4)

```
❌ CREATED → COMPLETED         (missing APPROVED, EXECUTING)
❌ CREATED → EXECUTING         (missing APPROVED)
❌ APPROVED → COMPLETED        (missing EXECUTING)
❌ EXECUTING → APPROVED        (backwards - not allowed)
❌ COMPLETED → EXECUTING       (terminal state - locked)
❌ FAILED → EXECUTING          (terminal state - locked)
```

## Rejection Codes (Learn Them)

| Code | Meaning |
|------|---------|
| `state_prerequisite_missing` | History lacks required states |
| `semantic_transition_invalid` | Transition not in FSM |
| `terminal_state_transition` | Trying to exit terminal state |
| `hidden_state_detected` | State in history but not in lineage |
| `synthetic_state_injected` | State without prerequisites |
| `governance_state_violation` | Governance insufficient |

## API Functions

### Validate Single Transition

```python
from control_plane.security.semantic_guard_engine import validate_state_transition

validate_state_transition(
    execution_id="exec_123",
    current_state="CREATED",
    next_state="APPROVED",
    history=("CREATED",),
)
# Raises ValueError if invalid
```

### Validate Entire History

```python
from control_plane.security.semantic_guard_engine import validate_state_history

validate_state_history(
    execution_id="exec_123",
    history=("CREATED", "APPROVED", "EXECUTING", "COMPLETED"),
)
# Detects hidden states
```

### Validate Replay Chain

```python
from control_plane.security.semantic_guard_engine import validate_replay_chain

validate_replay_chain(
    execution_id="exec_123",
    replay_events=[...],
)
# Reconstructs history from lineage and validates
```

## Integration Point

Phase 4 is **automatically called** in `advance_execution_state()`:

```python
from contracts.execution_contract import ExecutionContract, advance_execution_state

contract = ExecutionContract(...)

# Phase 4 validates automatically:
contract = advance_execution_state(
    contract,
    next_state="APPROVED",
    governance_state=None,  # Optional: pass governance state if coupling needed
)
```

**No additional code needed** - Phase 4 is built in.

## Error Message Format

```
[execution_id] Semantic guard violation: 
SEMANTIC VIOLATION: violation_code
Attempted transition: CURRENT → NEXT
Missing states: STATE1, STATE2
History: CREATED → APPROVED
```

## Debugging Checklist

If you get a Phase 4 rejection:

1. ✓ Check the violation code (tells you what's wrong)
2. ✓ Check the missing states (what's needed in history)
3. ✓ Verify execution history is correct
4. ✓ If hidden state, check lineage events
5. ✓ If governance violation, check governance_state parameter

## Valid Execution Path (The Happy Path)

```
CREATED
  ↓ (via advance_execution_state(..., "APPROVED"))
APPROVED
  ↓ (via advance_execution_state(..., "EXECUTING"))
EXECUTING
  ↓ (via advance_execution_state(..., "COMPLETED"))
COMPLETED ✓ (Terminal - success)
```

Or with failure:

```
CREATED → APPROVED → EXECUTING → FAILED ✓ (Terminal - failure)
```

## Common Mistakes & Fixes

### Mistake 1: Skipping Approval

```python
❌ Wrong:
contract = advance_execution_state(contract, "EXECUTING")
# History: CREATED → EXECUTING
# Result: REJECTED (missing APPROVED)

✅ Correct:
contract = advance_execution_state(contract, "APPROVED")
contract = advance_execution_state(contract, "EXECUTING")
# History: CREATED → APPROVED → EXECUTING
# Result: OK
```

### Mistake 2: Assuming Terminal States Are Optional

```python
❌ Wrong:
contract = advance_execution_state(contract, "COMPLETED")
# Without going through EXECUTING first
# Result: REJECTED (missing EXECUTING)

✅ Correct:
contract = advance_execution_state(contract, "EXECUTING")
contract = advance_execution_state(contract, "COMPLETED")
```

### Mistake 3: Trying to Exit Terminal

```python
❌ Wrong:
contract.execution_state = "COMPLETED"
contract = advance_execution_state(contract, "EXECUTING")
# Result: REJECTED (terminal state lock)

✅ Correct:
# Terminal states are final - no way out
# Must create new execution if retry needed
```

### Mistake 4: Hidden State Injection

```python
❌ Wrong:
history = ("CREATED", "EXECUTING")  # APPROVED missing!
validate_state_history(execution_id="exec_123", history=history)
# Result: REJECTED (missing APPROVED in history)

✅ Correct:
history = ("CREATED", "APPROVED", "EXECUTING", "COMPLETED")
validate_state_history(execution_id="exec_123", history=history)
# Result: OK
```

## Performance Impact

- Per-transition overhead: ~50 microseconds
- Total overhead negligible (< 0.1% of execution time)
- No optimization needed

## Testing Phase 4

```bash
# Run all Phase 4 tests
pytest tests/test_phase4_semantic_guards.py -v

# Run specific test
pytest tests/test_phase4_semantic_guards.py::TestInvalidSemanticJumps -v

# Run with coverage
pytest tests/test_phase4_semantic_guards.py --cov=control_plane.security
```

## When to Use governance_state Parameter

```python
# Use when you want to enforce governance coupling:
contract = advance_execution_state(
    contract,
    "EXECUTING",
    governance_state="APPROVED",  # Governance must be at least APPROVED
)

# Omit if governance coupling not needed:
contract = advance_execution_state(
    contract,
    "EXECUTING",
)
```

## Semantic FSM Quick Reference

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐
│ CREATED │───→│ APPROVED │───→│ EXECUTING│───→│ COMPLETED │
└─────────┘    └──────────┘    └──────────┘    └───────────┘
    │               │               │                │
    │               │               │                │
    └───────────────┼───────────────┼────────────────┘
                    │               │
                    v               v
                 ┌──────┐       (Terminal)
                 │FAILED│
                 └──────┘
              (Terminal)

Arrows show ONLY valid transitions.
No shortcuts, no backdoors, no exceptions.
```

## Error Recovery

If Phase 4 rejects a transition:

```python
try:
    contract = advance_execution_state(contract, next_state)
except ValueError as e:
    logger.error(f"Phase 4 violation: {e}")
    # Determine what went wrong
    # Usually: wrong next_state or skipped required state
    # Fix: Check execution history and retry correct path
```

## Advanced: Checking Before Attempt

```python
from control_plane.security.semantic_guard_engine import get_semantic_guard

engine = get_semantic_guard()

# Check if transition would be valid
result = engine.validate_transition(
    execution_id="exec_123",
    current_state="CREATED",
    next_state="EXECUTING",
    history=("CREATED",),
)

if result:  # None means valid, report object means invalid
    print(f"Would be rejected: {engine.explain_violation(result)}")
else:
    print("Transition would be accepted")
```

## Key Takeaways

1. **Phase 4 is always active** - No opt-in, no configuration needed
2. **Invalid jumps are impossible** - Not just prevented, structurally blocked
3. **Error messages are specific** - They tell you exactly what's wrong
4. **Performance is negligible** - ~50 µs per transition
5. **Follow the happy path** - CREATED → APPROVED → EXECUTING → COMPLETED
6. **Terminal states are final** - COMPLETED and FAILED have no exits
7. **Hidden states are detected** - Lineage must match history

## Questions?

- **How do I debug a rejection?** → Check the rejection code and missing states
- **Can I disable Phase 4?** → Not recommended, but code is in execution_contract.py
- **Will this break existing code?** → Only if code was doing invalid transitions
- **What if I need different rules?** → Update TRANSITION_PREREQUISITES in semantic_guard_engine.py

## One-Minute Summary

Phase 4 ensures execution history follows business logic:
- ✓ You cannot skip approval
- ✓ You cannot skip execution  
- ✓ You cannot inject hidden states
- ✓ You cannot exit terminal states
- ✓ Every transition is validated against prerequisites

**Result:** Execution integrity at the semantic level.
