# PHASE 2.5.5 — REMAINING SILENT EXCEPTION BOUNDARY FORENSIC AUDIT

**Scope**: PRAVAH ONLY  
**Authoritative Execution Root**: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Audit Target**: Remaining silent exception handlers in `agent_api.py` and `main.py`  
**Date**: September 7, 2026  
**Status**: COMPLETE  
**Final Classification**: **B — Confirmed Remediation Required**

---

## 1. EXECUTIVE SUMMARY

Following the remediation of the primary Control Plane error boundaries in Phase 2.5.2 and the removal of synthetic external-link telemetry in Phase 2.5.4, this forensic audit evaluates the two remaining unclosed silent exception paths in the Pravah codebase:

1. **`backend/control_plane/api/agent_api.py` (`/metrics` Prometheus handler, lines 458–480)**:
   Catches `Exception` with `pass` while parsing `decision_history.jsonl`.
   **Finding**: **Defect Confirmed (B)**. When the log file cannot be opened or parsed due to I/O error or malformed JSON, the exception is swallowed without logging a warning. The endpoint silently reports `pravah_stability_score 100`, `pravah_failures_total 0`, and `pravah_recoveries_total 0`. This produces **falsely perfect telemetry** and masks log file degradation. Remediation is required.

2. **`backend/control_plane/backend/app/main.py` (`execute_action()` error transition unwind, lines 1054 & 1104)**:
   Catches `Exception` with `pass` when attempting a secondary transition of `current_contract` to `"FAILED"`.
   **Finding**: **Architecturally Fail-Closed (A)**. The primary execution failure is NEVER masked; the function unconditionally returns `False, {"status": "failed", "rejection_code": "COMPLETION_FAILED" | "EXECUTION_EXCEPTION"}`. It does not grant execution rights, does not create false success, and caller boundaries treat the action as blocked. However, logging the secondary failure (`logger.warning`) would improve audit observability.

Full regression tests from the authoritative root confirm **353 passed tests** (0 failed). `git diff -- VANA/` is completely empty.

---

## 2. DEEP FORENSIC AUDIT OF PATH 1: `backend/control_plane/api/agent_api.py` (`/metrics`)

### 2.1 Exact Source Location & Caller Chain
- **File**: `backend/control_plane/api/agent_api.py`
- **Function**: `prometheus_metrics()` (lines 458–505)
- **Target Block** (lines 465–480):
  ```python
  history_file = os.path.join(root_dir, "logs", "control_plane", "decision_history.jsonl")
  if os.path.exists(history_file):
      try:
          with open(history_file, "r", encoding="utf-8") as f:
              for line in f:
                  if not line.strip():
                      continue
                  record = json.loads(line)
                  action = record.get("executed_action") or record.get("action")
                  if action in ["scale_up", "heal", "restart"]:
                      recoveries += 1
                  elif record.get("state") == "degraded" or record.get("event_type") == "crash":
                      failures += 1
      except Exception:
          pass
          
  # Stability = 100 - (failures * 2) + (recoveries * 3)
  stability_score = 100 - (failures * 2) + (recoveries * 3)
  stability_score = max(0, min(100, stability_score))
  ```
- **Caller Chain**:
  External Prometheus scraper / monitoring probe $\to$ HTTP `GET /metrics` on port 7000 $\to$ Flask route $\to$ `prometheus_metrics()`.

### 2.2 Potential Exceptions
- `OSError` / `PermissionError`: File permission locks or I/O failure reading `decision_history.jsonl`.
- `json.JSONDecodeError`: Torn write, partial line, or syntax corruption in `decision_history.jsonl`.
- `UnicodeDecodeError`: Invalid UTF-8 bytes in the log file.
- `AttributeError`: If a parsed JSON record is not a dictionary and `.get()` fails.

### 2.3 Prior State Mutation
- **None**. `prometheus_metrics()` is a strictly read-only scrape endpoint. No in-memory state, contract, or database is modified before or during the block.

### 2.4 Seven-Factor Risk Assessment
| Risk Factor | Assessment | Forensic Detail |
|---|:---:|---|
| **Hide a security failure?** | **NO** | Not an authentication, authorization, or cryptographic verification path. |
| **Hide an authorization failure?** | **NO** | Public `/metrics` endpoint with `@limiter.exempt`. |
| **Hide persistence failure?** | **NO** | Does not write or commit state; only reads existing logs. |
| **Create false success?** | **YES (Telemetry)** | If `decision_history.jsonl` fails on line 1, `failures=0` and `recoveries=0`. The equation computes `stability_score = 100 - 0 + 0 = 100`. The scraper receives `pravah_stability_score 100` even if the system crashed repeatedly before the read failed. |
| **Strand execution state?** | **NO** | No execution lifecycle or state machine is managed here. |
| **Create incorrect telemetry?** | **YES** | Silently halts log aggregation mid-file or at start, emitting undercounted failure/recovery counts and a fabricated 100% stability score. |
| **Affect observability?** | **YES** | Swallows errors with `pass` without logging a `logger.warning` or `logger.error`. Operators have no indication that metrics calculation failed. |

