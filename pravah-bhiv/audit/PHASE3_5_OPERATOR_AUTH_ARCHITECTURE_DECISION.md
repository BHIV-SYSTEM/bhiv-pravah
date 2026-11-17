# FORENSIC ARCHITECTURE DECISION REPORT: TASK PHASE 3.5
## Pravah Operator Authentication & Authorization Architecture Decision

**Date:** 2026-09-12  
**Audit Target:** Authoritative Operator Identity Source, Operator Role/Authorization Model, Next.js BFF Architecture Analysis, Alternative Architectures Evaluation, Mutation-by-Mutation Decision Matrix, and Owner Decision Gate  
**Execution Root:** `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Classification:** **B — FORMAL ARCHITECTURE DECISION DOCUMENT (DESIGN & GOVERNANCE GATE ONLY)**  
**Implementation Status:** **BLOCKED until owner/security architecture decisions are approved.**  
**Authorization Gate:** **NO — ARCHITECTURE DECISION ONLY. IMPLEMENTATION IS NOT AUTHORIZED.**

---

## Executive Summary

Following the completion and certification of **Phase 3.3** (Frontend Auth Architecture Baseline), **Phase 3.4** (Mutation Authorization Boundary Forensics), and **Phase 3.4.1** (Mutation Inventory Closure & Defect Evidence Verification), this report delivers the authoritative architecture decision document for Pravah operator authentication and authorization.

Key forensic determinations established in this report:
1. **No Authoritative Browser Operator Identity Source Exists:** The repository contains zero user databases, zero password hashes, zero OAuth/OIDC/SAML integrations, zero Google authentication, and zero browser session stores. Backend `TokenAuth` issues HS256 tokens strictly via in-process Python calls in tests and CLI scripts.
2. **No Operator Role or Authorization Model Exists:** `TokenAuth` payload contains strictly `{"user_id", "exp", "iat"}`. The backend extracts `caller_id` solely for audit log strings. There are no role checks, no capability mappings for operators, and no permission models. Any valid token grants unrestricted mutation authority (`SEC-AUTH-NO-AUTHZ-001`).
3. **The Next.js BFF Architecture is Technically Compatible but Blocked:** While Next.js App Router route handlers already exist (`frontend/src/app/api/vana/group4/route.ts`) and Node.js can securely isolate `JWT_SECRET_KEY`, the BFF **cannot be implemented safely** until the repository owner formally approves: (a) the operator identity source, (b) the session storage model, and (c) the operator role/authorization matrix.
4. **Current HTTP 401 Behavior is Correct Fail-Closed Security:** Invocations from `/api-explorer` and the Dashboard link form directly reach port 8000 without credentials and are rejected with `HTTP 401 Unauthorized`. This fail-closed posture must NOT be bypassed or weakened.
5. **Implementation Gate Enforced:** All production code, frontend code, backend code, tests, and contracts remain 100% frozen. Implementation is explicitly blocked pending owner review and sign-off.

---

## Section A: Authoritative Operator Identity Source

A comprehensive forensic investigation of all files, configurations, deployment manifests, dependencies, and git history was conducted across `frontend/`, `backend/`, and environment definitions to evaluate potential operator identity sources.

### Evaluation of Identity Source Candidates

| Identity Candidate | Exists in Repo? | Exact Source / Config Evidence | Can Authenticate Browser Operator? | Can Safely Support Pravah Mutation Boundary? | Additional Infrastructure Required |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **1. Local Operator Identity / Session** | **NO** | `frontend/src/` has zero session stores, no cookie management, no `localStorage` token logic. `frontend/package.json` contains no session packages (`iron-session`, `express-session`, etc.). | NO | NO (No state or lifecycle exists) | Session storage backend (Redis / encrypted signed cookie store), login route, session lifecycle handlers. |
| **2. Pre-Shared Operator Token** | **PARTIALLY (CLI/Test only)** | `backend/security/auth.py:15` (`generate_token`), `backend/environments/prod.env:50` (committed hex secret), `backend/tests/test_phase2_ingestion_api.py:27`. | NO (in browser) | **UNSAFE** if exposed to browser; **ACCEPTABLE** only if entered per-session into memory or mediated by server-side BFF. | Token delivery mechanism, out-of-band operator distribution protocol, or BFF proxy. |
| **3. Existing JWT Issuance** | **NO (Issuance Endpoint Absent)** | `backend/security/auth.py` defines `TokenAuth.generate_token()` as an internal Python method. No HTTP `/login`, `/auth/token`, or `/oauth/token` route exists in FastAPI or Flask. | NO | NO (Browser cannot request a token via HTTP) | Authentication endpoint, user validation logic, credential verification store. |
| **4. OIDC / SSO** | **NO** | Zero OIDC/OAuth2 client dependencies in `frontend/package.json` (no `next-auth`, `@auth/core`, `oidc-client-ts`). Zero OIDC provider libraries in `requirements.txt`. Zero discovery URLs (`.well-known/openid-configuration`). | NO | NO (Not present) | Identity Provider (Keycloak, Okta, Auth0, Dex), OIDC discovery client, redirect callback endpoints, client credentials. |
| **5. Google Authentication** | **NO** | String searches across entire repository for `Google` locate only Google Fonts (`Outfit`, `JetBrains Mono`, `Inter` in `frontend/src/app/globals.css:1`, `backend/observer_server.py:461`), Google SRE documentation quotes, and test domains. Zero Google OAuth2 client IDs or SDKs. | NO | NO (Not present) | Google Cloud Console OAuth2 Client ID/Secret, OAuth consent screen, redirect URI handler, Google auth library. |
| **6. Another Existing IdP (SAML, LDAP, etc.)** | **NO** | Zero LDAP, SAML, or enterprise identity provider configurations exist in repository. | NO | NO (Not present) | Enterprise IdP connection, certificate management, metadata XML/endpoints. |
| **7. Service Identity (Machine-to-Machine)** | **YES (Service-only)** | `backend/control_plane/api/agent_api.py:309` (`check_shakti_auth` via `PRAVAH_API_KEY` + `X-Source-System`), `backend/executer/guard.py:18` (`verify_service_auth` HMAC), `backend/control_plane/core/rl_orchestrator_safe.py:155` (`SSPL_SECRET_KEY`). | NO | NO (Service tokens are strictly machine-to-machine; cannot represent human operator intent or non-repudiation) | None for services, but cannot be repurposed for browser operators without violating principle of least privilege. |

### Authoritative Determination

> ### NO AUTHORITATIVE BROWSER OPERATOR IDENTITY SOURCE IS CURRENTLY PROVEN.
> 
> The Pravah repository acts exclusively as a *token-verifying resource server* for mutations. It possesses zero operator identity infrastructure, zero credential storage, zero login endpoints, and zero identity federation. Before any operator authentication can be operationalized, the repository owner must formally designate and approve an operator identity source.

---

## Section B: Operator Role & Authorization Model

A systematic audit was conducted across the backend source code (`backend/security/`, `backend/control_plane/`, `backend/contracts/`) to identify existing role and capability definitions.

### Source Evidence on Existing Roles

1. **Constitutional Roles (`backend/control_plane/core/registry_manager.py:63`, `backend/scripts/validate_constitutional_boundaries.py:154`):**
   - Defines `governance_role: "observability_only"` and `authority_level: "passive_observer"` for Pravah services.
   - Purpose: Enforces the constitutional boundary that Pravah as an observability agent cannot unilaterally execute actions without governance approval.
   - **Scope:** Machine/service governance boundary, **not** human operator authorization.
2. **Capability Adapter (`backend/control_plane/capabilities/execution_rights_adapter.py:38-70`):**
   - Defines `VERIFIED_CAPABILITY_MAPPINGS`:
     - `"governed-execution"`: `source_id: "governance"`, `role: "execution_authority"`, `allowed_actions: ["restart", "scale_up", "scale_down", "rollback"]`.
     - `"vana-environmental_observation"`: `source_id: "VANA"`, `role: "environmental_observation"`.
   - Purpose: Validates automated recovery actions triggered by RL Orchestrator against execution contracts.
   - **Scope:** Service capability mapping, **not** human operator authorization.
3. **`TokenAuth` Claims (`backend/security/auth.py:17-21`):**
   ```python
   payload = {
       'user_id': user_id,
       'exp': time.time() + expires_in,
       'iat': time.time()
   }
   ```
   - Encodes strictly `user_id`, `exp`, and `iat`.
   - **Zero role claims, zero group memberships, zero scope arrays, zero permissions.**
4. **Endpoint Inspection (`backend/control_plane/backend/app/main.py:290-324`):**
   - `verify_control_plane_auth` extracts `caller_id = payload.get("user_id") or payload.get("sub") or "authenticated_user"`.
   - Returns `{"caller_id": str(caller_id), "payload": payload}`.
   - **Zero role evaluation:** Neither `/ingest-link` nor `/remove-link` verifies caller privilege, role, or ownership.

### Finding: Operator Role Model Does Not Exist

**No operator role or authorization model currently exists in the Pravah repository.** Any valid JWT signed with `JWT_SECRET_KEY` is treated identically as an all-powerful credential regardless of who the caller is.

### Minimum Authorization Decisions Required by Endpoint

To close existing vulnerabilities and establish a sound security boundary, the repository owner must approve the authorization policy for the following three operator-facing mutations:

#### 1. `POST /ingest-link` (Port 8000)
- **Current Defect:** Any valid JWT allows ingesting links. Ingestion initiates HTTP HEAD requests and background metadata resolution (`_generate_link_metadata`), consuming server resources.
- **Minimum Model Decision:**
  - `viewer`: Read-only access to `/live-dashboard`. **Forbidden (403)** from calling `/ingest-link`.
  - `operator`: Authorized to ingest monitored links.
  - `admin`: Authorized to ingest monitored links.

#### 2. `POST /remove-link` (Port 8000) — Addressing `SEC-AUTH-NO-AUTHZ-001`
- **Current Defect (`SEC-AUTH-NO-AUTHZ-001`):** `main.py:1273` extracts `caller_id` purely for audit journal logging (`monitored_links_journal.append_link_removed`). Any valid JWT issued to any entity (even a low-privilege service) can delete any monitored link cluster-wide, causing immediate denial-of-service for monitoring.
- **Minimum Model Decision (Owner must select one):**
  - **Option 1 (Role-Based Authorization - RBAC):** Only callers with claim `role == "admin"` (or `role in ["admin", "lead_operator"]`) are authorized to remove links. Callers with `role == "operator"` or `role == "viewer"` receive `HTTP 403 Forbidden`.
  - **Option 2 (Ownership-Based Authorization):** Ingested links store `owner_id: caller_id`. A caller can remove a link only if `caller_id == link.owner_id` OR caller possesses `role == "admin"`.
  - **Recommendation:** **Option 1 (RBAC)** — simplest, most robust model for cluster operations without introducing complex ownership state migrations.

#### 3. `POST /api/control-plane/override` (Port 7000) — Addressing `SEC-DEFECT-OVR-001`
- **Current Defect (`SEC-DEFECT-OVR-001`):** `agent_api.py:284` has **zero authentication and zero authorization**. It accepts unauthenticated POST requests rate-limited only to 40/minute by IP. Freezing an application causes `rl_orchestrator_safe.py:246` to refuse all automated self-healing actions cluster-wide.
- **Minimum Model Decision (Owner must select one):**
  - **Remediation Path A (Port 7000 TokenAuth + RBAC):** Integrate `TokenAuth` into Flask on port 7000. Require valid JWT with `role in ["operator", "admin"]`. Reject unauthenticated requests with `HTTP 401` and unauthorized requests with `HTTP 403`.
  - **Remediation Path B (BFF Remediation Proxy):** Bind port 7000 `/api/control-plane/override` strictly to `127.0.0.1` (loopback). Only allow access via a Next.js BFF route handler `/api/control-plane/override` that validates the operator session and enforces `role in ["operator", "admin"]` before forwarding locally to port 7000.
  - **Remediation Path C (Decommission / Internal CLI Only):** Remove `/api/control-plane/override` from HTTP exposure entirely; manage application overrides strictly via CLI scripts (`python -m control_plane.manage_override`).
  - **Recommendation:** **Remediation Path B (BFF Proxy) combined with Path A (TokenAuth on Flask)** to ensure defense-in-depth across both network layers.

---

## Section C: BFF (Backend-For-Frontend) Architecture Analysis

The proposed architecture:
```text
Browser (React Client)
   ↓  [Session Credential: HttpOnly Secure Cookie or Bearer Session Token]
