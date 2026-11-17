# Pravah Production CI/CD & Deployment Pipeline

## Overview

This document explains the complete CI/CD pipeline for deploying the Pravah multi-agent system to a production VM using GitHub Actions, Docker Hub, and automated rollback capabilities.

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Developer Pushes Code                        │
│                      (to main branch)                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              STAGE 1: GitHub Actions CI/CD Pipeline             │
│                      (.github/workflows/ci.yml)                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
    ┌────────┐          ┌────────┐          ┌────────┐
    │ Lint   │          │ Test   │          │ Build  │
    │        │          │        │          │ Docker │
    └────────┘          └────────┘          └────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
    ┌──────────────────────────────────────────────────┐
    │   Push Docker Image to Docker Hub Registry       │
    │   (Format: dockerhub_username/pravah:latest)     │
    └────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│        Trigger SSH Deployment to Production VM       │
│        (via appleboy/ssh-action)                     │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│           STAGE 2: VM Deployment Script              │
│        (Downloads docker-compose.yml from GitHub)    │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────────────┐
    │  1. Create Backup of Current Deployment    │
    │     /opt/pravah-backup/backup_YYYYMMDD_*  │
    └────────────────┬───────────────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────────────┐
    │  2. Pull Latest Images from Docker Hub     │
    │     docker compose pull                    │
    └────────────────┬───────────────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────────────┐
    │  3. Stop Old Containers                    │
    │     docker compose down                    │
    └────────────────┬───────────────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────────────┐
    │  4. Start New Containers                   │
    │     docker compose --profile prod up -d    │
    └────────────────┬───────────────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────────────┐
    │  5. Run Health Checks                      │
    │     - Redis ping                           │
    │     - Control Plane API                    │
    │     - Decision Brain API                   │
    └────────────────┬───────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
     SUCCESS              FAILURE
          │                     │
          ▼                     ▼
    ✅ Deployment         🔄 Automatic Rollback
       Complete            (restore from backup)
                           ❌ Notify Team
```

---

## File Structure

```
backend/
├── .github/
│   └── workflows/
│       └── ci.yml                    # GitHub Actions workflow
├── Dockerfile                        # Multi-stage production build
├── docker-compose.yml                # Docker Compose for VM (pulls from Docker Hub)
├── .env.example                      # Environment variables template
├── pravah-compose.service            # Systemd service file
├── pravah-compose-rollback.service   # Rollback service file
├── scripts/
│   ├── setup-vm.sh                   # One-time VM setup script
│   └── rollback.sh                   # Automatic rollback script
├── environments/
│   └── prod.env                      # Production env template
└── wsgi.py                           # Flask app entry point
```

---

## Component Explanations

### 1. GitHub Actions Workflow (`.github/workflows/ci.yml`)

**Purpose:** Automate testing, building, and deployment on every push to `main`

**Stages:**

#### Stage 1: Lint
```yaml
- Runs flake8 to catch syntax errors
- Checks code formatting (black)
- Fails soft (continue-on-error: true) so lint issues don't block pipeline
```

#### Stage 2: Test
```yaml
- Spins up Redis service container
- Installs Python dependencies
- Runs pytest on tests/ directory
- Generates code coverage report
```

#### Stage 3: Build
```yaml
- Sets up Docker Buildx (for multi-architecture support)
- Logs into Docker Hub using GitHub secrets
- Builds Dockerfile with layer caching
- Pushes image to Docker Hub as:
  - docker.io/USERNAME/pravah:latest
  - docker.io/USERNAME/pravah:main-<SHA>
