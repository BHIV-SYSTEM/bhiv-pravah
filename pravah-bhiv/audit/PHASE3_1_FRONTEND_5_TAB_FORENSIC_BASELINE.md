# PHASE 3.1 FRONTEND 5-TAB FORENSIC BASELINE

**Audit Date**: 2026-09-12  
**Authoritative Execution Root**: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Scope**: Pravah Frontend Console (`frontend/`)  
**Status**: COMPLETE — FORENSIC / BASELINE ONLY (Zero Production Code Modified)

---

## 1. Executive Summary & Repository Scope Forensics

This audit forensically establishes the exact state of the five core Pravah Frontend console routes:
1. **Dashboard** (`/`)
2. **Runtime** (`/runtime`)
3. **Replay Engine** (`/replay`)
4. **Live Logs** (`/logs`)
5. **Analytics** (`/analytics`)

### 1.1 Git State & VANA Invariance
- `git status --short`: Zero production code files, test files, or VANA files modified.
- All pre-existing modified files in git status are runtime-generated logs and nonce stores (`logs/agent/`, `logs/control_plane/`, `security/nonce_store.json`).
- `git diff --name-only | findstr /i "vana"`: **0 diff** (VANA completely untouched).
- `npx tsc --noEmit` (in `frontend`): **0 errors** (TypeScript compilation passes).

### 1.2 Local Service Infrastructure Verification
During this audit, all backend dependencies and frontend servers were verified running on local TCP ports:
- `http://localhost:4500`: Next.js 16.2.12 Frontend (PID 21832, Node.js)
- `http://localhost:8000`: Pravah Decision Brain FastAPI (PID 17764, Python 3.14 Uvicorn)
- `http://localhost:7000`: Multi-Agent Control Plane Flask (PID 11420, Python 3.14)
- `http://localhost:8600`: Pravah Observer FastAPI (PID 17000, Python 3.14 Uvicorn)

---

## 2. Route-by-Route Forensic Breakdown

### 2.1 Route 1: `/` (System Dashboard)

1. **Exact Component File**:
   `frontend/src/app/page.tsx`
2. **Exact Hooks / Services / API Functions**:
   - `useLiveDashboard()` (`frontend/src/hooks/useBackend.ts` line 4) &rarr; `api.getLiveDashboard()` (`frontend/src/services/api.ts` line 42)
   - `useObserverEvents(10)` (`frontend/src/hooks/useBackend.ts` line 89) &rarr; `api.getObserverEvents(10)` (`frontend/src/services/api.ts` line 165)
   - `useIngestLink()` (`frontend/src/hooks/useBackend.ts` line 122) &rarr; `api.ingestLink(link)` (`frontend/src/services/api.ts` line 111)
   - `useRemoveLink()` (`frontend/src/hooks/useBackend.ts` line 132) &rarr; `api.removeLink(link)` (`frontend/src/services/api.ts` line 116)
3. **Exact Backend Endpoints & Ports**:
   - `GET http://localhost:8000/live-dashboard`
   - `GET http://localhost:8600/api/events?limit=10`
   - `POST http://localhost:8000/ingest-link`
   - `POST http://localhost:8000/remove-link`
4. **Actual Backend Response Schema (`GET /live-dashboard`)**:
   Authoritative backend schema in `backend/control_plane/backend/app/schemas.py` line 106 (`LiveDashboardResponse`):
   ```python
   {
       "generated_at": datetime,
       "environment": str, # e.g. "prod"
       "system_health": {
           "cpu_utilization_pct": int | null,
           "memory_utilization_pct": int | null,
           "status": str, # "HEALTHY" | "DEGRADED" | "UNKNOWN"
           "collection_status": str # "available" | "unavailable"
       },
       "ml_intelligence": {
           "latency_ema_p50": float,
           "latency_ema_p95": float,
           "latency_ema_p99": float,
           "failure_rate_15m": float,
           "error_velocity": float,
           "avg_retries_per_event": float,
           "max_retry_chain": int,
           "cert_success_rate_rolling": float,
           "validation_score_mean": float,
           "validation_score_variance": float,
           "bottleneck_component_encoded": int,
           "bottleneck_latency_ms": float,
           "queue_depth_zscore": float,
           "latency_zscore": float,
           "correlated_failure_index": float,
           "throughput_rps_1m": float,
           "throughput_rps_5m": float,
           "cpu_utilization_pct": float,
           "memory_utilization_pct": float
       },
       "recent_decisions": list[DecisionResponse],
       "monitored_services": list[LiveDomainStatus]
       # LiveDomainStatus: { name, domain, url, status, health_score, response_time_ms, cpu_percent, memory_percent, uptime_percent, last_action, errors_24h }
   }
   ```
