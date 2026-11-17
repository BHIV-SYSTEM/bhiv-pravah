# TASK 4.3.10 — PHASE 8 API DRIFT FORENSICS

## 1. Baseline
Executing `pytest -q` yielded:
- **Collected**: 216
- **Passed**: 207
- **Failed**: 9
- **Warnings**: 333

## 2. Exact 5 Phase 8 Failures
1. `backend/tests/test_phase8_execution_closure.py::test_api_missing_capability`
2. `backend/tests/test_phase8_execution_closure.py::test_api_unmapped_capability`
3. `backend/tests/test_phase8_execution_closure.py::test_agent_runtime_unmapped_capability`
4. `backend/tests/test_phase8_execution_closure.py::test_rl_orchestrator_production_mode`
5. `backend/tests/test_phase8_execution_closure.py::test_rl_orchestrator_simulation_mode`

## 3. Current Production Signatures
- `execute_action(action: str, service_id: str)`
- `SafeOrchestrator.__init__(self, env: str = 'dev')`
- `AgentRuntime.__init__(self, env: str = 'dev', agent_id: Optional[str] = None, loop_interval: float = 5.0, decision_provider: Optional[DecisionProvider] = None)`
- `HTTPDecisionProvider.__init__(self, endpoint_url: str = None, timeout: float = 2.0)` (Requires `PRAVAH_MAIN_API` env var if `endpoint_url` is not provided)

## 4. Git-History Evidence
A search of the history (via python parsing of `git log -p --all`) reveals that the signatures for `execute_action`, `SafeOrchestrator`, and `AgentRuntime` were consolidated into their current forms as part of a major monorepo consolidation commit (`2b6b6ff feat: consolidate Pravah subprojects into monorepo...`). The API drift represents a structural tightening of security interfaces in the unified repo.

## 5. Caller/Call-Site Evidence
- **`execute_action`**: Called internally by `/control-plane/runtime-ingest` in `main.py`. The `requested_capability` argument has been structurally removed. Inside `execute_action`, the capability is hardcoded to `"governed-execution"`. This eliminates caller-controlled capability spoofing.
- **`SafeOrchestrator`**: Derives execution privileges entirely from the `env` parameter (`prod` vs `stage` vs `dev`), rather than a caller-supplied `execution_mode` flag.
- **`AgentRuntime`**: Supports dependency injection via `decision_provider`. `test_phase6_vm_deployment.py` contains the established testing pattern: `AgentRuntime(env="dev", agent_id="agent-t6", decision_provider=_DP())`.

## 6. Individual Test Analysis

### A. `test_api_missing_capability`
- **TEST**: Verifies that the API blocks execution if `requested_capability` is missing.
- **EXPECTED**: API blocks the request.
- **ACTUAL**: `TypeError: execute_action() got an unexpected keyword argument 'requested_capability'`.
- **CURRENT PRODUCTION API**: `execute_action(action, service_id)`
- **WHY FAILURE OCCURS**: The argument was removed.
- **IS TEST EXPECTATION OBSOLETE?**: Yes. The caller can no longer omit or supply capabilities; the API dictates the capability internally.
- **IS PRODUCTION BEHAVIOR CORRECT?**: Yes. Hardcoding the capability prevents caller spoofing.
- **EVIDENCE**: `main.py:616` -> `auth_payload = authorize_execution(capability_id="governed-execution", action=action)`

### B. `test_api_unmapped_capability`
- **TEST**: Verifies that the API blocks execution if `requested_capability` is an unmapped value.
- **EXPECTED**: API blocks the request.
- **ACTUAL**: `TypeError: execute_action() got an unexpected keyword argument 'requested_capability'`.
- **CURRENT PRODUCTION API**: `execute_action(action, service_id)`
- **WHY FAILURE OCCURS**: The argument was removed.
- **IS TEST EXPECTATION OBSOLETE?**: Yes, same reason as above.
- **IS PRODUCTION BEHAVIOR CORRECT?**: Yes, security bounds are tighter.
- **EVIDENCE**: See above.

