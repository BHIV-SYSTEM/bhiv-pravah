# 🔄 DOCKER COMPOSE FILES - SIDE BY SIDE COMPARISON

## File Overview

```
┌─────────────────────────────────┬─────────────────────────────────┐
│   docker-compose.yml            │   docker-compose.prod.yml       │
│   (DEVELOPMENT)                 │   (PRODUCTION)                  │
├─────────────────────────────────┼─────────────────────────────────┤
│ • Builds images locally          │ • Pulls from Docker Hub         │
│ • Code mounted (hot reload)      │ • No code volumes              │
│ • Standard ports                 │ • Remapped ports               │
│ • 2-5 min startup time          │ • 30-60 sec startup time       │
│ • Development profiles           │ • Production profiles           │
│ • Perfect for local dev          │ • Perfect for VM deployment    │
└─────────────────────────────────┴─────────────────────────────────┘
```

---

## Configuration Comparison

### Service Definition

```
DEVELOPMENT (docker-compose.yml):
┌─────────────────────────────────────────────────────────┐
│ control-plane:                                          │
│   build:                                                │
│     context: ./backend              ← Builds locally    │
│     dockerfile: Dockerfile                              │
│   image: pravah-control-plane:latest                    │
│   ports:                                                │
│     - "7000:7000"                   ← Standard port     │
│   volumes:                                              │
│     - ./backend/logs:/app/logs                          │
│     - ./backend/data:/app/data                          │
│     - ./backend:/app                ← Code mounting!    │
│   command: uvicorn ... --reload     ← Hot reload!       │
└─────────────────────────────────────────────────────────┘

PRODUCTION (docker-compose.prod.yml):
┌─────────────────────────────────────────────────────────┐
│ control-plane:                                          │
│   image: docker.io/username/pravah:latest              │
│                                     ← Pulls from Hub!   │
│   ports:                                                │
│     - "7001:7000"                   ← Remapped port     │
│   volumes:                                              │
│     - ./logs:/app/logs              ← Only data volumes │
│     - ./data:/app/data                                  │
│   command: gunicorn wsgi:app        ← Production mode   │
└─────────────────────────────────────────────────────────┘
```

---

## Port Mapping Visual

```
DEVELOPMENT (docker-compose.yml):
┌─────────────────────────────────────────────────────────┐
│ Your Local Machine (localhost)                          │
├─────────────────────────────────────────────────────────┤
│ 7000  → Control Plane  (Flask)                          │
│ 8000  → Decision Brain (FastAPI)                        │
│ 8600  → Observer       (FastAPI)                        │
│ 9090  → Prometheus     (Metrics)                        │
│ 6379  → Redis          (Cache)                          │
│                                                         │
│ Usage: http://localhost:7000                            │
└─────────────────────────────────────────────────────────┘

PRODUCTION (docker-compose.prod.yml):
┌─────────────────────────────────────────────────────────┐
│ Production VM (203.0.113.45 example)                    │
├─────────────────────────────────────────────────────────┤
│ 7001  → Control Plane  (Flask)      [7000 internal]     │
│ 8001  → Decision Brain (FastAPI)    [8000 internal]     │
│ 8602  → Observer       (FastAPI)    [8600 internal]     │
│ 9091  → Prometheus     (Metrics)    [9090 internal]     │
│ 6380  → Redis          (Cache)      [6379 internal]     │
│                                                         │
│ Usage: http://203.0.113.45:7001                        │
│ (Avoids port conflicts on VM)                          │
└─────────────────────────────────────────────────────────┘
```

---

## Build vs Pull Process

