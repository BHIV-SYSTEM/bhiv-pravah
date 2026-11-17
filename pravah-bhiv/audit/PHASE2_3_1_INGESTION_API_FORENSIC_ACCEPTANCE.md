# FORENSIC ACCEPTANCE AUDIT: TASK PHASE 2.3.1
## Pravah Ingestion API Remediation Acceptance Forensics

**Date:** 2026-09-04  
**Audit Target:** Phase 2.3 Implementation (`backend/control_plane/backend/app/main.py`, `schemas.py`, `monitored_links_journal.py`, `backend/tests/test_phase2_ingestion_api.py`)  
**Execution Root:** `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Accepted Forensic Baseline:** `audit/PHASE2_2_INGESTION_API_AUTH_CONTRACT_FORENSICS.md`  
**Prior Remediation Report:** `audit/PHASE2_3_INGESTION_API_REMEDIATION.md`  

**FINAL CLASSIFICATION:** **B — PARTIALLY PROVEN; SPECIFIC REMEDIATION GAPS REMAIN**

---

## 1. Executive Summary

A forensic code audit and dynamic execution analysis of the Phase 2.3 Ingestion API remediation was conducted across all twelve mandated acceptance vectors.

### Positive Confirmations:
1. **Formal Contracts:** Pydantic schemas (`LinkIngestRequest`, `LinkRemoveRequest`, `LinkMetadataResponse`, `MonitoredLinkItem`, `LinkIngestResponse`, `LinkRemoveResponse`, `IngestionErrorResponse`) are strictly implemented with `model_config = ConfigDict(extra="forbid")`, HTTP/HTTPS scheme restrictions, host validation, port range enforcement (1–65535), and control character rejection.
2. **Authentication Enforcement:** `POST /ingest-link` and `POST /remove-link` are strictly protected by `verify_control_plane_auth` reusing the authoritative `backend/security/auth.py:TokenAuth` JWT mechanism. Missing, malformed, invalid, or expired credentials consistently yield HTTP 401 Unauthorized. Telemetry registrations are cleanly separated from the `"governed-execution"` action capability.
3. **Error Boundary Hardening:** Broad silent exception swallowing (`except Exception: pass`) was eliminated from `_generate_link_metadata()`. Only expected network/parsing exceptions `(requests.exceptions.RequestException, ValueError)` are caught, populating explicit `enrichment_status: "fallback_heuristic"`, recording `enrichment_error`, and emitting structured warnings. Unexpected programming bugs bubble up rather than being suppressed.
4. **VANA Integrity:** `git diff -- VANA/` is completely empty (0 lines). Zero VANA code, tests, or documentation were altered.
5. **Phase 1 Non-Regression:** All 242 Phase 1 baseline tests continue to pass; 29 new tests were added, bringing the total suite to 271 passing tests.

### Confirmed Remediation Gaps (Requiring Classification B):
1. **Replay Hash Verification Gap (`SEC-JRN-001`):** `append_link_ingested` and `append_link_removed` compute and write `record_hash = sha256(canonical_record)`, but `replay_monitored_links()` **never validates or recomputes `record_hash` during journal replay**. If an attacker or storage defect mutates record content while keeping valid JSON syntax, replay silently accepts the tampered record.
2. **Visible-Before-Durable Atomicity Gap (`ERR-ATOM-001`):** In both endpoints, in-memory globals (`_INGESTED_LINKS`, `_LINK_METADATA`, `_LINK_EVENTS`) are mutated **before** calling `append_link_ingested` or `append_link_removed`. If journal writing fails (e.g. disk full, read-only FS, permissions), memory remains modified while disk has no record, causing memory/disk divergence and permanently blocking duplicate retries.
3. **Concurrency Race Condition Gap (`CONC-001`):** FastAPI executes synchronous route handlers in a threadpool. `_INGESTED_LINKS` lacks synchronization locks in `main.py`. Two concurrent requests for the same link can race past the duplicate check while `_generate_link_metadata()` executes outbound requests, resulting in duplicate in-memory monitors and duplicate journal records.
4. **Coarse Authorization vs Authentication:** TokenAuth cryptographic validation is proven, but fine-grained authorization (RBAC/scopes) is not implemented: any valid authenticated caller can delete any active monitoring target.

---

## 2. Forensic Vector 1: Formal API Contracts

### Code Inspection (`backend/control_plane/backend/app/schemas.py:127-260`)

```python
class LinkIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    link: str = Field(..., min_length=8, max_length=2048)

    @field_validator("link")
    @classmethod
    def validate_url(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("URL cannot be empty")
        if any(c.isspace() or ord(c) < 32 for c in clean):
            raise ValueError("URL contains illegal whitespace or control characters")
        parsed = urllib.parse.urlsplit(clean)
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError("URL scheme must be http or https")
        if not parsed.netloc:
            raise ValueError("URL must include a valid network location (hostname)")
        try:
            port = parsed.port
            if port is not None and not (1 <= port <= 65535):
                raise ValueError("Port out of range (1-65535)")
        except ValueError as e:
            raise ValueError(f"URL contains invalid port: {e}")
        host = parsed.netloc.split(":")[0]
        if not host or ("." not in host and host != "localhost"):
            raise ValueError("URL must have a valid host (e.g., domain or localhost)")
        return clean
```

### Forensic Findings:
- **`extra="forbid"`:** Present and active on both `LinkIngestRequest` and `LinkRemoveRequest`. Confirmed via test `test_unexpected_fields_rejected_422`.
- **Scheme Validation:** Strictly checks `parsed.scheme.lower() in ("http", "https")`. Protocols like `ftp://`, `file://`, `javascript:`, etc. are rejected with HTTP 422.
- **Hostname & Domain Validation:** Requires `parsed.netloc` non-empty. Splits port and verifies hostname contains a dot (`.`) or equals `"localhost"`. Single-word strings without dots (e.g. `http://nosuchdomain`) are rejected with HTTP 422.
- **Port Range Validation:** Enforces integer bounds `1 <= port <= 65535` and catches non-numeric ports (e.g. `http://localhost:invalidport` rejects with HTTP 422).
- **Length & Control Characters:** Min length 8, max length 2048. Strings containing control characters (`ord < 32`) or internal whitespace (`c.isspace()`) are rejected with HTTP 422.
- **Syntactic vs. Live Validation:** Validation is strictly **syntactic** (using `urllib.parse.urlsplit`). It does **not** execute live DNS lookups or socket connects during Pydantic parsing. This is architecturally appropriate, as performing synchronous DNS lookups inside Pydantic model parsing causes severe latency and Denial-of-Service vulnerability. Live external reachability is bounded inside `_generate_link_metadata()`.
- **Response Models:** `LinkIngestResponse` and `LinkRemoveResponse` match the serialized payloads returned by `main.py`.

**Verdict:** **CONTRACT VERIFICATION PROVEN.**

---

## 3. Forensic Vector 2: Authentication vs. Authorization

### Code Trace (`backend/control_plane/backend/app/main.py:235-269`)
```python
def verify_control_plane_auth(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_token: Optional[str] = Header(None, alias="X-API-Token"),
) -> dict[str, Any]:
    token = None
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1 and not parts[0].lower().startswith("bearer"):
            token = parts[0]
        else:
            raise HTTPException(status_code=401, detail="Malformed Authorization header")
    elif x_api_token:
        token = x_api_token.strip()

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required: missing token")

    auth_instance = get_auth()
    result = auth_instance.verify_token(token)
    if not result.get("valid"):
        error_msg = result.get("error", "Invalid or expired token")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {error_msg}")

    payload = result.get("payload", {})
    caller_id = payload.get("user_id") or payload.get("sub") or "authenticated_user"
    return {"caller_id": str(caller_id), "payload": payload}
```

### Forensic Determination:
1. **What a valid JWT proves:**
   - The caller holds a JSON Web Token signed with `JWT_SECRET_KEY` using HS256.
   - The token has not expired (`exp` claim is in the future).
   - The token asserts a caller identity (`user_id`).
2. **Are roles, scopes, or permissions checked?**
   - **NO.** Neither `TokenAuth.verify_token()` nor `verify_control_plane_auth()` inspects user roles, claims, or permissions.
3. **Can ANY authenticated caller ingest or remove links?**
   - **YES.** Any caller holding any valid token can invoke both `POST /ingest-link` and `POST /remove-link`.
4. **Comparison against Phase 2.2 audit:**
   - Phase 2.2 Section 3.G & 3.H noted that `/ingest-link` is a control-plane registration mutation and does not require capability governance. Section 3.I noted that deletion is higher risk and requires tracking caller identity.
   - Phase 2.3 Scope explicitly directed: *"Do NOT incorrectly route these endpoints through the 'governed-execution' capability because these are monitoring registration mutations, not infrastructure execution... Establish caller identity through the existing authentication mechanism."*
5. **Classification:**
   - **AUTHENTICATION PROVEN:** Yes. Cryptographic token verification is strictly enforced; anonymous/forged callers receive HTTP 401.
   - **FINE-GRAINED AUTHORIZATION NOT IMPLEMENTED (ACCEPTABLE BY DESIGN FOR PHASE 2.3):** RBAC / role scopes were not requested in the Phase 2.3 scope. However, technical documentation must avoid claiming "authorization proven."

**Verdict:** **AUTHENTICATION PROVEN; FINE-GRAINED RBAC NOT REQUIRED BY DESIGN.**

---

## 4. Forensic Vector 3: Replay & Hash Integrity

### Code Inspection (`backend/control_plane/persistence/monitored_links_journal.py`)

#### Record Writing (`append_link_ingested` & `append_link_removed`):
```python
record: Dict[str, Any] = {
    "event_type": "LINK_INGESTED",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "link": link,
    "name": name,
    "caller_id": caller_id,
    "ingested_item": ingested_item,
    "metadata": metadata,
}
record["record_hash"] = _hash_record(record)
```

#### Record Replay (`replay_monitored_links:115-195`):
```python
with open(target_path, "r", encoding="utf-8") as f:
    for line_no, raw_line in enumerate(f, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            ...
            raise LineagePersistenceCorruptionError(...)

        if not isinstance(record, dict) or "event_type" not in record or "link" not in record:
            ...
            raise LineagePersistenceCorruptionError(...)

        event_type = record["event_type"]
        link = record["link"]
        if event_type == "LINK_INGESTED":
            ...
        elif event_type == "LINK_REMOVED":
            ...
        else:
            ...
            raise LineagePersistenceCorruptionError(...)
```

### Forensic Defect Analysis (`SEC-JRN-001`):
1. **Is `record_hash` verified during replay?**
   - **NO.** `replay_monitored_links` parses `record` but never recomputes `_hash_record(record)` or checks `record.get("record_hash")`.
2. **Is there a hash chain?**
   - **NO.** There is no `previous_hash` linking record $N$ to record $N-1$. Each record is independent.
3. **Can an attacker tamper with journal data without detection?**
   - **YES.** An attacker or disk storage corruption can modify `link`, `name`, `caller_id`, or `metadata` in `monitored_links.jsonl`. As long as the JSON remains syntactically valid and contains `event_type` and `link`, `replay_monitored_links` will accept it without error.
4. **What constitutes corruption in the current implementation?**
   - Unparseable JSON syntax (`JSONDecodeError`).
   - Non-dictionary object, or dictionary missing `event_type` or `link`.
   - Unknown `event_type` string.
   - It does **not** detect record content tampering.
5. **Test Authenticity Gap:**
   - Test `test_persistence_journal_records_deterministic_events` only asserts `assert "record_hash" in r and len(r["record_hash"]) == 64`.
   - No test asserts that tampering with a record's hash or content triggers rejection during replay.

**Verdict:** **DEFECT CONFIRMED (`SEC-JRN-001`). Replay does not verify record hashes.**

---

## 5. Forensic Vector 4: Persistence Atomicity

### Execution Trace (`backend/control_plane/backend/app/main.py:1003-1074`)

In `POST /ingest-link`:
1. Check duplicate against `_INGESTED_LINKS` (memory).
2. Generate metadata `_generate_link_metadata(link)`.
3. Mutate memory: `_LINK_METADATA[link] = metadata`.
4. Mutate memory: `_INGESTED_LINKS.append(ingested_item)`.
5. Mutate memory: `_LINK_EVENTS.appendleft(...)`.
6. Append to disk: `append_link_ingested(...)` (opens file, writes, flushes, fsyncs).
7. Return response.

In `POST /remove-link`:
1. Mutate memory: `_INGESTED_LINKS = [item for item in _INGESTED_LINKS if item["link"] != link]`.
2. Mutate memory: `del _LINK_METADATA[link]`.
3. Mutate memory: `_LINK_EVENTS.appendleft(...)`.
4. Append to disk: `append_link_removed(...)`.
5. Return response.

### Forensic Defect Analysis (`ERR-ATOM-001`):
1. **Ordering:** The operation is **`visible-before-durable`**.
2. **Failure Scenario:** If `append_link_ingested` raises an `OSError` (e.g. disk full, read-only disk, I/O error):
   - The in-memory state has already been modified (`_INGESTED_LINKS` contains the link, `_LINK_METADATA` contains metadata).
   - FastAPI catches the unhandled `OSError` and returns HTTP 500 to the client.
   - The client thinks the request failed.
   - BUT the in-memory dashboard displays the link as active and healthy.
   - If the client retries the request, `ingest_link` returns HTTP 200 `{"success": False, "error": "Link already being monitored"}`!
   - When the server process restarts, the link disappears because the journal write never succeeded.
3. **Classification:** **`Inconsistent on persistence failure`**. It is not transactional and lacks compensating rollback.

**Verdict:** **DEFECT CONFIRMED (`ERR-ATOM-001`). Visible-before-durable without rollback on journal write failure.**

---

## 6. Forensic Vector 5: Concurrency & Race Conditions

### Architectural Analysis:
1. `monitored_links_journal.py` uses `_MONITORED_LINKS_LOCK = threading.RLock()`. This lock serializes write operations to the file.
2. However, in `main.py`:
   - `_INGESTED_LINKS` is a global Python `list`.
   - `_LINK_METADATA` is a global Python `dict`.
   - Neither data structure is guarded by a concurrency lock.
3. FastAPI executes synchronous route handlers (`def ingest_link(...)`) using `anyio.to_thread.run_sync` inside a multi-threaded worker pool.
4. **Race Scenario:**
   - Thread 1 and Thread 2 receive simultaneous `POST /ingest-link` requests for the same URL `https://github.com/foo/bar`.
   - Thread 1 checks `existing = next(...)` -> `None`.
   - Thread 2 checks `existing = next(...)` -> `None`.
   - Both threads invoke `_generate_link_metadata()`, which makes outbound HTTP requests to GitHub (up to 2.0s timeout).
   - Thread 1 finishes enrichment, appends to `_INGESTED_LINKS`, and writes `LINK_INGESTED` to the journal.
   - Thread 2 finishes enrichment, appends to `_INGESTED_LINKS`, and writes `LINK_INGESTED` to the journal.
5. **Outcome:**
   - `_INGESTED_LINKS` contains duplicate entries for the identical link.
   - `monitored_links.jsonl` contains two consecutive `LINK_INGESTED` records.
   - Metrics endpoints (`/metrics`, `/control-plane/status`) report inflated link counts.

**Verdict:** **DEFECT CONFIRMED (`CONC-001`). Endpoint mutation pipeline lacks concurrency synchronization.**

---

## 7. Forensic Vector 6: Startup Recovery

### Code Trace (`backend/control_plane/backend/app/main.py:183-196`):
```python
@app.on_event("startup")
async def startup_event():
    global _INGESTED_LINKS, _LINK_METADATA, _LINK_EVENTS
    try:
        active_links, metadata_map, event_history = replay_monitored_links()
        _INGESTED_LINKS = active_links
        _LINK_METADATA = metadata_map
        for ev in event_history:
            _LINK_EVENTS.append(ev)
        logger.info("Recovered %d monitored links from journal", len(_INGESTED_LINKS))
    except LineagePersistenceCorruptionError as exc:
        logger.critical("Monitored links journal corrupted: %s", exc)
        raise
```

### Forensic Determination:
- Replay occurs on FastAPI startup via `@app.on_event("startup")`.
- Active links are reconstructed using a dictionary `active_links_map[link] = ingested_item`, ensuring duplicates in the journal collapse deterministically into a single active entry.
- Removed links are popped from the map, ensuring removed targets remain deactivated.
- Metadata is restored into `_LINK_METADATA`.
- Corrupted lines (syntax or missing schema keys) raise `LineagePersistenceCorruptionError`, halting startup fail-closed.
- **Gap:** As noted in Vector 3, tampered records with valid JSON syntax are not detected because `record_hash` is not verified during replay.

**Verdict:** **STARTUP RECOVERY PROVEN (Subject to Vector 3 Hash Verification Gap).**

---

## 8. Forensic Vector 7: Metadata Error Boundary

### Code Trace (`backend/control_plane/backend/app/main.py:302-369`):
```python
def _generate_link_metadata(link: str) -> dict[str, Any]:
    ...
    if is_github:
        parts = link.split("github.com/")
        if len(parts) > 1:
            repo_path = parts[1].strip("/").split("?")[0].split("#")[0]
            if repo_path.endswith(".git"):
                repo_path = repo_path[:-4]
            path_segments = [p for p in repo_path.split("/") if p]
            if len(path_segments) >= 2:
                canonical_repo = f"{path_segments[0]}/{path_segments[1]}"
                try:
                    import requests
                    resp = requests.get(...)
                    if resp.status_code == 200:
                        ...
                        enrichment_status = "enriched"
                    elif resp.status_code in (403, 429):
                        enrichment_status = "fallback_heuristic"
                        enrichment_error = f"GitHub API rate limit or forbidden: HTTP {resp.status_code}"
                        logger.warning(...)
                    else:
                        enrichment_status = "fallback_heuristic"
                        enrichment_error = f"GitHub API returned HTTP {resp.status_code}"
                        logger.warning(...)
                except (requests.exceptions.RequestException, ValueError) as exc:
                    enrichment_status = "fallback_heuristic"
                    enrichment_error = f"Network or parsing failure: {type(exc).__name__}: {str(exc)}"
                    logger.warning(...)
```

### Forensic Determination:
1. Expected network exceptions (`requests.exceptions.RequestException`, `ValueError`) are handled gracefully without terminating ingestion.
2. Rate limits (HTTP 429/403) and 404/500 responses set `enrichment_status = "fallback_heuristic"` and log structured warnings.
3. Unexpected programming exceptions (e.g. `TypeError`, `KeyError`) are **not** swallowed.
4. Fallback is explicitly identified and never represented as verified external data.
5. In automated tests, external network calls are mocked via `monkeypatch.setattr(requests, "get", ...)`. This is appropriate for CI deterministic testing, but must be acknowledged as mock verification rather than live external network proof.

**Verdict:** **METADATA ERROR BOUNDARY PROVEN.**

---

## 9. Forensic Vector 8: Test Authenticity Matrix

| Test Function | Classification | Boundary Under Test | Uses Mocks? | Genuine Proof? |
| :--- | :--- | :--- | :--- | :--- |
| `test_missing_authentication_rejected_401` | Security Boundary | `TestClient(app)` -> `verify_control_plane_auth` | No | **YES** |
| `test_invalid_authentication_token_rejected_401` | Security Boundary | `TestClient(app)` -> `TokenAuth.verify_token` | No | **YES** |
| `test_expired_authentication_token_rejected_401` | Security Boundary | `TestClient(app)` -> `TokenAuth.verify_token` | No | **YES** |
| `test_x_api_token_header_accepted` | Integration Test | `TestClient(app)` -> `verify_control_plane_auth` | No | **YES** |
| `test_unauthorized_removal_rejected_401` | Security Boundary | `TestClient(app)` -> `verify_control_plane_auth` | No | **YES** |
| `test_valid_authenticated_ingestion` | Integration / Security | `TestClient(app)` -> Full Pipeline -> Journal | No | **YES** |
| `test_malformed_url_rejected_422` (9 cases) | Contract Validation | `TestClient(app)` -> Pydantic Schema | No | **YES** |
| `test_wrong_field_name_rejected_422` | Contract Validation | `TestClient(app)` -> Pydantic Schema | No | **YES** |
| `test_wrong_type_rejected_422` | Contract Validation | `TestClient(app)` -> Pydantic Schema | No | **YES** |
| `test_unexpected_fields_rejected_422` | Contract Validation | `TestClient(app)` -> Pydantic `extra="forbid"` | No | **YES** |
| `test_duplicate_ingestion_rejected_deterministic`| Contract Validation | `TestClient(app)` -> Deduplication logic | No | **YES** |
| `test_authenticated_removal_success` | Integration / Security | `TestClient(app)` -> Pipeline -> Journal | No | **YES** |
| `test_nonexistent_removal` | Contract Validation | `TestClient(app)` -> Removal handler | No | **YES** |
| `test_metadata_enrichment_success_github` | Unit / Logic Test | `_generate_link_metadata` parsing | Yes (`requests.get`) | **Controlled Mock** |
| `test_metadata_enrichment_network_failure_produces_fallback` | Error Boundary | `_generate_link_metadata` exception handling | Yes (`requests.get`) | **Controlled Mock** |
| `test_metadata_enrichment_rate_limit_produces_fallback` | Error Boundary | `_generate_link_metadata` rate-limit handling | Yes (`requests.get`) | **Controlled Mock** |
| `test_unexpected_programming_exception_not_swallowed` | Error Boundary | `_generate_link_metadata` | Yes (hash injector) | **YES** |
| `test_persistence_journal_records_deterministic_events` | Persistence Test | `monitored_links_journal` file I/O | No | **PARTIAL** (does not test hash tamper) |
| `test_startup_recovery_restores_active_monitored_links` | Persistence Test | `replay_monitored_links` reconstruction | No | **YES** |
| `test_journal_corruption_fails_closed` | Failure Injection | `replay_monitored_links` syntax corruption | No | **YES** |
| `test_journal_schema_corruption_fails_closed` | Failure Injection | `replay_monitored_links` schema corruption | No | **YES** |

### Critical Testing Omissions:
1. No concurrency race test (multiple threads hitting `/ingest-link` concurrently).
2. No journal write failure atomicity test (verifying rollback if `append_link_ingested` raises `OSError`).
3. No hash verification test (asserting that altering a record's text with valid JSON raises corruption during replay).

---

## 10. Forensic Vector 9: Report Claims vs. Actual Evidence

| Claim in `audit/PHASE2_3_INGESTION_API_REMEDIATION.md` | Actual Code Reality | Forensic Finding |
| :--- | :--- | :--- |
| *"Authoritative Authentication & Caller Identity"* | Verified by `TokenAuth.verify_token()`. | **ACCURATE** |
| *"Formal API Contracts with strict validation"* | Pydantic schemas with `extra="forbid"`, scheme, host, and port checks. | **ACCURATE** |
| *"Hardened Metadata Error Boundary"* | Broad exception swallowing eliminated; fallback explicitly flagged. | **ACCURATE** |
| *"Durable Local Journal Persistence... SHA-256 record hashes"* | Record hashes are written to file, but **never verified on replay**. | **OVERSTATED** |
| *"Atomic durable persistence"* | State is mutated in memory **before** disk append; no rollback on failure. | **OVERSTATED** |
| *"Complete verification"* | Concurrency, rollback, and hash tampering were untested. | **OVERSTATED** |

---

## 11. Forensic Vector 10: VANA Integrity Verification

Command executed:
```bash
git diff -- VANA/
```
Output:
*(Empty, 0 lines returned)*

**Verdict:** **VANA INTEGRITY 100% PRESERVED. ZERO MODIFICATIONS.**

---

## 12. Forensic Vector 11: Repository Working Tree Status

Command executed:
```bash
git status --short
```

Output:
```text
 M backend/contracts/execution_contract.py
 M backend/control_plane/backend/app/main.py
 M backend/control_plane/backend/app/schemas.py
 M backend/control_plane/capabilities/execution_rights_adapter.py
 M backend/control_plane/capabilities/registry/group1-observation-api.json
 M backend/control_plane/capabilities/test_execution_rights_adapter.py
 M backend/control_plane/core/execution_lineage.py
 M backend/control_plane/persistence/__init__.py
 M backend/reliability-controller2-main/executer/app.py
 M backend/security/lineage_verifier.py
 M backend/security/nonce_store.json
 M backend/security/trace_consumption.json
 M backend/tests/adversarial_test_suite/test_deterministic_recovery.py
 M backend/tests/test_phase15_gap_governed_abstention.py
 M backend/tests/test_phase5_deployment_validators.py
 M backend/tests/test_phase8_execution_closure.py
 M backend/tests/test_replay_sovereignty.py
 D deliverables.zip
 M deployment_verification_packet/readiness_validation.log
 M logs/UptimeMonitor_debug.log
 M logs/agent/agent_proof.jsonl
 M logs/agent/agent_runtime.log
 M logs/control_plane/append_only_log.jsonl
 M logs/control_plane/execution_lineage.jsonl
 M logs/control_plane/governance_state.json
 M logs/control_plane/policy_enforcement.jsonl
 M logs/day1_proof.log
 M logs/dev/metrics/uptime_metrics.csv
 M logs/dev/runtime_restart_log.csv
 M logs/dev/uptime_log.csv
 M logs/prod/orchestrator_decisions.jsonl
 M payload_integrity.log
 M runtime_rl_proof.log
 M security/nonce_store.json
 M security/trace_consumption.json
 M trace_log.jsonl
?? ../logs/
?? audit/
?? backend/control_plane/persistence/monitored_links_journal.py
?? backend/pytest.ini
?? backend/tests/adversarial_test_suite/test_execution_boundary_lineage.py
?? backend/tests/adversarial_test_suite/test_persistence_corruption.py
?? backend/tests/test_phase2_ingestion_api.py
?? pytest.ini
?? ../trace_log.jsonl
```

### Analysis of Modified & Untracked Files:
1. **Authorized Phase 2.3 Changes:**
   - `backend/control_plane/backend/app/schemas.py`
   - `backend/control_plane/backend/app/main.py`
   - `backend/control_plane/persistence/monitored_links_journal.py`
   - `backend/control_plane/persistence/__init__.py`
   - `backend/tests/test_phase2_ingestion_api.py`
   - `audit/PHASE2_3_INGESTION_API_REMEDIATION.md`
   - `audit/PHASE2_3_1_INGESTION_API_FORENSIC_ACCEPTANCE.md` (this report)
2. **Prior Authorized Phase 1 Changes:** Files modified during Phase 1.7 through 1.9.2 (documented in prior accepted audits).
3. **Runtime & Log Files:** Dynamic logs and state tracking files generated during test executions.
4. **VANA Material:** Completely clean (0 modifications).

---

## 13. Forensic Vector 12: Dynamic Test Execution Evidence

### A. Test Collection Count
```text
pytest --collect-only -q
...
271 tests collected in 0.88s
```

### B. Full Test Suite Execution
```text
pytest -q
...
271 passed, 370 warnings in 17.08s
```

### C. Phase 2.3 Dedicated Regression Test Execution
```text
pytest backend/tests/test_phase2_ingestion_api.py -v
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv\backend
configfile: pytest.ini
collected 29 items

backend\tests\test_phase2_ingestion_api.py::test_missing_authentication_rejected_401 PASSED [  3%]
backend\tests\test_phase2_ingestion_api.py::test_invalid_authentication_token_rejected_401 PASSED [  6%]
backend\tests\test_phase2_ingestion_api.py::test_expired_authentication_token_rejected_401 PASSED [ 10%]
backend\tests\test_phase2_ingestion_api.py::test_x_api_token_header_accepted PASSED [ 13%]
backend\tests\test_phase2_ingestion_api.py::test_unauthorized_removal_rejected_401 PASSED [ 17%]
backend\tests\test_phase2_ingestion_api.py::test_valid_authenticated_ingestion PASSED [ 20%]
backend\tests\test_phase2_ingestion_api.py::test_malformed_url_rejected_422[not-a-valid-url] PASSED [ 24%]
backend\tests\test_phase2_ingestion_api.py::test_malformed_url_rejected_422[ftp://downloads.example.org/archive.tar.gz] PASSED [ 27%]
backend\tests\test_phase2_ingestion_api.py::test_malformed_url_rejected_422[http://] PASSED [ 31%]
backend\tests\test_phase2_ingestion_api.py::test_malformed_url_rejected_422[https://] PASSED [ 34%]
backend\tests\test_phase2_ingestion_api.py::test_malformed_url_rejected_422[javascript:alert(1)] PASSED [ 37%]
backend\tests\test_phase2_ingestion_api.py::test_malformed_url_rejected_422[https://invalid url with spaces.com] PASSED [ 41%]
backend\tests\test_phase2_ingestion_api.py::test_malformed_url_rejected_422[http://localhost:invalidport] PASSED [ 44%]
backend\tests\test_phase2_ingestion_api.py::test_malformed_url_rejected_422[http:///foo] PASSED [ 48%]
backend\tests\test_phase2_ingestion_api.py::test_malformed_url_rejected_422[http://nosuchdomain] PASSED [ 51%]
backend\tests\test_phase2_ingestion_api.py::test_wrong_field_name_rejected_422 PASSED [ 55%]
backend\tests\test_phase2_ingestion_api.py::test_wrong_type_rejected_422 PASSED [ 58%]
backend\tests\test_phase2_ingestion_api.py::test_unexpected_fields_rejected_422 PASSED [ 62%]
backend\tests\test_phase2_ingestion_api.py::test_duplicate_ingestion_rejected_deterministic PASSED [ 65%]
backend\tests\test_phase2_ingestion_api.py::test_authenticated_removal_success PASSED [ 68%]
backend\tests\test_phase2_ingestion_api.py::test_nonexistent_removal PASSED [ 72%]
backend\tests\test_phase2_ingestion_api.py::test_metadata_enrichment_success_github PASSED [ 75%]
backend\tests\test_phase2_ingestion_api.py::test_metadata_enrichment_network_failure_produces_fallback PASSED [ 79%]
backend\tests\test_phase2_ingestion_api.py::test_metadata_enrichment_rate_limit_produces_fallback PASSED [ 82%]
backend\tests\test_phase2_ingestion_api.py::test_unexpected_programming_exception_not_swallowed PASSED [ 86%]
backend\tests\test_phase2_ingestion_api.py::test_persistence_journal_records_deterministic_events PASSED [ 89%]
backend\tests\test_phase2_ingestion_api.py::test_startup_recovery_restores_active_monitored_links PASSED [ 93%]
backend\tests\test_phase2_ingestion_api.py::test_journal_corruption_fails_closed PASSED [ 96%]
backend\tests\test_phase2_ingestion_api.py::test_journal_schema_corruption_fails_closed PASSED [100%]
======================= 29 passed, 2 warnings in 3.44s ========================
```

---

## 14. Identified Gaps & Required Remediation Tasks

The audit identifies three concrete engineering gaps that prevent an unconditional "A" classification:

### GAP 1: Replay Hash Verification & Tamper Detection (`SEC-JRN-001`)
- **Location:** `backend/control_plane/persistence/monitored_links_journal.py:replay_monitored_links`
- **Defect:** `record["record_hash"]` is ignored during replay. If any field of a record is tampered with, replay accepts it.
- **Required Remediation:** In `replay_monitored_links()`, compute the canonical SHA-256 hash over the record's payload (excluding `record_hash`) and assert equality with `record.get("record_hash")`. If mismatched or missing, raise `LineagePersistenceCorruptionError` fail-closed.

### GAP 2: Persistence Atomicity / Rollback on Write Failure (`ERR-ATOM-001`)
- **Location:** `backend/control_plane/backend/app/main.py:ingest_link` and `remove_link`
- **Defect:** In-memory state is modified before writing to disk. If `append_link_ingested` or `append_link_removed` fails, the in-memory state remains modified, leading to divergence between active state and persistent storage.
- **Required Remediation:** Wrap the memory mutation and journal write in a try-except block, or perform durable disk append *first* before exposing the link in `_INGESTED_LINKS` and `_LINK_METADATA`, or roll back memory on persistence error.

### GAP 3: Concurrency Race Protection on Link Ingestion (`CONC-001`)
- **Location:** `backend/control_plane/backend/app/main.py:ingest_link` and `remove_link`
- **Defect:** `_INGESTED_LINKS` has no thread lock. Two simultaneous requests for the same URL can pass the duplicate check in parallel while `_generate_link_metadata` executes, creating duplicate in-memory links and duplicate journal entries.
- **Required Remediation:** Introduce a concurrency lock (e.g. `_INGESTION_LOCK = threading.Lock()`) serializing the admission, duplicate check, and mutation sequence for monitored links.

---

## 15. Final Classification & Recommendation

### **FINAL CLASSIFICATION: B — PARTIALLY PROVEN; SPECIFIC REMEDIATION GAPS REMAIN**

Phase 2.3 has substantially elevated the security posture of the ingestion API:
- Zero authentication is closed (TokenAuth verified).
- Unvalidated dictionaries are closed (Strict Pydantic schemas verified).
- Silent error suppression is closed (Structured warnings and fallback states verified).
- Process-only memory is closed (Append-only journal and startup recovery verified).

However, because:
1. Replay does not verify `record_hash` integrity (`SEC-JRN-001`),
2. Mutations are visible before durable without compensating rollback (`ERR-ATOM-001`), and
3. Concurrent requests can race duplicate ingestion (`CONC-001`),

the implementation cannot be classified as fully proven (A). A bounded Phase 2.3.2 hardening remediation is recommended to close these three specific gaps.
