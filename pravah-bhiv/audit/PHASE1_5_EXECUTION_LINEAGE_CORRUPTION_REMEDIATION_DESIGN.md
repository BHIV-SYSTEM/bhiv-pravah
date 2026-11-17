# TASK PHASE 1.5: Execution Lineage Corruption Remediation Design Forensics

## 1. Baseline Verification

Execution Root: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`
- **Tests Collected**: 216
- **Tests Passed**: 216
- **Tests Failed**: 0
- **Errors**: 0
- **Warnings**: 345 (deprecation warnings from `datetime.utcnow()`)

The pytest test suite baseline is 100% clean and passing.

---

## 2. Independent Verification of Phase 1.4 Findings

The findings reported in Task Phase 1.4 were independently verified directly from the repository source code:

| Finding | Source Location | Code Behavior | Independent Verification Status |
|---|---|---|---|
| **A. Silent `JSONDecodeError` swallow** | [`backend/control_plane/core/execution_lineage.py:48-51`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/execution_lineage.py#L48-L51) | `try: rows.append(json.loads(line)) except json.JSONDecodeError: continue` | **CONFIRMED**: Malformed lines are discarded with zero logging, alerting, or error propagation. |
| **B. Empty execution replay returns `valid: True`** | [`backend/control_plane/core/execution_lineage.py:161-170`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/execution_lineage.py#L161-L170) | `if not events: return { ... "valid": True }` | **CONFIRMED**: Replay of a non-existent or completely corrupted execution ID reports `"valid": True`. |
| **C. Verification endpoint passes empty executions** | [`backend/control_plane/backend/app/main.py:998-1027`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/backend/app/main.py#L998-L1027) | `api_verify_lineage()` returns `VerifyResponse(valid=True, hash_chain_valid=True, fsm_valid=True, error=None)` | **CONFIRMED**: API reports green cryptographic and FSM status for empty or unparseable execution IDs. |
| **D. Latest corrupted event dropped during index rebuild** | [`backend/control_plane/core/execution_lineage.py:55-63`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/execution_lineage.py#L55-L63) | `_rebuild_index()` populates index exclusively from `_read_events()` | **CONFIRMED**: If tail event $E_n$ is corrupted, `_LINEAGE_INDEX[id]` points to $E_{n-1}$. |
| **E. Tail branching across restarts** | [`backend/control_plane/core/execution_lineage.py:102-149`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/execution_lineage.py#L102-L149) | `append_lineage_event()` takes `prev_hash` from `_LINEAGE_INDEX` | **CONFIRMED**: Appends a new event signed with $E_{n-1}$'s hash as parent, silently orphaning $E_n$ and branching history. |
| **F. Cryptographic checks only validate provided events** | [`backend/security/lineage_verifier.py:142-185`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/security/lineage_verifier.py#L142-L185) | `verify_replay_chain()` checks signatures and parent hashes only on events in list | **CONFIRMED**: Verifier is robust against payload tampering, reordering, and unsigned events, but is completely bypassed when corrupted lines are omitted before reaching it. |

---

## 3. Required Security Semantics Matrix

The following matrix establishes the required fail-closed semantics across all persistence corruption cases:

| Case | Scenario | Replay Result | API Verify Response | HTTP Status | Append Allowed? | Operator Action Required? |
|---|---|---|---|---|---|---|
| **Case A** | Execution ID genuinely does not exist in an intact journal | `events: []`, `valid: False`, `error: "EXECUTION_NOT_FOUND"` | `valid=False`, `hash_chain_valid=False`, `fsm_valid=False`, `error="EXECUTION_NOT_FOUND"` | `200` (Structured response) | YES (New execution starting with `CREATED`) | None |
| **Case B** | Execution ID exists but all of its records are malformed | Raises `LineagePersistenceCorruptionError` | `valid=False`, `hash_chain_valid=False`, `fsm_valid=False`, `error="LINEAGE_PERSISTENCE_CORRUPTION"` | `200` (Structured error response) | NO (Blocked by corrupted store lock) | YES (Quarantine/restore) |
| **Case C** | Intermediate lineage record is corrupted | Raises `LineagePersistenceCorruptionError` (if malformed JSON) or `LineageBreakError` (if tampered) | `valid=False`, `hash_chain_valid=False`, `fsm_valid=False`, `error="LINEAGE_CHAIN_BREAK"` | `200` (Structured error response) | NO (Blocked) | YES (Quarantine/restore) |
| **Case D** | Final/tail lineage record is corrupted | Raises `LineagePersistenceCorruptionError` | `valid=False`, `hash_chain_valid=False`, `fsm_valid=False`, `error="LINEAGE_PERSISTENCE_CORRUPTION"` | `200` (Structured error response) | NO (Blocked from tail branching) | YES (Repair truncated bytes / restore) |
| **Case E** | Lineage file contains malformed record for an unknown/unrelated execution | Raises `LineagePersistenceCorruptionError` | `valid=False`, `hash_chain_valid=False`, `fsm_valid=False`, `error="LINEAGE_PERSISTENCE_CORRUPTION"` | `200` (Structured error response) | NO (Journal lock) | YES (Security incident investigation) |
| **Case F** | Lineage file is missing or empty (0 bytes) | `events: []`, `valid: False`, `error: "EXECUTION_NOT_FOUND"` | `valid=False`, `hash_chain_valid=False`, `fsm_valid=False`, `error="EXECUTION_NOT_FOUND"` | `200` (Structured response) | YES (Normal initialization) | None |

*Note on Case E*: In a single-journal file, because an unparseable line's `execution_id` cannot be determined, it is mathematically impossible to prove that a corrupt line does not belong to the queried execution. Treating Case E as isolated is an inherent fail-open vulnerability; therefore, any unparseable line must fail closed for the entire journal.

---

## 4. Error Model Design

### Exception Classification
Journal corruption is fundamentally a **security and replay integrity failure**.
According to the Pravah operational runbook (`backend/docs/phase7/08_operational_runbook.md`, line 164):
> *"Alert security team — hash chain corruption is a potential security incident."*

### Proposed Error Hierarchy
In [`backend/security/lineage_verifier.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/security/lineage_verifier.py), all verification exceptions inherit from `ReplayIntegrityError`.
We define a new exception subclass within this existing hierarchy:

