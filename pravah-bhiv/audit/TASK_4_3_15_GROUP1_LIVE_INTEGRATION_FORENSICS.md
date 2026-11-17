# TASK 4.3.15: Group1 Live Integration Forensics

This report documents the forensic investigation of the single remaining full-suite test failure (`test_group1_observation_api_live_health`). No modifications were made to production code, test code, registry configuration, or deployment state.

## 1. Execution-Root Verification
- **Command Location:** `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`
- **Git Root:** `C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah`
- **Test Collection (`pytest --collect-only -q`):** 216 tests collected.
- **Full Suite Run (`pytest -q`):** 1 failed, 215 passed. (The single failure is `test_group1_observation_api_live_health`).

## 2. Failing Test Analysis
**File:** `backend/tests/test_phase10_group1_integration.py`
- **Expected Endpoint:** Dynamic, sourced from `CapabilityDiscovery().discover_by_id("group1-observation-api")`.
- **Method & Timeout:** `GET` request to `{endpoint}/health` with `timeout=10`.
- **Expected Status:** HTTP `200 OK`.
- **Expected Response Schema:** JSON containing `{"status": "healthy"}`.
- **Authentication:** None required.
- **Test Intent:** This is a live integration test intended to prove that the registry is correctly configured with a functional, deployed capability endpoint.

## 3. Exact Registry State
**File:** `backend/control_plane/capabilities/registry/group1-observation-api.json`
- `status`: `DOCUMENTED`
- `deployment_status`: `PENDING`
- `live_endpoint_available`: `false`
- `runtime.endpoint`: `null`
- **Note:** "Application-side contract and canonical persistence are locally verified. PostgreSQL/PostGIS VM deployment and final shared-environment end-to-end validation remain pending."

## 4. Group1 Implementation & Deployment Evidence
A search across the repository (`git grep`) reveals that the Group 1 Observation API is implemented and deployed. It does not run from this repository natively; it is a shared, external service.
- Documentation such as `GROUP1_RUNTIME_VERIFICATION.md`, `VANA_CONTROL_CENTER_ASSESSMENT.md`, and `VANA_ENDPOINT_CONTRACT.md` clearly states the service is live at `http://163.128.209.18:8013`.
- `frontend/src/services/api.ts` directly uses this IP as the canonical URL.

## 5. Safe Connectivity Result
A read-only fetch against the documented health endpoint was performed:
```http
GET http://163.128.209.18:8013/health
```
**Result:** 
```json
{"status":"healthy","service":"VANA MasterDB Observation API","version":"1.0.0"}
```
The service is confirmed live, reachable, and completely healthy.

## 6. Test-vs-Deployment Comparison
- The test correctly reads the registry.
- The registry explicitly returns `null` for the endpoint.
- The actual deployment exists, is healthy, and perfectly fulfills the contract.
- The `GROUP1_RUNTIME_VERIFICATION.md` document claims the registry was updated to reflect the live status, but `git log` proves `group1-observation-api.json` was never modified since its creation on Aug 17. 

## 7. Classification
**TEST CORRECT — CONFIGURATION GAP**
The test is doing its job enforcing that the live registry aligns with the real environment. The Group 1 service is fully deployed and healthy, but the JSON configuration file (`registry/group1-observation-api.json`) was never updated to bridge the gap.

## 8. Required Next Action
To resolve the failure natively without mocking or weakening the test, the registry configuration must be updated to match the real deployed environment. 
Edit `backend/control_plane/capabilities/registry/group1-observation-api.json`:
- Set `runtime.endpoint` to `"http://163.128.209.18:8013"`
- Set `metadata.live_endpoint_available` to `true`
- Set `metadata.deployment_status` to `"DEPLOYED"`
- Set `metadata.runtime_status` to `"LIVE"`

## 9. Git Integrity
Running `git diff --stat` against the Phase 10 test file and the registry JSON confirms that **0 modifications** were introduced during this investigation.
