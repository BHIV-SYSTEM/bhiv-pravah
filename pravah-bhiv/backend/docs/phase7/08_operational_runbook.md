# Operational Runbook
**Phase 7 — Documentation & Handover | Version 1.0.0**

---

## 1. Daily Operations Checklist

```bash
# Morning health sweep (run as cron: 0 9 * * *)

#!/bin/bash
DATE=$(date +%Y-%m-%d)
LOG="/app/logs/ops/daily_check_${DATE}.log"

echo "=== Daily Health Check ${DATE} ===" | tee $LOG

# 1. Container status
echo "[1] Container Status:" | tee -a $LOG
docker compose ps | tee -a $LOG

# 2. API health
echo "[2] Control Plane API:" | tee -a $LOG
curl -s http://localhost:7000/api/health | jq . | tee -a $LOG

# 3. Redis ping
echo "[3] Redis:" | tee -a $LOG
docker exec pravah-redis redis-cli ping | tee -a $LOG

# 4. Journal integrity
echo "[4] Journal Integrity:" | tee -a $LOG
docker exec pravah-control-plane python verify_phase3.py 2>&1 | tee -a $LOG

# 5. Disk usage
echo "[5] Disk Usage:" | tee -a $LOG
df -h /app/logs /app/data | tee -a $LOG

# 6. Journal size
echo "[6] Journal Size:" | tee -a $LOG
ls -lh /app/logs/control_plane/append_only_log.jsonl | tee -a $LOG

echo "=== Check Complete ===" | tee -a $LOG
```

---

## 2. Service Management

### Start All Services
```bash
docker compose --profile prod up -d
```

### Stop All Services (graceful)
```bash
docker compose down
```

### Restart Specific Service
```bash
docker compose restart control-plane
docker compose restart redis
```

### View Logs
```bash
# Live logs
docker compose logs -f control-plane

# Last 200 lines
docker compose logs --tail=200 control-plane

# Agent-specific logs
tail -f /app/logs/agent.log | grep "agent-t6"
```

---

## 3. Scaling Operations

### Scale Up Workers
```bash
# Via environment variable (requires restart)
GUNICORN_WORKERS=8 docker compose up -d control-plane

# Check current workers
docker exec pravah-control-plane ps aux | grep gunicorn | wc -l
```

### Scale Down Workers
```bash
GUNICORN_WORKERS=2 docker compose up -d control-plane
```

### Emergency Freeze (halt all autonomous actions)
```bash
# Set environment variable and restart
EMERGENCY_FREEZE_ENABLED=true docker compose up -d control-plane

# Verify freeze is active
curl http://localhost:7000/api/status | jq '.governance.freeze_active'
```

---

## 4. Recovery Procedures

### Procedure 1: Restart After Crash

```bash
# 1. Check last known state
cat /app/logs/agent/agent_state_*.json | jq .

# 2. Verify journal integrity
docker exec pravah-control-plane python verify_phase3.py

# 3. Run recovery validator
docker exec pravah-control-plane python -c "
from control_plane.deployment.recovery_validator import RecoveryValidator
r = RecoveryValidator().validate('<execution_id>')
print('Status:', r.status)
print('State hash:', r.state_hash)
"

# 4. If recovery passes, restart service
docker compose restart control-plane

# 5. Verify startup validators pass
curl http://localhost:7000/api/health
```

### Procedure 2: Redis Failure Recovery

```bash
# 1. Check Redis status
docker exec pravah-redis redis-cli ping

# 2. If unreachable, restart Redis
docker compose restart redis

# 3. Control plane will auto-fallback to local EventBus
# Verify fallback is active:
docker compose logs --tail=50 control-plane | grep "EventBus"

# 4. Once Redis recovers, events will auto-reconnect
# No manual intervention required for the local bus fallback
```

### Procedure 3: Hash Chain Corruption

```bash
# STOP — do not restart the service

# 1. Identify corruption point
python verify_phase3.py 2>&1 | grep "FAIL"

# 2. Get last good snapshot
cat data/snapshot_registry.json | jq 'to_entries | sort_by(.value.at_sequence) | last'

# 3. Restore from last good snapshot (execution continues from that point)
# Journal entries after the last good snapshot are quarantined to:
cp logs/control_plane/append_only_log.jsonl \
   logs/control_plane/append_only_log.jsonl.corrupted.$(date +%s)

# 4. Alert security team — hash chain corruption is a potential security incident
echo "ALERT: Hash chain corruption detected at $(date)" | \
  mail -s "SECURITY: Journal Tamper Alert" ops@team.com
```

### Procedure 4: Disk Full

```bash
# 1. Check disk usage
df -h

# 2. Archive old logs (NOT the journal)
find /app/logs -name "*.log" -mtime +30 -exec gzip {} \;
find /app/logs -name "*.log.gz" -mtime +90 -exec mv {} /archive/ \;

# 3. NEVER touch:
# - /app/logs/control_plane/append_only_log.jsonl
# - /app/data/bucket/*.json (certified artifacts)
# - /app/data/replay_index.json
# - /app/data/snapshot_registry.json
```

---

## 5. Monitoring Thresholds

| Metric | Warning | Critical | Action |
|---|---|---|---|
| CPU % | > 70% | > 90% | `scale_up` |
| Memory % | > 75% | > 90% | `scale_up` / `restart` |
| Redis memory | > 400 MB | > 480 MB | Flush expired keys |
| Journal size | > 500 MB | > 1 GB | Archive + rotate non-journal logs |
| Error rate 15m | > 2% | > 10% | `alert` / `restart` |
| Validation score | < 0.7 | < 0.5 | `alert` / `freeze` |
| Latency p99 | > 500ms | > 2000ms | `scale_up` |

---

## 6. Cron Jobs

```bash
# /etc/cron.d/pravah
# Telemetry collection every 5 minutes
*/5 * * * * root docker exec pravah-control-plane python -m control_plane.telemetry.telemetry_collector

# Daily health check at 9 AM
0 9 * * * root /app/scripts/daily_health_check.sh >> /var/log/pravah_daily.log 2>&1

# Weekly journal integrity verification (Sunday 2 AM)
0 2 * * 0 root docker exec pravah-control-plane python verify_phase3.py >> /var/log/pravah_weekly_integrity.log 2>&1

# Log cleanup (keep 30 days of non-journal logs)
0 3 * * * root find /app/logs -name "*.log" -not -name "append_only_log*" -mtime +30 -delete
```

---

## 7. Deployment Workflow (CI/CD)

```
git push → GitHub Actions CI
    │
    ├── Run: pytest tests/
    ├── Run: pytest tests/test_phase6_vm_deployment.py (35 tests must pass)
    ├── Build: docker build -t pravah-control-plane:<sha>
    ├── Push: registry.example.com/pravah-control-plane:<sha>
    │
    └── Deploy:
         docker compose pull
         docker compose --profile prod up -d --remove-orphans
         curl http://localhost:7000/api/health  ← must return 200
         python verify_phase3.py               ← must return PASSED
```

---

## 8. Backup Policy

| Data | Backup Frequency | Retention | Method |
|---|---|---|---|
| `append_only_log.jsonl` | Continuous (append-only) | Forever | Replication / cloud object store |
| `replay_index.json` | On every update | 90 days | Daily snapshot |
| `snapshot_registry.json` | On every snapshot | 90 days | Daily backup |
| `data/bucket/*.json` | On write | Forever | Cloud object store |
| `logs/*.log` | Daily | 30 days | Compressed archive |
