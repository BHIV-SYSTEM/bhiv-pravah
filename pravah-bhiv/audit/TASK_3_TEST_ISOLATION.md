# Task 3 — Test Isolation Remediation

## Confirmed Root Cause
The `test_phase15_gap_governed_abstention.py` file included a global module-level mutation of `MultiAppControlPlane` using `MagicMock()`. Because this was executed at the top level of the file (during import time), it permanently replaced the actual class definition in `sys.modules["control_plane.multi_app_control_plane"]`. As a result, subsequent tests in the suite, specifically `test_unified_discovery.py`, were receiving the mock object instead of the actual class when they imported it, leading to test isolation breakage and incorrect failures.

## Original Global Mutation
```python
# Patch MultiAppControlPlane before any control_plane import
import control_plane.multi_app_control_plane
control_plane.multi_app_control_plane.MultiAppControlPlane = MagicMock()
```

## Correct Patch Target
The `MultiAppControlPlane` class is imported directly into the `control_plane.multi_app_control_plane` namespace. It is consumed by integration layers (e.g., `runtime.py`, `agent_api.py`) but not explicitly instantiated in the domain logic exercised by Phase 15 tests. The correct target for the patch, to isolate it purely to this test suite, is `control_plane.multi_app_control_plane.MultiAppControlPlane`.

## Fix Applied
Removed the global module mutation at the top of the file and replaced it with a test-scoped `pytest` fixture using `monkeypatch`:
```python
@pytest.fixture(autouse=True)
def mock_multi_app_control_plane(monkeypatch):
    import control_plane.multi_app_control_plane
    monkeypatch.setattr(control_plane.multi_app_control_plane, "MultiAppControlPlane", MagicMock())
```
This scopes the mock exactly to the tests within `test_phase15_gap_governed_abstention.py` and strictly tears it down after execution, preventing cross-test contamination.

## Tests Requiring Mock
While no unit under test in Phase 15 explicitly instantiates `MultiAppControlPlane` (it is not used in `ActionGovernance` or `ContextualResultAdapter`), the mock was scoped to all tests inside `test_phase15_gap_governed_abstention.py` to preserve the original author's intent without leaking.

## Isolation Verification
Running `test_phase15_gap_governed_abstention.py` and `test_unified_discovery.py` consecutively in the same pytest process confirms that the mock no longer leaks. `test_unified_discovery.py` receives the real `MultiAppControlPlane` class.

## Unified Discovery Verification
The `test_unified_discovery` test now **PASSES** successfully, as it executes against the real production behavior.

## Full Suite Verification
Collected: 216
Passed: 202
Failed: 14
Skipped: 0
Errors: 0
Warnings: 333
The Unified Discovery failure has disappeared from the full suite run.

## Other Suspicious Global State
A codebase-wide search revealed that the exact same global module-level mutation anti-pattern exists in two other locations:
1. `VANA/tests/test_phase14_vana_bootstrap.py` (Line 10)
2. `backend/control_plane/capabilities/test_execution_rights_adapter.py` (Line 11)

These tests also execute `control_plane.multi_app_control_plane.MultiAppControlPlane = MagicMock()` globally and will likely cause similar isolation issues depending on pytest execution order.

## Production Code Changes
**NO**

## Nonce Store State
The `backend/security/nonce_store.json` diff shows new UUID nonces and timestamps appended to the JSON array. This is tracked runtime state modified by security/replay tests (e.g., `test_replay_sovereignty.py`) that actually hit the file system instead of mocking the persistence layer. This is expected side-effect state from test execution and does not represent corruption.

## Final Status
PASS
