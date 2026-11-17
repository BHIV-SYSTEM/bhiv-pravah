# PRAVAH — Health Status Stability & Clickable Service URLs Verification Report

**Date:** November 14, 2026
**Repository:** `C:\Users\Microsoft\week\bhiv-pravah`
**Status:** IMPLEMENTED & LOCALLY VERIFIED (Pending VM Deployment)

---

## 1. Executive Summary

Based on Alay's feedback, two targeted system improvements have been implemented across the PRAVAH backend and frontend:

1. **Elimination of Health Status Fluctuation:**
   Resolved the issue where external and slow-polling services repeatedly oscillated between `HEALTHY` and `DEGRADED`. Implemented configurable hysteresis thresholds, consecutive failure/success counters, rolling latency evaluation, preserved genuine `UNREACHABLE` states under sustained downtime, and ensured raw probe metrics are cleanly distinguished from stabilized display statuses without masking actual outages.

2. **Secure Clickable Service URLs:**
   Updated all service-list views across **Observer**, **Services**, **Control Plane**, and the **Main Dashboard** so network endpoint URLs open in a new tab (`target="_blank"`, `rel="noopener noreferrer"`). Developed a hardened URL sanitizer component (`ServiceUrlLink`) that strips user credentials, redacts sensitive query tokens, rejects malicious URI schemes (`javascript:`, `data:`), stops click event propagation to parent cards/rows, and safely degrades missing or placeholder URLs into plain text without rendering broken links.

All 95 backend tests, 6 unit validation tests, TypeScript compilation, Next.js production build across 20 routes, and Playwright verification passed.

---

## 2. Root Cause Analysis: Health Status Fluctuation

### Identified Root Causes

1. **Single-Probe Latency Breaches Triggered Immediate Status Flipping:**
   In `health_engine.py`, the probe evaluation logic directly compared instantaneous `latency_ms > self.sla_latency`. External endpoints (e.g., Render-hosted services such as Gurukul, UniGuru, Sarathi) and local services under intermittent load naturally experience network jitter (e.g. 520ms on probe N, 480ms on probe N+1). A single packet exceeding the SLA threshold immediately mutated the service state to `DEGRADED`, and the subsequent normal packet immediately reset it to `HEALTHY`, causing continuous status flapping.

2. **Absence of Consecutive Degradation and Recovery Hysteresis:**
   Prior to this fix, there was no consecutive sample memory. Transient socket resets or HTTP 5xx errors flipped the service to `DEGRADED` on sample 1, and 1 successful check flipped it back to `HEALTHY`. A true state machine requires **damping** on entering degradation and **confirmation** on recovery.

3. **Conflation of Raw Probe Data and Stabilized Presentation State:**
   Raw instantaneous probe measurements were directly assigned to `svc["status"]`. The UI had no way to display stabilized health while keeping actual instantaneous latency visible.

---

## 3. Implementation Details

### A. Backend Health Hysteresis & Threshold Engine (`health_engine.py`)

- **Configurable Damping Parameters:**
  - `PRAVAH_DEGRADATION_THRESHOLD` (Default: 2): Requires $N$ consecutive degraded probes before a healthy service transitions to `DEGRADED`.
  - `PRAVAH_RECOVERY_THRESHOLD` (Default: 2): Requires $M$ consecutive healthy probes before a degraded or recovering service returns to `HEALTHY`.
  - `PRAVAH_UNREACHABLE_THRESHOLD` (Default: 2): Requires sustained connection failures before escalating to canonical `UNREACHABLE`.
- **State Machine Mechanics:**
  - **Damping:** An isolated slow probe or transient glitch increments `consecutive_degraded` but leaves stabilized `status` as `HEALTHY`.
  - **Recovery:** A degraded service entering recovery displays `DEGRADED (Recovering 1/2)` until the recovery threshold is achieved.
  - **Sustained Outages:** Connection refused or timeout errors sustain `UNREACHABLE` or `DEGRADED` states; real outages are never masked or artificially forced to `HEALTHY`.
  - **Staleness Preservation:** `check_staleness()` guarantees that when polling data is older than $2.5 \times \text{poll\_interval}$, the state transitions to `STALE` and is never rendered as `HEALTHY`.
