# Replay Mapping
**Phase 7 — Documentation & Handover | Version 1.0.0**

---

## 1. Overview

Replay is the process of deterministically reconstructing the state of any execution from the append-only journal. It is the foundation of all crash recovery, audit, and certification operations.

---

## 2. Persistence Layer Components

```
┌───────────────────────────────────────────────────────────────────┐
│                    Replay Subsystem                               │
│                                                                   │
│  ┌─────────────────────────────────┐                             │
│  │       AppendOnlyLog             │  ← Source of Truth          │
│  │  logs/control_plane/            │                             │
│  │  append_only_log.jsonl          │                             │
│  └─────────────┬───────────────────┘                             │
│                │ read events by execution_id                      │
│                ▼                                                   │
│  ┌─────────────────────────────────┐                             │
│  │     HashLineageVerifier         │  ← Chain Integrity           │
│  │  verify_sequence_continuity()   │                             │
│  │  verify_hash_chain()            │                             │
│  │  compute_execution_state_hash() │                             │
│  └─────────────┬───────────────────┘                             │
│                │ state_hash                                        │
│                ▼                                                   │
│  ┌─────────────────────────────────┐                             │
│  │       ReplayIndex               │  ← Fast Lookup               │
│  │  data/replay_index.json         │                             │
│  │  update_execution()             │                             │
│  │  get_execution_info()           │                             │
│  └─────────────┬───────────────────┘                             │
│                │ execution metadata                               │
│                ▼                                                   │
│  ┌─────────────────────────────────┐                             │
│  │     SnapshotRegistry            │  ← State Checkpoints         │
│  │  data/snapshot_registry.json    │                             │
│  │  register_snapshot()            │                             │
│  │  get_snapshot(at_sequence)      │                             │
│  └─────────────────────────────────┘                             │
└───────────────────────────────────────────────────────────────────┘
```

---

## 3. Event Lifecycle States

```
CREATED  →  APPROVED  →  EXECUTING  →  COMPLETED
                      ↘  FAILED
                      ↘  REJECTED
```

Each transition appends a new **immutable** event to the log with:
- `sequence`: monotonic integer per `execution_id`
- `event_hash`: `SHA-256(execution_id + state + timestamp + source + details)`
- `previous_hash`: `event_hash` of the immediately prior event in the chain
- `lineage_proof`: `SHA-256(event_hash + previous_hash + str(sequence))`

---

## 4. Hash Chain Structure

```
Event 1 (CREATED)
├── event_hash:    H1 = SHA256(exec_id + "CREATED"  + t1 + ...)
├── previous_hash: ""   (genesis — no prior event)
└── lineage_proof: LP1 = SHA256(H1 + "" + "1")

Event 2 (APPROVED)
├── event_hash:    H2 = SHA256(exec_id + "APPROVED" + t2 + ...)
├── previous_hash: H1
└── lineage_proof: LP2 = SHA256(H2 + H1 + "2")

Event 3 (EXECUTING)
├── event_hash:    H3 = SHA256(exec_id + "EXECUTING"+ t3 + ...)
├── previous_hash: H2
└── lineage_proof: LP3 = SHA256(H3 + H2 + "3")

Event 4 (COMPLETED)
├── event_hash:    H4 = SHA256(exec_id + "COMPLETED"+ t4 + ...)
├── previous_hash: H3
└── lineage_proof: LP4 = SHA256(H4 + H3 + "4")

State Hash = SHA256(H1 + H2 + H3 + H4)   ← deterministic fingerprint
```

---

## 5. Replay Index Schema

File: `data/replay_index.json`

```json
{
  "<execution_id>": {
    "start_sequence":   1,
    "end_sequence":     4,
    "event_count":      4,
    "first_event_hash": "<sha256>",
    "last_event_hash":  "<sha256>",
    "last_timestamp":   1723354527,
    "source_ids":       ["system"]
  }
}
```

---

## 6. Snapshot Registry Schema

File: `data/snapshot_registry.json` (or `<work_dir>/snapshot_registry.json`)

```json
{
  "<snapshot_id>": {
    "execution_id": "<execution_id>",
    "at_sequence":  4,
    "state_hash":   "<sha256>",
    "created_at":   1723354527
  }
}
```

---

## 7. Recovery Algorithm

```
RecoveryValidator.validate(execution_id, expected_state_hash)

Step 1: Load journal events for execution_id from AppendOnlyLog
Step 2: verify_sequence_continuity() → sequence_ok
Step 3: verify_hash_chain()          → chain_ok
Step 4: LineageVerifier.verify_lineage_signatures() → signatures_ok
Step 5: If any check fails → return RECOVERY_FAILED

Step 6: compute_execution_state_hash(events) → computed_hash
Step 7: Compare computed_hash == expected_state_hash
Step 8: If mismatch → return RECOVERY_FAILED with "state_hash_mismatch"

Step 9: Rebuild ReplayIndex if missing (crash simulation)
Step 10: Return READY with state_hash
```

---

## 8. Replay Verification Commands

```bash
# Full lineage verification (mirrors Phase 3 acceptance)
python verify_phase3.py

# Expected output:
# ✓ Hash chain verification: PASSED
# ✓ Sequence continuity:     PASSED
# ✓ State hash:              <sha256>
# ✓ FULL LINEAGE VERIFICATION: PASSED

# Manual recovery validation
python -c "
from control_plane.deployment.recovery_validator import RecoveryValidator
r = RecoveryValidator().validate('<execution_id>', expected_state_hash='<sha256>')
print('Status:', r.status)
print('State hash:', r.state_hash)
print('Failures:', r.failures)
"
```

---

## 9. Replay Acceptance Criteria

| Check | Method | Expected Result |
|---|---|---|
| Hash chain | `verify_hash_chain()` | `ok=True` for all events |
| Sequence continuity | `verify_sequence_continuity()` | `ok=True`, no gaps |
| State determinism | `compute_execution_state_hash()` | Same hash on every replay |
| Tamper detection | `event_hash` cross-check | Fail immediately on any mutation |
| Full lineage | `RecoveryValidator.validate()` | `result.ready == True` |

---

## 10. Journal Integrity Rules

| Rule | Enforcement |
|---|---|
| Events are **append-only** | `AppendOnlyLog` never calls UPDATE/DELETE |
| Sequence numbers are **monotonic** | `OrderingViolation` raised on violation |
| Hash chains are **continuous** | `HashChainBreak` raised on discontinuity |
| Journal must **never be rotated** | Logrotate config excludes `append_only_log.jsonl` |
| State hashes are **deterministic** | `SHA-256` with stable canonical serialization |
