# Pravah-BHIV Deployment Guide
**Phase 7 — Documentation & Handover | Version 1.0.0**

---

## 1. Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Docker Engine | 24.x | 26.x |
| Docker Compose | 2.20 | 2.29 |
| Python | 3.11 | 3.14 |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 50 GB |
| OS | Ubuntu 22.04 | Ubuntu 24.04 / Windows 11 |

### Required Environment Variables

Copy `.env.example` to `.env` and populate all mandatory keys:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `ENVIRONMENT` | ✅ | `dev` | Runtime env: `dev` / `stage` / `prod` |
| `SSPL_SECRET_KEY` | ✅ | `dev-key` | Signed-sovereignty proof key |
| `LINEAGE_SIGNING_KEY` | ✅ | `dev-key` | Hash-chain signing key |
| `REDIS_HOST` | ✅ | `redis` | Redis service host |
| `REDIS_PORT` | — | `6380` | Host-side Redis port |
| `REDIS_DB` | — | `2` | Redis database index |
| `GUNICORN_WORKERS` | — | `4` | Worker process count |
| `DECISION_BRAIN_PORT` | — | `8000` | Internal decision-brain port |
| `AUTONOMY_DECISIONS_ENABLED` | — | `true` | Enable autonomous RL decisions |
| `AUTONOMY_LEARNING_ENABLED` | — | `false` | Enable live RL training |
| `EMERGENCY_FREEZE_ENABLED` | — | `false` | Emergency governance freeze |

---

## 2. Service Topology

```
Host (VM / bare-metal)
│
├── pravah-redis         :6380  → Redis Event Bus
├── pravah-control-plane :7000  → Control Plane API (Gunicorn/Flask)
├── pravah-decision-brain:8000  → Decision Brain (RL Engine)
├── pravah-observer      :8080  → Observer / Telemetry Server
└── pravah-tantra-stream :9000  → TANTRA Event Stream (WebSocket)
```

---

## 3. Quick Start (Development)

```bash
# 1. Clone and enter backend
cd backend

# 2. Configure environment
cp .env.example .env
# Edit .env — set SSPL_SECRET_KEY and LINEAGE_SIGNING_KEY at minimum

# 3. Start all dev services
docker compose --profile dev up -d

# 4. Verify all containers healthy
docker compose ps

# 5. Smoke-test the health endpoint
curl http://localhost:7000/api/health
```

Expected response:
```json
{"status": "healthy", "env": "dev", "version": "1.0.0"}
```

---

## 4. Production Deployment (Yotta VM)

```bash
# 1. Pull latest SHA-tagged images (never use :latest in prod)
docker compose --profile prod pull

# 2. Start with production profile
docker compose --profile prod up -d --remove-orphans

# 3. Verify startup validators pass
docker exec pravah-control-plane python -c "
from control_plane.deployment.startup_validator import StartupValidator
r = StartupValidator().validate()
print('READY' if r.ready else 'NOT READY', r.failures)
"

# 4. Verify full lineage
docker exec pravah-control-plane python verify_phase3.py
```

---

## 5. Startup Validation Gates

The system enforces **four sequential gates** before serving traffic:

| Gate | Phase | Check |
|---|---|---|
| 1 | Signed Lineage | `LINEAGE_SIGNING_KEY` set; proof packet present |
| 2 | Policy Engine | `ActionGovernance` loads without error |
| 3 | Persistence | `append_only_log.jsonl` + `replay_index.json` exist |
| 4 | Semantic Guard | `SelfRestraint` module loads without error |

`ReadinessValidator` blocks HTTP traffic until **all four gates pass**.

---

## 6. Systemd Service (Bare-Metal VM)

```bash
# Install the provided systemd unit
sudo cp pravah-compose.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pravah-compose
sudo systemctl start pravah-compose

# Check status
sudo systemctl status pravah-compose
```

---

## 7. Rollback Procedure

```bash
# 1. Stop current stack
docker compose down

# 2. Roll back to previous SHA tag
export CONTROL_PLANE_IMAGE=pravah-control-plane:<prev-sha>
docker compose --profile prod up -d

# 3. Verify journal integrity (no hash-chain break from rollback)
python verify_phase3.py

# 4. If hash-chain is broken, replay from last good snapshot
python -c "
from control_plane.deployment.recovery_validator import RecoveryValidator
r = RecoveryValidator().validate('<execution_id>')
print(r.status, r.failures)
"
```

---

## 8. Health Endpoints

| Endpoint | Port | Description |
|---|---|---|
| `GET /api/health` | 7000 | Control-plane liveness |
| `GET /api/status` | 7000 | Agent state + loop count |
| `GET /api/metrics` | 7000 | Telemetry snapshot |
| `GET /health` | 8000 | Decision-brain liveness |
| `GET /health` | 8080 | Observer liveness |
