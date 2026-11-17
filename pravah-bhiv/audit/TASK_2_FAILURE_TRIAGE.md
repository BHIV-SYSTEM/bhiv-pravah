# Pravah Enterprise Codebase Audit: Task 2 Failure Triage

This document provides a comprehensive root-cause analysis and classification for the 15 existing test failures in the `pravah-bhiv` repository. The test suite baseline is 216 tests collected, with 201 passing and 15 failing.

The investigation was performed strictly as an audit without modifying production code, weakening assertions, or bypassing real implementations.

## Overview of Failures

Total Failures: 15

| Classification | Count |
| :--- | :--- |
| **B. TEST BUG** / **C. STALE/LEGACY TEST** | 13 |
| **D. ENVIRONMENT/CONFIGURATION ISSUE** | 1 |
| **E. EXTERNAL DEPENDENCY ISSUE** / **F. EXPECTED FAILURE** | 1 |
| **A. REAL PRODUCTION BUG** | 0 |

---

## 1. Confirmed Test Bugs & Stale Tests (13 Failures)

These tests fail due to outdated signatures, improper mocking, or injecting invalid data that violates internal system contracts.

### 1.1 State Hash Mismatches (Phase 5 & 6)
**Tests:**
- `backend/tests/adversarial_test_suite/test_deterministic_recovery.py::test_recovery_has_no_drift`
- `backend/tests/test_phase5_deployment_validators.py::test_recovery_validator_validates_restart_determinism`
- `backend/tests/test_phase5_deployment_validators.py::test_healthcheck_replay_wraps_recovery_result`
- `backend/tests/test_phase5_deployment_validators.py::test_restart_rebuild_preserves_state`
- `backend/tests/test_phase5_deployment_validators.py::test_recovery_fails_on_corrupted_journal`

**Root Cause:**
These tests manually inject events into the `AppendOnlyLog` mock using hardcoded string values for `previous_hash` (e.g., `""`, `"h1"`, `"h2"`) and `sequence_hash` instead of computing valid cryptographic hashes. When the `HashLineageVerifier` (via `RecoveryValidator`) recomputes the state hash from the sequence, it does not match the mocked snapshot hashes. This is a **STALE/LEGACY TEST** issue where the test setup does not respect the stricter validation logic introduced in the production lineage verifier.

### 1.2 Stale Method Signatures (Phase 8)
**Tests:**
- `backend/tests/test_phase8_execution_closure.py::test_api_missing_capability`
- `backend/tests/test_phase8_execution_closure.py::test_api_unmapped_capability`
- `backend/tests/test_phase8_execution_closure.py::test_rl_orchestrator_production_mode`
- `backend/tests/test_phase8_execution_closure.py::test_rl_orchestrator_simulation_mode`

**Root Cause:**
These tests fail with `TypeError: got an unexpected keyword argument`.
- `execute_action()` in `backend.app.main` now only accepts `action` and `service_id`. The tests pass a deprecated `requested_capability` argument.
- `SafeOrchestrator.__init__()` in `rl_orchestrator_safe.py` no longer accepts the `execution_mode` keyword argument (it only accepts `env='dev'`). The tests attempt to instantiate it with `execution_mode="production"`.
This is a clear **STALE TEST / TEST BUG** due to API drift.

### 1.3 Improper Patch Paths (Phase 15)
**Tests:**
- `backend/tests/test_phase15_gap_governed_abstention.py::test_governance_allows_noop_contract`
- `backend/tests/test_phase15_gap_governed_abstention.py::test_full_gap_flow_no_operational_execution`
- `backend/tests/test_phase15_gap_governed_abstention.py::test_abstention_evidence_written_to_ledger`

**Root Cause:**
These tests attempt to patch `ActionGovernance.evaluate_contract` using the path `"backend.tests.test_phase15_gap_governed_abstention.ActionGovernance.evaluate_contract"`. Because they patch the class reference *inside the test module* instead of the module under test, the mock is not applied where the code actually executes, causing the real governance evaluation to run and raise unexpected errors/block decisions. This is a standard **TEST BUG** related to incorrect `unittest.mock.patch` usage.

### 1.4 Global Mock Leak (Unified Discovery)
**Test:**
- `backend/tests/test_unified_discovery.py::test_unified_discovery`

**Root Cause:**
This test passes when run in isolation, but fails in the suite with an assertion error (`AssertionError: Entity list should contain all capabilities`).
The root cause is a global mock leak from `test_phase15_gap_governed_abstention.py`. At the top of `test_phase15`, the file does:
```python
import control_plane.multi_app_control_plane
control_plane.multi_app_control_plane.MultiAppControlPlane = MagicMock()
```
Because this patch is applied globally at the module level (outside of a test case or context manager), it permanently replaces `MultiAppControlPlane` with a mock for all tests that run afterward. When `test_unified_discovery.py` runs, `cp.list_runtime_entities()` returns a mock object instead of the actual list of capabilities, causing the length assertion to fail. This is a **TEST BUG (Mock Leak)**.

---

## 2. Environment & Configuration Issues (1 Failure)

**Test:**
- `backend/tests/test_phase8_execution_closure.py::test_agent_runtime_unmapped_capability`

**Root Cause:**
The test initializes `AgentRuntime()`. By default, `AgentRuntime` falls back to `HTTPDecisionProvider()`, which requires the `PRAVAH_MAIN_API` environment variable to be set. Since the test does not mock the decision provider or set the required environment variable, it raises `ConfigurationError: PRAVAH_MAIN_API is required`.
**Classification: D. ENVIRONMENT/CONFIGURATION ISSUE**. The test needs a mock decision provider or the correct environment variables injected for test context.

---

## 3. External Resource Dependencies (1 Failure)

**Test:**
- `backend/tests/test_phase10_group1_integration.py::test_group1_observation_api_live_health`

**Root Cause:**
This test reads the capability registry for `group1-observation-api` and attempts to perform a live HTTP health check against its documented endpoint.
However, in the current capability registry (`group1-observation-api.json`), the `endpoint` is explicitly defined as `null` and `live_endpoint_available` is `false`. The test fails immediately when attempting to extract a `None` endpoint.
**Classification: E. EXTERNAL DEPENDENCY ISSUE / F. EXPECTED/INTENTIONAL FAILURE**. The test expects a live staging/prod environment where this dependent API is deployed, which is intentionally not present in the current sandbox.

---

## Maintenance Heaviness & Recommendation

No real production bugs were identified in the application logic. All 15 failures are artifacts of the testing framework, API evolution, mock leakage, or intentional integration boundaries.

**Next Steps for Remediation (When Authorized):**
1. Fix the global module patch in `test_phase15` by using a `@patch` decorator or `patch()` context manager.
2. Update the `SafeOrchestrator` and `execute_action` test calls to match their current production signatures.
3. Replace hardcoded `"h1"`, `"h2"` hashes in the `AppendOnlyLog` mocks with dynamically computed sequence hashes using `HashLineageVerifier` in Phase 5 and Phase 6 tests.
4. Mock the `decision_provider` when instantiating `AgentRuntime` in the Phase 8 test.
5. Skip or mock the live network call in the Phase 10 integration test when `endpoint` is `null`.
