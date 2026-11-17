# PHASE 2.5.1 FORENSIC AUDIT: SILENT EXCEPTION & BEST-EFFORT BOUNDARY CLOSURE

**Scope**: PRAVAH ONLY  
**Authoritative Execution Root**: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Audit Target**: Rigorous Verification of All Silent Exception (`except Exception: pass`) Handlers, Fallbacks, and Alleged Best-Effort Paths  
**Audit Date**: 2026-09-07  
**Status**: COMPLETE  
**Final Classification**: **B — ONE OR MORE SILENT EXCEPTION PATHS ARE DEFECTS**

---

## 1. EXECUTIVE SUMMARY & OBJECTIVE

In the Phase 2.5 audit (`audit/PHASE2_5_ERROR_BOUNDARY_FORENSIC_AUDIT.md`), several `except Exception: pass` and silent fallback paths were cataloged as "Best-Effort Telemetry" or "Best-Effort Local Persistence" while concluding with `A — NO ERROR-BOUNDARY GAPS FOUND`.

Under **TASK PHASE 2.5.1**, a forensic review was conducted to evaluate whether these silent exception handlers are legitimately permitted by the Pravah architecture and Phase 2 error-boundary requirements (`REQ-2.8` / `P2.D`), or whether they constitute observability and fail-closed security defects.

### Forensic Determination:
The Phase 2.5 "A" classification is **NOT VALID**. Multiple silent exception handlers across security boundaries, execution contracts, audit trails, and observability telemetry are **CONFIRMED DEFECTS**:
1. **Critical Fail-Open Security Gap in `execution_contract.py`**: The semantic guard engine (`semantic_guard_engine`) is wrapped in `except Exception: validate_semantic_transition = None`. If the guard module fails to import, contract transitions bypass all FSM and governance checks entirely!
2. **Fail-Open Anti-Replay Breaches in `trace_consumption.py` and `nonce_store.py`**: Disk persistence read failures are caught via `except Exception: pass`. If the JSON file is corrupted or unreadable upon process restart, all consumed traces and nonces are silently discarded, exposing the system to replay attacks.
3. **Audit Trail Loss in `agent_api.py` (`shakti_events`)**: `append_decision_history` is wrapped in `except Exception: pass`. If appending fails, the event is silently lost while the API returns HTTP 200 asserting successful pipeline publication.
4. **Outage Masking in `main.py` (`_build_live_dashboard_payload`)**: If system metric extraction (`psutil`) fails, `system_cpu` defaults to `0`, which evaluates `< 80`, causing the dashboard to falsely report `status: "HEALTHY"`.

---

## 2. AUDIT OF TARGET AREAS

### 2.1 `backend/control_plane/backend/app/main.py`

#### A. `_calculate_aggregate_metrics()` (Lines 530–620)
```python
# 1. Real System Metrics
try:
    system_cpu = int(psutil.cpu_percent())
    system_memory = int(psutil.virtual_memory().percent)
except Exception:
    system_cpu = 20
    system_memory = 40

# 2. Real Git stats (workspace repository)
git_commits = 0
git_contributors = 1
git_files = 365
try:
    commits_res = subprocess.run(["git", "rev-list", "--count", "HEAD"], capture_output=True, text=True, check=True)
    git_commits = int(commits_res.stdout.strip())
except Exception:
    pass
...
# 3. Real Test Coverage
real_coverage = 78
try:
    import coverage
    cov = coverage.Coverage()
    cov.load()
    real_coverage = int(cov.report(file=open(os.devnull, "w")))
except Exception:
    pass
```

| Forensic Question | Evaluation & Technical Proof |
| :--- | :--- |
| **What exact operation can fail?** | 1. `psutil` system metrics calls if restricted by container cgroups/permissions.<br>2. `git rev-list`, `git log`, `git ls-files` subprocesses if `git` is absent or the environment is not a Git repo (e.g. production container images where `.git` is purged).<br>3. `coverage.report()` if coverage file is absent or coverage is uninstalled.<br>4. File I/O reading `decision_history.jsonl` or `policy_enforcement.jsonl`. |
| **Can failure produce misleading data?** | **YES**. If `coverage` fails, it reports a hardcoded fake `avg_test_coverage: 78`. If `git` fails, it reports fake `total_files: 365`. If `psutil` fails, it reports fake `system_cpu: 20` and `system_memory: 40`. |
| **Is the affected value operationally/security relevant?** | **OPERATIONALLY RELEVANT**. This function feeds `GET /orchestration/metrics` and the Prometheus scrape endpoint `GET /metrics` (`pravah_decision_brain_total_commits`, etc.). Monitoring systems scraping Prometheus will ingest fabricated metrics rather than null/unavailable indicators. |
| **Does failure affect only presentation/telemetry?** | YES (read-only; no state mutation). |
| **Is the exception observable anywhere?** | **NO**. All exceptions are silently swallowed (`pass`) with zero log statements. |
| **Can an operator distinguish "real zero" from "calculation failed"?** | **NO**. Fabricated non-zero numbers (78%, 365 files, 20% CPU) actively simulate healthy metrics instead of reporting failure. |
| **Can the fallback hide a production outage?** | YES, for Prometheus scraping of node resource health. |
| **Is silent suppression explicitly authorized by contract?** | NO. |