5. **Frontend Expected Schema (`frontend/src/types/index.ts` lines 98–136)**:
   Expects: `header`, `live_production_monitoring`, `summary_metrics`, `ai_learning_status`, `system_health` (as Array), `performance_metrics`, `project_files_status`, `enhanced_telemetry`, `policy_evolution`, `error_analytics`, `auto_failover_status`, `live_events`.
6. **Schema & Property Mismatches**:
   - **`monitored_services` vs `live_production_monitoring`**: Backend returns `monitored_services`. Frontend looks for `dashboard.live_production_monitoring` (line 108). Evaluates to `[]`, leaving all charts and monitored link tables empty.
   - **`system_health` Object vs Array**: Backend returns `{ cpu_utilization_pct, memory_utilization_pct, status, collection_status }`. Frontend checks `Array.isArray(dashboard.system_health)`. Evaluates to `false`, leaving the top 4 metric cards completely blank.
   - **`live_events` vs `eventsData`**: Page line 42 fetches `eventsData` via `useObserverEvents(10)`, but line 364 checks `dashboard.live_events` which does not exist in backend response.
   - **`header` & `auto_failover_status`**: Do not exist in backend response payload.
7. **HTTP Status Code**:
   - Page: `GET http://localhost:4500/` &rarr; **HTTP 200 OK**.
   - Backend: `GET http://localhost:8000/live-dashboard` &rarr; **HTTP 200 OK**.
   - Observer: `GET http://localhost:8600/api/events?limit=10` &rarr; **HTTP 200 OK**.
8. **Rendered State**:
   **Empty State**. Top cards are blank; charts show no data; service distribution shows "No nodes active"; failover domain displays "N/A"; live events feed is blank.
9. **Hardcoded / Synthetic Values**:
   - `'System Dashboard'` and `'Live Telemetry'` fallback header text.
   - `'SYSTEM OPERATIONAL'` status pill (hardcoded in JSX).
10. **Authentication Requirement**:
    - Queries (`GET /live-dashboard`, `GET /api/events`): **Unauthenticated**.
    - Mutations (`POST /ingest-link`, `POST /remove-link`): **Authenticated** (`verify_control_plane_auth` requires valid JWT).
11. **Authentication Reality**:
    Frontend Axios client omits `Authorization` header. Calling ingest or remove from the UI fails with HTTP 401 (`Authentication required: missing token`).

---

### 2.2 Route 2: `/runtime` (Runtime Manager)

1. **Exact Component File**:
   `frontend/src/app/runtime/page.tsx`
2. **Exact Hooks / Services / API Functions**:
   - `useLiveDashboard()` (`frontend/src/hooks/useBackend.ts` line 4) &rarr; `api.getLiveDashboard()`
   - `useAutonomousStatus()` (`frontend/src/hooks/useBackend.ts` line 13) &rarr; `api.getAutonomousStatus()` (`api.ts` line 47)
3. **Exact Backend Endpoints & Ports**:
   - `GET http://localhost:8000/live-dashboard` (Port 8000)
   - `GET http://localhost:8000/autonomous-status` (Port 8000)
4. **Actual Backend Response Schema (`GET /autonomous-status`)**:
   `{"last_runtime": null, "last_action": null, "recent_autonomous_decisions": [], "loop_running": true}`
