# TASK PHASE 1.4: Execution Lineage Persistence Integrity Forensics

## 1. Executive Summary & Baseline

This forensic audit investigates whether `ExecutionLineage`'s handling of corrupted JSON/JSONL records in `logs/control_plane/execution_lineage.jsonl` (and related append-only journals) can result in silent data loss, skipped lineage, broken integrity verification, replay-safety bypasses, or fail-open behavior.

### Baseline Verification
- **Execution Root**: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`
- **Tests Collected**: 216
- **Tests Passed**: 216
- **Tests Failed**: 0
- **Errors**: 0
- **Warnings**: 345 (deprecation warnings related to `datetime.utcnow()`)

The pytest baseline is verified clean and fully green.

---

## 2. Authoritative Implementation & Architecture

### Component Locations
- **Implementation**: [`backend/control_plane/core/execution_lineage.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/execution_lineage.py)
- **Cryptographic & Chain Verifier**: [`backend/security/lineage_verifier.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/security/lineage_verifier.py)
- **Semantic Guard Engine**: [`backend/control_plane/security/semantic_guard_engine.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/security/semantic_guard_engine.py)
- **Primary Callers**:
  - `contracts/execution_contract.py` (`build_execution_contract`, `advance_execution_state`)
  - `control_plane/backend/app/main.py` (`/api/lineage/{execution_id}`, `/api/lineage/{execution_id}/verify`)
  - `scripts/smoke_runtime_attestation.py`
  - Adversarial and unit tests (`test_phase1_signed_lineage.py`, `test_tampered_replay.py`, `test_order_corruption.py`, `test_unsigned_events.py`, `test_concurrent_replay.py`)

### Persistence Architecture
- **Storage File**: `logs/control_plane/execution_lineage.jsonl`
- **Format**: Newline-delimited JSON (JSONL), UTF-8 encoded.
- **Record Schema**:
  ```json
  {
    "event_id": "<uuid4>",
    "trace_id": "<uuid4>",
    "execution_id": "<str>",
    "previous_hash": "<str>",
    "parent_hash": "<str>",
    "timestamp": 1725350000.0,
    "state": "CREATED|APPROVED|EXECUTING|...",
    "execution_hash": "<sha256>",
    "source": "<str>",
    "details": {},
    "payload_hash": "<sha256>",
    "signer": "<str>",
    "signature": "<hmac-sha256>",
    "trace_hash": "<sha256>",
    "event_hash": "<sha256>"
  }
  ```
- **Write Path**:
  `append_lineage_event()` -> `_ensure_index_loaded()` -> acquires `_LINEAGE_LOCK` (`threading.Lock`) -> resolves `previous_hash` from `_LINEAGE_INDEX` -> signs trace via `build_signed_trace()` -> opens file in append (`"a"`) mode -> `handle.write(...)` -> `handle.flush()` -> `os.fsync(handle.fileno())` -> updates in-memory `_LINEAGE_INDEX[execution_id] = event_hash`.
- **Read Path**:
  `_read_events()` opens `get_lineage_log_path()` in read (`"r"`) mode without acquiring locks -> strips lines -> parses each line via `json.loads(line)`.

### Concurrency & Locking
- **Thread Safety**: Writes within the same Python process are guarded by `_LINEAGE_LOCK = threading.Lock()`.
- **Unlocked Reads**: `_read_events()` does **not** acquire `_LINEAGE_LOCK`. Concurrent reads while writing can inspect the file simultaneously.
- **Process Concurrency**: There is **no file-level locking** (`fcntl.flock` or `msvcrt.locking`). Concurrent processes appending to `execution_lineage.jsonl` can interleave raw writes.

---

## 3. The JSONDecodeError Execution Path