Next.js Server-Side BFF Route Handler (/api/control-plane/*)
   ↓  [Backend Credential: HS256 JWT signed with JWT_SECRET_KEY]
Pravah Backend (:8000 / :7000)
```

### Forensic Evaluation of the 11 Architectural Dimensions

1. **Where Browser Authentication / Session State Would Live:**
   - In the browser, session credentials must live in an **`HttpOnly`, `SameSite=Lax`, `Secure` cookie** managed exclusively by the Next.js server.
   - The React client JavaScript (`window`, `localStorage`, `sessionStorage`) must have **zero read access** to this cookie, mitigating XSS token-stealing attacks.
   - On the Next.js server, session state is validated either via a signed cryptographic session cookie (e.g. encrypted with a separate `SESSION_SECRET`) or against a server-side session cache.
2. **Where Backend JWT Generation / Credential Handling Would Live:**
   - JWT generation lives **exclusively on the Next.js server runtime (Node.js)** inside the API route handler (`src/app/api/.../route.ts`).
   - The Next.js server acts as an authorized token minter or credential forwarder, generating short-lived (e.g., 60-second) HS256 JWTs on-the-fly specifically for upstream dispatch to port 8000.
3. **How `JWT_SECRET_KEY` Would Remain Server-Side:**
   - `JWT_SECRET_KEY` is loaded from process environment variables (`process.env.JWT_SECRET_KEY`).
   - It is **strictly prohibited** from having the `NEXT_PUBLIC_` prefix.
   - Next.js Webpack/Turbopack compilers automatically exclude non-`NEXT_PUBLIC_` environment variables from client bundles, preventing secret leakage into client JavaScript.
4. **How the BFF Would Authenticate to Port 8000:**
   - The BFF constructs an HTTP request using Node.js native `fetch`.
   - It attaches the header `Authorization: Bearer <signed_jwt>` or `X-API-Token: <signed_jwt>`.
   - Port 8000's `verify_control_plane_auth` parses and verifies the token against its own `JWT_SECRET_KEY`, returning HTTP 200.
5. **How the Backend Would Distinguish Operator Identity:**
   - The BFF includes the authenticated operator's identity in the JWT payload:
     ```json
     {
       "user_id": "operator@pravah.internal",
       "role": "operator",
       "sub": "operator@pravah.internal",
       "exp": 1789196400,
       "iat": 1789196340
     }
     ```
   - Port 8000 extracts `caller_id = payload.get("user_id")` and logs the true human operator's identity into the append-only journal (`monitored_links_journal.jsonl`).
6. **How Authorization Would Be Enforced for `/remove-link`:**
   - **Dual-Layer Enforcement:**
     1. *BFF Layer:* Next.js route handler checks operator session claims: if `session.role !== "admin"`, immediately returns `HTTP 403 Forbidden` without calling backend.
     2. *Backend Layer (Hardened):* Backend `main.py` inspects `auth["payload"].get("role")`: if `role != "admin"`, raises `HTTPException(status_code=403, detail="Administrative privilege required to remove links")`.
7. **How `/api/control-plane/override` Would Be Protected:**
   - Next.js exposes `/api/control-plane/override`.
   - The route handler validates operator session and checks `role in ["operator", "admin"]`.
   - Forwards request locally to `http://127.0.0.1:7000/api/control-plane/override`.
   - Direct external access to port 7000 is closed via network security groups or loopback binding.
8. **Whether the BFF Should Proxy Only Operator Mutations:**
   - **YES.** The BFF should proxy **strictly operator mutations** (`/ingest-link`, `/remove-link`, `/override`).
   - Read-only observability queries (`/live-dashboard`, `/autonomous-status`, `/orchestration/metrics`, `/api/events`) should continue directly to backend ports or pass through transparent caching, as they require no privileges and avoid unnecessary Node.js server overhead.
9. **Whether Service-to-Service Endpoints Must Remain Inaccessible to the Browser:**
   - **YES, CATEGORICALLY.**
   - Endpoints such as `POST /api/runtime` (:7000, HMAC trace signature), `POST /pravah/events` (:7000, ecosystem API key), `POST /execute-action` (:5003, container executor), and `POST /control-plane/runtime-ingest` (:8000) must **never be exposed or proxied through the BFF to the browser**.
   - These routes belong to internal machine-to-machine boundaries with high-risk execution capabilities.
10. **Trust-Boundary Risks Introduced by the BFF:**
    - *Confused Deputy Vulnerability:* If the BFF signs backend JWTs using a single static hardcoded identity (e.g. `user_id: "bff_service"`) without authenticating the browser user first, any unauthenticated browser visitor could trigger mutations through the BFF.
    - *BFF Compromise:* Because the Next.js server would hold `JWT_SECRET_KEY`, any Remote Code Execution (RCE) vulnerability in Node.js or npm dependencies compromises cluster-wide signing keys.
    - *Session Fixation / CSRF:* Browser-to-BFF requests using cookies require robust CSRF protection (SameSite cookie enforcement and Anti-CSRF tokens for mutating requests).
11. **Required Deployment & Runtime Assumptions:**
    - Next.js must be deployed as a **Node.js server process** (`next start`), not as a static export (`next export` / `output: 'export'`).
    - The Next.js server container must reside within the same internal private network (VPC / Docker network) as ports 8000 and 7000.
    - `JWT_SECRET_KEY` and `SESSION_SECRET` must be injected into the Next.js environment via secure secrets management (e.g., Kubernetes Secrets, AWS Secrets Manager, Vault).

> ### GOVERNANCE WARNING: BFF CANNOT BE IMPLEMENTED IN ISOLATION
> 
> A BFF is merely a *transport and signing proxy*; it is **not an identity provider**. Implementing a BFF without an approved identity source simply shifts the unauthenticated boundary from port 8000 to the BFF route handler. Therefore, BFF implementation remains **strictly blocked** until Section A (Identity Source) and Section B (Role Model) are formally approved by the owner.

---

## Section D: Alternative Architectures Comparison

| Architecture Dimension | Option A: Next.js BFF + Approved Operator Session | Option B: Direct Browser Auth via External IdP (OIDC/OAuth2) | Option C: Internal-Only Operator Console (Modal Token / Loopback) |
| :--- | :--- | :--- | :--- |
| **Authentication Flow** | Browser &rarr; BFF Session &rarr; Node.js signs HS256 JWT &rarr; Backend (:8000/:7000). | Browser &rarr; IdP (OIDC Auth Code Flow + PKCE) &rarr; JWT ID/Access Token &rarr; Backend (:8000/:7000). | Operator generates JWT via CLI script &rarr; Pastes into frontend session modal &rarr; Sent in memory `Authorization` header. |
| **Secret Location** | `JWT_SECRET_KEY` resides on Next.js server & backend services. | IdP holds private key (RS256); backend holds public key (JWKS endpoint). | `JWT_SECRET_KEY` resides on server only. Operator holds personal ephemeral token. |
| **Browser Exposure** | ZERO secret exposure. Browser holds only `HttpOnly` session cookie. | ZERO secret exposure. Browser holds user-scoped RS256 access token. | ZERO secret exposure. Browser holds user-pasted JWT in volatile memory only. |
| **Backend Trust Boundary** | Backend trusts BFF signature as authentic operator intent. | Backend verifies asymmetric signature against IdP JWKS. | Backend verifies HS256 signature against `JWT_SECRET_KEY`. |
| **AuthN Mechanism** | Session cookie + Next.js server-side minting. | OAuth2 PKCE / OpenID Connect token exchange. | Direct `Authorization: Bearer <jwt>` from browser memory. |
| **AuthZ Mechanism** | BFF role check + Backend RBAC claims verification. | Claims in IdP access token (`roles`, `groups`) verified by backend. | Claims in CLI-generated JWT verified by backend. |
| **Operational Complexity** | **MODERATE.** Requires Next.js server runtime and session management. | **HIGH.** Requires standing up / configuring external IdP (Keycloak/Auth0/Google). | **VERY LOW.** Requires zero new backend infrastructure or IdP services. |
| **Security Risks** | BFF becomes high-value target; CSRF protection required. | Network dependency on external IdP; token renewal complexity. | Operator token leakage if pasted into untrusted terminal; manual token rotation. |
| **Compatibility with Pravah Code** | **EXCELLENT.** Compatible with current FastAPI `verify_control_plane_auth`. | **POOR.** Requires rewriting `TokenAuth` from HS256 symmetric to RS256 JWKS asymmetric. | **EXCELLENT.** 100% compatible with existing `verify_control_plane_auth` without backend code changes. |
| **Required Future Changes** | Implement Next.js BFF route handlers, session cookies, and login view. | Deploy IdP, rewrite backend auth middleware to fetch JWKS, add OIDC client to UI. | Add Operator Token entry modal in UI (stored in React state); pass token to Axios client. |
| **Currently Implementable?** | **NO (Blocked by missing identity source)** | **NO (Blocked by absent IdP)** | **PARTIALLY (Requires owner approval of CLI token workflow)** |
| **Explicit Owner Approval Required?** | **YES** | **YES** | **YES** |

### Architectural Recommendation

1. **Long-Term Target (Production Enterprise):** **Option A (Next.js BFF)** with an enterprise identity provider (OIDC/SAML). This provides seamless SSO, centralized user management, HttpOnly cookie security, and complete isolation of backend secrets.
2. **Immediate Pragmatic Step (If Single-Operator Console):** If the owner intends Pravah as an internal operational console without deploying enterprise IdP infrastructure, **Option C (Ephemeral Operator Token Modal)** or **Option A with a Local Pre-Shared Operator Credential** is the fastest path to unblocking mutations while strictly maintaining fail-closed security and zero secret leakage.

---

## Section E: Mutation-by-Mutation Decision Matrix

All 12 primary mutating endpoints identified across Pravah services are categorized by their authoritative trust boundary and intended operational role:

| Endpoint | Port | Current AuthN | Current AuthZ | Intended Caller | Intended AuthN | Intended AuthZ | Browser Allowed? | BFF Required? | Decision Status |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `POST /ingest-link` | 8000 | `verify_control_plane_auth` (HS256 JWT) | None (Any valid JWT) | Human Operator / Admin | Operator AuthN (Session/JWT) | Operator / Admin Role | **YES (via BFF)** | **YES** | **OPERATOR-FACING — Awaiting Identity & Role Approval** |
| `POST /remove-link` | 8000 | `verify_control_plane_auth` (HS256 JWT) | None (`SEC-AUTH-NO-AUTHZ-001`) | Human Operator / Admin | Operator AuthN (Session/JWT) | Admin Role / Link Owner | **YES (via BFF)** | **YES** | **OPERATOR-FACING — Blocked by SEC-AUTH-NO-AUTHZ-001** |
| `POST /api/control-plane/override` | 7000 | **NONE** (`SEC-DEFECT-OVR-001`) | **NONE** | Human Operator / Admin | Operator AuthN (TokenAuth or BFF) | Admin / Operator Role | **YES (via BFF)** | **YES** | **OPERATOR-FACING — Blocked by SEC-DEFECT-OVR-001 Remediation** |
| `POST /vana/execute` | 8000 | None (HTTP layer) | Schema validation (`Group4Intake`) | VANA Group 2 Intake | Service Auth (mTLS or HMAC) | Service Capability | **NO** | **NO** | **UNRESOLVED F-BOUNDARY — Architecture Decision Required** |
| `POST /control-plane/runtime-ingest` | 8000 | None (HTTP layer) | `authorize_execution("governed-execution")` | Internal Agent Loop | Service Auth (HMAC / Localhost) | `governed-execution` Capability | **NO** | **NO** | **UNRESOLVED F-BOUNDARY — Service Boundary Hardening Required** |
| `POST /evidence` | 8000 | None | None | In-Memory Telemetry Stub | Reconcile with Port 7000 | Decommission or Unify | **NO** | **NO** | **UNRESOLVED F-BOUNDARY — Cross-Port Divergence Decision** |
| `POST /pravah/events` | 7000 | `check_shakti_auth` (`PRAVAH_API_KEY`) | `X-Source-System` Whitelist | Ecosystem Services (Shakti, etc.) | Pre-shared API Key | Source Whitelist | **NO** | **NO** | **SERVICE-TO-SERVICE — Certified Robust** |
| `POST /pravah/api/v1/publish` | 7000 | `check_shakti_auth` (`PRAVAH_API_KEY`) | `X-Source-System` Whitelist | Ecosystem Services (Alias) | Pre-shared API Key | Source Whitelist | **NO** | **NO** | **SERVICE-TO-SERVICE — Certified Robust** |
| `POST /evidence` | 7000 | `check_shakti_auth` (`PRAVAH_API_KEY`) | `X-Source-System` Whitelist | Ecosystem Services | Pre-shared API Key | Source Whitelist | **NO** | **NO** | **SERVICE-TO-SERVICE — Certified Robust** |
| `POST /api/runtime` | 7000 | `verify_request_trace` (HMAC) | Schema & Replay Check | Sarathi / Execution Pipeline | HMAC Trace Signature | Single-use Nonce / Timestamp | **NO** | **NO** | **SERVICE-TO-SERVICE — Certified Hardened** |
| `POST /api/ingest` | 8600 | None | None | Telemetry Collectors | Network Boundary (Passive Sink) | Passive Observer Role | **NO** | **NO** | **SERVICE-TO-SERVICE — Certified Passive Sink** |
| `POST /execute-action` | 5003 | `verify_service_auth` (HMAC) | Nonce + `governed-execution` | Decision Brain / Orchestrator | Service HMAC Signature | Governance Contract Execution | **NO** | **NO** | **SERVICE-TO-SERVICE — Certified Hardened** |

---

## Section F: Current 401 Behavior

### Detailed Interaction Lifecycle on `/api-explorer` and Dashboard

1. **Trigger:** A browser user opens `http://localhost:4500/api-explorer` and triggers the "Test Ingestion Endpoint" action, or submits a URL in the Dashboard link monitoring form (`http://localhost:4500/`).
2. **Client Dispatch:** The React client executes Axios POST call directly to backend port 8000:
   ```http
   POST http://localhost:8000/ingest-link HTTP/1.1
   Host: localhost:8000
   Content-Type: application/json

   {"link": "https://github.com/example/repo"}
   ```
3. **Backend Processing:** FastAPI route handler `ingest_link` invokes dependency `verify_control_plane_auth`.
4. **Header Inspection:** FastAPI inspects incoming headers for `Authorization` or `X-API-Token`. Both are absent.
5. **Fail-Closed Rejection:** FastAPI immediately halts execution and returns:
   ```http
   HTTP/1.1 401 Unauthorized
   Server: uvicorn
   Content-Type: application/json
   Content-Length: 51

   {"detail":"Authentication required: missing token"}
   ```
6. **UI State:** The frontend query client catches the 401 error and renders a notification or error state.

### Definitive Security Verdict

> ### THE CURRENT HTTP 401 BEHAVIOR IS PROPER, DESIRABLE, AND FAIL-CLOSED.
> 
> The 401 response is **not a bug**; it is the proven enforcement of the security boundary specified under `SEC-AUTH-001`. The backend is correctly protecting cluster state from unauthenticated browser callers. 
> 
> Under no circumstances should this 401 error be resolved by:
> - Removing `Depends(verify_control_plane_auth)` from backend routes.
> - Bundling `JWT_SECRET_KEY` into frontend JavaScript to generate tokens in the browser.
> - Hardcoding a static token into frontend client source code.
> 
> The 401 error will and must remain until an approved, authenticated proxy or session architecture is formally implemented.

---

## Section G: Required Owner Decisions

Before any engineering implementation begins, the repository owner and security architect must explicitly review and sign off on the following **12 foundational architecture decisions**:

1. **Operator Identity Source:** Which identity provider or mechanism shall serve as the source of truth for human operators? (e.g., Local pre-shared operator credentials, Corporate OIDC/SSO, GitHub/Google OAuth, or Infrastructure CLI issuance?)
2. **Operator Session Model:** How shall operator sessions be maintained between browser and frontend? (e.g., Server-side encrypted `HttpOnly` cookie, Redis session store, or ephemeral in-memory token per browser tab?)
3. **Operator Role Model:** What authoritative role taxonomy shall be established for Pravah? (e.g., `viewer`, `operator`, `admin`?)
4. **`/ingest-link` Authorization Policy:** Which roles are permitted to ingest monitored links? (Recommended: `operator` and `admin`.)
5. **`/remove-link` Authorization Policy (`SEC-AUTH-NO-AUTHZ-001`):** How shall deletion authorization be enforced? (Recommended: Require `admin` role, or require link-creator ownership.)
6. **`/api/control-plane/override` Authorization Policy (`SEC-DEFECT-OVR-001`):** Which roles are permitted to freeze/unfreeze autonomous recovery? (Recommended: Strictly `admin` role.)
7. **Port 7000 Override Remediation Strategy:** Shall `POST /api/control-plane/override` be protected by adding `TokenAuth` directly to Flask, or by binding port 7000 to loopback `127.0.0.1` and requiring Next.js BFF proxying?
8. **Trust Model for `POST /control-plane/runtime-ingest` (Port 8000):** Shall this route be protected by service-to-service HMAC authentication, or restricted strictly to internal Docker/Kubernetes networking?
9. **Trust Model for `POST /evidence` (Port 8000):** Shall this in-memory endpoint be decommissioned in favor of Port 7000's authenticated evidence store, or hardened with matching authentication?
10. **Trust Model for `POST /vana/execute` (Port 8000):** What service-level authentication mechanism shall govern the VANA Group 4 intake boundary?
11. **Strict Service-to-Service Isolation Boundary:** Confirmation that ports 5003 (`/execute-action`), 7000 (`/api/runtime`), and 8600 (`/api/ingest`) shall remain permanently isolated from browser access.
12. **Final Frontend Authentication Architecture Approval:** Formal approval to adopt **Option A (Next.js BFF)** as the target architecture for operator mutations.

---

## Section H: Implementation Gate

```
================================================================================
                           SECURITY IMPLEMENTATION GATE
================================================================================

IMPLEMENTATION STATUS: BLOCKED

Implementation of frontend operator authentication, BFF route handlers, login
interfaces, or authorization middleware is STRICTLY BLOCKED until the repository
owner formally resolves and signs off on the 12 Owner Decisions in Section G.

Zero production code, zero frontend components, zero backend contracts, and zero
test suites may be altered during Phase 3.5.

================================================================================
```

---

## Section I: Repository Integrity Verification

Forensic git verification commands executed from repository root `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah`:

### Command 1: `git diff -- VANA/`
- **Output:** Empty (0 lines of diff).
- **Verdict:** VANA contracts, tests, and source code are 100% untouched.

### Command 2: `git status --short VANA/`
- **Output:** Empty (0 modified or untracked files in VANA).
- **Verdict:** Complete VANA isolation preserved.

### Command 3: `git status --short`
- **Modified (Pre-existing accepted Phase 3.2 files):**
  - `pravah-bhiv/deployment_verification_packet/readiness_validation.log`
  - `pravah-bhiv/frontend/src/app/analytics/page.tsx`
  - `pravah-bhiv/frontend/src/app/page.tsx`
  - `pravah-bhiv/frontend/src/app/replay/page.tsx`
  - `pravah-bhiv/frontend/src/app/runtime/page.tsx`
  - `pravah-bhiv/frontend/src/types/index.ts`
  - Runtime service log files (`logs/...`)
  - Runtime state files (`security/nonce_store.json`, `security/trace_consumption.json`)
- **Untracked (Audit Reports & Phase 3.2 route):**
  - `pravah-bhiv/audit/PHASE3_1_FRONTEND_5_TAB_FORENSIC_BASELINE.md`
  - `pravah-bhiv/audit/PHASE3_3_FRONTEND_AUTH_ARCHITECTURE_FORENSICS.md`
  - `pravah-bhiv/audit/PHASE3_4_MUTATION_AUTHORIZATION_BOUNDARY_FORENSICS.md`
  - `pravah-bhiv/audit/PHASE3_4_1_MUTATION_BOUNDARY_CLOSURE.md`
  - `pravah-bhiv/audit/PHASE3_5_OPERATOR_AUTH_ARCHITECTURE_DECISION.md` (THIS REPORT)
  - `pravah-bhiv/frontend/src/app/logs/` (Accepted Phase 3.2 route)
- **Verdict:** Zero production code, test code, or backend contracts modified during Phase 3.5.

### Command 4: `git diff --stat`
- **Output:** Confirms zero uncommitted code modifications beyond pre-existing Phase 3.2 baseline and active service log appends.

### Command 5: `git diff --name-only`
- **Output:** Confirms zero changes outside accepted Phase 3.2 scope.

---

## Final Report Requirements: Authoritative Answers

1. **Does Pravah currently have an authoritative browser operator identity source?**  
   **NO.** No browser operator identity source, user store, login route, or IdP configuration currently exists in the repository.
2. **Does Pravah currently have an authoritative operator role/authorization model?**  
   **NO.** `TokenAuth` payload contains strictly `user_id`, `exp`, and `iat`. The backend performs zero role, capability, or permission verification on human callers.
3. **Is the BFF technically compatible?**  
   **YES.** Next.js App Router route handlers already operate in the project, Node.js can securely isolate `JWT_SECRET_KEY`, and port 8000 natively accepts the HS256 JWTs it generates.
4. **Is BFF actually implementable now, or blocked by missing identity/AuthZ decisions?**  
   **BLOCKED.** Implementing the BFF now without an approved identity source and role model would create an unauthenticated confused deputy proxy.
5. **What exact authentication architecture is recommended, and why?**  
   **Next.js BFF (Option A) with HttpOnly secure session cookies.** It completely prevents `JWT_SECRET_KEY` leakage into browser bundles, provides a clean separation between browser session state and backend cluster tokens, and requires zero changes to the core FastAPI token verification engine.
6. **What exact decisions must the owner approve?**  
   The 12 formal decisions enumerated in Section G (Identity source, session model, role taxonomy, `/ingest-link` authz, `/remove-link` authz, `/override` remediation strategy, and service endpoint isolation).
7. **Which endpoints are operator-facing?**  
   - `POST /ingest-link` (Port 8000)
   - `POST /remove-link` (Port 8000)
   - `POST /api/control-plane/override` (Port 7000)
8. **Which endpoints remain service-to-service?**  
   - `POST /api/runtime` (Port 7000)
   - `POST /pravah/events` (Port 7000)
   - `POST /pravah/api/v1/publish` (Port 7000)
   - `POST /evidence` (Port 7000)
   - `POST /api/ingest` (Port 8600)
   - `POST /execute-action` (Port 5003)
9. **Which endpoints remain F?**  
   - `POST /control-plane/runtime-ingest` (Port 8000)
   - `POST /evidence` (Port 8000)
   - `POST /vana/execute` (Port 8000)
10. **Why does `/api-explorer` currently return 401?**  
    Because the browser dispatches direct, unauthenticated requests to port 8000, which strictly enforces `verify_control_plane_auth` requiring a signed HS256 JWT. The 401 response is correct fail-closed security.
11. **What must NOT be changed before approval?**  
    Backend auth dependencies, frontend client callers, `JWT_SECRET_KEY` distribution, port 7000 override route, VANA contracts, and test fixtures must not be touched or bypassed.
12. **Is implementation permitted in this task?**  
    **NO — ARCHITECTURE DECISION ONLY. IMPLEMENTATION IS NOT AUTHORIZED.**
