# Pravah Production Deployment Guide
**Target Platform**: Yotta Bare-Metal VM (Docker Compose + systemd)  
**Staging**: Render.com (maintained during migration)  
**Production**: Yotta Cloud (India) — D1 Compute

---

## Architecture Overview

```
                          ┌─────────────────────────────────┐
                          │       Yotta Bare-Metal VM        │
                          │                                  │
  ┌──────────────┐        │  ┌─────────────────────────┐    │
  │  Observed    │ ◄──────┼──│   Observer (port 8600)   │    │
  │  Services    │        │  │   FastAPI / Uvicorn      │    │
  │  (20+ apps)  │        │  └────────────┬────────────┘    │
  └──────────────┘        │               │ observes         │
                          │  ┌────────────▼────────────┐    │
  ┌──────────────┐        │  │  Control Plane (7000)   │    │
  │  Telemetry   │ ───────┼─►│  Flask / Gunicorn       │    │
  │  Push        │        │  └────────────┬────────────┘    │
  └──────────────┘        │               │                  │
                          │  ┌────────────▼────────────┐    │
  ┌──────────────┐        │  │ Decision Brain (8000)    │    │
  │  Prometheus  │ ◄──────┼──│  FastAPI / Uvicorn       │    │
  │  (9090)      │        │  └────────────┬────────────┘    │
  └──────────────┘        │               │                  │
                          │  ┌────────────▼────────────┐    │
                          │  │  Redis Event Bus (6379)  │    │
                          │  │  (loopback-bound)        │    │
                          │  └─────────────────────────┘    │
                          │                                  │
                          │  ┌─────────────────────────┐    │
                          │  │  Deploy Workers (x3)     │    │
                          │  │  Queue Monitor           │    │
                          │  │  Health Monitor          │    │
                          │  └─────────────────────────┘    │
                          └─────────────────────────────────┘
```

---

## Pre-Deployment Checklist

### Secrets & Environment

- [ ] Generate production `SSPL_SECRET_KEY` (min 32 bytes, random):
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
- [ ] Generate `JWT_SECRET_KEY`
- [ ] Replace **all** `##SECRET:*##` placeholders in `environments/prod.env`
- [ ] Replace **all** `##YOTTA_URL:*##` placeholders with real service endpoints
- [ ] Confirm `DEMO_MODE=false` and `DEMO_FREEZE_MODE=false`

### Infrastructure

- [ ] Docker Engine ≥ 24.x installed on Yotta VM
- [ ] Docker Compose plugin ≥ 2.20 installed (`docker compose version`)
- [ ] VM has minimum **4 vCPU / 8 GB RAM** for full production stack
- [ ] Ports **7000, 8000, 8600** accessible (firewall / security group rules configured)
- [ ] Port **6379** (Redis) bound to loopback only — **do not expose externally**
- [ ] Port **9090** (Prometheus) bound to loopback — expose via reverse proxy (nginx/caddy) if needed
- [ ] `/opt/pravah/` directory created with correct ownership
- [ ] Log volume directories pre-created: `mkdir -p /opt/pravah/pravah-bhiv/backend/logs`

### Code

- [ ] Repository cloned to `/opt/pravah/pravah-bhiv` (or symlinked)
- [ ] Git branch set to production-release tag
- [ ] `environments/prod.env` has zero `##` placeholders remaining

---

## Deployment Procedure

### Step 1 — Clone & Configure

```bash
# On Yotta VM as root or privileged user
git clone https://github.com/IamShivamPal/pravah-int.git /opt/pravah/pravah-bhiv
cd /opt/pravah/pravah-bhiv/backend

# Edit prod.env and fill in all placeholder values
nano environments/prod.env

# Verify no placeholders remain
grep -c "##" environments/prod.env
# Expected output: 0
```

### Step 2 — Build Docker Images

```bash
cd /opt/pravah/pravah-bhiv/backend

docker compose -f ../yotta-deploy.yaml \
  --env-file environments/prod.env \
  build --pull
```

### Step 3 — Install systemd Service

```bash
cp /opt/pravah/pravah-bhiv/pravah.service /etc/systemd/system/pravah.service
chmod +x /opt/pravah/pravah-bhiv/backend/scripts/start_prod_services.sh
systemctl daemon-reload
systemctl enable pravah.service
```

### Step 4 — Start Production Stack

```bash
# Start via systemd (recommended — survives VM reboots)
systemctl start pravah.service

# -- OR -- start manually for first-time validation
cd /opt/pravah/pravah-bhiv/backend
./scripts/start_prod_services.sh start
```

### Step 5 — Post-Deployment Health Validation

```bash
cd /opt/pravah/pravah-bhiv/backend
python3 scripts/validate_prod_health.py \
  --env prod \
  --output deployment_verification_packet/prod_runtime_health.json

# Review the proof file
cat deployment_verification_packet/prod_runtime_health.json | python3 -m json.tool
```

Expected output (all PASS):
```
  Overall Verdict: PASS
  Proof written -> deployment_verification_packet/prod_runtime_health.json
```

### Step 6 — Verify Prometheus Scraping

```bash
# From VM (Prometheus is loopback-bound)
curl http://localhost:9090/api/v1/targets | python3 -m json.tool
```

All three targets (`pravah-control-plane`, `pravah-decision-brain`, `pravah-observer`) should show `"health": "up"`.

---

## Service Endpoints Reference

