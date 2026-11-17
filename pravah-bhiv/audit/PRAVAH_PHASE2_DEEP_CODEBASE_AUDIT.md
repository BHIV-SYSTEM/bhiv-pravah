# Executive Summary

This document provides a deep, code-level, production-readiness audit of the `bhiv-pravah` repository for Phase 2: Advanced Integration & Security Hardening — SHIVAM PRAVAH Enterprise Runtime Deployment and ML Intelligence Foundation. The audit evaluates the architectural integrity, security posture, integration completeness, traceability, and deterministic execution capabilities of the codebase.

The current system exhibits partial readiness. While the architectural foundation (Control Plane, FastAPI backends, Next.js frontend) and core concepts (Traceability, Decision Engine, Telemetry) are implemented, numerous production paths rely on mocks, simulations, or local hardcoded behaviors that bypass strict contracts and external integrations. Specifically, the test suite is failing due to missing imports, the RL Decision Engine relies on a frozen demo mode, and authentication is missing on several endpoints.

# Repository Inventory

**Application Code**
- `frontend/` (Next.js Application)
- `backend/control_plane/` (Core Control Plane logic, multi-app registry, capabilities, telemetry, executor)
- `backend/orchestrator/` (App Orchestration)
- `backend/executer/` (Runtime Executors)
- `backend/insightflow/` (Telemetry/Websocket)
- `backend/sarathi/` (API Router)

**Infrastructure Code**
- `backend/Dockerfile`
- `backend/docker-compose.yml`
- `backend/docker-compose.local.yaml`
- `backend/docker-compose.production.template.yml`
- `backend/reliability-controller2-main/k8s/`
- `.github/workflows/cicd.yml`

**Tests**
- `backend/tests/` (Unit and Integration tests using pytest)
- `backend/scripts/run_hostile_tests.py` (Adversarial test suite)

**Configuration**
- `backend/environments/` (dev.env, prod.env, stage.env)
- `backend/control_plane/config/apps_registry.json`

**Documentation**
- `backend/docs/`
- `backend/review_packets/`
- `backend/GROUP4_EOD_20260826/GROUP4_EOD_HANDOVER.md`

**Legacy/Dead Code**
- `backend/_local_simulation.py`
- `backend/validate_demo_lock.py`

# Architecture Derived From Code

**Component:** Control Plane API (FastAPI)
**Location:** `backend/control_plane/backend/app/main.py`
**Entry point:** `FastAPI` app initialization
**Main responsibilities:** Exposing endpoints for runtime ingestion, health checks, and dashboard metrics.
**Dependencies:** `ActionGovernance`, `DecisionEngine`, `IntegrationBridge`, `HTTPDecisionProvider`
**Who calls it:** External services sending telemetry, frontend dashboard
**What it calls:** `HTTPDecisionProvider`, `ActionGovernance`
**Persistence:** `INGESTED_RUNTIME_STATE` (In-memory dict)
**Current status:** ACTIVE

**Component:** Agent Runtime
**Location:** `backend/agent_runtime.py`
**Entry point:** `AgentRuntime.run()`
**Main responsibilities:** Autonomous agent loop (sense, validate, decide, enforce, act, observe, explain).
**Dependencies:** `RedisEventBus`, `ActionGovernance`, `HTTPDecisionProvider`, `AgentStateManager`, `PerceptionLayer`
**Current status:** ACTIVE (Requires `PRAVAH_MAIN_API`)

**Component:** Decision Brain
**Location:** `backend/control_plane/core/rl/external_api/rl_decision_brain.py`
**Main responsibilities:** Make RL-based decisions based on metrics (CPU, memory).
**Current status:** SIMULATED / NON-PRODUCTION (Uses `demo_mode=True`)

**Component:** Telemetry Collector
**Location:** `backend/control_plane/telemetry/telemetry_collector.py`
**Current status:** ACTUALLY IMPLEMENTED

# Runtime Entry Points

1. **Entry point:** FastAPI Control Plane
   **File:** `backend/control_plane/backend/app/main.py`
   **Function:** `app = FastAPI(...)`
   **Status:** PRODUCTION

2. **Entry point:** Observer Server
   **File:** `backend/observer_server.py`
   **Status:** ACTIVE