```
DEVELOPMENT (Builds Images):
┌─────────────────────────────────────────────────────────┐
│ docker compose build                                    │
│    ↓                                                    │
│ Read: ./backend/Dockerfile                              │
│    ↓                                                    │
│ Stage 1: Build Python environment                      │
│    ├─ Install dependencies                              │
│    ├─ Create venv                                       │
│    └─ ~1.2GB intermediate image                         │
│    ↓                                                    │
│ Stage 2: Create runtime image                          │
│    ├─ Copy venv from builder                            │
│    ├─ Copy code                                         │
│    └─ ~500MB final image (local)                        │
│    ↓                                                    │
│ Result: pravah-control-plane:latest (LOCAL)            │
│         pravah-decision-brain:latest (LOCAL)           │
│         pravah-observer:latest (LOCAL)                 │
│                                                         │
│ Time: 5-10 minutes (first run)                         │
│       1-3 minutes (subsequent with cache)               │
└─────────────────────────────────────────────────────────┘

PRODUCTION (Pulls Images):
┌─────────────────────────────────────────────────────────┐
│ docker compose -f docker-compose.prod.yml pull         │
│    ↓                                                    │
│ Query Docker Hub: docker.io/username/pravah:latest     │
│    ↓                                                    │
│ Download: ~500MB image (already built)                 │
│    ↓                                                    │
│ Extract to local Docker daemon                         │
│    ↓                                                    │
│ Result: docker.io/username/pravah:latest (PULLED)      │
│                                                         │
│ Time: 1-2 minutes (depends on internet)                │
│       30 seconds (subsequent pulls)                     │
└─────────────────────────────────────────────────────────┘
```

---

## Volume Mounting

```
DEVELOPMENT (with Code):
┌──────────────────────────────────────────────────┐
│ Host Machine                Container              │
├──────────────────────────────────────────────────┤
│                                                  │
│ ./backend/               ←────→  /app            │
│   ├─ control_plane.py    mounted  (same code)   │
│   ├─ decision_brain/              (live edits)   │
│   └─ observer_server.py                          │
│                                                  │
│ When you edit control_plane.py:                  │
│   1. Save file on host                           │
│   2. FastAPI detects change                      │
│   3. Container auto-reloads                      │
│   4. No restart needed!                          │
│                                                  │
└──────────────────────────────────────────────────┘

PRODUCTION (No Code):
┌──────────────────────────────────────────────────┐
│ Host Machine                Container              │
├──────────────────────────────────────────────────┤
│                                                  │
│ ./logs/                  ←────→  /app/logs       │
│ ./data/                  ←────→  /app/data       │
│                          (readonly code)         │
│                                                  │
│ Code is INSIDE the image:                        │
│   - Not accessible from host                     │
│   - Not modifiable                               │
│   - Immutable (production-safe)                  │
│                                                  │
│ Only data/logs mounted:                          │
│   - Persistent across restarts                   │
│   - Accessible from host                         │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## Startup Time Comparison

```
DEVELOPMENT (docker-compose.yml):
Time ────────────────────────────────────────────────
  0s  → docker compose up
  1s  → Pull base images
  2s  → Start building
  3s  ├─ Install dependencies (apt-get, pip)
  5s  ├─ Compile dependencies
  7s  └─ Create runtime image
  8s  → Start containers
  9s  → Health checks
 10s  → Services ready
 ~~~~  ✓ READY (10 minutes for full build + cache)

PRODUCTION (docker-compose.prod.yml):
Time ────────────────────────────────────────────────
  0s  → docker compose pull
  1s  → Query Docker Hub
  5s  → Download image (~500MB)
 15s  → Extract layers
 20s  → docker compose up
 25s  → Start containers
 30s  → Health checks
 35s  → Services ready
 ~~~~  ✓ READY (1 minute total)
```

---

## Development vs Production Workflow

```
LOCAL DEVELOPMENT:
┌─────────────────────────────────────────────────────┐
│ 1. docker compose build                             │
│    (builds images locally)                          │
│    ↓                                                │
│ 2. docker compose up                                │
│    (starts containers with code volumes)            │
│    ↓                                                │
│ 3. Edit code: control_plane.py                     │
│    (changes auto-reload via --reload)               │
│    ↓                                                │
│ 4. Test changes: http://localhost:7000              │
│    (no restart needed!)                             │
│    ↓                                                │
│ 5. docker compose down                              │
│    (stop all containers)                            │
└─────────────────────────────────────────────────────┘