5. **Frontend Expected Schema**:
   `AutonomousStatus`: `{ last_runtime: Record<string, any> | null, last_action: string | null, recent_autonomous_decisions: Record<string, any>[], loop_running: boolean }`. Matches backend schema.
6. **Schema & Property Mismatches**:
   - Line 34: `const runtimes = dashboard?.live_production_monitoring || [];`
     Because backend provides `monitored_services`, `runtimes` is always `[]`.
   - Line 137: `autoStatus?.last_action || dashboard?.live_production_monitoring?.[0]?.last_action || 'noop'`. Falls back to `'noop'` because `live_production_monitoring` is undefined.
   - The page does not query registered control plane apps from Port 7000 (`/api/control-plane/health`), where 49 registered services reside.
7. **HTTP Status Code**:
   - Page: `GET http://localhost:4500/runtime` &rarr; **HTTP 200 OK**.
   - Backend: `GET http://localhost:8000/autonomous-status` &rarr; **HTTP 200 OK**.
8. **Rendered State**:
   **Partially Rendered**.
   - Active Compute Nodes table: "No active compute nodes available."
   - RL Autonomy Loop card: Status `RUNNING`, Loop cycle `Continuous`, Last Execution Event `noop`.
   - Historical Decisions table: "No decisions recorded in loop current cycles."
9. **Hardcoded / Synthetic Values**:
   - Fallback string `'noop'`.
   - Hardcoded text: "Rules require RL Agent suggestions to pass Shakti E2E governance contract checking."
10. **Authentication Requirement**:
    - **Unauthenticated**. Both endpoints are public read-only within CORS.
11. **Authentication Reality**:
    - Unauthenticated, works without token.

---

### 2.3 Route 3: `/replay` (Replay Engine)

1. **Exact Component File**:
   `frontend/src/app/replay/page.tsx` (and `frontend/src/components/ReplayVisualizer.tsx`)
2. **Exact Hooks / Services / API Functions**:
   - `useObserverLineage()` (`useBackend.ts` line 97) &rarr; `api.getObserverLineage()` (`api.ts` line 173)
   - `useLineageReplay(activeExecId)` (`useBackend.ts` line 105) &rarr; `api.getLineageReplay(id)` (`api.ts` line 82)
   - `useVerifyLineage(activeExecId)` (`useBackend.ts` line 113) &rarr; `api.verifyLineage(id)` (`api.ts` line 98)
3. **Exact Backend Endpoints & Ports**:
   - `GET http://localhost:8600/api/lineage` (Port 8600)
   - `GET http://localhost:8000/api/lineage/{execution_id}` (Port 8000)
   - `GET http://localhost:8000/api/lineage/{execution_id}/verify` (Port 8000)
4. **Actual Backend Response Schema**:
   - `GET /api/lineage` (Observer):
     `{"lineages": [{"bundle_id": str, "trace_id": str, "execution_id": str, "decision_id": str, "decision_type": str, "authority_chain": list[str], "evidence": dict|list, "replay_reference": str, "constitutional_hash": str, "produced_at": str, "correlation_id": str, "source": str, "action": str}]}`
   - `GET /api/lineage/{id}`:
     `{"execution_id": str, "valid": bool, "final_state": str|null, "execution_state_history": list[str], "events": list[dict], "execution_hash": str|null, "runtime_attestation": dict|null}`
   - `GET /api/lineage/{id}/verify`:
     `{"execution_id": str, "valid": bool, "hash_chain_valid": bool, "fsm_valid": bool, "error": str|null, "runtime_attestation_valid": bool|null, "runtime_attestation_error": str|null}`
5. **Frontend Expected Schema**:
   `EvidenceBundle`: matches backend schema.
6. **Schema & Property Mismatches**:
   - Schema matches accurately.
   - **Crash Risk**: Line 178 does `bundle.authority_chain?.join(' -> ')`. If `authority_chain` is ever a string or non-array from unnormalized logs, calling `.join()` throws an unhandled `TypeError`, crashing the React tree.
   - Live payload verification: All 13 items in current live observer return `list[str]`. Defensive check (`Array.isArray(...)`) is warranted.
