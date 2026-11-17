# 🚀 Production Docker Compose - Updated with SHA Tags

## Critical Update: SHA Tag Implementation

**Important:** The production docker-compose.yml now uses **SHA image tags** for proper rollback support.

---

## 📋 What Changed

### Before (❌ Broken Rollback)
```yaml
control-plane:
  image: docker.io/username/pravah:latest
```

**Problem:** Always pulls `latest`, so rollback redeploys the broken version!

### After (✅ Fixed Rollback)
```yaml
control-plane:
  image: docker.io/username/pravah:${PRAVAH_IMAGE_TAG:-latest}
```

**Solution:** Uses specific SHA tag, so rollback restores exact previous version!

---

## 🔑 How SHA Tags Work

### GitHub Actions Build Process

```bash
# 1. Extract first 8 characters of commit SHA
TAG=${GITHUB_SHA::8}
# Example: 4f7a8e5c

# 2. Push both tags to Docker Hub
docker push docker.io/username/pravah:4f7a8e5c  (SHA tag)
docker push docker.io/username/pravah:latest     (latest tag)

# 3. Pass SHA to deployment
export PRAVAH_IMAGE_TAG=4f7a8e5c
```

### Deployment Script

```bash
# 1. Save version for tracking
echo "$IMAGE_TAG" > /opt/pravah/current_version
# Output: 4f7a8e5c

# 2. Export variable
export PRAVAH_IMAGE_TAG=4f7a8e5c

# 3. Docker-compose uses the variable
docker compose pull
# Pulls: docker.io/username/pravah:4f7a8e5c (specific version)
```

### Rollback Script

```bash
# 1. Read previous version
PREVIOUS_TAG=$(cat /opt/pravah/previous_version)

# 2. Set variable to previous
export PRAVAH_IMAGE_TAG=$PREVIOUS_TAG

# 3. Docker-compose pulls previous version
docker compose pull
docker compose up -d
# Pulls: docker.io/username/pravah:$PREVIOUS_TAG (exact previous version)
# Result: ✅ Correct rollback!
```

---

## 🎯 Version Tracking on VM

### Files Created During Deployment

```
/opt/pravah/current_version    ← SHA of currently running version
/opt/pravah/previous_version   ← SHA of previous version (for rollback)
```

### Example Versions

```
Deployment 1: 4f7a8e5c
  current_version = 4f7a8e5c

Deployment 2: 3e6b7d2a
  previous_version = 4f7a8e5c (saved for rollback)
  current_version = 3e6b7d2a

Deployment 3: 2d5c6e1f (FAILS)
  Rollback reads: previous_version = 3e6b7d2a
  Restores exactly that version!
```

---

## 📊 Updated Environment Variables

### On Production VM

```bash
# .env file on VM
ENVIRONMENT=prod
REDIS_PORT=6380
CONTROL_PLANE_PORT=7001
DECISION_BRAIN_PORT=8001
OBSERVER_PORT=8602
PROMETHEUS_PORT=9091
DOCKER_HUB_USERNAME=your-username
DOCKER_REGISTRY=docker.io
PRAVAH_IMAGE_TAG=latest  # Set by CI/CD, defaults to latest
```

### Set by GitHub Actions During Deploy

```bash
# These are exported by the deploy script
export PRAVAH_IMAGE_TAG=4f7a8e5c
# docker-compose.yml uses this variable
```

---

## 🔄 Complete Deployment Flow

```
1. Developer pushes to main
   ↓
2. GitHub Actions Build
   ├─ Lint & Test
   ├─ Build Docker image
   ├─ Generate SHA tag: 4f7a8e5c (first 8 chars of commit)
   ├─ Push tags:
   │  ├─ docker.io/username/pravah:4f7a8e5c (SHA tag)
   │  └─ docker.io/username/pravah:latest (always updated)
   └─ Pass IMAGE_TAG=4f7a8e5c to Deploy
   ↓
3. GitHub Actions Deploy
   ├─ SSH into VM
   ├─ Create backup of current deployment
   ├─ Set: PRAVAH_IMAGE_TAG=4f7a8e5c
   ├─ Save: previous_version = (old value)
   ├─ Save: current_version = 4f7a8e5c
   ├─ docker compose pull → pulls :4f7a8e5c tag
   ├─ docker compose down
   ├─ docker compose up -d
   ├─ Health checks (Redis, Control Plane, Decision Brain, Observer)
   └─ ✅ Deployment complete with SHA: 4f7a8e5c
   ↓
4. If Health Checks Fail
   ├─ Rollback stage triggered
   ├─ SSH into VM
   ├─ Read: PREVIOUS_TAG=$(cat /opt/pravah/previous_version)
   ├─ Set: PRAVAH_IMAGE_TAG=$PREVIOUS_TAG
   ├─ docker compose pull → pulls previous :$PREVIOUS_TAG
   ├─ docker compose down
   ├─ docker compose up -d
   └─ ✅ Rolled back to previous SHA!
```

