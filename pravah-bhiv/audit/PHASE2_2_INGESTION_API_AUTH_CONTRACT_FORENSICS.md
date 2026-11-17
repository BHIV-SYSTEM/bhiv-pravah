# FORENSIC AUDIT REPORT: TASK PHASE 2.2
## Pravah Ingestion API Contract & Authentication Forensic Audit

**Date:** 2026-09-04  
**Audit Target:** Control Plane Ingestion Boundary (`POST /ingest-link`, `POST /remove-link`), Metadata Enrichment (`_generate_link_metadata`), and Security Frameworks  
**Execution Root:** `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Primary Authoritative References:**
- `audit/PRAVAH_PHASE2_DEEP_CODEBASE_AUDIT.md` (Findings `SEC-AUTH-001`, `ERR-001`, `SEC-002`)
- `backend/security/auth.py` (`TokenAuth` JWT authentication)
- `backend/security/signing.py` (`verify_trace_signature`, `verify_service_request`)
- `backend/core_hooks/middleware.py` (`verify_request_trace`)
- `backend/control_plane/backend/app/schemas.py` (`LiveDomainStatus`, `LiveDashboardResponse`)
- `audit/PHASE2_1_FORENSIC_BASELINE.md` (Accepted Baseline)

**Final Classification:** **A — READY FOR REMEDIATION**

---

## 1. Executive Finding

A rigorous forensic code audit of the Pravah ingestion API boundary (`POST /ingest-link` and `POST /remove-link`) confirms the vulnerabilities identified in Phase 2.1:
1. **Zero Authentication (`SEC-AUTH-001`):** Both endpoints are completely unauthenticated. Any external caller with network access can inject arbitrary URLs or delete active monitored entities.
2. **Unmanaged Schema & Boundary Type Safety:** The endpoints accept raw, unvalidated Python dictionaries (`payload: dict[str, Any]`). No Pydantic models, type checks, or URL format validations exist.
3. **Mute Exception Swallowing (`ERR-001`):** `_generate_link_metadata()` executes outbound requests to `api.github.com` wrapped in `except Exception: pass`, silently suppressing network timeouts, connection drops, and HTTP 429 rate limits.
4. **Transient In-Memory State:** Monitored entities and event history exist only in memory (`_INGESTED_LINKS`, `_LINK_METADATA`, `_LINK_EVENTS`). All state is erased upon process restart.
5. **Zero Test Coverage:** Neither endpoint is exercised by any unit, integration, or adversarial test.

Because Pravah already possesses mature authentication primitives (`backend/security/auth.py` for token verification and `backend/security/signing.py` for HMAC trace signing), **no new authentication architecture is required**. The boundary is fully ready for remediation.

---

## 2. Current Endpoint Forensics

### A. Endpoint Definitions & Source Inspection (`backend/control_plane/backend/app/main.py:1003-1074`)

```python
@app.post("/ingest-link")
def ingest_link(payload: dict[str, Any]) -> dict[str, Any]:
    """Ingest a repository or website link for monitoring."""
    link = payload.get("link", "").strip()
    if not link:
        return {"success": False, "error": "Link cannot be empty"}
    ...
