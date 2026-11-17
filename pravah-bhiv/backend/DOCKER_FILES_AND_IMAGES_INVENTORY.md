# 📊 Docker Files & Images - Complete Inventory

## 🐳 Docker Files (3 Total)

### 1. **Dockerfile**
- **Location:** `./backend/Dockerfile`
- **Purpose:** Production multi-stage build
- **Type:** Single Dockerfile for all services
- **Build Context:** `./backend`

### 2. **docker-compose.yml**
- **Location:** `./backend/docker-compose.yml`
- **Purpose:** Development (builds images locally)
- **Services:** 10 total
- **Builds From:** Dockerfile (locally)
- **Profiles:** dev, prod

### 3. **docker-compose.prod.yml**
- **Location:** `./backend/docker-compose.prod.yml`
- **Purpose:** Production (pulls from Docker Hub)
- **Services:** 10 total (same as dev)
- **Pulls From:** Docker Hub (no local build)
- **Profiles:** prod, staging
- **Image Tags:** Uses `${PRAVAH_IMAGE_TAG:-latest}` (SHA-based)

---

## 🎨 Docker Images Created (1 Total Built)

### Single Unified Image

**Image Name:** `docker.io/{DOCKER_HUB_USERNAME}/pravah`

**Tags Created by CI/CD:**
```
docker.io/username/pravah:4f7a8e5c     ← SHA tag (specific version)
docker.io/username/pravah:latest       ← Latest tag (always newest)
```

**Single Dockerfile Used:**
```
./backend/Dockerfile
  ├─ Stage 1: Builder (compile dependencies)
  └─ Stage 2: Runtime (final image ~500MB)
```

---

## 📋 How Services Use the Image

### Development (docker-compose.yml)

**10 Services = 10 Container INSTANCES from ONE Dockerfile:**

```yaml
services:
  redis:
    image: redis:7-alpine              ← External image (not our Dockerfile)
  
  control-plane:
    build: ./backend/Dockerfile        ← Builds locally
    image: pravah-control-plane:latest
    # Runs command: gunicorn wsgi:app
  
  decision-brain:
    build: ./backend/Dockerfile        ← Same Dockerfile
    image: pravah-decision-brain:latest
    # Runs command: uvicorn control_plane.backend.app.main:app
  
  observer:
    build: ./backend/Dockerfile        ← Same Dockerfile
    image: pravah-observer:latest
    # Runs command: uvicorn observer_server:app
  
  deploy-worker-1/2/3:
    build: ./backend/Dockerfile        ← Same Dockerfile
    image: pravah-worker:latest
    # Runs command: python -m control_plane.agents.multi_deploy_agent
  
  queue-monitor:
    build: ./backend/Dockerfile        ← Same Dockerfile
    image: pravah-monitor:latest
    # Runs command: python -m monitoring.queue_monitor
  
  health-monitor:
    build: ./backend/Dockerfile        ← Same Dockerfile
    image: pravah-monitor:latest
    # Runs command: python -m monitoring.infra_health_monitor
  
  prometheus:
    image: prom/prometheus:v2.54.1     ← External image
```

---

### Production (docker-compose.prod.yml)

**10 Services = 10 Container INSTANCES from ONE Docker Hub Image:**

```yaml
services:
  redis:
    image: redis:7-alpine              ← External image

  control-plane:
    image: docker.io/username/pravah:${PRAVAH_IMAGE_TAG:-latest}
    # Runs: gunicorn wsgi:app
  
  decision-brain:
    image: docker.io/username/pravah:${PRAVAH_IMAGE_TAG:-latest}
    # Runs: uvicorn control_plane.backend.app.main:app
  
  observer:
    image: docker.io/username/pravah:${PRAVAH_IMAGE_TAG:-latest}
    # Runs: uvicorn observer_server:app
  
  deploy-worker-1/2/3:
    image: docker.io/username/pravah:${PRAVAH_IMAGE_TAG:-latest}
    # Runs: python -m control_plane.agents.multi_deploy_agent
  
  queue-monitor:
    image: docker.io/username/pravah:${PRAVAH_IMAGE_TAG:-latest}
    # Runs: python -m monitoring.queue_monitor
  
  health-monitor:
    image: docker.io/username/pravah:${PRAVAH_IMAGE_TAG:-latest}
    # Runs: python -m monitoring.infra_health_monitor
  
  prometheus:
    image: prom/prometheus:v2.54.1     ← External image
```

---

## 🔍 Image Breakdown

### Custom Images Built (1)

```
FROM python:3.11-slim (base image from Docker Hub)
├─ Stage 1: Builder
│  └─ Installs all dependencies
│
└─ Stage 2: Runtime (final image)
   ├─ Copies code
   ├─ Copies virtual environment
   ├─ Creates non-root user
   └─ Final size: ~500MB
   
Result: docker.io/username/pravah:latest (ONE IMAGE)
```

### External Images Used (2)

```
1. redis:7-alpine
   - Used by: redis service
   - Size: ~13MB

2. prom/prometheus:v2.54.1
   - Used by: prometheus service
   - Size: ~200MB
```

---

## 📊 Service Count vs Image Count

```
docker-compose.yml:
├─ Services: 10 containers defined
├─ Custom images: 1 (built locally)
├─ External images: 2 (redis, prometheus)
└─ Containers running: 10 instances

docker-compose.prod.yml:
├─ Services: 10 containers defined
├─ Custom images: 1 (pulled from Docker Hub)
├─ External images: 2 (redis, prometheus)
└─ Containers running: 10 instances
```

---

## 🎯 Service to Image Mapping

### 7 Services Use the SAME Custom Image

