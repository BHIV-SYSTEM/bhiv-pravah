# FORENSIC AUDIT REPORT: TASK PHASE 3.3
## Pravah Frontend Authentication Architecture Forensics & Decision Baseline

**Date:** 2026-09-12  
**Audit Target:** Pravah Frontend Authentication Architecture, Backend Mutation Security Boundary, and Operator Credential Lifecycle  
**Execution Root:** `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Classification:** **B — REQUIRES EXPLICIT ARCHITECTURE / OWNER DECISION**  
**Implementation Blocker:** **Frontend authentication implementation is BLOCKED pending an authoritative authentication architecture decision.**

---

## 1. Executive Conclusion

A comprehensive forensic audit of the Pravah frontend source code, backend control plane boundaries, deployment manifests, security primitives, and live local services confirms that:

1. **Frontend Has Zero Authentication Primitives:**
   The Next.js frontend contains no login dialog, no session or token storage (`localStorage`, `sessionStorage`, cookies, or reactive memory), no auth middleware, no route protection, and no Authorization header generation. All Axios and Fetch clients dispatch unauthenticated requests with only `Content-Type: application/json`.
2. **Backend Mutations Strictly Require Token Authentication (`SEC-AUTH-001`):**
   The backend Decision Brain endpoints `POST /ingest-link` and `POST /remove-link` strictly enforce caller authentication via the FastAPI dependency `verify_control_plane_auth`. Callers must supply an authentic HS256 JSON Web Token signed with `JWT_SECRET_KEY` via either `Authorization: Bearer <token>` or `X-API-Token: <token>`.
3. **Protected Mutations Remain Fail-Closed:**
   Live local verification confirms that unauthenticated invocations of `POST /ingest-link` and `POST /remove-link` are rejected with `HTTP 401 Unauthorized` and payload `{"detail":"Authentication required: missing token"}`.
4. **No Token Issuance Layer Exists:**
   The backend exposes no `/login`, `/auth`, or `/token` issuance endpoint. Tokens are generated strictly via in-process Python calls (`get_auth().generate_token(...)`) in tests and CLI scripts.
5. **Architectural Impasse:**
   Because frontend client bundles must never be entrusted with the cluster symmetric secret (`JWT_SECRET_KEY`), and no server-side proxy or login exchange endpoint exists, the frontend cannot safely acquire or transmit valid credentials under the current repository architecture.

Therefore, **frontend authentication implementation is BLOCKED pending an authoritative authentication architecture decision.**

---

## 2. Current Frontend Authentication State (Discovery)

A systematic forensic inspection across the frontend codebase (`frontend/src/`) established the following:

| Inspection Area | Target Files / References | Forensic Finding |
| :--- | :--- | :--- |
| **API Client Wrappers** | `frontend/src/services/api.ts` (Lines 18–37) | Three Axios clients (`decisionBrainApi`, `controlPlaneApi`, `observerApi`) are instantiated. None define an Authorization header or token interceptor. Only `Content-Type: application/json` is defined. |
| **Mutation Invocation** | `frontend/src/services/api.ts` (Lines 111–119) | `api.ingestLink` and `api.removeLink` execute direct Axios POST calls to `/ingest-link` and `/remove-link` with no authentication headers. |
| **Hooks / TanStack Query** | `frontend/src/hooks/useBackend.ts` (Lines 122–140) | `useIngestLink` and `useRemoveLink` execute `api.ingestLink` and `api.removeLink` with raw payload parameters only. |
| **Token & Session Storage** | `frontend/src/` | Grep across entire `frontend/src` for `localStorage`, `sessionStorage`, `cookies`, `token`, `session`, `auth` returned zero matches for credential storage. |
| **Global UI Store** | `frontend/src/store/useUiStore.ts` | Zustand store tracks `sidebarOpen`, `commandPaletteOpen`, `notifications`, `activeTraceId`, and `activeExecutionId`. Zero authentication states, user models, or token properties exist. |
| **User Menu / Login UI** | `frontend/src/components/Layout.tsx` (Lines 181–187) | The "Operator" profile element is a static, non-interactive HTML `<button>` containing a static User icon and text. It attaches no `onClick` handler, modal trigger, or form. |
| **Auth Middleware** | `frontend/src/middleware.ts` | File does not exist. No Next.js middleware is configured. |
| **Route Protection** | `frontend/src/app/**` | All page routes (`/`, `/runtime`, `/replay`, `/logs`, `/analytics`, `/control-plane`, `/execution`, `/configuration`, `/observer`) render directly with zero route guards. |
| **Environment Variables** | `frontend/README.md`, `frontend/.env*` | Only public endpoint URLs are defined (`NEXT_PUBLIC_DECISION_BRAIN_URL`, `NEXT_PUBLIC_CONTROL_PLANE_URL`, `NEXT_PUBLIC_OBSERVER_URL`). Zero credential, secret, or token environment variables exist. |
| **BFF / Proxy Routes** | `frontend/src/app/api/` | Only `vana` reverse proxy routes exist (`group2`, `group4`). No authentication proxy, session handler, or token generation route exists. |

---

## 3. Backend Authentication Contract

The authoritative backend authentication implementation was inspected across `backend/control_plane/backend/app/main.py`, `backend/security/auth.py`, `backend/control_plane/api/agent_api.py`, and test suites.

### 3.1 Verification Dependency: `verify_control_plane_auth`
- **Location:** `backend/control_plane/backend/app/main.py` (Lines 290–324)
- **Signature:**
  ```python
  def verify_control_plane_auth(
      authorization: Optional[str] = Header(None, alias="Authorization"),
      x_api_token: Optional[str] = Header(None, alias="X-API-Token"),
  ) -> dict[str, Any]:
  ```
- **Execution Logic:**
  1. **Header Inspection:** Accepts credentials via `Authorization` or `X-API-Token`.
  2. **Bearer Parsing:** If `Authorization` is provided, splits by whitespace:
     - If two parts and prefix is `Bearer` (case-insensitive): extracts token.
     - If single part without `Bearer` prefix: extracts token directly.
     - Otherwise: raises `HTTPException(status_code=401, detail="Malformed Authorization header")`.
  3. **Fallback Header:** If `Authorization` is absent but `X-API-Token` is present, uses its value directly.
  4. **Missing Check:** If neither header yields a token string, immediately raises:
     `HTTPException(status_code=401, detail="Authentication required: missing token")`.
  5. **Cryptographic Validation:** Calls `get_auth().verify_token(token)`.
  6. **Rejection:** If `not result.get("valid")`, raises:
     `HTTPException(status_code=401, detail=f"Authentication failed: {error_msg}")`.
  7. **Identity Resolution:** Extracts caller identifier:
     `caller_id = payload.get("user_id") or payload.get("sub") or "authenticated_user"`.
     Returns dict `{"caller_id": str(caller_id), "payload": payload}`.

### 3.2 Cryptographic Primitive: `TokenAuth`
- **Location:** `backend/security/auth.py` (Lines 8–68)
- **Algorithm:** `HS256` (HMAC with SHA-256).
- **Secret Key Resolution:**
  `self.secret_key = secret_key or os.getenv('JWT_SECRET_KEY', 'default-jwt-secret-change-in-prod')`
- **Payload Schema:**
  `{"user_id": user_id, "exp": time.time() + expires_in, "iat": time.time()}` (default expiry: 3600 seconds).
- **Verification Method:**
  `jwt.decode(token, self.secret_key, algorithms=['HS256'])`
  Catches `jwt.ExpiredSignatureError` (returns `{"valid": False, "error": "Token expired"}`) and `jwt.InvalidTokenError` (returns `{"valid": False, "error": "Invalid token"}`).

### 3.3 Test Coverage
- **Location:** `backend/tests/test_phase2_ingestion_api.py` (Lines 61–120)
- The test suite proves that:
  - Missing token on `/ingest-link` &rarr; HTTP 401 (`test_missing_authentication_rejected_401`)
  - Invalid signature/structure &rarr; HTTP 401 (`test_invalid_authentication_token_rejected_401`)
  - Expired token &rarr; HTTP 401 (`test_expired_authentication_token_rejected_401`)
  - `X-API-Token` header equivalence &rarr; HTTP 200 (`test_x_api_token_header_accepted`)
  - Missing token on `/remove-link` &rarr; HTTP 401 (`test_unauthorized_removal_rejected_401`)
  - Valid token &rarr; HTTP 200 (`test_valid_authenticated_ingestion`)

### 3.4 Secret Management Forensics (Redacted)
- **Development:** `backend/environments/dev.env` does NOT define `JWT_SECRET_KEY`. The backend silently falls back to `'default-jwt-secret-change-in-prod'`.
- **Staging:** `backend/environments/stage.env` does NOT define `JWT_SECRET_KEY`. The backend silently falls back to `'default-jwt-secret-change-in-prod'`.
- **Production Config File:** `backend/environments/prod.env` line 50 defines a committed 64-character hex secret string for `JWT_SECRET_KEY` (`[REDACTED_PROD_HEX_SECRET]`).
- **Container Manifests:** `yotta-deploy.yaml:84` and `docker-compose.production.template.yml:38` reference `JWT_SECRET_KEY=${JWT_SECRET_KEY}`, intended to be injected from the host environment or secrets manager.

---

## 4. Endpoint Authentication Boundary Matrix

Comprehensive mapping of all primary endpoints across the three backend services:

| Endpoint | Port | Method | Service | Auth Required? | Accepted Credential | Frontend Currently Supplies? | Live Local Status & Response |
| :--- | :---: | :---: | :--- | :---: | :--- | :---: | :--- |
| `/ingest-link` | 8000 | POST | Decision Brain | **YES** | HS256 JWT (`Authorization: Bearer <jwt>` or `X-API-Token: <jwt>`) signed with `JWT_SECRET_KEY` | **NO** | `HTTP 401 Unauthorized` (`{"detail":"Authentication required: missing token"}`) |
| `/remove-link` | 8000 | POST | Decision Brain | **YES** | HS256 JWT (`Authorization: Bearer <jwt>` or `X-API-Token: <jwt>`) signed with `JWT_SECRET_KEY` | **NO** | `HTTP 401 Unauthorized` (`{"detail":"Authentication required: missing token"}`) |
| `/live-dashboard` | 8000 | GET | Decision Brain | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Live system health & monitored links) |
| `/autonomous-status` | 8000 | GET | Decision Brain | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Continuous loop runtime state) |
| `/recent-activity` | 8000 | GET | Decision Brain | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Decision list) |
| `/decision-summary` | 8000 | GET | Decision Brain | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Aggregate statistics) |
| `/action-scope` | 8000 | GET | Decision Brain | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Allowed actions dictionary) |
| `/orchestration/metrics` | 8000 | GET | Decision Brain | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Unified metrics JSON) |
| `/api/lineage/{id}` | 8000 | GET | Decision Brain | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Lineage replay payload) |
| `/api/lineage/{id}/verify`| 8000 | GET | Decision Brain | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Cryptographic verification) |
| `/api/ml/features/latest`| 8000 | GET | Decision Brain | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Computed ML intelligence features) |
| `/process-runtime` | 8000 | POST | Decision Brain | **NO** | None (Public telemetry ingestion) | N/A | `HTTP 200 OK` (Returns requested action) |
| `/api/control-plane/apps` | 7000 | GET | Control Plane | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (App list) |
| `/api/control-plane/health`| 7000 | GET | Control Plane | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Control plane health summary) |
| `/api/control-plane/history/{app}`| 7000 | GET | Control Plane | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Decision history timeline) |
| `/api/control-plane/override`| 7000 | POST | Control Plane | **NO** | None (Rate limited: 40/min, unauthenticated) | N/A | `HTTP 400 Bad Request` (Empty payload) / `HTTP 200` (Valid payload) |
| `/pravah/events` | 7000 | POST | Control Plane | **YES** | Static token `PRAVAH_API_KEY` + `X-Source-System` header | **NO** | `HTTP 401 Unauthorized` (`{"error":"Unauthorized"}`) |
| `/api/runtime` | 7000 | POST | Control Plane | **YES** (Trace) | HMAC Trace signature (`X-Trace-Signature`, `nonce`, `timestamp`) | **NO** | `HTTP 401 Unauthorized` (`"Trace verification failed"`) |
| `/api/status` | 8600 | GET | Observer Server | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Observation store status) |
| `/api/events` | 8600 | GET | Observer Server | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Telemetry event list) |
| `/api/lineage` | 8600 | GET | Observer Server | **NO** | None (Public read-only) | N/A | `HTTP 200 OK` (Evidence bundles list) |
| `/api/metrics` | 8600 | GET | Observer Server | **NO** | None (Prometheus exposition) | N/A | `HTTP 200 OK` (Prometheus text format) |
| `/api/ingest` | 8600 | POST | Observer Server | **NO** | None (Internal push sink) | N/A | `HTTP 200 OK` (`{"accepted":true}`) |

---

## 5. Live Verification Evidence

Live interactions executed against the local running services confirm the security boundaries:

### Test 1: Unauthenticated `POST http://localhost:8000/ingest-link`
- **Request:**
  ```http
  POST /ingest-link HTTP/1.1
  Host: localhost:8000
  Content-Type: application/json

  {"link": "https://github.com/torvalds/linux"}
  ```
- **Live Response:**
  ```http
  HTTP/1.1 401 Unauthorized
  server: uvicorn
  content-type: application/json
  content-length: 51

  {"detail":"Authentication required: missing token"}
  ```
- **Verdict:** **FAIL-CLOSED.** Denied without credentials.

### Test 2: Unauthenticated `POST http://localhost:8000/remove-link`
- **Request:**
  ```http
  POST /remove-link HTTP/1.1
  Host: localhost:8000
  Content-Type: application/json

  {"link": "https://github.com/torvalds/linux"}
  ```
- **Live Response:**
  ```http
  HTTP/1.1 401 Unauthorized
  server: uvicorn
  content-type: application/json
  content-length: 51

  {"detail":"Authentication required: missing token"}
  ```
- **Verdict:** **FAIL-CLOSED.** Denied without credentials.

### Test 3: Unauthenticated Read-Only Dashboard Invocations
- `GET http://localhost:8000/live-dashboard` &rarr; `HTTP 200 OK`
- `GET http://localhost:8000/autonomous-status` &rarr; `HTTP 200 OK`
- `GET http://localhost:8600/api/events` &rarr; `HTTP 200 OK`
- `GET http://localhost:8600/api/lineage` &rarr; `HTTP 200 OK`
- **Verdict:** **UNAUTHENTICATED OBSERVABILITY CONFIRMED.** Observability does not require operator credentials.

---

## 6. Authentication Ownership Analysis

We investigated which architectural layer is intended or capable of owning operator authentication:

| Potential Ownership Layer | Repository Evidence | Technical Feasibility & Safety Assessment |
| :--- | :--- | :--- |
| **1. Frontend Client (Browser)** | `frontend/src/` has no auth code. | **CATEGORICALLY UNSAFE.** Generating HS256 JWTs directly in the browser requires bundling `JWT_SECRET_KEY` into client JavaScript (`NEXT_PUBLIC_JWT_SECRET_KEY`). Any user inspecting client source can extract the root cluster signing key and forge arbitrary admin tokens. |
| **2. Backend (FastAPI / Flask)** | Implements `verify_control_plane_auth` and `TokenAuth.verify_token`, but has **zero token issuance endpoints** (no `/login`, `/auth`, `/oauth`). | **INCOMPLETE.** The backend acts purely as a *relying party* (verifying tokens), not an *identity provider* (issuing tokens). It cannot issue tokens without introducing a user store, credential database, and login route. |
| **3. Reverse Proxy / Gateway** | `yotta-deploy.yaml` and `PRODUCTION_DEPLOYMENT.md` expose ports 7000, 8000, and 8600 directly. Reverse proxy (Nginx/Caddy) is mentioned only as an optional loopback forwarder for Prometheus (`9090`). | **ABSENT.** No API Gateway (e.g. Kong, Traefik, Envoy, OAuth2-Proxy) is configured in the repository to authenticate users and inject upstream Bearer headers. |
| **4. External Identity Provider (IdP)** | No OAuth2, OIDC, SAML, Keycloak, or Auth0 configuration or dependency exists. | **ABSENT.** No external IdP integration exists. |
| **5. Next.js BFF (Backend-For-Frontend)** | Next.js API routes (`frontend/src/app/api/`) run server-side in Node.js and can securely read server-only environment variables (e.g., `INTERNAL_JWT_SECRET_KEY`). | **POTENTIAL FUTURE CANDIDATE.** A Next.js API Route Handler (e.g. `/api/mutate/ingest`) could securely hold the secret server-side, sign requests, and forward them to port 8000 without exposing secrets to the browser. However, this is NOT currently implemented or authorized. |
| **6. Out-of-Band CLI / Operator Scripting** | All tests and verification scripts generate tokens out-of-band via `get_auth().generate_token(...)` using shell/Python environments. | **CURRENT PROVEN MECHANISM.** In the current repository design, tokens are intended to be generated by infrastructure administrators with direct server/CLI access. |

---

## 7. Deployment and Environment Findings

1. **Development vs. Production Parity Discrepancy:**
   - In `dev.env` and `stage.env`, `JWT_SECRET_KEY` is omitted, causing `backend/security/auth.py` to fall back to the known string `'default-jwt-secret-change-in-prod'`.
   - In `prod.env`, `JWT_SECRET_KEY` is statically defined in git.
   - In production manifests (`yotta-deploy.yaml` line 84), `JWT_SECRET_KEY` is passed from environment variables.
2. **Frontend Deployment Isolation:**
   - The Next.js frontend is absent from `yotta-deploy.yaml` and `docker-compose.production.template.yml`. It is treated as an independent console process rather than an integrated container in the backend deployment stack.
3. **CORS Configuration:**
   - FastAPI (`control_plane/backend/app/main.py:186`) configures CORS with origins including `http://localhost:4500`, `http://localhost:3200`, `http://localhost:3000`.
   - Flask (`control_plane/api/agent_api.py:81`) configures CORS similarly.
   - Cross-origin requests from the frontend are allowed by CORS, but fail on mutation due to 401 authentication.

---

## 8. Concrete Security Risks

### PROVEN RISKS
1. **Predictable Development JWT Fallback (`SEC-AUTH-DEV-001`):**
   When `JWT_SECRET_KEY` is unset (the default in `dev.env` and `stage.env`), `backend/security/auth.py:12` defaults to `'default-jwt-secret-change-in-prod'`. Any entity with knowledge of this public repository string can trivially forge valid JWT tokens for any user ID (`security_operator`, `admin`, etc.) that will be accepted by `verify_control_plane_auth`.
2. **Committed Secret in Source Control (`SEC-AUTH-PROD-001`):**
   `backend/environments/prod.env:50` contains a committed 64-character hex secret for `JWT_SECRET_KEY`. This key is committed to the repository history, compromising any production instance relying on this file.
3. **Inability of Frontend to Execute Legitimate Mutations (`SEC-UI-INTEG-001`):**
   Because the frontend has no credential delivery or generation mechanism, any operator attempting to ingest or remove a link via the UI encounters a silent or visible failure (`HTTP 401`).
4. **Client Secret Exposure Risk Under Naive Remediation (`SEC-CLIENT-LEAK-001`):**
   If an implementer attempts to fix frontend mutations by importing `jsonwebtoken` or `jose` into the React client with `process.env.NEXT_PUBLIC_JWT_SECRET_KEY`, the cluster secret will be permanently exposed in client browser bundles.
5. **Inconsistent Security Across Ports (`SEC-AUTH-INCONSISTENT-001`):**
   - Port 8000 enforces `TokenAuth` HS256 JWT on `/ingest-link` and `/remove-link`.
   - Port 7000 enforces `check_shakti_auth` (`PRAVAH_API_KEY` + `X-Source-System`) on `/pravah/events`.
   - Port 7000 enforces NO authentication on `/api/control-plane/override` (only rate limiting).
   - Port 8600 enforces NO authentication on any endpoint (including `/api/ingest`).

### UNRESOLVED / REQUIRES OWNER DECISION
1. **Operator Identity Lifecycle:**
   Whether Pravah is intended as an internal single-operator console (where a single static API token suffices), a multi-user dashboard requiring individual credentials, or an automated pipeline where mutations are triggered only via CI/CD.
2. **Storage and Transmission Mechanism:**
   If personal operator tokens are used, whether they should be stored in browser `sessionStorage` (cleared on tab close), `localStorage`, or managed via HttpOnly secure cookies.
3. **Role-Based Authorization (RBAC):**
   `verify_control_plane_auth` extracts `caller_id` but performs no authorization or capability check against `VERIFIED_CAPABILITY_MAPPINGS`. Any valid JWT for *any* user ID grants full administrative mutation power.

---

## 9. Required Architecture Decision

All architectural paths and remediation strategies are strictly classified into categories **A**, **B**, and **C**:

### Category A — Already Supported Safely
1. **Read-Only Dashboard & Observability Consumption:**
   All read-only telemetry, runtime loops, lineage replay, and event streaming endpoints across ports 8000, 7000, and 8600 are public and fully functional without operator authentication. The Phase 3.2 remediation correctly wired these without requiring tokens.
2. **Fail-Closed Backend Mutation Enforcement:**
   Backend `verify_control_plane_auth` robustly rejects unauthenticated mutating calls with HTTP 401. This security boundary is proven and must remain untouched.

---

### Category B — Requires Explicit Architecture / Owner Decision
The repository provides four viable architectural patterns to bridge the frontend-to-backend mutation gap. Selecting among them requires an explicit owner decision:

- **Option B.1: Next.js BFF Server-Side Proxy (Recommended for Simplicity & Security)**
  - *Mechanism:* Create Next.js API Route Handlers (`frontend/src/app/api/links/ingest/route.ts` and `route.ts`). The Route Handler runs server-side in Node.js, accesses `JWT_SECRET_KEY` (server-side only, never prefixed with `NEXT_PUBLIC_`), signs an authentic token via `jsonwebtoken`, and proxies the request to `http://localhost:8000/ingest-link`.
  - *Why B:* Changes the frontend network architecture from direct client-to-backend calls to a BFF proxy pattern. Requires defining the server environment secret lifecycle.
- **Option B.2: Operator Token Settings Input in UI (Recommended for Multi-Operator Traceability)**
  - *Mechanism:* Add an "Operator Credential" modal in the UI (triggered from the existing Operator profile button in `Layout.tsx` or `configuration/page.tsx`). The operator enters a pre-generated token (issued via CLI by cluster admins). The token is saved in browser `sessionStorage` and attached to outgoing Axios mutation requests as `Authorization: Bearer <token>`.
  - *Why B:* Requires operators to generate tokens out-of-band via CLI scripts and paste them into the browser. Requires UX decisions on token entry and expiry alerts.
- **Option B.3: Backend Authentication & Login Endpoint**
  - *Mechanism:* Implement a formal `/api/auth/login` endpoint on port 8000 that validates operator credentials (username/password or API key) and returns a signed JWT. Frontend implements a login dialog.
  - *Why B:* Requires implementing user management, password hashing, and token issuance in the backend control plane, which currently does not exist.
- **Option B.4: Retain Ingestion as CLI/Automation Only (Formal Read-Only UI Posture)**
  - *Mechanism:* Officially declare the Pravah Web Console as an **Observability-Only Console**. Disable the link ingestion form on the Dashboard and display an informative badge: *"Link Ingestion is managed via CLI/CI pipeline in accordance with TANTRA Safeguard 4 (Visibility ≠ Execution)"*.
  - *Why B:* Modifies feature scope; requires product owner confirmation that link ingestion from the web UI is not mandatory.

---

### Category C — Unsafe / Must NOT Be Implemented As-Is
1. **Browser-Side JWT Generation (`NEXT_PUBLIC_JWT_SECRET_KEY`):**
   - *Why Unsafe:* Requires exposing the symmetric signing key to the browser client bundle, permanently compromising the backend cluster security.
2. **Hardcoding a Static JWT in Frontend Code:**
   - *Why Unsafe:* Hardcodes credentials into git version control, bypasses token expiration, and prevents operator identity revocation.
3. **Weakening or Removing Backend Authentication on `/ingest-link` and `/remove-link`:**
   - *Why Unsafe:* Violates `SEC-AUTH-001`, re-opening control-plane infrastructure mutations to arbitrary unauthenticated network callers.
4. **Ad-Hoc Unencrypted LocalStorage Token Persistence Without Lifecycle:**
   - *Why Unsafe:* Storing sensitive tokens indefinitely in `localStorage` without expiry checks or logout lifecycle invites cross-site script (XSS) credential theft.

---

## 10. Authoritative Implementation Status

> ### 🛑 ARCHITECTURAL BLOCKER NOTICE
> **Frontend authentication implementation is BLOCKED pending an authoritative authentication architecture decision.**
>
> Neither frontend client code nor backend authentication configuration may be modified to bridge operator authentication until the repository owner explicitly approves an architectural option from Category B.

---

## 11. VANA Integrity Verification

VANA components and contracts are strictly out of scope. Verification commands confirm zero modifications:

- `git diff -- VANA/`: **0 diff lines (Clean)**
- `git status --short VANA/`: **Clean (0 modified/untracked files)**

---

## 12. Repository Scope Verification

Repository status inspection verifies strict adherence to forensic scope:

- `git status --short`: Confirms no unauthorized production or test code modifications were introduced during Phase 3.3.
- `git diff --name-only`: Only pre-existing runtime log files and Phase 3.2 frontend remediation files are present.
- Newly created files: **EXACTLY ONE** file:
  - `audit/PHASE3_3_FRONTEND_AUTH_ARCHITECTURE_FORENSICS.md`
