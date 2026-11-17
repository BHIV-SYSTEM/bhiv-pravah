# Task 1 Final Verification

## Git State
- **`git status --short`:** Shows multiple untracked files generated during audit runs (logs, JSON dumps). Both `pytest.ini` files are listed as untracked `?? pytest.ini` and `?? backend/pytest.ini`. No application source code has been modified.
- **`git diff --stat`:** `pravah-bhiv/backend/security/nonce_store.json | 2 +-` (Just a state modification in a JSON data file during testing).

## pytest.ini Inventory
Exactly two `pytest.ini` files exist:
1. **`pravah-bhiv/pytest.ini`** (Newly created / untracked)
   ```ini
   [pytest]
   testpaths =
       backend/tests
       VANA/tests
   ```
2. **`pravah-bhiv/backend/pytest.ini`** (Newly created / untracked)
   ```ini
   [pytest]
   testpaths = tests
   ```
These files restrict test discovery to the explicit `tests` directories, avoiding recursive discovery into manual scratch scripts.

## Collection Result
- **`pytest --collect-only -q`:** Completes without interruption.
- **collected:** 216
- **errors:** 0
- **warnings:** Captured normally, no collection abort.

## Full Test Result
- **passed:** 201
- **failed:** 15
- **skipped:** 0
- **xfailed:** 0
- **xpassed:** 0
- **errors:** 0
- **warnings:** 333
- **deselected:** 0

## Exact Test Accounting
- Collected: 216
- Executed (Passed + Failed): 201 + 15 = 216
- The total strictly matches the collection count.

## All Remaining Failures
The 15 failing tests are:
1. `backend/tests/adversarial_test_suite/test_deterministic_recovery.py::test_recovery_has_no_drift`
   - **Failure type:** `AssertionError: assert False is True`
   - **Root cause:** Validation fails because `trace_valid` is False.
   - **Classification:** Application/Test bug (Recovery Validator logic).
2. `backend/tests/test_phase10_group1_integration.py::test_group1_observation_api_live_health`
   - **Failure type:** `AssertionError: Endpoint is missing in registry`
   - **Root cause:** Group1 API not registered in the environment test harness.
   - **Classification:** Test configuration / Environment issue.
3-5. `backend/tests/test_phase15_gap_governed_abstention.py` (3 tests)
   - **Failure type:** `AttributeError: module 'backend' has no attribute 'tests'`
   - **Root cause:** Bad import statement within the test file.
   - **Classification:** Test bug.
6-9. `backend/tests/test_phase5_deployment_validators.py` (4 tests)
   - **Failure type:** `AssertionError: assert False is True` / Hash mismatch
   - **Root cause:** State hash mismatch during restart recovery.
   - **Classification:** Application/Test bug.
10-11. `backend/tests/test_phase8_execution_closure.py` (2 tests)
   - **Failure type:** `TypeError: execute_action() got an unexpected keyword argument 'requested_capability'`
   - **Root cause:** Test calls `execute_action()` with obsolete kwargs.
   - **Classification:** Stale/Legacy test.
12-14. `backend/tests/test_phase8_execution_closure.py` (3 tests)
   - **Failure type:** `TypeError: SafeOrchestrator.__init__() got an unexpected keyword argument 'execution_mode'` & `ConfigurationError: PRAVAH_MAIN_API is required`
   - **Root cause:** Outdated method signature and missing env mock.
   - **Classification:** Stale/Legacy test & Test config issue.
15. `backend/tests/test_unified_discovery.py::test_unified_discovery`
   - **Failure type:** `AssertionError: 0 == 8`
   - **Root cause:** Discovery engine returned empty list instead of 8 capabilities.
   - **Classification:** Application/Test bug.

## Build Import Investigation
- **Import:** `from build.build_engine import BuildEngine` inside `backend/orchestrator/app_orchestrator.py`
- **Does `build/build_engine.py` exist?** No.
- **Is `app_orchestrator.py` used?** It is only referenced by manual debug scripts like `onboarding_entry.py`, `test_orchestrator.py`, and `deploy_orchestrator.py`. None of these are in the active decision or control plane flow.
- **BUILD STATUS:** BROKEN APPLICATION CODE / LEGACY. The file is stale and correctly excluded from pytest discovery.

## VANA Import Investigation
- **Failure:** `ModuleNotFoundError: No module named 'VANA'`
- **Investigation:** `VANA/` does not contain an `__init__.py` file (it is a namespace package). When tests were recursively discovered from a subfolder, `VANA/` was excluded from Python's `sys.path`.
- **Resolution:** Setting `pytest.ini` in the repository root makes `pravah-bhiv` the pytest `rootdir`, properly appending it to `sys.path`. The import is a legitimate package import when executed from the repository root.

## PRAVAH_MAIN_API Investigation
- **Where read:** `backend/agent_runtime.py` inside `AgentRuntime.__init__` and `HTTPDecisionProvider`.
- **Usage:** Used to point the agent to the `decision-brain` service in production.
- **Tests:** Most tests correctly mock this using `@patch.dict(os.environ, {"PRAVAH_MAIN_API": "http://decision-brain:8000"}, clear=True)`.
- **Why it failed previously:** `scratch/test_imports.py` runs at module level instantly when parsed, instantiating `AgentRuntime` outside of any mock context. It is a manual debug script, not a pytest.

## pytest.ini Correctness Assessment
Restricting testpaths via `pytest.ini` is the **correct and appropriate fix**.
Both `backend/orchestrator/test_orchestrator.py` and `backend/scratch/test_imports.py` are manual debugging scripts utilizing `if __name__ == "__main__":` with `argparse` and threads. They are explicitly NOT pytest-compatible suites. Excluding them from test discovery prevents `pytest` from crashing on broken legacy imports or module-level execution blocks.

## Production Code Impact
No production code was modified during this baseline verification.

## Task 1 Acceptance Criteria
- [x] Collection succeeds
- [x] Exact test accounting reconciles (15 + 201 = 216)
- [x] All 15 remaining failures classified
- [x] `pytest.ini` correctly placed
- [x] No duplicate/unintended `pytest.ini` files
- [x] No application behavior modified
- [x] `build` import explicitly classified (LEGACY)
- [x] VANA import issue classified (PYTHONPATH/rootdir scoping)
- [x] `PRAVAH_MAIN_API` requirement classified
- [x] Remaining failures understood

**Status:** PASS
