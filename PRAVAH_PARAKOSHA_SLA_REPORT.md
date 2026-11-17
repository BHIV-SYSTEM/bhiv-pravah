# PRAVAH — Parakosha (bhiv-mdu-api) Health SLA Verification Report

**Date:** 2026-11-14
**Target Service:** Parakosha (`bhiv-mdu-api`)
**Target Health Endpoint:** `https://parakosha.blackholeinfiverse.com/health`
**Git Branch:** `fix/parakosha-mdu-health-sla`
**Status:** VERIFIED & READY FOR COMMIT

---

## 1. Executive Summary & Root Cause Analysis

### Problem Statement
Live Pravah monitoring reported `bhiv-mdu-api` (Parakosha) in a persistent `DEGRADED` status despite the service returning HTTP 200 with an entirely healthy payload:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 2.2
    },
    "gc_shakti": {
      "status": "reachable",
      "http_status": 200,
      "latency_ms": 376.9
    }
  }
}
```

### Root Cause
1. **Downstream Dependent Checks:** Parakosha's `/health` endpoint executes an active downstream reachability probe to `gc_shakti`, which incurs ~370–450ms of network roundtrip latency in addition to local database verification (~2ms).
2. **Normal Baseline Latency:** The composite HTTP roundtrip for Parakosha consistently measures between **680ms and 780ms**.
3. **Global Fixed SLA Constraint:** The Pravah Observer previously enforced a hardcoded global SLA of **500ms** across all services indiscriminately (`SLA_LATENCY_MS=500`).
4. **False Degradation:** Because 755ms > 500ms, the health engine correctly categorized this as `High latency (755.1ms exceeds 500ms SLA)`, causing false-positive DEGRADED alerts on a healthy service.

---

## 2. Solution Architecture & Technical Changes

### 2.1 Per-Service SLA Configuration
- **Configurable Environment Variable:** `PRAVAH_MDU_SLA_MS` with default `1200` ms.
- **ServiceHealthTracker Enhancement (`pravah-bhiv/backend/health_engine.py`):**
  - Added `service_slas: Optional[Dict[str, float]]` parameter to `__init__`.
  - Added `set_service_sla(name: str, sla_ms: float)` dynamic registration method.
  - Updated `register_service(...)` and `record_probe_result(...)` to resolve `effective_sla = sla_ms if sla_ms is not None else svc.get("sla_ms") or self.service_slas.get(name, self.sla_latency)`.
  - Updated probe latency evaluation to verify against `effective_sla` instead of the global SLA.
  - Updated `get_performance_summary()` slow endpoint detection to compare individual service p95 latencies against each service's configured SLA.
  - Exposed `sla_ms` in `get_unified_product_health()` output dictionary for UI visibility.

### 2.2 Observer Server Integration (`pravah-bhiv/backend/observer_server.py`)
- Configured:
  ```python
  PRAVAH_MDU_API_URL = os.getenv("PRAVAH_MDU_API", "https://parakosha.blackholeinfiverse.com")
  PRAVAH_MDU_SLA_MS = float(os.getenv("PRAVAH_MDU_SLA_MS", "1200"))
  ```
- Initialized `health_tracker` with `service_slas={"bhiv-mdu-api": PRAVAH_MDU_SLA_MS}`.
- Updated `_probe_service` signature and invocation to pass `sla_ms`.
- Registered `bhiv-mdu-api` in `_poll_loop` with `url=PRAVAH_MDU_API_URL`, `health_url=f"{PRAVAH_MDU_API_URL}/health"`, and `sla_ms=PRAVAH_MDU_SLA_MS`.

### 2.3 Strict Guarantee & Guardrails
- **Other Services Unchanged:** All other services (`crm-api`, `gurukul`, `blockchain`, `trade-bot`, etc.) strictly retain the 500ms global SLA.
- **Genuine Degradation Retained:** Parakosha responses exceeding 1200ms trigger `DEGRADED`.
- **Genuine Outages Retained:** Connection failures or HTTP 5xx errors trigger `DEGRADED` and sustained outages become `UNREACHABLE`.
- **Hysteresis Preserved:** Transient latency blips remain damped; recovery requires consecutive healthy probes.
- **Staleness Audit Preserved:** Missing probes for > 25s transition to `STALE`.

---

## 3. Test Verification Matrix

| Suite | Component / Test | Status | Evidence |
|---|---|---|---|
| **Per-Service SLA** | `test_parakosha_mdu_at_750ms_remains_healthy_under_1200ms_sla` | **PASSED** | Normal 755ms/780ms probe evaluates to `HEALTHY` |
| **Per-Service SLA** | `test_parakosha_mdu_above_1200ms_becomes_degraded` | **PASSED** | 1350ms/1400ms probe evaluates to `DEGRADED` (exceeds 1200ms SLA) |
| **Global SLA Retention** | `test_other_services_retain_500ms_global_sla` | **PASSED** | `crm-api` at 550ms degrades under 500ms SLA |
| **Sustained Outage** | `test_consecutive_failures_produce_unreachable_on_parakosha` | **PASSED** | 2 consecutive connection refused probes -> `UNREACHABLE` |
| **Recovery Threshold** | `test_consecutive_successes_recover_parakosha` | **PASSED** | Requires 2 consecutive healthy checks to transition back to `HEALTHY` |
| **Staleness Audit** | `test_stale_monitoring_data_on_parakosha` | **PASSED** | Unprobed data > 25s transitions to `STALE`, never displays as HEALTHY |
| **Separation of Metrics** | `test_raw_and_stabilized_status_with_per_service_sla` | **PASSED** | Raw status, stabilized status, rolling avg, and SLA exposed cleanly |
| **Stability Suite** | `test_health_stability.py` (Total 13 tests) | **PASSED** | 13/13 passed in 0.17s |
| **Backend Regression** | Complete backend test suite (6 files, 102 tests) | **PASSED** | 102/102 passed in 2.41s |
| **Unit Tests** | `test_service_url_link.js` | **PASSED** | 6/6 passed |
| **TypeScript** | `npx tsc --noEmit` | **PASSED** | 0 errors |

---

## 4. Git Delivery Plan

- **Branch:** `fix/parakosha-mdu-health-sla` (branched from `origin/main` at `2a3de57`).
- **Files Modified/Added:**
  - `pravah-bhiv/backend/health_engine.py`
  - `pravah-bhiv/backend/observer_server.py`
  - `pravah-bhiv/backend/tests/test_health_stability.py`
  - `PRAVAH_PARAKOSHA_SLA_REPORT.md`
- **Commit Message:**
  `fix: add per-service Parakosha health SLA`
- **Safety Checks:**
  - `git diff --cached --check` executed with zero whitespace errors.
  - Zero modifications to Docker, CI/CD, `.env`, or secrets.
  - Remote push targeted solely to `origin/fix/parakosha-mdu-health-sla`.