- **Raw Probe vs. Stabilized Separation:**
  - `svc["raw_status"]`: Instantaneous probe outcome (`HEALTHY`, `DEGRADED`, `UNREACHABLE`).
  - `svc["raw_detail"]`: Sanitized raw response detail.
  - `svc["status"]`: Stabilized canonical display state.
  - `svc["latency_ms"]`: Exact probe latency.
  - `svc["rolling_avg_latency_ms"]`: Rolling average latency from reservoir.
  - `svc["last_checked"]`: Exact UTC ISO timestamp.

### B. Observer Server Integration (`observer_server.py`)

- Initialized `ServiceHealthTracker` with configurable environment variables (`PRAVAH_DEGRADATION_THRESHOLD`, `PRAVAH_RECOVERY_THRESHOLD`, `PRAVAH_UNREACHABLE_THRESHOLD`).
- Forwarded `raw_status` and `rolling_avg_latency_ms` into the observation event bus and telemetry stream.

### C. Secure Clickable URL Component (`ServiceUrlLink.tsx`)

Created `pravah-bhiv/frontend/src/components/ServiceUrlLink.tsx`:
- **Security Sanitization:** Strips embedded basic auth userinfo (`http://user:pass@host` $\rightarrow$ `http://host`), redacts sensitive tokens in query parameters (`token=REDACTED`), and strictly whitelists `http:` and `https:` protocols.
- **Placeholder Handling:** Strings such as `"N/A"`, `"-"`, `"null"`, `"unknown"`, and `"Internal Service"` safely render as non-clickable muted text.
- **Interaction Protection:** Uses `e.stopPropagation()` to ensure clicking the link does not trigger parent row selection, accordion toggles, or card clicks.
- **Responsive Layout:** Applies `truncate` with `break-all` and external link icon (`ExternalLink` from `lucide-react`).

### D. Frontend View Integrations

- `pravah-bhiv/frontend/src/app/observer/page.tsx`: Embedded `ServiceUrlLink` on all service cards.
- `pravah-bhiv/frontend/src/app/services/page.tsx`: Integrated `ServiceUrlLink` into the canonical service inventory table.
- `pravah-bhiv/frontend/src/app/control-plane/page.tsx`: Added clickable health probe and app endpoint links on orchestrated agent cards.
- `pravah-bhiv/frontend/src/app/page.tsx`: Integrated clickable links into Customer Products and Platform Core tables on the main Dashboard.

---

## 4. Verification & Test Evidence

### A. Backend Pytest Suite (95/95 Passed)

Command executed:
```bash
python -m pytest pravah-bhiv/backend/tests/test_all_10_requirements.py \
                 pravah-bhiv/backend/tests/test_application_telemetry_isolation.py \
                 pravah-bhiv/backend/tests/test_runtime_activation.py \
                 pravah-bhiv/backend/tests/test_control_plane_override.py \
                 pravah-bhiv/backend/tests/test_cpu_metrics_stability.py \
                 pravah-bhiv/backend/tests/test_health_stability.py
```

Results:
```
collected 95 items

pravah-bhiv/backend/tests/test_all_10_requirements.py ..............     [ 14%]
pravah-bhiv/backend/tests/test_application_telemetry_isolation.py .....  [ 20%]
pravah-bhiv/backend/tests/test_runtime_activation.py ........            [ 28%]
pravah-bhiv/backend/tests/test_control_plane_override.py ............... [ 44%]
......................................                                   [ 84%]
pravah-bhiv/backend/tests/test_cpu_metrics_stability.py .........        [ 93%]
pravah-bhiv/backend/tests/test_health_stability.py ......                [100%]

======================= 95 passed, 7 warnings in 2.33s ========================
```

