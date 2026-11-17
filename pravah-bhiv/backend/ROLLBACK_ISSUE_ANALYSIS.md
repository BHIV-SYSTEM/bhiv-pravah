# 🔍 ROLLBACK ISSUE ANALYSIS

## ❌ Current Rollback Problem

The rollback job has an issue: it pulls the previous image tag correctly BUT doesn't export the `PRAVAH_IMAGE_TAG` environment variable to docker-compose.

### Current Rollback Script
```bash
PREVIOUS_TAG=$(cat "$DEPLOY_DIR/previous_version")

echo "Rolling back to $PREVIOUS_TAG"

docker pull docker.io/${{ secrets.DOCKER_HUB_USERNAME }}/pravah:$PREVIOUS_TAG

docker compose down

docker compose up -d  # ❌ PROBLEM: PRAVAH_IMAGE_TAG not set!

docker compose ps

echo "Rollback completed."
```

### What Happens

1. ✅ Reads `previous_version` file correctly (e.g., `4f7a8e5c`)
2. ✅ Pulls the correct image from Docker Hub: `:4f7a8e5c`
3. ❌ **BUT** doesn't export `PRAVAH_IMAGE_TAG=4f7a8e5c`
4. ❌ docker-compose.prod.yml uses `${PRAVAH_IMAGE_TAG:-latest}`
5. ❌ Falls back to `:latest` tag instead of `:4f7a8e5c`
6. ❌ **Rolls back to LATEST, not PREVIOUS!** 🚨

### The Fix

Must export the environment variable:

```bash
PREVIOUS_TAG=$(cat "$DEPLOY_DIR/previous_version")

echo "Rolling back to $PREVIOUS_TAG"

# ✅ ADD THIS LINE
export PRAVAH_IMAGE_TAG="$PREVIOUS_TAG"

docker pull docker.io/${{ secrets.DOCKER_HUB_USERNAME }}/pravah:$PREVIOUS_TAG

docker compose down

docker compose -f docker-compose.prod.yml up -d  # ✅ NOW uses correct tag!

docker compose ps

echo "Rollback completed."
```

---

## 📋 Issues Found

### Issue 1: Missing PRAVAH_IMAGE_TAG Export ❌
```bash
# Current (broken)
docker compose up -d

# Should be (fixed)
export PRAVAH_IMAGE_TAG="$PREVIOUS_TAG"
docker compose -f docker-compose.prod.yml up -d
```

### Issue 2: Not Using docker-compose.prod.yml ❌
```bash
# Current (uses default docker-compose.yml)
docker compose down
docker compose up -d

# Should be (uses production file explicitly)
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Issue 3: Missing --profile prod ❌
```bash
# Current (might not start all services)
docker compose up -d

# Should be (ensures all prod services start)
docker compose -f docker-compose.prod.yml --profile prod up -d
```

---

## ✅ Fixed Rollback Script

```bash
rollback:
  needs: deploy
  if: failure()
  runs-on: ubuntu-latest

  steps:
    - name: Rollback deployment
      uses: appleboy/ssh-action@v1.2.0
      with:
        host: ${{ secrets.PROD_VM_HOST }}
        username: ${{ secrets.PROD_VM_USER }}
        password: ${{ secrets.PROD_VM_PASSWORD }}
        port: ${{ secrets.PROD_VM_PORT }}

        script: |
          set -euo pipefail

          DEPLOY_DIR="/opt/pravah"

          # 1. Read previous version
          PREVIOUS_TAG=$(cat "$DEPLOY_DIR/previous_version")
          echo "Rolling back to $PREVIOUS_TAG"

          # 2. Login to Docker Hub
          echo "${{ secrets.DOCKER_HUB_TOKEN }}" | docker login \
            --username "${{ secrets.DOCKER_HUB_USERNAME }}" \
            --password-stdin

          # 3. Pull previous image
          docker pull \
            docker.io/${{ secrets.DOCKER_HUB_USERNAME }}/pravah:$PREVIOUS_TAG

          # 4. Export image tag for docker-compose
          export PRAVAH_IMAGE_TAG="$PREVIOUS_TAG"

          cd "$DEPLOY_DIR"

          # 5. Stop current containers
          docker compose -f docker-compose.prod.yml down

          # 6. Start with previous version
          docker compose -f docker-compose.prod.yml --profile prod up -d

          # 7. Wait for services
          echo "Waiting for Redis..."
          timeout 300 bash -c '
          until docker compose -f docker-compose.prod.yml exec -T redis redis-cli ping
          do
              sleep 5
          done
          '

          # 8. Verify services
          echo "Checking control plane..."
          timeout 300 bash -c '
          until curl -fs http://localhost:7001/api/health
          do
              sleep 5
          done
          '

          echo "Checking decision brain..."
          timeout 300 bash -c '
          until curl -fs http://localhost:8001/health
          do
              sleep 5
          done
          '

          echo "Checking observer..."
          timeout 300 bash -c '
          until curl -fs http://localhost:8602/health
          do
              sleep 5
          done
          '

          # 9. Show status
          docker compose -f docker-compose.prod.yml ps

          # 10. Update current version file
          echo "Rollback completed to $PREVIOUS_TAG"
          echo "$PREVIOUS_TAG" > "$DEPLOY_DIR/current_version"