```python
class LineagePersistenceCorruptionError(ReplayIntegrityError):
    """Raised when persistence storage (e.g. JSONL journal) contains corrupted, unparseable, or truncated records."""
    def __init__(self, message: str, line_number: Optional[int] = None, raw_line: Optional[str] = None):
        super().__init__(message)
        self.line_number = line_number
        self.raw_line = raw_line
```

### Why Not Reuse Existing Exceptions?
- `LineageBreakError`: Specifically denotes a mismatch between `current_parent` and `expected_parent` hashes across valid JSON records. Using it for syntax corruption obscures file corruption vs cryptographic tampering.
- `PayloadHashMismatchError`: Specifically denotes HMAC payload tampering.
- A dedicated `LineagePersistenceCorruptionError` cleanly informs operators and automated monitoring that the physical storage medium or file content is corrupted.

---

## 5. Fail-Closed Read Design Evaluation

| Strategy | Security Guarantee | Data Loss Risk | Recovery Overhead | Recommendation |
|---|---|---|---|---|
| **Option A**: Raise immediately on first malformed JSON line | **Maximum (Fail-Closed)**. Zero corruption can pass undetected. | Zero. Stops further state corruption. | Operator must quarantine or fix corrupted line. | **SELECTED (Primary)** |
| **Option B**: Mark store corrupted; reject all operations | **High**. Prevents any subsequent writes or reads. | Zero. Prevents state divergence. | Requires restart/repair flag reset. | **SELECTED (For Appends)** |
| **Option C**: Automatic in-place quarantine of malformed records | **Low**. In-place modification of append-only log violates immutability rules. | High. Automatic rewriting risks dropping evidence. | Automated. | **REJECTED** |
| **Option D**: Ignore malformed records if "unrelated" | **Zero (Fail-Open)**. An unparseable record cannot prove its ownership. | High. Corrupted tail records would be skipped. | Low. | **REJECTED** |