3. **Entry point:** Agent Runtime Loop
   **File:** `backend/agent_runtime.py`
   **Function:** `AgentRuntime.run()`
   **Status:** ACTIVE

4. **Entry point:** Local Simulation
   **File:** `backend/_local_simulation.py`
   **Status:** DEVELOPMENT ONLY

# End-to-End Runtime Flows

**Flow:** Telemetry Ingestion -> Decision -> Execution
1. HTTP Request (Telemetry)
   ↓ `main.py` (Router / `build_decision_request`)
2. Validation
   ↓ `HTTPDecisionProvider`
3. Decision Engine (External API / RL Brain)
   ↓ `ActionGovernance.evaluate_action()`
4. Governance / Execution Gate (`enforce_action_scope`)
   ↓ `requests.post("http://localhost:5003/execute-action")`
5. Runtime / Executor (External / Local Executor)

# API Contract Audit

| Method | Path | Router | Auth | Request Schema | Response Schema | Service | Status |
| ------ | ---- | ------ | ---- | -------------- | --------------- | ------- | ------ |
| POST | /ingest-link | main.py | None | dict | dict | Control Plane | NOT ENFORCED |
| POST | /process-runtime | main.py | None | RuntimeIngestPayload | DecisionResponse | Decision Brain | ENFORCED |
| POST | /execute-action | executor.py| Signed Headers | dict | dict | Executor | ENFORCED |

# Authentication & Authorization Audit

**Finding ID:** SEC-AUTH-001
**Severity:** HIGH
**Component:** Control Plane
**File:** `backend/control_plane/backend/app/main.py`
**Function:** `ingest_link()`
**Evidence:** 
```python
@app.post("/ingest-link")
def ingest_link(payload: dict[str, Any]) -> dict[str, Any]:
```
**Actual behavior:** Endpoint accepts requests without authorization middleware/dependency.
**Expected behavior:** API should validate authentication headers (e.g., JWT, API key) to authorize ingestion.
**Impact:** Unauthenticated users can ingest links and alter telemetry metrics.
**Recommended implementation:** Add authentication dependency to the endpoint.
**Status:** OPEN

# Trace Sovereignty & Traceability Audit

**Implementation:** `build_signed_telemetry` uses HMAC-SHA256 signatures with `SSPL_SECRET`.
**Trace Generation:** CLIENT-SUPPLIED but verified by CORE-SIGNED HMAC.
**Status:** IMPLEMENTED BUT NOT WIRED globally across all endpoints (some endpoints bypass signature validation).
**Bypass:** `execute_action` inside `main.py` generates new internal signed headers but does not pass through the original trace payload cleanly.

# Decision Engine Audit

**Component:** `rl_decision_brain.py`
**Status:** SIMULATED / NON-PRODUCTION.
The RL layer uses `demo_mode=True` which disables learning and exploration, enforcing deterministic fallback rules.
**Trigger:** Real runtime data triggers it, but the output is rule-based simulation.

# Runtime / Executor Audit

**Component:** `backend/executer/executor.py`
**Status:** MOCK EXECUTION / SIMULATED EXECUTION in some paths.
**Validation:** `_mock_execute_action()` is used in the RL training layer. Real execution relies on localhost endpoints:
**Evidence:**
```python
response = requests.post(
    "http://localhost:5003/execute-action",
    json=payload,
    headers=headers,
    timeout=3
)
```
**Status:** SIMULATED EXECUTION (Hardcoded to localhost:5003).

# Database & Storage Audit

**Persistence:** Mostly file-based JSON/CSV logging.
- `append_only_log.jsonl`
- `logs/agent/agent_state_*.json`
- Redis is used for EventBus (`RedisEventBus`).
**Status:** SIMULATED / NON-PRODUCTION. True relational database persistence is not fully wired for all state.

# Observability & Production Monitoring Audit

**Implemented:** Metrics exported via CSV files (e.g., `logs/dev/metrics/latency_metrics.csv`), UptimeMonitor.
**Status:** PARTIALLY READY. Uses file-based logging rather than structured Prometheus metrics for all endpoints, though a `prometheus.yml` exists.

# Error Handling & Error Boundary Audit

