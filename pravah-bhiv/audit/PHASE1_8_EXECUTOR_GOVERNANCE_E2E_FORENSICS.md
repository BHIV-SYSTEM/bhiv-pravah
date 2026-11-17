# TASK PHASE 1.8 — REAL EXECUTOR & GOVERNANCE E2E FORENSIC AUDIT

**Audit Date**: 2026-09-04  
**Audit Target**: Complete Pravah Execution Path (`Runtime/Decision -> Capability Authorization -> Execution Contract -> Action Governance -> Real Executor Gateway -> Execution Result -> Signed Execution Lineage`)  
**Execution Root**: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Final Classification**: **B. PARTIALLY PROVEN — specific real-boundary evidence still missing**

---

## 1. Executive Summary & Baseline Results

This forensic audit evaluates the entire execution lifecycle in Pravah, tracing how runtime inputs and decision requests flow through capability discovery, rights adaptation, cryptographic contract formation, action governance enforcement, and out to the executor gateway.

### Baseline Test Execution
Run from `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`:
```
pytest --collect-only -q
222 tests collected in 0.79s

pytest -q
222 passed, 345 warnings in 4.28s
```
- **Tests Collected**: 222
- **Passed**: 222
- **Failed**: 0
- **Errors**: 0
- **Skipped**: 0
- **Warnings**: 345 (deprecation warnings for `datetime.utcnow()` and FastAPI `@app.on_event`)

---

## 2. Real Production Execution Path Trace

The production execution pipeline connects multiple layers from ingest to execution dispatch. Below is the step-by-step trace of every transition in the active source code:

| Step | Component | Exact File & Location | Input Contract | Output Contract | Security / Governance Check | Execution Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Runtime Ingest** | FastAPI Ingest Endpoint | [`backend/control_plane/backend/app/main.py:1134`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/backend/app/main.py#L1134) (`runtime_ingest`) | `RuntimeIngestPayload` (`service_id`, `issue_type`, `metrics`, `environment`) | Validated Pydantic model; calls `build_decision_request()` | Payload schema validation via Pydantic | **REAL** (Active endpoint) |
| **2. Decision Engine** | Rule-based Decision Engine | [`backend/control_plane/backend/app/decision_engine.py:20`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/backend/app/decision_engine.py#L20) (`DecisionEngine.decide`) | `DecisionRequest` (`cpu`, `memory`, `environment`, `service_id`) | `DecisionResponse` (`selected_action`, `confidence`, `reason`, `version`) | Environment action-scope check (`ACTION_SCOPE[env]`) | **REAL** (Pure function) |
| **3. Capability Discovery** | Discovery Engine | [`backend/control_plane/capabilities/capability_discovery.py:34`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/capabilities/capability_discovery.py#L34) (`discover_by_id`) | `capability_id = "governed-execution"` | Capability JSON definition from registry | Registry status check (`status == "PRESENT"`) | **REAL** (Reads filesystem JSON) |
| **4. Capability Authorization** | Execution Rights Adapter | [`backend/control_plane/capabilities/execution_rights_adapter.py:203`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/capabilities/execution_rights_adapter.py#L203) (`authorize_execution`) | `capability_id`, `action` | Cryptographically signed `auth_payload` dictionary | Validates mapping existence, verified status, evidence file & line bounds, action allowlist, signs with HMAC-SHA256 | **REAL** (Fail-closed boundary) |
| **5. Execution Contract** | Contract Builder | [`backend/contracts/execution_contract.py:117`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/contracts/execution_contract.py#L117) (`build_execution_contract`) | `DecisionContract`, `auth_payload`, `approved_by="sarathi"` | `ExecutionContract` instance | Verifies `auth_payload` signature; appends `CREATED` and `APPROVED` lineage events | **REAL** (Signs and logs lineage) |
| **6. Action Governance** | Multi-Layer Governance | [`backend/control_plane/core/action_governance.py:293`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/action_governance.py#L293) (`evaluate_contract`) | `DecisionContract`, context containing `ExecutionContract` | `GovernanceDecision` (`should_block`, `admission_state`, `policy_snapshot`) | Environment eligibility check, action cooldown check, repetition limit check, policy engine admission check | **REAL** (Enforces policy) |
| **7. Policy Engine** | Deterministic Policy Engine | [`backend/control_plane/security/deterministic_policy_engine.py:441`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/security/deterministic_policy_engine.py#L441) (`admit`) | `PolicyAdmissionRequest` | `PolicyAdmissionDecision` (`allowed`, `rejection_code`, `legitimacy`) | Validates governance contract HMAC signature, execution contract action matching, version matching | **REAL** (Evaluates rules) |
| **8. Execution Gate** | Enforcement Check | [`backend/control_plane/backend/app/main.py:662`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/backend/app/main.py#L662) | `GovernanceDecision` | Continues if `not should_block`; returns HTTP 200 rejection if `should_block` | Checks `governance_decision.should_block` | **REAL** (Gate enforced) |
| **9. Network Dispatch** | HTTP Client | [`backend/control_plane/backend/app/main.py:685`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/backend/app/main.py#L685) | `payload = {"action": action, "service_id": service_id}` | HTTP Response from `http://localhost:5003/execute-action` | Signs request with `X-Service-Id`, `X-Service-Timestamp`, `X-Service-Nonce`, `X-Service-Signature` | **BLOCKED** (Target port 5003 offline) |
| **10. Real Executor** | Flask Execution Service | [`backend/reliability-controller2-main/executer/app.py:126`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/reliability-controller2-main/executer/app.py#L126) | HTTP POST with headers and JSON body | JSON: `{"execution_id": uuid, "status": "executed"/"failed", "verified": bool}` | Verifies HMAC headers (`verify_service_auth`); validates action; checks cooldown; executes docker/k8s subprocess | **UNREACHABLE** (Daemon not running) |
| **11. Execution Result** | API Response Bridge | [`backend/control_plane/backend/app/main.py:692`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/backend/app/main.py#L692) | Executor response JSON | `(True, response.json())` | Catches exceptions and returns `(False, str(e))` | **NOT PROVEN** (Mocked in all tests) |
| **12. Lineage Append** | Post-Execution Lineage | [`backend/contracts/execution_contract.py:270`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/contracts/execution_contract.py#L270) (`transition_contract_state`) | Intended: `new_state = "EXECUTED"` | Intended: Appended `EXECUTED` event in `execution_lineage.jsonl` | Intended: Semantic transition guard validation | **NOT IMPLEMENTED** (Never called in `main.py`) |
| **13. Lineage Replay** | Replay Verifier | [`backend/control_plane/core/execution_lineage.py:207`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/execution_lineage.py#L207) (`replay_execution_lineage`) | `execution_id` | Replay summary dict | Cryptographic hash chain verification, signature checks, state transition rules | **REAL** (Evaluates journal) |

---

## 3. Action Governance Verification

Inspected: [`ActionGovernance`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/action_governance.py#L89), [`evaluate_contract()`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/action_governance.py#L293), and [`DeterministicPolicyEngine.admit()`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/security/deterministic_policy_engine.py#L441).

### Security Boundary Analysis:
Can an execution reach the executor without:
1. **Valid capability authorization?**  
   **NO.** In `main.py:616`, `authorize_execution(capability_id="governed-execution", action=action)` is invoked first. If the capability is unmapped or the action is not in `allowed_actions`, `authorize_execution()` raises `CapabilityNotFound` or `MappingNotFound`, returning `False, {"status": "rejected", "rejection_code": "EXECUTION_NOT_PERMITTED"}` before governance or executor is reached.
2. **Valid execution contract?**  
   **NO.** In `main.py:643`, `build_execution_contract()` is invoked with `decision` and `auth_payload`. If `auth_payload` lacks a valid HMAC signature, contract building raises `ValueError`.
3. **Valid mapping?**  
   **NO.** `ExecutionRightsAdapter._validate_mapping()` verifies that the evidence file exists within the repository root, line numbers are within range, and `verification.status == "VERIFIED"`.
4. **Valid signature?**  
   **NO.** `DeterministicPolicyEngine._verify_governance_contract()` verifies the HMAC signature of the governance contract against `signing_key`.
5. **Approved governance decision?**  
   **NO.** In `main.py:662`, `if governance_decision.should_block:` halts execution immediately. Actions violating cooldown (e.g. 60s for restart), exceeding repetition limits (3 per 300s), or disallowed in the environment (e.g. `scale_up` in `prod`) are blocked.
6. **Execution gate (`validate_execution_gate`)?**  
   **FINDING**: [`backend/control_plane/executor/governance_gate.py:7`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/executor/governance_gate.py#L7) defines `validate_execution_gate(payload)`, requiring `service_id`, `action`, and `trace_id`. However, **no production code in `main.py` or `ActionGovernance` calls `validate_execution_gate()`**. The gating is performed entirely by `if governance_decision.should_block:` in `main.py`.

---

## 4. Real Executor Gateway Implementation Analysis

File inspected: [`backend/reliability-controller2-main/executer/app.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/reliability-controller2-main/executer/app.py)

### Technical Specifications:
- **Framework**: Flask (`app = Flask(__name__)`)
- **Listening Interface**: `0.0.0.0:5003` (`if __name__ == "__main__": app.run(host="0.0.0.0", port=5003)`)
- **Route**: `POST /execute-action`
- **Request Headers**: `X-Service-Id`, `X-Service-Timestamp`, `X-Service-Nonce`, `X-Service-Signature`
- **Expected Body**: `{"service_id": str, "action": str, "trace_id": Optional[str]}`
- **Authentication**: `verify_service_auth(data)` verifies HMAC header signatures. In non-prod environments when headers are omitted, it falls back to checking `X-CALLER: sarathi`.
- **Validation**: `VALID_ACTIONS = ["restart", "scale_up", "scale_down", "noop"]`. Actions outside this list return HTTP 400.
- **Cooldown**: Enforces a 10-second cooldown per `service_id` (`COOLDOWN_TIME = 10`), returning HTTP 429 if active.
- **Execution Mechanism**:
  - `EXECUTION_MODE == "docker"`:
    - `"restart"`: Invokes `subprocess.run(["docker", "restart", service_id], capture_output=True, text=True)`.
    - `"scale_up"`: Simulates result string (`f"DOCKER_SCALE_UP simulated for {service_id}"`).
    - `"scale_down"`: Simulates result string (`f"DOCKER_SCALE_DOWN simulated for {service_id}"`).
    - `"noop"`: Returns `"noop"`.
  - `EXECUTION_MODE == "kubernetes"`:
    - `"restart"`: Invokes `kubectl rollout restart deployment/{service_id}`.
    - `"scale_up"`: Invokes `kubectl scale deployment/{service_id} --replicas=2`.
    - `"scale_down"`: Invokes `kubectl scale deployment/{service_id} --replicas=1`.
- **Verification**: `verify_deployment(service_id)` executes `docker ps` or `kubectl get pods` to verify container presence.

### Availability Determination:
- **Port 5003 Status**: **OFFLINE**. Connection probe returns `[WinError 10061] No connection could be made because the target machine actively refused it`.
- **Host Infrastructure**: Docker Desktop daemon is not running (`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`).
- **Kubernetes**: Client installed (`v1.36.1`), but no local cluster is active.
- **Controlled Local Execution**: Safe local execution of `app.py` cannot be established without launching an unmanaged background process and mocking Docker/K8s commands. As instructed, no simulated fakes were substituted to claim E2E proof.

---

## 5. Governance → Executor Network Boundary Analysis

File inspected: [`backend/control_plane/backend/app/main.py:680-692`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/backend/app/main.py#L680-L692)

```python
payload = {
    "action": action,
    "service_id": service_id
}
headers = build_signed_headers(service_id, payload)
response = requests.post(
    "http://localhost:5003/execute-action",
    json=payload,
    headers=headers,
    timeout=3
)
```

### Forensic Findings at the Network Boundary:
1. **URL Construction**: Fixed string `"http://localhost:5003/execute-action"`. It does not read from an environment variable such as `EXECUTOR_URL`.
2. **Missing Execution Contract Propagation**: The `ExecutionContract` constructed on line 643 is **NOT** included in `payload` or headers sent to the executor. The executor has no awareness of the upstream contract.
3. **Missing Capability Information**: `capability_id` (`"governed-execution"`) is not passed across the HTTP boundary.
4. **Missing Trace Information**: `trace_id` is omitted from `payload`. Consequently, the executor's single-use replay protection (`is_trace_consumed(trace_id)`) on lines 156-164 of `executer/app.py` is bypassed, and the executor generates its own unlinked `execution_id = str(uuid.uuid4())`.
5. **Direct Caller Bypass Vulnerability**:
   - In non-prod environments (`ENVIRONMENT != "prod"`), `executer/app.py:149` permits callers with header `X-CALLER: sarathi` to execute actions without cryptographic signatures and without having passed through Pravah's `ActionGovernance`.
   - In prod environments, callers must possess the shared `SECRET_KEY` to generate valid `X-Service-Signature` headers, but the executor does not verify whether the action was evaluated or approved by `ActionGovernance`.

---

## 6. Real Positive Path Investigation

We investigated whether a safe, non-destructive action can execute live through:
`Pravah -> Governance -> Real Executor -> Result -> Lineage`

### Forensic Determination: **CANNOT COMPLETE LIVE**
1. **Action `"noop"`**:
   - In `ActionGovernance`, `"noop"` is eligible in all environments with 0s cooldown.
   - However, in `VERIFIED_CAPABILITY_MAPPINGS["governed-execution"]["allowed_actions"]`, the allowed actions are explicitly:
     `["restart", "scale_up", "scale_down", "rollback"]`.
   - `"noop"` is **NOT** in `allowed_actions`. Calling `execute_action("noop", "app01")` fails-closed at `authorize_execution()`, raising `MappingNotFound: Action 'noop' is not authorized for capability 'governed-execution'`.
2. **Action `"restart"`**:
   - `"restart"` passes `authorize_execution()`, creates an `ExecutionContract`, and passes `ActionGovernance.evaluate_contract()`.
   - However, when attempting `requests.post("http://localhost:5003/execute-action")`, the connection fails immediately because port 5003 is offline. `execute_action()` catches the exception and returns `False, "<connection refused>"`.
3. **Action `"rollback"`**:
   - Permitted by `governed-execution`, but rejected by the executor's `VALID_ACTIONS = ["restart", "scale_up", "scale_down", "noop"]`.

**Conclusion**: No safe, non-destructive action can complete the full live unmocked path in this environment.

---

## 7. Negative & Adversarial Case Analysis

| Scenario | Rejection Point | Exception / Status | Executor Reached? | Lineage Appended? | False Success Risk |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Unknown Capability** | `authorize_execution()` | `CapabilityNotFound` / `EXECUTION_NOT_PERMITTED` | **NO** | None | **ZERO** (Aborts immediately) |
| **B. Unauthorized Action** | `authorize_execution()` | `MappingNotFound` / `EXECUTION_NOT_PERMITTED` | **NO** | None | **ZERO** (Aborts immediately) |
| **C. Invalid Execution Contract** | `build_execution_contract()` | `ValueError` / `ValidationError` | **NO** | None | **ZERO** (Aborts before call) |
| **D. Forged Contract Signature** | `validate_execution_contract()` | `ValueError: signature mismatch` | **NO** | None | **ZERO** (HMAC mismatch) |
| **E. Invalid Capability Mapping** | `_validate_mapping()` | `MappingNotFound` (bad evidence file/line) | **NO** | None | **ZERO** (Fail-closed mapping) |
| **F. Governance Rejection** | `ActionGovernance.evaluate_contract()` | `should_block = True` (`cooldown_active`, etc.) | **NO** | `CREATED`, `APPROVED` | **ZERO** (Lineage stops; HTTP call aborted) |
| **G. Missing Executor** | `requests.post()` | `requests.exceptions.ConnectionError` | **FAILED AT NETWORK** | `CREATED`, `APPROVED` | **ZERO** (Returns `False, error`) |
| **H. Executor Rejection** | `executer/app.py` | HTTP 400/401/403/429 (`status="failed"`) | **YES (if online)** | `CREATED`, `APPROVED` | **ZERO** (Returns executor status) |
| **I. Malformed Executor Output** | `response.json()` | `requests.exceptions.JSONDecodeError` | **YES (if online)** | `CREATED`, `APPROVED` | **ZERO** (Returns `False, error`) |

All negative boundaries fail-closed cleanly. At no point can an unmapped capability, unauthorized action, forged signature, or network error produce a false-positive success.

---

## 8. Lineage Closure Analysis

Inspected: [`backend/control_plane/core/execution_lineage.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/control_plane/core/execution_lineage.py) and [`backend/contracts/execution_contract.py`](file:///C:/Users/black/OneDrive/Desktop/Pravah/bhiv-pravah/pravah-bhiv/backend/contracts/execution_contract.py).

### Findings:
1. **Pre-Execution Lineage**:
   - In `build_execution_contract()` (`contracts/execution_contract.py:179-190`), two events are appended to `execution_lineage.jsonl`:
     1. `state = "CREATED"`
     2. `state = "APPROVED"`
   - Both events are cryptographically chained (`previous_hash`), timestamped, and HMAC signed with `source = "governance"`.
2. **Post-Execution Lineage Gap (CRITICAL ARCHITECTURAL FINDING)**:
   - When the executor returns an execution result (success or failure), `execute_action()` returns `True, response.json()`.
   - In `main.py::runtime_ingest()`, lines 1209-1220 log the execution result to `trace_logger.log_event` (`logs/trace_log.jsonl`).
   - **However, neither `execute_action()` nor `runtime_ingest()` invokes `transition_contract_state()` or `append_lineage_event()` to record `EXECUTED`, `COMPLETED`, or `FAILED` in `execution_lineage.jsonl`.**
   - The method `transition_contract_state()` in `contracts/execution_contract.py:270` is never called anywhere in the production codebase.
   - Consequently, the execution contract in the lineage store remains permanently at `APPROVED`. The post-execution lifecycle is not closed in the authoritative lineage journal.
3. **Lineage Replay Behavior**:
   - Calling `replay_execution_lineage(contract.execution_id)` succeeds with `valid=True`, but `final_state` is `"APPROVED"`, reflecting that execution completion was never recorded to the journal.

---

## 9. Existing Test Quality & Mock Classification

Repository test suites were audited for mocking patterns at critical boundaries:

| Test File | Test Name | Boundary Mocked | Classification | Forensic Finding |
| :--- | :--- | :--- | :--- | :--- |
| `backend/tests/test_phase8_execution_closure.py` | `test_api_missing_capability` | `requests.post`, `sign_trace`, `canonicalize` | **MOCKED E2E CLAIM** | Simulates HTTP 200 executor response; does not test real network or signing key. |
| `backend/tests/test_phase8_execution_closure.py` | `test_api_unmapped_capability` | `requests.post`, `VERIFIED_CAPABILITY_MAPPINGS = {}` | **UNIT/INTEGRATION ONLY** | Proves unmapped capability rejects before HTTP call; `mock_post.assert_not_called()`. |
| `backend/tests/test_phase8_execution_closure.py` | `test_agent_runtime_unmapped_capability` | `AgentRuntime._initialize_components` | **UNIT/INTEGRATION ONLY** | Proves `AgentRuntime._enforce()` rejects `scale_up` in prod via real `ActionGovernance`. |
| `backend/tests/test_phase8_execution_closure.py` | `test_rl_orchestrator_demo_mode` | `ActionGovernance` | **MOCKED E2E CLAIM** | Patches `ActionGovernance` directly; governance checks are bypassed. |
| `backend/control_plane/capabilities/test_execution_rights_adapter.py` | `test_integration_execute_action_bypasses_adapter_success` | `requests.post`, `_load_state`, `_save_state` | **PARTIAL E2E / MOCKED EXECUTOR** | Evaluates real `authorize_execution`, `build_execution_contract`, and `ActionGovernance`, but mocks executor response with `MockResponse({"status": "executed"})`. |
| `backend/control_plane/capabilities/test_execution_rights_adapter.py` | `test_integration_execute_action_bypasses_adapter_rejection` | `requests.post` | **REAL INTEGRATION NEGATIVE TEST** | Real `authorize_execution` rejects `"invalid_action"`; verifies `mock_post.assert_not_called()`. |
| `backend/tests/test_replay_sovereignty.py` | `test_executer_app_endpoints` | `check_nonce`, `is_trace_consumed`, `consume_trace`, `execute_action`, `requests.post` | **UNIT/INTEGRATION ONLY** | Tests Flask route handlers via `app.test_client()`, but patches subprocess execution and trace storage. |
| `backend/tests/test_phase16_group4_action_request.py` | (Multiple tests) | `ActionGovernance.evaluate_contract` | **MOCKED E2E CLAIM** | Injects synthetic `approved_decision` or `blocked_decision` into intake pipelines. |
| `backend/tests/test_group4_final_lineage_closure.py` | (Multiple tests) | `ActionGovernance.evaluate_contract` | **MOCKED E2E CLAIM** | Injects synthetic `approved_decision` to test downstream translation. |
| `backend/tests/test_cert001_decision_routing.py` | (Multiple tests) | `agent_runtime.ActionGovernance`, `requests.post` | **MOCKED E2E CLAIM** | Both governance and HTTP dispatch are mocked simultaneously. |

**Key Takeaway**: There is **zero unmocked test coverage** for the live HTTP hop between Pravah and the executor gateway on port 5003.

---

## 10. External Dependencies Breakdown

- **PROVEN LOCALLY**:
  - Capability discovery against registry JSON files
  - Fail-closed execution rights adaptation and action allowlist enforcement
  - Execution contract formation and HMAC payload signing
  - ActionGovernance policy enforcement (cooldowns, repetition suppression, environment eligibility)
  - Deterministic policy engine admission evaluation
  - Execution lineage persistence fail-closed behavior (Phase 1.7 fix)
- **PROVEN BY SOURCE**:
  - Wiring in `main.py::execute_action()` calling `authorize_execution()`, `build_execution_contract()`, and `ActionGovernance.evaluate_contract()`
  - Executor endpoint request handling and HMAC header verification in `executer/app.py`
  - Gap: Missing propagation of `execution_contract`, `capability_id`, and `trace_id` in HTTP payload
  - Gap: Omission of `EXECUTED`/`COMPLETED` lineage transitions after executor return
- **PROVEN BY EXISTING TEST**:
  - Unit and mock-isolated integration behaviors across all 222 passing tests
- **NOT PROVEN**:
  - Live unmocked HTTP request delivery from Pravah to the executor on port 5003
  - Live container restart or scale operations via Docker or Kubernetes
  - Live deployment verification via `docker ps` or `kubectl get pods`
- **BLOCKED BY ENVIRONMENT**:
  - Executor process (`bhiv-sarathi`) is offline (port 5003 connection refused)
  - Docker daemon is offline on the host OS
  - No active local Kubernetes cluster

---

## 11. Repository Integrity

- `git status --short`: Verified. No production files, tests, or configurations were modified.
- `git diff -- VANA/`: **0 lines of diff**. All VANA code, documentation, tasks, and audits remain 100% untouched.
- Exactly one report created: `audit/PHASE1_8_EXECUTOR_GOVERNANCE_E2E_FORENSICS.md`.
- No scratch, helper, or temporary files were created.

---

## 12. Final Classification & Conclusion

### Final Classification:
**B. PARTIALLY PROVEN — specific real-boundary evidence still missing**

### Rationale:
1. **Upstream Governance Path Is Fully Proven**: The path from `Runtime/Decision` through `Capability Authorization`, `Execution Contract Construction`, and `Action Governance Policy Evaluation` is fully implemented, wired in production code, and cryptographically verified.
2. **Real Network Boundary Evidence Is Missing**: The executor gateway on port 5003 is offline in this environment. All tests claiming E2E execution mock `requests.post`. Live unmocked delivery from Pravah to the executor has never been demonstrated.
3. **Contract Propagation Gap**: The HTTP request constructed in `main.py::execute_action()` does not transmit `execution_contract`, `capability_id`, or `trace_id` to the executor.
4. **Lineage Closure Gap**: The production code never transitions execution contracts to `EXECUTED` or `COMPLETED` in `execution_lineage.jsonl`. Lineage records stop at `APPROVED`.
