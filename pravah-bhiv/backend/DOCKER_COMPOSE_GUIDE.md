# 📋 Docker Compose - Development vs Production

## Overview

You now have **TWO docker-compose files**:

1. **docker-compose.yml** - Development (builds from code)
2. **docker-compose.prod.yml** - Production (pulls from Docker Hub)

---

## 🔄 Comparison

### docker-compose.yml (Development)

**Purpose:** Local development, testing, building images locally

**How it works:**
```yaml
services:
  control-plane:
    build:
      context: ./backend
      dockerfile: Dockerfile
    image: pravah-control-plane:latest
    # Builds image locally from ./backend/Dockerfile
```

**Characteristics:**
- ✅ Builds images locally
- ✅ Code volumes mounted (hot reload)
- ✅ Uses `--reload` flag in FastAPI
- ✅ Dev-friendly settings
- ✅ Standard ports (7000, 8000, 8600, 9090)
- ✅ Default profiles: dev, prod
- ✅ Faster iteration for development

**Volumes:**
```yaml
volumes:
  - ./backend/logs:/app/logs
  - ./backend/data:/app/data
  - ./backend:/app  # Code mounting
```

**Use Cases:**
- Local development
- Testing new features
- CI/CD testing
- Building Docker images

---

### docker-compose.prod.yml (Production)

**Purpose:** Production deployment on VM, uses pre-built images

**How it works:**
```yaml
services:
  control-plane:
    image: ${DOCKER_REGISTRY:-docker.io}/${DOCKER_HUB_USERNAME}/pravah:latest
    # Pulls image from Docker Hub
```

**Characteristics:**
- ✅ Pulls pre-built images from Docker Hub
- ✅ Remapped ports (7001, 8001, 8602, 9091)
- ✅ No code volumes (immutable images)
- ✅ Prod-ready settings
- ✅ Avoids port conflicts on VM
- ✅ Profiles: prod, staging
- ✅ Fast deployment

**Volumes:**
```yaml
volumes:
  - ./logs:/app/logs       # Host logs directory
  - ./data:/app/data       # Host data directory
  # NO code volumes
```

**Use Cases:**
- Production deployment
- Staging environment
- VM-based deployments
- Using pre-built images

---

## 📊 Detailed Comparison

| Feature | Development | Production |
|---------|-------------|-----------|
| **Images** | Build locally | Pull from Docker Hub |
| **File** | docker-compose.yml | docker-compose.prod.yml |
| **Build** | `build:` section | `image:` section |
| **Context** | ./backend | docker.io/username/pravah:latest |
| **Port Mapping** | 7000, 8000, 8600, 9090 | 7001, 8001, 8602, 9091 |
| **Code Volumes** | Yes (./backend:/app) | No |
| **Hot Reload** | Yes (uvicorn --reload) | No |
| **Fast API Reload** | Yes | No |
| **Network Name** | pravah-dev-network | pravah-production-network |
| **Build Time** | 5-10 min | ~1 min (pull only) |
| **Profiles** | dev, prod | prod, staging |
| **Environment** | dev | prod |

---

## 🚀 Usage Examples

### Development - Build and Run Locally

```bash
# Start development services
docker compose up -d --profile dev

# Watch logs
docker compose logs -f

# Rebuild after code changes
docker compose down
docker compose up -d --build

# Stop
docker compose down
```

### Development - Test Production Image Locally

```bash
# Build the production image first
docker compose build

# Then use production compose with locally built image
docker compose -f docker-compose.prod.yml up -d --profile prod

# Access services
curl http://localhost:7001/api/health    # Note: prod ports!
```

### Production - Deploy on VM

```bash
# SSH into VM
ssh ubuntu@your-vm-ip

# Navigate to deploy directory
cd /opt/pravah

# Create .env file
cp .env.example .env
nano .env  # Set DOCKER_HUB_USERNAME and other vars

# Deploy using production compose
docker compose -f docker-compose.prod.yml pull

docker compose -f docker-compose.prod.yml --profile prod up -d

# Verify
docker compose -f docker-compose.prod.yml ps
```

---

## 🔧 Configuration

### Development (.env)

```bash
ENVIRONMENT=dev
REDIS_PORT=6379
CONTROL_PLANE_PORT=7000
DECISION_BRAIN_PORT=8000
OBSERVER_PORT=8600
PROMETHEUS_PORT=9090
```

### Production (.env)

```bash
ENVIRONMENT=prod
REDIS_PORT=6380
CONTROL_PLANE_PORT=7001
DECISION_BRAIN_PORT=8001
OBSERVER_PORT=8602
PROMETHEUS_PORT=9091
DOCKER_HUB_USERNAME=your-username
DOCKER_REGISTRY=docker.io
```

---

## 📋 File Structure

```
backend/
├─ docker-compose.yml           (Development - builds locally)
├─ docker-compose.prod.yml      (Production - pulls from Docker Hub)
├─ Dockerfile                   (Used by docker-compose.yml)
├─ .env.example                (Template for environment variables)
└─ .github/workflows/ci.yml     (Uses docker-compose.prod.yml)
```