```

#### Stage 4: Deploy
```yaml
- Runs ONLY on main branch (not on develop or PRs)
- Uses SSH to connect to production VM
- Downloads fresh docker-compose.yml from GitHub
- Creates backup before deployment
- Pulls latest images from Docker Hub
- Stops old containers and starts new ones
- Runs health checks
- Triggers rollback on failure
```

**Key Secrets Required in GitHub:**
```
DOCKER_HUB_USERNAME       - Your Docker Hub username
DOCKER_HUB_TOKEN          - Docker Hub personal access token
PROD_VM_HOST              - Public IP of production VM
PROD_VM_USER              - SSH user (usually ubuntu or root)
PROD_VM_SSH_KEY           - Private SSH key for password-less auth
PROD_VM_PORT              - SSH port (default: 22)
```

---

### 2. Dockerfile (Multi-stage Build)

**Purpose:** Create optimized production Docker image

**Stage 1: Builder**
```dockerfile
FROM python:3.11-slim as builder
- Installs build tools (gcc, build-essential)
- Creates Python virtual environment
- Installs all dependencies from requirements.txt
- Result: ~1.2GB (not pushed)
```

**Stage 2: Runtime**
```dockerfile
FROM python:3.11-slim
- Copies only virtual environment from builder
- Copies application code
- Creates non-root user (pravah:1000)
- Exposes ports: 7000, 8000, 8600
- Health check: curl http://localhost:7000/api/health
- Final size: ~500MB (pushed to Docker Hub)
```

**Benefits:**
- Reduces final image size by 60%
- Excludes build tools from production image
- Improves security (non-root user)
- Faster pulls from Docker Hub

---

### 3. Docker Compose (deployment/docker-compose.yml)

**Purpose:** Orchestrate all services on the production VM

**Key Features:**

**Profiles:**
- `prod` - Production services (default for CI/CD)
- `dev` - Development services
- `legacy` - Old Streamlit dashboards (local dev only)

**Services:**

| Service | Purpose | Port | Restart | Image |
|---------|---------|------|---------|-------|
| redis | Event bus | 6379 | unless-stopped | redis:7-alpine |
| control-plane | Agent runtime | 7000 | unless-stopped | USERNAME/pravah |
| decision-brain | Policy engine | 8000 | unless-stopped | USERNAME/pravah |
| observer | Health monitoring | 8600 | unless-stopped | USERNAME/pravah |
| deploy-worker-1/2/3 | Parallel deployment | N/A | unless-stopped | USERNAME/pravah |
| queue-monitor | Queue monitoring | N/A | unless-stopped | USERNAME/pravah |
| health-monitor | System health | N/A | unless-stopped | USERNAME/pravah |
| prometheus | Metrics scraping | 9090 | unless-stopped | prom/prometheus |

**Key Configuration:**

```yaml
# Environment variables from .env file
environment:
  - REDIS_HOST=redis          # Docker DNS name (not localhost)
  - ENVIRONMENT=prod
  - PYTHONUNBUFFERED=1

# Volume mounts for logs and data persistence
volumes:
  - ./logs:/app/logs          # Host: /opt/pravah/logs
  - ./data:/app/data          # Host: /opt/pravah/data

# Health checks for automatic restart
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
  interval: 10s
  timeout: 5s
  retries: 5

# Resource limits
deploy:
  resources:
    limits:
      cpus: "2.00"
      memory: 1G
    reservations:
      cpus: "0.50"
      memory: 256M

# Restart policy: always restart unless manually stopped
restart: unless-stopped
```

---

### 4. Environment Variables (.env)

**Purpose:** Configure application behavior without rebuilding Docker image

**Loaded By:** `docker compose --env-file .env`

**Categories:**

```bash
# Core Settings
ENVIRONMENT=prod              # prod | staging | dev
DEBUG=false                  # Never true in production
LOG_LEVEL=INFO               # DEBUG | INFO | WARNING | ERROR

# Service Ports
CONTROL_PLANE_PORT=7000
DECISION_BRAIN_PORT=8000
OBSERVER_PORT=8600
REDIS_PORT=6379

# Worker Configuration
GUNICORN_WORKERS=4           # CPU cores x 2
UVICORN_WORKERS=2

# Docker Hub
DOCKER_HUB_USERNAME=myusername

# Secrets (should be empty, injected by CI/CD)
SSPL_SECRET_KEY=
LINEAGE_SIGNING_KEY=
JWT_SECRET_KEY=

# External Service URLs
PRAVAH_GURUKUL_API=http://gurukul-api.com:3000
PRAVAH_HR_API=http://hr-api.com:8000
# ... more services
```

**On VM:**
- Location: `/opt/pravah/.env`
- Created from `.env.example` during setup
- Edit with: `nano /opt/pravah/.env`
- Secrets come from GitHub Actions (CI/CD injects them)

---

### 5. Systemd Service Files

**Purpose:** Auto-manage docker-compose with OS-level systemd

#### pravah-compose.service

```ini
[Unit]
Description=Pravah Multi-Agent CI/CD System (Docker Compose)
After=docker.service              # Start after Docker daemon
Requires=docker.service           # Require Docker to run

