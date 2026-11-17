# TASK 4.3.7 — REMAINING FAILURE FORENSICS

## 1. Exact Baseline
Running `pytest -q` locally from the repository root produced the following collection and execution counts:
- **Total Collected**: 216
- **Passed**: 202
- **Failed**: 14
- **Errors**: 0 (Collection is fully repaired)

## 2. All 14 Failures
1. `backend/tests/adversarial_test_suite/test_deterministic_recovery.py::test_recovery_has_no_drift`
2. `backend/tests/test_phase10_group1_integration.py::test_group1_observation_api_live_health`
3. `backend/tests/test_phase15_gap_governed_abstention.py::test_governance_allows_noop_contract`
4. `backend/tests/test_phase15_gap_governed_abstention.py::test_full_gap_flow_no_operational_execution`
5. `backend/tests/test_phase15_gap_governed_abstention.py::test_abstention_evidence_written_to_ledger`
6. `backend/tests/test_phase5_deployment_validators.py::test_recovery_validator_validates_restart_determinism`
7. `backend/tests/test_phase5_deployment_validators.py::test_healthcheck_replay_wraps_recovery_result`
8. `backend/tests/test_phase5_deployment_validators.py::test_restart_rebuild_preserves_state`
9. `backend/tests/test_phase5_deployment_validators.py::test_recovery_fails_on_corrupted_journal`
10. `backend/tests/test_phase8_execution_closure.py::test_api_missing_capability`
11. `backend/tests/test_phase8_execution_closure.py::test_api_unmapped_capability`
12. `backend/tests/test_phase8_execution_closure.py::test_agent_runtime_unmapped_capability`
13. `backend/tests/test_phase8_execution_closure.py::test_rl_orchestrator_production_mode`
14. `backend/tests/test_phase8_execution_closure.py::test_rl_orchestrator_simulation_mode`

## 3. Phase 5 Analysis (Deployment Validators)
- **Exact production function involved**: `RecoveryValidator.validate` located in `backend/control_plane/deployment/recovery_validator.py`.
- **Expected contract**: Validates boot-time recovery by verifying the journal's monotonic sequence, hash chain continuity, cryptographic signatures, and execution determinism.
- **Actual behavior**: Verification correctly fails and returns `hash_verification_failed:HASH_CHAIN`.
- **Why test fails**: The test generates mock `ExecutionEvent` records and manually appends them using `journal.append(...)`. These mock events bypass proper cryptographic generation and lack valid lineage signatures.
- **Test expectation vs Architecture**: The current architecture strictly enforces `LineageVerifier.verify_lineage_signatures(journal_events)` (line 68). The test expectation is stale as it does not supply cryptographically signed mock events.
- **Production incomplete**: No. The production code correctly denies admission to unsigned/forged events.

## 4. Phase 8 Analysis (Execution Closure)
- **Exact production component**: `execute_action()` in `backend/control_plane/backend/app/main.py`, `AgentRuntime` in `backend/agent_runtime.py`, and `SafeOrchestrator` in `backend/control_plane/core/rl_orchestrator_safe.py`.
- **Expected contract**: Block unauthorized state changes and securely route execution requests.
- **Actual implementation**: `execute_action()` now strictly takes `(action: str, service_id: str)` because capability inference was internalized in Task 4.3. `SafeOrchestrator.__init__` strictly takes `(env: str)`. `AgentRuntime` natively relies on `PRAVAH_MAIN_API`.
- **Why test fails**: 
  - `test_api_*` injects an obsolete `requested_capability` kwarg (`TypeError`).
  - `test_rl_orchestrator_*` injects an obsolete `execution_mode` kwarg (`TypeError`).
  - `test_agent_runtime_*` fails to mock the environment variable `PRAVAH_MAIN_API` (`ConfigurationError`).
- **Production incomplete**: No.
- **Test uses stale API**: Yes, entirely. The tests are calling signatures that were refactored for security and closure.

## 5. Phase 15 Analysis (Governed Abstention)
- **Exact production implementation**: `ActionGovernance.evaluate_contract()`.
- **Expected governance behavior**: Governance should intercept unapproved operational actions, produce NOOP contracts (abstentions), and write to the ledger.
- **Why test fails**: The tests fail *only* during the global `pytest -q` suite with an `AttributeError: module 'backend' has no attribute 'tests'`. They **PASS** when run individually.
- **Persistence interaction**: Working normally (30/30 tests pass locally).
- **Test expectation vs Architecture**: The test expects to mock `backend.tests.test_phase15_gap_governed_abstention.ActionGovernance`. However, because `backend/tests` lacks an `__init__.py`, pytest treats `backend` as a top-level module during global collection and fails the `unittest.mock.patch` lookup.
- **Production incomplete**: No. This is a fragile testing path/isolation issue.