7. **HTTP Status Code**:
   - Page: `GET http://localhost:4500/replay` &rarr; **HTTP 200 OK**.
   - Backend: All three endpoints return **HTTP 200 OK**.
8. **Rendered State**:
   **Meaningful Data Rendered**.
   The evidence table renders all 13 active lineage bundles with timestamps, execution IDs, bundle IDs, and authority chains. Clicking replay queries the backend verification engine and updates visualizer states.
9. **Hardcoded / Synthetic Values**:
   - None. Data originates from backend observer journal.
10. **Authentication Requirement**:
    - **Unauthenticated**. All three endpoints are public read-only within CORS.
11. **Authentication Reality**:
    - Unauthenticated, works without token.

---

### 2.4 Route 4: `/logs` (Live Logs)

1. **Exact Component File**:
   **GENUINELY ABSENT**. Directory `frontend/src/app/logs` does not exist (`Test-Path` returned `False`).
2. **Exact Hooks / Services / API Functions**:
   None instantiated.
   Available hooks in `useBackend.ts`:
   - `useObserverEvents(limit, refetchInterval)` (calls `GET http://localhost:8600/api/events`)
   - `useObserverStatus(refetchInterval)` (calls `GET http://localhost:8600/api/status`)
   - `useRecentActivity()` (calls `GET http://localhost:8000/recent-activity`)
3. **Exact Backend Endpoints & Ports**:
   Candidate endpoints:
   - `GET http://localhost:8600/api/events?limit=100` (Port 8600)
   - `GET http://localhost:8600/api/status` (Port 8600)
4. **Actual Backend Response Schema (`GET /api/events`)**:
   ```json
   {
       "total": int,
       "events": [
           {
               "ts": "2026-09-12T05:42:01.354484",
               "service": "samruddhi",
               "status": "healthy",
               "detail": "...",
               "latency_ms": 1831.8
           }
       ]
   }
   ```
5. **Frontend Expected Schema**:
   `TelemetryEvent` in `types/index.ts` line 9:
   `{ ts: string; service: string; status: string; detail: string; latency_ms: number; }`. Exactly matches observer response.
6. **Schema & Property Mismatches**:
   Route file is missing completely.
7. **HTTP Status Code**:
   - Page: `GET http://localhost:4500/logs` &rarr; **HTTP 404 Not Found**.
   - Backend candidate: `GET http://localhost:8600/api/events` &rarr; **HTTP 200 OK**.
8. **Rendered State**:
   **Next.js 404 "This page could not be found."**
9. **Hardcoded / Synthetic Values**:
   - N/A.
10. **Authentication Requirement**:
    - Candidate observer endpoints: **Unauthenticated**.
11. **Authentication Reality**:
    - Observer telemetry streams are public read-only within CORS.

---

### 2.5 Route 5: `/analytics` (Analytics Center)

1. **Exact Component File**:
   `frontend/src/app/analytics/page.tsx`
2. **Hooks / Services / API Functions**:
   - `useLiveDashboard()` (`frontend/src/hooks/useBackend.ts` line 4) &rarr; `api.getLiveDashboard()`
3. **Exact Backend Endpoints & Ports**:
   - `GET http://localhost:8000/live-dashboard` (Port 8000)
4. **Actual Backend Response Schema (`GET /live-dashboard`)**:
   Returns: `generated_at`, `environment`, `system_health`, `ml_intelligence`, `recent_decisions`, `monitored_services`.
   (Full schema detailed under Section 2.1).
5. **Frontend Expected Schema**:
   - `dashboard.live_production_monitoring` for chart series.
   - `dashboard.enhanced_telemetry.avg_latency`, `.cost`, `.success`, `.requests` for metric cards.
