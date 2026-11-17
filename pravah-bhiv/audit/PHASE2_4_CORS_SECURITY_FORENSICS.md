# PHASE 2.4 FORENSIC AUDIT: CONTROL-PLANE CORS SECURITY

**Scope**: PRAVAH ONLY  
**Target Component**: Control Plane FastAPI Application (`backend/control_plane/backend/app/main.py`)  
**Audit Date**: 2026-09-07  
**Status**: COMPLETE  
**Final Classification**: **B — Confirmed CORS Security Gap; Remediation Required**  

---

## 1. EXECUTIVE SUMMARY & FORENSIC DISCOVERY

This audit investigates the Cross-Origin Resource Sharing (CORS) configuration of the Pravah Control Plane to independently verify and expand upon the baseline finding originally identified in Phase 2.1 (`SEC-002` / `REQ-2.9`).

### 1.1 Core Forensic Findings
1. **Unrestricted Vercel Subdomain Acceptance**:
   `backend/control_plane/backend/app/main.py` configures `allow_origin_regex` with the default pattern:
   ```python
   r"^https://.*\.vercel\.app$|^http://localhost:\d+$"
   ```
   This regex matches **any** tenant hosted on Vercel (`https://<any-tenant>.vercel.app`). Any untrusted third party with a free Vercel account can deploy an arbitrary web application that is fully trusted by the Pravah Control Plane's CORS middleware.

2. **Unrestricted Localhost Port Expansion**:
   The pattern `^http://localhost:\d+$` trusts **every** port on `localhost` (ports `0` through `65535`). If a developer or operator runs any untrusted script, test runner, secondary web server (e.g. Jupyter, Jenkins, local web server, or compromised npm dev server) on any local port, that server has cross-origin access to the Control Plane.

3. **Wildcard Default in Docker Compose**:
   In `backend/docker-compose.yml` (line 143), the environment variable is declared as:
   ```yaml
   - BACKEND_CORS_ORIGINS=${BACKEND_CORS_ORIGINS:-*}
   ```
   If `BACKEND_CORS_ORIGINS` is unset at container startup, it injects `*`, causing `_parse_cors_origins()` to return `["*"]`, which completely opens the Control Plane to all origins worldwide.

4. **Production Environment Configuration Flaw**:
   In `backend/environments/prod.env` (line 69), the production configuration specifies:
   ```env
   BACKEND_CORS_ORIGIN_REGEX="^https://.*\.yotta\.com$|^https://.*\.vercel\.app$|^http://localhost:\d+$"
   ```
   This retains the broad wildcard regex for both `*.vercel.app` and `localhost:\d+`, along with broad `*.yotta.com` wildcarding, while enclosing the pattern in literal double quotes that can corrupt regex parsing depending on the env loader.

5. **Exposed Unauthenticated Control Plane Endpoints**:
   While `/ingest-link` and `/remove-link` enforce `TokenAuth`, multiple high-privilege Control Plane endpoints—most critically `POST /control-plane/runtime-ingest`, `POST /process-runtime`, `POST /vana/execute`, and `GET /live-dashboard`—are **completely unauthenticated**. Because CORS reflects the requesting origin for any Vercel tenant or localhost port, an attacking web page visited by a user can read sensitive operational telemetry, trigger RL decision loops, and invoke operational actions cross-origin.

6. **Complete Absence of Regression Tests**:
   There are currently **0 tests** in the repository covering CORS middleware behavior, preflight handling, or origin rejection.

---

## 2. SOURCE-OF-TRUTH DISCOVERY

### 2.1 Authoritative Runtime Configuration
The authoritative runtime entrypoint for the Pravah Decision Brain and Control Plane API is `backend/control_plane/backend/app/main.py`.

Lines 103–123 and 173–182 define the CORS middleware setup:

```python
# backend/control_plane/backend/app/main.py:103-124
def _parse_cors_origins() -> list[str]:
    """Parse explicit CORS origins from env with sane defaults for local and prod."""
    raw = os.getenv(
        "BACKEND_CORS_ORIGINS",
        ",".join(
            [
                "http://localhost:4500",
                "http://localhost:3000",
                "https://multi-agent-control-plane-frontend.vercel.app",
            ]
        ),
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _cors_origin_regex() -> str:
    """Allow Vercel preview URLs and localhost ports unless overridden."""
    return os.getenv(
        "BACKEND_CORS_ORIGIN_REGEX",
        r"^https://.*\.vercel\.app$|^http://localhost:\d+$",
    )

# backend/control_plane/backend/app/main.py:173-181
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins() + ["http://localhost:8000", "http://localhost:4500"],
    allow_origin_regex=_cors_origin_regex(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,
)
```

### 2.2 Configuration Sources and Precedence
| Source Location | Mechanism | Configured Value / Default | Impact |
| :--- | :--- | :--- | :--- |
| `main.py:105-115` | `os.getenv("BACKEND_CORS_ORIGINS")` | Default: `localhost:4500`, `localhost:3000`, `multi-agent-control-plane-frontend.vercel.app` | Base explicit origins list |
| `main.py:175` | Code concatenation | Appends `["http://localhost:8000", "http://localhost:4500"]` | Hardcoded addition (redundant `localhost:4500`) |
| `main.py:118-123` | `os.getenv("BACKEND_CORS_ORIGIN_REGEX")` | Default: `r"^https://.*\.vercel\.app$\|^http://localhost:\d+$"` | Matches all Vercel subdomains & localhost ports |
| `docker-compose.yml:143` | Container environment | `BACKEND_CORS_ORIGINS=${BACKEND_CORS_ORIGINS:-*}` | Injects `*` if env var unset |
| `prod.env:68-69` | Production env template | `BACKEND_CORS_ORIGINS=...`, `BACKEND_CORS_ORIGIN_REGEX="^https://.*\.yotta\.com$\|^https://.*\.vercel\.app$\|^http://localhost:\d+$"` | Persists broad regex into production |
| `agent_api.py:77-83` | Independent Flask API (port 7000) | Explicit list: `["https://multi-agent-control-plane-frontend.vercel.app", "https://multi-agent-control-plane-frontend-dev.vercel.app", "http://localhost:4500", "http://localhost:3200", "http://localhost:3000"]` | **Note**: `agent_api.py` does NOT use regex; it uses an explicit allowlist! |
| `observer_server.py:350-355` | Observer FastAPI (port 8600) | `allow_origins=["*"]` | Wide-open observer interface |

---

## 3. CURRENT ALLOWED-ORIGIN ANALYSIS

### 3.1 Explicitly Allowed Origins
When defaults apply in `main.py`:
- `http://localhost:4500` (Pravah Next.js frontend dev & production server port)
- `http://localhost:3000` (Standard Next.js dev port)
- `http://localhost:8000` (Backend self-origin)
- `https://multi-agent-control-plane-frontend.vercel.app` (Legitimate production frontend origin)

### 3.2 Regex-Expanded Origins
The regex `r"^https://.*\.vercel\.app$|^http://localhost:\d+$"` introduces massive over-permissioning:
1. **Any Vercel Subtenant**:
   - `https://attacker-control-panel.vercel.app` $\implies$ **ALLOWED**
   - `https://phishing-site.vercel.app` $\implies$ **ALLOWED**
   - `https://any-unrelated-project.vercel.app` $\implies$ **ALLOWED**
2. **Any Localhost Port**:
   - `http://localhost:9999` $\implies$ **ALLOWED**
   - `http://localhost:8080` $\implies$ **ALLOWED**
   - `http://localhost:1337` $\implies$ **ALLOWED**
3. **Wildcard Containment in Docker**:
   If deployed via `docker-compose` without overriding `BACKEND_CORS_ORIGINS`, `"*" in allow_origins` is `True`, permitting **every origin on the internet**.

### 3.3 Headers, Methods, and Credentials
- `allow_credentials`: `False` (Cookies / HTTP Basic auth not sent).
- `allow_methods`: `["*"]` (GET, POST, PUT, DELETE, PATCH, OPTIONS, etc.).
- `allow_headers`: `["*"]` (Permits `Authorization`, `X-API-Token`, `Content-Type`, custom headers).
- `max_age`: `86400` (Preflight results cached for 24 hours).

