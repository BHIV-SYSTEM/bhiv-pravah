# TASK 4.3.8 — FAILURE CLASSIFICATION REVIEW

## 1. Baseline
Running `pytest -q` perfectly reproduces the expected outcome:
- **Collected**: 216
- **Passed**: 202
- **Failed**: 14
- **Errors**: 0

## 2. Phase 5 / Adversarial Review (Security Tests)
- **What is tested**: Deterministic recovery, sequence continuity, corruption detection, and hash-chain validation.
- **Is signature validation the STATED invariant?**: No, the tests target hash chains and state snapshot determinism.
- **Does it intentionally construct unsigned events?**: Yes, it uses `journal.append(...)` which does not generate or attach RSA signatures.
- **Does production legitimately require signed events?**: Yes. The `RecoveryValidator` enforces `LineageVerifier.verify_lineage_signatures(journal_events)` to prevent malicious boot-time state injections.
- **Would mocking LineageVerifier weaken security?**: Yes, modifying the test to mock `LineageVerifier` would bypass a real security layer inside a security-focused test suite.
- **Can it be corrected safely?**: Yes, by updating the test's `_fake_ready_startup` or test setup logic to generate cryptographically valid signatures for the mock events, preserving the strict validation boundary.
- **Final Determination**: **SAFE TO UPDATE TEST FIXTURES**

## 3. Phase 8 Review (API Drift)
- **When/Why API changed**: 
  - `execute_action()`: Changed in Task 4.3 to strip `requested_capability` from caller control, hardcoding authorization to eliminate capability-spoofing vectors.
  - `SafeOrchestrator.__init__()`: Changed previously to remove `execution_mode`, ensuring the RL orchestrator uses environment-bound security rather than caller-overridable modes.
  - `AgentRuntime`: Changed to strictly require `PRAVAH_MAIN_API` for secure decision routing.
- **Is old API obsolete?**: Yes. The compatibility contract does not require these obsolete parameters; they were removed precisely because they were security liabilities.
- **Would test update preserve intent?**: Yes. The tests' intent (e.g., verifying capability rejection or runtime configuration) can be cleanly expressed with the modern signatures.

## 4. Phase 15 Review (Patching & Namespace)
- **Why it passes locally but fails globally**: The `backend/tests/` directory lacks an `__init__.py`. When `pytest` collects the entire `pravah-bhiv/` root, `backend` acts as a top-level package, but `tests` does not register as a sub-module of `backend`. Thus, `patch("backend.tests.test_phase15_gap_governed_abstention...")` fails with `AttributeError: module 'backend' has no attribute 'tests'`. 
- **When run locally**: Pytest dynamically alters `sys.path` and/or module naming, allowing the relative resolution to occasionally succeed depending on the exact invocation.
- **Determination**: **NAMESPACE/PACKAGE-LAYOUT DEFECT**. This is a pure test isolation/configuration defect, unrelated to production governance logic.

## 5. Group 1 Review (Observation Test)
- **Registry State**: `"status": "DOCUMENTED"`, `"endpoint": null`, `"live_endpoint_available": false`, `"deployment_status": "PENDING"`.
- **Test Expectation**: Asserts the endpoint is non-null and performs a live health check.
- **Test Intent**: Live deployment health check / readiness gate.
- **Meaning of `endpoint=null`**: The registry legitimately acknowledges that the Postgres/PostGIS API deployment is pending in the shared environment.
- **Skipping consequence**: Skipping would correctly match the documented registry state. It would not hide an unexpected deployment gap.
- **Determination**: **TEST CORRECT — ENVIRONMENT NOT READY**

## 6. Verification of "0 Production Defects" Claim
**Verified.** Every failure represents a test that is out of synchronization with the modern production security boundary:
- Phase 5/Adversarial fail because production properly rejects their unsigned synthetic inputs.
- Phase 8 fails because production removed caller-overridable security parameters (kwargs).
- Phase 15 fails because of python module layout (`__init__.py` absence) affecting `unittest.mock.patch`.
- Group 1 fails because it tests for a live endpoint that the registry correctly marks as `PENDING`.
No failure demonstrates a regression in operational contracts.

