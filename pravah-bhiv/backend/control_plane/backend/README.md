# Pravah Decision Brain Backend (FastAPI)

This module provides the FastAPI backend consumed by the dashboard frontend.

## Location

- App entry: control_plane/backend/app/main.py
- Runner: control_plane/backend/run.py

## Principles

- Stateless API process state (recent decisions and links are in-memory)
- Deterministic decision behavior
- Environment-aware action constraints
- No direct production side effects from decision endpoints

## Stack

- Python 3.10+
- FastAPI
- Uvicorn
- Pydantic

## Endpoints

Core:
- GET /health
- GET /action-scope
- POST /decision
- GET /recent-activity
- GET /decision-summary

Dashboard:
- GET /
- GET /live-dashboard
- GET /dashboard/state

Control-plane integration:
- GET /control-plane/status
- GET /control-plane/apps
- GET /orchestration/metrics
- POST /decision-with-control-plane

Runtime/autonomous visibility:
- GET /autonomous-status
- GET /test/runtime-cycle
- GET /orchestration/runtime-cycle

Link monitoring:
- POST /ingest-link
- POST /remove-link

## Run Locally

From repository root:

```powershell
cd control_plane
$env:BACKEND_PORT="8000"
..\.venv\Scripts\python.exe backend\run.py
```

Health check:

- http://localhost:8000/health

## CORS

Configured in app/main.py using:

- BACKEND_CORS_ORIGINS
- BACKEND_CORS_ORIGIN_REGEX

Defaults include local frontend origins and Vercel domains.

## Integration Notes

The backend uses IntegrationBridge to expose control-plane status and metrics.

Integration is best-effort:
- If control-plane components are unavailable, backend endpoints degrade gracefully.
- In-memory recent activity remains available.