#### B. `_build_live_dashboard_payload()` (Lines 644–675)
```python
# Extract ML Intelligence Features
try:
    extractor = MLFeatureExtractor(env=env)
    ml_intelligence = extractor.extract_features().model_dump()
except Exception:
    ml_intelligence = {}
    
# Get System Health
try:
    system_cpu = int(psutil.cpu_percent())
    system_memory = int(psutil.virtual_memory().percent)
except Exception:
    system_cpu = 0
    system_memory = 0
    
system_health = {
    "cpu_utilization_pct": system_cpu,
    "memory_utilization_pct": system_memory,
    "status": "HEALTHY" if system_cpu < 80 else "DEGRADED"
}
```

| Forensic Question | Evaluation & Technical Proof |
| :--- | :--- |
| **What exact operation can fail?** | 1. `MLFeatureExtractor.extract_features()` if model files, telemetry db, or numpy/scipy dependencies fail.<br>2. `psutil.cpu_percent()` / `psutil.virtual_memory().percent()` on OS/container metric failure. |
| **Can failure produce misleading data?** | **YES**. If `psutil` crashes, `system_cpu` is set to `0`. Because `0 < 80`, `"status"` is evaluated as `"HEALTHY"`! |
| **Can the fallback hide a production outage?** | **YES**. A complete failure of host observability causes the dashboard to display `status: "HEALTHY"` with 0% CPU, masking monitoring failure. |
| **Is the exception observable anywhere?** | **NO**. Zero logging; zero error telemetry. |
| **Can an operator distinguish "real zero" from "calculation failed"?** | **NO**. A failed monitor is indistinguishable from an idle system. |

---

### 2.2 `backend/security/trace_consumption.py`

Lines 20–42:
```python
def _load_store(self):
    """Load consumed traces from disk."""
    if os.path.exists(self.store_file):
        try:
            with open(self.store_file, 'r') as f:
                data = json.load(f)
                self.consumed_traces = set(data.get('traces', []))
                self.timestamps = data.get('timestamps', {})
                self._cleanup_expired()
        except Exception:
            pass

def _save_store(self):
    """Save consumed traces to disk."""
    os.makedirs(os.path.dirname(self.store_file), exist_ok=True)
    try:
        with open(self.store_file, 'w') as f:
            json.dump({
                'traces': list(self.consumed_traces),
                'timestamps': self.timestamps
            }, f)
    except Exception:
        pass
```

| Forensic Question | Evaluation & Technical Proof |
| :--- | :--- |
| **What persistent state is being read/written?** | The canonical registry of single-use consumed execution trace IDs (`security/trace_consumption.json`). |
| **What happens if disk persistence fails?** | In `_save_store()`, the exception is swallowed. `consume(trace_id)` returns `True`, claiming the trace was durably consumed, but disk state was never updated. |
| **Does in-memory state remain safe?** | Only until process termination. In-memory set `self.consumed_traces` is transient. |
| **Can replay protection become weaker?** | **YES**. If persistence fails or if `_load_store()` encounters a corrupted file/I-O error upon startup, `except Exception: pass` silently leaves `self.consumed_traces` empty! |
| **Can a process restart cause a consumed trace to become reusable?** | **YES**. All traces consumed prior to restart are forgotten if loading fails or if saving failed, allowing identical requests to be re-executed. |
| **Is the fallback security-preserving?** | **NO**. It is **FAIL-OPEN**. A failure to read security state results in granting execution rights rather than aborting or alerting. |
| **Is failure observable?** | **NO**. Zero logging; `logger` is not even imported in `trace_consumption.py`. |
| **Does the architecture explicitly permit best-effort persistence here?** | **NO**. Trace single-use consumption is an anti-replay security invariant. |