```
Our Dockerfile builds ONE image:
docker.io/username/pravah:latest

This image is used by 7 services:
1. control-plane      → runs: gunicorn wsgi:app
2. decision-brain     → runs: uvicorn control_plane.backend.app.main:app
3. observer           → runs: uvicorn observer_server:app
4. deploy-worker-1    → runs: python -m control_plane.agents.multi_deploy_agent
5. deploy-worker-2    → runs: python -m control_plane.agents.multi_deploy_agent
6. deploy-worker-3    → runs: python -m control_plane.agents.multi_deploy_agent
7. queue-monitor      → runs: python -m monitoring.queue_monitor
8. health-monitor     → runs: python -m monitoring.infra_health_monitor

(Uses different COMMANDS to start different services)
```

### 2 Services Use EXTERNAL Images

```
redis:7-alpine
  └─ Service: redis (event bus)

prom/prometheus:v2.54.1
  └─ Service: prometheus (metrics)
```

---

## 💾 Image Sizes

```
Custom Pravah Image:
  docker.io/username/pravah:latest
  Size: ~500MB (multi-stage optimized)
  Build time: 5-10 minutes (local) / 1-2 minutes (CI/CD)

External Images:
  redis:7-alpine: ~13MB
  prometheus:v2.54.1: ~200MB
```

---

## 🔄 Build & Deploy Flow

### Development (Local Builds)

```
1. docker-compose.yml reads Dockerfile
2. docker compose build
   └─ Builds: docker.io/username/pravah:latest (LOCAL)
3. docker compose up -d
   └─ Creates 10 containers from local image + external images
```

### Production (Docker Hub Pulls)

```
1. docker-compose.prod.yml references Docker Hub
2. GitHub Actions builds once:
   └─ Builds: docker.io/username/pravah:4f7a8e5c (SHA)
   └─ Pushes: docker.io/username/pravah:latest
3. docker compose pull
   └─ Pulls: docker.io/username/pravah:${PRAVAH_IMAGE_TAG}
4. docker compose up -d
   └─ Creates 10 containers from pulled image + external images
```

---

## 📋 Summary Table

| Item | Count | Details |
|------|-------|---------|
| **Dockerfile Files** | 1 | `./backend/Dockerfile` |
| **docker-compose Files** | 2 | `docker-compose.yml` (dev) + `docker-compose.prod.yml` (prod) |
| **Custom Docker Images Built** | 1 | `docker.io/username/pravah` (used by 8 services) |
| **External Docker Images Used** | 2 | redis:7-alpine, prometheus:v2.54.1 |
| **Total Containers Running** | 10 | Same across dev and prod |
| **Services per Container** | 1 | Each container runs one service |

---

## 🎨 Architecture Diagram

```
Dockerfile (1 file)
    │
    ├─ Docker Build → Image: pravah:latest (1 image built)
    │
    ├─ Development Path:
    │  └─ docker-compose.yml (builds locally)
    │     └─ Creates 10 containers:
    │        ├─ redis (external image)
    │        ├─ control-plane (pravah image)
    │        ├─ decision-brain (pravah image)
    │        ├─ observer (pravah image)
    │        ├─ deploy-worker-1/2/3 (pravah image)
    │        ├─ queue-monitor (pravah image)
    │        ├─ health-monitor (pravah image)
    │        └─ prometheus (external image)
    │
    └─ Production Path:
       └─ docker-compose.prod.yml (pulls from Docker Hub)
          └─ Creates 10 containers:
             ├─ redis (external image)
             ├─ control-plane (pravah image from Hub)
             ├─ decision-brain (pravah image from Hub)
             ├─ observer (pravah image from Hub)
             ├─ deploy-worker-1/2/3 (pravah image from Hub)
             ├─ queue-monitor (pravah image from Hub)
             ├─ health-monitor (pravah image from Hub)
             └─ prometheus (external image)
```

---

## 🔑 Key Points

### ✅ ONE Dockerfile
- Single `./backend/Dockerfile` defines the image
- Multi-stage build (builder + runtime)
- Final image size: ~500MB

### ✅ ONE Custom Image
- `docker.io/username/pravah:latest`
- Used by 8 out of 10 services
- Different `COMMAND` per service container

### ✅ TWO docker-compose Files
- `docker-compose.yml` - Builds image locally (development)
- `docker-compose.prod.yml` - Pulls image from Docker Hub (production)

### ✅ TEN Containers
- Same 10 services in both dev and prod
- Same image used by 8 of them
- 2 external images (redis, prometheus)

### ✅ SHA Tags Strategy
- CI/CD generates SHA tag: `4f7a8e5c`
- Pushes: `docker.io/username/pravah:4f7a8e5c` (specific version)
- Pushes: `docker.io/username/pravah:latest` (always newest)
- Production deploys use SHA tag for reliable rollback

---

## 📈 Statistics

```
Docker Files:        1 Dockerfile + 2 docker-compose files = 3 files
Docker Images:       1 custom image + 2 external images = 3 images
Containers:          10 running containers
Services:            10 services
Shared Image Usage:  8 out of 10 services use the same image
```

---

## ✅ Conclusion

Your setup uses:
- **1 Dockerfile** to define the application image
- **1 Custom Image** (used by 8 services with different commands)
- **2 External Images** (redis, prometheus)
- **2 docker-compose files** (one for dev builds, one for prod pulls)
- **10 Containers** (same services in both environments)
- **SHA Tags** (for version tracking and reliable rollback)

**Result:** Efficient, scalable, production-ready setup! ✅

---

**Created:** August 2026  
**Updated:** Complete inventory  
**Status:** Production Ready
