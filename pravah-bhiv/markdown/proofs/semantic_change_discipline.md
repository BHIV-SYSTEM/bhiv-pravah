# Semantic Change Discipline (Phase 8)

This document establishes the change control rules, compatibility gates, and deprecation recovery path for modifying state transitions and vocabulary.

---

## 1. Change Control Process

Changes to state semantics or the transition FSM rules are subject to the following discipline:
1. **Proposal of Change**: Proposing a change requires updating the constitutional schema files (`execution_state.py`, `semantic_guard_engine.py`, `semantic_transition_validator.py`).
2. **GC Signature Signing**: The new configuration rules must be signed using active cryptographic governance keys, producing a new GC-approved policy artifact.
3. **Verification Testing**: The adversarial test suite must run and pass against the updated rules.
4. **Active Deployment Phase-In**: The engine loads the new policy, updating the `runtime_policy_version` index.

---

## 2. Compatibility & Deprecation Reconstruction

* **Historical Replay Integrity**: Old lineages written under deprecated state semantics must remain readable and verifiable.
* **Recovery Rule**: The [RecoveryValidator](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/deployment/recovery_validator.py#L30) must map the historical `expected_state_hash` matching the deprecated schema, executing standard FSM checks under the policy snapshot corresponding to that specific execution version.
* **Replay Isolation**: Replayers load versioned constraints from the lineage `policy_snapshot` metadata to evaluate old sequences, preventing modern validation rules from breaking backward compatibility.

---

## 3. Semantic Drift Rejection Proof

### Verification Mechanism
To verify that semantic drift is programmatically rejected, the test suite executes transition validations:
* **Test Case**: `test_hidden_state_synthetic_injection` inside [test_phase4_semantic_guards.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/tests/test_phase4_semantic_guards.py#L234)
* **Anomaly**: A degraded runtime node attempts to transition state history using the invalid jump path `CREATED` $\rightarrow$ `EXECUTING`, skipping the prerequisite `APPROVED` state.
* **Outcome**: The [SemanticGuardEngine](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L247) throws [SemanticTransitionViolation.SYNTHETIC_STATE_INJECTED](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L45) and returns a validation error, blocking state mutation.

```text
Attempt semantic drift:
CREATED -> EXECUTING (APPROVED skipped)

Replay check result:
REJECTED (SYNTHETIC_STATE_INJECTED)
```