**Finding ID:** ERR-001
**Severity:** MEDIUM
**Component:** Link Ingestion
**File:** `backend/control_plane/backend/app/main.py`
**Function:** `_generate_link_metadata`
**Evidence:**
```python
except Exception:
    pass # Fallback cleanly if rate limited or network failure
```
**Actual behavior:** Broad exception is caught and silently ignored.
**Expected behavior:** The exception should be logged, and specific exceptions (like `requests.Timeout`) should be handled.
**Impact:** Networking issues are hidden, making debugging difficult.
**Recommended implementation:** Log the exception details and handle specific errors appropriately.
**Status:** OPEN

# Metadata Extraction Audit

| Format | Documented | Code Exists | Wired | Tested | Production Ready |
| ------ | ---------- | ----------- | ----- | ------ | ---------------- |
| JSON | Yes | Yes | Yes | Yes | Yes |
| TXT/CSV| Yes | Yes | Yes | Partial | No |

# Multi-Format Support Audit

**Status:** PARTIALLY SUPPORTED (Primarily JSON event payloads).

# ML / AI Intelligence Audit

**Component:** `MLFeatureExtractor` in `main.py`
**Status:** PLACEHOLDER / RULE-BASED. Features are extracted statically or with simulated data. The model does not dynamically learn in production (`demo_mode=True`).

# Deterministic Execution Audit

**Status:** Deterministic execution is enforced via `demo_mode=True` in the RL brain, but this is a mock of determinism rather than true reproducible ML inference.

# Contract Boundary Audit

**Contracts:** `DecisionRequest`, `RuntimeIngestPayload`
**Bypass:** Direct dictionary access is used in several places instead of Pydantic validation (e.g., `payload.get("action")`).

# Test Coverage Audit

Pytest is used. `pytest --collect-only` fails due to missing `build` module and `PRAVAH_MAIN_API` configuration error.
**Status:** RED. Tests do not pass natively without specific mock/env setups.

# E2E Integration Audit

| Link | Implemented | Actually Wired | Tested | Real | Evidence |
| ---- | ----------- | -------------- | ------ | ---- | -------- |
| Telemetry -> API | Yes | Yes | No | Yes | `main.py` routes |
| API -> Decision | Yes | Yes | No | Mock | `HTTPDecisionProvider` |
| Decision -> Exec | Yes | Yes | No | Mock | Localhost hardcode |

# Docker & Deployment Audit

**Status:** `docker-compose.yml` and `Dockerfile` exist. However, scripts like `start_prod_services.ps1` hardcode localhost configurations and dummy keys.

# CI/CD Audit

**Status:** `.github/workflows/cicd.yml` exists.

# Configuration & Environment Audit

**Secrets:** `SSPL_SECRET_KEY` defaults to `default-secret-key-change-in-prod`. `environments/prod.env` uses placeholder templates.

# Security Findings

**Finding ID:** SEC-002
**Severity:** HIGH
**Component:** Executer API
**File:** `backend/control_plane/backend/app/main.py`
**Evidence:** 
```python
os.getenv("BACKEND_CORS_ORIGIN_REGEX", r"^https://.*\.vercel\.app$|^http://localhost:\d+$")
```
**Risk:** Broad CORS regex allowing any localhost port and any vercel app.

# Dependency Audit

**Status:** Requirements files present (`requirements.txt`). Missing module `build` in dependencies, causing tests to fail.

# Dead Code / Legacy Code Audit

- `_local_simulation.py`: CI/CD Simulation tool, dead code in production.
- `validate_demo_lock.py`: Test data mock, dead code in production.

# Mock / Fake / Simulation Audit

**Finding:** `_setup_mock_mode()` in `RedisEventBus`.
**Classification:** PRODUCTION MOCK (Fallback).

**Finding:** `_mock_execute_action()` in RL Training Layer.
**Classification:** DEVELOPMENT MOCK.

**Finding:** `demo_mode=True` in `rl_decision_brain.py`.
**Classification:** SIMULATION.

# Phase-2 Requirement Mapping

| Assignment Requirement | Existing Code | Actual Status | Gap | Priority |
| ---------------------- | ------------- | ------------- | --- | -------- |
| Automated Metadata | `MLFeatureExtractor`| Mocked | Requires real model | P1 |
| Authentication | `auth.py` | Partial | Missing on APIs | P0 |
| Traceability | `hmac` signatures | Wired | Incomplete coverage | P1 |

