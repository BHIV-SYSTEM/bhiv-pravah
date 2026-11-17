# 🔌 Port Mapping Configuration Guide

## Problem
Your VM has these ports already in use:
```
80, 443, 3000, 3001, 3002, 3003, 3004, 3005, 5000, 5001, 5002, 5173, 5174, 5175,
5432, 5433, 6379, 8000, 8001, 8002, 8003, 8004, 8005, 8006, 8008, 8080, 8081, 8082,
8083, 8084, 8085, 8103, 8444, 9000, 9001, 9002, 9003, 9090, 9091, 9092, 9443, 27017,
27018, 30303, 30304, 30305, 30306, 30307
```

## Solution
Pravah services have been automatically remapped to available ports:

---

## 📊 Port Mapping (Original → Used)

| Service | Original Port | Used Port | Protocol | Purpose |
|---------|---------------|-----------|----------|---------|
| Redis | 6379 | **6380** | TCP | Event Bus |
| Control Plane | 7000 | **7001** | HTTP | Flask API |
| Decision Brain | 8000 | **8001** | HTTP | FastAPI |
| Observer | 8600 | **8602** | HTTP | Health Monitoring |
| Prometheus | 9090 | **9091** | HTTP | Metrics |

**Internal Container Ports** (inside docker network - DO NOT CHANGE):
- Redis: 6379 (internal)
- Control Plane: 7000 (internal)
- Decision Brain: 8000 (internal)
- Observer: 8600 (internal)
- Prometheus: 9090 (internal)

---

## 🔧 How It Works

### Container Perspective (Always the same)
```yaml
# Inside container - services listen on these ports
redis-cli ping                    # 6379
Control Plane: http://localhost:7000/api/health
Decision Brain: http://localhost:8000/health
Observer: http://localhost:8600/health
Prometheus: http://localhost:9090
```

### Host/External Perspective (What changed)
```
Outside VM - you connect to these ports
http://your-vm-ip:6380    → redis (6379 in container)
http://your-vm-ip:7001    → control-plane (7000 in container)
http://your-vm-ip:8001    → decision-brain (8000 in container)
http://your-vm-ip:8602    → observer (8600 in container)
http://your-vm-ip:9091    → prometheus (9090 in container)
```

---

## 📋 Configuration Details

### In docker-compose.yml
```yaml
services:
  control-plane:
    ports:
      - "${CONTROL_PLANE_PORT:-7001}:7000"
      #  HOST:VM               CONTAINER:PORT
```

**Translation:**
- `7001` - External port (what you use from outside)
- `7000` - Internal container port (inside docker)

### In .env File
```bash
# On VM: /opt/pravah/.env

# Service Port Configuration
CONTROL_PLANE_PORT=7001      # External port
DECISION_BRAIN_PORT=8001     # External port
OBSERVER_PORT=8602           # External port
REDIS_PORT=6380              # External port

# Internal port (inside container) - DO NOT CHANGE
REDIS_HOST=redis             # Use service DNS name
REDIS_PORT=6379              # Internal port (stays same)
```

---

## 🔑 GitHub Secrets (Updated)

You now need 7 secrets instead of 5:

```
DOCKER_HUB_USERNAME       ← Your Docker Hub username
DOCKER_HUB_PASSWORD       ← Your Docker Hub password or token
PROD_VM_HOST              ← Your VM public IP
PROD_VM_USER              ← SSH username (ubuntu)
PROD_VM_SSH_KEY           ← SSH private key
PROD_VM_PORT              ← SSH port (optional, default 22)
```

**New secrets:**
- `DOCKER_HUB_PASSWORD` - Your Docker Hub password or personal access token

---

## ✅ Verification Commands

### Check which ports are being used
```bash
# On VM
sudo lsof -i :6380  # Should show: docker (redis)
sudo lsof -i :7001  # Should show: docker (control-plane)
sudo lsof -i :8001  # Should show: docker (decision-brain)
sudo lsof -i :8602  # Should show: docker (observer)
sudo lsof -i :9091  # Should show: docker (prometheus)
```

### Test services from inside VM
```bash
docker compose ps

# Access from VM itself
curl http://localhost:7001/api/health    # Control Plane (external)
docker exec pravah-control-plane curl http://localhost:7000/api/health  # Internal
```

### Test services from outside VM
```bash
# From your local machine
curl http://your-vm-ip:7001/api/health
curl http://your-vm-ip:8001/health
curl http://your-vm-ip:8602/health
curl http://your-vm-ip:9091
```

---

## 🔄 How the Docker Port Mapping Works