---

## 4. SECURITY THREAT MODEL & ATTACK VECTORS

```
Attacker Deploy on Vercel                          Victim Browser Context
(https://evil-tenant.vercel.app)               (Developer or Operator)
               │                                            │
               │ 1. Victim visits attacker site             │
               ├───────────────────────────────────────────►│
               │                                            │
               │ 2. Background script sends cross-origin    │
               │    fetch("http://localhost:8000/...")      │
               │                                            │
               │                                            ▼
               │                           Pravah Control Plane API
               │                           (http://localhost:8000)
               │                                            │
               │ 3. Browser checks CORS Preflight           │
               │    Origin: https://evil-tenant.vercel.app  │
               │                                            │
               │ 4. FastAPI matches `.*\.vercel\.app`!      │
               │    Returns: Access-Control-Allow-Origin:   │
               │             https://evil-tenant.vercel.app │
               │                                            │
               │ 5. Browser allows request & response read! │
               │◄───────────────────────────────────────────┤
               │                                            │
               ▼                                            ▼
Data Exfiltration / Action Triggering:        CRITICAL ACTIONS EXECUTED:
- Reads /live-dashboard                     - POST /control-plane/runtime-ingest
- Reads /recent-activity                      Triggers DecisionEngine + execute_action()
- Reads /metrics                             - POST /process-runtime
- Reads /api/lineage/{id}                     Mutates decision queues
```

### 4.1 Concrete Attack Vectors

#### Vector A: Cross-Origin Invocation of Mutating Autonomous Runtime Ingest
`POST /control-plane/runtime-ingest` accepts a `RuntimeIngestPayload` and has **no authentication dependency**:
```python
@app.post("/control-plane/runtime-ingest")
def runtime_ingest(payload: RuntimeIngestPayload):
    ...
    decision = DecisionEngine.decide(decision_request)
    success, execution_result = execute_action(
        action=decision.selected_action,
        service_id=payload.service_id,
    )
```
- An attacker site hosted on `https://attacker.vercel.app` can issue cross-origin POST requests to `http://localhost:8000/control-plane/runtime-ingest`.
- The browser checks CORS. The Control Plane matches `.*\.vercel\.app`, sends `Access-Control-Allow-Origin: https://attacker.vercel.app`, and permits the request.
- The request triggers `DecisionEngine.decide()` and invokes `execute_action()` on live services without caller verification.

#### Vector B: Cross-Origin Telemetry & State Exfiltration
Endpoints such as:
- `GET /live-dashboard`
- `GET /recent-activity`
- `GET /metrics`
- `GET /orchestration/metrics`
- `GET /api/lineage/{execution_id}`
contain sensitive system metrics, topology, ML features, active links, and execution history.
Because CORS reflects the requesting origin, JavaScript on `https://attacker.vercel.app` or `http://localhost:9999` can read the full JSON response bodies.

#### Vector C: Localhost Pivoting / Side-Channel Compromise
Developers frequently run third-party tools, local dev servers for other projects, or test mock servers on other ports (e.g. 3001, 8080, 8888).
Under `^http://localhost:\d+$`, any cross-site scripting flaw or malicious dependency in any local tool can interact directly with the Pravah Control Plane.

---

## 5. CONTROL-PLANE ENDPOINT IMPACT MATRIX

