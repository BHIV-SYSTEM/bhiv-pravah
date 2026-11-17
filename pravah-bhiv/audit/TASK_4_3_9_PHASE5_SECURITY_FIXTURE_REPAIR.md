# TASK 4.3.9 — PHASE 5 SECURITY FIXTURE REPAIR

## 1. Baseline Phase 5 Result
Running `pytest backend/tests/test_phase5_deployment_validators.py -q` before changes yielded:
- **Collected**: 7
- **Passed**: 3
- **Failed**: 4 (`test_recovery_validator_validates_restart_determinism`, `test_healthcheck_replay_wraps_recovery_result`, `test_restart_rebuild_preserves_state`, `test_recovery_fails_on_corrupted_journal`)

## 2. Exact Original Fixture Problem
The tests injected synthetic mock events directly into the append-only journal (`journal.append("exec123", "e1", "CREATED", ...)`). Because these mock events were unsigned, they failed the strict cryptographic signature checks required by production.

## 3. Exact Production Security Invariant Enforced
The `RecoveryValidator` enforces `LineageVerifier.verify_lineage_signatures(journal_events)`. This requires every event's `details["signature"]` to contain a valid HMAC-SHA256 signature generated over a specific canonical `trace_material` dictionary. Unsigned events automatically trigger `hash_verification_failed:HASH_CHAIN`.

## 4. Real Signing Implementation Used
We analyzed `backend/security/lineage_verifier.py` and `backend/security/signed_trace.py` and used the real production signing mechanism: `sign_trace(canonicalize(trace_material))` powered by `LINEAGE_SIGNING_KEY`.

## 5. Construction of Valid Signed Fixtures
A local helper function `_append_signed` was implemented directly inside the test files. It intercepts the event properties, computes the canonical `trace_material` exactly as production expects, signs it, and passes the resulting signature natively into `journal.append(..., details={"signature": sig})`.

## 6. Tests Modified
- `backend/tests/test_phase5_deployment_validators.py`
- `backend/tests/adversarial_test_suite/test_deterministic_recovery.py`

## 7. Preservation of Original Test Intent
- For standard determinism and rebuild tests, the valid signatures satisfy the boot-time verifier, allowing the original sequence and state-hash logic to execute and pass flawlessly. No assertions were altered.
- For `test_recovery_fails_on_corrupted_journal`, the test intentionally simulates hash-chain corruption. The test was modified to corrupt the `event_hash` AND cryptographically re-sign the event. This prevents the test from failing trivially at the initial signature check, forcing the execution to proceed to the hash-chain assembly where it triggers the intended `state_hash_mismatch`.

## 8. Evidence LineageVerifier was NOT Mocked
The `_fake_ready_startup` monkeypatching logic remains exactly as it was. No new `patch` or `monkeypatch` directives were added to bypass `LineageVerifier.verify_event_signature`. The verifier legitimately passes because the signatures are real.

## 9. Evidence Production Code was NOT Modified
`git diff -- backend/control_plane/deployment/recovery_validator.py` and `git diff -- backend/security/` returned zero output. The only production diffs present in the tree correspond to `main.py` and `execution_rights_adapter.py` modified during the prior Task 4.3 authorization remediation.

## 10. Targeted Phase 5 Result
Running `pytest backend/tests/test_phase5_deployment_validators.py -q` post-remediation yields:
- **Passed**: 7
- **Failed**: 0

## 11. Relevant Adversarial Result
Running `pytest backend/tests/adversarial_test_suite/test_deterministic_recovery.py -q` yields:
- **Passed**: 1
- **Failed**: 0

## 12. Full Pytest Result
Running `pytest -q` on the full suite post-remediation yields:
- **Collected**: 216
- **Passed**: 207 (Up from 202)
- **Failed**: 9 (Down from 14)
- **Errors**: 0

## 13. Remaining Failures
The remaining 9 failures precisely match the documented defects from Task 4.3.8:
- **Phase 8 (5 failures)**: Stale APIs (`requested_capability`, `execution_mode`, missing `PRAVAH_MAIN_API`).
- **Phase 15 (3 failures)**: Test isolation namespace defect (`__init__.py` missing).
- **Group 1 (1 failure)**: Tests for live observation endpoint that the registry correctly dictates is `PENDING`.

## 14. Git Diff Summary
The intentional source changes executed by this task were restricted entirely to:
- `M backend/tests/test_phase5_deployment_validators.py`
- `M backend/tests/adversarial_test_suite/test_deterministic_recovery.py`
*(Note: Some runtime logs and nonce stores reflect typical state transitions from executing the test suite.)*
