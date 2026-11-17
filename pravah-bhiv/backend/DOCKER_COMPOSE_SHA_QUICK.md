# 🚀 Docker Compose - SHA Tags Edition

## ⚡ Quick Reference

You have **two docker-compose files** with an important difference:

| File | Purpose | Image Tag |
|------|---------|-----------|
| `docker-compose.yml` | Development (local builds) | Built locally |
| `docker-compose.prod.yml` | Production (Docker Hub pulls) | `${PRAVAH_IMAGE_TAG}` (SHA-based) |

---

## 🔑 Critical: SHA Tag Implementation

### What It Does

```bash
# CI/CD generates SHA tag from commit
GITHUB_SHA = abc1234def567890

# Extracts first 8 chars
IMAGE_TAG = abc1234d

# Pushes both tags to Docker Hub
docker.io/username/pravah:abc1234d  (SHA tag - SPECIFIC VERSION)
docker.io/username/pravah:latest    (latest tag - ALWAYS NEWEST)

# During deploy, uses SPECIFIC SHA tag
docker compose pull  → pulls :abc1234d (NOT :latest!)
```

### Why It Matters

```
❌ OLD (Using latest):
   Deploy A (v1) → latest = v1
   Deploy B (v2) → latest = v2
   B fails, rollback → pulls latest = v2 (WRONG VERSION!)
   ❌ Rollback failed

✅ NEW (Using SHA):
   Deploy A (v1, SHA: abc123) → tag = abc123
   Deploy B (v2, SHA: def456) → tag = def456, previous = abc123
   B fails, rollback → pulls previous SHA = abc123 ✅
   ✅ Rollback works!
```

---

## 📋 On Production VM

### Version Files

```bash
# Current version running
cat /opt/pravah/current_version
# Output: abc1234d

# Previous version (for rollback)
cat /opt/pravah/previous_version
# Output: 8f9e7d6c
```

### Manual SHA Deploy

```bash
# Set specific SHA
export PRAVAH_IMAGE_TAG=abc1234d

# Pull that version
docker compose -f docker-compose.prod.yml pull

# Start it
docker compose -f docker-compose.prod.yml up -d --profile prod
```

### Manual SHA Rollback

```bash
# Get previous SHA
export PRAVAH_IMAGE_TAG=$(cat /opt/pravah/previous_version)

# Deploy previous version
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --profile prod
```

---

## 🚀 Deployment Flow

```
Push to main
    ↓
GitHub Actions Build
├─ Extract SHA: abc1234d
├─ Build image
├─ Push: :abc1234d and :latest
└─ Pass IMAGE_TAG=abc1234d to Deploy
    ↓
GitHub Actions Deploy
├─ export PRAVAH_IMAGE_TAG=abc1234d
├─ Save: current_version=abc1234d
├─ docker compose pull (pulls :abc1234d)
├─ docker compose up -d
└─ Health checks
    ↓
If Fails:
├─ Rollback reads: previous_version
├─ export PRAVAH_IMAGE_TAG=$previous_version
├─ docker compose pull (pulls :$previous_version)
└─ Restored to previous version ✅
```

---

## 🔄 Services Using SHA Tags

All these services use the SHA variable:

```yaml
image: ${DOCKER_REGISTRY}/${DOCKER_HUB_USERNAME}/pravah:${PRAVAH_IMAGE_TAG:-latest}
```

- ✅ control-plane
- ✅ decision-brain
- ✅ observer
- ✅ deploy-worker-1
- ✅ deploy-worker-2
- ✅ deploy-worker-3
- ✅ queue-monitor
- ✅ health-monitor

---

## 📊 Environment Variables

```bash
# On VM .env (Set by CI/CD during deploy)
PRAVAH_IMAGE_TAG=abc1234d    # SHA tag from GitHub Actions
DOCKER_HUB_USERNAME=username
DOCKER_REGISTRY=docker.io
```

---

## ✅ Verify SHA in Use

```bash
# Check current SHA
cat /opt/pravah/current_version

# Verify container uses that SHA
docker inspect pravah-control-plane | grep Image
# Should show: ...pravah:abc1234d

# Verify it matches
docker compose ps
```

---

## 🎯 Why SHA Tags Matter

1. **Exact Version Control** - Know exactly which commit is running
2. **Safe Rollback** - Rollback to previous commit, not broken version
3. **Audit Trail** - Full history of which SHAs were deployed
4. **Manual Deploy** - Can deploy any SHA manually
5. **No "Latest" Confusion** - Never accidentally deploy wrong version

---

## 📚 Full Documentation

- **SHA_TAG_IMPLEMENTATION.md** - Technical deep dive
- **DOCKER_COMPOSE_PROD_SHA.md** - Production guide with SHA tags
- **CI/CD Flow** - .github/workflows/ci.yml shows SHA generation

---

## 🔍 Key Files

| File | Uses SHA? | Location |
|------|-----------|----------|
| docker-compose.yml | ❌ Local | Local development |
| docker-compose.prod.yml | ✅ YES (${PRAVAH_IMAGE_TAG}) | Production on VM |
| ci.yml | ✅ YES (generates & passes SHA) | .github/workflows/ |

---

## ⚡ TL;DR

- **Development**: `docker compose up` (local builds)
- **Production**: SHA tags for reliable rollback
- **CI/CD**: Generates SHA (abc1234d), pushes both :abc1234d and :latest
- **Deploy**: Uses :abc1234d (specific version, not :latest)
- **Rollback**: Uses previous SHA from file (previous_version)
- **Result**: ✅ Rollback always works!

---

**Status:** ✅ SHA Tags Implemented  
**Rollback:** ✅ Fixed & Reliable  
**Ready:** ✅ Production Ready
