# Pravah Degraded Operation Doctrine (Phase 8 Executable Blueprint)

This document establishes the official executable boundaries and operational invariants for the Pravah control plane during degraded states.

---

## 1. Cryptographic and Lineage Failures

### When signatures fail:
* **Legitimacy Status**: `ILLEGITIMATE`
* **Runtime State**: `BLOCKED`
* **System Action**: 
  1. The API middleware [verify_service_auth](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/core_hooks/service_auth.py#L22) aborts the request pipeline immediately.
  2. The server returns HTTP status `401 Unauthorized` with a JSON payload declaring `"status": "failed"` and `"reason": "Invalid service signature"`.
  3. The [DeterministicPolicyEngine](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py#L118) transitions the request state to [AdmissionState.POLICY_SIGNATURE_INVALID](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py#L37), logs the signature rejection to `logs/control_plane/policy_enforcement.jsonl`, and blocks state mutation.

### When trace continuity breaks:
* **Legitimacy Status**: `ILLEGITIMATE`
* **Runtime State**: `BLOCKED`
* **System Action**:
  1. The middleware detects missing or malformed trace headers and blocks the request with HTTP status `403 Forbidden` (`Missing X-Caller header`).
  2. If an event log verification is requested, the [LineageVerifier](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/security/lineage_verifier.py) asserts that the sequence starts with the `CREATED` state. If this rule is violated, it raises [SequenceViolationError](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/security/lineage_verifier.py#L17) (`REPLAY_REJECTED_MUST_START_WITH_CREATED`).
  3. The orchestrator catches the exception, aborts the operational cycle, and locks the state machine into the terminal `AgentState.BLOCKED` status.

### When replay partially reconstructs:
* **Legitimacy Status**: `LEGITIMATE_AMBIGUOUS`
* **Runtime State**: `HALTED`
* **System Action**:
  1. The [SemanticGuardEngine](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L155) evaluates the sequence of reconstructed states against the [SemanticFSM](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L93) prerequisites.
  2. If missing steps or synthetic insertions are detected, it raises a `ValueError` with [SemanticTransitionViolation.SYNTHETIC_STATE_INJECTED](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L45) or `HIDDEN_STATE_DETECTED`.
  3. The [RecoveryValidator](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/deployment/recovery_validator.py#L30) flags a `state_hash_mismatch`, records a `"FAIL"` outcome status inside `deployment_verification_packet/recovery_validation.log`, returns `ready = False`, and prevents system boot.

---

## 2. Schema and Dependency Failures

### When schemas diverge:
* **Legitimacy Status**: `ILLEGITIMATE`
* **Runtime State**: `BLOCKED`
* **System Action**:
  1. The gateway executes schema validation via `InputValidator.validate_runtime_payload`. If fields are missing, it throws a `400 Bad Request` with payload details.
  2. In the policy engine, if the request version doesn't match the active configuration, the engine returns [AdmissionState.POLICY_VERSION_MISMATCH](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py#L36) with [RejectionCode.POLICY_VERSION_MISMATCH](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py#L26), rejecting execution.

### When dependencies disappear:
* **Redis event bus**: Catches connection failures and dynamically falls back to an in-memory `MockEventBus` (`LEGITIMATE_DEGRADED`).
* **RL Decision Brain (Port 8008)**: Catches connection exceptions and routes decision processing to `fallback_safe`, executing the default safety `noop` action (`LEGITIMATE_DEGRADED`).
* **Persisted index files**: Startup and recovery validators fail to load, log error flags to the verification packet, return `ready = False` (`LEGITIMATE_AMBIGUOUS`), and keep the system offline to prevent state corruption.

---

## 3. Human and Authority Invariants

### When operators are unavailable:
* **System Action**:
  1. The system operates autonomously within its closed-loop cycle (**Sense → Validate → Decide → Enforce → Act → Observe → Explain**).
  2. The dashboard UI monitors connection status. If it detects a timeout to the control plane API, it displays a `DISCONNECTED` alert chip and locks all user input fields to prevent mock command execution or manual overrides.

### Degraded Continuation Authority:
* **Authority Source**: Cryptographically Signed Constitutional Policy (GC-approved).
* **Authorizer**: Governance-approved policy artifact (`PolicySnapshot`) matching active public keys.
* **Runtime Role**: Enforce only. **The runtime has ZERO authority to generate or expand its own legitimacy bounds.**
* **Revocation Path**: Policy version replacement at runtime via signed configuration override.

### Who records legitimacy?
* **Recording Entities**:
  1. The append-only persistence ledger [AppendOnlyLog](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/persistence/append_only_log.py#L12) writes all state changes and hashes to `logs/control_plane/append_only_log.jsonl`.
  2. The [DeploymentProofPacket](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/deployment/deployment_proof.py#L22) records validation outcomes inside the `deployment_verification_packet/` folder (`startup_validation.log`, `readiness_validation.log`, `recovery_validation.log`).

### Who escalates ambiguity?
* **Escalating Entities**:
  1. The [SemanticGuardEngine](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L155) escalates logical transition failures by throwing a `ValueError` which transitions the state machine to a blocked error state.
  2. The [ReadinessValidator](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/deployment/readiness_validator.py#L25) escalates file or recovery index corruption by refusing startup and marking the node status as degraded.

---

## 4. Deterministic Hostile-Condition Outcomes

The following matrix defines the exact legitimacy status and operational boundaries for each hostile condition:

| Hostile Condition | Legitimacy Status | Runtime State | Allowed Operations / Actions | Replay Status |
| :--- | :--- | :--- | :--- | :--- |
| **Signature Failure** | `ILLEGITIMATE` | `BLOCKED` | Reject Request / Log Violation | `INVALID` |
| **Trace Break** | `ILLEGITIMATE` | `BLOCKED` | Halt Request / Terminate Workflow | `INVALID` |
| **Partial Replay (Gap)** | `LEGITIMATE_AMBIGUOUS` | `HALTED` | Read-only Replay / Log Dispute | `INVALID` |
| **Schema Divergence** | `ILLEGITIMATE` | `BLOCKED` | Reject Request / Reject Execution | `INVALID` |
| **Redis Connection Loss** | `LEGITIMATE_DEGRADED` | `DEGRADED` | Local mock bus / Memory queue | `VALID` |
| **RL Brain Loss** | `LEGITIMATE_DEGRADED` | `DEGRADED` | Fallback `noop` action / Persistence | `VALID` |
| **Index File Loss** | `LEGITIMATE_AMBIGUOUS` | `HALTED` | Halt Boot / Rebuild Index | `INVALID` |
| **Operator Absence** | `LEGITIMATE_VALID` | `ACTIVE` | Normal closed-loop execution | `VALID` |

---

## 5. Ambiguity Handling Doctrine

Whenever system states, configuration values, or cryptographic lineages become contradictory, the runtime transitions to the `AMBIGUITY_DETECTED` state.

```text
===========================================================
               AMBIGUITY_DETECTED STATE RULES
===========================================================
Allowed Operations:
  * telemetry observation (observe)
  * append-only log writing (persist)
  * history playback/verification (replay)

Forbidden Operations:
  * action execution command dispatch (execute)
  * signing of state transitions (authorize)
  * index or registry updates (mutate state)
  * continuation of active loop workflow (continue workflow)
===========================================================
```

---

## 6. Executable Decision Matrix

The following decision rules are implemented programmatically by the validation engines to determine legitimacy:

| Sig Valid | Trace Continuity | Schema Matches | Key Dependencies | Computed legitimacy | Action Allowed |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **No** | *Any* | *Any* | *Any* | `ILLEGITIMATE` | `REJECT` |
| **Yes** | **No** | *Any* | *Any* | `ILLEGITIMATE` | `HALT` |
| **Yes** | **Yes** | **No** | *Any* | `ILLEGITIMATE` | `REJECT` |
| **Yes** | **Yes** | **Yes** | **Missing DB / Index** | `LEGITIMATE_AMBIGUOUS` | `HALT` |
| **Yes** | **Yes** | **Yes** | **Missing Redis/RL** | `LEGITIMATE_DEGRADED` | `DEGRADED_ALLOWED` (noop fallback) |
| **Yes** | **Yes** | **Yes** | **All Available** | `LEGITIMATE_VALID` | `EXECUTE` |

---

## 7. Forbidden Actions

The following actions are **permanently forbidden** and will be immediately blocked by the runtime guards:
1. **Unsigned State Transition**: State transitions attempted without verification headers will be blocked.
2. **State Machine Jumps**: Attempting to skip states (e.g. transitioning from `CREATED` directly to `COMPLETED`) is blocked by the FSM transition controls.
3. **Governance Cooldown Violation**: Attempting to execute an action (e.g., `restart`) within its active cooldown period (defaulting to 60 seconds) is blocked.
4. **Environment Constraint Breach**: Running scaling actions (`scale_up` / `scale_down`) in the `prod` environment. Only `noop` and `restart` are eligible actions under production settings.