# Production Readiness Scorecard

- Architecture: YELLOW
- Security: RED
- Testing: RED
- CI/CD: YELLOW

# Prioritized Gap List

**P0 - Critical**
- Fix failing tests and broken imports (`build` module missing, configuration errors).
- Remove hardcoded `localhost:5003` URLs from `execute_action`.
- Enforce authentication on all control plane APIs.

**P1 - High**
- Replace `demo_mode=True` simulated RL with a real deterministic ML model or explicit rule engine.
- Wire up a real database instead of local JSON/CSV files.

# Required External Resources

- Production Database (PostgreSQL/Redis)
- Real Decision Engine / ML Model API
- Secrets Manager (for `SSPL_SECRET_KEY`, etc.)
- True Executor API endpoint

# Verification Commands & Results

- `pytest --collect-only`: FAILED
```text
Command: pytest --collect-only
Failure: ImportError while importing test module
Reason: ModuleNotFoundError: No module named 'build', ConfigurationError: PRAVAH_MAIN_API is required for production Decision Brain execution.
Required resource: Properly configured test environment.
```

# Git History Findings

UNVERIFIED — REQUIRES RUNTIME/ENVIRONMENT ACCESS

# Recommended Implementation Sequence

1. **Task ID:** FIX_TESTS
   **Title:** Fix Test Environment & Imports
   **Why first:** Cannot verify any other changes without a working test suite.
   **Files likely involved:** `backend/orchestrator/app_orchestrator.py`, `backend/agent_runtime.py`
   **Implementation objective:** Ensure `pytest` completes collection and tests pass.
   
2. **Task ID:** SECURE_APIS
   **Title:** Implement Authentication Middleware
   **Why first:** Security prerequisite before wiring real executors.
   **Files likely involved:** `backend/control_plane/backend/app/main.py`
   **Implementation objective:** Enforce token authentication on ingestion APIs.

3. **Task ID:** WIRE_REAL_EXECUTOR
   **Title:** Replace localhost hardcodes with dynamic executor discovery
   **Why first:** Enables real E2E testing.
   **Files likely involved:** `backend/control_plane/backend/app/main.py`
   **Implementation objective:** Use environment variables or service discovery to route `execute_action`.

# Final Certification Assessment

## Current System Status
Overall: RED

## Phase-2 Certification
NOT READY

## Top 10 Risks
1. Test suite is broken, preventing validation.
2. Hardcoded localhost endpoints in production paths.
3. Lack of authentication on critical ingestion endpoints.
4. Mute exception swallowing in networking code.
5. RL Decision Engine is frozen in demo mode.
6. Overly permissive CORS settings.
7. Dependency on local file system for persistence.
8. Missing dependencies (`build` module) in requirements.
9. Incomplete trace propagation in external requests.
10. Secrets exposed or loosely managed via templates.

## Top 10 Required Actions
1. Fix Python imports and configuration errors.
2. Remove hardcoded executor URL and use environment variable.
3. Add authentication dependency to `/ingest-link`.
4. Fix broad exception handler in `_generate_link_metadata`.
5. Remove `demo_mode=True` or implement real ML engine.
6. Restrict CORS regex.
7. Integrate Redis/PostgreSQL for persistent state.
8. Add missing dependencies to `requirements.txt`.
9. Ensure `X-Trace-Id` flows cleanly through all requests.
10. Integrate Yotta Secrets Manager natively.

## First Task To Implement
**Fix Test Environment & Imports**
The system currently cannot pass basic pytest collection due to a missing `build` module in `orchestrator/app_orchestrator.py` and unconfigured environment variables (`PRAVAH_MAIN_API`). This must be fixed first because it unlocks the ability to verify all subsequent Phase-2 work securely.
- **Files involved:** `backend/orchestrator/app_orchestrator.py`, `backend/agent_runtime.py`, `backend/requirements.txt`
- **Required external resources:** N/A
- **Acceptance criteria:** `pytest --collect-only` and `pytest` run without fatal import or configuration errors.
- **Verification method:** Run `pytest`.
