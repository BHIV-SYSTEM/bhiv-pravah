# Phase 9 — Full Acceptance Review Packet

**Date**: 2026-06-11  
**System**: Pravah Multi-Agent Control Plane  
**Audit Rule**: No marketing language. No closure inflation.

---

## 1. Entry Points

The system has three primary entry paths. Each carries a distinct trust and validation profile.

### 1.1 Flask Control Plane API

**File**: [agent_api.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/api/agent_api.py)  
**Port**: 7000 (configurable via `CONTROL_PLANE_PORT`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Liveness probe |
| `/api/status` | GET | Runtime FSM state |
| `/api/runtime` | POST | Canonical runtime decision intake |
| `/api/control-plane/apps` | GET | Onboarded app registry |
| `/api/control-plane/health` | GET | Health overview dashboard |
| `/api/control-plane/history/<app>` | GET | Decision history timeline |
| `/api/control-plane/override` | POST | Manual freeze set/clear |

**Validation pipeline on `/api/runtime`** (in order):

```text
1. verify_request_trace(payload)    → 401 on trace verification failure
2. validate_trace(payload)          → 400 on trace rule failure
3. InputValidator.validate_runtime_payload(payload) → 400 on schema failure
4. _validate_runtime_payload (jsonschema) → 400 on schema failure
5. agent.handle_external_event()    → 500 on runtime failure
```

Rate limiting: `30/min` on runtime intake, `100/min` on health.

### 1.2 FastAPI Decision Backend

**File**: `control_plane/backend/app/main.py`  
**Port**: 8000

Provides `/decision`, `/live-dashboard`, `/autonomous-status`, `/orchestration/metrics`. Decision engine runs deterministic Q-table lookups. Integration bridge reports control-plane link status.

### 1.3 Deployment Orchestrator

**File**: [deploy_pravah.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/deploy_pravah.py)

Boot sequence:
1. `setup_environment()` — sets `ENVIRONMENT`, `PORT`, `LOG_LEVEL`
2. `start_agent_runtime()` — launches `agent_runtime.py` as subprocess
3. `start_api_server()` — launches Flask API (dev) or Gunicorn (prod)
4. `health_check()` — polls `/api/health` up to 5 times
5. `display_status()` — prints process table and access points

The runtime thread is also started directly inside `agent_api.py` via `threading.Thread(target=start_agent_loop, daemon=True).start()` at module load. This means the agent loop runs inside the API process.

---

## 2. Core Execution Flow

### 2.1 Agent Loop FSM

**File**: [agent_runtime.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/agent_runtime.py)

```text
IDLE → OBSERVING → VALIDATING → DECIDING → ENFORCING → ACTING → OBSERVING_RESULTS → EXPLAINING → IDLE
              ↘                                                                                    ↗
               BLOCKED ←──────────── (any failure) ─────────────────────────────────────────→ IDLE
```

States defined in [AgentState](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/core/agent_state.py#L13). Transitions enforced in [VALID_TRANSITIONS](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/core/agent_state.py#L31). Invalid transitions raise `ValueError`.

### 2.2 Decision Path

```text
PerceptionLayer.perceive()
   → RuntimeEventAdapter / HealthSignalAdapter
   → RuntimeEventValidator (envelope validation)
   → InputValidator (schema validation)
   → ActionGovernance.evaluate_action()
       ├── Eligibility (env-scoped allowlist)
       ├── Cooldown (time-based per action type)
       ├── Repetition suppression (sliding window)
       └── DeterministicPolicyEngine.admit()
              ├── sig_valid / nonce_valid
              ├── trace_valid
              ├── schema_valid (policy_version check)
              ├── GovernanceContract signature (HMAC)
              └── LegitimacyDoctrine.compute() → legitimacy
   → DecisionProvider.decide()
       ├── HTTPDecisionProvider (production: RL brain on port 8008)
       └── LocalRuleDecisionProvider (test: in-process rules)
   → execute() via action executor
   → Proof logging
```

### 2.3 DecisionProvider Abstraction

**Defined at**: [agent_runtime.py:L59-L79](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/agent_runtime.py#L59)

```python
class DecisionProvider:
    def decide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

class HTTPDecisionProvider(DecisionProvider):
    def decide(self, payload):
        response = requests.post(self.endpoint_url, json=payload, timeout=self.timeout)
        return response.json()
```

`AgentRuntime.__init__` accepts `decision_provider: Optional[DecisionProvider]`. This decouples the runtime from HTTP transport and allows in-process testing without network mocks.

---

## 3. Replay Acceptance Matrix

Full matrix documented in [replay_acceptance_matrix.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/review_packets/replay_acceptance_matrix.md).

### 3.1 Replay Chain Architecture

| Layer | Component | File |
|---|---|---|
| Persistence | `AppendOnlyLog` | [append_only_log.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/persistence/append_only_log.py) |
| Hash verification | `HashLineageVerifier` | [hash_lineage_verifier.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/persistence/hash_lineage_verifier.py) |
| Signature verification | `LineageVerifier` | [lineage_verifier.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/security/lineage_verifier.py) |
| Index | `ReplayIndex` | [replay_index.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/persistence/replay_index.py) |
| Snapshots | `SnapshotRegistry` | [replay_index.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/persistence/replay_index.py) |
| Boot recovery | `RecoveryValidator` | [recovery_validator.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/deployment/recovery_validator.py) |

### 3.2 Hostile Condition Coverage

| Condition | Defense | Replay Result |
|---|---|---|
| Process restart | Hash chain + state hash comparison on boot | `PASS` — zero drift |
| Partial dependency failure | `ReadinessValidator` blocks boot | `PASS` — refuses startup |
| Duplicate delivery | `TraceConsumptionRegistry` + `NonceStore` | `PASS` — rejects duplicate |
| Delayed delivery | Timestamp age verification (300s window) | `PASS` — rejects stale |
| Network degradation | Hash chain breaks on reorder/loss | `PASS` — `SequenceViolationError` |
| Schema evolution | `DeterministicPolicyEngine` version check | `PASS` — `POLICY_VERSION_MISMATCH` |
| Cross-service disagreement | `ActionGovernance` blocks unauthorized | `PASS` — `EXECUTION_DENIED` |
| Degraded runtime | `SemanticGuardEngine` detects hidden states | `PASS` — `SYNTHETIC_STATE_INJECTED` |

### 3.3 Replay Error Taxonomy

| Exception | Meaning |
|---|---|
| `UnsignedReplayEventError` | Event missing HMAC signature |
| `PayloadHashMismatchError` | Payload content changed after signing |
| `LineageBreakError` | Parent hash does not match previous event |
| `SequenceViolationError` | Events out of order or sequence gap |
| `DuplicateReplayError` | Same trace_id or event_id seen twice |
| `TimestampSanityError` | Negative, future, or backward timestamp |

### 3.4 Test Suite Evidence

98 tests, 0 failures. Verified in [replay_acceptance_matrix.md §4](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/review_packets/replay_acceptance_matrix.md).

---

## 4. Hostile Reality Proof

**Evidence file**: [hostile_runtime_results.log](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/proofs/phase8/hostile_runtime_results.log)  
**Test suite**: [run_hostile_tests.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/scripts/run_hostile_tests.py) (654 lines, 10 scenarios)

### 4.1 Per-Scenario Results

| # | Scenario | Expected | Actual | Runtime State | Action | Verdict |
|---|---|---|---|---|---|---|
| 1 | Signature failure | `ILLEGITIMATE` | `ILLEGITIMATE` | `BLOCKED` | `REJECT` | **PASS** |
| 2 | Trace corruption | `ILLEGITIMATE` | `ILLEGITIMATE` | `BLOCKED` | `HALT` | **PASS** |
| 3 | Duplicate delivery | `ILLEGITIMATE` | `ILLEGITIMATE` | `BLOCKED` | `REJECT` | **PASS** |
| 4 | Ordering corruption | `ILLEGITIMATE` | `ILLEGITIMATE` | `BLOCKED` | `HALT` | **PASS** |
| 5 | Schema mismatch | `ILLEGITIMATE` | `ILLEGITIMATE` | `BLOCKED` | `REJECT` | **PASS** |
| 6 | Network degradation | `LEGITIMATE_DEGRADED` | `LEGITIMATE_DEGRADED` | `DEGRADED` | `DEGRADED_ALLOWED` | **PASS** |
| 7 | Dependency outage | `LEGITIMATE_DEGRADED` | `LEGITIMATE_DEGRADED` | `DEGRADED` | `DEGRADED_ALLOWED` | **PASS** |
| 8 | Cross-service disagreement | `LEGITIMATE_AMBIGUOUS` | `LEGITIMATE_AMBIGUOUS` | `HALTED` | `HALT` | **PASS** |
| 9 | Partial replay reconstruction | `LEGITIMATE_AMBIGUOUS` | `LEGITIMATE_AMBIGUOUS` | `HALTED` | `REPLAY_ONLY` | **PASS** |
| 10 | Operator absence | `LEGITIMATE_VALID` | `LEGITIMATE_VALID` | `ACTIVE` | `EXECUTE` | **PASS** |

### 4.2 Suite Aggregates

```json
{
  "phase": 7,
  "hostile_tests": 10,
  "passed": 10,
  "failed": 0,
  "visible_legitimacy_outcomes": 10,
  "missing_legitimacy_outcomes": 0,
  "silent_continuations_detected": 0,
  "runtime_produced_legitimacy": true,
  "overall_verdict": "PASS"
}
```

### 4.3 How Each Scenario Exercises Real Components

| Scenario | Component Exercised | Not Synthetic Because |
|---|---|---|
| 1. Signature failure | `DeterministicPolicyEngine.admit(sig_valid=False)` | Engine produces `PolicyAdmissionDecision` with `ILLEGITIMATE` legitimacy |
| 2. Trace corruption | `RecoveryValidator.validate()` on corrupted journal | Writes real journal, corrupts signature bytes, runs real hash chain verification |
| 3. Duplicate delivery | `DeterministicPolicyEngine.admit(nonce_valid=False)` | Nonce invalidity routed through same admission path as production |
| 4. Ordering corruption | `SemanticGuardEngine.validate_state_history()` → Policy | Semantic violation detected by guard, routed to policy as `trace_valid=False` |
| 5. Schema mismatch | `DeterministicPolicyEngine.admit(schema_valid=False)` | Version `v2` vs runtime `v1` produces `POLICY_VERSION_MISMATCH` |
| 6–7. Network/Dependency | `DeterministicPolicyEngine` with `DependencyCondition.RL_UNAVAILABLE` | Dependency enum propagated through real doctrine path |
| 8. Cross-service | `RecoveryValidator` with manipulated `ReplayIndex` (event_count=2 vs actual 3) | Real journal + real index with deliberate count mismatch |
| 9. Partial replay | `RecoveryValidator` with event physically deleted from journal | Journal file written, event line removed, recovery run on truncated file |
| 10. Operator absence | `AgentRuntime._execute_agent_loop()` with injected `LocalRuleDecisionProvider` | Full FSM cycle: sense → validate → decide → enforce → act → observe → explain |

---

## 5. Enforcement Ceiling Proof

### 5.1 Sarathi Enforcement Ceilings

Documented in [sarathi_authority_matrix.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/proofs/phase8/sarathi_authority_matrix.md).

| Sarathi MAY | Sarathi MAY NOT |
|---|---|
| Reject unsigned API requests | Decide recovery actions |
| Reject replay attempts (duplicate nonces) | Modify Q-table calculations |
| Reject duplicate event traces | Define legitimacy outcomes |
| Block out-of-cooldown requests | Create constitutional policy |
| Enforce environment constraints | Modify governance policy |
| Validate payload structure | Certify replay acceptance |
| Observe target service status | Redefine state semantics |

### 5.2 Pravah Negative Authority Lock

Documented in [pravah_negative_authority_lock.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/proofs/phase8/pravah_negative_authority_lock.md).

Six hard prohibitions:

1. **SHALL NOT manufacture authority** — zero authority to bypass or rewrite security policies
2. **SHALL NOT reinterpret legitimacy** — cannot alter or re-classify legitimacy states
3. **SHALL NOT rewrite canonical semantics** — cannot alter transition sequences or prerequisites
4. **SHALL NOT silently authorize degraded continuation** — must transparently report degraded modes
5. **SHALL NOT inherit orchestration sovereignty** — enforcement agent only
6. **SHALL NOT own governance semantics** — policy parameters reside outside runtime

### 5.3 Code-Level Enforcement Evidence

| Lock | Code Location | Mechanism |
|---|---|---|
| Governance contract immutability | [deterministic_policy_engine.py:L273](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py#L273) | `if not contract.immutable: raise DeterministicExecutionRejection` |
| Trusted signer check | [deterministic_policy_engine.py:L297](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py#L297) | `if contract.governance_approver not in self.trusted_signers: raise` |
| HMAC signature validation | [deterministic_policy_engine.py:L306-L317](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py#L306) | `hmac.compare_digest(expected_signature, contract.signature)` |
| Policy version alignment | [deterministic_policy_engine.py:L558](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py#L558) | `if coerced_request.policy_version != runtime_policy_version` |
| Eligibility rules (env-scoped) | [action_governance.py:L134-L138](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/core/action_governance.py#L134) | Hardcoded allowlists per environment |
| Doctrine separation header | [legitimacy_doctrine.py:L1-L7](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/legitimacy_doctrine.py#L1) | File header declares evaluator-only role |

---

## 6. Degraded Operation Doctrine

Full doctrine at [degraded_runtime_doctrine.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/proofs/phase8/degraded_runtime_doctrine.md).

### 6.1 Decision Matrix

Implemented as `LegitimacyDoctrine.compute()` in [legitimacy_doctrine.py:L82-L107](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/legitimacy_doctrine.py#L82):

| sig | trace | schema | deps | → Legitimacy | → State | → Action |
|---|---|---|---|---|---|---|
| ✗ | — | — | — | `ILLEGITIMATE` | `BLOCKED` | `REJECT` |
| ✓ | ✗ | — | — | `ILLEGITIMATE` | `BLOCKED` | `HALT` |
| ✓ | ✓ | ✗ | — | `ILLEGITIMATE` | `BLOCKED` | `REJECT` |
| ✓ | ✓ | ✓ | `MISSING_DB_INDEX` | `LEGITIMATE_AMBIGUOUS` | `HALTED` | `HALT` |
| ✓ | ✓ | ✓ | `PARTIAL_REPLAY_GAP` | `LEGITIMATE_AMBIGUOUS` | `HALTED` | `REPLAY_ONLY` |
| ✓ | ✓ | ✓ | `RL_UNAVAILABLE` | `LEGITIMATE_DEGRADED` | `DEGRADED` | `DEGRADED_ALLOWED` |
| ✓ | ✓ | ✓ | `ALL_AVAILABLE` | `LEGITIMATE_VALID` | `ACTIVE` | `EXECUTE` |

### 6.2 Dependency Fallback Behaviors

| Dependency | Failure Mode | Fallback | Legitimacy |
|---|---|---|---|
| Redis event bus | Connection refused | In-memory `MockEventBus` | `LEGITIMATE_DEGRADED` |
| RL Decision Brain | Timeout / unreachable | Fallback `noop` action via safe executor | `LEGITIMATE_DEGRADED` |
| Replay index file | Missing or corrupted | Rebuild attempt from journal; if fails → `ready=False` | `LEGITIMATE_AMBIGUOUS` |
| Journal file | Missing or empty | `journal_missing_or_empty` failure | `LEGITIMATE_AMBIGUOUS` |

### 6.3 Ambiguity State Rules

```text
AMBIGUITY_DETECTED — Allowed: observe, persist, replay. Forbidden: execute, authorize, mutate state, continue workflow.
```

---

## 7. Authority Declarations

### 7.1 Legitimacy Ownership Chain

```text
Constitutional Policy (external, GC-approved)
   │
   └── LegitimacyDoctrine (runtime evaluator ONLY)
          │
          ├── DeterministicPolicyEngine.admit() → PolicyAdmissionDecision.legitimacy
          ├── RecoveryValidator.validate() → RecoveryValidationResult.legitimacy
          ├── ActionGovernance.evaluate_action() → GovernanceDecision.legitimacy
          └── AgentRuntime._last_legitimacy (propagated from above)
```

Legitimacy is **produced** by runtime components but **defined** by constitutional policy. The test suite **reads** legitimacy, it does not inject it.

### 7.2 Governance Authority

| Authority | Owner | Runtime Role |
|---|---|---|
| Legitimacy semantics | Constitutional policy | Evaluate only |
| State vocabulary | [execution_state.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/contracts/execution_state.py) | Read only |
| Policy parameters | `PolicySnapshot` (signed) | Enforce only |
| Recovery decisions | RL Decision Brain | Consume only |
| Transition rules | `SemanticFSM.ALLOWED_TRANSITIONS` | Enforce only |

### 7.3 Audit Evidence

Every admission decision writes a record to `logs/control_plane/policy_enforcement.jsonl` via [DeterministicPolicyEngine._log_decision()](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py#L423). Every governance action writes to `logs/control_plane/append_only_log.jsonl`. Every recovery validation writes to `deployment_verification_packet/`.

All hostile test records include `doctrine_inputs` providing full audit evidence of the inputs that produced each legitimacy outcome.

---

## 8. Deployment Reality Proof

### 8.1 Boot Validation Chain

```text
deploy_pravah.py
   ├── StartupValidator (file presence, Redis, module availability)
   ├── ReadinessValidator (journal integrity, replay index)
   └── RecoveryValidator (hash chain, signature, state hash comparison)
         ├── HashLineageVerifier.verify_sequence_continuity()
         ├── HashLineageVerifier.verify_hash_chain()
         ├── LineageVerifier.verify_lineage_signatures()
         ├── ReplayIndex.get_execution() → event count match
         ├── SnapshotRegistry.get_latest_snapshot() → state hash match
         └── LegitimacyDoctrine.compute() → legitimacy
```

If any validator returns `ready=False`, the system does not accept traffic.

### 8.2 Restart Survival Evidence

From [live_operational_reality.md §4](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/proofs/phase8/live_operational_reality.md):

```json
{
  "before_restart": {
    "state_hash": "07f4c32142d8adab5c0cddbcaa12ba5f859de8af4fb94ce299ed2e5f96e95550",
    "index_exists": true
  },
  "after_restart": {
    "state_hash": "07f4c32142d8adab5c0cddbcaa12ba5f859de8af4fb94ce299ed2e5f96e95550",
    "index_exists": true
  },
  "match": true
}
```

State hash is SHA-256 of the reconstructed execution state. Identical before and after restart.

### 8.3 Deployment Topology (as deployed)

| Process | Port | Status |
|---|---|---|
| Flask Control Plane API | 7000 | Single-process, threaded agent loop |
| FastAPI Decision Backend | 8000 | Independent process |
| RL Decision Brain | 8008 | External service (separate repo) |
| Redis | 6379 | Optional; falls back to in-memory |
| Action Executor | 5003 | Separate service |
| Observability Monitor | 5004 | SSE stream |
| Dashboard Frontend | 4500 | Next.js |

---

## 9. State Semantics Closure

### 9.1 Canonical State Vocabularies

**Execution States** (defined in `contracts/execution_state.py`):

| State | Meaning | Terminal |
|---|---|---|
| `CREATED` | Lifecycle initiated, parameters registered | No |
| `APPROVED` | Governance validated, signature verified | No |
| `EXECUTING` | Dispatched to executor, actively running | No |
| `COMPLETED` | Terminal success, outcomes verified | Yes |
| `FAILED` | Terminal failure, aborted path logged | Yes |

**Legitimacy States** (defined in [LegitimacyStatus](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/legitimacy_doctrine.py#L12)):

| State | Meaning |
|---|---|
| `LEGITIMATE_VALID` | All checks pass, full authority |
| `LEGITIMATE_DEGRADED` | Dependency fallback active, limited operations |
| `LEGITIMATE_AMBIGUOUS` | Lineage dispute or index mismatch, halted |
| `ILLEGITIMATE` | Cryptographic or schema failure, blocked |

**Agent Runtime States** (defined in [AgentState](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/core/agent_state.py#L13)):

`IDLE`, `OBSERVING`, `VALIDATING`, `DECIDING`, `ENFORCING`, `ACTING`, `OBSERVING_RESULTS`, `EXPLAINING`, `BLOCKED`, `SHUTTING_DOWN`

### 9.2 Semantic FSM Transition Rules

Defined in [SemanticFSM.ALLOWED_TRANSITIONS](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L102):

```text
CREATED  → {APPROVED, FAILED}
APPROVED → {EXECUTING, FAILED}
EXECUTING → {COMPLETED, FAILED}
COMPLETED → {} (terminal)
FAILED    → {} (terminal)
```

Prerequisites enforced in [TRANSITION_PREREQUISITES](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L111):

```text
APPROVED  requires {CREATED}
EXECUTING requires {CREATED, APPROVED}
COMPLETED requires {CREATED, APPROVED, EXECUTING}
FAILED    requires {CREATED}
```

### 9.3 Alias Prohibition

The `EXECUTED` alias is handled by normalization in `SemanticFSM._normalize_state()` which maps it to `EXECUTING`. The [state_semantics_contract.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/proofs/phase8/state_semantics_contract.md) explicitly prohibits aliases in production payloads and declares `EXECUTED` as invalid for lineage events.

### 9.4 Semantic Ownership

State vocabulary is owned by `contracts/execution_state.py`. No runtime, dashboard, or API engine has authority to define, inject, or edit state semantics. Changes require a policy version update.

---

## 10. Remaining Known Limitations

### 10.1 Documented in [KNOWN_LIMITATIONS.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/KNOWN_LIMITATIONS.md)

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| 1 | **Local governance persistence** — `governance_state.json` is filesystem-local with thread locks | Split-brain governance in multi-node deployment | Upgrade to Redis or PostgreSQL |
| 2 | **Docker scaling simulation** — `scale_up`/`scale_down` in Docker mode are logged but not executed | No actual containers spawned during Docker-mode scaling | Use Kubernetes executor for physical scaling |
| 3 | **Strict trace sequence ordering** — single-process trace logger can throw `ValueError` on concurrent interleaving | Race condition in multi-worker uvicorn | `reset_trace()` per request; extend to partition by `trace_id` |
| 4 | **Hardcoded monitor targets** — static dictionary in monitor app | Adding services requires code changes | Introduce dynamic service discovery |

### 10.2 Not Documented Elsewhere (Identified During This Review)

| # | Limitation | Impact |
|---|---|---|
| 5 | **Static signing keys** — `POLICY_SIGNING_KEY` and `SECRET_KEY` have hardcoded default values in source | Any attacker with code access can forge governance contracts |
| 6 | **No key rotation** — no procedure or tooling for rotating signing keys | Compromised key has no recovery path short of code redeployment |
| 7 | **Code-embedded policy** — governance policies are Python constants, not externally loaded artifacts | Policy changes require code deployment, not hot-reload |
| 8 | **Local-only audit logs** — all JSONL logs are filesystem-local | Node failure destroys audit trail; no SIEM integration |
| 9 | **Duplicate import** — `from unittest import result` appears twice in `agent_runtime.py` lines 15-16 | No functional impact; code hygiene defect |
| 10 | **Legacy `call_decision_engine` function** — standalone function at `agent_runtime.py:L82-L87` bypasses `DecisionProvider` abstraction | Dead code that could be called accidentally, circumventing the abstraction |

---

## 11. Honest Maturity Estimate

### 11.1 What Is Genuinely Mature

- **FSM enforcement**: Enumerated transitions with `ValueError` on violation. No silent fallthrough. Verified across 10 hostile scenarios.
- **Legitimacy architecture**: Pure evaluator pattern with `DependencyCondition` enum. Runtime produces legitimacy; tests read it. Doctrine separation is structural, not aspirational.
- **Cryptographic lineage**: HMAC-SHA256 per-event signatures, hash chains, sequence verification, duplicate detection, timestamp sanity checks. `LineageVerifier.verify_replay_chain()` runs the full chain in a single pass.
- **Hostile validation**: 10/10 scenarios pass. Zero silent continuations. Every failure produces auditable `doctrine_inputs`.
- **Governance separation**: `GovernanceContract` with HMAC signature, immutability flag, trusted signer whitelist. Policy engine rejects mismatched versions, unsigned contracts, untrusted signers.
- **DecisionProvider abstraction**: Runtime decoupled from HTTP. Injectable decision sources for test and production.
- **Boot-time recovery**: Real hash chain verification, real signature delegation, real state hash comparison.

### 11.2 What Is Not Mature

- **Key management**: Static defaults. No rotation. No HSM. No compromise response procedure.
- **Multi-node coordination**: Governance state is local. Cooldowns are per-process. No distributed consensus.
- **Policy lifecycle**: Policies are code constants. No external store. No hot-reload. No independent versioning.
- **Operational observability**: No external audit log sink. No SIEM pipeline. No alerting on legitimacy state changes.
- **Scale execution**: Docker scaling is simulated. Kubernetes executor exists but is not tested in this review.
- **Constitutional formalization**: The "constitution" is distributed across markdown files and code comments. No single, versioned, independently deployable constitutional artifact.

### 11.3 Classification

**Late Prototype / Early Production-Candidate**

Ready for:
- Single-node controlled deployments
- Development and staging environments
- Architecture validation and demonstration

Not ready for:
- Multi-tenant production
- Compliance-audited environments
- Horizontal scaling under load

This classification is based on code evidence, not aspiration.

---

## 12. What Remains Unresolved

### 12.1 Architectural

| # | Issue | Severity | Resolution Path |
|---|---|---|---|
| 1 | Static signing keys with hardcoded defaults | **Critical** | External secrets management (Vault, AWS Secrets Manager) + key rotation procedure |
| 2 | Single-node governance state | **Critical** for multi-node | Migrate `governance_state.json` to Redis or PostgreSQL with distributed locking |
| 3 | Code-embedded policy definitions | **High** | External policy store with signed, versioned policy artifacts and hot-reload capability |
| 4 | No external audit log pipeline | **High** | SIEM integration (Splunk, ELK, or cloud-native equivalent) for `policy_enforcement.jsonl` and `append_only_log.jsonl` |

### 12.2 Operational

| # | Issue | Severity | Resolution Path |
|---|---|---|---|
| 5 | Docker scaling is simulated | **Medium** | Validate Kubernetes executor with physical pod scaling |
| 6 | Trace sequence interleaving under concurrency | **Medium** | Partition trace validation context by `trace_id` |
| 7 | Hardcoded monitor targets | **Low** | Dynamic service discovery registry |
| 8 | `EXECUTED` alias normalization in SemanticFSM | **Low** | Remove alias support; reject `EXECUTED` outright at intake validation |

### 12.3 Code Hygiene

| # | Issue | File | Line |
|---|---|---|---|
| 9 | Duplicate `from unittest import result` | `agent_runtime.py` | 15-16 |
| 10 | Legacy `call_decision_engine` function bypasses `DecisionProvider` | `agent_runtime.py` | 82-87 |

### 12.4 Verification Gaps

| # | Gap | Current State |
|---|---|---|
| 11 | No load testing evidence | No proof that the system maintains legitimacy guarantees under concurrent request volume |
| 12 | No multi-node deployment test | Recovery validation is only proven single-node |
| 13 | No key compromise simulation | No hostile test for a scenario where the signing key itself is compromised |
| 14 | No long-running stability test | FSM loop stability over hours/days is not proven |

---

*End of Phase 9 Acceptance Review Packet*
