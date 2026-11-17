# TASK_4_3_13: Phase 15 Test Isolation Remediation

This report documents the resolution of the Phase 15 test isolation failures identified in Task 4.3.12. 

## 1. Root Cause
The 3 failing tests in `test_phase15_gap_governed_abstention.py` used a string-based mock target:
```python
with patch("backend.tests.test_phase15_gap_governed_abstention.ActionGovernance.evaluate_contract", ...)
```
When `pytest` collects the full test suite with `backend` as the rootdir, it resolves test files under the `tests.*` namespace, not `backend.tests.*`. The string-based patch attempted to dynamically resolve `backend.tests`, which caused Python's `sys.modules` to throw an `AttributeError` because `backend` is treated as a namespace package lacking a `tests` attribute in that execution context. This fragile pathing caused the tests to pass in isolation but fail in the full suite.

## 2. Exact Change
In `backend/tests/test_phase15_gap_governed_abstention.py`, I replaced the three fragile string patches with robust object-based patching using the actual imported `ActionGovernance` class:

**Before:**
```python
with patch("backend.tests.test_phase15_gap_governed_abstention.ActionGovernance.evaluate_contract", return_value=approved_decision):
```

**After:**
```python
with patch.object(ActionGovernance, "evaluate_contract", return_value=approved_decision):
```
This guarantees the patch targets the exact `ActionGovernance` object consumed by the test regardless of test-collection namespace paths.

## 3. Before/After Test Results

### Before Remediation:
- **Phase 15 Isolated**: 30 passed, 0 failed.
- **Full Suite**: 4 failures (including 3 from Phase 15).

### After Remediation:
- **Phase 15 Isolated**: 30 passed, 0 failed.
- **Full Suite**: 1 failure, 215 passed. (The only remaining failure is the explicitly preserved Phase 10 Group1 deployment gap).
- **Phase 15 Full Suite Contribution**: 0 failures. 

## 4. Proof of Zero Production Modification
A `git diff` against `backend/control_plane/` and `backend/security/` confirms that no production logic, governance behaviors, or safety invariants were altered. 
- `backend/security/nonce_store.json` recorded standard nonce churn from running the tests.
- `test_phase15_gap_governed_abstention.py` contains exactly the three `patch.object()` corrections.

No tests were skipped, no assertions were weakened, and no production boundaries were compromised. The Phase 15 suite is completely remediated.