## 7. Review of Recommended Remediations
- **4.3.8 (Phase 8 test updates)**: **APPROVE**. The API drift is intentional and security-critical. Tests must be updated to use the modern signatures.
- **4.3.9 (Phase 15 patch/import fix)**: **APPROVE**. Adding `__init__.py` or correcting the `patch` string target resolves the pytest collection inconsistency without altering governance logic.
- **4.3.10 (Phase 5 / Adversarial Fix)**: **REJECT** the strategy of mocking `LineageVerifier`. **APPROVE** the strategy of generating valid cryptographic signatures for the test fixtures. We must not weaken the security test to obtain a pass.
- **4.3.11 (Group 1 test skip)**: **APPROVE**. The test explicitly checks a live endpoint that is not yet hosted. It should be skipped or marked `xfail` conditionally based on the registry's `live_endpoint_available` flag.

## 8. Summary Table

| # | Test | Original Classification | Validated Classification | Evidence | Remediation |
|---|------|--------------------------|---------------------------|----------|-------------|
| 1 | `test_recovery_has_no_drift` | Stale/API Drift | Stale Test Fixtures | `assert False is True` (LineageVerifier rejects unsigned mock events) | Generate signed mock events |
| 2 | `test_group1_observation_api...` | Env/Configuration | Env Not Ready | `cap.get("endpoint")` is null (Registry dictates `PENDING`) | Skip until `live_endpoint_available` is true |
| 3 | `test_governance_allows_noop...` | Test Defect (Isolation) | Namespace Defect | `AttributeError: module 'backend' has no attribute 'tests'` | Fix `patch` target / Add `__init__.py` |
| 4 | `test_full_gap_flow_no_op...` | Test Defect (Isolation) | Namespace Defect | `AttributeError: module 'backend' has no attribute 'tests'` | Fix `patch` target / Add `__init__.py` |
| 5 | `test_abstention_evidence_wr...` | Test Defect (Isolation) | Namespace Defect | `AttributeError: module 'backend' has no attribute 'tests'` | Fix `patch` target / Add `__init__.py` |
| 6 | `test_recovery_validator_val...` | Stale/API Drift | Stale Test Fixtures | `failures=['hash_verification_failed:HASH_CHAIN']` | Generate signed mock events |
| 7 | `test_healthcheck_replay_wr...` | Stale/API Drift | Stale Test Fixtures | `failures=['hash_verification_failed:HASH_CHAIN']` | Generate signed mock events |
| 8 | `test_restart_rebuild_preser...`| Stale/API Drift | Stale Test Fixtures | `failures=['hash_verification_failed:HASH_CHAIN']` | Generate signed mock events |
| 9 | `test_recovery_fails_on_corr...`| Stale/API Drift | Stale Test Fixtures | Strict hash check masks test's corruption check | Generate signed mock events |
| 10 | `test_api_missing_capability` | Stale/API Drift | API Obsolete | `TypeError: unexpected keyword argument 'requested_capability'` | Update test to use modern API |
| 11 | `test_api_unmapped_capability` | Stale/API Drift | API Obsolete | `TypeError: unexpected keyword argument 'requested_capability'` | Update test to use modern API |
| 12 | `test_agent_runtime_unmapped...`| Env/Configuration | Environment Missing | `ConfigurationError: PRAVAH_MAIN_API is required` | Mock or set `PRAVAH_MAIN_API` in test |
| 13 | `test_rl_orchestrator_prod...` | Stale/API Drift | API Obsolete | `TypeError: unexpected keyword argument 'execution_mode'` | Update test to use modern API |
| 14 | `test_rl_orchestrator_sim...` | Stale/API Drift | API Obsolete | `TypeError: unexpected keyword argument 'execution_mode'` | Update test to use modern API |