6. **Schema & Property Mismatches**:
   - **`live_production_monitoring` missing**: Backend emits `monitored_services`. Result: `chartsData` is empty `[]`.
   - **`enhanced_telemetry` missing**: Backend does NOT emit `enhanced_telemetry` or fields named `avg_latency`, `cost`, `requests`, `success`.
   - **Available backend analytics**: Backend DOES provide real ML feature extraction metrics under `ml_intelligence`:
     - `latency_ema_p50`, `latency_ema_p95`, `latency_ema_p99`
     - `failure_rate_15m`, `cert_success_rate_rolling`
     - `throughput_rps_1m`, `throughput_rps_5m`
     - `cpu_utilization_pct`, `memory_utilization_pct`
   - Real orchestration metrics also exist under `GET http://localhost:8000/orchestration/metrics`.
7. **HTTP Status Code**:
   - Page: `GET http://localhost:4500/analytics` &rarr; **HTTP 200 OK**.
   - Backend: `GET http://localhost:8000/live-dashboard` &rarr; **HTTP 200 OK**.
8. **Rendered State**:
   **Empty Charts with Hardcoded Stat Placeholders**.
   - Response Latency Histogram: Empty.
   - Downstream Stability Uptime: Empty.
   - Failure Frequency: Empty.
   - Metric cards display hardcoded fallbacks: `'120ms'`, `'$0.0025'`, `'100%'`, `'1'`.
9. **Hardcoded / Synthetic Values**:
   - `'120ms'`, `'$0.0025'`, `'100%'`, `'1'` are hardcoded fallback values in JSX.
10. **Authentication Requirement**:
    - **Unauthenticated**. `GET /live-dashboard` is public read-only within CORS.
11. **Authentication Reality**:
    - Unauthenticated, works without token.

---

## 3. Dedicated Authentication Forensics & Integration Gap Assessment

### 3.1 Frontend Inspection (`frontend/src/services/api.ts`)
- Inspection of `api.ts` confirms three Axios clients (`decisionBrainApi`, `controlPlaneApi`, `observerApi`).
- None of the clients configure `Authorization` or `X-API-Token` headers.
- There are no Axios request/response interceptors.
- There is no authentication module, session token hook, or token storage utility.

### 3.2 Frontend Storage Inspection
- `localStorage`: Only used for theme preference (`theme: 'light' | 'dark'`).
- `sessionStorage`: Zero occurrences in entire frontend codebase.
- Cookies: Zero occurrences in entire frontend codebase.
- Zustand store (`useUiStore.ts`): Zero authentication states or token properties.
- Navigation bar (`Layout.tsx` line 182): The "Operator" profile icon is a static HTML button with no click handler or auth modal.

### 3.3 Backend Inspection (`backend/control_plane/backend/app/main.py`)
- Ingestion endpoints require authentication:
  ```python
  @app.post("/ingest-link", response_model=LinkIngestResponse)
  def ingest_link(payload: LinkIngestRequest, auth: dict[str, Any] = Depends(verify_control_plane_auth)):
  ```
  ```python
  @app.post("/remove-link", response_model=LinkRemoveResponse)
  def remove_link(payload: LinkRemoveRequest, auth: dict[str, Any] = Depends(verify_control_plane_auth)):
  ```
- `verify_control_plane_auth()` reads `Authorization: Bearer <token>` or `X-API-Token: <token>`.
- Validates token against `TokenAuth` in `backend/security/auth.py`.
- The live backend process enforces `JWT_SECRET_KEY` configured in `backend/environments/prod.env` line 50.
- Missing token yields HTTP 401: `{"detail": "Authentication required: missing token"}`.
- Invalid token yields HTTP 401: `{"detail": "Authentication failed: Invalid token"}`.

### 3.4 Forensic Determination: Integration Gap
- **No legitimate frontend authentication, login dialog, or token issuance flow exists in the codebase.**
- Per strict task instructions:
  - We do NOT generate a token automatically in frontend code.
  - We do NOT hardcode a JWT into `api.ts` or client files.
  - We do NOT create a new ad-hoc authentication mechanism without authorization.
