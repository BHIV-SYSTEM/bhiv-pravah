# TASK 4.3.5 — EXECUTOR & PYTEST FORENSICS

## 1. Executor Implementation
- **Location**: `backend/reliability-controller2-main/executer/app.py`
- **Type**: Python Flask application.
- **Port**: 5003
- **Primary dependencies**: `flask`, `requests`, `docker` / `kubectl` (via `subprocess`), `core_hooks`, `security`.
- **Function**: Executes actions ("restart", "scale_up", "scale_down") against Docker or Kubernetes deployments based on `EXECUTION_MODE`.

## 2. Executor Startup Requirements
- **Command**: `docker-compose up -d executer` (via `backend/reliability-controller2-main/docker-compose.yml`) OR `python app.py`.
- **Environment Dependencies**: The executor natively imports `core_hooks.service_auth` and `security.nonce_store`. These modules exist in the `backend/` directory, meaning the Python path MUST include `backend/` for the executor to successfully boot.
- **Runtime Dependencies**: Requires Docker daemon access (`EXECUTION_MODE=docker`) or Kubernetes context (`EXECUTION_MODE=kubernetes`) to process actions.

## 3. Executor Availability
- **Status**: The service is **NOT RUNNING**.
- **Evidence**: `urllib.request.urlopen('http://localhost:5003/health')` returns `<urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>`.

## 4. Port Ownership
- **Command**: `netstat -ano | findstr :5003`
- **Result**: No output. No process currently owns or listens on port 5003.

## 5. Safe Startup Assessment
- **Feasibility**: **STARTABLE (Conditionally)**
- **Assessment**: The executor can technically be booted by setting `PYTHONPATH=.../backend` and running `python app.py`. However, doing so would expose a live service that actively manipulates Docker/K8s infrastructure (`subprocess.run(["docker", "restart", service_id])`). Running this service outside of an ephemeral sandbox or explicitly mocked environment poses a potential risk of destructive execution if live `service_id`s are dispatched. 

## 6. Exact `pytest -q` Collection Errors
Running `pytest -q` from the repository root yields 3 Collection Errors:
1. `VANA/tests/test_phase15_integration_boundary.py` -> `ModuleNotFoundError: No module named 'VANA'`
2. `backend/orchestrator/test_orchestrator.py` -> `ModuleNotFoundError: No module named 'build'`
3. `backend/scratch/test_imports.py` -> `agent_runtime.ConfigurationError: PRAVAH_MAIN_API is required for production Decision Brain execution.`

## 7. VANA Investigation
- **Error Source**: `VANA/tests/test_phase15_integration_boundary.py` line 17 (`from VANA.vana_integration import ...`)
- **Root Cause**: The test explicitly munges `sys.path` to inject `pravah-bhiv/backend`, allowing it to resolve `control_plane`. However, the root `pravah-bhiv` directory itself is never added to `sys.path`. When pytest scans this file, the Python interpreter cannot resolve the top-level `VANA` package.
- **Classification**: Test-layout / Configuration defect.

## 8. Orchestrator Investigation
- **Error Source**: `backend/orchestrator/app_orchestrator.py` line 9 (`from build.build_engine import BuildEngine`)
- **Root Cause**: The module `build_engine.py` or the `build` package does not exist anywhere within the repository tree. 
- **Classification**: Stale Code / API Drift. This is an obsolete/abandoned orchestrator file that references deleted dependencies.

## 9. Scratch Test Investigation
- **Error Source**: `backend/scratch/test_imports.py` line 18 (`agent = AgentRuntime(env="dev")`)
- **Root Cause**: The script instantiates the `AgentRuntime` immediately at module load time (top-level scope). This constructor performs a strict environment variable assertion (`PRAVAH_MAIN_API`). Because it's named `test_imports.py`, pytest attempts to parse/import the file during collection, triggering the hard crash.
- **Classification**: Scratch/Debug Code. This script was intended for manual execution, not automated pytest collection.

## 10. Current Pytest Configuration
- **File**: `pytest.ini` (Root)
- **testpaths**: `pravah-bhiv/backend/tests`, `pravah-bhiv/VANA/tests`
- **Root Cause of Bleed**: The `testpaths` in the root `pytest.ini` are misconfigured. They assume pytest is executed from one directory *above* `pravah-bhiv`. When executed inside `pravah-bhiv`, pytest cannot find `pravah-bhiv/backend/tests` and falls back to: `PytestConfigWarning: No files were found in testpaths... Searching recursively from the current directory instead.` This recursion bleeds into `scratch/`, `orchestrator/`, and misconfigured `VANA/` tests.

## 11. Collection-Mode Results
- `pytest --collect-only -q`: **FAILS** (3 Errors). The recursion bleeds into all unmaintained folders.
- `pytest backend/control_plane/capabilities/test_execution_rights_adapter.py --collect-only -q`: **SUCCEEDS** (21 tests collected).
- `pytest backend/tests --collect-only -q`: **SUCCEEDS** (207 tests collected).
- `pytest VANA/tests --collect-only -q`: **FAILS** (1 Error). The VANA module resolution error triggers.

## 12. Root Causes
1. **Executor Availability**: It is not orchestrated by default outside of the `docker-compose` environment.
2. **Pytest Failure**: `pytest.ini` has incorrect `testpaths` relative to the CWD, causing infinite recursive directory scanning that trips over obsolete (`orchestrator/`), sandbox (`scratch/`), and pathing-fragile (`VANA/`) Python scripts.

## 13. What is Proven
- The true reason `pytest -q` failed is a configuration/pathing error, NOT a compilation/syntax error in the primary application codebase.
- The executor (`bhiv-sarathi`) is completely offline but structurally intact.
- The 14 failures inside the primary test paths remain perfectly stable.

## 14. What remains unproven
- The cryptographic boundaries (Missing Contracts, Forged Signatures, Caller Identity) at the Golang/Python executor edge remain unproven because the service was purposely not started to avoid destructive side-effects.

## 15. Recommended Remediation Tasks
1. **Fix Pytest Configuration**: Update root `pytest.ini` `testpaths` to `backend/tests` and `VANA/tests` (removing the `pravah-bhiv/` prefix).
2. **Fix VANA Imports**: Properly inject the repository root into `PYTHONPATH` or `sys.path` within VANA tests, or convert it into an installable module.
3. **Ignore Obsolete Folders**: Add `backend/scratch` and `backend/orchestrator` to `norecursedirs` in `pytest.ini`.
