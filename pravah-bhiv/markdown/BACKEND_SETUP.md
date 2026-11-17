# Backend Setup and Configuration

This repository currently contains two backend API surfaces under control_plane:

1. Flask Control Plane API (runtime intake and control-plane operations)
2. FastAPI Decision Brain API (dashboard and decision-brain endpoints)

Both are used in the codebase today and should be treated as complementary services.

## 1) Flask Control Plane API

Path:

- control_plane/api/agent_api.py

Default port:

- 7000 (CONTROL_PLANE_PORT, fallback PORT)

Key endpoints:

- GET /api/health
- GET /api/status
- POST /api/runtime
- GET /api/control-plane/apps
- GET /api/control-plane/health
- GET /api/control-plane/history/<app_name>
- POST /api/control-plane/override

Run locally:

```powershell
cd control_plane
$env:ENVIRONMENT="dev"
$env:CONTROL_PLANE_PORT="7000"
..\.venv\Scripts\python.exe api\agent_api.py
```

## 2) FastAPI Decision Brain API

Paths:

- control_plane/backend/app/main.py
- control_plane/backend/run.py

Default port:

- 8000 (BACKEND_PORT, fallback PORT)

Key endpoints:

- GET /health
- GET /action-scope
- POST /decision
- GET /recent-activity
- GET /live-dashboard
- GET /decision-summary
- POST /decision-with-control-plane
- GET /control-plane/status
- GET /control-plane/apps
- GET /orchestration/metrics
- GET /autonomous-status
- POST /ingest-link
- POST /remove-link

Run locally:

```powershell
cd control_plane
$env:BACKEND_PORT="8000"
..\.venv\Scripts\python.exe backend\run.py
```

## 3) Frontend Integration

Frontend path:

- dashboard/frontend

Default frontend port from package script:

- 4500

Recommended .env.local values:

```env
NEXT_PUBLIC_BACKEND_PORT=8000
NEXT_PUBLIC_DECISION_BRAIN_API_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_CONTROL_PLANE_URL=http://localhost:7000
```

## 4) CORS

FastAPI CORS is configured in:

- control_plane/backend/app/main.py

Variables:

- BACKEND_CORS_ORIGINS
- BACKEND_CORS_ORIGIN_REGEX

## 5) Production (Render)

render.yaml defines backend startup as:

- uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT

When deploying only FastAPI + frontend, this is sufficient. If Flask runtime intake is also needed in production, deploy Flask as a separate service.

## 6) Troubleshooting

Cannot connect to FastAPI:

1. Verify http://localhost:8000/health returns 200.
2. Check dashboard/frontend/.env.local values.
3. Restart frontend after env changes.

Cannot connect to Flask:

1. Verify http://localhost:7000/api/health returns 200.
2. Confirm CONTROL_PLANE_PORT and ENVIRONMENT are set.

Port already in use:

```powershell
netstat -ano | findstr ":7000"
netstat -ano | findstr ":8000"
taskkill /PID <PID> /F
```
