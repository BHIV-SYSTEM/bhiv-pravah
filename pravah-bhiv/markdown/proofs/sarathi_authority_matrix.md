# Sarathi Authority & Enforcement Ceilings Matrix (Phase 8)

This document establishes the official authority bounds and ceilings of the **Sarathi Caller Enforcement Layer** to prevent it from silently acquiring sovereign system authority. 

---

## 1. Sarathi Authority Boundaries

The authority boundaries of the Sarathi caller enforcement layer are strictly defined as follows:

### What Sarathi MAY Reject:
1. **Unsigned API Requests**: Any incoming payload targeting [app.py](/c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/reliability-controller2-main/executer/app.py) that fails HMAC-SHA256 signature verification.
2. **Replay Attempts**: Requests with duplicate nonces recorded in `security/nonce_store.json`.
3. **Duplicate Event Traces**: Requests containing a previously consumed `trace_id` retrieved from `security/trace_consumption.json`.
4. **Out-of-Cooldown Requests**: Action calls for a service (e.g. `web1-blue`) arriving within its configured cooldown period (60s default for `restart`, 120s for `scale_up`/`scale_down`).
5. **Ineligible Action Payloads**: Requests requesting actions not permitted in the active environment (e.g., scaling actions targeting the `prod` environment).

### What Sarathi MAY Enforce:
1. **Cryptographic service identification**: Enforces the presence and validation of `X-Service-Id`, `X-Service-Timestamp`, `X-Service-Nonce`, and `X-Service-Signature` headers.
2. **Timestamp age limitations**: Drops calls with timestamps older than the sliding age threshold.
3. **Rate Dampening**: Blocks redundant executions of identical actions within the repetition window.
4. **Environment Constraints**: Freezes action access depending on environment limits (e.g., only `noop` and `restart` in production).

### What Sarathi MAY Validate:
1. **Payload structural integrity**: Ensures incoming parameters match the schema signatures.
2. **Service ID Matching**: Verifies that the sender matches the signature context (`X-Service-Id` matching payload context).

### What Sarathi MAY Observe:
1. **Target service status**: Observes target application response logs.
2. **Execution metrics**: Observes metrics passing through the performance and decision logs (`logs/performance_log.csv` and `logs/agent/agent_decisions.log`).

### What Sarathi MAY NOT Decide:
1. **Recovery Actions**: **Sarathi has ZERO authority to calculate state transitions or determine recovery plans.** Recovery actions (whether to scale up, scale down, restart, or rollback) are decided solely by the FSM core ([agent_runtime.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/agent_runtime.py)) and Ritesh's persistent RL Decision Brain ([pravah-integration](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/pravah-integration.py-main) on Port `8008`).
2. **Q-learning rewards**: Cannot modify Q-table calculations, target rewards, or learning policies.
3. **Application thresholds**: Cannot decide service health levels or latency alert triggers.

### Legitimacy-State Enforcement Bounds:
* **Outcome Enforcement**: Sarathi MAY enforce legitimacy outcomes (such as blocking requests when computed legitimacy matches `ILLEGITIMATE` or `LEGITIMATE_AMBIGUOUS`).
* **State Redefinition Lock**: Sarathi MAY NOT define legitimacy outcomes or re-classify state definitions. Legitimacy states (`LEGITIMATE_VALID`, `LEGITIMATE_DEGRADED`, `LEGITIMATE_AMBIGUOUS`, `ILLEGITIMATE`) originate exclusively from the constitutional policy and runtime doctrine, never from the enforcement layer itself.

---

## 2. External Authority & Ownership Exclusions

### What Requires External Authority:
Sarathi SHALL NOT authorize:
1. Degraded continuation authorization.
2. Constitutional policy creation.
3. Governance policy modification.
4. Legitimacy state definition.
5. Replay acceptance certification.
6. State semantic redefinition.
7. Deployment acceptance decisions.

*Authority Source*: GC-approved signed governance artifacts only.

### Permanently Outside Enforcement Ownership:
Sarathi can never own:
* Governance semantics
* Constitutional legitimacy
* Replay truth
* Canonical lineage
* State vocabulary
* Recovery planning
* Runtime sovereignty
* Deployment acceptance
* Acceptance scoring
* Constitutional interpretation

These responsibilities cannot be delegated to Sarathi.

---

## 3. Invariant Ceilings and Emergency Doctrine

### A. Override Authority
* **Doctrine**: No manual command line, dashboard parameter, or external script is capable of overriding Sarathi signature validation at runtime. 
* **Mechanism**: Bypassing signature checks is cryptographically impossible. Any changes to the validation policy constraints require a hard configuration override of `SSPL_SECRET_KEY` / `POLICY_SIGNING_KEY` and a process restart.

### B. Emergency Bypass Doctrine
* **Doctrine**: Emergency execution bypasses are forbidden at the API gateway layer. 
* **Mechanism**: In the event of catastrophic failure, operators must execute recovery directly at the infrastructure level (e.g. via direct kubectl/docker CLI commands bypass). The [Action Executor API](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/executer/app.py) will reject any unauthenticated requests in production, preventing backdoors.

### C. Enforcement Legitimacy Source
* **Doctrine**: Sarathi derives its operational legitimacy exclusively from:
  1. The cryptographic keys (`SSPL_SECRET_KEY` / `POLICY_SIGNING_KEY`) loaded securely from the environment.
  2. The policy rules defined in the [DeterministicPolicyEngine](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py#L118) constraints.

### D. Dispute Handling
* **Doctrine**: In the event of a disagreement (e.g. caller headers authenticate successfully, but the event history contains sequence gaps):
  1. The FSM strictly prioritizes lineage checks. The [SemanticGuardEngine](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L155) halts the execution loop and transitions to the `BLOCKED` error state.
  2. Execution is aborted, and the incident is flagged for manual operator inspection via the append-only journal (`trace_log.jsonl`).

### E. Enforcement Ceiling
* **Doctrine**: Sarathi's boundary ends at **syntactic and policy verification**.
* **Ceiling Limits**:
  - It does not own or modify the ledger.
  - It does not generate state-reconstruction paths during boot (owned by [RecoveryValidator](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/deployment/recovery_validator.py#L30)).
  - It does not display or cache active visual telemetry (owned by `unified-monitor-dashboard-main` on Port `8050`).

---

## 4. Sovereignty Boundary Lock

Sarathi is strictly an enforcement participant.

**Sarathi is NOT**:
* a governance authority
* a legitimacy authority
* a replay authority
* a semantic authority
* a constitutional authority

**Sarathi MAY ONLY**:
* validate
* reject
* enforce

**Sarathi MAY NEVER**:
* authorize
* reinterpret
* govern
* certify
* legitimize