- **Classification**: The absence of a frontend authentication mechanism for mutating actions (`/ingest-link`, `/remove-link`) is an **Integration Gap requiring an architectural decision**. Read-only dashboard and observability features can proceed without auth.

---

## 4. Classification of Implementation Proposals

Every proposed remediation from the implementation plan is classified into categories **A**, **B**, or **C**:

- **A = Directly proven and safe to implement**:
  1. **Create `/logs/page.tsx`**: Route is genuinely 404. Backend Observer endpoint `GET http://localhost:8600/api/events` is active, unauthenticated, and emits real `TelemetryEvent` data matching types.
  2. **Map `monitored_services` on Dashboard**: Backend schema proves `monitored_services` exists. Mapping this field safely populates the monitored links table and latency/resource charts.
  3. **Parse `system_health` Object on Dashboard**: Backend schema proves `system_health` is `{ cpu_utilization_pct, memory_utilization_pct, status, collection_status }`. Parsing this object safely renders CPU, Memory, and System Status cards.
  4. **Bind Ecosystem Timeline to Observer Events**: Hook `useObserverEvents(10)` is already active on Dashboard page; binding its result replaces the non-existent `dashboard.live_events`.
  5. **Map `monitored_services` on Runtime Page**: Safely populates the active compute table when links/runtimes are ingested.
  6. **Add Defensive `Array.isArray()` Check for `authority_chain` on Replay**: Eliminates potential unhandled `TypeError` in React.
  7. **Map `monitored_services` into Analytics Histograms**: Safely populates latency, error, and uptime charts.
  8. **Map `ml_intelligence` into Analytics Stat Cards**: Replaces hardcoded mock strings (`'120ms'`, `'$0.0025'`, etc.) with real calculated ML features (`latency_ema_p50`, `cert_success_rate_rolling`, `throughput_rps_1m`).

- **B = Requires design/authorization decision**:
  1. **Frontend Authentication for Ingest/Remove Link**: Since mutating endpoints require JWT and no frontend login or token distribution mechanism exists, a design decision is required:
     - *Option 1*: Implement an Operator Token input in Configuration/Settings page stored in `localStorage`.
     - *Option 2*: Expose a Next.js server-side route handler that signs or proxies requests using a server-side secret.
     - *Option 3*: Keep ingestion disabled in public UI and display a read-only badge.

- **C = Contradicted by current source/runtime evidence**:
  - *None*. No proposals contradict source or runtime evidence.

---

## 5. Verification Checklist & Route HTTP Status Matrix

| Route | Page File Status | Port Called | Route HTTP Status | Data Rendered |
|---|---|---|---|---|
| `/` | Exists (`app/page.tsx`) | `8000`, `8600` | **200 OK** | Empty (Schema mismatch on `system_health` and `monitored_services`) |
| `/runtime` | Exists (`app/runtime/page.tsx`) | `8000` | **200 OK** | Partial (Autonomy loop running, compute table empty) |
| `/replay` | Exists (`app/replay/page.tsx`) | `8600`, `8000` | **200 OK** | **Meaningful Data** (13 live evidence bundles rendered) |
| `/logs` | **ABSENT** (`app/logs/` missing) | `8600` (candidate) | **404 Not Found** | 404 Page |
| `/analytics` | Exists (`app/analytics/page.tsx`) | `8000` | **200 OK** | Empty (Charts empty, cards display hardcoded fallbacks) |

---

## 6. Final Certification & Classification

### **Final Forensic Classification: B**
- **Justification**:
  - Phase 3.1 frontend baseline is completely investigated and verified against running local services.
  - All read-only observability wiring across the 5 tabs (creating `/logs`, fixing schema property mismatches, binding real observer events, and defensive type-guards) is **Classification A** (fully proven and safe to implement).
  - Mutating operations (`POST /ingest-link`, `POST /remove-link`) remain blocked on an authentication architecture decision (**Classification B**), as no legitimate frontend token acquisition flow exists.
  - Zero production code was modified during this task. Zero VANA diff was introduced.