| Endpoint | Method | Auth Enforced | Mutating | Cross-Origin Threat via Broad CORS |
| :--- | :--- | :--- | :--- | :--- |
| `/health` | GET | None | No | Low (Health status exposed) |
| `/action-scope` | GET | None | No | Low (Action scope matrix exposed) |
| `/recent-activity` | GET | None | No | **HIGH**: Operational decisions exfiltratable |
| `/` | GET | None | No | **HIGH**: Full live dashboard payload readable |
| `/live-dashboard` | GET | None | No | **HIGH**: Full system telemetry, ML features, active links readable |
| `/decision-summary` | GET | None | No | Medium: Aggregate operational stats readable |
| `/ingest-link` | POST | **TokenAuth** (`401` on missing/bad token) | Yes | Medium: Preflight accepted; protected by token, but CORS provides 0 defense-in-depth |
| `/remove-link` | POST | **TokenAuth** (`401` on missing/bad token) | Yes | Medium: Preflight accepted; protected by token |
| `/control-plane/status` | GET | None | No | Low: System status readable |
| `/control-plane/apps` | GET | None | No | Medium: Registered application list exposed |
| `/orchestration/metrics`| GET | None | No | Medium: RL brain & control plane metrics exposed |
| `/metrics` | GET | None | No | Medium: Prometheus telemetry exposed |
| `/api/health` | GET | None | No | Low: Health check |
| `/api/lineage/{id}` | GET | None | No | **HIGH**: Cryptographic lineage, state history readable |
| `/api/lineage/{id}/verify` | GET | None | No | Medium: Lineage verification details readable |
| `/process-runtime` | POST | None | **Yes** | **CRITICAL**: Telemetry processing & decision insertion unauthenticated |
| `/control-plane/runtime-ingest` | POST | None | **Yes** | **CRITICAL**: Triggers DecisionEngine and operational `execute_action()`! |
| `/autonomous-status` | GET | None | No | Low: Autonomy flags readable |
| `/dashboard/state` | GET | None | No | Medium: Dashboard state readable |
| `/pravah/events` | POST | None | Yes | Medium: Ingests trace events into system |
| `/evidence` | POST | None | Yes | Medium: Stores evidence bundles |
| `/evidence/{ref}` | GET | None | No | Medium: Reads evidence bundles |
| `/api/ml/features/latest`| GET | None | No | Medium: Real-time ML feature vector readable |
| `/vana/execute` | POST | None | **Yes** | **HIGH**: Submits Group 2 rulings into Group 4 intake boundary |

---

## 6. AUTHENTICATION INTERACTION ANALYSIS

### 6.1 Does TokenAuth Render CORS Harmless?
**NO.**
1. **Only 2 of 24 endpoints use TokenAuth**: Only `/ingest-link` and `/remove-link` currently declare `auth = Depends(verify_control_plane_auth)`.
2. **22 endpoints are unauthenticated**: Mutating endpoints like `/control-plane/runtime-ingest` and observation endpoints like `/live-dashboard` rely solely on network and browser-origin boundaries.
3. **Defense-in-Depth Collapse**: Even for `/ingest-link` and `/remove-link`, CORS is designed to be the browser's outermost perimeter. Permitting `Authorization` headers and reflecting `Access-Control-Allow-Origin` for arbitrary Vercel origins means that if an attacker manages to obtain a token (e.g. via local storage inspection, side-channel, or phishing), the browser will execute the cross-origin request without origin-level rejection.

---

## 7. TEST AUTHENTICITY EVALUATION

### 7.1 Existing Tests
A comprehensive search of `backend/tests/` reveals:
- Total CORS tests: **0**
- Total preflight `OPTIONS` tests: **0**
- Total origin rejection tests: **0**

### 7.2 Current Test Deficiency
No automated test proves:
- That legitimate origins (`https://multi-agent-control-plane-frontend.vercel.app`, `http://localhost:4500`) are accepted.
- That unapproved Vercel tenants (`https://attacker.vercel.app`) are rejected.
- That unapproved localhost ports (`http://localhost:9999`) are rejected.
- That unapproved external origins (`https://evil.com`) are rejected.
- That `allow_credentials` remains `False`.
- That preflight `OPTIONS` headers are properly restricted.

---

## 8. REQUIRED TEST MATRIX DESIGN (REMEDIATION GATE)

The following test suite must be implemented during remediation in a dedicated test module (`backend/tests/test_phase2_cors_security.py`):

