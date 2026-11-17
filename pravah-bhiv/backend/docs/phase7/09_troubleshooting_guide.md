# Troubleshooting Guide
**Phase 7 — Documentation & Handover | Version 1.0.0**

---

## Quick Diagnosis Flow

```
Service down / error?
        │
        ├── docker compose ps  → Check container status
        ├── docker logs        → Check error messages
        ├── curl /api/health   → Check HTTP liveness
        └── verify_phase3.py   → Check journal integrity
```

---

## Issue Index

| # | Symptom | Section |
|---|---|---|
| 1 | Container not starting | §1 |
| 2 | `redis.exceptions.ConnectionError` | §2 |
| 3 | `hash_verification_failed:HASH_CHAIN` | §3 |
| 4 | `signatures_ok = False` in recovery | §4 |
| 5 | `governance_block` logged on every request | §5 |
| 6 | `Expected dict result from handle_external_event` | §6 |
| 7 | High memory / CPU | §7 |
| 8 | Telemetry shows `unreachable` health status | §8 |
| 9 | `OrderingViolation` in journal | §9 |
| 10 | 502 / 503 from control plane | §10 |

---

## §1 — Container Not Starting

**Symptom:** `docker compose ps` shows `Restarting` or `Exit 1`.

**Diagnosis:**
```bash
docker compose logs --tail=100 control-plane
```

**Common causes:**

| Error Message | Cause | Fix |
|---|---|---|
| `No module named 'control_plane'` | `PYTHONPATH` not set | Ensure `PYTHONPATH=/app` in compose env |
| `Address already in use` | Port 7000 occupied | `lsof -i :7000` → kill conflicting process |
| `SSPL_SECRET_KEY not set` | Missing env var | Add to `.env` file |
| `Permission denied: logs/` | Volume mount perms | `chmod -R 755 logs/` on host |

---

## §2 — Redis ConnectionError

**Symptom:** `redis.exceptions.ConnectionError` in logs.

**What happens:** Control plane auto-falls back to local `EventBus`. Autonomous operation **continues** without Redis.

**To verify fallback is active:**
```bash
docker compose logs control-plane | grep "EventBus\|fallback\|redis"
```

**To restore Redis:**
```bash
docker compose restart redis
# Wait ~10s for health check to pass
docker exec pravah-redis redis-cli ping
```

**Note:** The local EventBus does not persist events across restarts. Restore Redis before restarting the service if event continuity is required.

---

## §3 — Hash Chain Verification Failed

**Symptom:** `verify_phase3.py` outputs `FAIL` or `hash_verification_failed:HASH_CHAIN`.

**Immediate actions:**
```bash
# 1. STOP — do not write new events to the journal
# 2. Identify which sequence number failed
python verify_phase3.py 2>&1 | grep "seq"

# 3. View the raw journal entry at that sequence
python -c "
import json
with open('logs/control_plane/append_only_log.jsonl') as f:
    for i, line in enumerate(f):
        rec = json.loads(line)
        if rec.get('event', {}).get('sequence') == <seq>:
            print(json.dumps(rec, indent=2))
"
```

**Causes:**
- File was edited externally (text editor, logrotate truncation)
- Disk write error during append
- Security incident (unauthorized mutation)

**Resolution:**
- Restore from last known good snapshot + tail re-append
- If intentional audit trail is required, quarantine the journal and start a fresh one
- Alert security team if tamper is suspected

---

## §4 — `signatures_ok = False` in RecoveryValidator

**Symptom:** Recovery validation fails with `hash_verification_failed:HASH_CHAIN` even though hash chain is intact.

**Root cause:** `security.lineage_verifier.LineageVerifier.verify_lineage_signatures()` raised an exception. This happens when:
- Events were generated without HMAC/RSA signatures (test or dev environment)
- `LINEAGE_SIGNING_KEY` is not set

**In tests:** This is expected behavior — mock `verify_lineage_signatures` to return `None`:
```python
with patch("security.lineage_verifier.LineageVerifier.verify_lineage_signatures", return_value=None):
    result = RecoveryValidator(...).validate(...)
```

**In production:** Ensure `LINEAGE_SIGNING_KEY` is set and every event is signed at creation.

---

## §5 — `governance_block` on Every Request

**Symptom:** All agent cycles end with `governance_block`; no actions are executed.

**Diagnosis:**
```bash
docker compose logs control-plane | grep "governance_block\|block_reason"
```

**Common causes:**