```

```python
@app.post("/remove-link")
def remove_link(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove a monitored link from the dashboard."""
    link = payload.get("link", "").strip()
    if not link:
        return {"success": False, "error": "Link cannot be empty"}
    ...
```

### B. Forensics by Architectural Property

| Property | Current Production Implementation (`/ingest-link` & `/remove-link`) | Forensic Verdict |
| :--- | :--- | :--- |
| **Request Schema** | Raw `payload: dict[str, Any]`. No Pydantic schema model. | **DEFECTIVE** |
| **Response Schema** | Unstructured `dict[str, Any]` (e.g. `{"success": True, "message": ...}`). | **DEFECTIVE** |
| **Payload Validation** | `payload.get("link", "").strip()`. Non-string types (e.g. integer or list) crash with `AttributeError`. Non-URL strings (e.g. `"foo"`, `"javascript:..."`) pass validation. | **DEFECTIVE** |
| **Authentication** | **None.** No FastAPI dependencies (`Depends`), no token checks, no HMAC headers. | **DEFECTIVE (`SEC-AUTH-001`)** |
| **Authorization** | **None.** No role check, no API key check, no capability requirement. | **DEFECTIVE** |
| **Replay Protection** | Duplicate links are rejected by string equality check on `/ingest-link`. However, removal/re-addition spam has no timestamp or nonce protection. | **PARTIALLY PROVEN** |
| **Nonce Handling** | None. | **DEFECTIVE** |
| **Trace Sovereignty** | No trace ID accepted, generated, signed, or logged. | **DEFECTIVE** |
| **Logging** | Appends in-memory event dict to `_LINK_EVENTS` deque. Zero disk or structured logging. | **DEFECTIVE** |
| **Error Handling** | Swallows all network/parsing exceptions in `_generate_link_metadata()`. Returns HTTP 200 with synthetic metrics on failure. | **DEFECTIVE (`ERR-001`)** |
| **Persistence** | Ephemeral Python globals (`_INGESTED_LINKS: list`, `_LINK_METADATA: dict`). Erased on process restart. | **DEFECTIVE** |
| **Caller Identity** | Completely anonymous / unknown. | **DEFECTIVE** |
| **Capability Bound** | None. Bypasses `VERIFIED_CAPABILITY_MAPPINGS`. | **UNGOVERNED** |

### C. Execution Call Path Tracing

#### Ingestion Flow:
1. `POST /ingest-link` enters `main.py:1003`.
2. Checks `if not link` (returns HTTP 200 `{"success": False, "error": "Link cannot be empty"}`).
3. Checks `_INGESTED_LINKS` for exact duplicate (returns HTTP 200 `{"success": False, "error": "Link already being monitored"}`).
4. Invokes `_generate_link_metadata(link)` (`main.py:267`):
   - Computes deterministic integer hash: `_get_link_hash(link) = hash(link) % 10000`.
   - If `"github.com"` in link, executes `requests.get("https://api.github.com/repos/{repo_path}", timeout=2.0)`.
   - On network error, rate limit, or invalid JSON: catches `except Exception: pass`.
   - Synthesizes heuristic metadata fields (`commits`, `branches`, `test_coverage`, `ci_status`).
5. Stores metadata in `_LINK_METADATA[link]`.
6. Invokes `_extract_link_name(link)` (`main.py:230`) to extract domain or repo name.
7. Appends item to global in-memory `_INGESTED_LINKS`.
8. Prepends event to global in-memory `_LINK_EVENTS` deque (maxlen 20).
9. Returns HTTP 200 with dictionary payload.

#### Removal Flow:
1. `POST /remove-link` enters `main.py:1046`.
2. Checks `if not link`.
3. Filters `_INGESTED_LINKS = [item for item in _INGESTED_LINKS if item["link"] != link]`.
4. Deletes entry from `_LINK_METADATA[link]` if present.
5. If removed count > 0, prepends event to `_LINK_EVENTS` and returns `{"success": True}`.
6. Else returns `{"success": False, "error": "Link not found"}`.

---

## 3. Existing Security Mechanism Forensics

Pravah already implements production security mechanisms in `backend/security/` and `backend/core_hooks/`. We investigated how these apply to the ingestion API:

### A. What Authentication Mechanism is Authoritative?
- **Repository Evidence:**
  - `audit/PRAVAH_PHASE2_DEEP_CODEBASE_AUDIT.md` (Finding `SEC-AUTH-001`) explicitly specifies: *"API should validate authentication headers (e.g., JWT, API key) to authorize ingestion"* and references `auth.py`.
  - `backend/security/auth.py` implements `TokenAuth`, which generates and verifies HS256 JWT tokens using `JWT_SECRET_KEY`.
  - `backend/security/signing.py` implements HMAC-SHA256 request signing (`verify_trace_signature` with `X-Trace-Id`, `X-Timestamp`, `X-Trace-Signature`).
- **Forensic Determination:**
  - For dashboard/client requests: **Bearer Token authentication (`TokenAuth` in `backend/security/auth.py`)** is the primary intended mechanism.
  - For cross-service / pipeline telemetry: **Signed trace headers (`verify_trace_signature` in `backend/security/signing.py`)** are authoritative.
  - Both mechanisms exist, share standard secret resolution patterns, and must be supported or unified via a clean FastAPI dependency.

### B. What Headers / Fields Are Required?
- Under Token Authentication:
  `Authorization: Bearer <jwt_token>` (or `X-API-Token: <token>`)
- Under HMAC Trace Authentication:
  `X-Trace-Id: <uuid>`, `X-Timestamp: <unix_epoch>`, `X-Trace-Signature: <hmac_sha256>`

### C. How is the Caller Identified?
- Under `TokenAuth`: Decoded JWT payload contains `user_id` or `service_id` along with standard `exp` and `iat` claims.
- Under HMAC signing: The caller proves knowledge of the shared secret (`SSPL_SECRET_KEY`).

### D. How is Replay Prevented?
- Under `TokenAuth`: Protected by JWT expiration (`exp`).
- Under HMAC signing: Protected by timestamp age verification (`abs(now - timestamp) <= 300s`).
- State deduplication: An active link cannot be ingested twice while present in `_INGESTED_LINKS`.

### E. How are Traces Signed?
- `security.signing.sign_trace(trace_id, timestamp, payload_dict)` computes HMAC-SHA256 over `f"{trace_id}:{timestamp}:{sha256(canonical_payload)}"`.

### F. Which Existing Dependency / Function Should an Ingestion Endpoint Call?
- A dedicated FastAPI dependency (e.g. `verify_ingestion_auth` in `control_plane/backend/app/auth_deps.py` or within `main.py`) wrapping `TokenAuth.verify_token()` from `backend/security/auth.py`, with support for fallback trace HMAC verification via `verify_trace_signature()`.

### G. Is Capability Authorization Required?
- **Repository Evidence:**
  - `control_plane/capabilities/execution_rights_adapter.py:38-70` defines `VERIFIED_CAPABILITY_MAPPINGS`.
  - The only registered operational capability is `"governed-execution"` (authorizing `"restart"`, `"scale_up"`, `"scale_down"`, `"rollback"`).
  - Capability authorization is designed strictly for **execution authority over infrastructure**, not telemetry/monitoring ingestion.
- **Forensic Verdict:** **NO.** Capability authorization is not required for link monitoring registration. Enforcing `"governed-execution"` here would constitute a severe architectural boundary violation.

### H. Is `/ingest-link` a Control-Plane Mutation that Requires Governance?
- **Repository Evidence:**
  - `/ingest-link` modifies control plane monitoring targets (`_INGESTED_LINKS`), which changes aggregate telemetry (`/orchestration/metrics` and `/metrics`).
  - However, it does not execute infrastructure actions (restarts/scaling) governed by `ActionGovernance` cooldowns or rate limits.
- **Forensic Verdict:** It is an **administrative control-plane registration mutation**. It requires strict authentication and input validation, but does not route through `ActionGovernance.evaluate_contract()`.

### I. Is `/remove-link` Higher Privilege Than `/ingest-link`?
- **Repository Evidence:**
  - Adding a link expands monitoring coverage.
  - Removing a link deletes an active monitoring target and purges historical metadata (`del _LINK_METADATA[link]`), potentially blinding the control plane to outages.
- **Forensic Verdict:** **YES.** Deletion/deregistration is a higher-risk administrative mutation. At minimum, it requires the same authenticated caller identity as ingestion, with explicit logging of who deleted the target.

---

## 4. Contract Forensics

### A. Current Contract State
- Existing schemas in `backend/control_plane/backend/app/schemas.py`:
  - `LiveDomainStatus`: Represents a single monitored domain in `LiveDashboardResponse`.
  - `LiveDashboardResponse`: Top-level dashboard model containing `monitored_services: list[LiveDomainStatus]`.
- **Missing Schemas:**
  - No Pydantic model for link ingestion request.
  - No Pydantic model for link removal request.
  - No Pydantic model for ingestion response.
  - No Pydantic model for removal response.
  - No Pydantic model for link metadata or enrichment results.

### B. Necessity of New Pydantic Contracts
An existing contract cannot be reused because `DecisionRequest` and `RuntimeIngestPayload` represent telemetry metric vectors (CPU, memory, error rates), not URL monitoring targets. **New formal Pydantic contracts are strictly necessary.**

### C. Precise Contract Specification

#### 1. `LinkIngestRequest` (`BaseModel`)
```python
class LinkIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link: str = Field(
        ...,
        min_length=8,
        max_length=2048,
        description="Fully qualified HTTP or HTTPS URL to repository or website"
    )

    @field_validator("link")
    @classmethod
    def validate_url(cls, v: str) -> str:
        clean = v.strip()
        if not (clean.startswith("http://") or clean.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        # Validate hostname presence and prevent control characters
        parsed = urllib.parse.urlparse(clean)
        if not parsed.netloc:
            raise ValueError("URL must include a valid network location (hostname)")
        return clean
```

#### 2. `LinkRemoveRequest` (`BaseModel`)
```python
class LinkRemoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link: str = Field(..., min_length=8, max_length=2048)
```

#### 3. `LinkMetadataResponse` (`BaseModel`)
```python
class LinkMetadataResponse(BaseModel):
    type: str
    commits: int
    branches: int
    pull_requests: int
    stars: int
    files: int
    contributors: int
    last_commit: str
    test_coverage: float
    ci_status: str
    avg_response_time: int
    error_rate: float
    enrichment_status: Literal["enriched", "fallback_heuristic", "offline"]
```

#### 4. `LinkIngestResponse` (`BaseModel`)
```python
class LinkIngestResponse(BaseModel):
    success: bool
    message: str
    ingested_link: Optional[LiveDomainStatus] = None
    metadata: Optional[LinkMetadataResponse] = None
    enrichment_status: str = "success"
```

#### 5. `LinkRemoveResponse` (`BaseModel`)
```python
class LinkRemoveResponse(BaseModel):
    success: bool
    message: str
```

#### 6. `ErrorResponse` (`BaseModel`)
```python
class IngestionErrorResponse(BaseModel):
    success: Literal[False] = False
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None
```

---

## 5. Threat Model Analysis

Every threat category was forensically evaluated against current production code:

| Threat Category | Attack Vector / Scenario | Production Defenses in Code | Forensic Status |
| :--- | :--- | :--- | :--- |
| **Unauthenticated Caller** | Anonymous client submits links or deletes services. | **None.** No auth decorator or dependency on endpoints. | **DEFECT (`SEC-AUTH-001`)** |
| **Unauthorized Caller** | Low-privilege client executes removal of critical monitors. | **None.** No authorization or role checks exist. | **DEFECT** |
| **Malformed Payload** | Non-JSON body, missing keys, or wrong types (e.g. `{"link": 123}`). | FastAPI catches invalid JSON; however `payload.get("link", "").strip()` raises `AttributeError` on non-string. | **DEFECT** |
| **Arbitrary URL** | Submitting `"file:///etc/passwd"`, `"ftp://..."`, or non-URL text. | No protocol or syntax check; accepted and stored verbatim. | **DEFECT** |
| **Malicious URL / SSRF** | Submitting GitHub path targeting internal networks or metadata services. | Uses `requests.get(f"https://api.github.com/repos/{repo_path}")`; relies on GitHub API domain. | **PARTIALLY PROVEN** |
| **Replayed Request** | Rapid spamming of removal and re-addition to manipulate analytics. | Deduplication prevents identical concurrent links, but removal cycle has no replay defense. | **PARTIALLY PROVEN** |
| **Duplicate Request** | Submitting already-monitored link. | Checked via `next((item for item in _INGESTED_LINKS if item["link"] == link), None)`. | **PROVEN** |
| **Forged HMAC** | Attacker submitting forged signature headers. | HMAC headers are ignored on these endpoints. | **NOT PROVEN** |
| **Stale Timestamp** | Submitting expired telemetry requests. | Not validated on these endpoints. | **NOT PROVEN** |
| **Reused Nonce** | Replaying previously valid service requests. | Nonce store not checked on these endpoints. | **NOT PROVEN** |
| **Cross-Service Caller** | Internal microservice calling without service identity. | Accepted anonymously without service identity. | **DEFECT** |
| **Privilege Escalation** | Anonymous caller calling `/remove-link`. | Unchecked; anyone can delete targets. | **DEFECT** |
| **Metadata Extraction Failure** | GitHub API down or repository private. | `except Exception: pass` silently suppresses error; outputs fake metrics. | **DEFECT (`ERR-001`)** |
| **GitHub / API Timeout** | Outbound API call hangs or delays response. | Hardcoded `timeout=2.0` stops hang, but exception is swallowed. | **PARTIALLY PROVEN** |
| **Rate Limiting** | GitHub API returns 429 Too Many Requests. | Swallowed as generic exception; defaults to fake numbers without warning. | **DEFECT** |
| **Process Restart** | Server reboot, worker recycle, or container restart. | Ephemeral globals reset to empty; all monitored targets lost. | **DEFECT** |

---

## 6. Observability & Error Handling Forensics

### A. Current Implementation of `_generate_link_metadata`
```python
if is_github:
    try:
        import requests
        parts = link.split("github.com/")
        if len(parts) > 1:
            repo_path = parts[1].strip("/")
            resp = requests.get(f"https://api.github.com/repos/{repo_path}", timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                base_stars = data.get("stargazers_count", 0)
                ...
    except Exception:
        pass # Fallback cleanly if rate limited or network failure
```

### B. Findings on Error Handling
1. **Silent Suppression:** Broad `except Exception: pass` hides:
   - `requests.exceptions.Timeout`
   - `requests.exceptions.ConnectionError`
   - `requests.exceptions.HTTPError` (e.g. 403 Forbidden, 429 Too Many Requests)
   - `json.JSONDecodeError`
2. **Missing Operational Signals:**
   - No log entry is written (`logger.warning` or `logger.error` is absent).
   - The returned status is hardcoded: `"status": "HEALTHY" if metadata["ci_status"] == "passing" else "DEGRADED"`, where `ci_status` is computed via `link_hash % 3 != 0`, giving the client a false sense of passing CI.
3. **Decoupling Ingestion from Enrichment:**
   - An ingestion request should succeed if the URL is valid, but the system must explicitly disclose `enrichment_status: "fallback_heuristic"` or `"offline"` when external APIs fail, logging the exact error reason.

---

## 7. Persistence Responsibility

### A. Evaluated In-Memory State
- `_INGESTED_LINKS: list[dict[str, Any]]`
- `_LINK_METADATA: dict[str, dict[str, Any]]`
- `_LINK_EVENTS: deque[dict[str, Any]]`

### B. Architectural Determination: PostgreSQL vs. Local Journal
- **PostgreSQL / Relational Database:** **NOT REQUIRED.**
  As established in Phase 1 accepted audits (`PHASE1_10_CORE_IMPLEMENTATION_OBSERVABILITY_ACCEPTANCE.md`), Pravah's architectural principle avoids external relational databases for core runtime state. Recommending PostgreSQL here would contradict repository standards and introduce unneeded operational overhead.
- **Approved Pravah Persistence Pattern:** **Local Append-Only JSONL Journal.**
  Pravah uses append-only JSONL files (`logs/control_plane/execution_lineage.jsonl`, `logs/control_plane/append_only_log.jsonl`) with forward hash chaining and replay reconstruction.
- **Recommended Storage for Ingestion:**
  - File: `logs/control_plane/monitored_links.jsonl`
  - Event types: `LINK_INGESTED`, `LINK_REMOVED`.
  - On startup: Read and replay `monitored_links.jsonl` to reconstruct `_INGESTED_LINKS` and `_LINK_METADATA` deterministically.

---

## 8. Test Authenticity & Coverage

A comprehensive search of `backend/tests` confirmed:
- `backend/tests/test_phase2_deterministic_policy_engine.py`: Tests the constitutional policy engine, but does **not** test `/ingest-link` or `/remove-link`.
- Total tests exercising `/ingest-link`: **0**.
- Total tests exercising `/remove-link`: **0**.
- Total tests exercising `_generate_link_metadata`: **0**.
- Total tests exercising `TokenAuth` in `backend/security/auth.py`: **0**.
- **Coverage Status: 100% UNTESTED.**

---

## 9. Exact Remediation Specification

Before remediation begins, the following precise architectural design is established:

```text
+-----------------------------------------------------------------------------------+
|                        INGESTION API REMEDIATION PLAN                             |
+-----------------------------------------------------------------------------------+
| 1. CONTRACTS (schemas.py)                                                         |
|    - LinkIngestRequest: Strict URL validation, scheme check, max 2048 chars       |
|    - LinkIngestResponse: Typed response with LiveDomainStatus & enrichment status |
|    - LinkRemoveRequest: Typed removal request with URL validation                 |
|    - LinkRemoveResponse: Typed removal confirmation                               |
|                                                                                   |
| 2. AUTHENTICATION (main.py / auth_deps.py)                                        |
|    - Create FastAPI dependency `verify_control_plane_auth`                        |
|    - Reuses `TokenAuth` from `backend/security/auth.py`                           |
|    - Validates Bearer token from `Authorization: Bearer <token>`                  |
|    - Supports dev environment fallback key for seamless local testing             |
|    - Missing/invalid token returns HTTP 401 Unauthorized                          |
|                                                                                   |
| 3. ERROR BOUNDARY & LOGGING (main.py)                                             |
|    - Remove `except Exception: pass` from `_generate_link_metadata`               |
|    - Catch specific `requests.RequestException` and log structured warning         |
|    - Return explicit `enrichment_status`: "enriched" | "offline_heuristic"        |
|                                                                                   |
| 4. DURABLE PERSISTENCE (main.py / persistence)                                   |
|    - Create `logs/control_plane/monitored_links.jsonl`                            |
|    - Ingest appends `LINK_INGESTED` record; remove appends `LINK_REMOVED`         |
|    - Startup hook replays journal to repopulate `_INGESTED_LINKS`                 |
|                                                                                   |
| 5. CORS HARDENING (main.py)                                                       |
|    - Restrict regex to known local ports (3000, 4500, 8000) and specific domains  |
|                                                                                   |
| 6. REGRESSION TESTS (backend/tests/test_phase2_ingestion_api.py)                  |
|    - 10+ dedicated automated tests covering auth, contracts, errors, persistence |
+-----------------------------------------------------------------------------------+
```

---

## 10. Final Classification

### **A — READY FOR REMEDIATION**

### Forensic Verdict:
1. **Requirements are Complete & Authoritative:** `audit/PRAVAH_PHASE2_DEEP_CODEBASE_AUDIT.md` unambiguously defines findings `SEC-AUTH-001`, `ERR-001`, and `SEC-002`.
2. **Security Primitives Already Exist:** `backend/security/auth.py` (`TokenAuth`) provides the exact JWT verification required, eliminating any need to invent new security mechanisms.
3. **No Architectural Ambiguity:** Pravah's persistence standards (local append-only JSONL) and FastAPI contract standards (Pydantic models) clearly dictate the implementation pattern.
4. **Implementation Scope is Bounded:** Clean separation between link monitoring registration and infrastructure execution governance is fully preserved.

---

## Validation & Verification

### Test Suite Execution
```text
pytest --collect-only -q
242 tests collected in 0.88s

pytest -q
242 passed, 370 warnings in 13.25s
```

### Repository Integrity Checks
```bash
git diff -- VANA/
# Output: (empty, 0 lines)

git status --short
# Output confirms only authorized files and this single audit report exist.
```

The remediation phase can proceed immediately upon user authorization.