---

### 2.3 `backend/security/nonce_store.py`

Lines 18–37:
```python
def _load_store(self):
    """Load nonces from file."""
    if os.path.exists(self.store_file):
        try:
            with open(self.store_file, 'r') as f:
                data = json.load(f)
                self.nonces = set(data.get('nonces', []))
                self.nonce_timestamps = data.get('timestamps', {})
                self._cleanup_expired()
        except Exception:
            pass

def _save_store(self):
    """Save nonces to file."""
    os.makedirs(os.path.dirname(self.store_file), exist_ok=True)
    with open(self.store_file, 'w') as f:
        json.dump({
            'nonces': list(self.nonces),
            'timestamps': self.nonce_timestamps
        }, f)
```

| Forensic Question | Evaluation & Technical Proof |
| :--- | :--- |
| **What happens if the nonce store cannot be read?** | If `security/nonce_store.json` has invalid JSON, bad permissions, or read errors, `except Exception: pass` silently leaves `self.nonces` empty. |
| **What happens if persistence fails?** | In `_save_store()`, no `try/except` exists, meaning write errors crash the request, but read errors in `_load_store()` are completely swallowed. |
| **Can nonce reuse occur after restart?** | **YES**. If `_load_store()` fails, previously used nonces are wiped from memory, permitting replay of messages within the time-skew window. |
| **Is the behavior fail-closed?** | **NO**. It is **FAIL-OPEN**. Nonce store corruption leads to permitting reused nonces. |
| **Is the failure observable?** | **NO**. No logging exists in `nonce_store.py`. |
| **Is local persistence security-critical or merely optimization?** | **SECURITY-CRITICAL**. The module docstring explicitly declares: `"""SSPL Phase III - Nonce Store for Replay Attack Prevention"""`. |

---

### 2.4 `backend/control_plane/api/agent_api.py`

#### A. `runtime_decision` Observer POST (Lines 209–224)
```python
try:
    requests.post(
        "http://localhost:8600/api/observer/event",
        json={...},
        timeout=1.0
    )
except Exception:
    pass # Observer down should not affect the control plane
```
- **Analysis**: The observer on port 8600 is an auxiliary visual observer. The runtime decision has already completed. Failing the control plane if the observer UI is down would invert dependency polarity.
- **Classification**: **CONDITIONAL / ACCEPTABLE NON-CRITICAL TELEMETRY**, *BUT* silently swallowing without `logger.warning` violates observability requirements.

#### B. `shakti_events` Decision History Append (Lines 364–377)
```python
try:
    control_plane.append_decision_history({
        "app_name": "shakti-gc",
        "executed_action": payload["action"],
        "reason": f"Ecosystem event: {payload['event_type']}",
        "execution_success": True,
        "event": {
            "trace_id": payload["trace_id"],
            "correlation_id": payload["correlation_id"]
        }
    })
except Exception:
    pass

return jsonify(response_payload), 200
```
- **Analysis**: The endpoint accepts an ecosystem event, returns HTTP 200 with `"status": "CONNECTED", "detail": "Event published to Pravah pipeline"`, but if disk append to `decision_history.jsonl` fails, it swallows the exception.
- **Impact**: **AUDIT TRAIL LOSS**. The client is told the event is published, but no trace or record exists in the decision log.
- **Classification**: **DEFECT**. Must either fail or emit structured error logging.

#### C. `load_evidence_bundles` & `save_evidence_bundle` (Lines 320–338)
```python
def load_evidence_bundles():
    ...
    try:
        with open(EVIDENCE_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_evidence_bundle(evidence_ref: str, bundle: dict):
    ...
    try:
        with open(EVIDENCE_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)
        return True
    except Exception:
        return False
```
- **Analysis**: If `evidence_bundle.json` is corrupted, it silently returns `{}`. If saving fails, it returns `False` without logging.
- **Classification**: **DEFECT (Observability)**.

---

### 2.5 `backend/contracts/execution_contract.py` FALLBACKS

#### A. `transition_contract_state()` Semantic Guard Import Fallback (Lines 259–266)
```python
# Phase 4: Semantic guard engine - comprehensive semantic + governance validation
try:
    # Import here to avoid circular import at module import time
    from control_plane.security.semantic_guard_engine import (
        validate_state_transition as validate_semantic_transition,
    )
except Exception:
    validate_semantic_transition = None

if validate_semantic_transition is not None:
    try:
        validate_semantic_transition(...)
    except ValueError as e:
        raise ValueError(f"[{contract.execution_id}] Semantic guard violation: {str(e)}") from e

# IF validate_semantic_transition IS None:
history = tuple(contract.execution_state_history)
history = history + (new_state,)
updated_contract = contract.model_copy(...)
return updated_contract
```