### 2.5 Best-Effort vs. Fail-Open Classification
- **Classification**: **Observable Telemetry Defect (Silent Swallowing)**.
- While intended as a best-effort scrape handler to avoid crashing the Prometheus endpoint, silently swallowing read errors and defaulting to `pravah_stability_score 100` directly violates Phase 2 error-boundary principles established in Phase 2.5.1 and 2.5.3.

### 2.6 Test Authenticity & Failure Behavior Proof
- **Existing Coverage**: **ZERO**.
  Inspection of `backend/tests/` reveals zero tests requesting `GET /metrics` against the Flask `agent_api.py` app (`flask_client`). Existing prometheus tests in `test_phase2_error_boundary_security.py` exercise the FastAPI `prometheus_metrics` endpoint in `main.py`, NOT the Flask endpoint in `agent_api.py`.
- **Failure Behavior Proven?**: **NO**. The behavior under file corruption or read error is completely untested.

### 2.7 Remediation Requirement
- **Remediation Required**: **YES**.
  1. Catch exceptions, log a descriptive warning (`logger.warning("Failed to parse decision history for metrics: %s", exc)`).
  2. Mark stability as unavailable or degraded, or omit unverified gauges rather than calculating a false `100` score.

---

## 3. DEEP FORENSIC AUDIT OF PATH 2: `backend/control_plane/backend/app/main.py` (`execute_action()`)

### 3.1 Exact Source Location & Caller Chain
- **File**: `backend/control_plane/backend/app/main.py`
- **Function**: `execute_action()` (lines 779–1116)
- **Target Block A** (lines 1043–1064):
  ```python
  except Exception as comp_err:
      # G7: Failure during EXECUTED -> COMPLETED must transition to FAILED
      from security.lineage_verifier import LineagePersistenceCorruptionError
      if isinstance(comp_err, LineagePersistenceCorruptionError):
          return False, { ... }
      try:
          current_contract = transition_contract_state(
              contract_executed,
              "FAILED",
              source="runtime",
              details={
                  "rejection_code": "COMPLETION_FAILED",
                  "reason": f"Completion transition failed: {str(comp_err)}",
                  "trace_id": canonical_trace_id,
              },
          )
      except Exception:
          pass
      return False, {
          "status": "failed",
          "action": action,
          "service_id": service_id,
          "execution_id": current_contract.execution_id,
          "trace_id": canonical_trace_id,
          "reason": f"Completion transition failed: {str(comp_err)}",
          "rejection_code": "COMPLETION_FAILED",
      }
  ```
- **Target Block B** (lines 1081–1115):
  ```python
  if current_contract and current_contract.execution_state not in ("COMPLETED", "FAILED"):
      try:
          target_rejection = "COMPLETION_FAILED" if current_contract.execution_state == "EXECUTED" else "EXECUTION_EXCEPTION"
          transition_contract_state(
              current_contract,
              "FAILED",
              source="runtime",
              details={
                  "rejection_code": target_rejection,
                  "reason": str(e),
                  "trace_id": canonical_trace_id,
              },
          )
      except LineagePersistenceCorruptionError as p_err:
          return False, { ... }
      except Exception:
          pass

  return False, {
      "status": "failed",
      "action": action,
      "service_id": service_id,
      "execution_id": getattr(current_contract, "execution_id", execution_id),
      "trace_id": locals().get("canonical_trace_id", trace_id),
      "reason": str(e),
      "rejection_code": "EXECUTION_EXCEPTION",
  }
  ```
- **Caller Chain**:
  `POST /control-plane/runtime-ingest` (line 1646) $\to$ `execute_action()`.

### 3.2 Potential Exceptions
- During the secondary attempt to call `transition_contract_state(..., "FAILED")`:
  - `ValueError`: Contract terminal state lock or invalid transition rule.
  - `LineagePersistenceCorruptionError`: Explicitly caught and handled prior to `except Exception`.
  - `RuntimeError`: Semantic guard engine failure or unmapped transition error.

### 3.3 Prior State Mutation
- In Block A: Contract has already transitioned to `EXECUTED` in lineage logs. The executor has already executed the action.
- In Block B: Contract was in `APPROVED` or `EXECUTED`.

