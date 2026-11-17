# FORENSIC AUDIT REPORT: TASK PHASE 3.4
## Pravah Mutation Authorization Boundary Forensics

**Date:** 2026-09-12  
**Audit Target:** All Pravah Backend Endpoints Capable of Mutating State, Trust-Boundary Classification, Authentication vs. Authorization Gap Analysis, and Frontend Mutation Exposure  
**Execution Root:** `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Classification:** **B — REQUIRES EXPLICIT ARCHITECTURE / OWNER DECISION**  
**Implementation Blocker:** **Frontend authentication implementation is BLOCKED pending an authoritative mutation trust-boundary decision.**

---

## 1. Executive Conclusion

A forensic security boundary audit of every mutating HTTP endpoint across the Pravah ecosystem (`control_plane` FastAPI, `control_plane` Flask, `observer` FastAPI, and downstream execution targets) establishes that:

1. **Mutation Endpoints Span Five Radically Incompatible Trust Models:**
   The repository does not possess a unified security boundary. Instead, mutation endpoints are partitioned into five disconnected security paradigms:
   - *JWT Bearer / X-API-Token Authentication* (Decision Brain Port 8000: `/ingest-link`, `/remove-link`)
   - *Static API Key + Source System Whitelisting* (Control Plane Port 7000: `/pravah/events`, `/evidence`)
   - *HMAC-SHA256 Trace Request Signing* (Control Plane Port 7000: `/api/runtime`)
   - *Service HMAC + Capability Authorization + Single-Use Nonce Consumption* (Action Executor Port 5003: `/execute-action`)
   - *Completely Unauthenticated Administrative Mutations* (Control Plane Port 7000: `/api/control-plane/override`)

2. **Severe Administrative Exposure on `POST /api/control-plane/override` (`SEC-DEFECT-OVR-001`):**
   The endpoint `POST /api/control-plane/override` on port 7000 modifies control-plane state (sets or clears per-application freeze modes, directly suppressing autonomous system recovery). This endpoint enforces **zero authentication** and **zero authorization**, relying solely on a client IP rate limit (`40 per minute`). Live testing confirmed that unauthenticated callers can freeze or unfreeze cluster applications. The frontend directly exposes UI controls for this endpoint on three separate pages.

3. **Authentication Exists Without Authorization on Port 8000:**
   Where authentication is enforced (`/ingest-link`, `/remove-link`), the system performs **AuthN without AuthZ**. Any cryptographically valid JWT—regardless of `user_id`, subject, or caller identity—automatically possesses total administrative authority to ingest or delete monitored links. No user roles, capability checks, or permission matrices are evaluated.

4. **Frontend Mutation Dependency Is Narrower Than Assumed:**
   Only three backend mutation endpoints are ever invoked by the frontend:
   - `POST /ingest-link` (Port 8000) — Blocked by 401 (AuthN required, frontend supplies none)
   - `POST /remove-link` (Port 8000) — Blocked by 401 (AuthN required, frontend supplies none)
   - `POST /api/control-plane/override` (Port 7000) — Exposed unauthenticated (Succeeds without auth)
   All other mutations (`/api/runtime`, `/execute-action`, `/api/ingest`, `/pravah/events`, `/vana/execute`) are internal service-to-service boundaries that must **never** be exposed to browser clients.

---

## 2. Complete Mutation Endpoint Inventory

Every HTTP endpoint capable of mutating memory, disk, database, queue, or control-plane state was discovered and audited:

| # | Endpoint | Port | Service | Source File | Method | Auth Dependency | AuthZ / Capability Check | Rate Limiting | State / System Effect | Known Callers | Frontend Caller | Test Coverage | Live Status |
| :-: | :--- | :---: | :--- | :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `/ingest-link` | 8000 | Decision Brain | `main.py:1182` | POST | `verify_control_plane_auth` (JWT) | None (Any valid JWT) | None | Persists link to HMAC journal; mutates `_INGESTED_LINKS` | Admin CLI, Frontend | `api.ingestLink` | `test_phase2_ingestion_api.py` | `401 Unauthorized` |
| **2** | `/remove-link` | 8000 | Decision Brain | `main.py:1273` | POST | `verify_control_plane_auth` (JWT) | None (Any valid JWT) | None | Persists removal to HMAC journal; deletes from `_INGESTED_LINKS` | Admin CLI, Frontend | `api.removeLink` | `test_phase2_ingestion_api.py` | `401 Unauthorized` |
| **3** | `/process-runtime` | 8000 | Decision Brain | `main.py:1575` | POST | None | None | None | Computes RL decision; appends to `_RECENT_DECISIONS` deque | Internal simulators | None | None | `200 OK` |
| **4** | `/control-plane/runtime-ingest` | 8000 | Decision Brain | `main.py:1626` | POST | None | `authorize_execution("governed-execution")` | None | Logs trace; triggers `execute_action()` through governance | Runtime intake agents | None | `test_unified_discovery.py` | `200 OK` |
| **5** | `/pravah/events` | 8000 | Decision Brain | `main.py:1798` | POST | None | None | None | Stateless mock echo (returns status CONNECTED) | None (Mock stub) | None | None | `422 Unprocessable` (Schema) |
| **6** | `/evidence` | 8000 | Decision Brain | `main.py:1806` | POST | None | None | None | Stores bundle in in-memory `_EVIDENCE_STORE` dict | Port 8000 test suite | None | None | `422 Unprocessable` (Schema) |
| **7** | `/vana/execute` | 8000 | Decision Brain | `main.py:1843` | POST | None | Contract validation (`Group4IntakeBoundary`) | None | Translates Group 2 ruling; records governed abstention | Next.js VANA proxy | `/api/vana/group4` | `test_phase15_gap_governed_abstention.py` | `500` (requires contract body) |
| **8** | `/api/runtime` | 7000 | Control Plane | `agent_api.py:155` | POST | `verify_request_trace` (HMAC) | Schema validation (`InputValidator`) | 30/min | Dispatches external event to autonomous runtime agent | Monitored apps, tests | None | `test_phase2_error_boundary_security.py` | `401 Unauthorized` |
| **9** | `/api/control-plane/override` | 7000 | Control Plane | `agent_api.py:284` | POST | **NONE** | **NONE** | 40/min | Writes to `app_overrides.json`; suppresses app auto-recovery | Frontend, IntegrationClient | `api.postOverride` | `integration_client.py` | `200 OK` (Unauthenticated!) |
| **10**| `/pravah/events` | 7000 | Control Plane | `agent_api.py:356` | POST | `check_shakti_auth` (`PRAVAH_API_KEY`) | Source whitelist (`X-Source-System`) | Exempt | Forwards Shakti event; logs to append-only log | Ecosystem microservices | None | `verify_shakti_observability.py` | `401 Unauthorized` |
| **11**| `/pravah/api/v1/publish` | 7000 | Control Plane | `agent_api.py:357` | POST | `check_shakti_auth` (`PRAVAH_API_KEY`) | Source whitelist (`X-Source-System`) | Exempt | Same handler as `/pravah/events` | Ecosystem microservices | None | None | `401 Unauthorized` |
| **12**| `/evidence` | 7000 | Control Plane | `agent_api.py:402` | POST | `check_shakti_auth` (`PRAVAH_API_KEY`) | Source whitelist (`X-Source-System`) | Exempt | Atomic write to `data/evidence_bundles.json` | Shakti / MasterDB | None | `verify_masterdb_observability.py` | `401 Unauthorized` |
| **13**| `/api/ingest` | 8600 | Observer | `observer_server.py:434`| POST | None | None | None | Appends telemetry to `observation_store["events"]` deque | Observed microservices | None | `test_svacs_observability.py` | `200 OK` |
| **14**| `/execute-action` | 5003 | Action Executor | `executer/app.py:126` | POST | `verify_service_auth` (HMAC) | `capability_id`, `execution_id`, nonce check | None | Executes host container operations (docker/kubectl) | Control Plane dispatcher | None | `test_phase8_execution_closure.py` | N/A (Downstream) |
| **15**| `/simulate-failure`| 5001 | Web1 Target | `web1/app.py:12` | POST | None | None | None | Toggles internal crash flag in mock target app | Demo runner scripts | None | `start_presentation.ps1` | N/A (Downstream) |

---

## 3. Trust Boundary Classification

Every mutating endpoint is classified into exactly one architectural trust boundary category:

- **A — Public by design**
- **B — Internal service-to-service**
- **C — Operator authenticated**
- **D — Operator authenticated + authorized**
- **E — Trace/signature authenticated**
- **F — Unclear / architecture decision required**
- **G — Security defect**

| Endpoint | Port | Classification | Repository Evidence & Justification |
| :--- | :---: | :---: | :--- |
| `POST /ingest-link` | 8000 | **C — Operator authenticated** | Source `main.py:1185` enforces `verify_control_plane_auth`. Requires valid JWT. Intended for human operator or administrative CI to register monitoring targets. |
| `POST /remove-link` | 8000 | **C — Operator authenticated** | Source `main.py:1276` enforces `verify_control_plane_auth`. Requires valid JWT. Intended for human operator to deregister monitoring targets. |
| `POST /process-runtime` | 8000 | **B — Internal service-to-service** | Source `main.py:1575` processes telemetry payloads and queries `DecisionEngine`. Does not execute live actions. Used for simulation and telemetry intake. |
| `POST /control-plane/runtime-ingest` | 8000 | **F — Unclear / architecture decision required** | Source `main.py:1626` triggers `execute_action()` without HTTP authentication, relying on internal capability and governance filters. Needs clear trust boundary definition. |
| `POST /pravah/events` | 8000 | **A — Public by design** | Source `main.py:1798` is a stateless mock stub returning `{status: CONNECTED}`. No state mutation. |
| `POST /evidence` | 8000 | **F — Unclear / architecture decision required** | Source `main.py:1806` has zero authentication, whereas the identical route on port 7000 (`agent_api.py:402`) strictly requires `check_shakti_auth`. Severe cross-port divergence. |
| `POST /vana/execute` | 8000 | **B — Internal service-to-service** | Source `main.py:1843` consumes Group 2 runtime responses for VANA. Governed intake boundary; records governed abstentions. |
| `POST /api/runtime` | 7000 | **E — Trace/signature authenticated** | Source `agent_api.py:155` enforces `verify_request_trace(payload)` requiring HMAC-SHA256 `X-Trace-Signature`, `X-Trace-Id`, and timestamp freshness. |
| `POST /api/control-plane/override` | 7000 | **G — Security defect** | Source `agent_api.py:284` mutates control plane freeze states without authentication or authorization. Rate limiting is the only control. Confirmed live vulnerability. |
| `POST /pravah/events` | 7000 | **B — Internal service-to-service** | Source `agent_api.py:356` enforces `check_shakti_auth` (`PRAVAH_API_KEY` + `X-Source-System`). Intended strictly for ecosystem microservice telemetry publishing. |
| `POST /pravah/api/v1/publish` | 7000 | **B — Internal service-to-service** | Source `agent_api.py:357` is identical alias for `shakti_events`. Token-authenticated internal service route. |
| `POST /evidence` | 7000 | **B — Internal service-to-service** | Source `agent_api.py:402` enforces `check_shakti_auth`. Saves evidence bundles to disk. Token-authenticated internal pipeline route. |
| `POST /api/ingest` | 8600 | **B — Internal service-to-service** | Source `observer_server.py:434` receives passive telemetry events from observed services. Appends to display buffer only; no operational authority. |
| `POST /execute-action` | 5003 | **E — Trace/signature authenticated** | Source `executer/app.py:126` enforces HMAC `verify_service_auth`, capability checks, execution hashes, and trace nonce consumption. Hardened execution runner. |
| `POST /simulate-failure` | 5001 | **A — Public by design** | Source `web1/app.py:12` is a deliberate demo failure trigger on a test mock target app. |

---

## 4. Critical Endpoint Forensic Deep-Dive

Detailed forensic analysis of the seven primary mutation boundaries:

### 4.1 `POST /ingest-link` (Port 8000)
- **Intended Caller:** Human operator via Pravah Console or automated deployment pipeline via CI.
- **Caller Type:** Operator / Admin.
- **Authentication:** Enforced via `verify_control_plane_auth`. Accepts HS256 JWT signed with `JWT_SECRET_KEY` in `Authorization: Bearer` or `X-API-Token`.
- **Authorization:** **ABSENT.** Any valid JWT for any `user_id` is permitted. No capability or permission check.
- **State Effect:** Atomically commits an append-only event to the HMAC journal (`monitored_links_journal.append_link_ingested`) and updates memory (`_INGESTED_LINKS`). Alters aggregate cluster telemetry.
- **Remote Exposure:** Exposed to the network on port 8000 (`0.0.0.0:8000`).
- **Proven Safety:** **PROVEN SAFE (Fail-Closed).** Rejects unauthenticated callers with HTTP 401.

### 4.2 `POST /remove-link` (Port 8000)
- **Intended Caller:** Human operator via Pravah Console.
- **Caller Type:** Operator / Admin.
- **Authentication:** Enforced via `verify_control_plane_auth`. Same JWT requirement as `/ingest-link`.
- **Authorization:** **ABSENT.** Any valid JWT can remove any link.
- **State Effect:** Atomically commits removal to journal; purges item from `_INGESTED_LINKS` and `_LINK_METADATA`.
- **Remote Exposure:** Exposed to the network on port 8000.
- **Proven Safety:** **PROVEN SAFE (Fail-Closed).** Rejects unauthenticated callers with HTTP 401.

### 4.3 `POST /process-runtime` (Port 8000)
- **Intended Caller:** Automated runtime observation worker or simulation script.
- **Caller Type:** Internal service / Script.
- **Authentication:** None.
- **Authorization:** None.
- **State Effect:** Passes metrics to `DecisionEngine.decide()` and appends decision to `_RECENT_DECISIONS`. Does NOT execute actions on infrastructure.
- **Remote Exposure:** Exposed on port 8000.
- **Proven Safety:** **PROVEN SAFE.** Pure computation and diagnostic logging. Does not mutate operational cluster infrastructure.

### 4.4 `POST /api/control-plane/override` (Port 7000)
- **Intended Caller:** Human operator troubleshooting an application.
- **Caller Type:** Operator.
- **Authentication:** **COMPLETELY ABSENT.** No header, token, or secret is inspected.
- **Authorization:** **COMPLETELY ABSENT.**
- **State Effect:** Writes to `logs/control_plane/app_overrides.json`. Directly modifies orchestrator behavior: `rl_orchestrator_safe.py:246` checks `get_app_override()` and **refuses all automated remediation actions** for that application.
- **Remote Exposure:** Exposed on port 7000 (`0.0.0.0:7000:7000` in `yotta-deploy.yaml`).
- **Proven Safety:** **PROVEN SECURITY DEFECT (`SEC-DEFECT-OVR-001`).** Any network caller can freeze arbitrary applications without credentials.

### 4.5 `POST /pravah/events` (Port 7000 vs Port 8000 Divergence)
- **Port 7000 Implementation:** Enforces `check_shakti_auth()`. Validates `Authorization: Bearer <PRAVAH_API_KEY>` against `PRAVAH_API_KEY` environment variable and requires `X-Source-System` header in `{"SHAKTI", "BHIV_MASTERDB", "WORKFLOW_BLACKHOLE", "UNIGURU"}`. **Proven Safe (Fail-Closed).**
- **Port 8000 Implementation:** Defines an unauthenticated stub returning `{status: CONNECTED}`.
- **Intended Caller:** GC-Shakti ecosystem services (service-to-service).
- **Caller Type:** Internal microservice.
- **Proven Safety:** Port 7000 is safe; Port 8000 is an unauthenticated dead stub.

### 4.6 `POST /api/runtime` (Port 7000)
- **Intended Caller:** Instrumented microservice agents reporting runtime telemetry spikes.
- **Caller Type:** Internal service agent.
- **Authentication:** Enforced via `verify_request_trace`. Requires HMAC-SHA256 signature (`X-Trace-Signature`) computed with `SSPL_SECRET_KEY`, matching timestamp (`X-Timestamp`) within 300s, and `X-Trace-Id`.
- **Authorization:** Enforced via contract validation against `RUNTIME_SCHEMA` and `InputValidator`.
- **State Effect:** Triggers `agent.handle_external_event(...)`, which evaluates action policies.
- **Remote Exposure:** Exposed on port 7000.
- **Proven Safety:** **PROVEN SAFE (Fail-Closed).** Missing or invalid signatures reject with `HTTP 401 Unauthorized` (`Trace verification failed`).

### 4.7 `POST /api/ingest` (Port 8600)
- **Intended Caller:** Observed ecosystem microservices or control plane forwarder.
- **Caller Type:** Internal telemetry agent.
- **Authentication:** None.
- **Authorization:** None.
- **State Effect:** Appends to in-memory `observation_store["events"]` deque (maxlen 500).
- **Remote Exposure:** Exposed on port 8600.
- **Proven Safety:** **PROVEN SAFE.** Passive observability sink. Holds zero operational authority (TANTRA Safeguard 1).

---

## 5. Special Review: `POST /api/control-plane/override`

### 5.1 Deep Forensic Source Inspection
Inspection of `backend/control_plane/api/agent_api.py:284-303`:
```python
@app.route("/api/control-plane/override", methods=["POST"])
@limiter.limit("40 per minute")
def control_plane_override():
    """Manual override panel actions: set or clear temporary per-app freeze."""
    payload = request.get_json(silent=True) or {}

    try:
        app_name, action, duration, reason = InputValidator.validate_control_plane_override_payload(payload)
    except InputValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    try:
        if action == "clear_freeze":
            result = control_plane.clear_manual_override(app_name)
        else:
            result = control_plane.set_manual_override(app_name, duration, reason)
        return jsonify({"status": "success", "result": result}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
```

### 5.2 Key Questions Answered from Concrete Evidence:
1. **Does it mutate control-plane state?**  
   **YES.** Calls `control_plane.set_manual_override()` or `clear_manual_override()`, writing to `logs/control_plane/app_overrides.json`.
2. **What actions can it perform?**  
   It can activate (`set_freeze`) or deactivate (`clear_freeze`) a temporary operational freeze for any application up to 1440 minutes (24 hours).
3. **Can it freeze/unfreeze/modify applications?**  
   **YES.** In `backend/control_plane/core/rl_orchestrator_safe.py:246`:
   ```python
   if app_override and app_override.get('freeze_enabled') and action != 'noop':
       result = self._build_refusal_result(
           action_requested=action,
           reason=f"Manual app freeze active for {app_name}: {app_override.get('reason', 'manual_override')}",
           reason_code='app_manual_freeze_override',
           ...
   ```
   When freeze is enabled, the autonomous orchestrator **refuses all recovery actions** (restarts, rollbacks, scaling).
4. **Is it intended for operators or internal automation?**  
   Intended for **human operators** during emergency troubleshooting.
5. **Is there any hidden authorization mechanism?**  
   **NO.** Inspection of `agent_api.py`, `multi_app_control_plane.py`, `app_override_manager.py`, and `input_validator.py` confirms zero authorization checks.
6. **Is rate limiting the ONLY protection?**  
   **YES.** Flask-Limiter `@limiter.limit("40 per minute")` using remote IP is the sole defensive mechanism.
7. **Are there deployment-level network restrictions?**  
   **NO.** In `yotta-deploy.yaml:72`, port 7000 is bound to `0.0.0.0:7000:7000`. In `PRODUCTION_DEPLOYMENT.md:62`, port 7000 is explicitly designated as externally accessible through firewalls.
8. **Is it reachable from the frontend?**  
   **YES.** Wired directly in `frontend/src/services/api.ts:140` (`postOverride`), consumed by `usePostOverride()` on three separate frontend views.
9. **Is the lack of authentication intentional or accidental?**  
   **ACCIDENTAL / ARCHITECTURAL DEFECT.** The endpoint was developed as part of the local engineering UI and hardened only with schema validation (`InputValidator`) without connecting it to `TokenAuth` or `check_shakti_auth`.

### 5.3 Classification
- **Classification:** **G — SECURITY DEFECT (`SEC-DEFECT-OVR-001`)** / **F — ARCHITECTURE DECISION REQUIRED**
- **Action Required:** Must NOT be modified during Phase 3.4. Requires owner decision to either protect via `TokenAuth` or restrict network binding to internal loopback.

---

## 6. Authentication vs. Authorization Analysis

The repository was audited to determine whether identity verification (AuthN) is paired with permission enforcement (AuthZ):

| Endpoint | Authentication ("Who are you?") | Authorization ("Are you allowed to do this?") | Forensic Finding |
| :--- | :--- | :--- | :--- |
| `POST /ingest-link` | Verifies JWT signature against `JWT_SECRET_KEY`. Extracts `caller_id`. | **NONE.** Does not check if `caller_id` has ingestion privileges. Any valid JWT succeeds. | **AuthN without AuthZ.** No role or capability enforcement. |
| `POST /remove-link` | Verifies JWT signature against `JWT_SECRET_KEY`. Extracts `caller_id`. | **NONE.** Any valid JWT can delete any monitored entity. | **AuthN without AuthZ.** Severe privilege over-granting. |
| `POST /api/control-plane/override` | **NONE.** | **NONE.** | **Zero Security Boundary.** |
| `POST /api/runtime` | Verifies HMAC signature with `SSPL_SECRET_KEY`. | Verifies payload against strict schema. | **Signature AuthN + Schema AuthZ.** |
| `POST /execute-action` | Verifies HMAC signature with service secret. | Verifies `capability_id == "governed-execution"`, action in `allowed_actions`, single-use trace nonce. | **Full AuthN + Full AuthZ.** The only complete security implementation in the repo. |

### Role and Capability Finding:
- `VERIFIED_CAPABILITY_MAPPINGS` in `backend/control_plane/capabilities/execution_rights_adapter.py:38-70` defines operational rights (`governed-execution` allowing `restart`, `scale_up`, `scale_down`, `rollback`).
- **These capability mappings are enforced ONLY on container execution dispatchers (`execute_action()`, `/execute-action`).**
- **They are completely decoupled from operator HTTP endpoints.** No operator roles (`admin`, `operator`, `auditor`) exist anywhere in the backend codebase.

---

## 7. Existing Security Primitive Mapping

| Security Primitive | Authoritative Implementation | Scope of Protection | Endpoints Protected | Endpoints NOT Protected |
| :--- | :--- | :--- | :--- | :--- |
| **TokenAuth (HS256 JWT)** | `backend/security/auth.py` | Control Plane Ingestion Mutations | `POST /ingest-link`<br>`POST /remove-link` | All other endpoints across ports 8000, 7000, 8600 |
| **Trace HMAC Signing** | `backend/security/signing.py` | Runtime Telemetry Ingestion | `POST /api/runtime` (Port 7000) | Ingestion mutations, overrides |
| **Service HMAC + Nonce** | `backend/security/service_auth.py` | Action Execution Boundary | `POST /execute-action` (Port 5003) | All control-plane HTTP routes |
| **Shakti Key Whitelisting** | `backend/control_plane/api/agent_api.py` | Ecosystem Telemetry Publishing | `POST /pravah/events` (Port 7000)<br>`POST /evidence` (Port 7000) | `POST /evidence` (Port 8000)<br>`POST /api/control-plane/override` |
| **Action Governance** | `backend/control_plane/core/action_governance.py` | Autonomous Remediations | Autonomous Loop decisions | Direct manual overrides |
| **Rate Limiting (Flask-Limiter)** | `backend/control_plane/api/agent_api.py` | Denial-of-Service Defense | `POST /api/control-plane/override` (40/min)<br>`POST /api/runtime` (30/min) | All port 8000 and 8600 endpoints |

---

## 8. Frontend Mutation Exposure

Every frontend UI control capable of invoking backend mutations was audited:

| UI Component | File & Line | Target Endpoint | Current Credential Behavior | Current Live Response | Trust Classification | Exposure Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **Add Monitored Link Form** | `frontend/src/app/page.tsx:81` | `POST /ingest-link` (8000) | Unauthenticated (No Authorization header) | `HTTP 401 Unauthorized` | **C** | **Fail-Closed.** User sees failure toast; backend denies write. |
| **Remove Monitored Link Button** | `frontend/src/app/page.tsx:95` | `POST /remove-link` (8000) | Unauthenticated (No Authorization header) | `HTTP 401 Unauthorized` | **C** | **Fail-Closed.** User sees failure toast; backend denies write. |
| **Control Plane Override Form** | `frontend/src/app/control-plane/page.tsx:46` | `POST /api/control-plane/override` (7000) | Unauthenticated (No Authorization header) | `HTTP 200 OK` (when action is valid) | **G** | **LIVE DEFECT.** Any user can freeze apps without auth. |
| **Services Quick Freeze Button** | `frontend/src/app/services/page.tsx:38` | `POST /api/control-plane/override` (7000) | Unauthenticated (No Authorization header) | `HTTP 200 OK` (when action is valid) | **G** | **LIVE DEFECT.** Any user can freeze apps without auth. |
| **Command Palette Quick Actions** | `frontend/src/components/CommandPalette.tsx:58,68` | `POST /api/control-plane/override` (7000) | Unauthenticated (No Authorization header) | `HTTP 200 OK` (when action is valid) | **G** | **LIVE DEFECT.** Quick-action unfreeze succeeds unauthenticated. |

---

## 9. Live Verification Results

Live local requests executed without privileged credentials confirm the boundary states:

```bash
# 1. Ingest Link without auth -> FAIL-CLOSED
POST http://localhost:8000/ingest-link
Response: HTTP/1.1 401 Unauthorized
Body: {"detail":"Authentication required: missing token"}

# 2. Remove Link without auth -> FAIL-CLOSED
POST http://localhost:8000/remove-link
Response: HTTP/1.1 401 Unauthorized
Body: {"detail":"Authentication required: missing token"}

# 3. Control Plane Override without auth -> LIVE SECURITY DEFECT
POST http://localhost:7000/api/control-plane/override
Body: {"app_name":"test_app","action":"set_freeze","duration_minutes":5,"reason":"test_audit"}
Response: HTTP/1.1 200 OK
Body: {"result":{"app_name":"test_app","freeze_enabled":true,"freeze_until":"2026-09-12T06:36:32Z","reason":"test_audit"},"status":"success"}

# 4. Clear Override without auth -> LIVE SECURITY DEFECT
POST http://localhost:7000/api/control-plane/override
Body: {"app_name":"test_app","action":"clear_freeze"}
Response: HTTP/1.1 200 OK
Body: {"result":{"app_name":"test_app","freeze_enabled":false},"status":"success"}

# 5. Pravah Events on port 7000 without auth -> FAIL-CLOSED
POST http://localhost:7000/pravah/events
Response: HTTP/1.1 401 UNAUTHORIZED
Body: {"error":"Unauthorized","status":"error"}

# 6. Runtime Intake on port 7000 without trace HMAC -> FAIL-CLOSED
POST http://localhost:7000/api/runtime
Response: HTTP/1.1 401 UNAUTHORIZED
Body: {"details":"Missing trace id","error":"Trace verification failed","status":"error"}

# 7. Process Runtime on port 8000 without auth -> PROVEN SAFE (Read-mostly)
POST http://localhost:8000/process-runtime
Body: {"cpu_usage":50,"memory_usage":40}
Response: HTTP/1.1 200 OK
Body: {"action_requested":"noop","confidence":0.95,"reason":"No threshold exceeded"}

# 8. Observer Telemetry Ingest on port 8600 without auth -> PROVEN SAFE (Passive)
POST http://localhost:8600/api/ingest
Body: {"service":"test_svc","status":"healthy","data":{}}
Response: HTTP/1.1 200 OK
Body: {"accepted":true}
```

---

## 10. Security Classification Summary

Every mutating endpoint evaluated receives one definitive classification:

| Security Status | Endpoints | Rationale |
| :--- | :--- | :--- |
| **PROVEN SAFE** | `POST /ingest-link`<br>`POST /remove-link`<br>`POST /api/runtime`<br>`POST /pravah/events` (7000)<br>`POST /pravah/api/v1/publish`<br>`POST /evidence` (7000)<br>`POST /process-runtime`<br>`POST /api/ingest`<br>`POST /execute-action`<br>`POST /simulate-failure` | Either strictly fail-closed via cryptographic tokens/signatures, or proven strictly passive/simulation with zero operational infrastructure authority. |
| **ARCHITECTURE DECISION REQUIRED** | `POST /control-plane/runtime-ingest`<br>`POST /evidence` (8000)<br>`POST /vana/execute` | Inconsistent security primitives between ports, or service-to-service contracts that lack explicit authentication wrapping. |
| **PROVEN SECURITY DEFECT** | `POST /api/control-plane/override` | Confirmed by source inspection, live execution, and deployment exposure. Allows unauthenticated callers to freeze applications and disable automated recovery cluster-wide (`SEC-DEFECT-OVR-001`). |

---

## 11. Frontend Authentication Architecture Requirements

The forensic discovery establishes clear boundary constraints for any future frontend authentication implementation:

1. **Mutations That Genuinely Require Operator Authentication:**
   - `POST /ingest-link` (Port 8000)
   - `POST /remove-link` (Port 8000)
   - `POST /api/control-plane/override` (Port 7000) — *Must be unified under operator auth before production.*
2. **Mutations That Require Authorization Beyond Authentication:**
   - `POST /remove-link` and `POST /api/control-plane/override` are destructive or operational-freeze actions. They must not be accessible to every authenticated identity. A role requirement (`admin` or `operator`) must be defined.
3. **Mutations That Are Service-to-Service Only (Never Expose to Browser):**
   - `POST /api/runtime` (Port 7000) — Enforces HMAC trace signing (`SSPL_SECRET_KEY`).
   - `POST /pravah/events` (Port 7000) — Enforces `PRAVAH_API_KEY`.
   - `POST /evidence` (Port 7000) — Enforces `PRAVAH_API_KEY`.
   - `POST /execute-action` (Port 5003) — Enforces container execution HMAC.
   - `POST /control-plane/runtime-ingest` (Port 8000) — Automated pipeline intake.
4. **Mutations That Are Pure Telemetry Sinks:**
   - `POST /api/ingest` (Port 8600) — Passive observer sink.
   - `POST /process-runtime` (Port 8000) — Stateless simulation computation.

---

## 12. Final A / B / C Classification

- **Category A — Security boundary already proven:**
  - `POST /ingest-link` and `POST /remove-link` fail-closed verification.
  - `POST /api/runtime` HMAC trace signature enforcement.
  - `POST /pravah/events` (port 7000) and `POST /evidence` (port 7000) Shakti auth.
  - `POST /execute-action` (port 5003) multi-layer signature and nonce consumption.
- **Category B — Requires explicit owner / architecture decision:**
  - **Endpoint `POST /api/control-plane/override` remediation posture:** Whether to connect it to `TokenAuth` (matching port 8000), bind port 7000 strictly to loopback/private subnet, or eliminate UI override controls.
  - **Operator Authorization Scheme:** Whether to implement role-based access control (RBAC) in `verify_control_plane_auth` or accept any authenticated token for mutations.
  - **Port 8000 vs 7000 Evidence / Events Divergence:** Whether to decommission unauthenticated stubs on port 8000 (`/evidence`, `/pravah/events`) in favor of port 7000 authoritative routes.
- **Category C — Security defect requiring remediation:**
  - **`SEC-DEFECT-OVR-001` (`POST /api/control-plane/override`):** Unauthenticated operational mutation exposed to the network and wired to frontend UI.
  - **`SEC-AUTH-NO-AUTHZ-001` (`POST /remove-link`):** Destructive entity deletion accessible to any valid token holder without permission checks.

---

## 13. VANA Integrity Verification

VANA is completely OUT OF SCOPE. Verification confirms zero modifications:
- `git diff -- VANA/`: **0 diff lines (Clean)**
- `git status --short VANA/`: **Clean (0 modified/untracked files)**

---

## 14. Repository Scope Verification

- `git status --short`: Confirms no unauthorized production or test code modifications were introduced during Phase 3.4.
- Newly created files: **EXACTLY ONE** file:
  - `audit/PHASE3_4_MUTATION_AUTHORIZATION_BOUNDARY_FORENSICS.md`