### B. Health Stability Test Suite (`test_health_stability.py`)

1. `test_transient_latency_spike_does_not_flip_healthy_status`: Confirms single 650ms spike on a healthy service is damped and does not trigger DEGRADED.
2. `test_alternating_probes_prevent_status_flapping`: Confirms sequence of alternating 530ms/240ms probes maintains steady HEALTHY status.
3. `test_sustained_failures_trigger_degradation_and_unreachable`: Confirms consecutive failures cross thresholds to DEGRADED and sustained connection refused transitions to UNREACHABLE.
4. `test_recovery_requires_consecutive_successes`: Confirms recovering from DEGRADED requires 2 consecutive successful checks.
5. `test_stale_data_is_never_shown_as_healthy`: Confirms expired last_checked timestamps are classified as STALE.
6. `test_raw_probe_and_stabilized_status_separation`: Confirms raw error metrics are recorded while stabilized status remains damped.

### C. Frontend Unit & Type Checks

- `node pravah-bhiv/frontend/scripts/test_service_url_link.js`: 6/6 assertions passed (valid URLs, credential stripping, token redaction, scheme rejection, placeholder fallbacks).
- `npx tsc --noEmit`: Exited with code 0 (zero TypeScript errors).
- `npm run build`: Exited with code 0 across all 20 Next.js routes.

### D. Playwright E2E Suite (`test_service_urls_playwright.py`)

- `Observer Service URL Links`: PASS (Found external service links with `target="_blank"`).
- `Services Table URL Links`: PASS (Found clickable service table links).
- `Control Plane URL Links`: PASS (Health probe and service URL links rendered).
- `Dashboard Product Scorecard Links`: PASS (Customer product table links rendered).
- `Security & Credentials Redaction`: PASS (No `javascript:` or embedded userinfo credentials found in anchor tags).

---

## 5. Modified and Untracked Files Summary

| File Path | Type | Description |
|:---|:---|:---|
| `pravah-bhiv/backend/health_engine.py` | Source | Hysteresis damping, thresholds, rolling latency, raw vs stabilized state |
| `pravah-bhiv/backend/observer_server.py` | Source | Threshold configuration and telemetry event enrichment |
| `pravah-bhiv/backend/tests/test_health_stability.py` | Test | 6 regression tests for health stability and hysteresis |
| `pravah-bhiv/frontend/src/components/ServiceUrlLink.tsx` | Component | Secure clickable link component with redaction and propagation stop |
| `pravah-bhiv/frontend/src/app/observer/page.tsx` | Frontend | Integrated clickable URLs on Observer cards |
| `pravah-bhiv/frontend/src/app/services/page.tsx` | Frontend | Integrated clickable URLs in Services inventory table |
| `pravah-bhiv/frontend/src/app/control-plane/page.tsx` | Frontend | Integrated clickable URLs on Control Plane agent cards |
| `pravah-bhiv/frontend/src/app/page.tsx` | Frontend | Integrated clickable URLs on Main Dashboard product scorecard |
| `pravah-bhiv/frontend/scripts/test_service_url_link.js` | Test | Unit test for `ServiceUrlLink` sanitization and validation |
| `pravah-bhiv/frontend/scripts/test_service_urls_playwright.py` | Test | Playwright E2E test verifying clickable links across views |

---

## 6. Live Verification Notice

> [!IMPORTANT]
> All code changes are verified locally and adhere strictly to repository governance. In accordance with operational instructions:
> - No code has been committed or pushed yet.
> - The live system at `https://pravah.blackholeinfiverse.com` and the Observer daemon at port `8600` on the VM are running the previous deployment (`5244270`).
> - The status stabilization and clickable URL updates will take effect on the live environment once these changes are authorized, committed, pushed to `origin/main`, and deployed to the remote VM.