In [`backend/control_plane/core/execution_lineage.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/execution_lineage.py#L37-L52), `_read_events()` contains:

```python
def _read_events() -> List[Dict[str, Any]]:
    path = get_lineage_log_path()
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows
```

### Path Trace on Specific Corruption Types
1. **Malformed JSON / Truncated Line**:
   - `json.loads(line)` raises `json.JSONDecodeError`.
   - The exception is caught by `except json.JSONDecodeError: continue`.
   - **Observable Behavior**: The corrupted line is **silently ignored**. Zero logs, warnings, or metrics are emitted.
2. **Missing Fields on Valid JSON Syntax**:
   - `json.loads(line)` succeeds and returns a dict.
   - During replay, `LineageVerifier.verify_replay_chain()` checks `_signed_material()`: if required fields are missing, it raises `UnsignedReplayEventError("REPLAY_REJECTED_UNSIGNED_EVENT")`.
   - Thus, schema omissions in syntactically valid JSON fail closed during replay.
3. **Empty Result Behavior**:
   In `replay_execution_lineage(execution_id)`:
   ```python
   events = [event for event in _read_events() if event.get("execution_id") == execution_id]
   if not events:
       return {
           "execution_id": execution_id,
           "events": [],
           "execution_state_history": [],
           "final_state": None,
           "execution_hash": None,
           "valid": True,
       }
   ```
   **Observable Behavior**: If all events for an `execution_id` were corrupted (or if a non-existent `execution_id` is queried), replay returns **`"valid": True`** with an empty event list!

---

## 4. Security & Integrity Impact Analysis

### Finding 1: Silent Loss of Terminal States (False Valid Replay)
If an execution reaches a terminal or restrictive state (e.g., `CREATED` -> `APPROVED` -> `REJECTED`), and the final `REJECTED` line suffers corruption (disk fault, truncation, or hostile modification):
- `_read_events()` drops the corrupted `REJECTED` line.
- `replay_execution_lineage()` receives only `[CREATED, APPROVED]`.
- `verify_replay_chain()` validates `CREATED` -> `APPROVED` successfully.
- The execution is certified as **`valid: True`** with `final_state: APPROVED`.
- **Impact**: A rejected or aborted execution is falsely presented as authorized and valid.

### Finding 2: False Verification of Missing/Corrupted Executions
When an operator or API client calls:
`GET /api/lineage/{execution_id}/verify`
for an execution whose records were corrupted (or deleted, or never written):
- `replay_execution_lineage(execution_id)` returns `{"valid": True, ...}`.
- The endpoint returns:
  ```json
  {
    "execution_id": "corrupted_or_missing_id",
    "valid": true,
    "hash_chain_valid": true,
    "fsm_valid": true,
    "error": null
  }
  ```
- **Impact**: The system reports `hash_chain_valid: true` and `fsm_valid: true` when **zero** events were verified. This is a definitive **fail-open** verification defect.

### Finding 3: Lineage Branching / Forking Across Restarts
On process initialization, `_ensure_index_loaded()` calls `_rebuild_index()`:
```python
def _rebuild_index() -> Dict[str, str]:
    index: Dict[str, str] = {}
    for event in _read_events():
        execution_id = event.get("execution_id")
        event_hash = event.get("trace_hash") or event.get("event_hash")
        if execution_id and event_hash:
            index[execution_id] = event_hash
    return index
```
- If an execution's latest event $E_n$ is corrupted at the tail of the log:
  - `_rebuild_index()` sets `_LINEAGE_INDEX[execution_id] = hash(E_{n-1})`.
- When the runtime resumes and calls `append_lineage_event()`, it builds a new event $E'_n$ with `parent_hash = hash(E_{n-1})`.
- **Impact**: The log silently branches from the corrupted point. A historical event is permanently orphaned/overwritten without audit detection, violating append-only immutability.

### Finding 4: Replay Chain Behavior on Non-Terminal Corruption
- **Corrupted Initial Event (`CREATED`)**: The subsequent event (`APPROVED`) becomes index 0 during replay. `verify_replay_chain` checks `if index == 0 and event.get("state") != "CREATED"`, raising `SequenceViolationError`. (Fails closed upon replay).
- **Corrupted Intermediate Event**: If event $E_2$ is skipped, event $E_3$ has `parent_hash == hash(E_2)`, but the verifier expects `hash(E_1)`. This raises `LineageBreakError`. (Fails closed upon replay).
- **Critical Caveat**: Both of these fail-closed protections only trigger if someone runs replay. The logging layer itself continues operating and writing without error.

---

## 5. Concrete Failure Scenarios

### Scenario A: Revocation Evasion via Tail Truncation
1. Execution `exec-99` is flagged for policy violation; state `BLOCKED` is appended to `execution_lineage.jsonl`.
2. A crash or bad sector corrupts the trailing bytes of the `BLOCKED` record.
3. System restarts.
4. `_rebuild_index()` skips the corrupted line; index for `exec-99` reverts to `APPROVED`.
5. Auditor queries `/api/lineage/exec-99/verify`.
6. Result: `valid: true, final_state: APPROVED`.
7. **Result**: The policy revocation is completely lost, and downstream systems treat the action as cleanly approved.

### Scenario B: Operator Blindness to Storage Disk Failure
1. A server disk fills up, causing write truncation in `execution_lineage.jsonl`.
2. System monitoring checks `/api/lineage/{execution_id}/verify` as a health probe.
3. Because empty/skipped lines return `valid: true`, health monitoring reports 100% integrity green.
4. Production continues serving requests while lineage history is actively rotting on disk.

---

## 6. Test Coverage Analysis

An audit of all tests in `backend/tests/adversarial_test_suite/` and `backend/tests/test_phase1_signed_lineage.py`:
- `test_order_corruption.py`: Tests reordered valid JSON lines (`SequenceViolationError`).
- `test_tampered_replay.py`: Tests altered fields in valid JSON lines (`PayloadHashMismatchError`).
- `test_unsigned_events.py`: Tests missing signatures in valid JSON lines (`UnsignedReplayEventError`).
- `test_concurrent_replay.py`: Tests concurrent read replay threads.
- `test_deterministic_recovery.py`: Tests `AppendOnlyLog` clean recovery.

**Coverage Verdict**:
There is **zero test coverage** in the repository for:
- `JSONDecodeError` during lineage read
- Partial/truncated line persistence recovery
- Empty event query behavior in `replay_execution_lineage`
The passing `216/216` test suite gives false confidence because corrupt JSON persistence was never tested against `ExecutionLineage`.

---

## 7. Architectural Intent

Documentation across the repository confirms that journal integrity is intended to be strict and fail-closed:
1. `backend/docs/phase7/08_operational_runbook.md` (Line 164):
   > *"Alert security team — hash chain corruption is a potential security incident. STOP — do not restart the service."*
2. `backend/docs/phase7/02_vm_configuration_guide.md` (Line 147):
   > *"The append_only_log.jsonl must never be rotated, truncated, or deleted. It is the source of truth for all replay and certification operations."*
3. `ENGINEERING_AUDIT.md`:
   > *Lineage logs are declared as cryptographically locked, append-only, and tamper-evident.*

The silent swallow `except json.JSONDecodeError: continue` and the empty-events `"valid": True` directly contradict this documented architectural intent.

---

## 8. Proof Matrix

| Question | Evidence | Status | Gap |
|---|---|---|---|
| Does `_read_events()` catch `JSONDecodeError`? | `execution_lineage.py:49-51` | PROVEN | Swallows error silently with `continue` |
| Is corruption logged or surfaced? | `execution_lineage.py` | DEFECT | No logger, alert, or exception |
| Does tail corruption cause false state replay? | `replay_execution_lineage()` | PROVEN BUG | Corrupted tail record yields prior state as valid |
| Does empty execution verify as valid? | `execution_lineage.py:169` | PROVEN BUG | Returns `"valid": True` on empty event list |
| Does API endpoint report valid for empty ID? | `main.py:1020-1027` | PROVEN BUG | Returns `valid=True, hash_chain_valid=True` |
| Do existing tests verify corrupt persistence? | Test suite grep | NOT TESTED | Zero tests for `JSONDecodeError` |
| Does file write support multi-process locks? | `_LINEAGE_LOCK` inspection | DEFECT | In-process thread lock only; no `flock` |
| Does the architecture intend corruption to be fatal? | `08_operational_runbook.md` | PROVEN | Documented as security incident |

---

## 9. Final Classification

### **B. BUG — current behavior can silently lose lineage/integrity/security evidence and production behavior should be changed.**

**Technical Justification**:
1. `_read_events()` in `backend/control_plane/core/execution_lineage.py` silently discards corrupted records without audit logging, halting, or throwing an integrity error.
2. `replay_execution_lineage()` explicitly returns `"valid": True` when `events` is empty, allowing corrupt or missing lineage records to pass cryptographic verification endpoints.
3. Tail record corruption leaves executions in false prior states that re-verify as legitimate.
4. The behavior directly violates the security runbook declaring log corruption a high-severity security incident.

---

## 10. Production Change Decision (Remediation Specification)

As instructed, **no production code or tests were modified during this audit**. The following remediation is specified for the upcoming implementation task:

### 1. Target File: `backend/control_plane/core/execution_lineage.py`
- **Function**: `_read_events()`
  - **Change**: Replace silent `except json.JSONDecodeError: continue` with fail-closed handling.
  - **Proposed Behavior**: Define a `LineagePersistenceCorruptionError(ReplayIntegrityError)`. When encountering an invalid JSON line, log an immediate `CRITICAL` audit event containing line number and corrupted bytes, and raise `LineagePersistenceCorruptionError` (or support an explicit operator quarantine recovery mode).
- **Function**: `replay_execution_lineage()`
  - **Change**: When `not events`, do **not** return `"valid": True`.
  - **Proposed Behavior**:
    ```python
    if not events:
        return {
            "execution_id": execution_id,
            "events": [],
            "execution_state_history": [],
            "final_state": None,
            "execution_hash": None,
            "valid": False,
            "error": "EXECUTION_LINEAGE_NOT_FOUND",
        }
    ```

### 2. Target File: `backend/control_plane/backend/app/main.py`
- **Function**: `api_verify_lineage()`
  - **Change**: Check `result.get("events")`. If empty, return `valid=False, hash_chain_valid=False, fsm_valid=False, error="EXECUTION_NOT_FOUND"`.

### 3. Required Regression Tests
- Create adversarial tests in `backend/tests/adversarial_test_suite/test_persistence_corruption.py`:
  1. `test_corrupted_jsonl_line_raises_persistence_error`
  2. `test_empty_execution_replay_returns_invalid`
  3. `test_api_verify_rejects_missing_or_corrupted_lineage`
  4. `test_tail_corruption_detected_before_branching`

### 4. Compatibility & Migration Risks
- Any monitoring script or client that currently queries non-existent IDs and expects HTTP 200 with `valid: true` will receive `valid: false`. This is the intended security posture.
- Corrupted lines in existing dev logs will immediately raise errors upon read rather than quietly skipping, exposing previously unnoticed corrupted records.

---

## 11. Git Integrity Verification

```
git status --short
?? audit/PHASE1_4_EXECUTION_LINEAGE_PERSISTENCE_FORENSICS.md
```
- **Zero** source code modifications.
- **Zero** test modifications.
- **Zero** registry/config modifications.
- All VANA audits, documentation, and evidence remain completely preserved and untouched.