### 3.4 Seven-Factor Risk Assessment
| Risk Factor | Assessment | Forensic Detail |
|---|:---:|---|
| **Hide a security failure?** | **NO** | Does not bypass security; unconditional `return False` follows. |
| **Hide an authorization failure?** | **NO** | Authorization was evaluated prior to reaching this stage. |
| **Hide persistence failure?** | **NO** | If persistence corrupted, `LineagePersistenceCorruptionError` returns distinct error. |
| **Create false success?** | **NO** | Unconditionally returns `allowed=False` with `"status": "failed"`. The caller (`runtime-ingest`) explicitly checks `if not success:` and logs `verification: {"verified": False}` and `status: "blocked"`. |
| **Strand execution state?** | **PARTIAL IN-MEMORY ONLY** | If `transition_contract_state(..., "FAILED")` fails, the contract object in memory remains `EXECUTED`. However, the caller receives `allowed=False`, the response reports `"status": "failed"`, and no execution rights are granted. |
| **Create incorrect telemetry?** | **NO** | Caller logs `"status": "blocked"` in execution logs. |
| **Affect observability?** | **MINOR** | The secondary failure to record `"FAILED"` in lineage is not logged via `logger.warning`. |

### 3.5 Best-Effort vs. Fail-Open Classification
- **Classification**: **Fail-Closed Cleanup with Missing Observability Logging**.
- The path is strictly fail-closed: it always returns `False` and communicates failure to the caller. Swallowing the secondary cleanup error with `pass` prevents an unwinding error from crashing the API server uncaught, but it should log a warning.

### 3.6 Test Authenticity & Failure Behavior Proof
- **Existing Coverage**: **PROVEN**.
  `backend/tests/adversarial_test_suite/test_execution_boundary_lineage.py` line 713 (`test_failure_during_completion_transitions_to_failed`):
  Simulates a completion failure during `transition_contract_state(..., "COMPLETED")` and proves that:
  - `allowed is False`
  - `response["status"] == "failed"`
  - `response["rejection_code"] == "COMPLETION_FAILED"`
  - `replay["final_state"] == "FAILED"`
  - `replay["execution_state_history"] == ["CREATED", "APPROVED", "EXECUTED", "FAILED"]`

### 3.7 Remediation Requirement
- **Remediation Required**: **NON-CRITICAL / HYGIENE ONLY**.
  Because the path is already strictly fail-closed (`return False, {"status": "failed", ...}`), it does not constitute a security vulnerability. Adding `logger.warning` is recommended for operational observability.

---

## 4. CODEBASE SCAN: REMAINING SILENT EXCEPTION PATTERNS

A comprehensive scan of `backend/` for `except Exception:` and `except Exception as ...:` was conducted.

| File & Line | Pattern | Classification | Architectural Analysis & Finding |
|---|---|:---:|---|
| `control_plane/api/agent_api.py:478` | `except Exception: pass` | **B (Remediation Required)** | **Defect**: Swallows log read errors, emits false `pravah_stability_score 100`. |
| `control_plane/backend/app/main.py:1054` | `except Exception: pass` | **A (Fail-Closed / Safe)** | Cleanup unwind in `execute_action()`: unconditionally returns `False, {"status": "failed"}`. |
| `control_plane/backend/app/main.py:1104` | `except Exception: pass` | **A (Fail-Closed / Safe)** | Cleanup unwind in `execute_action()`: unconditionally returns `False, {"status": "failed"}`. |
| `control_plane/backend/app/main.py:678` | `except Exception: ml_intelligence = {}` | **A (Fail-Closed / Safe)** | Best-effort ML feature extraction fallback. Audited in Phase 2.5.1. |
| `control_plane/backend/app/main.py:1517` | `except Exception: runtime_attestation_valid = None` | **A (Fail-Closed / Safe)** | Safe replay verification fallback for optional attestation. |
| `security/trace_consumption.py:62` | `except Exception: pass` | **A (Fail-Closed / Safe)** | Temp file removal during store persistence error; immediately followed by `raise RuntimeError`. Audited in Phase 2.5.2. |
| `security/trace_consumption.py:105` | `except Exception: rollback; raise` | **A (Fail-Closed / Safe)** | Rolls back in-memory trace state and re-raises unhandled. |
| `security/nonce_store.py:60` | `except Exception: pass` | **A (Fail-Closed / Safe)** | Temp file removal; immediately followed by `raise RuntimeError`. |
| `security/nonce_store.py:97` | `except Exception: rollback; raise` | **A (Fail-Closed / Safe)** | Rolls back in-memory nonce state and re-raises unhandled. |
| `security/signing.py:167` | `except Exception: return False` | **A (Fail-Closed / Safe)** | Timestamp parsing failure returns `False` (signature check rejected). |
| `security/signing.py:250` | `except Exception: return False` | **A (Fail-Closed / Safe)** | Nonce timestamp parsing failure returns `False` (signature check rejected). |
| `core_hooks/middleware.py:40` | `except Exception: raise TraceVerificationError` | **A (Fail-Closed / Safe)** | Timestamp parsing failure raises explicit security exception. |
| `control_plane/executor/executor.py:352` | `except Exception: return False` | **A (Fail-Closed / Safe)** | Docker inspect failure returns `False` (action verification fails). |
| `control_plane/multi_app_control_plane.py:40` | `except Exception: continue` | **A (Fail-Closed / Safe)** | Corrupt app spec file skipped during registry discovery. |
| `control_plane/multi_app_control_plane.py:106` | `except Exception: pass` | **A (Fail-Closed / Safe)** | Asynchronous Sarathi signal emission after successful decision append. Audited in Phase 2.5.2. |
| `control_plane/core/action_governance.py:181` | `except Exception: pass` | **A (Fail-Closed / Safe)** | Best-effort local governance state load from JSON. Audited in Phase 2.5.1. |
| `control_plane/core/action_governance.py:202` | `except Exception: pass` | **A (Fail-Closed / Safe)** | Best-effort local governance state snapshot save. Audited in Phase 2.5.1. |
| `control_plane/core/action_governance.py:616` | `except Exception: pass` | **A (Fail-Closed / Safe)** | Auxiliary append-only log record during governance transition. Audited in Phase 2.5.1. |

