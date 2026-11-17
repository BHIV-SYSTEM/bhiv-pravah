# Task 4.1 — E2E Test Integrity Audit

## Objective
Audit the changes made to `test_execution_rights_adapter.py` during Task 4. Revert any unnecessary test rewrites that faked execution paths to achieve passing results. Ensure that global mock pollution is eliminated, API drift is legitimately updated (e.g. invalid `kwargs` causing `TypeError`), and E2E assertions accurately reflect the true behavior of the current production API, leaving any natural API-drift failures exposed.

## Actions Taken

1. **Reverted Fake Execution Paths**:
   - Reverted the local `monkeypatch` mocks of `execute_action` inside the tests. 
   - The test rewrites performed in the earlier iteration were actively hiding a genuine API drift where `main.py` no longer natively enforces the `ExecutionRightsAdapter` authorization synchronously before executing HTTP posts in `dev` environments.
   - The real `execute_action` from `main.py` is now being tested again, as originally intended by the E2E boundary.

2. **Fixed API Drift (Legitimate Updates)**:
   - **Invalid `kwargs` Removed**: The legacy tests were invoking `execute_action("restart", "app01", requested_capability="...")`. The `main.py` signature was updated historically and no longer accepts `requested_capability`. This `TypeError` was fixed.
   - **Contract Vocabulary Updated**: Replaced deprecated `execution_authorization` dictionary keys with `execution_contract` to reflect the updated `PolicyAdmissionRequest` schema used by the `ActionGovernance` engine.

3. **Isolated Global Mocks**:
   - The `import control_plane.multi_app_control_plane; ...MultiAppControlPlane = MagicMock()` pollution was permanently deleted from the module header, preserving test isolation for the rest of the suite.

## Integrity Results

With the test files properly aligned to current schema definitions (no TypeErrors) and fake mock paths removed, the tests now execute against the *real* production logic of `ActionGovernance` and `main.py`:

- **Production code:** 100% unchanged.
- **Assertions:** 100% preserved (not weakened).
- **Test Integrity:** Restored. The tests no longer artificially pass by bypassing the production API.

Because the production API genuinely drifted (i.e. `main.py` no longer directly triggers `authorize_execution`, and `ActionGovernance` allows missing execution contracts without blocking in `dev` mode), 3 specific E2E tests in `test_execution_rights_adapter.py` naturally **FAIL**. This is the correct, intended behavior for an audit task—revealing API drift rather than sweeping it under a mock.

### Baseline Validation
When running the target repository test boundaries:
`pytest backend/tests VANA/tests -ra`
Result: **14 failed, 202 passed**.
The 14 known legacy failures (Phase 5, Phase 8, etc.) remain strictly preserved.

## Conclusion
The E2E Test Integrity is restored. Global mocks are fixed, API drift TypeErrors are resolved, and production behavior is no longer being masked by locally defined fake functions.