[Service]
Type=oneshot                      # One-time execution
RemainAfterExit=yes              # Keep running after ExecStart
WorkingDirectory=/opt/pravah     # Where to run docker compose

ExecStartPre=docker compose pull  # Update images first
ExecStart=docker compose --profile prod up -d  # Start services
ExecStop=docker compose down      # Stop on systemctl stop

OnFailure=pravah-compose-rollback.service  # Trigger rollback
Restart=on-failure                # Restart if it crashes
RestartSec=10s                    # Wait 10s before restart

[Install]
WantedBy=multi-user.target        # Start on system boot
```

**Usage:**
```bash
# Enable auto-start on system boot
sudo systemctl enable pravah-compose

# Start services
sudo systemctl start pravah-compose

# Check status
sudo systemctl status pravah-compose

# View logs
journalctl -u pravah-compose -f

# Stop services
sudo systemctl stop pravah-compose

# Restart services
sudo systemctl restart pravah-compose
```

#### pravah-compose-rollback.service

```ini
# Triggered when pravah-compose.service fails
# Runs scripts/rollback.sh to restore previous version
```

---

### 6. Rollback Script (`scripts/rollback.sh`)

**Purpose:** Automatically restore previous working deployment on failure

**Flow:**
```bash
1. Stop current services (docker compose down)
2. Remove broken deployment (rm -rf /opt/pravah/*)
3. Find latest backup (ls -t /opt/pravah-backup/)
4. Restore files from backup (cp -r backup/* /opt/pravah/)
5. Start previous version (docker compose --profile prod up -d)
6. Wait and verify health checks
7. Log results to /var/log/pravah-rollback.log
```

**Backup Location:** `/opt/pravah-backup/backup_YYYYMMDD_HHMMSS/`
- Timestamped for easy identification
- Keeps last 5 backups (older ones auto-deleted)
- Contains: docker-compose.yml, .env, logs, data

**Triggered By:**
- CI/CD deployment fails health checks
- Service crashes and won't restart
- Manual: `sudo systemctl start pravah-compose-rollback`

---

### 7. VM Setup Script (`scripts/setup-vm.sh`)

**Purpose:** One-time initialization of a fresh VM

**Run Once:**
```bash
# On fresh Ubuntu 22.04 VM
bash ./scripts/setup-vm.sh https://github.com/your-org/your-repo.git
```

**Performs:**
```
1. Update system packages
2. Install Docker & docker-compose
3. Create /opt/pravah directory structure
4. Clone repo (sparse checkout - only backend folder)
5. Copy .env.example → .env template
6. Install systemd service files
7. Make scripts executable
8. Pull Docker images (optional)
9. Display next steps for operator
```

---

## Deployment Process (Step-by-Step)

### Prerequisites

**On GitHub:**
1. Create Docker Hub account & personal access token
2. Add 5 secrets to GitHub repository settings:
   ```
   DOCKER_HUB_USERNAME
   DOCKER_HUB_TOKEN
   PROD_VM_HOST
   PROD_VM_USER
   PROD_VM_SSH_KEY
   ```

**On Production VM:**
1. Fresh Ubuntu 22.04 instance
2. SSH enabled with public key auth
3. Sudo access for main user
4. Run: `bash ./scripts/setup-vm.sh <repo-url>`

---

### Workflow: Push → Build → Deploy

**Step 1: Developer Pushes to Main**
```bash
git add .
git commit -m "Fix: Update service logic"
git push origin main
```

**Step 2: GitHub Actions Triggers**
- Webhook event: `on.push.branches.[main]`
- Starts ci.yml workflow

**Step 3: Lint Job Runs**
```bash
flake8 .
black --check .
# ✅ If passed, continue
# ⚠️ If failed, log warnings but don't fail pipeline
```

**Step 4: Test Job Runs**
```bash
pytest tests/ --cov=.
# Needs Redis service (started automatically)
# ✅ If tests pass, continue
# ❌ If tests fail, stop pipeline (notify developer)
```

**Step 5: Build Job Runs**
```bash
# Step 5a: Build multi-stage Dockerfile
docker build --target runtime -t docker.io/username/pravah:latest .

# Step 5b: Push to Docker Hub
docker push docker.io/username/pravah:latest
docker push docker.io/username/pravah:main-<commit-sha>
```

**Step 6: Deploy Job Runs (main branch only)**
```bash
# Step 6a: SSH into VM
ssh -i $PROD_VM_SSH_KEY ubuntu@prod-vm-ip

# Step 6b: Download fresh docker-compose.yml
curl -o /opt/pravah/docker-compose.yml \
  https://raw.githubusercontent.com/.../main/backend/docker-compose.yml

# Step 6c: Create backup
cp -r /opt/pravah/* /opt/pravah-backup/backup_20240115_143022/

# Step 6d: Pull latest images from Docker Hub
cd /opt/pravah
docker compose pull
# Pulls: docker.io/username/pravah:latest

# Step 6e: Stop old containers
docker compose down

# Step 6f: Start new containers
docker compose --profile prod up -d

# Step 6g: Wait for health checks
sleep 10
docker compose exec -T redis redis-cli ping
# If fails → trigger rollback

# Step 6h: Display status
docker compose ps
```

**Step 7: Health Checks**
```bash
✅ Redis responding to PING
✅ Control Plane HTTP 200
✅ Decision Brain HTTP 200
✅ Services in health state

If ANY fail:
  1. Stop new containers
  2. Restore from backup
  3. Start previous version
  4. Report failure in GitHub Actions
```

**Step 8: Post-Deployment**
- Old backup files (>5) deleted
- Logs show deployment summary
- GitHub Actions marks workflow as ✅ Success

---

## Rollback Scenarios

### Automatic Rollback

**Triggered when:**
1. Health checks fail after `docker compose up -d`
2. Deployment script detects Redis not responding
3. Systemd service OnFailure condition triggered

**Happens in:**
- CI/CD deployment SSH script (inline)
- Or triggered via `pravah-compose-rollback.service`

**Time:** < 2 minutes

**Result:**
```
Old containers stopped
Previous docker-compose.yml restored
Previous .env restored
Services restart with last-known-good configuration
Logs saved to /opt/pravah-backup/
```

### Manual Rollback

**If automatic rollback needed:**
```bash
# SSH into VM
ssh ubuntu@prod-vm-ip

# Option 1: Via systemd service
sudo systemctl start pravah-compose-rollback

# Option 2: Run rollback script directly
bash /opt/pravah/scripts/rollback.sh

# Option 3: Restore specific backup
cp -r /opt/pravah-backup/backup_YYYYMMDD_HHMMSS/* /opt/pravah/
docker compose --profile prod up -d
```

### Viewing Backups

```bash
# List all backups with timestamps
ls -lhtr /opt/pravah-backup/

# Check backup contents
ls -la /opt/pravah-backup/backup_20240115_143022/

# Restore specific backup
cp -r /opt/pravah-backup/backup_20240115_143022/* /opt/pravah/
docker compose --profile prod up -d
```

---

## Monitoring & Logs

### Real-time Service Logs

```bash
# All services
docker compose logs -f

# Specific service (e.g., Control Plane)
docker compose logs -f control-plane

# Last 100 lines
docker compose logs --tail=100 control-plane

# Last hour
docker compose logs --since=1h
```

### Systemd Logs

```bash
# Deployment logs
journalctl -u pravah-compose -f

# Rollback logs
journalctl -u pravah-compose-rollback

# All pravah-related logs
journalctl -g pravah -f
```

### Application Logs (saved to disk)

```bash
# Location: /opt/pravah/logs/

ls -la logs/
# logs/access.log         - HTTP requests
# logs/error.log          - Application errors
# logs/prod/              - Production logs
# logs/prod/performance/  - Performance metrics

# Real-time tail
tail -f logs/error.log
tail -f logs/access.log
```

### Prometheus Metrics

```
http://prod-vm-ip:9090

# Scrapes metrics from:
- Control Plane :7000/metrics
- Decision Brain :8000/metrics
- Observer :8600/metrics
- Redis
```

---

## Troubleshooting

### Deployment Failed - Check These

**1. GitHub Actions shows red X**
```bash
# Click "Details" → see which stage failed
# Lint: Check .github/workflows/ci.yml syntax
# Test: Check pytest results (check requirements.txt)
# Build: Check Dockerfile syntax
# Deploy: Check SSH credentials
```

**2. Services stuck in "Restarting"**
```bash
docker compose logs control-plane | tail -50
# Check for:
# - Out of memory (exit 137)
# - Port already in use (EADDRINUSE)
# - Redis not connected
# - Missing environment variables
```

**3. Rollback didn't trigger**
```bash
# Check if backup exists
ls -la /opt/pravah-backup/

# Check systemd rollback service
sudo systemctl status pravah-compose-rollback
journalctl -u pravah-compose-rollback

# Manual trigger
bash /opt/pravah/scripts/rollback.sh
```

**4. Docker compose pull fails**
```bash
# Check Docker Hub credentials
docker login -u USERNAME

# Check image exists
docker search USERNAME/pravah

# Check Docker Hub repo is public
```

**5. SSH deployment fails**
```bash
# Check SSH key permissions (local machine)
chmod 600 ~/.ssh/prod_vm_key

# Check SSH connectivity (local machine)
ssh -i ~/.ssh/prod_vm_key ubuntu@prod-vm-ip echo "success"

# Check GitHub secrets are correct
# Settings → Secrets → Review PROD_VM_*
```

---

## Best Practices

### For Developers

1. **Keep main branch stable**
   - Merge to main only after PR review
   - Develop on feature branches

2. **Write tests**
   - New code = new tests
   - Minimum 70% coverage
   - Run locally: `pytest tests/`

3. **Pin dependencies**
   - requirements.txt: exact versions
   - Prevents surprises in production

4. **Use feature flags**
   - New features behind ENV vars
   - Safer rollouts

### For Operations

1. **Monitor logs daily**
   - Check: `docker compose logs --since=24h`
   - Look for errors and warnings

2. **Weekly backup cleanup**
   - Auto-cleans last 5 (can reduce to 3)
   - Store old backups in S3/archival

3. **Test rollback monthly**
   - Manual trigger to verify process works
   - Time it to measure downtime

4. **Update dependencies**
   - requirements.txt: `pip list --outdated`
   - Dockerfile: `python:3.11-slim` → update base image monthly

5. **Resource monitoring**
   - Check `docker stats`
   - Alert if CPU/memory exceeded

---

## Security Considerations

### Secrets Management
✅ DO:
- Store secrets in GitHub Secrets
- Inject via environment at deployment time
- Use .env.example (NO real values)

❌ DON'T:
- Commit .env with real values
- Hardcode secrets in Dockerfile
- Use generic passwords

### Network Security
✅ DO:
- SSH only via key auth (no password)
- Run services in private network (docker network)
- Use firewall to restrict ports

❌ DON'T:
- Expose Redis (6379) to public internet
- Disable SSH key requirement
- Run all services on 0.0.0.0:*

### Image Security
✅ DO:
- Run containers as non-root (pravah:1000)
- Scan images: `docker scan docker.io/username/pravah`
- Update base image regularly

❌ DON'T:
- Run as root in container
- Use `latest` tag in Dockerfile (should be explicit version)

---

## Summary

| Component | Purpose | When Changed |
|-----------|---------|--------------|
| ci.yml | GitHub Actions workflow | When CI logic changes |
| Dockerfile | Build production image | When dependencies added |
| docker-compose.yml | Orchestrate services | When services change |
| .env.example | Environment template | When new ENV vars added |
| scripts/setup-vm.sh | First-time VM setup | When Docker version updates |
| scripts/rollback.sh | Auto-restore backup | When backup structure changes |
| pravah-compose.service | Systemd control | When systemd logic changes |

---

## Contact & Support

For issues with:
- **CI/CD pipeline**: Check GitHub Actions logs
- **Deployment**: Check `/var/log/pravah-*` on VM
- **Rollback**: Check `/opt/pravah-backup/` structure
- **Services**: Check `docker compose logs`

---

**Version:** 1.0  
**Last Updated:** 2024  
**Maintainer:** DevOps Team