#### B. Direct Answers to Audit Questions:
1. **Can the system execute an action when the semantic guard functionality is unavailable?**  
   **YES**. If `semantic_guard_engine` raises an exception during import (e.g. `ImportError`, syntax error, missing dependency, corrupt installation), `validate_semantic_transition` is set to `None`. The code then skips all transition checks, executes the transition, updates `execution_state_history`, and returns the updated contract!
2. **Is that an intentional dev-only behavior, production behavior, or a fail-open security gap?**  
   **CRITICAL FAIL-OPEN SECURITY GAP**. There is no check for `ENVIRONMENT == "dev"`. In production, any invalid state transition (such as skipping `APPROVED` or skipping `EXECUTED`, or transitioning backwards from `COMPLETED`) is permitted if the guard module fails to load.
3. **Can policy snapshot fallback disable security/governance checks?**  
   In `build_execution_contract()` (lines 145–153):
   ```python
   if policy_snapshot is not None and not isinstance(policy_snapshot, PolicySnapshot):
       try:
           policy_snapshot = PolicySnapshot(...)
       except Exception:
           policy_snapshot = None
   ```
   If a malformed policy snapshot dict is passed, instead of raising a validation error, it silently coerces `policy_snapshot = None` and computes the execution hash without policy snapshot binding!

---

## 3. REQUIREMENT MAPPING MATRIX

Every investigated silent handler is evaluated below against the Phase 2 requirements (Fail-Closed, Observability, Determinism, Auditability, Security):

| Handler / Code Location | Intended Purpose | Failure Consequence | Classification |
| :--- | :--- | :--- | :---: |
| `execution_contract.py:259-266` | Semantic guard dynamic import | Disables FSM & governance validation; permits illegal state transitions | **DEFECT (CRITICAL FAIL-OPEN)** |
| `execution_contract.py:152` | Policy snapshot coercion | Drops policy binding from execution hash on malformed snapshot | **DEFECT (FAIL-OPEN COERCION)** |
| `trace_consumption.py:29` | Load consumed traces | Drops all anti-replay protection on startup read failure | **DEFECT (FAIL-OPEN REPLAY GAP)** |
| `trace_consumption.py:41` | Save consumed traces | Silently drops persistence while caller claims successful consumption | **DEFECT (PERSISTENCE LEAK)** |
| `nonce_store.py:27` | Load nonces from disk | Drops historical nonces; permits nonce reuse after restart | **DEFECT (FAIL-OPEN REPLAY GAP)** |
| `main.py:663` (`_build_live_dashboard_payload`) | `psutil` system metrics | CPU defaults to 0, evaluates < 80, falsely displays `status: "HEALTHY"` | **DEFECT (OUTAGE MASKING)** |
| `main.py:582` (`_calculate_aggregate_metrics`) | Coverage report | Injects hardcoded fake 78% coverage into Prometheus metrics | **DEFECT (FABRICATED METRICS)** |
| `agent_api.py:375` (`shakti_events`) | Append decision history | Event published response returned without audit record on disk | **DEFECT (AUDIT TRAIL LOSS)** |
| `agent_api.py:326, 336` | Evidence bundle I/O | Returns empty dict or False without any log statement | **DEFECT (OBSERVABILITY GAP)** |
| `agent_api.py:222` (`runtime_decision`) | Auxiliary observer event POST | Drops observer packet; core decision unblocked | **CONDITIONAL (NEEDS LOGGING)** |

---

## 4. TEST AUTHENTICITY EVALUATION

Inspection of the test suite (`backend/tests/`) reveals:
1. **Semantic Guard Import Failure**: **ZERO tests**. No test exists that simulates `ImportError` on `semantic_guard_engine` to verify whether `transition_contract_state` fails closed. The code path was untested and allowed to fail open.
2. **Corrupted `trace_consumption.json`**: **ZERO tests**. In `backend/tests/test_replay_sovereignty.py`, tests only exercise in-memory single-use trace protection during a single process run. No test verifies behavior when `trace_consumption.json` contains malformed JSON or unreadable permissions on restart.
3. **Corrupted `nonce_store.json`**: **ZERO tests**. No test tests restart recovery or corrupted nonce store handling.
4. **Misleading Telemetry Fallbacks**: **ZERO tests**. In `test_phase2_ingestion_api.py`, tests assert aggregate metrics when files exist, but zero tests assert that metric collection failures surface error indicators rather than fabricated defaults (e.g. 78% coverage).