| Test ID | Test Scenario | Request Details | Expected Result |
| :--- | :--- | :--- | :--- |
| **CORS-01** | Approved Production Origin | `Origin: https://multi-agent-control-plane-frontend.vercel.app`<br>`GET /health` | `Access-Control-Allow-Origin: https://multi-agent-control-plane-frontend.vercel.app`<br>`Status: 200` |
| **CORS-02** | Approved Dev Frontend Origin (Port 4500) | `Origin: http://localhost:4500`<br>`GET /live-dashboard` | `Access-Control-Allow-Origin: http://localhost:4500`<br>`Status: 200` |
| **CORS-03** | Approved Dev Alt Origin (Port 3000) | `Origin: http://localhost:3000`<br>`GET /live-dashboard` | `Access-Control-Allow-Origin: http://localhost:3000`<br>`Status: 200` |
| **CORS-04** | Approved Self Origin (Port 8000) | `Origin: http://localhost:8000`<br>`GET /health` | `Access-Control-Allow-Origin: http://localhost:8000`<br>`Status: 200` |
| **CORS-05** | Unapproved Vercel Tenant Rejection | `Origin: https://evil-attacker.vercel.app`<br>`GET /live-dashboard` | **No `Access-Control-Allow-Origin` header in response** |
| **CORS-06** | Unapproved Localhost Port Rejection | `Origin: http://localhost:9999`<br>`GET /live-dashboard` | **No `Access-Control-Allow-Origin` header in response** |
| **CORS-07** | Arbitrary External HTTPS Origin Rejection | `Origin: https://evil.com`<br>`GET /health` | **No `Access-Control-Allow-Origin` header in response** |
| **CORS-08** | Null Origin Rejection | `Origin: null`<br>`GET /health` | **No `Access-Control-Allow-Origin` header in response** |
| **CORS-09** | Preflight OPTIONS on Approved Origin | `OPTIONS /control-plane/runtime-ingest`<br>`Origin: http://localhost:4500`<br>`Access-Control-Request-Method: POST`<br>`Access-Control-Request-Headers: content-type` | `Status: 200`<br>`Access-Control-Allow-Origin: http://localhost:4500`<br>`Access-Control-Allow-Methods` contains `POST`<br>`Access-Control-Allow-Headers` contains `content-type` |
| **CORS-10** | Preflight OPTIONS on Unapproved Origin | `OPTIONS /control-plane/runtime-ingest`<br>`Origin: https://malicious.vercel.app`<br>`Access-Control-Request-Method: POST` | **No `Access-Control-Allow-Origin` header**; preflight rejected |
| **CORS-11** | Credentials Policy Enforcement | `Origin: http://localhost:4500`<br>`GET /health` | **`Access-Control-Allow-Credentials` is NOT `true`** |
| **CORS-12** | Environment Variable Override | Set `BACKEND_CORS_ORIGINS="https://custom.domain.com"`<br>`Origin: https://custom.domain.com` | `Access-Control-Allow-Origin: https://custom.domain.com` |

---

## 9. RECOMMENDED PRODUCTION REMEDIATION DESIGN

### 9.1 Minimal, Fail-Closed Source Remediation

#### A. In `backend/control_plane/backend/app/main.py`:
1. **Eliminate the wildcard regex default**:
   Change `_cors_origin_regex()` so that by default it returns `None` (or empty string `""`), disabling regex-based matching completely unless explicitly configured for staging environments:
   ```python
   def _cors_origin_regex() -> Optional[str]:
       """Optional regex for preview environments. Disabled by default in production."""
       val = os.getenv("BACKEND_CORS_ORIGIN_REGEX", "").strip()
       return val if val else None
   ```
2. **Define strict explicit approved origins**:
   Consolidate and deduplicate default approved origins:
   ```python
   DEFAULT_APPROVED_ORIGINS = [
       "http://localhost:4500",
       "http://localhost:3000",
       "http://localhost:8000",
       "https://multi-agent-control-plane-frontend.vercel.app",
       "https://multi-agent-control-plane-frontend-dev.vercel.app",
   ]

   def _parse_cors_origins() -> list[str]:
       raw = os.getenv("BACKEND_CORS_ORIGINS", "").strip()
       if not raw:
           return list(DEFAULT_APPROVED_ORIGINS)
       origins = [o.strip() for o in raw.split(",") if o.strip()]
       # Reject accidental wildcard in explicit list
       return [o for o in origins if o != "*"]
   ```