## 6. Group 1 / Observation Failure
- **Expected payload/schema**: Test asserts `endpoint is not None`.
- **Actual producer payload**: The capability registry (`group1-observation-api.json`) explicitly dictates `"status": "DOCUMENTED"` and `"endpoint": null`, along with `"live_endpoint_available": false`.
- **Actual consumer contract**: The test consumes the capability ID and verifies live health.
- **Schema drift**: The environment is genuinely NOT deployed (status is PENDING). The registry faithfully reports this. 
- **Ownership**: The test asserts a future, operational state that contradicts the registry schema.

## 7. Adversarial Analysis (Deterministic Recovery)
- **Exact security invariant**: Execution determinism and trace lineage must remain un-drifted on recovery.
- **Test setup**: Like Phase 5, it injects synthetic mock events into the append-only journal.
- **Production implementation**: `RecoveryValidator` enforces `LineageVerifier`.
- **Genuine defect?**: No. It proves the invariant is so robust that it catches the test's artificial forgery attempt because it lacks cryptographic signatures.
- **Stale test?**: Yes. Mock events must be properly signed to pass the modern validator.

## 8. Test Quality Audit
Every failed test bypasses the production path it claims to validate, or uses a stale API.
- **Phase 5/Adversarial**: Injects fake contracts lacking cryptographic signatures.
- **Phase 8**: Uses stale APIs and improper environment mocks.
- **Phase 15**: Patches absolute path strings globally that break without namespace `__init__.py`.
- **Group 1**: Expects a state that the local registry explicitly marks as unhosted.

## 9. Compared with Passed Tests
When `test_phase15_gap_governed_abstention.py` is executed locally:
`pytest backend/tests/test_phase15_gap_governed_abstention.py`
All 30 tests pass, confirming the NOOP contract logic is fully operational. The 3 global failures are exclusively a patching conflict.

## 10. Production Code Evidence (Git Diff)
The only production files containing modifications are from the authorized Task 4.3 run:
- `M backend/control_plane/backend/app/main.py`
- `M backend/control_plane/capabilities/execution_rights_adapter.py`
**No other production code has been modified.**

## 11. Final Classification Table

| # | Test | Classification | Production Defect? | Test Defect? | Evidence |
|---|------|----------------|--------------------|--------------|----------|
| 1 | `test_recovery_has_no_drift` | Stale/API Drift | No | Yes | `assert False is True` (LineageVerifier rejects unsigned mock events) |
| 2 | `test_group1_observation_api_live_health` | Env/Configuration | No | Yes | `cap.get("endpoint")` is null (Registry dictates `PENDING`) |
| 3 | `test_governance_allows_noop_contract` | Test Defect (Isolation) | No | Yes | `AttributeError: module 'backend' has no attribute 'tests'` |
| 4 | `test_full_gap_flow_no_operational_execution`| Test Defect (Isolation) | No | Yes | `AttributeError: module 'backend' has no attribute 'tests'` |
| 5 | `test_abstention_evidence_written_to_ledger` | Test Defect (Isolation) | No | Yes | `AttributeError: module 'backend' has no attribute 'tests'` |
| 6 | `test_recovery_validator_validates_restart_determinism`| Stale/API Drift | No | Yes | `failures=['hash_verification_failed:HASH_CHAIN']` |
| 7 | `test_healthcheck_replay_wraps_recovery_result`| Stale/API Drift | No | Yes | `failures=['hash_verification_failed:HASH_CHAIN']` |
| 8 | `test_restart_rebuild_preserves_state` | Stale/API Drift | No | Yes | `failures=['hash_verification_failed:HASH_CHAIN']` |
| 9 | `test_recovery_fails_on_corrupted_journal` | Stale/API Drift | No | Yes | Strict hash check occurs before test's corruption check |
| 10 | `test_api_missing_capability` | Stale/API Drift | No | Yes | `TypeError: unexpected keyword argument 'requested_capability'` |
| 11 | `test_api_unmapped_capability` | Stale/API Drift | No | Yes | `TypeError: unexpected keyword argument 'requested_capability'` |
| 12 | `test_agent_runtime_unmapped_capability` | Env/Configuration | No | Yes | `ConfigurationError: PRAVAH_MAIN_API is required` |
| 13 | `test_rl_orchestrator_production_mode` | Stale/API Drift | No | Yes | `TypeError: unexpected keyword argument 'execution_mode'` |
| 14 | `test_rl_orchestrator_simulation_mode` | Stale/API Drift | No | Yes | `TypeError: unexpected keyword argument 'execution_mode'` |

## 12. Recommended Remediation Tasks
1. **Task 4.3.8:** Update Phase 8 tests to reflect the modern kwargs for `execute_action()` and `SafeOrchestrator()`, and mock `PRAVAH_MAIN_API`.
2. **Task 4.3.9:** Add `__init__.py` to `backend/tests/` or refactor Phase 15 tests to patch the targeted module without relying on the absolute path string.
3. **Task 4.3.10:** Inject valid signatures or mock `LineageVerifier` in Phase 5 and Adversarial test suites to pass the newly enforced cryptographic validation.
4. **Task 4.3.11:** Skip `test_group1_observation_api_live_health` if the environment is documented as `PENDING`.