---

## 5. DISTINCTION: LEGITIMATE FALLBACK VS. SILENT DEFECT

A legitimate best-effort fallback is permitted **ONLY IF** it satisfies all six architectural criteria:
1. **Architecturally Authorized**: Documented as non-fatal in the system design.
2. **Security-Preserving**: Cannot permit unauthorized execution, bypass validation, or disable replay protection.
3. **Observable**: Emits structured warning logs (`logger.warning`) containing error details and target identifiers.
4. **Deterministic**: Produces unambiguous fallback values that cannot be mistaken for valid measurements (e.g., `None` or `-1` rather than fake `78` or fake `"HEALTHY"`).
5. **Auditable**: Never drops audit trail entries while returning success to callers.
6. **Tested**: Verified with negative/failure injection tests.

The handlers in `execution_contract.py`, `trace_consumption.py`, `nonce_store.py`, `main.py`, and `agent_api.py` violate these criteria.

---

## 6. VANA & REPOSITORY INTEGRITY VERIFICATION

Executed from authoritative root `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`:

### 6.1 Test Collection Count
```
pytest --collect-only -q
312 tests collected in 0.89s
```

### 6.2 Full Test Suite Execution
```
pytest -q
312 passed, 370 warnings in 21.46s
```

### 6.3 VANA Directory Immutability
```
git diff -- VANA/
(empty - 0 modifications)
```

### 6.4 Git Working Tree Status
```
git status --short audit/
?? audit/PHASE2_5_1_SILENT_EXCEPTION_BOUNDARY_FORENSICS.md
```

---

## 7. REMEDIATION ORDER (FOR SUBSEQUENT IMPLEMENTATION PHASE)

*Note: Per instructions, remediation is NOT implemented in this task.*

The exact minimal remediation plan to close these defects:

1. **Remediation Step 1 (`backend/contracts/execution_contract.py`)**:
   - Change `except Exception: validate_semantic_transition = None` in `transition_contract_state` to **fail closed**:
     ```python
     try:
         from control_plane.security.semantic_guard_engine import validate_state_transition
     except Exception as err:
         raise RuntimeError(f"CRITICAL: Semantic guard engine unavailable: {err}") from err
     ```
   - In `build_execution_contract()`, reject malformed `policy_snapshot` with `raise ValueError` instead of coercing to `None`.
2. **Remediation Step 2 (`backend/security/trace_consumption.py`)**:
   - In `_load_store()`, import `logging`. If `self.store_file` is corrupted, log `logger.critical(...)` and raise `RuntimeError("CRITICAL: Corrupt trace consumption registry")` instead of silently ignoring it.
   - In `_save_store()`, log `logger.critical(...)` and raise or fail closed when disk persistence fails so `consume()` cannot return false success.
3. **Remediation Step 3 (`backend/security/nonce_store.py`)**:
   - In `_load_store()`, import `logging`. If reading fails, log error and fail closed.
4. **Remediation Step 4 (`backend/control_plane/backend/app/main.py`)**:
   - In `_build_live_dashboard_payload()`, if `psutil` fails, set `system_health["status"] = "UNKNOWN"` (or `"DEGRADED"`) and log `logger.warning(...)` instead of setting CPU to 0 and claiming `"HEALTHY"`.
   - In `_calculate_aggregate_metrics()`, log warnings on git/psutil/coverage failures and return `None` or `0` with explicit telemetry status flags instead of hardcoded numbers like `78` or `365`.
5. **Remediation Step 5 (`backend/control_plane/api/agent_api.py`)**:
   - In `shakti_events()`, if `append_decision_history` fails, log `logger.error(...)` and return HTTP 500 or degraded status instead of silent `pass`.
   - In `runtime_decision()`, add `logger.warning("Observer event forward failed: %s", exc)` inside the observer try/except block.

---

## 8. FINAL CLASSIFICATION

# **B — ONE OR MORE SILENT EXCEPTION PATHS ARE DEFECTS**

The forensic audit conclusively proves that while monitored-link ingestion (`_generate_link_metadata`, `/ingest-link`, `/remove-link`) has been hardened, several critical silent exception handlers in execution contracts, anti-replay stores, audit logging, and telemetry extraction remain fail-open or unobservable defects.
