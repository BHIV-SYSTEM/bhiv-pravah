# TASK PHASE 2.3.4 — FORENSIC DESIGN GATE FOR AUTHENTICATED JOURNAL & DURABLE RECOVERY

**Date:** 2026-09-04  
**Author:** DeepMind Antigravity Pair Programmer (Forensic Systems & Remediation)  
**Scope:** PRAVAH ONLY  
**Execution Root:** `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Classification:** **A — DESIGN FULLY ESTABLISHED; IMPLEMENTATION CAN PROCEED SAFELY**

---

## Executive Summary

Phase 2.3.3 conclusively established that the Phase 2.3.2 implementation achieved **accidental corruption detection** and **in-process memory synchronization**, but remained vulnerable to:
1. **Adversarial record forgery** because `record_hash` is an unkeyed SHA-256 digest without secret-key authentication or hash chaining.
2. **Journal corruption on filesystem failures** because `f.write() -> f.flush() -> os.fsync()` lacks truncation rollback on error and crash recovery for torn trailing writes.
3. **Duplicate journal admissions on retry** after uncertain persistence errors.

This forensic design gate establishes the exact, approved, non-invented architecture to remediate all three findings in Phase 2.3.5. It specifies:
- The authoritative security primitive (`security.signing.PayloadSigner` backed by `SSPL_SECRET_KEY`).
- A tamper-evident sequential hash-chain contract (`previous_hash` + `signature`).
- A deterministic filesystem append-rollback mechanism and torn-tail crash recovery contract.
- Natural and trace-correlated idempotency semantics.
- A secure backward-compatibility migration path that prevents downgrade attacks.

---

## 1. Existing Security Primitive Forensics

A forensic audit of existing Pravah security modules was performed across the codebase:

### 1.1 Comparative Primitive Analysis

| Primitive | Module Location | Secret Key Variable | Canonicalization Method | Signature Construction | Verification Method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Execution Lineage Signer** | [`backend/security/signed_trace.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/security/signed_trace.py) | `LINEAGE_SIGNING_KEY` | `canonicalize()` (custom recursive dict sort) | `hmac.new(SECRET_KEY, _trace_material, sha256)` | `lineage_verifier.verify_signature()` + FSM transition checks |
| **SSPL Payload Signer** | [`backend/security/signing.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/security/signing.py) | `SSPL_SECRET_KEY` | `canonical_serialize()` (recursive sort of dict, list, set, pydantic) | `hmac.new(secret_key, canonical_payload, sha256)` | `hmac.compare_digest(signature, expected_signature)` |
| **Trace Header Verifier** | [`backend/core_hooks/middleware.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/core_hooks/middleware.py) | `SSPL_SECRET_KEY` | `canonical_serialize()` | `sign_trace(trace_id, timestamp, payload)` | `verify_trace_signature()` with 300s TTL check |

### 1.2 Architectural Answers to Core Questions