| Block Type | Meaning | Fix |
|---|---|---|
| `cooldown` | Action executed too recently | Wait for cooldown window to expire |
| `repetition` | Same action repeated too many times | Diversify action mix; check decision brain |
| `eligibility` | Action not allowed in current FSM state | Check agent FSM state |
| `policy` | Governance policy violated | Review `ActionGovernance` policy config |
| `admission` | Resource or safety gate blocked | Check system resources |

**Emergency unblock:**
```bash
# Reset governance state (dev/stage only — not prod without approval)
docker exec pravah-control-plane python -c "
from control_plane.core.action_governance import ActionGovernance
g = ActionGovernance(env='dev')
g.reset_action_history()
print('Governance state reset')
"
```

---

## §6 — `handle_external_event` Returns Non-Dict

**Symptom:** `AssertionError: Expected dict result from handle_external_event` in tests.

**Root cause:** Governance blocked the action, setting `_last_decision = "noop"` (string). The method then returns a string instead of a dict.

**Fix (tests):** Mock `ActionGovernance.evaluate_action` to return an allowed decision:
```python
from control_plane.core.action_governance import GovernanceDecision
_allowed = GovernanceDecision(should_block=False, reason="test", legitimacy="LEGITIMATE_VALID")
with patch("control_plane.core.action_governance.ActionGovernance.evaluate_action", return_value=_allowed):
    result = runtime.handle_external_event(payload)
```

**Fix (production):** Investigate governance block reason per §5.

---

## §7 — High Memory / CPU

**Symptom:** Container reports `memory_utilization_pct > 90%` in telemetry.

**Quick checks:**
```bash
# Container resource usage
docker stats pravah-control-plane --no-stream

# Process list
docker exec pravah-control-plane top

# Redis memory
docker exec pravah-redis redis-cli info memory | grep used_memory_human
```

**Resolution:**
```bash
# Scale up Gunicorn workers
GUNICORN_WORKERS=2 docker compose up -d control-plane  # reduce if memory-bound

# Or add more RAM to VM

# Flush Redis if maxmemory is hit
docker exec pravah-redis redis-cli flushdb
```

---

## §8 — Telemetry Shows `unreachable` Health Status

**Symptom:** `health_endpoint_status: "unreachable"` in `telemetry.json`.

**Cause:** `TelemetryCollector` calls `http://127.0.0.1:8000/health` (decision brain port). If the decision brain is down, this returns `unreachable`.

**Diagnosis:**
```bash
curl http://localhost:8000/health
docker compose ps decision-brain
docker compose logs decision-brain
```

**This does NOT stop control plane operation** — the system continues with the local EventBus and last known decision.

---

## §9 — `OrderingViolation` in Journal

**Symptom:** `OrderingViolation` raised when appending to journal.

**Cause:** A duplicate sequence number was attempted (concurrent write bug or replay of old events).

**Diagnosis:**
```bash
# Check the last valid sequence for the execution
python -c "
from control_plane.persistence.append_only_log import AppendOnlyLog
log = AppendOnlyLog()
events = log.get_execution_events('<execution_id>')
print('Last seq:', events[-1].sequence if events else 'none')
"
```

**Resolution:**
- In the code: always read `_execution_sequences[execution_id]` before appending
- Do not replay or manually insert journal entries

---

## §10 — 502 / 503 from Control Plane

**Symptom:** Nginx or load balancer returns `502 Bad Gateway` or `503 Service Unavailable`.

**Diagnosis path:**
```bash
# 1. Is the container running?
docker compose ps control-plane

# 2. Is Gunicorn responding internally?
docker exec pravah-control-plane curl -s http://localhost:7000/api/health

# 3. Check worker count (should be > 0)
docker exec pravah-control-plane ps aux | grep gunicorn

# 4. Check for OOM kills
dmesg | grep -i "killed process"
```

**Common fixes:**

| Cause | Fix |
|---|---|
| All Gunicorn workers OOM killed | Increase `GUNICORN_WORKERS` memory limit or add RAM |
| Startup validation failed | Check startup validator output and fix missing artifacts |
| Port conflict | `lsof -i :7000` → kill conflicting process |
| Gunicorn timeout | Increase `--timeout 120` for slow RL inference |

---

## Useful One-Liners

```bash
# Last 5 agent decisions
docker exec pravah-control-plane cat logs/agent.log | grep "decision" | tail -5 | jq .

# All governance blocks in last hour
docker compose logs --since=1h control-plane | grep governance_block

# Journal record count
wc -l logs/control_plane/append_only_log.jsonl

# Replay index summary
cat data/replay_index.json | jq 'to_entries | length'

# Active trace IDs in telemetry stream
docker compose logs --tail=100 control-plane | grep trace_id | jq -r '.trace_id' | sort -u
```