| Service | Port | Health URL | Purpose |
|---|---|---|---|
| Control Plane | 7000 | `GET /api/health` | Agent API, registry, decisions |
| Decision Brain | 8000 | `GET /health` | Policy engine, telemetry ingestion |
| Observer | 8600 | `GET /health` | Passive service health dashboard |
| Observer API | 8600 | `GET /api/status` | Polling status + observed services |
| Observer Metrics | 8600 | `GET /api/metrics` | Prometheus text format |
| Redis | 6379 | TCP ping | Event bus (loopback only) |
| Prometheus | 9090 | `GET /-/healthy` | Metrics scraper (loopback only) |

---

## Service Dependency Order

Boot sequence (enforced by both Docker Compose `depends_on` and the startup script):

```
Redis  →  Control Plane  →  Decision Brain  →  Observer
           ↓                                    
    Deploy Workers (x3)
    Queue Monitor
    Health Monitor
    Prometheus
```

Shutdown sequence (reverse):
```
Prometheus  →  Workers  →  Observer  →  Decision Brain  →  Control Plane  →  Redis
```

---

## Managing the Stack

```bash
# Status
systemctl status pravah.service
# -- OR --
./scripts/start_prod_services.sh status

# Live logs — all services
./scripts/start_prod_services.sh logs

# Live logs — specific service
./scripts/start_prod_services.sh logs control-plane

# Graceful restart
systemctl restart pravah.service
# -- OR --
./scripts/start_prod_services.sh restart

# Run health check only (generates proof)
./scripts/start_prod_services.sh health

# Stop all
systemctl stop pravah.service
```

---

## Rollback Procedure

If a deployment fails health checks:

```bash
# 1. Stop current stack
systemctl stop pravah.service

# 2. Roll back to previous git tag
cd /opt/pravah/pravah-bhiv
git checkout <previous-release-tag>

# 3. Rebuild images from previous code
cd backend
docker compose -f ../yotta-deploy.yaml --env-file environments/prod.env build --pull

# 4. Restart
systemctl start pravah.service

# 5. Re-validate
python3 scripts/validate_prod_health.py --env prod \
  --output deployment_verification_packet/prod_runtime_health.json
```

---

## Staging (Render.com) — Maintained During Migration

The `render.yaml` in `pravah-bhiv/` remains active for staging validation. Staging uses:

- `DEMO_MODE=true` (safe for external review)
- Single-worker Uvicorn
- Render's native port injection (`$PORT`)

To validate staging before promoting to production:
1. Deploy PR branch to Render staging
2. Confirm `/health` and `/api/health` respond correctly
3. Promote tag to Yotta production deployment

---

## Monitoring & Alerting

### Prometheus Targets

Access Prometheus UI (on VM):
```bash
curl http://localhost:9090/-/ready
```

Current scrape jobs (from `monitoring/prometheus.yml`):
- `pravah-control-plane` — scrapes `:7000/metrics` every 15s
- `pravah-decision-brain` — scrapes `:8000/metrics` every 15s
- `pravah-observer` — scrapes `:8600/api/metrics` every 15s (Prometheus text format)

### Key Observer Metrics

| Metric | Type | Description |
|---|---|---|
| `observer_poll_count_total` | counter | Total polling loops run |
| `observer_monitored_services_total` | gauge | Number of observed services |
| `observer_healthy_services_total` | gauge | Currently healthy services |
| `observer_degraded_services_total` | gauge | Currently degraded services |

---

## Log Management

All logs use Docker's `json-file` driver with rotation:

| Service | Max Size | Max Files |
|---|---|---|
| Control Plane | 100 MB × 10 = 1 GB | 10 |
| Decision Brain | 100 MB × 10 = 1 GB | 10 |
| Observer | 50 MB × 5 = 250 MB | 5 |
| Redis | 50 MB × 5 = 250 MB | 5 |
| Prometheus | 20 MB × 3 = 60 MB | 3 |

View logs:
```bash
docker logs pravah-control-plane --tail 100 -f
docker logs pravah-observer --tail 100 -f
```

---

## Resource Requirements (Yotta VM Sizing)

| Service | CPU Limit | Memory Limit |
|---|---|---|
| Redis | 0.5 | 640 MB |
| Control Plane | 2.0 | 1 GB |
| Decision Brain | 2.0 | 1 GB |
| Observer | 1.0 | 512 MB |
| Workers (x3) | 1.0 each | 512 MB each |
| Prometheus | 0.5 | 512 MB |
| **Total** | **~10 vCPU** | **~6 GB** |

**Recommended Yotta VM**: 16 vCPU / 16 GB RAM (leaves headroom for observed services co-located on same VM).

---

## Security Notes

1. **Redis**: Bound to loopback (`127.0.0.1:6379`) — never expose port 6379 on public interface
2. **Prometheus**: Bound to loopback (`127.0.0.1:9090`) — expose via authenticated reverse proxy only
3. **SSPL_SECRET_KEY**: Must be injected via Yotta Secrets Manager — never committed to VCS
4. **CORS**: Set `BACKEND_CORS_ORIGINS` to specific production domain only
5. **Firewall**: Only ports 7000, 8000, 8600 should be externally accessible

---

## Deployment Evidence

Post-deployment proof artifacts are stored in:

```
backend/deployment_verification_packet/
├── prod_runtime_health.json       ← Generated by validate_prod_health.py
├── phase6_summary.json            ← Phase 6 resilience proofs
├── dependency_loss_proof.log      ← Redis fallback validation
├── replay_proof.log               ← Replay correctness validation
├── schema_discipline_proof.log    ← Contract enforcement validation
├── observability_proof.log        ← Observer consistency validation
└── hash_verification.log          ← Cryptographic integrity checks
```

The `prod_runtime_health.json` file is the primary deployment evidence artifact for Yotta production, replacing all local demo evidence.
