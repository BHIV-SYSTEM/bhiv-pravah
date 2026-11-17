# TASK 4.3.2 — EVIDENCE PATH FORENSICS

## 1. Git HEAD version of execution_rights_adapter.py
The `git show HEAD:pravah-bhiv/backend/control_plane/capabilities/execution_rights_adapter.py` command reveals the exact original mapping state:
```json
        "evidence": {
            "file": "contracts/execution_contract.py",
            "line": 194
        }
```

## 2. Current working-tree version
The current uncommitted modification in `backend/control_plane/capabilities/execution_rights_adapter.py` reveals the mapping is currently:
```json
        "evidence": {
            "file": "backend/contracts/execution_contract.py",
            "line": 194
        }
```

## 3. Current evidence mapping
As established above, the active mapping string being used by the runtime in the current tree is `backend/contracts/execution_contract.py`.

## 4. Actual repository file locations
Checking `Path.cwd()` directly in Python yields:
- `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv\contracts\execution_contract.py` -> **exists: False** (file: False)
- `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv\backend\contracts\execution_contract.py` -> **exists: True** (file: True)

## 5. Actual PROJECT_ROOT value
The expression used in `ExecutionRightsAdapter`:
```python
PROJECT_ROOT = Path(__file__).resolve().parents[3]
```
At runtime, this unambiguously resolves to:
```
C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv
```
This resolution is entirely static based on file location and does NOT change depending on the runtime working directory (CWD).

## 6. Actual path-resolution algorithm
The resolution algorithm from the source is explicitly:
```python
    project_root = PROJECT_ROOT.resolve()
    candidate = (project_root / evidence_file).resolve()
    if not candidate.is_file():
        raise MappingNotFound(...)
```

## 7. Resolution of: contracts/execution_contract.py
Using the exact path-resolution algorithm, `contracts/execution_contract.py` resolves to:
`C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv\contracts\execution_contract.py`
**Result:** exists? False, is_file? False.

## 8. Resolution of: backend/contracts/execution_contract.py
Using the exact path-resolution algorithm, `backend/contracts/execution_contract.py` resolves to:
`C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv\backend\contracts\execution_contract.py`
**Result:** exists? True, is_file? True.

## 9. Direct production authorize_execution() result
Running a raw invocation of `authorize_execution('governed-execution', 'restart')` against the current unmocked production state outputs:
```
SUCCESS
{'capability_id': 'governed-execution', 'action': 'restart', 'authorized_source_id': 'governance', 'role': 'execution_authority', 'allowed_actions': ['restart', 'scale_up', 'scale_down', 'rollback'], 'mapping_status': 'VERIFIED', 'evidence': {'file': 'backend/contracts/execution_contract.py', 'line': 194}, 'signature': '0127adacb35f0a60cf5dc28a90e8b5f91dcdb043b0bb1ae85a7e22ca2720b456'}
```

## 10. Whether the unit tests use production mapping or injected mapping
Inspection of `backend/control_plane/capabilities/test_execution_rights_adapter.py` unequivocally proves that the 21 passing unit tests DO NOT use the production `VERIFIED_CAPABILITY_MAPPINGS`.
Instead, they use an injected mock fixture `valid_adapter`:
```python
TEST_EVIDENCE_FILE = "backend/control_plane/capabilities/execution_rights_adapter.py"

def valid_mapping_data():
    return {
        "test-capability": {
             # ...
            "evidence": {
                "file": TEST_EVIDENCE_FILE, ...
            }
        }
    }
```
The test suite's 100% pass rate historically masked the broken path in the production dictionary, as the dictionary was completely mocked out during the unit tests.

## 11. Exact test results
Running the unit test suite yields:
`21 passed, 3 warnings in 0.61s`
Running the direct production authorization script yields `SUCCESS`.

## 12. Current production diffs
The current git working tree contains the following uncommitted modifications introduced during Task 4.3:
- `backend/control_plane/backend/app/main.py`: Updated `execute_action()` to actively authorize capabilities against `ExecutionRightsAdapter`.
- `backend/control_plane/capabilities/execution_rights_adapter.py`: Updated `VERIFIED_CAPABILITY_MAPPINGS` to correct the broken path to `backend/contracts/execution_contract.py`.
- `backend/control_plane/capabilities/test_execution_rights_adapter.py`: Updated to include a spy that asserts Governance context assembly natively, and mock `ActionGovernance` persistence paths to isolate E2E state.

## 13. Final determination
The original repository HEAD state was fundamentally broken for production runtime environments. 
Because `PROJECT_ROOT` resolves to `pravah-bhiv` statically, the legacy path string `contracts/execution_contract.py` resolved to a nonexistent file path, causing an unhandled `MappingNotFound` exception.
This broken state was completely obscured because the unit test suite bypassed the production dictionary and injected its own static mappings. The E2E tests previously failed this authorization and were heavily monkeypatched.

The change to `backend/contracts/execution_contract.py` is the **correct, objective, and only functionally viable path** under the current source code's resolution logic.