### Selected Architecture (Option A + Option B)
1. **On Read (`_read_events`)**:
   Scan line by line. Upon encountering `json.JSONDecodeError`, do **not** execute `continue`. Immediately raise `LineagePersistenceCorruptionError(f"Corrupted record at line {line_num}", line_number=line_num)`.
2. **On Index Rebuild (`_ensure_index_loaded`)**:
   If `_read_events()` raises `LineagePersistenceCorruptionError`, set module-level flag `_LINEAGE_STORE_CORRUPTED = True`.
3. **On Write (`append_lineage_event`)**:
   If `_LINEAGE_STORE_CORRUPTED is True`, immediately raise `LineagePersistenceCorruptionError("Append blocked: lineage journal is in corrupted state")`.

---

## 6. Empty Execution Semantics

In [`backend/control_plane/core/execution_lineage.py:162-170`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/execution_lineage.py#L162-L170), the existing code currently returns:
```python
if not events:
    return {
        "execution_id": execution_id,
        "events": [],
        "execution_state_history": [],
        "final_state": None,
        "execution_hash": None,
        "valid": True,  # <-- DEFECT
    }
```

### Remediation
An execution that has zero events has never undergone state transitions, has no cryptographic signatures, and has no verified hash chain. Returning `"valid": True` is invalid.

The required return dictionary is:
```python
if not events:
    return {
        "execution_id": execution_id,
        "events": [],
        "execution_state_history": [],
        "final_state": None,
        "execution_hash": None,
        "valid": False,
        "error": "EXECUTION_NOT_FOUND",
    }
```

### API Endpoint (`api_verify_lineage`)
In [`backend/control_plane/backend/app/main.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/backend/app/main.py#L998-L1027):
```python
replay_result = replay_execution_lineage(execution_id)
if not replay_result.get("valid"):
    return VerifyResponse(
        execution_id=execution_id,
        valid=False,
        hash_chain_valid=False,
        fsm_valid=False,
        error=replay_result.get("error", "EXECUTION_NOT_FOUND"),
        runtime_attestation_valid=None,
        runtime_attestation_error=None,
    )
```
This guarantees:
1. `valid: false`
2. `hash_chain_valid: false`
3. `fsm_valid: false`
4. `error: "EXECUTION_NOT_FOUND"`
5. The frontend UI displays `Transition: INVALID` and `Hash Chain: COMPROMISED` instead of `VALID` and `SECURE`.

---

## 7. Tail Corruption & Branching Feasibility Analysis

### Is Tail Branching Possible in Production Today?
**YES. 100% CONFIRMED.**

### Concrete Production Execution Flow:
1. Process appends Event 1 (`CREATED`, hash=`H1`) and Event 2 (`APPROVED`, hash=`H2`).
2. Process writes Event 3 (`EXECUTING`, hash=`H3`), but a power cut or crash causes partial line write `{"event_id": "abc", "state": "EXEC`.
3. Process restarts.
4. `_ensure_index_loaded()` invokes `_rebuild_index()`.
5. `_read_events()` reads Line 1 (`H1`), Line 2 (`H2`), and Line 3 (`JSONDecodeError` -> `continue`).
6. `_LINEAGE_INDEX[execution_id]` is set to `H2`.
7. Runtime invokes `append_lineage_event(execution_id, state="FAILED", ...)` or re-attempts `"EXECUTING"`.
8. `prev_hash` is resolved as `_LINEAGE_INDEX[execution_id] == H2`.
9. A new event is signed with `parent_hash = H2` and written to Line 4.
10. **Result**: Line 3 is permanently bypassed. The journal silently branched at `H2`. Both Event 2 and Event 4 form a mathematically valid HMAC chain, and Event 3 is erased from active lineage without detection.

### Prevention Architecture:
1. `_read_events()` raises `LineagePersistenceCorruptionError` on Line 3.
2. `_ensure_index_loaded()` catches this and sets `_LINEAGE_STORE_CORRUPTED = True`.
3. `append_lineage_event()` checks `_LINEAGE_STORE_CORRUPTED` and refuses any write.
4. The system halts append operations until an operator isolates Line 3.

---

## 8. Corruption Detection Scope

The minimum mechanism that preserves complete integrity:
1. **Startup / Eager Index Load**: Scan journal during application startup. If corrupt, refuse to set index and lock appends.
2. **Replay Read**: Any read operation parses all lines strictly.
3. **Dedicated Health / Operational Check**: Add a validation routine to `backend/verify_phase3.py` (or a dedicated script) to report line-level integrity of `execution_lineage.jsonl`.

---

## 9. Concurrency & Locking Scope

- **Current State**: `_LINEAGE_LOCK = threading.Lock()` protects multithreaded writes in the primary process. Reads are unlocked. Multi-process file locks are absent.
- **Deployment Analysis**: In production, Pravah runs as a single Uvicorn worker process (`workers=1` in `backend/control_plane/backend/run.py`). Multi-process write contention is therefore not occurring under standard deployment.
- **Architectural Decision**:
  - Thread-level fail-closed locking is a **REQUIRED SECURITY FIX**.
  - Cross-process `fcntl.flock` / `msvcrt.locking` is classified as **OPTIONAL PRODUCTION HARDENING** and should not be bundled into this persistence corruption bugfix.

---

## 10. API Compatibility Analysis

### Consumers Inspected:
1. **Frontend**: [`frontend/src/services/api.ts`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/frontend/src/services/api.ts#L98-L109) and [`frontend/src/app/replay/page.tsx`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/frontend/src/app/replay/page.tsx#L114-L121).
   - Frontend already binds to `verify.hash_chain_valid ? 'healthy' : 'critical'`.
   - Returning `valid=False, hash_chain_valid=False` for missing/corrupt executions immediately enables the frontend to display the correct failure UI without breaking TypeScript contracts.
2. **HTTP Status Codes**:
   - For `/api/lineage/{execution_id}/verify`: Maintain `HTTP 200` with `valid=False, error="EXECUTION_NOT_FOUND"`. This matches the explicit contract in `main.py`: *"Returns structured booleans rather than raising errors to aid operators."*
   - For `/api/lineage/{execution_id}`: Maintain `HTTP 200` with `ReplayResponse(valid=False, events=[], error="EXECUTION_NOT_FOUND")`.
   - If `LineagePersistenceCorruptionError` occurs: Return `HTTP 500` (or `HTTP 503 Service Unavailable`) indicating underlying persistence storage is corrupted.

---

## 11. Regression Test Suite Design (Planned)

The following tests must be created in a new test module `backend/tests/adversarial_test_suite/test_persistence_corruption.py`:

```python
# Planned Test Specifications (Do NOT execute or implement yet):

def test_read_events_raises_persistence_corruption_error_on_syntax_error(monkeypatch, tmp_path):
    """Proves that a line with malformed JSON raises LineagePersistenceCorruptionError."""

def test_read_events_raises_persistence_corruption_error_on_truncated_bytes(monkeypatch, tmp_path):
    """Proves that a truncated JSON line (partial write) raises LineagePersistenceCorruptionError."""

def test_replay_execution_lineage_returns_invalid_on_empty_execution(monkeypatch, tmp_path):
    """Proves that querying an execution ID with zero records returns valid=False and error=EXECUTION_NOT_FOUND."""

def test_api_verify_lineage_returns_invalid_on_empty_execution(client):
    """Proves that GET /api/lineage/{id}/verify returns valid=False, hash_chain_valid=False for missing IDs."""

def test_tail_corruption_blocks_further_appends(monkeypatch, tmp_path):
    """Proves that if the journal tail is corrupted, append_lineage_event refuses to append and prevents branching."""

def test_clean_journal_roundtrip_remains_fully_functional(monkeypatch, tmp_path):
    """Proves that valid executions continue to write, read, and verify with valid=True (no regression)."""
```

---

## 12. Recovery & Operational Requirements

### Existing Runbook Gap:
- `backend/docs/phase7/08_operational_runbook.md` documents Procedure 3 for `append_only_log.jsonl`, but contains **no recovery instructions** for `logs/control_plane/execution_lineage.jsonl`.

### Required Operational Procedure (To be documented in runbook):
1. **On `LineagePersistenceCorruptionError`**:
   - Alert logs emit: `CRITICAL: Lineage journal corrupted at line X: <corrupted_snippet>`.
   - Service blocks further appends to preserve audit immutability.
2. **Operator Intervention**:
   - Operator inspects `logs/control_plane/execution_lineage.jsonl` at line $X$.
   - If line $X$ was a partial trailing write from a crashed process, operator archives the corrupted log to `execution_lineage.jsonl.corrupted.<timestamp>`, trims the incomplete trailing line, and validates integrity before restarting service.

---

## 13. Final Remediation Specification

### Required Security Fix (PR Scope):
1. **[`backend/security/lineage_verifier.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/security/lineage_verifier.py)**:
   - Add `LineagePersistenceCorruptionError(ReplayIntegrityError)`.
2. **[`backend/control_plane/core/execution_lineage.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/execution_lineage.py)**:
   - In `_read_events()`: Replace `except json.JSONDecodeError: continue` with `raise LineagePersistenceCorruptionError(f"Corrupted record in {path} at line {line_no}", line_number=line_no, raw_line=line)`.
   - In `_rebuild_index()` / `_ensure_index_loaded()`: On `LineagePersistenceCorruptionError`, set global `_LINEAGE_STORE_CORRUPTED = True`.
   - In `append_lineage_event()`: If `_LINEAGE_STORE_CORRUPTED is True`, raise `LineagePersistenceCorruptionError`.
   - In `replay_execution_lineage()`: If `not events`, return `"valid": False, "error": "EXECUTION_NOT_FOUND"`.
3. **[`backend/control_plane/backend/app/main.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/backend/app/main.py)**:
   - In `api_verify_lineage()`: If `replay_result.get("valid") is False`, return `VerifyResponse(execution_id=execution_id, valid=False, hash_chain_valid=False, fsm_valid=False, error=replay_result.get("error", "EXECUTION_NOT_FOUND"))`.
   - In `api_replay_lineage()`: Pass through `valid=False` when events are empty.
4. **[`backend/tests/adversarial_test_suite/test_persistence_corruption.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/tests/adversarial_test_suite)**:
   - Implement the 6 specified regression tests.

### Optional Hardening (Future Scope):
- Cross-process file locking (`fcntl.flock` / Windows `msvcrt`) for CLI/multiprocess deployments.
- Offline CLI diagnostic tool: `python -m control_plane.scripts.verify_lineage_journal`.

---

## 14. Final Classification

### **A. REMEDIATION CLEARLY DEFINED — implementation can begin after explicit authorization.**

**Justification**:
- All production findings are independently confirmed in source code.
- Required fail-closed semantics across all cases (A through F) are strictly defined.
- Error model, read/write/startup behaviors, API compatibility, and test designs are completely established.
- Zero open architectural ambiguities remain.

---

## 15. Git Integrity Verification

```
git status --short
?? audit/PHASE1_4_EXECUTION_LINEAGE_PERSISTENCE_FORENSICS.md
?? audit/PHASE1_5_EXECUTION_LINEAGE_CORRUPTION_REMEDIATION_DESIGN.md
```
- **Zero** source code modifications.
- **Zero** test modifications.
- **Zero** registry/config modifications.
- All VANA audit reports, tasks, documentation, and code remain 100% intact and untouched.
