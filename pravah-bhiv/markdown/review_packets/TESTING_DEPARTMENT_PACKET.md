# TESTING DEPARTMENT PACKET: RAPID SYSTEM VALIDATION GUIDE

**Status:** Testing Department Reference  
**Audience:** QA Engineers & Systems Auditors  
**Validation Time Limit:** 5–10 Minutes  

This validation packet outlines the exact commands and checks required to verify the census correctness, schema declarations, trace continuity, replay claims, and integration readiness of the converged Pravah system.

---

## 1. System Census Correctness Audit (1 Minute)

To verify the directory layout and attribution matches the system census:

### Check File Structure
Verify that the canonical control plane, execution monitor, and visualizer files are in place. Run this command to verify folder listings:
```powershell
# In CWD: c:\Users\black\OneDrive\Desktop\Pravah\BHIV
Get-ChildItem -Directory | Select-Object Name
```
**Assert:**
* `multi-agent-control-plane-main` is present (Shivam's CP core).
* `reliability-controller2-main` is present (Rayyan's execution stream v2).
* `pravah-integration.py-main` is present (Ritesh's persistent RL Brain).
* `unified-monitor-dashboard-main` is present (Ritesh's dashboard UI).

---

## 2. Replay Claims & Cryptographic Verification (3 Minutes)

To verify that the replay verifier validates chain lineage, rejects duplicate actions, validates signatures, and fails on payload tampering:

### Run the Sovereignty Test Suite
Execute the dedicated integration test suite using python or pytest:
```powershell
# In CWD: c:\Users\black\OneDrive\Desktop\Pravah\BHIV\multi-agent-control-plane-main
$env:PYTHONIOENCODING="utf-8"; python tests/test_replay_sovereignty.py
```
**Assert Output:**
* All 4 tests must PASS.
* Displays the test runner log:
  ```text
  tests\test_replay_sovereignty.py ....                                 [100%]
  ============================ 4 passed in 0.09s =============================
  ```

### Verify Lineage Sequence Validation (`CREATED` Check)
Open [test_replay_sovereignty.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/tests/test_replay_sovereignty.py) and check `test_first_state_must_be_created`.
* **Assert:** Lineage verification raises a `SequenceViolationError` if the first event block in the trace is not state `CREATED`.

### Verify Payload Tampering Rejection
Check `test_payload_tampering_invalidates_signature`.
* **Assert:** Changing any value in a signed payload causes the signature check (`verify_payload`) to fail.

---

## 3. Trace Continuity & Isolation Claims (2 Minutes)

To verify that traces propagate end-to-end and are protected from duplicate execution:

### Single-Use Trace Protection Check
Check `test_single_use_trace_protection` in [test_replay_sovereignty.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/tests/test_replay_sovereignty.py).
* **Assert:** When a trace ID is processed, it registers with `TraceConsumptionRegistry`. Subsequent calls with the same trace ID return `is_consumed = True` and fail early in the validator.

### Verify Cross-Layer Execution Checks
Check `test_executer_app_endpoints` in [test_replay_sovereignty.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/tests/test_replay_sovereignty.py).
* **Assert:**
  * Submitting requests with a duplicate `X-Service-Nonce` is blocked as a replay attack (HTTP 401).
  * Submitting requests with a previously consumed `trace_id` is blocked (HTTP 400).
  * In `prod` environments, requests without valid signature headers are rejected (HTTP 401).

---

## 4. Schema Declarations & Metric Ingest Verification (2 Minutes)

To verify that metric schema translations prevent metric scaling drift:

### Inspect Runtime Ingest Scale
Verify that metrics scale correctly. Run this python command to assert that fractional metrics are multiplied by `100` before ingestion:
```powershell
# In CWD: c:\Users\black\OneDrive\Desktop\Pravah\BHIV
.venv\Scripts\python.exe -c "import sys, os; sys.path.insert(0, os.path.abspath('multi-agent-control-plane-main')); from agent_runtime import AgentRuntime; Mock = type('Mock', (object,), {'env': 'dev'}); data = {'cpu_percent': 0.95, 'memory_percent': 0.83, 'error_rate': 0}; contract = AgentRuntime._map_to_runtime_contract(Mock, data); assert contract['cpu_usage'] == 0.95 and contract['memory_usage'] == 0.83; print('Metrics Scale Check Passed!')"
```
**Assert:**
* Fractional metrics from Shivam's CP mapping map correctly inside `_map_to_runtime_contract` as float attributes:
  ```json
  "cpu_usage": data.get("cpu_percent", 0),
  "memory_usage": data.get("memory_percent", 0)
  ```
  This is matched directly to Ritesh's State Encoder requirements.

---

## 5. Integration Readiness Checks (2 Minutes)

To verify the mock decision bypass and file system settings:

### Scan for Hardcoded FS Paths
Run this check to scan the dashboard repository for absolute local user paths (such as `C:\Users\spal4\...` or similar user directories):
```powershell
# In CWD: c:\Users\black\OneDrive\Desktop\Pravah\BHIV
Select-String -Path "pipeline-integration-py-main\dashboard.py" -Pattern "C:\\Users\\"
```
**Assert Output:**
* The search will output the lines referencing local paths:
  ```text
  pipeline-integration-py-main\dashboard.py:297:    LOG_FILE = r"C:\Users\spal4\Desktop\SHIVAM\BHIV\multi-agent-control-plane-main\logs\dev\rl_execution_feedback.jsonl"
  ```
* Identifies the specific path drift that must be parameterized before full staging environment deployment.

### Verify Mock Decision Bypass
Review [agent_runtime.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/agent_runtime.py) decides step.
```powershell
# In CWD: c:\Users\black\OneDrive\Desktop\Pravah\BHIV\multi-agent-control-plane-main
Select-String -Path "agent_runtime.py" -Pattern "process-runtime"
```
**Assert Output:**
* Locates the decidings endpoint:
  ```text
  agent_runtime.py:638:                "http://localhost:5000/process-runtime",
  ```
* Identifies that the runtime currently queries Port `5000` (the mock integration dashboard) and must be updated to point to Port `8008` (the persistent RL Brain) for production readiness.
