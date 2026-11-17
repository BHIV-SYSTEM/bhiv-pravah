# Implementation Checklist

## 📋 Pre-Deployment Checklist

Use this checklist to ensure everything is properly configured before deploying to production.

---

## ✅ Phase 1: GitHub Setup (Do This First)

- [ ] **Create Docker Hub Account**
  - [ ] Go to https://hub.docker.com
  - [ ] Sign up with email
  - [ ] Verify email
  - [ ] Create public repository named "pravah"

- [ ] **Generate Docker Hub Token**
  - [ ] Account Settings → Security → Personal Access Tokens
  - [ ] Create token
  - [ ] Copy token (save securely - you'll use it once)
  - [ ] Scope: Read & Write

- [ ] **Add GitHub Secrets (5 Total)**
  - [ ] Go to GitHub Repo → Settings → Secrets and variables → Actions
  - [ ] Click "New repository secret"
  
  - [ ] **DOCKER_HUB_USERNAME**
    - [ ] Value: `your-dockerhub-username`
    - [ ] Verify no spaces
    - [ ] Verify case (Docker Hub usernames are lowercase)
  
  - [ ] **DOCKER_HUB_TOKEN**
    - [ ] Value: (paste from Docker Hub token)
    - [ ] Verify it's the full token (45+ characters)
    - [ ] Not your password, it's the generated token
  
  - [ ] **PROD_VM_HOST**
    - [ ] Value: `your-vm-public-ip` (e.g., `203.0.113.45`)
    - [ ] Verify IP is reachable: `ping your-vm-public-ip`
    - [ ] NOT localhost, 127.0.0.1, or private IP
  
  - [ ] **PROD_VM_USER**
    - [ ] Value: SSH username (usually `ubuntu` or `root`)
    - [ ] Verify user exists on VM: `ssh ubuntu@your-vm-ip whoami`
    - [ ] Verify sudo access: `ssh ubuntu@your-vm-ip sudo whoami`
  
  - [ ] **PROD_VM_SSH_KEY**
    - [ ] Value: (entire private key content)
    - [ ] Get from: `cat ~/.ssh/id_rsa` (on your local machine)
    - [ ] Includes: `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----`
    - [ ] Verify key works: `ssh -i ~/.ssh/id_rsa ubuntu@your-vm-ip echo "success"`

---

## ✅ Phase 2: VM Preparation

- [ ] **VM Provisioning**
  - [ ] OS: Ubuntu 22.04 LTS (64-bit)
  - [ ] CPU: Minimum 2 cores (4 recommended)
  - [ ] RAM: Minimum 4GB (8GB recommended)
  - [ ] Disk: Minimum 20GB (50GB recommended)
  - [ ] Network: Public IP assigned
  - [ ] SSH: Port 22 open, public key auth enabled

- [ ] **SSH Access Verified**
  - [ ] Can SSH without password: `ssh ubuntu@vm-ip`
  - [ ] Key-based auth working: `ssh -i ~/.ssh/id_rsa ubuntu@vm-ip`
  - [ ] Sudo works without password: `ssh ubuntu@vm-ip sudo whoami`

- [ ] **VM Ready Check**
  - [ ] VM is publicly accessible: `ping vm-ip`
  - [ ] SSH port open: `telnet vm-ip 22` (should connect)
  - [ ] Can execute remote commands: `ssh ubuntu@vm-ip uname -a`

---

## ✅ Phase 3: Repository Files Verification

- [ ] **Check All Files Exist**
  - [ ] `.github/workflows/ci.yml` ✓
  - [ ] `Dockerfile` ✓
  - [ ] `docker-compose.yml` ✓
  - [ ] `.env.example` ✓
  - [ ] `.dockerignore` ✓
  - [ ] `pravah-compose.service` ✓
  - [ ] `pravah-compose-rollback.service` ✓
  - [ ] `scripts/setup-vm.sh` ✓
  - [ ] `scripts/rollback.sh` ✓

- [ ] **Verify File Permissions**
  - [ ] `scripts/setup-vm.sh` is readable
  - [ ] `scripts/rollback.sh` is readable
  - [ ] Git will track all files: `git status` shows nothing to commit

- [ ] **Verify Content**
  - [ ] `ci.yml` contains 5 stages (lint, test, build, deploy, notify)
  - [ ] `Dockerfile` has 2 stages (builder, runtime)
  - [ ] `docker-compose.yml` has 9 services defined
  - [ ] `.env.example` has DOCKER_HUB_USERNAME placeholder

---

## ✅ Phase 4: Initial VM Setup

- [ ] **SSH into Fresh VM**
  - [ ] `ssh ubuntu@your-vm-ip`

- [ ] **Clone Repository** (on VM)
  - [ ] `git clone https://github.com/your-org/your-repo.git`
  - [ ] `cd your-repo/backend`
  - [ ] `ls -la` shows files (Dockerfile, docker-compose.yml, etc.)

- [ ] **Run Setup Script** (on VM)
  - [ ] `bash scripts/setup-vm.sh https://github.com/your-org/your-repo.git`
  - [ ] Script completes without errors
  - [ ] Verifies Docker installed: `docker --version`
  - [ ] Verifies Docker Compose: `docker-compose --version`

- [ ] **Setup Completed**
  - [ ] Directory `/opt/pravah/` created
  - [ ] Directory `/opt/pravah-backup/` created
  - [ ] Systemd services installed
  - [ ] `.env` file created from template

---

## ✅ Phase 5: Environment Configuration

- [ ] **Edit Production Environment** (on VM)
  - [ ] `nano /opt/pravah/.env`
  - [ ] Set required values:
    - [ ] `DOCKER_HUB_USERNAME=your-dockerhub-username`
    - [ ] `ENVIRONMENT=prod`
    - [ ] `SSPL_SECRET_KEY=<generate-random-string>`
    - [ ] `LINEAGE_SIGNING_KEY=<generate-random-string>`

- [ ] **Configure External Services**
  - [ ] Review all `PRAVAH_*_API=` entries
  - [ ] Set real URLs for your integrations (or keep existing if available)
  - [ ] Verify URLs are accessible

- [ ] **Verify Environment**
  - [ ] Save .env file
  - [ ] Test read: `source /opt/pravah/.env && echo $DOCKER_HUB_USERNAME`
  - [ ] Verify value appears correct

---

## ✅ Phase 6: Docker Setup

- [ ] **Docker Daemon Running** (on VM)
  - [ ] `sudo systemctl status docker` shows "active (running)"
  - [ ] `docker ps` shows no errors

- [ ] **Docker Hub Login** (on VM)
  - [ ] `docker login` (use your Docker Hub credentials)
  - [ ] Login succeeds: "Login Succeeded"
  - [ ] Verify: `cat ~/.docker/config.json | grep auth`

- [ ] **Pull Test Image** (on VM)
  - [ ] `docker pull redis:7-alpine`
  - [ ] Image downloaded successfully
  - [ ] Verify: `docker image ls redis:7-alpine`

---

## ✅ Phase 7: Systemd Services

- [ ] **Services Installed**
  - [ ] `ls -la /etc/systemd/system/pravah* | wc -l` shows 2
  - [ ] Both service files exist and readable

- [ ] **Enable Services**
  - [ ] `sudo systemctl enable pravah-compose`
  - [ ] `sudo systemctl daemon-reload`
  - [ ] Verify: `sudo systemctl is-enabled pravah-compose` shows "enabled"

- [ ] **Start Services**
  - [ ] `sudo systemctl start pravah-compose`
  - [ ] Wait 15 seconds
  - [ ] `docker compose ps` shows services starting/running

- [ ] **Check Status**
  - [ ] `sudo systemctl status pravah-compose` shows "active"
  - [ ] `docker compose ps | wc -l` shows 10+ services
  - [ ] Most services showing "Up" status

---

## ✅ Phase 8: Health Checks (on VM)

- [ ] **Redis**
  - [ ] `docker compose exec -T redis redis-cli ping`
  - [ ] Returns: `PONG`

- [ ] **Control Plane**
  - [ ] `docker compose logs control-plane | tail -20` shows no critical errors
  - [ ] Service status: `docker compose ps control-plane` shows "Up"

- [ ] **Services Running**
  - [ ] `docker compose ps` output shows:
    - [ ] redis: Up
    - [ ] control-plane: Up
    - [ ] decision-brain: Up
    - [ ] observer: Up
    - [ ] (workers & monitors can be Up or healthy)

---

## ✅ Phase 9: GitHub Actions Test

- [ ] **Make Test Commit**
  - [ ] `echo "# Deployment Test" >> README.md`
  - [ ] `git add README.md`
  - [ ] `git commit -m "test: trigger CI/CD"`
  - [ ] `git push origin main`

- [ ] **Monitor GitHub Actions**
  - [ ] GitHub Repo → Actions tab
  - [ ] Latest workflow is running
  - [ ] Wait for stages to complete (2-5 minutes):
    - [ ] ✅ Lint passes
    - [ ] ✅ Test passes
    - [ ] ✅ Build passes
    - [ ] ✅ Push passes
    - [ ] ✅ Deploy passes

- [ ] **Verify Deployment** (on VM)
  - [ ] `docker compose ps` shows fresh containers
  - [ ] `docker images | grep pravah` shows recently pulled image
  - [ ] Check logs: `docker compose logs --since=5m`

---

## ✅ Phase 10: Rollback Test

- [ ] **Create Backup**
  - [ ] `ls -la /opt/pravah-backup/` shows latest backup
  - [ ] Note the backup timestamp

- [ ] **Trigger Manual Rollback** (on VM)
  - [ ] `sudo systemctl start pravah-compose-rollback`
  - [ ] Wait 30 seconds
  - [ ] `docker compose ps` shows services still running

- [ ] **Verify Rollback Logs**
  - [ ] `tail -50 /var/log/pravah-rollback.log` shows success
  - [ ] Services restored and running

---

## ✅ Phase 11: Monitoring & Access

- [ ] **Access Services**
  - [ ] Control Plane: `curl http://your-vm-ip:7000` (should not 404)
  - [ ] Decision Brain: `curl http://your-vm-ip:8000/docs` (FastAPI docs)
  - [ ] Observer: `curl http://your-vm-ip:8600` (should respond)
  - [ ] Prometheus: `http://your-vm-ip:9090` (in browser, should load)

- [ ] **Check Logs**
  - [ ] `docker compose logs -f --tail=10` shows service activity
  - [ ] No repeated error messages
  - [ ] Services appear healthy

- [ ] **System Resources**
  - [ ] `docker stats --no-stream` shows reasonable CPU/Memory usage
  - [ ] No service using >80% CPU
  - [ ] No service using >90% Memory

---

## ✅ Phase 12: Documentation Review

- [ ] **Team Training**
  - [ ] Distribute `QUICK_REFERENCE.md` to ops team
  - [ ] Distribute `DEPLOYMENT_GUIDE.md` for detailed reference
  - [ ] Review common commands:
    - [ ] `docker compose ps`
    - [ ] `docker compose logs -f`
    - [ ] `docker compose restart <service>`

- [ ] **Runbooks Created**
  - [ ] Team has copy of `QUICK_REFERENCE.md`
  - [ ] Emergency contacts documented
  - [ ] Escalation procedure documented

---

## ✅ Phase 13: Production Hardening

- [ ] **Firewall Configured** (on VM)
  - [ ] SSH port (22) accessible only to trusted IPs (or VPN)
  - [ ] HTTP ports (7000, 8000, 8600, 9090) restricted to needed IPs
  - [ ] Redis (6379) NOT exposed to internet

- [ ] **Secrets Verified**
  - [ ] No secrets in `.env` are default/placeholder values
  - [ ] All `##PLACEHOLDER##` values have been replaced
  - [ ] `.env` file is NOT in git (check `.gitignore`)

- [ ] **Backups Verified**
  - [ ] `/opt/pravah-backup/` has at least one backup
  - [ ] Backup contains: `docker-compose.yml`, `.env`, `logs/`, `data/`
  - [ ] Restore test successful (Phase 10)

- [ ] **Logging Configured**
  - [ ] Check log file size: `du -sh /opt/pravah/logs/`
  - [ ] Not consuming excessive disk (< 1GB typical)
  - [ ] Old logs rotate: `ls -la /opt/pravah/logs/ | head -20`

---

## ✅ Phase 14: Final Verification

- [ ] **Complete Deployment Test**
  - [ ] Make another commit to main
  - [ ] Push and monitor full CI/CD pipeline
  - [ ] Verify deployment succeeded on VM

- [ ] **Smoke Tests**
  - [ ] All services healthy: `docker compose ps`
  - [ ] No error logs: `docker compose logs | grep ERROR | head`
  - [ ] Services responding: `curl http://localhost:7000`

- [ ] **Documentation Complete**
  - [ ] Runbooks written
  - [ ] Emergency procedures documented
  - [ ] Team trained
  - [ ] Contact list updated

---

## ✅ Phase 15: Go-Live

- [ ] **Pre-Launch Checklist**
  - [ ] All 14 phases above completed ✓
  - [ ] All team members trained ✓
  - [ ] Emergency procedures tested ✓
  - [ ] Backups verified ✓
  - [ ] Monitoring configured ✓

- [ ] **Launch Approved**
  - [ ] Stakeholder sign-off: _______________
  - [ ] DevOps lead approval: _______________
  - [ ] Date approved: _______________

- [ ] **Post-Launch Monitoring**
  - [ ] Monitor logs for 24 hours
  - [ ] Check deployment frequency (monitor that new pushes trigger correctly)
  - [ ] Verify auto-restart works (manually stop a service, check it restarts)
  - [ ] Test rollback once more manually

---

## 🎯 Troubleshooting During Setup

### Docker Compose Files Not Found
```bash
# Solution:
cd /opt/pravah
ls -la docker-compose.yml
# Should exist. If not, check setup-vm.sh output
```

### Services Won't Start
```bash
# Check logs:
docker compose logs --tail=50

# Check port conflicts:
sudo lsof -i :7000
sudo lsof -i :8000
sudo lsof -i :8600
sudo lsof -i :6379

# Restart docker:
sudo systemctl restart docker
docker compose up -d --profile prod
```

### CI/CD Deploy Fails
```bash
# Check GitHub Actions logs for specific error
# SSH into VM and check:
docker compose ps
docker compose logs -f

# If deployment script couldn't SSH:
ssh -i ~/.ssh/id_rsa ubuntu@your-vm-ip echo "test"
# If fails, verify SSH key secret in GitHub
```

### Rollback Doesn't Work
```bash
# Check backup exists:
ls -lh /opt/pravah-backup/

# Check rollback script:
bash /opt/pravah/scripts/rollback.sh

# Check logs:
tail -50 /var/log/pravah-rollback.log
```

---

## 📞 When to Escalate

- [ ] If Phase 1-3 fails → Contact GitHub support / Docker Hub support
- [ ] If Phase 4-8 fails → Contact VM provider / check VM logs
- [ ] If Phase 9 fails → Check GitHub Actions logs / local repo issues
- [ ] If Phase 10-12 fails → Check Docker Compose / service logic issues
- [ ] If Phase 13-14 fails → Security / networking issues

---

## ✅ Sign-Off

- [ ] All 15 phases completed
- [ ] All verifications passed
- [ ] Team trained
- [ ] Documentation in place
- [ ] Emergency procedures tested
- [ ] Ready for production

**Completed By:** _______________  
**Date:** _______________  
**Approved By:** _______________

---

**Document Version:** 1.0  
**Last Updated:** 2024