---

## 🔑 Key Differences - Side by Side

### Building Images

**Development (docker-compose.yml):**
```yaml
control-plane:
  build:
    context: ./backend
    dockerfile: Dockerfile
  image: pravah-control-plane:latest
```
→ Builds locally every time

**Production (docker-compose.prod.yml):**
```yaml
control-plane:
  image: docker.io/username/pravah:latest
```
→ Pulls pre-built image

### Port Mappings

**Development:**
```yaml
ports:
  - "${CONTROL_PLANE_PORT:-7000}:7000"    # 7000
  - "${DECISION_BRAIN_PORT:-8000}:8000"   # 8000
  - "${OBSERVER_PORT:-8600}:8600"         # 8600
  - "${PROMETHEUS_PORT:-9090}:9090"       # 9090
```

**Production:**
```yaml
ports:
  - "${CONTROL_PLANE_PORT:-7001}:7000"    # 7001 (avoid conflicts)
  - "${DECISION_BRAIN_PORT:-8001}:8000"   # 8001 (avoid conflicts)
  - "${OBSERVER_PORT:-8602}:8600"         # 8602 (avoid conflicts)
  - "${PROMETHEUS_PORT:-9091}:9090"       # 9091 (avoid conflicts)
```

### Code Volumes

**Development (hot reload):**
```yaml
volumes:
  - ./backend/logs:/app/logs
  - ./backend/data:/app/data
  - ./backend:/app  ← Code mounting for live edits
```

**Production (immutable):**
```yaml
volumes:
  - ./logs:/app/logs
  - ./data:/app/data
  # No code mounting - image is immutable
```

---

## 🔄 Workflow

### Local Development

```
Edit Code
    ↓
docker compose up
    ↓
Services reload automatically (--reload)
    ↓
Test changes
    ↓
Commit code
```

### Push to Production

```
git push origin main
    ↓
GitHub Actions triggers
    ├─ Lint code
    ├─ Test code
    ├─ Build Docker image (uses docker-compose.yml)
    ├─ Push to Docker Hub
    └─ Deploy (uses docker-compose.prod.yml)
       ├─ Pull images from Docker Hub
       ├─ Start services
       └─ Verify health checks
```

---

## 🛠️ Commands Reference

### Development

```bash
# Start development
docker compose up -d --profile dev

# Build images locally
docker compose build

# Rebuild with no cache
docker compose build --no-cache

# See logs
docker compose logs -f

# Stop
docker compose down

# Remove all data
docker compose down -v
```

### Production

```bash
# Pull latest images
docker compose -f docker-compose.prod.yml pull

# Start services
docker compose -f docker-compose.prod.yml --profile prod up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop
docker compose -f docker-compose.prod.yml down

# Health check
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
```

---

## 📊 Performance

| Metric | Dev | Prod |
|--------|-----|------|
| First Start | 5-10 min | 1-2 min |
| Subsequent Starts | 2-5 min | 30 sec |
| Image Build | Included | Pre-built |
| Deployment | ~10 min | ~5 min |
| Code Changes | Instant (reload) | Requires redeploy |

---

## 🔒 Security

### Development
- Code exposed in container
- Hot reload enabled
- Debug settings enabled
- Local only

### Production
- Code NOT in container (immutable)
- No hot reload
- Prod settings
- Firewall rules
- Secrets from environment variables

---

## ✅ Checklist

### For Development

- [ ] Use `docker-compose.yml`
- [ ] Run `docker compose build` after code changes
- [ ] Services reload automatically (FastAPI --reload)
- [ ] Access on standard ports (7000, 8000, 8600, 9090)
- [ ] Stop with `docker compose down`

### For Production

- [ ] Use `docker-compose.prod.yml`
- [ ] Ensure Docker images pushed to Docker Hub first
- [ ] Set DOCKER_HUB_USERNAME in .env
- [ ] Run `docker compose -f docker-compose.prod.yml pull` first
- [ ] Access on remapped ports (7001, 8001, 8602, 9091)
- [ ] Use systemd for auto-start
- [ ] Monitor with `docker compose logs -f`

---

## 🚀 CI/CD Integration

The GitHub Actions workflow:

1. **Build Phase** (uses `docker-compose.yml`)
   - Lint code
   - Run tests
   - Build Docker image locally

2. **Push Phase**
   - Push image to Docker Hub

3. **Deploy Phase** (uses `docker-compose.prod.yml`)
   - Pull images from Docker Hub
   - Start services via SSH

---

## 📝 Summary

**docker-compose.yml** = Development-focused, builds locally, hot reload
**docker-compose.prod.yml** = Production-focused, pulls from Docker Hub, remapped ports

Use the right file for the right environment! 🎯

---

**Created:** August 2026
**Version:** 2.0
**Status:** Ready for Development & Production
