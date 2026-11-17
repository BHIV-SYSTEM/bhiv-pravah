# Task 4.2 — Production E2E Wiring Verification

## Objective
Audit the execution authorization boundary between `ExecutionRightsAdapter`, `main.py`, and `ActionGovernance` to verify whether current tests prove production wiring or falsely claim E2E coverage by manually reconstructing missing wiring within test environments.

## 1. Actual Production Call Graph

Tracing the native, unmodified source code of `backend/control_plane/backend/app/main.py::execute_action()`:

1. **`execute_action(action, service_id)`** is invoked.
2. Instantiates `ActionGovernance(env=env)`.
3. Creates a static `DecisionContract`.
4. Constructs an empty authorization context directly inline:
```python
            context={
                "service_id": service_id,
                "app_name": service_id,
                "env": env,
                "source": "backend_api",
            }
```
5. Calls `governance.evaluate_contract(decision, context)`.
6. Checks `governance_decision.should_block`.
7. Submits `requests.post("http://localhost:5003/execute-action")`.

### Deficiencies in Production Wiring
- **`authorize_execution` is NEVER imported** into `main.py`.
- **`ExecutionRightsAdapter` is NEVER invoked** natively during an API request.
- **`execution_contract` is NEVER constructed** and thus completely absent from the governance context.
- The entire capability discovery and payload signing phase is **bypassed**.

## 2. E2E Test Monkeypatch Analysis

The previous tests claimed to be "E2E" but achieved passing coverage exclusively through aggressive monkeypatching.

**Legacy Monkeypatches:**
- `importlib.reload(adapter_module)`
- `main_module.authorize_execution = adapter_module.authorize_execution`
- Injecting fake functions mimicking the expected behavior of `ActionGovernance`.

**Audit Finding:** The tests were actively repairing the production wiring *inside* the test environment. By artificially binding `authorize_execution` into `main.py`, the tests falsely proved the adapter was integrated. A true E2E test must rely solely on native imports.

## 3. Remediation & Test Reclassification

All monkeypatches rewriting production import paths have been **REMOVED**.

The tests have been accurately reclassified to reflect reality:

### A. Unit Tests (Unchanged)
Tests directly exercising `ExecutionRightsAdapter` isolated functions remain valid unit tests.

### B. Governance / Security Integration
`test_governance_authorization_enforcement_and_forgery`
- **Result:** FAILED. 
- **Reason:** Real `ActionGovernance` explicitly ignores missing execution contracts in dev environments (returns `should_block=False`), exposing that strict E2E cryptographic enforcement is partially offline natively.

### C. True Production E2E / Integration
`test_integration_execute_action_does_not_invoke_adapter` (Formerly `test_true_e2e_integration_proof`)
- **Result:** PASSED.
- **Reason:** Now cleanly proves that the adapter is bypassed. A mock on `authorize_execution` designed to crash the application *is never triggered*, confirming the bypass natively.

`test_integration_execute_action_bypasses_adapter_rejection`
- **Result:** FAILED.
- **Reason:** Asserts that missing capabilities should fail execution. Because `main.py` bypasses the capability check, it attempts to execute natively instead of rejecting it.

## 4. Final Verification

**Full Suite Run:**
`pytest backend/tests VANA/tests -ra`
- **Passed:** 202
- **Failed:** 14 (The exact legacy failures are strictly preserved. The reclassified adapter tests are in a different module and do not pollute this baseline count).

**Module Run:**
`pytest backend/control_plane/capabilities/test_execution_rights_adapter.py -v`
- **Passed:** 21
- **Failed:** 2 (The exact tests that expose the broken production wiring).

**Production Integrity:**
No production source code files (`main.py`, `execution_rights_adapter.py`, `action_governance.py`) were modified during this audit.

## Conclusion & Next Steps
The tests now report the unvarnished truth: `main.py` does not invoke the required authorization path natively. The production wiring is definitively broken. 

**Per the final rule requirement, we must STOP here and report this production wiring gap.** We cannot proceed to the Group 4 Handover Documentation until this is acknowledged.
