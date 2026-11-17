# TASK_4_3_12: Remaining Failure Forensics

This report documents the forensic investigation of the 4 remaining test failures in the Pravah backend test suite. No production code, test code, or configurations were modified during this investigation.

## Baseline
`git status --short` confirms a clean workspace (temporary files removed, tracked files unmodified).
Running `pytest -q` produces the following exact 4 failures out of 216 tests:
1. `backend/tests/test_phase10_group1_integration.py::test_group1_observation_api_live_health`
2. `backend/tests/test_phase15_gap_governed_abstention.py::test_governance_allows_noop_contract`
3. `backend/tests/test_phase15_gap_governed_abstention.py::test_full_gap_flow_no_operational_execution`
4. `backend/tests/test_phase15_gap_governed_abstention.py::test_abstention_evidence_written_to_ledger`

## Failure Classifications

| Test | Exact Failure | Production Behavior | Classification | Evidence | Recommended Next Action |
| ---- | ------------- | ------------------- | -------------- | -------- | ----------------------- |
| `test_group1_observation_api_live_health` | `AssertionError: Endpoint is missing in registry` | The group 1 observation API capability is successfully registered but is in `PENDING` deployment status with `endpoint: null`. | **ENVIRONMENT NOT READY** / **DEPLOYMENT/INTEGRATION GAP** | `registry/group1-observation-api.json` confirms `"live_endpoint_available": false` and `"endpoint": null`. The test assumes a live deployment exists. | Wait for actual deployment of Group 1 Observation API or mock the registry if isolated testing is desired. |
| `test_governance_allows_noop_contract` | `AttributeError: module 'backend' has no attribute 'tests'` during `patch(...)` setup | `ActionGovernance` correctly allows `noop` contracts. | **TEST DEFECT** | Fails only during full test suite run. `patch` uses a fragile string path (`"backend.tests..."`) which breaks depending on how `pytest` initializes `sys.modules` and the `rootdir`. | Rewrite the patch using `patch.object(ActionGovernance, ...)` or use the correct relative module path. |
| `test_full_gap_flow_no_operational_execution` | `AttributeError: module 'backend' has no attribute 'tests'` during `patch(...)` setup | The GAP flow successfully translates to `noop` and proceeds through governance without triggering operational changes. | **TEST DEFECT** | Passes perfectly in isolation. Fails in full suite purely because of the same fragile `mock.patch` string path issue. | Rewrite the patch using `patch.object`. |
| `test_abstention_evidence_written_to_ledger` | `AttributeError: module 'backend' has no attribute 'tests'` during `patch(...)` setup | The recorder successfully writes a `GOVERNED_ABSTENTION` event to the `AppendOnlyLog` with correct provenance. | **TEST DEFECT** | Passes perfectly in isolation. Fails in full suite purely because of the same fragile `mock.patch` string path issue. | Rewrite the patch using `patch.object`. |

## Phase 10 (Group 1 Integration) Forensics
* **Endpoint Expected:** The test discovers `group1-observation-api` and attempts to hit `<endpoint>/health`.
* **Endpoint Source:** `backend/control_plane/capabilities/registry/group1-observation-api.json`.
* **Current Registry State:** The registry explicitly declares `"endpoint": null` and `"deployment_status": "PENDING"`.
* **Nature of Test:** It is a live integration test asserting a true network connection. Because the environment has not been fully provisioned (PostGIS/VM deployment is pending), the test fails correctly.

## Phase 15 (Governed Abstention) Forensics
* **Isolation Analysis:** 
  * Running `pytest -q backend/tests/test_phase15_gap_governed_abstention.py` independently **passes flawlessly** (30 passed, 0 failed).
  * Running individual tests via `::test_name` also **passes flawlessly**.
* **Failure Cause:** The failures occur only during full-suite test collection (`pytest -q`). The three failing tests contain the following context manager:
  ```python
  with patch("backend.tests.test_phase15_gap_governed_abstention.ActionGovernance.evaluate_contract", return_value=approved_decision):
  ```
  This is a fragile mock target. When `pytest` executes from the root with the corrected `pytest.ini`, the test files are loaded as `tests.test_phase15...`. Because `backend` is not a real Python package (no `__init__.py`), Python treats it as a namespace package. When `mock.patch` tries to dynamically resolve `backend.tests...` during the full test run (where `sys.modules` is heavily populated), it fails to find the `tests` submodule under the `backend` namespace, throwing an `AttributeError`.
* **Conclusion:** Production code is fully intact and functioning as specified. The failures are entirely due to improper patching strategy in the tests themselves. Our recent fix to `pytest.ini` (which properly aligned test collection) exposed this pre-existing fragile path. 

**Acceptance Criteria Met:**
- No production changes made.
- No tests modified, skipped, or weakened.
- Forensics strictly relied on test output and source verification.
