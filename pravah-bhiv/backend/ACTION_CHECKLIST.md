# ✅ ACTION CHECKLIST - What You Need to Do NOW

## Immediate Actions (15 minutes)

### Step 1: Create/Login to Docker Hub
- [ ] Go to https://hub.docker.com
- [ ] Sign up or login
- [ ] Create public repository named "pravah"

### Step 2: Generate Docker Hub Personal Access Token
- [ ] Go to: Account Settings (top right menu)
- [ ] Click: Security
- [ ] Click: Personal Access Tokens
- [ ] Click: New Access Token
- [ ] Name it: "Pravah CI/CD"
- [ ] Scope: Read & Write
- [ ] Click: Generate
- [ ] **IMPORTANT:** Copy the token (you'll only see it once!)
- [ ] Save it somewhere safe (needed for GitHub)

### Step 3: Add 6 GitHub Secrets
Go to your GitHub repository:
```
Settings → Secrets and variables → Actions → New repository secret
```

Add these 6 secrets (copy exactly):

#### 1. DOCKER_HUB_USERNAME
```
Name: DOCKER_HUB_USERNAME
Value: your-dockerhub-username
Example: john-doe
```

#### 2. DOCKER_HUB_TOKEN
```
Name: DOCKER_HUB_TOKEN
Value: (paste the token from Docker Hub)
```

#### 3. PROD_VM_HOST
```
Name: PROD_VM_HOST
Value: your-vm-public-ip
Example: 203.0.113.45
```

#### 4. PROD_VM_USER
```
Name: PROD_VM_USER
Value: ubuntu (or your SSH user)
```

#### 5. PROD_VM_PASSWORD
```
Name: PROD_VM_PASSWORD
Value: your-ssh-password
```

#### 6. PROD_VM_PORT
```
Name: PROD_VM_PORT
Value: 22 (or your custom SSH port)
```

---

## Verification (5 minutes)

### Check 1: All Secrets Added
```
GitHub → Settings → Secrets and variables → Actions
Should show 6 secrets:
✓ DOCKER_HUB_USERNAME
✓ DOCKER_HUB_TOKEN
✓ PROD_VM_HOST
✓ PROD_VM_USER
✓ PROD_VM_PASSWORD
✓ PROD_VM_PORT
```

### Check 2: Files Exist
```bash
# In ./backend/ directory:
✓ .github/workflows/ci.yml
✓ docker-compose.yml
✓ Dockerfile
✓ .env.example
✓ scripts/setup-vm.sh
```

### Check 3: Docker Hub Setup
```
✓ Docker Hub account created
✓ Repository "pravah" created (public)
✓ Personal access token generated and saved
```

---

## First Deployment (5 minutes)

### Step 1: Push Code
```bash
git add .
git commit -m "ci: setup production CI/CD pipeline"
git push origin main
```

### Step 2: Monitor GitHub Actions
```
GitHub → Actions → Latest workflow
Watch for:
1. Lint ✓
2. Test ✓
3. Build & Push ✓
4. Deploy ✓
(Takes 2-5 minutes)
```

### Step 3: Verify Deployment
```bash
# SSH into your VM
ssh username@your-vm-ip

# Check if containers running
docker compose ps

# Check logs
docker compose logs -f
```

---

## Production VM Setup

### One-Time Setup (On Your VM)
```bash
# SSH into VM
ssh username@your-vm-ip

# Create deploy directory
mkdir -p /opt/pravah

# Copy files (or clone repo)
# Then run setup script
bash /opt/pravah/scripts/setup-vm.sh

# Edit environment
nano /opt/pravah/.env
# Update: DOCKER_HUB_USERNAME
```

---

## After First Deployment

### Check Service Status
```bash
docker compose ps

# Should show:
# pravah-redis (healthy)
# pravah-control-plane (Up)
# pravah-decision-brain (Up)
# pravah-observer (Up)
# ... and others
```

### Test Services
```bash
# Redis
docker compose exec redis redis-cli ping
# Expected: PONG

# Control Plane
curl http://localhost:7001/api/health
# Expected: HTTP 200

# Decision Brain
curl http://localhost:8001/health
# Expected: HTTP 200
```

### Check Logs
```bash
# All services
docker compose logs

# Specific service
docker compose logs control-plane

# Follow in real-time
docker compose logs -f
```

---

## Troubleshooting

### If Deploy Fails
1. Check GitHub Actions logs (click the red X)
2. Look for error messages
3. Common issues:
   - Wrong Docker Hub credentials
   - Wrong VM IP/password
   - Dockerfile syntax error
   - Test failure

### If Services Won't Start on VM
1. Check docker logs: `docker compose logs`
2. Check port conflicts: `sudo lsof -i :6380`
3. Check disk space: `df -h`
4. Check memory: `free -h`

### If Rollback Needed
```bash
# Check available backups
ls -lh /opt/pravah-backup/

# Restore specific backup
BACKUP=backup_20260803_130000
cp -r /opt/pravah-backup/$BACKUP/* /opt/pravah/

# Restart
docker compose down
docker compose --profile prod up -d
```

---

## Quick Reference Commands

```bash
# View all services
docker compose ps

# View logs
docker compose logs -f

# Stop services
docker compose down

# Start services
docker compose --profile prod up -d

# Restart specific service
docker compose restart control-plane

# Health check
docker compose exec redis redis-cli ping

# Check Docker Hub
docker search yourusername/pravah

# Manual deploy trigger
git push origin main
```

---

## Timeline

| Time | Action | Status |
|------|--------|--------|
| Now | Add GitHub secrets | ⏳ TODO |
| 5 min | Push code | ⏳ TODO |
| 5-10 min | GitHub Actions runs | ⏳ WAITING |
| 10-15 min | Docker build completes | ⏳ WAITING |
| 15-20 min | Image pushed to Docker Hub | ⏳ WAITING |
| 20-25 min | Deploy to VM starts | ⏳ WAITING |
| 25-30 min | Services running on VM | ⏳ WAITING |

---

## Success Criteria

✅ All 6 GitHub secrets added
✅ GitHub Actions workflow completes (all green checkmarks)
✅ Docker image pushed to Docker Hub
✅ Services running on VM
✅ Health checks passing
✅ Can access services on remapped ports:
  - http://vm-ip:7001 (Control Plane)
  - http://vm-ip:8001 (Decision Brain)
  - http://vm-ip:8602 (Observer)
  - http://vm-ip:9091 (Prometheus)

---

## 🎯 Summary

**What you're setting up:**
- Automated CI/CD pipeline (GitHub Actions)
- Docker image building and registry (Docker Hub)
- Automatic VM deployment with rollback
- 10 production services running in Docker

**What gets automated:**
- Code quality checks (lint)
- Unit tests (pytest)
- Docker image building (multi-stage)
- Docker image push (Docker Hub)
- VM deployment (SSH)
- Service health monitoring
- Automatic rollback on failure

**Result:**
Push code → Everything automated → Services live in 5-30 minutes

---

**Status:** ✅ Ready to Start
**Next:** Add GitHub secrets now!

---

For detailed information, see:
- CICD_CHANGES_SUMMARY.md - Complete overview
- docker-compose.yml - Service configuration
- .github/workflows/ci.yml - Pipeline steps