3. **Clean up `app.add_middleware()`**:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=_parse_cors_origins(),
       allow_origin_regex=_cors_origin_regex(),
       allow_credentials=False,
       allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
       allow_headers=["Authorization", "Content-Type", "X-API-Token", "Accept"],
       max_age=86400,
   )
   ```

#### B. In `backend/docker-compose.yml`:
Line 143:
```yaml
# BEFORE:
- BACKEND_CORS_ORIGINS=${BACKEND_CORS_ORIGINS:-*}

# AFTER:
- BACKEND_CORS_ORIGINS=${BACKEND_CORS_ORIGINS:-http://localhost:4500,http://localhost:3000,https://multi-agent-control-plane-frontend.vercel.app}
```

#### C. In `backend/environments/prod.env`:
Lines 68–69:
```env
# BEFORE:
BACKEND_CORS_ORIGINS=https://##YOTTA_URL:PRAVAH_FRONTEND_DOMAIN##,http://localhost:8000
BACKEND_CORS_ORIGIN_REGEX="^https://.*\.yotta\.com$|^https://.*\.vercel\.app$|^http://localhost:\d+$"

# AFTER:
BACKEND_CORS_ORIGINS=https://##YOTTA_URL:PRAVAH_FRONTEND_DOMAIN##,https://multi-agent-control-plane-frontend.vercel.app,http://localhost:8000
BACKEND_CORS_ORIGIN_REGEX=
```

---

## 10. REGRESSION & COMPATIBILITY ANALYSIS

1. **Pravah Frontend Compatibility**:
   - The Pravah Next.js frontend is configured in `frontend/package.json` to run on `http://localhost:4500`.
   - In production, it deploys to `https://multi-agent-control-plane-frontend.vercel.app`.
   - Both origins remain explicitly allowlisted. Zero functionality in the frontend will be broken.
2. **Next.js Server-Side Proxies Unaffected**:
   - As documented in `frontend/src/services/api.ts` (lines 220–265), Group 2 and Group 4 VANA requests use Next.js server routes (`/api/vana/group2`, `/api/vana/group4`).
   - Server-to-server HTTP calls do not enforce browser CORS and are unaffected.
3. **External API / CI/CD Clients Unaffected**:
   - Python test suites, curl commands, and server-to-server webhook consumers do not send browser `Origin` headers and do not evaluate CORS.
4. **Local Development Experience**:
   - Developers using standard local ports (`4500`, `3000`, `8000`) continue to work seamlessly without manual env setup.

---

## 11. VERIFICATION OF INTEGRITY

### 11.1 VANA Directory Integrity
```
git diff -- VANA/
(empty — 0 lines modified)
```

### 11.2 Authoritative Test Baseline
From authoritative root `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`:
```
pytest --collect-only -q
298 tests collected in 0.86s

pytest -q
298 passed, 370 warnings in 18.59s
```

---

## 12. RIGOROUS INVENTORY & FINAL CLASSIFICATION

### 12.1 PROVEN
- `_cors_origin_regex()` in `main.py:118-123` allows any tenant on `*.vercel.app` and any port on `localhost:\d+`.
- `docker-compose.yml:143` defaults to wildcard `*` if `BACKEND_CORS_ORIGINS` is unset.
- `prod.env:69` retains broad wildcard regex patterns.
- High-privilege mutating endpoints (e.g. `POST /control-plane/runtime-ingest`) are unauthenticated and directly exposed to cross-origin browser invocation under this regex.
- Sensitive telemetry endpoints (e.g. `GET /live-dashboard`, `GET /recent-activity`) reflect `Access-Control-Allow-Origin` to arbitrary Vercel tenants, enabling cross-origin data exfiltration.
- The test suite has exactly **0 CORS tests**.

### 12.2 NOT PROVEN
- Exploitation across non-browser clients (CORS is a browser-only security barrier; non-browser attackers are unaffected by CORS).

### 12.3 REMAINING GAPS
- Unrestricted Vercel and localhost regex patterns remain active in `main.py`.
- No CORS regression tests exist in the codebase.

### 12.4 RECOMMENDED REMEDIATION
- Execute Task Phase 2.4.1 to implement the minimal fail-closed remediation and test suite defined in Sections 8 and 9.

### 12.5 Final Classification
**B — Confirmed CORS Security Gap; Remediation Required**
