# State Semantics Contract (Phase 8)

This contract defines the canonical state vocabulary, semantic ownership bounds, and cross-service dispute resolutions for the Pravah control plane.

---

## 1. Single Canonical State Vocabulary

All modules, services, and replayers within the Pravah ecosystem must strictly adhere to the single canonical state definitions.

### A. Execution States
As defined in the canonical system contract:
* **`CREATED`**: Initial lifecycle state. Lineage and parameters registered.
* **`APPROVED`**: Governance validated and signature verified. Eligible for execution.
* **`EXECUTING`**: Dispatched to the container executor layer and actively running.
* **`COMPLETED`**: Terminal success. Transition outcomes verified.
* **`FAILED`**: Terminal failure. Aborted path logged.

### B. Legitimacy States
As defined in [degraded_runtime_doctrine.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/proofs/phase8/degraded_runtime_doctrine.md):
* **`LEGITIMATE_VALID`**: Valid cryptographic, schema, and dependency state.
* **`LEGITIMATE_DEGRADED`**: Operational loop running in secondary dependency fallback.
* **`LEGITIMATE_AMBIGUOUS`**: Lineage dispute, validation mismatches, or structural index failures.
* **`ILLEGITIMATE`**: Signature verification failure, timestamp clock skew, or tampered payload.

---

## 2. No Alias Dependency

* **Lock Rule**: Aliases, mapping keys, and translated states are strictly prohibited. State transitions must evaluate using the exact literals defined above.
* **Prohibited State Aliases**: The literal `EXECUTED` is an invalid state representation. Any execution, telemetry payload, or lineage event carrying the `EXECUTED` status is strictly invalid, rejected, and blocked by verification gates.

---

## 3. Semantic Ownership

* **Owner of Semantics**: The constitutional schema definition [execution_state.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/contracts/execution_state.py) holds canonical ownership of the state vocabulary.
* **No Runtime Modification**: The runtime, dashboards, and API engines hold **zero authority** to define, inject, or edit state semantics. Any change requires a policy version update.

---

## 4. Cross-Service Semantic Conflict Handling

If a microservice attempts to execute or verify using a non-canonical state value (e.g. `EXECUTED`, `DEPLOYED`, or `HEALTHY`), the following rules apply:
1. **Intake Validation Refusal**: The schema checks in [input_validator.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/core/input_validator.py) block the call with a `400 Bad Request`.
2. **Transition Halt**: [SemanticGuardEngine](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L155) throws a `ValueError` for unknown transitions, halting the orchestrator cycle.
3. **Execution Block**: The [executer app.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/reliability-controller2-main/executer/app.py) checks the `action` and `state` payload, rejecting non-contract states.