### C. `test_agent_runtime_unmapped_capability`
- **TEST**: Verifies that `AgentRuntime` blocks state-changing actions when the capability is unmapped.
- **EXPECTED**: Action blocked by runtime governance.
- **ACTUAL**: `agent_runtime.ConfigurationError: PRAVAH_MAIN_API is required...`
- **CURRENT PRODUCTION API**: `AgentRuntime.__init__` instantiates `HTTPDecisionProvider` by default.
- **WHY FAILURE OCCURS**: The test constructs `AgentRuntime()` without a mocked decision provider.
- **IS TEST EXPECTATION OBSOLETE?**: No, the runtime must still block unmapped actions, but the test setup is flawed for the current API.
- **IS PRODUCTION BEHAVIOR CORRECT?**: Yes.
- **EVIDENCE**: `test_phase6_vm_deployment.py` demonstrates successful dependency injection `decision_provider=_DP()`.

### D. `test_rl_orchestrator_production_mode` / `test_rl_orchestrator_simulation_mode`
- **TEST**: Verifies `SafeOrchestrator` behavior changes based on `execution_mode="production"` vs `"simulation"`.
- **EXPECTED**: Production blocks state changes; Simulation permits them.
- **ACTUAL**: `TypeError: SafeOrchestrator.__init__() got an unexpected keyword argument 'execution_mode'`.
- **CURRENT PRODUCTION API**: `SafeOrchestrator(env="prod")`
- **WHY FAILURE OCCURS**: `execution_mode` was removed.
- **IS TEST EXPECTATION OBSOLETE?**: Yes, the configuration mechanism changed to environment-bound rules.
- **IS PRODUCTION BEHAVIOR CORRECT?**: Yes, binding safety logic to the immutable environment string rather than a caller flag is a stronger security invariant.
- **EVIDENCE**: `rl_orchestrator_safe.py:36` -> `self.safety_rules = {'prod': ['noop', 'restart'], ...}`.

## 7. Security Implications
- **Can a caller choose an arbitrary capability?** No, hardcoded in the handler.
- **Can a caller choose execution mode?** No, bound to `env`.
- **Can a caller bypass Decision Brain routing?** No.
- **Can an invalid capability reach the executor?** No.
- **Does the test exercise the real production authorization path?** The modified tests will exercise the exact bounds enforced by production logic.

## 8. Classification for Each Failure
1. `test_api_missing_capability` -> TEST DEFECT (API MIGRATION)
2. `test_api_unmapped_capability` -> TEST DEFECT (API MIGRATION)
3. `test_agent_runtime_unmapped_capability` -> TEST DEFECT (ENVIRONMENT CONFIGURATION / TEST ARCHITECTURE)
4. `test_rl_orchestrator_production_mode` -> TEST DEFECT (API MIGRATION)
5. `test_rl_orchestrator_simulation_mode` -> TEST DEFECT (API MIGRATION)

**Conclusion:** 0 Production Defects. All failures are due to the test suite trailing behind a deliberate, security-tightening API consolidation.

## 9. Recommended Remediation
- **`test_api_missing_capability`**: Remove this test entirely (obsolete risk).
- **`test_api_unmapped_capability`**: Rewrite to test integration by temporarily deleting `"governed-execution"` from `VERIFIED_CAPABILITY_MAPPINGS` in the fixture, then asserting `execute_action()` natively rejects it.
- **`test_agent_runtime_unmapped_capability`**: Pass a mock `LocalDecisionProvider` into `AgentRuntime(decision_provider=...)` during instantiation, preventing it from evaluating `PRAVAH_MAIN_API`.
- **`test_rl_orchestrator_production_mode`**: Rewrite to initialize `SafeOrchestrator(env="prod")` and verify `self.safety_rules` enforcement.
- **`test_rl_orchestrator_simulation_mode`**: Rewrite to initialize `SafeOrchestrator(env="dev")` and verify execution is permitted.

## 10. Explicit Statement of What MUST NOT be Changed
- Do NOT restore `requested_capability` to `execute_action`.
- Do NOT restore `execution_mode` to `SafeOrchestrator`.
- Do NOT modify `HTTPDecisionProvider` to ignore missing environment variables in production.
- Do NOT mock `ActionGovernance` boundaries or `authorize_execution` logic when tests are intended to validate those boundaries.

## 11. Evidence No Files Were Modified
Running `git diff -- backend/control_plane/backend/app/main.py backend/agent_runtime.py backend/control_plane/core/rl_orchestrator_safe.py` yields zero output. No tests were modified during this step.
