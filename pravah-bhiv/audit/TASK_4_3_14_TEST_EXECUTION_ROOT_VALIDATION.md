# TASK_4_3_14: Test Execution Root Validation

This report documents the resolution of the test execution-root/configuration inconsistency that resulted in 3 collection errors during a previous `pytest` run. No source code, tests, or configuration files were modified during this validation.

## 1. Git Repository Root vs Code Root
Executing `git rev-parse --show-toplevel` from `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah` returned:
```text
C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah
```
This is the true **Git Repository Root**. However, verifying the expected project paths from this directory resulted in failures:
- `Test-Path .\backend\tests` -> `False`
- `Test-Path .\VANA` -> `False`
- `Test-Path .\pytest.ini` -> `False`
- `Test-Path .\backend\pytest.ini` -> `False`

The actual application source code, tests, and pytest configuration files are nested one directory deeper inside the `pravah-bhiv` subfolder. 

The true **Code Execution Root** is:
```text
C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv
```

## 2. Pytest Execution from the Git Root (The Cause of Collection Errors)
Running `pytest --collect-only -q` from the Git Root (`bhiv-pravah`) traversed into the `pravah-bhiv` subdirectory, discovering 247 tests. Because `pytest` was executed from a directory above the actual source code, the Python `sys.path` did not contain the correct module roots (like `./VANA` or `./backend/orchestrator`). 

This produced the exact 3 collection errors previously observed:
1. `ERROR pravah-bhiv/VANA/tests/test_phase15_integration_boundary.py` (`ModuleNotFoundError: No module named 'VANA'`)
2. `ERROR pravah-bhiv/backend/orchestrator/test_orchestrator.py` (`ModuleNotFoundError: No module named 'build'`)
3. `ERROR pravah-bhiv/backend/scratch/test_imports.py` (`agent_runtime.ConfigurationError: PRAVAH_MAIN_API is required`)

## 3. The Authoritative Final Baseline
To achieve the correct baseline, all future `pytest` executions must be run from the **Code Execution Root**:
```powershell
cd C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv
```

Running `pytest -q` from this authoritative root yields the final trustworthy baseline:
- **Pytest rootdir**: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv\backend` (resolved automatically via `backend/pytest.ini`).
- **Configuration file used**: `pytest.ini` (at `pravah-bhiv/pytest.ini`)
- **Total Tests Run**: 216
- **Collection Errors**: 0
- **Passed**: 215
- **Failed**: 1
- **Remaining Failures**: `backend/tests/test_phase10_group1_integration.py::test_group1_observation_api_live_health`

## 4. Phase 15 Independent Verification
Running Phase 15 independently from the authoritative Code Execution Root:
```powershell
pytest -q backend/tests/test_phase15_gap_governed_abstention.py
```
**Result**: 30 passed, 0 failed. 

## Acceptance Criteria Met
- **No changes**: No source code, tests, or configurations were modified.
- **Git Root vs Code Root Proven**: The Git root is `bhiv-pravah`, but the Code/Execution root is `pravah-bhiv`.
- **Collection Errors Explained**: The errors occurred because `pytest` was executed one directory too high, breaking `sys.path` resolution.
- **Final Baseline Established**: The full test suite has exactly 1 failure (the Phase 10 deployment gap) and 0 collection errors when run from the correct directory.
