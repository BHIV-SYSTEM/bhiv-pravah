# VM Configuration Guide
**Phase 7 — Documentation & Handover | Version 1.0.0**

---

## 1. Recommended VM Specifications (Yotta Cloud)

| Parameter | Development | Staging | Production |
|---|---|---|---|
| vCPU | 2 | 4 | 8 |
| RAM | 4 GB | 8 GB | 16 GB |
| Disk (SSD) | 40 GB | 100 GB | 200 GB |
| Network | 100 Mbps | 1 Gbps | 10 Gbps |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

---

## 2. System Packages

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose v2
sudo apt-get install -y docker-compose-plugin

# Install Python 3.11+
sudo apt-get install -y python3.11 python3.11-venv python3-pip

# Install monitoring tools
sudo apt-get install -y htop iotop net-tools curl jq
```

---

## 3. Directory Layout on VM

```
/app/                          ← Docker WORKDIR (mounted from repo)
├── agent_runtime.py           ← AgentRuntime main entry
├── wsgi.py                    ← Gunicorn WSGI entry
├── control_plane/             ← Control plane modules
├── decision_brain/            ← RL decision engine
├── logs/                      ← Persistent log volume (docker: ./logs:/app/logs)
│   ├── access.log
│   ├── error.log
│   ├── control_plane/
│   │   └── append_only_log.jsonl   ← Immutable journal
│   └── agent/
│       ├── agent_state_<id>.json
│       └── memory_snapshot_<id>.json
├── data/                      ← Persistent data volume (docker: ./data:/app/data)
│   ├── bucket/                ← Certified execution artifacts
│   ├── replay_index.json      ← Replay index
│   └── snapshots/             ← State snapshots
└── proofs/                    ← Deployment proof packets
```

---

## 4. Port Mapping

| Service | Container Port | Host Port (default) | Protocol |
|---|---|---|---|
| Redis | 6379 | 6380 | TCP |
| Control Plane | 7000 | 7000 | HTTP |
| Decision Brain | 8000 | 8000 | HTTP |
| Observer | 8080 | 8080 | HTTP + WS |
| TANTRA Stream | 9000 | 9000 | WebSocket |

> **Firewall rule:** Only ports 7000 and 8080 should be externally accessible. All other ports should be restricted to the internal Docker network (`pravah-network`).

---

## 5. Redis Configuration

```bash
# Redis is started with these flags (from docker-compose.yml):
redis-server \
  --appendonly yes \
  --maxmemory 512mb \
  --maxmemory-policy allkeys-lru \
  --save 60 1000 \
  --loglevel notice
```

| Parameter | Value | Reason |
|---|---|---|
| `appendonly yes` | enabled | Durable event persistence |
| `maxmemory` | 512 MB | Prevents OOM on shared VMs |
| `maxmemory-policy` | allkeys-lru | Event bus eviction policy |
| `save 60 1000` | 60s / 1000 writes | Snapshot frequency |

---

## 6. Gunicorn Configuration (Control Plane)

```bash
gunicorn wsgi:app \
  --workers 4 \
  --worker-class sync \
  --bind 0.0.0.0:7000 \
  --timeout 120 \
  --keep-alive 5 \
  --access-logfile /app/logs/access.log \
  --error-logfile /app/logs/error.log \
  --log-level info
```

| Parameter | Value | Notes |
|---|---|---|
| `--workers` | 4 | `(2 × vCPU) + 1` formula |
| `--worker-class` | sync | Default; use `gevent` for I/O-heavy workloads |
| `--timeout` | 120s | Accounts for RL inference latency |
| `--keep-alive` | 5s | Connection reuse for health checkers |

---

## 7. Log Rotation

```bash
# /etc/logrotate.d/pravah
/app/logs/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    sharedscripts
    postrotate
        docker exec pravah-control-plane kill -USR1 1
    endscript
}

/app/logs/control_plane/append_only_log.jsonl {
    # NEVER rotate the journal — it is immutable and sovereign
    missingok
    notifempty
    nocreate
}
```

> ⚠️ **Critical:** The `append_only_log.jsonl` must **never** be rotated, truncated, or deleted. It is the source of truth for all replay and certification operations.

---

## 8. Environment Variable Security

```bash
# Store secrets in VM-level environment (not in .env file in prod)
sudo vi /etc/environment
# Add:
SSPL_SECRET_KEY="<strong-random-key>"
LINEAGE_SIGNING_KEY="<strong-random-key>"

# Or use Docker secrets (recommended for multi-node)
docker secret create sspl_secret_key ./sspl_key.txt
docker secret create lineage_signing_key ./lineage_key.txt
```

---

## 9. VM Health Checks

```bash
# Full system health sweep
#!/bin/bash
echo "=== Docker Services ==="
docker compose ps

echo "=== Control Plane API ==="
curl -s http://localhost:7000/api/health | jq .

echo "=== Redis Ping ==="
docker exec pravah-redis redis-cli ping

echo "=== Journal Integrity ==="
docker exec pravah-control-plane python verify_phase3.py

echo "=== Disk Usage ==="
df -h /app/logs /app/data
```