---

## 5. TEST AUTHENTICITY & REGRESSION VERIFICATION

Authoritative Code Root: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`

### 5.1 Pytest Collection
```powershell
pytest --collect-only -q
```
**Result**: **353 tests collected in 1.09s** (Exit Code: 0)

### 5.2 Full Pytest Suite Execution
```powershell
pytest -q
```
**Result**:
- **Collected**: 353
- **Passed**: 353
- **Failed**: 0
- **Errors**: 0
- **Skipped**: 0
- **Xfailed**: 0
- **Warnings**: 396
- **Execution Time**: 21.35s
- **Exit Code**: 0

### 5.3 Specific Production Path Test Analysis
- **`main.py:execute_action()` G7 Path**: Tested by `backend/tests/adversarial_test_suite/test_execution_boundary_lineage.py::test_failure_during_completion_transitions_to_failed` (**PASSED**). Authentically verifies transition to `FAILED` with `COMPLETION_FAILED`.
- **`agent_api.py:/metrics` Path**: **UNTESTED**. No existing test exercises this endpoint or verifies its failure behavior under log read errors.

---

## 6. VANA INTEGRITY & REPOSITORY HYGIENE

### 6.1 VANA Diff
```powershell
git diff -- VANA/
```
**Result**: **Completely empty (0 lines modified, 0 files modified)**.

### 6.2 Repository Hygiene
- Only `audit/PHASE2_5_5_REMAINING_SILENT_EXCEPTION_FORENSICS.md` was created.
- Zero scratch, helper, temporary, or debug files were created.
- Production code and existing tests were not modified.

---

## 7. FINAL CLASSIFICATION & REMEDIATION PLAN

### Final Classification:
# **B — Confirmed Remediation Required**

### Rationale:
1. `backend/control_plane/api/agent_api.py` lines 478–479 contains a confirmed observability defect: when `decision_history.jsonl` fails to read or parse, it silently swallows the exception and calculates `stability_score = 100`, emitting fabricated 100% stability telemetry without logging a warning.
2. In contrast, `backend/control_plane/backend/app/main.py` lines 1054 and 1104 are fail-closed (`return False, {"status": "failed", ...}`), but adding `logger.warning` will ensure complete observability consistency.

---

## 8. SMALLEST NEXT IMPLEMENTATION TASK (PHASE 2.5.6)

### Scope
PRAVAH ONLY.

### Authorized Files:
1. `backend/control_plane/api/agent_api.py`
2. `backend/control_plane/backend/app/main.py`
3. `backend/tests/test_phase2_error_boundary_security.py`
4. `audit/PHASE2_5_6_REMAINING_SILENT_EXCEPTION_REMEDIATION.md`

### Remediation Requirements:
1. **`agent_api.py` (`/metrics`)**:
   - In `prometheus_metrics()`: Log a descriptive warning on read/parse failure (`logger.warning("Failed to parse decision history for metrics: %s", exc)`).
   - When history parsing fails, set `stability_score = None` and omit `pravah_stability_score` or emit `pravah_stability_score_status unavailable` rather than calculating a false `100` score.
2. **`main.py` (`execute_action()`)**:
   - In lines 1054 and 1104: Add `logger.warning("Failed to record contract FAILED state during error unwind: %s", exc)` prior to `pass`.
3. **Tests**:
   - Add tests in `test_phase2_error_boundary_security.py` using `flask_client` proving:
     - Normal `/metrics` succeeds with genuine counts.
     - When `decision_history.jsonl` is corrupted or unwritable, `/metrics` does NOT emit fabricated 100% stability, logs a warning, and handles failure cleanly.
     - Unwind logging in `execute_action()` is captured during secondary failure.
