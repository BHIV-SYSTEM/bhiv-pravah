# Current System Architecture (As Implemented)

Date: 2026-03-19

This document reflects the architecture currently implemented in code.

## 1) Runtime Topology

- Flask Control Plane API: port 7000 by default
- FastAPI Decision Brain API: port 8000 by default
- Next.js Frontend: port 4500 by default
- Optional Redis event bus with in-process fallback

## 2) Component Map

Frontend:
- dashboard/frontend/app/page.tsx
- dashboard/frontend/app/decision-brain/page.tsx
- dashboard/frontend/services/api.ts

FastAPI backend:
- control_plane/backend/app/main.py
- control_plane/backend/app/decision_engine.py
- control_plane/backend/app/integration_bridge.py
- control_plane/backend/app/runtime_adapter.py

Flask control-plane API:
- control_plane/api/agent_api.py

Runtime and safety:
- agent_runtime.py
- control_plane/core/runtime_event_validator.py
- control_plane/core/runtime_rl_pipe.py
- control_plane/core/decision_arbitrator.py
- control_plane/core/action_governance.py
- control_plane/core/rl_orchestrator_safe.py

Multi-app:
- control_plane/multi_app_control_plane.py
- control_plane/app_override_manager.py

## 3) Main Flows

### A) Canonical Runtime Intake (Flask)

1. POST /api/runtime receives canonical payload.
2. Input validator + schema checks execute.
3. Payload is mapped into internal event envelope.
4. AgentRuntime runs one decision cycle.
5. Governance + safe orchestrator gates determine allow/refuse.
6. Results are logged and history is appended.

### B) Dashboard and Decision Flow (FastAPI)

1. Frontend polls /live-dashboard and metrics endpoints.
2. DecisionEngine returns deterministic action for test payloads.
3. Integration bridge reports control-plane integration status.
4. Autonomous background loop updates in-memory status snapshots.

### C) Manual Override Flow

1. Client calls /api/control-plane/override.
2. Override state is persisted to app_overrides.json.
3. Safe orchestrator enforces freeze before any non-noop action.

## 4) Safety and Governance

Gate order:
1. Manual freeze
2. Emergency freeze
3. Illegal action
4. Demo intake gate
5. Demo safety gate
6. Environment allowlist
7. Governance checks

Governance checks:
- Eligibility
- Cooldown
- Repetition suppression

## 5) Contracts and Validation

Canonical payload schema:
- runtime_payload_schema.json

Runtime validation:
- control_plane/core/runtime_event_validator.py
- control_plane/core/input_validator.py

## 6) Interfaces

Flask API:
- /api/health
- /api/status
- /api/runtime
- /api/control-plane/apps
- /api/control-plane/health
- /api/control-plane/history/<app_name>
- /api/control-plane/override

FastAPI API:
- /health
- /action-scope
- /decision
- /recent-activity
- /live-dashboard
- /decision-summary
- /decision-with-control-plane
- /control-plane/status
- /control-plane/apps
- /orchestration/metrics
- /autonomous-status
- /ingest-link
- /remove-link

## 7) Known Architectural Debt

- Duplicate API surfaces can cause confusion if ownership is not explicit.
- Some legacy docs/scripts still reference older backend paths and ports.
- Docker compose profile does not exactly match the current FastAPI + Next.js local topology.

## 8) Recommended Runtime Entry Commands

Flask:

```powershell
cd control_plane
$env:CONTROL_PLANE_PORT="7000"
..\.venv\Scripts\python.exe api\agent_api.py
```

FastAPI:

```powershell
cd control_plane
$env:BACKEND_PORT="8000"
..\.venv\Scripts\python.exe backend\run.py
```

Frontend:

```powershell
cd dashboard\frontend
npm run dev
```
