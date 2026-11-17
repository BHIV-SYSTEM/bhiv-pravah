# 🚀 Quick Usage Guide - Two Docker Compose Files

## 📋 TL;DR

You have two files:

| File | Use Case | Run With |
|------|----------|----------|
| `docker-compose.yml` | Local development, builds images | `docker compose up` |
| `docker-compose.prod.yml` | Production VM, pulls from Docker Hub | `docker compose -f docker-compose.prod.yml up` |

---

## 🔧 Development Setup

### Local Development

```bash
# Navigate to backend
cd ./backend

# Build images
docker compose build

# Start services
docker compose up -d --profile dev

# Check status
docker compose ps

# View logs
docker compose logs -f control-plane

# Stop
docker compose down
```

### Key Features
- ✅ Builds images locally from ./backend/Dockerfile
- ✅ Code mounted as volumes (hot reload)
- ✅ FastAPI --reload enabled
- ✅ Standard ports: 7000, 8000, 8600, 9090
- ✅ Perfect for development

---

## 🚀 Production Deployment

### On Production VM

```bash
# SSH into VM
ssh ubuntu@your-vm-ip

# Navigate to deploy directory
cd /opt/pravah

# Create environment file
cp .env.example .env
nano .env
# Set: DOCKER_HUB_USERNAME, DOCKER_REGISTRY

# Pull images from Docker Hub
docker compose -f docker-compose.prod.yml pull

# Start services
docker compose -f docker-compose.prod.yml --profile prod up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

### Key Features
- ✅ Pulls pre-built images from Docker Hub
- ✅ Remapped ports: 7001, 8001, 8602, 9091
- ✅ No code volumes (immutable containers)
- ✅ Systemd integration
- ✅ Production-ready

---

## 📊 Port Mapping Quick Reference

### Development (docker-compose.yml)
```
Control Plane:   http://localhost:7000/api/health
Decision Brain:  http://localhost:8000/health
Observer:        http://localhost:8600/health
Prometheus:      http://localhost:9090
Redis:           localhost:6379
```

### Production (docker-compose.prod.yml)
```
Control Plane:   http://vm-ip:7001/api/health
Decision Brain:  http://vm-ip:8001/health
Observer:        http://vm-ip:8602/health
Prometheus:      http://vm-ip:9091
Redis:           vm-ip:6380
```

---

## 🔄 Common Commands

### For Development

```bash
# Start all dev services
docker compose up -d --profile dev

# Build specific service
docker compose build control-plane

# Rebuild all (no cache)
docker compose build --no-cache

# Follow logs live
docker compose logs -f

# Stop and remove volumes
docker compose down -v

# Just stop (keep volumes)
docker compose down

# Restart specific service
docker compose restart decision-brain

# Execute command in service
docker compose exec control-plane python --version
```

### For Production

```bash
# Pull latest images
docker compose -f docker-compose.prod.yml pull

# Start services
docker compose -f docker-compose.prod.yml --profile prod up -d

# Check services
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f control-plane

# Stop services
docker compose -f docker-compose.prod.yml down

# Test Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli ping

# Restart all
docker compose -f docker-compose.prod.yml restart
```

---

## 🎯 When to Use Which File

### Use `docker-compose.yml` When:
- ✅ Developing locally
- ✅ Making code changes
- ✅ Testing new features
- ✅ Building Docker images
- ✅ Running CI/CD tests

### Use `docker-compose.prod.yml` When:
- ✅ Deploying to production VM
- ✅ Running staging environment
- ✅ Using pre-built images
- ✅ Need remapped ports
- ✅ Avoiding port conflicts

---

## 🔐 .env Files

### Development
```bash
# .env for docker-compose.yml
ENVIRONMENT=dev
REDIS_PORT=6379
CONTROL_PLANE_PORT=7000
DECISION_BRAIN_PORT=8000
OBSERVER_PORT=8600
PROMETHEUS_PORT=9090
```

### Production
```bash
# .env for docker-compose.prod.yml
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

## ✅ Verification

### Development Verification
```bash
# Should show all services building/running
docker compose ps

# Expected output:
# NAME               STATUS
# pravah-redis       Up (healthy)
# pravah-control-plane  Up
# pravah-decision-brain   Up
# ...
```

### Production Verification
```bash
# Should show images pulled and running
docker compose -f docker-compose.prod.yml ps

# Should respond to ping
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
# Expected: PONG
```

---

## 🚨 Troubleshooting

### Images not building (Development)
```bash
# Rebuild with verbose output
docker compose build --no-cache --verbose

# Check Dockerfile
cat ./backend/Dockerfile
```

### Images not pulling (Production)
```bash
# Verify Docker Hub credentials
docker login

# Check DOCKER_HUB_USERNAME in .env
cat .env | grep DOCKER_HUB

# Try pulling manually
docker pull docker.io/username/pravah:latest
```

### Port conflicts
```bash
# Check which ports are in use
sudo lsof -i :7000
sudo lsof -i :7001

# Use different ports in .env
CONTROL_PLANE_PORT=7002
```

### Services not starting
```bash
# View full logs
docker compose logs -f

# Check service health
docker compose ps

# Restart Docker daemon
docker restart
```

---

## 📊 File Differences Summary

```
Development (docker-compose.yml):
├─ Builds: YES (builds locally)
├─ Ports: 7000, 8000, 8600, 9090
├─ Code volumes: YES (./backend:/app)
├─ Hot reload: YES (--reload enabled)
└─ Use: Local development

Production (docker-compose.prod.yml):
├─ Builds: NO (pulls from Docker Hub)
├─ Ports: 7001, 8001, 8602, 9091
├─ Code volumes: NO (immutable)
├─ Hot reload: NO
└─ Use: Production deployment
```

---

## 🎓 Complete Workflow Example

### Day 1: Development
```bash
# Navigate to backend
cd ./backend

# Build images
docker compose build

# Start services
docker compose up -d --profile dev

# Make changes
nano control_plane.py

# Changes auto-reload
# Test at http://localhost:7000

# Stop when done
docker compose down
```

### Day 2: Commit & Deploy
```bash
# Commit changes
git add .
git commit -m "feature: update control plane"
git push origin main

# GitHub Actions triggers:
# 1. Builds image (docker-compose.yml)
# 2. Pushes to Docker Hub
# 3. Deploys to VM (docker-compose.prod.yml)

# On VM, services automatically:
# 1. Pull latest image
# 2. Stop old containers
# 3. Start new containers
# 4. Health checks verify
```

---

## 🎯 Summary

**One file for development, one for production.**

- **docker-compose.yml** = Local builds, dev-friendly, hot reload
- **docker-compose.prod.yml** = Docker Hub pulls, prod-ready, remapped ports

Choose the right one for your workflow! 🚀

---

**Quick Links:**
- Full guide: `DOCKER_COMPOSE_GUIDE.md`
- Development: `docker compose up -d`
- Production: `docker compose -f docker-compose.prod.yml up -d`