```
┌─────────────────────────────────────────────────────────────────┐
│ Your Local Machine                                              │
│                                                                 │
│ curl http://vm-ip:7001                                         │
│                 ↓                                               │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ Your VM (Linux)                                            │ │
│ │                                                            │ │
│ │ Network Traffic arrives on port 7001                      │ │
│ │                 ↓                                          │ │
│ │ Docker intercepts: 7001 → 7000                           │ │
│ │                 ↓                                          │ │
│ │ ┌──────────────────────────────────────────────────────┐  │ │
│ │ │ Docker Container (pravah-control-plane)             │  │ │
│ │ │                                                      │  │ │
│ │ │ Flask listening on 0.0.0.0:7000                    │  │ │
│ │ │                                                      │  │ │
│ │ │ curl http://localhost:7000 (from inside)           │  │ │
│ │ │           ↑                                          │  │ │
│ │ │ (same request, same service)                        │  │ │
│ │ └──────────────────────────────────────────────────────┘  │ │
│ │                                                            │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Finding Available Ports

If 6380, 7001, 8001, 8602, 9091 are also in use, find alternatives:

```bash
# On VM, check which ports are free
for port in 6380 6381 6382 7001 7002 7003 8001 8002 8003 8602 8603 8604 9091 9092 9093; do
  if ! sudo lsof -i :$port > /dev/null 2>&1; then
    echo "Port $port is AVAILABLE"
  fi
done
```

Then update in `.env`:
```bash
REDIS_PORT=6381          # Change if 6380 in use
CONTROL_PLANE_PORT=7002  # Change if 7001 in use
DECISION_BRAIN_PORT=8002 # Change if 8001 in use
OBSERVER_PORT=8603       # Change if 8602 in use
# Prometheus runs internally, edit docker-compose.yml if needed
```

---

## 📝 Update docker-compose.yml if Needed

Edit the ports section:

```yaml
redis:
  ports:
    - "6381:6379"  # Change 6381 if needed

control-plane:
  ports:
    - "7002:7000"  # Change 7002 if needed

decision-brain:
  ports:
    - "8002:8000"  # Change 8002 if needed

observer:
  ports:
    - "8603:8600"  # Change 8603 if needed

prometheus:
  ports:
    - "9092:9090"  # Change 9092 if needed
```

Then restart:
```bash
docker compose down
docker compose --profile prod up -d
```

---

## 🔒 Security Note

**Keep internal ports fixed:**
- Internal services communicate via Docker DNS (service names)
- Example: `REDIS_HOST=redis` and `REDIS_PORT=6379` (internal)
- Only EXTERNAL ports (7001, 8001, 8602, 9091) should be changed

**Never expose Redis to internet:**
```bash
# WRONG - exposes Redis to internet
redis:
  ports:
    - "6380:6379"  # If 6380 is open to internet!

# RIGHT - keep Redis internal only
redis:
  ports: []  # No external port exposed
  # Access only via docker service name internally
```

In our config, Redis is exposed for debugging. In production, remove it:
```yaml
redis:
  # Remove ports section - not exposed externally
  # Services access via: REDIS_HOST=redis (internal DNS)
```

---

## 🚀 Access Points After Deployment

```
Control Plane:   http://your-vm-ip:7001/api/health
Decision Brain:  http://your-vm-ip:8001/health
Observer:        http://your-vm-ip:8602/health
Prometheus:      http://your-vm-ip:9091
Redis CLI:       redis-cli -p 6380 ping
```

---

## 📊 Docker Compose Port Format

**Format:** `"HOST_PORT:CONTAINER_PORT"`

```yaml
ports:
  - "6380:6379"      # External:Internal
```

**Meaning:**
- `6380` = External port (what you use from outside)
- `6379` = Internal port (service listens inside container)

**Why both?**
- Containers need to communicate internally (6379)
- External clients connect via host port (6380)
- Allows multiple containers with same internal port

---

## ✅ Checklist

- [ ] Verify ports in docker-compose.yml (6380, 7001, 8001, 8602, 9091)
- [ ] Check if those ports are available: `sudo lsof -i :PORT`
- [ ] Add DOCKER_HUB_PASSWORD secret to GitHub
- [ ] Update .env on VM with Docker Hub credentials
- [ ] Test connectivity: `curl http://vm-ip:7001`
- [ ] Restart services: `docker compose down && docker compose --profile prod up -d`
- [ ] Verify all services running: `docker compose ps`

---

## 📞 Troubleshooting

**"Address already in use"**
```bash
# Find which process is using the port
sudo lsof -i :7001
# Kill it or choose different port
```

**"Connection refused"**
```bash
# Check if service is running
docker compose ps control-plane
# Check logs
docker compose logs control-plane
```

**"Cannot connect from outside VM"**
```bash
# Check firewall allows the port
sudo ufw allow 7001/tcp
# Test locally first
curl http://localhost:7001
```

---

## 🎯 Summary

- **Original ports in code**: 6379, 7000, 8000, 8600, 9090
- **Remapped to available ports**: 6380, 7001, 8001, 8602, 9091
- **Internal communication**: Unchanged (via Docker DNS)
- **External access**: Via remapped ports
- **GitHub secrets**: Added DOCKER_HUB_PASSWORD
- **env file**: Updated with Docker Hub credentials

All changes are in:
- `docker-compose.yml` (port mappings)
- `.github/workflows/ci.yml` (Docker login)
- `.env.example` (Docker credentials)

---

**Version:** 1.0
**Created:** 2024