#### A. Authoritative Secret Key
- **`SSPL_SECRET_KEY`** is the authoritative key for general structured payload signing across Pravah services and event buses (e.g., [`backend/control_plane/core/redis_event_bus.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/redis_event_bus.py#L15), [`backend/security/signing.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/security/signing.py#L36)).
- `LINEAGE_SIGNING_KEY` is reserved strictly for execution lineage FSM governance (`execution_id`, capability rights, agent state transitions).
- **Decision:** Use **`SSPL_SECRET_KEY`** via `security.signing.PayloadSigner`.

#### B. Key Loading Contract in Dev, Test, and Prod
In [`backend/security/signing.py:36-44`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/security/signing.py#L36-L44):
- In `prod` (`os.getenv('ENVIRONMENT', '').strip().lower() == 'prod'`): If `SSPL_SECRET_KEY` is not set or empty, initialization **raises `ValueError('SSPL_SECRET_KEY must be set in production')`** fail-closed.
- In `dev` and `test`: If `SSPL_SECRET_KEY` is not set, it defaults to a deterministic non-production key (`'default-secret-key-change-in-prod'`).
- This guarantees zero manual secret setup is required for pytest runs while maintaining fail-closed sovereignty in production.

#### C. Import and Circular Dependency Analysis
- `backend/security/signing.py` imports only standard library modules: `hashlib`, `hmac`, `json`, `os`, `time`, `typing`.
- It has **zero dependencies** on `control_plane`, `persistence`, `contracts`, or `fastapi`.
- Importing `from security.signing import sign_payload, verify_payload, get_signer` into `backend/control_plane/persistence/monitored_links_journal.py` has **zero risk of circular imports**.

#### D & E. Canonical Payload & Signature Coverage
- `PayloadSigner.sign_payload(payload_dict)` strips `'signature'` and `'signature_algorithm'`, recursively sorts all dictionary keys and nested structures via `canonical_serialize()`, and signs the exact canonical byte string.
- All payload fields (`event_id`, `timestamp`, `event_type`, `link`, `caller_id`, `name`, `ingested_item`, `metadata`, `previous_hash`, `record_hash`) are covered by the signature.

#### F. Hash-Chain Semantics
- In `execution_lineage.py`, hash chaining is partitioned per `execution_id`.
- For `monitored_links.jsonl`, the journal is a single, globally sequential log.
- Sequential hash chaining is established by having each record store:
  $$\text{previous\_hash} = \begin{cases} \text{"GENESIS"} & \text{for line 1} \\ \text{record}_{i-1}\text{["signature"]} & \text{for line } i > 1 \end{cases}$$
- Because each record's payload includes `previous_hash`, and the record is signed with `SSPL_SECRET_KEY`, any record deletion, insertion, or reordering breaks the signature and the chain.

#### G. Domain Separation from Execution Lineage
- **Monitored links are NOT execution lineage events.**
- Monitored links represent configuration target admission and dashboard telemetry. They do not possess an `execution_id`, do not transition through FSM states (`CREATED`, `APPROVED`, `EXECUTING`, `COMPLETED`), and are not governed actions.
- Reusing `execution_lineage.py` directly would violate domain separation and break FSM validation in `lineage_verifier.py`.

#### H. Recommended Approved Primitive
- **`PayloadSigner` (`backend/security/signing.py`)** is the approved, existing primitive for this journal.

---

## 2. Journal Security Contract

### 2.1 Complete Record Field Specification

| Field Name | Type | Required | Authenticated | Mutable | Purpose & Replay Semantic |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `event_id` | `str` (UUIDv4) | Yes | **Yes** | Immutable | Unique identifier; used for deduplication, audit tracing, and idempotency correlation. |
| `timestamp` | `str` (ISO-8601 UTC) | Yes | **Yes** | Immutable | Wall-clock event time; verified during replay for monotonicity / sanity. |
| `event_type` | `str` (`"LINK_INGESTED"` \| `"LINK_REMOVED"`) | Yes | **Yes** | Immutable | Primary state transition driver during replay. |
| `link` | `str` (Normalized URL) | Yes | **Yes** | Immutable | Target link identity; primary key for active monitored link dictionaries. |
| `caller_id` | `str` | Yes | **Yes** | Immutable | Authenticated caller identity; audit record. |
| `name` | `Optional[str]` | Conditional | **Yes** | Immutable | Display name (required for `LINK_INGESTED`; omitted or null for `LINK_REMOVED`). |
| `ingested_item` | `Optional[dict]` | Conditional | **Yes** | Immutable | Monitored link row dictionary (required for `LINK_INGESTED`; omitted/null for `LINK_REMOVED`). |
| `metadata` | `Optional[dict]` | Conditional | **Yes** | Immutable | Rich enrichment stats dictionary (required for `LINK_INGESTED`; omitted/null for `LINK_REMOVED`). |
| `previous_hash` | `str` (Hex) | Yes | **Yes** | Immutable | Signature of the preceding journal line (or `"GENESIS"` for line 1). Enforces ordering and continuity. |
| `record_hash` | `str` (SHA-256 Hex) | Yes | **Yes** | Immutable | Canonical unkeyed digest over core payload excluding signatures; provides fast integrity check. |
| `signature` | `str` (HMAC-SHA256 Hex) | Yes | **No** (Output) | Immutable | HMAC-SHA256 authenticator generated using `SSPL_SECRET_KEY`. |
| `signature_algorithm` | `str` | Yes | **No** (Output) | Immutable | Literal `"HMAC-SHA256"`. |

### 2.2 Attack Vector Detection Matrix

| Attack Vector | Attacker Action | Detection Mechanism |
| :--- | :--- | :--- |
| **Record Modification** | Modifies `link`, `caller_id`, or `metadata`. | Recomputed HMAC mismatch: `verify_payload()` returns `False`. Raises `LineagePersistenceCorruptionError`. |
| **Record Insertion** | Inserts a rogue record between line $k$ and $k+1$. | 1. Rogue record cannot be signed without `SSPL_SECRET_KEY`.<br>2. Line $k+1$'s `previous_hash` matches line $k$'s signature, not the inserted record. |
| **Record Deletion** | Deletes line $k$. | Line $k+1$'s `previous_hash` points to line $k$'s signature, which does not match line $k-1$'s signature. |
| **Record Reordering** | Swaps line $j$ and line $k$. | Both line $j$ and line $k$ have mismatched `previous_hash` values relative to their new neighbors. |
| **Unkeyed Hash Forgery** | Modifies payload and recomputes `record_hash = sha256(...)`. | Rejected because `signature` (HMAC) requires `SSPL_SECRET_KEY`. |

---

## 3. Backward Compatibility & Migration Strategy

### 3.1 Can Old Records Be Safely Replayed?
- **NO in production.** Accepting unsigned records in `ENVIRONMENT=prod` creates a catastrophic downgrade vulnerability: an attacker could simply strip the HMAC signature and claim the record is an "old Phase 2.3.2 record", completely bypassing cryptographic verification.
- **In non-production (dev/test):** Unsigned records can be replayed with a logged `WARNING` during local developer upgrades, but must be gated by `ENVIRONMENT != "prod"`.

### 3.2 Trusted Migration Path
To transition existing journal files to the authenticated contract without data loss:
1. **Schema Versioning:** Add a top-level journal metadata header or record version attribute (`"journal_version": 2`).
2. **Deterministic Migration Utility (`migrate_monitored_links_journal.py`):**
   - Reads existing Phase 2.3.2 records.
   - Verifies each record's existing `record_hash` against bit-rot.
   - Generates deterministic `event_id` (via `uuid.uuid5(uuid.NAMESPACE_URL, r['link'] + r['timestamp'])`).
   - Links records sequentially with `previous_hash` starting from `"GENESIS"`.
   - Signs every record using `PayloadSigner` with `SSPL_SECRET_KEY`.
   - Atomically replaces `monitored_links.jsonl` using a temporary file and `os.replace()`.

---

## 4. Filesystem Failure Model & Resilient Persistence Architecture

### 4.1 Failure Mode Analysis

| Failure Point | Filesystem State | In-Memory State | Recovery Strategy |
| :--- | :--- | :--- | :--- |
| **Write error before bytes written** | File length unchanged. | Unmutated. | Exception bubbles up; client receives error. Retry is safe. |
| **Partial write (ENOSPC mid-line)** | Trailing incomplete JSON line. | Unmutated. | **Rollback:** `f.truncate(initial_size)` resets file length to pre-write position. |
| **Flush error (OS cache error)** | Partial buffer written. | Unmutated. | **Rollback:** `f.truncate(initial_size)` strips uncommitted bytes. |
| **fsync error (EIO disk failure)** | Bytes in cache or on disk, unconfirmed. | Unmutated. | **Rollback:** `f.truncate(initial_size)` truncates file. Exception raised. |
| **Power loss / crash mid-write** | Torn trailing bytes on physical disk. | Process lost. | **Replay Crash Recovery:** If the *final line* of the file is unparseable or lacks a complete record, but all preceding lines have valid signatures and hash chains, truncate the torn tail and log a critical audit alert. |
| **Crash after fsync before response** | Durable record exists on disk. | Process lost. | On restart, replay restores record. Client retry is handled via idempotency. |

### 4.2 Chosen Strategy: Append + Rollback Truncation & Replay Tail Recovery

Rather than rewriting the entire file on every operation (which scales as $O(N^2)$), the production architecture will implement:

1. **Active Append with Truncation Guard:**
   ```python
   with _MONITORED_LINKS_LOCK:
       target_path.parent.mkdir(parents=True, exist_ok=True)
       initial_size = target_path.stat().st_size if target_path.exists() else 0
       try:
           with open(target_path, "a", encoding="utf-8") as f:
               f.write(line)
               f.flush()
               os.fsync(f.fileno())
       except Exception:
           if target_path.exists():
               try:
                   with open(target_path, "a", encoding="utf-8") as f_err:
                       f_err.truncate(initial_size)
               except Exception as trunc_exc:
                   logger.critical("Failed to truncate journal after write error: %s", trunc_exc)
           raise
   ```

2. **Replay Crash-Tail Recovery:**
   In `replay_monitored_links()`:
   - If a `JSONDecodeError` or truncated line occurs on the **final line** of the file, and all previous records are cryptographically valid:
     - Log a critical warning: `"Detected torn trailing record at EOF; truncating uncommitted write"`.
     - Truncate the file to the byte offset of the last complete record.
     - Continue clean recovery without blocking startup.
   - If any non-terminal line is corrupted, fail closed immediately (`LineagePersistenceCorruptionError`).

---

## 5. Idempotency & Duplicate Semantics

### 5.1 Natural URL Idempotency vs Trace-Id Correlation

In `/ingest-link` and `/remove-link`, the resource identity is the normalized URL:

1. **Lost Response Scenario:**
   - Step 1: Client calls `POST /ingest-link {"link": "https://github.com/org/repo"}`.
   - Step 2: Server persists to journal, publishes to memory, commits state.
   - Step 3: Network disconnects before client receives response.
   - Step 4: Client retries `POST /ingest-link {"link": "https://github.com/org/repo"}`.
2. **Current vs Desired Behavior:**
   - *Current:* Checks `if any(item["link"] == link for item in _INGESTED_LINKS): return LinkIngestResponse(success=False, error="Link already being monitored")`.
   - *Analysis:* Returning `success=False` on a retry causes naive clients to think the operation failed, even though the desired end-state was achieved.
   - *Desired Idempotent Contract:*
     If the link is already in `_INGESTED_LINKS`:
     Return `LinkIngestResponse(success=True, message=f"Link already monitored: {link}", ingested_link=..., metadata=..., enrichment_status=...)`.
     No duplicate event is written to disk. The client receives a clean success.
3. **Idempotency Header Support:**
   - Accept an optional `X-Trace-Id` or `Idempotency-Key` header (`Header(None)`).
   - If provided, store the mapping `_IDEMPOTENCY_INDEX[idempotency_key] = link`.
   - On retry with identical idempotency key, return the cached successful response.

---

## 6. Test Authenticity Requirements (Phase 2.3.5)

The following 8 targeted tests must be authored to prove Phase 2.3.5 without mocks or bypasses:

1. `test_replay_forged_payload_with_recomputed_hash_fails_closed`:
   Proves that an attacker who modifies a record and recomputes `record_hash = sha256(...)` is rejected because the HMAC signature is missing or invalid.
2. `test_replay_tampered_signed_payload_fails_closed`:
   Proves that modifying any signed payload field while leaving the HMAC signature intact fails closed with `LineagePersistenceCorruptionError`.
3. `test_replay_tampered_signature_fails_closed`:
   Proves that tampering with the signature string fails closed.
4. `test_replay_reordered_records_fails_closed`:
   Proves that swapping two valid signed records breaks the `previous_hash` chain and fails closed.
5. `test_replay_deleted_record_fails_closed`:
   Proves that deleting an intermediate record breaks the `previous_hash` chain and fails closed.
6. `test_persistence_partial_write_rolls_back_file_size`:
   Injects failure into `f.write()` / `os.fsync()` and verifies that `target_path.stat().st_size` reverts to its exact pre-write size.
7. `test_replay_torn_trailing_record_recovers_gracefully`:
   Appends a partial/truncated JSON line at the end of a valid journal, verifies that replay recovers all valid links, truncates the torn tail, and succeeds without crashing.
8. `test_idempotent_ingestion_retry_succeeds_without_duplicate_journal_entry`:
   Submits duplicate ingestion requests; verifies both return `success=True`, memory contains 1 entry, and the journal contains exactly 1 `LINK_INGESTED` record.

---

## 7. Required Implementation Files

### Source Files to Modify in Phase 2.3.5:
1. [`backend/control_plane/persistence/monitored_links_journal.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/persistence/monitored_links_journal.py)
   - Integrate `PayloadSigner` from `security.signing`.
   - Add `previous_hash` tracking and linear hash chaining.
   - Add pre-write size tracking and truncation rollback on write failure.
   - Add torn-tail crash recovery during replay.
2. [`backend/control_plane/backend/app/main.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/backend/app/main.py)
   - Update `/ingest-link` and `/remove-link` duplicate checking to support idempotent success responses.

### Test Files to Modify in Phase 2.3.5:
3. [`backend/tests/test_phase2_ingestion_api.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/tests/test_phase2_ingestion_api.py)
   - Update existing tamper tests to use authenticated signing.
   - Add the 8 new tests specified in Section 6.

---

## 8. Security Risks if Any Requirement Remains Unresolved

- **If HMAC signing is omitted:** Any local user, rogue container process, or compromised log-shipper can forge monitored URLs and compromise dashboard integrity.
- **If hash chaining is omitted:** An attacker can delete removal events, silently resurrecting decommissioned links.
- **If truncation rollback is omitted:** Disk full or transient I/O errors will leave corrupted trailing JSON lines, bricking control plane restarts.
- **If idempotency is omitted:** Network retries under load will return spurious errors or create journal bloat.

---

## 9. Exact Implementation Sequence for Phase 2.3.5

1. **Step 1:** Update `monitored_links_journal.py` to use `PayloadSigner.sign_payload()` and `verify_payload()`, computing `previous_hash` from the prior record's signature.
2. **Step 2:** Add filesystem pre-write size tracking and `f.truncate(initial_size)` exception handling in `append_link_ingested` and `append_link_removed`.
3. **Step 3:** Implement torn-tail recovery in `replay_monitored_links()` for truncated EOF lines while maintaining strict fail-closed verification on all prior records.
4. **Step 4:** Update `main.py` ingestion and removal endpoints to return idempotent responses on duplicate requests.
5. **Step 5:** Update and expand `test_phase2_ingestion_api.py` with all 8 new test proofs.
6. **Step 6:** Run full test regression (`pytest -q`), verify VANA diff is empty, and verify zero regressions.

---

## 10. Final Classification

### **FINAL CLASSIFICATION: A — DESIGN FULLY ESTABLISHED; IMPLEMENTATION CAN PROCEED SAFELY**

**Justification:**
- The existing approved security primitive (`PayloadSigner` + `SSPL_SECRET_KEY`) is identified and validated.
- The record contract provides complete protection against modification, insertion, deletion, and reordering.
- The filesystem failure model has a sound rollback and crash recovery design.
- Idempotency semantics are cleanly defined.
- Zero production code was modified during this design gate task.
