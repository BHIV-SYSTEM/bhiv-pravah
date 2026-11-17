 # Integration Walkthrough: Pravah Runtime Observation

We have successfully integrated the `pravah-bhiv` observation layer into the `AI-Artha`, `core-integrator-collaborative-`, and `gurukul-backend-` systems. Pravah now actively observes execution metrics, latencies, state changes, and error logs across these runtimes without ownership or interference in their control flows.

## What Was Changed

### 1. Decision Brain & Port Resolution (pravah-bhiv)
- **Main App Server (`main.py`)**: Added a `/process-runtime` POST route to the FastAPI Decision Brain (running on port `8000`). This endpoint converts the agent runtime telemetry to a standard `DecisionRequest`, triggers policy rules using `DecisionEngine.decide`, and appends the result to `_RECENT_DECISIONS` for dashboard logging.
- **Agent Runtime (`agent_runtime.py`)**: 
  - Updated the default target port for the decision endpoint to `8000` (configurable via `DECISION_BRAIN_PORT` or `PORT`) to resolve the port conflict with the Node.js backend.
  - Dynamically appended the `control_plane` directory to `sys.path` to allow imports like `import core...` to resolve cleanly without name shadowing issues.
- **Unified Deployment (`deploy_pravah.py`)**: Fixed python import paths to use `control_plane.api.agent_api:app` and replaced the incompatible `signal.pause()` with a standard `time.sleep` loop for Windows systems.
- **Registry Specs**: Created and onboarded the following application specs under `control_plane/apps/registry`:
  - `artha-backend.json` (Node.js backend, port 5000)
  - `artha-fastapi.json` (Python FastAPI, port 9000)
  - `bhiv-integrator.json` (Python Integrator Bridge, port 8004)
  - `gurukul-backend.json` (Python FastAPI, port 3000) ← **NEW**

### 2. AI-Artha Node.js Runtime Integration
- **Tantra Service (`tantra.service.js`)**: 
  - Implemented the signed telemetry generator `sendTelemetryToPravah` using native Node.js cryptography (HMAC-SHA256) and Axios.
  - Hooked this telemetry sender directly into the `emitEvent` method. Every time the Node.js application generates a compliance event, ledger action, or transaction lifecyle update, it asynchronously reports to Pravah.

### 3. AI-Artha Python FastAPI Runtime Integration
- **Runtime Observability (`runtime_observability.py`)**: Added a background thread-based signed telemetry emitter `send_telemetry_to_pravah`. Connected it to `record_platform_event` to observe platform actions.

### 4. BHIV Core-Integrator Pipeline Integration
- **Integration Bridge (`integration_bridge.py`)**: Implemented a background-threaded telemetry sender `_report_to_pravah` and hooked it into the end of `process_full_pipeline` to report overall execution durations and status codes.

### 5. Gurukul Backend Integration ← NEW
- **Observer Server (`observer_server.py`)**:
  - Added `GURUKUL_API_URL = os.getenv("PRAVAH_GURUKUL_API", "http://localhost:3000")` to read the Gurukul backend address from the environment variable already passed by `start_with_observer.py`.
  - Added `gurukul-backend` as the **first** entry in the `_poll_loop` services dictionary, probing `GURUKUL_API_URL/health` every 10 seconds with a read-only GET request.
  - Observer dashboard (`http://localhost:8600`) now automatically renders a `gurukul-backend` service card with real-time status, latency, and last-checked timestamp.
- **Control Plane Registry (`gurukul-backend.json`)**:
  - Created the canonical registry entry at `control_plane/apps/registry/gurukul-backend.json` for the Pravah `MultiAppControlPlane`, registering port `3000`, health endpoint `/health`, and scaling policy.
  - Decision history is now accessible at `GET /api/control-plane/history/gurukul-backend`.
- **Pravah Adapter (`pravah_adapter.py`)** — *No change needed*:
  - The existing `PravahAdapter` in `gurukul-backend-/backend/app/services/` already emits signed telemetry (`app: "gurukul-backend"`) to `PRAVAH_URL` every 60s and on every `emit_signal()` call from routers. This push path was already operational.
- **Launcher (`start_with_observer.py`)** — *No change needed*:
  - Already passes `PRAVAH_GURUKUL_API: http://localhost:3000` to the Observer process. Now that the Observer reads this variable, the wire is complete.

---

## Verification & Testing

To test the integration, we started the Pravah services and ran targeted verification scripts that directly mock operations in the target systems:

### 1. Verification of AI-Artha Node.js Observability
We triggered a transaction lifecycle event using [verify_artha_observability.js](file:///c:/Users/black/OneDrive/Desktop/Pravah/AI-Artha/backend/src/verify_artha_observability.js):
```bash
node src/verify_artha_observability.js
```
**Result**:
- Payload signed with trace ID `trace-b0595f7d-8c6e-4a0c-ac42-ddcdbdc2acda`.
- Pravah Flask API server received the POST request at `/api/runtime` and returned `200 OK`.
- The Decision Brain resolved the telemetry to a policy check and decided on `scale_down`.

### 2. Verification of AI-Artha FastAPI Observability
We ran [verify_fastapi_observability.py](file:///C:/Users/black/.gemini/antigravity-ide/brain/9a708983-52c9-4a32-8710-73529b366a29/scratch/verify_fastapi_observability.py):
```bash
python verify_fastapi_observability.py
```
**Result**:
- A platform event was triggered.
- Telemetry payload containing `app: artha-fastapi` was successfully posted to Pravah's `/api/runtime` endpoint.

### 3. Verification of Core-Integrator Observability
We executed [verify_integrator_observability.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/core-integrator-collaborative-/verify_integrator_observability.py) to simulate a pipeline run:
```bash
python verify_integrator_observability.py
```
**Result**:
- Telemetry payload containing `app: bhiv-integrator` was successfully posted to Pravah's `/api/runtime` endpoint.

### 4. Verification of Gurukul Backend Observability ← NEW
We executed [verify_gurukul_observability.py](file:///C:/Users/black/OneDrive/Desktop/Pravah/gurukul-backend-/verify_gurukul_observability.py):
```bash
python verify_gurukul_observability.py
```
**Result**:
- SSPL-signed telemetry payload with `app: gurukul-backend` and `trace: gurukul-verify-<id>` was posted to Pravah's `/api/runtime` endpoint.
- Pravah Control Plane returned `200 OK`.
- Decision Brain resolved the trace and logged the decision in `/api/control-plane/history/gurukul-backend`.
- Observer Dashboard (`http://localhost:8600`) showed `gurukul-backend` service card with `healthy` status.

### Pravah Unified Logs
As seen in `api_server.log`:
- **`artha-backend`**: Telemetry resolved, Decision Brain decided `scale_down` (due to low CPU load).
- **`artha-fastapi`**: Telemetry resolved, Decision Brain evaluated overloading state.
- **`bhiv-integrator`**: Telemetry resolved, Decision Brain logged execution duration (1250.5ms).
- **`gurukul-backend`**: Telemetry resolved, Decision Brain observed Gurukul runtime state and latency. Observer polls `/health` every 10s — passive, read-only.

Pravah now has complete execution visibility across **four** independent systems!

> **Principle preserved**: Pravah observes—not owns—the execution of `gurukul-backend`. No middleware, no route, no startup hook was added to the Gurukul codebase. The only telemetry path is the existing `PravahAdapter` fire-and-forget async POST, plus the Observer's passive health probes.

---

## Production Infrastructure — Yotta Deployment Readiness

Pravah has been hardened for production deployment on **Yotta Bare-Metal VM** (Docker Compose + systemd). The following artifacts were created or modified to make the system production-ready.

### Deployment Architecture

| Service | Port | Role |
|---|---|---|
| Control Plane (Flask/Gunicorn) | 7000 | Agent API, decision endpoint, registry |
| Decision Brain (FastAPI/Uvicorn) | 8000 | Policy engine, telemetry ingestion |
| Observer (FastAPI/Uvicorn) | 8600 | Passive health probing of 20+ services |
| Redis (self-hosted container) | 6379 | Event bus (loopback-bound) |
| Prometheus | 9090 | Metrics scraper (loopback-bound) |

### New Artifacts

| File | Purpose |
|---|---|
| [yotta-deploy.yaml](file:///c:/Users/black/OneDrive/Desktop/Pravah/pravah-bhiv/yotta-deploy.yaml) | Yotta production Docker Compose manifest |
| [pravah.service](file:///c:/Users/black/OneDrive/Desktop/Pravah/pravah-bhiv/pravah.service) | systemd unit for Yotta VM lifecycle management |
| [PRODUCTION_DEPLOYMENT.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/pravah-bhiv/PRODUCTION_DEPLOYMENT.md) | Complete Yotta deployment guide |
| [scripts/start_prod_services.sh](file:///c:/Users/black/OneDrive/Desktop/Pravah/pravah-bhiv/backend/scripts/start_prod_services.sh) | Bash startup orchestrator (Linux) |
| [scripts/start_prod_services.ps1](file:///c:/Users/black/OneDrive/Desktop/Pravah/pravah-bhiv/backend/scripts/start_prod_services.ps1) | PowerShell startup orchestrator (Windows) |
| [scripts/validate_prod_health.py](file:///c:/Users/black/OneDrive/Desktop\Pravah\pravah-bhiv/backend/scripts/validate_prod_health.py) | Health validation script with JSON proof output |

### Modified Artifacts

| File | What Changed |
|---|---|
| [docker-compose.yml](file:///c:/Users/black/OneDrive/Desktop/Pravah/pravah-bhiv/backend/docker-compose.yml) | Added prod/staging profiles; Observer and Decision Brain as first-class services; log rotation; resource limits; Prometheus service |
| [environments/prod.env](file:///c:/Users/black/OneDrive/Desktop/Pravah/pravah-bhiv/backend/environments/prod.env) | Hardened: DEMO_MODE=false; 23 observed service URL stubs; SSPL/JWT secret markers; all service ports |
| [monitoring/prometheus.yml](file:///c:/Users/black/OneDrive/Desktop/Pravah/pravah-bhiv/backend/monitoring/prometheus.yml) | Fixed targets from `127.0.0.1` to Docker DNS names; added Decision Brain scrape job; alerting stub |

### Deployment Evidence

The primary production evidence artifact is:

```
backend/deployment_verification_packet/prod_runtime_health.json
```

This file documents infrastructure readiness at the **configuration layer** and will be updated with live endpoint PASS/FAIL verdicts after Yotta VM deployment by running:

```bash
python3 scripts/validate_prod_health.py --env prod \
  --output deployment_verification_packet/prod_runtime_health.json
```

### Environment Split

| Environment | Platform | Status |
|---|---|---|
| **Production** | Yotta Bare-Metal VM | Ready for deployment |
| **Staging** | Render.com | Active (render.yaml unchanged) |
| **Local Dev** | Docker Compose `dev` profile | Unchanged |

> **Principle maintained**: Render.com staging is preserved during Yotta migration. After successful production validation on Yotta, Render can be decommissioned at the operator's discretion.