```

---

## 🔄 Comparison: Before vs After

### Before (Broken)
```bash
# Reads correct previous tag
PREVIOUS_TAG=$(cat "$DEPLOY_DIR/previous_version")  # 4f7a8e5c

# Pulls correct image
docker pull ...pravah:4f7a8e5c

# ❌ But doesn't set env var
docker compose down
docker compose up -d
# docker-compose.prod.yml uses: ${PRAVAH_IMAGE_TAG:-latest}
# Falls back to: latest ❌

# Result: Rolls back to LATEST, not previous version!
```

### After (Fixed)
```bash
# Reads correct previous tag
PREVIOUS_TAG=$(cat "$DEPLOY_DIR/previous_version")  # 4f7a8e5c

# Pulls correct image
docker pull ...pravah:4f7a8e5c

# ✅ Sets env var
export PRAVAH_IMAGE_TAG="4f7a8e5c"

docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml --profile prod up -d
# docker-compose.prod.yml uses: ${PRAVAH_IMAGE_TAG:-latest}
# Uses: 4f7a8e5c ✅

# Result: Rolls back to correct previous version!
```

---

## 📊 Rollback Flow (Fixed)

```
1. Deployment fails during health checks
   ↓
2. GitHub Actions triggers rollback job
   ↓
3. Rollback script runs on VM:
   ├─ Read: previous_version file → 4f7a8e5c
   ├─ Pull: docker.io/user/pravah:4f7a8e5c
   ├─ ✅ Export: PRAVAH_IMAGE_TAG=4f7a8e5c
   ├─ Run: docker compose -f docker-compose.prod.yml --profile prod up -d
   ├─ docker-compose.prod.yml resolves: ${PRAVAH_IMAGE_TAG} = 4f7a8e5c
   ├─ All 8 services pull: docker.io/user/pravah:4f7a8e5c
   ├─ Wait for health checks
   ├─ Update: current_version = 4f7a8e5c
   └─ ✅ Rollback complete - running PREVIOUS version!
```

---

## 🔑 Key Fix Points

1. **Export Variable**
   ```bash
   export PRAVAH_IMAGE_TAG="$PREVIOUS_TAG"
   ```

2. **Use Prod Compose File**
   ```bash
   docker compose -f docker-compose.prod.yml down
   docker compose -f docker-compose.prod.yml --profile prod up -d
   ```

3. **Wait for Services**
   ```bash
   # Same health checks as deploy job
   until docker compose -f docker-compose.prod.yml exec -T redis redis-cli ping
   until curl -fs http://localhost:7001/api/health
   until curl -fs http://localhost:8001/health
   until curl -fs http://localhost:8602/health
   ```

4. **Update Version File**
   ```bash
   echo "$PREVIOUS_TAG" > "$DEPLOY_DIR/current_version"
   ```

---

## ✅ Summary of Issues & Fixes

| Issue | Current | Fixed |
|-------|---------|-------|
| **Export PRAVAH_IMAGE_TAG** | ❌ NO | ✅ YES |
| **Use docker-compose.prod.yml** | ❌ NO (uses default) | ✅ YES (explicit -f flag) |
| **Use --profile prod** | ❌ NO | ✅ YES |
| **Health checks** | ✅ Basic | ✅ Complete (all 3 services) |
| **Version file update** | ❌ NO | ✅ YES |

---

## 🎯 Result After Fix

✅ Rollback pulls correct image tag
✅ Rollback exports PRAVAH_IMAGE_TAG variable
✅ docker-compose.prod.yml uses correct tag (not latest)
✅ All services start with previous SHA version
✅ Health checks verify rollback success
✅ Version tracking updated

**Rollback now works correctly!** ✅

---

**Status:** Issue identified and fixed
**Severity:** High (rollback was partially broken)
**Impact:** Now rollback restores correct previous version using SHA tags