---

## 💡 Key Benefits

✅ **Precise Version Control** - Every deployment tracked by commit SHA
✅ **Reliable Rollback** - Rollback restores exact previous version, not broken new version
✅ **Version History** - Can see which SHA is currently running and which was previous
✅ **Manual Deployment** - Can deploy any specific SHA manually if needed
✅ **No "Latest" Confusion** - Know exactly which version is running

---

## 🚀 Manual Deployment with SHA Tags

### Deploy Specific SHA (if doing manual deployment)

```bash
# SSH into VM
ssh ubuntu@your-vm-ip
cd /opt/pravah

# Set the SHA version you want
export PRAVAH_IMAGE_TAG=4f7a8e5c

# Pull that version
docker compose -f docker-compose.prod.yml pull

# Start services
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --profile prod

# Verify
docker compose ps
```

### Manual Rollback to Previous Version

```bash
# Check what's the previous version
cat /opt/pravah/previous_version
# Output: 3e6b7d2a

# Set to previous
export PRAVAH_IMAGE_TAG=3e6b7d2a

# Pull and start previous version
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --profile prod

# Verify it's rolled back
docker compose ps
cat /opt/pravah/current_version  # Should now show previous version
```

---

## 🔍 Verify SHA Tags

### Check Current Version Running

```bash
# SSH into VM
ssh ubuntu@your-vm-ip

# Check version file
cat /opt/pravah/current_version
# Output: 4f7a8e5c

# Verify the container image matches
docker inspect pravah-control-plane | grep Image
# Output: "Image": "docker.io/username/pravah:4f7a8e5c"
```

### Check Docker Hub Tags

```bash
# List all available SHAs on Docker Hub
docker search username/pravah

# Or via Docker Hub UI:
# hub.docker.com/r/username/pravah
# Shows all SHA tags and latest tag
```

---

## 📝 Services Using SHA Tags

All 8 services in `docker-compose.prod.yml` now use the variable:

```yaml
image: ${DOCKER_REGISTRY:-docker.io}/${DOCKER_HUB_USERNAME}/pravah:${PRAVAH_IMAGE_TAG:-latest}
```

Applied to:
- ✅ control-plane
- ✅ decision-brain
- ✅ observer
- ✅ deploy-worker-1
- ✅ deploy-worker-2
- ✅ deploy-worker-3
- ✅ queue-monitor
- ✅ health-monitor

---

## ⚙️ How docker-compose.prod.yml Uses SHA Tags

```yaml
# This variable is set by GitHub Actions during deploy
# export PRAVAH_IMAGE_TAG=4f7a8e5c

services:
  control-plane:
    # This resolves to:
    # docker.io/username/pravah:4f7a8e5c
    # (pulls the EXACT SHA version)
    image: ${DOCKER_REGISTRY:-docker.io}/${DOCKER_HUB_USERNAME}/pravah:${PRAVAH_IMAGE_TAG:-latest}
```

---

## 🎓 Comparison Table

| Feature | Old (latest) | New (SHA tags) |
|---------|---|---|
| **Image Tag** | docker.io/user/pravah:latest | docker.io/user/pravah:4f7a8e5c |
| **Version Control** | ❌ No | ✅ Yes (commit SHA) |
| **Rollback Accuracy** | ❌ Redeploys failed version | ✅ Restores previous version |
| **Version Tracking** | ❌ Unknown what's running | ✅ Exact SHA known |
| **Manual Deploy** | ❌ Can't target specific version | ✅ Can deploy any SHA |
| **Fallback** | Latest always used | ✅ Latest as fallback |
| **Breaking Bad?** | ❌ Rollback broken | ✅ Rollback fixed! |

---

## ✅ Checklist

Before deploying to production:

- [ ] Read this entire document
- [ ] Understand SHA tag strategy
- [ ] Know how to check current version: `cat /opt/pravah/current_version`
- [ ] Understand rollback uses `previous_version` file
- [ ] Have tested GitHub Actions deployment once
- [ ] Confirmed SHA tags in Docker Hub

---

## 📚 Additional Resources

- **SHA_TAG_IMPLEMENTATION.md** - Detailed technical explanation
- **DOCKER_COMPOSE_COMPARISON.md** - Visual comparison of dev vs prod
- **ACTION_CHECKLIST.md** - Step-by-step deployment checklist
- **.github/workflows/ci.yml** - CI/CD pipeline with SHA tag generation

---

## 🎯 Summary

**The production docker-compose now uses SHA image tags instead of `latest`.** This means:

1. ✅ Each deployment uses exact commit SHA
2. ✅ Rollback restores previous SHA (not broken version)
3. ✅ Version tracking enabled on VM
4. ✅ Can deploy/rollback to any specific SHA
5. ✅ Deployment is now safe and auditable

**Status:** ✅ Production Ready with Proper Rollback Support

---

**Updated:** August 2026  
**Version:** 2.1 (SHA tags added)  
**Status:** Production Ready