PRODUCTION DEPLOYMENT:
┌─────────────────────────────────────────────────────┐
│ 1. git push origin main                             │
│    (push code to GitHub)                            │
│    ↓                                                │
│ 2. GitHub Actions (uses docker-compose.yml)        │
│    ├─ Lint code                                     │
│    ├─ Run tests                                     │
│    ├─ docker compose build                          │
│    ├─ Push to Docker Hub                            │
│    └─ SSH to VM                                     │
│    ↓                                                │
│ 3. SSH Deploy (uses docker-compose.prod.yml)      │
│    ├─ docker compose pull                           │
│    ├─ docker compose down                           │
│    ├─ docker compose up                             │
│    └─ Health checks                                 │
│    ↓                                                │
│ 4. Services live at: http://vm-ip:7001             │
│    (new version deployed!)                          │
└─────────────────────────────────────────────────────┘
```

---

## Feature Comparison Matrix

```
┌─────────────────────┬──────────────────┬──────────────────┐
│ Feature             │ Development      │ Production       │
├─────────────────────┼──────────────────┼──────────────────┤
│ Builds locally      │ ✅ YES           │ ❌ NO            │
│ Image pull          │ ❌ NO            │ ✅ YES           │
│ Code volumes        │ ✅ YES           │ ❌ NO            │
│ Hot reload          │ ✅ YES           │ ❌ NO            │
│ Standard ports      │ ✅ 7000/8000     │ ❌ 7001/8001     │
│ Build time          │ 5-10 min         │ 1-2 min          │
│ Startup time        │ 2-5 min          │ 30-60 sec        │
│ Network name        │ pravah-dev-net   │ pravah-prod-net  │
│ Profile             │ dev, prod        │ prod, staging    │
│ Immutable           │ ❌ NO            │ ✅ YES           │
│ Security focus      │ ❌ Development   │ ✅ Production    │
│ Use case            │ Local dev        │ VM deployment    │
└─────────────────────┴──────────────────┴──────────────────┘
```

---

## Commands Side by Side

```
┌─────────────────────────────────┬─────────────────────────────────┐
│ DEVELOPMENT                     │ PRODUCTION                      │
├─────────────────────────────────┼─────────────────────────────────┤
│ docker compose build            │ docker compose -f docker-      │
│                                 │ compose.prod.yml pull          │
│                                 │                                 │
│ docker compose up -d            │ docker compose -f docker-      │
│ --profile dev                   │ compose.prod.yml up -d         │
│                                 │ --profile prod                  │
│                                 │                                 │
│ docker compose ps               │ docker compose -f docker-      │
│                                 │ compose.prod.yml ps            │
│                                 │                                 │
│ docker compose logs -f          │ docker compose -f docker-      │
│                                 │ compose.prod.yml logs -f       │
│                                 │                                 │
│ docker compose down             │ docker compose -f docker-      │
│                                 │ compose.prod.yml down          │
│                                 │                                 │
│ http://localhost:7000           │ http://vm-ip:7001              │
└─────────────────────────────────┴─────────────────────────────────┘
```

---

## Decision Tree

```
START
  │
  ├─ Are you developing locally?
  │  └─ YES → Use docker-compose.yml
  │     └─ docker compose up
  │     └─ Edit code → Auto-reload
  │
  ├─ Are you deploying to VM?
  │  └─ YES → Use docker-compose.prod.yml
  │     └─ docker compose -f docker-compose.prod.yml up
  │     └─ Pull images from Docker Hub
  │
  ├─ Do you need ports 7000/8000/8600?
  │  └─ YES → Use docker-compose.yml (dev)
  │  └─ NO → Use docker-compose.prod.yml (prod remapped)
  │
  └─ Need code hot-reload?
     └─ YES → Use docker-compose.yml
     └─ NO → Use docker-compose.prod.yml
```

---

## Summary Table

| Metric | Development | Production |
|--------|-------------|-----------|
| **File** | docker-compose.yml | docker-compose.prod.yml |
| **Build** | Local (5-10 min) | Docker Hub (1-2 min) |
| **Startup** | 2-5 minutes | 30-60 seconds |
| **Reload** | Auto (code changes) | Manual (redeploy) |
| **Ports** | 7000, 8000, 8600, 9090 | 7001, 8001, 8602, 9091 |
| **Code** | Mounted (editable) | Immutable (readonly) |
| **Network** | pravah-dev-network | pravah-production-network |
| **Use** | Local development | VM deployment |

---

**Choose the right file for your environment!** 🎯

Development = docker-compose.yml  
Production = docker-compose.prod.yml
