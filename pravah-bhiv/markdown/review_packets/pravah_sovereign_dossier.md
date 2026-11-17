# Pravah Sovereign Dossier — Phase 8

**Date**: 2026-06-11  
**Classification**: Architecture Review — Final  
**Author**: Automated Audit (Antigravity)  
**Audit Rule**: No optimism inflation. Honest maturity classification.

---

## 1. Canonical Operational Definition

Pravah is a **multi-agent runtime control plane** that orchestrates autonomous CI/CD recovery actions across distributed microservices.

It operates as a deterministic enforcement loop:

```text
sense → validate → decide → enforce → act → observe → explain
```

The runtime is implemented as a Python FSM
([AgentRuntime](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/agent_runtime.py#L90))
with 10 explicit states defined in
[AgentState](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/core/agent_state.py#L13):

| State | Loop Phase |
|---|---|
| `IDLE` | Waiting for next cycle |
| `OBSERVING` | Sense |
| `VALIDATING` | Validate |
| `DECIDING` | Decide |
| `ENFORCING` | Enforce |
| `ACTING` | Act |
| `OBSERVING_RESULTS` | Observe |
| `EXPLAINING` | Explain |
| `BLOCKED` | Error / Safety halt |
| `SHUTTING_DOWN` | Terminal |

Valid transitions are enumerated and enforced in
[AgentStateManager.VALID_TRANSITIONS](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/core/agent_state.py#L31).
Any invalid transition raises `ValueError`. There is no silent fallthrough.

---

## 2. Authority Model

### 2.1 Constitutional Authority Hierarchy

```text
Governance Constitution (external, GC-approved)
   │
   ├── PolicySnapshot (signed, versioned)
   │      └── GovernanceContract (HMAC-signed, immutable)
   │
   ├── LegitimacyDoctrine (runtime evaluator ONLY)
   │      └── Computes legitimacy from inputs; does not define semantics
   │
   └── Sarathi (enforcement layer ONLY)
          └── May reject; may NOT decide
```

### 2.2 Authority Boundaries

| Actor | MAY | MAY NOT |
|---|---|---|
| **Governance Constitution** | Define legitimacy semantics, policy rules, state vocabulary | — |
| **Pravah Runtime** | Enforce policy, persist lineage, observe signals, surface state | Manufacture authority, reinterpret legitimacy, rewrite semantics, silently authorize degraded continuation |
| **Sarathi** | Reject unsigned requests, enforce cooldowns, block ineligible actions | Decide recovery actions, modify Q-tables, define legitimacy states |
| **RL Decision Brain** | Compute recovery actions from Q-tables | Override governance, bypass policy |
| **Operator** | Monitor dashboard, apply manual overrides | Override cryptographic validation at runtime |

### 2.3 Negative Authority Lock

Defined in [pravah_negative_authority_lock.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/proofs/phase8/pravah_negative_authority_lock.md):

1. Pravah SHALL NOT manufacture authority.
2. Pravah SHALL NOT reinterpret legitimacy.
3. Pravah SHALL NOT rewrite canonical semantics.
4. Pravah SHALL NOT silently authorize degraded continuation.
5. Pravah SHALL NOT inherit orchestration sovereignty.
6. Pravah SHALL NOT own governance semantics.

> [!IMPORTANT]
> The `LegitimacyDoctrine` class header explicitly declares: *"LegitimacyDoctrine is a runtime evaluator ONLY. It evaluates constitutional rules defined by the policy/governance layer. It does not define legitimacy semantics."*

### 2.4 Honest Authority Assessment

**What works**: The doctrine evaluator is structurally separated from policy definition. `LegitimacyDoctrine.compute()` is a pure function that maps `(sig_valid, trace_valid, schema_valid, key_deps)` → `(legitimacy, state, action)`. It does not fetch, interpret, or mutate external policy.

**What is incomplete**: The "governance constitution" is currently a code-level constant (`PolicySnapshot` with hardcoded `policy_id`, `policy_version`), not an externally loaded, independently versioned, and separately deployable policy artifact. The signing key (`POLICY_SIGNING_KEY`) defaults to a static string. In production, this would need to be a rotatable secret managed by an external secrets store.

---

## 3. Runtime Role

### 3.1 Core Components

| Component | File | Role |
|---|---|---|
| Agent Runtime | [agent_runtime.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/agent_runtime.py) | Main FSM loop coordinator |
| Decision Provider | [agent_runtime.py:L59](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/agent_runtime.py#L59) | Abstract decision source interface |
| HTTP Decision Provider | [agent_runtime.py:L65](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/agent_runtime.py#L65) | Production HTTP-based decision engine |
| Policy Engine | [deterministic_policy_engine.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/deterministic_policy_engine.py) | HMAC-signed policy admission gate |
| Semantic Guard | `semantic_guard_engine.py` | FSM transition sequencing constraints |
| Action Governance | [action_governance.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/core/action_governance.py) | Cooldowns, eligibility, repetition suppression |
| Legitimacy Doctrine | [legitimacy_doctrine.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/legitimacy_doctrine.py) | Deterministic legitimacy evaluator |

### 3.2 Decision Path

```text
Runtime Payload (canonical schema)
   │
   ├── InputValidator (schema check)
   ├── RuntimeEventValidator (envelope check)
   │
   ├── DeterministicPolicyEngine.admit()
   │      ├── sig_valid / nonce_valid check
   │      ├── trace_valid check
   │      ├── schema_valid check
   │      ├── GovernanceContract signature verification
   │      ├── DecisionContract validation
   │      └── LegitimacyDoctrine.compute() → legitimacy, state, action
   │
   ├── ActionGovernance.evaluate_action()
   │      ├── Eligibility check (env-scoped)
   │      ├── Cooldown check
   │      ├── Repetition suppression
   │      └── Returns GovernanceDecision with legitimacy
   │
   └── DecisionProvider.decide() → action
          ├── HTTPDecisionProvider (production: RL brain)
          └── LocalRuleDecisionProvider (test: in-process)
```

### 3.3 Runtime Topology

| Process | Default Port | Technology |
|---|---|---|
| Control Plane API | 7000 | Flask |
| FastAPI Decision Backend | 8000 | FastAPI |
| RL Decision Brain | 8008 | External RL service |
| Redis Event Bus | 6379 | Redis (AOF mode) |
| Action Executor | 5003 | Flask |
| Observability Monitor | 5004 | Flask + SSE |
| Dashboard Frontend | 4500 | Next.js |

---

## 4. Deployment Role

### 4.1 Boot Sequence

1. `deploy_pravah.py` initializes environment and validates dependencies.
2. `StartupValidator` confirms persistence files, Redis connectivity, and core module availability.
3. `ReadinessValidator` verifies journal integrity and replay index state.
4. `RecoveryValidator` replays journal events, verifies hash chains, and compares state hashes against snapshots.
5. Only after all validators pass does the runtime accept incoming traffic.

### 4.2 Deployment Artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Append-Only Journal | `logs/control_plane/append_only_log.jsonl` | Immutable event lineage |
| Replay Index | `logs/control_plane/replay_index.json` | Indexed event boundaries |
| Snapshot Registry | `logs/control_plane/snapshot_registry.json` | State hash snapshots |
| Governance State | `logs/control_plane/governance_state.json` | Cooldown/repetition state |
| Policy Enforcement Log | `logs/control_plane/policy_enforcement.jsonl` | Audit trail of all admission decisions |
| Deployment Proof Packet | `deployment_verification_packet/` | Startup, readiness, recovery validation logs |

### 4.3 Honest Deployment Assessment

**What works**: Boot-time validation is real. `RecoveryValidator` loads actual journal events, runs hash chain verification through `HashLineageVerifier`, delegates signature checks to `LineageVerifier.verify_lineage_signatures()`, and compares state hashes against snapshots. If any check fails, the system blocks startup.

**What is incomplete**: Deployment is currently single-node. The governance state file (`governance_state.json`) is filesystem-local. In a multi-replica deployment, this causes split-brain governance. Redis is used for event bus but not for governance state synchronization.

---

## 5. Replay Doctrine

### 5.1 Replay Architecture

| Component | File | Responsibility |
|---|---|---|
| Append-Only Log | [append_only_log.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/persistence/append_only_log.py) | Immutable, hash-chained event persistence |
| Hash Lineage Verifier | [hash_lineage_verifier.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/persistence/hash_lineage_verifier.py) | Sequence continuity + hash chain verification |
| Lineage Verifier | [lineage_verifier.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/security/lineage_verifier.py) | Cryptographic signature + duplicate + timestamp verification |
| Replay Index | [replay_index.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/persistence/replay_index.py) | Execution boundary lookup |
| Recovery Validator | [recovery_validator.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/deployment/recovery_validator.py) | Boot-time recovery verification |

### 5.2 Replay Verification Chain

```text
Journal Events
   ├── verify_sequence_continuity() → sequence gaps?
   ├── verify_hash_chain() → hash chain intact?
   ├── verify_lineage_signatures() → cryptographic signatures valid?
   ├── ReplayIndex → event count match? last hash match?
   ├── SnapshotRegistry → state hash match?
   └── LegitimacyDoctrine.compute() → legitimacy outcome
```

### 5.3 Replay Error Classification

| Error | Exception/Flag | Doctrine Outcome |
|---|---|---|
| Unsigned event | `UnsignedReplayEventError` | `ILLEGITIMATE` |
| Payload hash mismatch | `PayloadHashMismatchError` | `ILLEGITIMATE` |
| Lineage break | `LineageBreakError` | `ILLEGITIMATE` |
| Sequence violation | `SequenceViolationError` | `ILLEGITIMATE` |
| Duplicate replay | `DuplicateReplayError` | `ILLEGITIMATE` |
| Timestamp sanity | `TimestampSanityError` | `ILLEGITIMATE` |
| Index event count mismatch | `replay_index_event_count_mismatch` | `LEGITIMATE_AMBIGUOUS` |
| Partial replay gap | Sequence gap detected | `LEGITIMATE_AMBIGUOUS` |

### 5.4 Honest Replay Assessment

**What works**: The replay chain is cryptographically anchored. Events are hash-chained, signed (HMAC-SHA256), and verified for sequence continuity, duplicate detection, and timestamp sanity. The `LineageVerifier.verify_replay_chain()` method enforces the full chain in a single pass.

**What is weak**: Replay reconstruction during partial gaps does not attempt forward repair or quorum-based reconciliation. It halts. This is safe but operationally conservative — a production system might want configurable partial-replay policies.

---

## 6. Boundary Model

### 6.1 Enforcement Gate Order

```text
1. Manual freeze check
2. Emergency freeze check
3. Illegal action check
4. Demo intake gate
5. Demo safety gate
6. Environment allowlist
7. Action Governance (eligibility → cooldown → repetition)
8. DeterministicPolicyEngine admission
9. SemanticGuardEngine transition validation
```

### 6.2 Environment Boundaries

| Environment | Allowed Actions |
|---|---|
| `prod` | `noop`, `restart` |
| `stage` | `restart`, `noop`, `scale_up`, `scale_down` |
| `dev` | `restart`, `scale_up`, `noop`, `scale_down`, `rollback` |

### 6.3 Cryptographic Boundaries

| Boundary | Mechanism |
|---|---|
| Service authentication | HMAC-SHA256 signature on `X-Service-Id`, `X-Service-Timestamp`, `X-Service-Nonce`, `X-Service-Signature` headers |
| Governance contract integrity | HMAC-SHA256 signature over canonical JSON of contract material |
| Replay event integrity | Per-event HMAC signature + hash chain + payload hash |
| Nonce replay prevention | `NonceStore` with persistent `nonce_store.json` |
| Trace consumption dedup | `trace_consumption.json` tracking consumed trace IDs |

---

## 7. Failure Doctrine

### 7.1 Deterministic Failure Matrix

| Condition | sig_valid | trace_valid | schema_valid | key_deps | Legitimacy | Runtime State | Action |
|---|---|---|---|---|---|---|---|
| Signature failure | ✗ | — | — | — | `ILLEGITIMATE` | `BLOCKED` | `REJECT` |
| Trace corruption | ✓ | ✗ | — | — | `ILLEGITIMATE` | `BLOCKED` | `HALT` |
| Schema mismatch | ✓ | ✓ | ✗ | — | `ILLEGITIMATE` | `BLOCKED` | `REJECT` |
| Missing DB/Index | ✓ | ✓ | ✓ | `MISSING_DB_INDEX` | `LEGITIMATE_AMBIGUOUS` | `HALTED` | `HALT` |
| Partial replay gap | ✓ | ✓ | ✓ | `PARTIAL_REPLAY_GAP` | `LEGITIMATE_AMBIGUOUS` | `HALTED` | `REPLAY_ONLY` |
| Redis/RL unavailable | ✓ | ✓ | ✓ | `RL_UNAVAILABLE` | `LEGITIMATE_DEGRADED` | `DEGRADED` | `DEGRADED_ALLOWED` |
| All healthy | ✓ | ✓ | ✓ | `ALL_AVAILABLE` | `LEGITIMATE_VALID` | `ACTIVE` | `EXECUTE` |

This matrix is implemented as a single deterministic function:
[LegitimacyDoctrine.compute()](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/legitimacy_doctrine.py#L82)

### 7.2 Failure Propagation Path

```text
Failure detected (sig/trace/schema/deps)
   │
   ├── LegitimacyDoctrine.compute() → legitimacy, state, action
   │
   ├── PolicyAdmissionDecision.legitimacy = legitimacy
   │   PolicyAdmissionDecision.doctrine_inputs = audit evidence
   │
   ├── GovernanceDecision.legitimacy = legitimacy
   │
   ├── RecoveryValidationResult.legitimacy = legitimacy
   │   RecoveryValidationResult.doctrine_inputs = audit evidence
   │
   └── AgentRuntime → transition to BLOCKED or log degraded mode
```

### 7.3 Silent Continuation Prevention

The hostile test suite verified zero silent continuations across all 10 hostile scenarios. Every failure produces:
- An explicit legitimacy outcome
- Auditable `doctrine_inputs`
- A visible runtime state transition
- A logged action (REJECT / HALT / DEGRADED_ALLOWED / REPLAY_ONLY / EXECUTE)

Evidence: [hostile_runtime_results.log](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/proofs/phase8/hostile_runtime_results.log)

---

## 8. Constitutional Safeguards

### 8.1 Implemented Safeguards

| Safeguard | Implementation | Status |
|---|---|---|
| **FSM transition enforcement** | `AgentStateManager.VALID_TRANSITIONS` raises `ValueError` on invalid transitions | ✅ Verified |
| **Signed governance contracts** | `GovernanceContract` with HMAC signature, immutability flag, trusted signer check | ✅ Verified |
| **Policy version alignment** | `DeterministicPolicyEngine` rejects `policy_version != runtime_policy_version` | ✅ Verified |
| **Nonce replay prevention** | `NonceStore` with persistent JSON tracking | ✅ Verified |
| **Trace consumption dedup** | `trace_consumption.json` blocks duplicate trace IDs | ✅ Verified |
| **Environment action scoping** | Hardcoded allowlists per environment in `ActionGovernance._eligibility_rules` | ✅ Verified |
| **Cooldown enforcement** | Time-based cooldown per action type with configurable periods | ✅ Verified |
| **Repetition suppression** | Sliding window counter with configurable limit (default 3 in 300s) | ✅ Verified |
| **Cryptographic lineage** | Hash-chained events with per-event HMAC signatures | ✅ Verified |
| **Boot-time recovery check** | `RecoveryValidator` blocks startup on hash mismatch | ✅ Verified |
| **Legitimacy doctrine separation** | `LegitimacyDoctrine` is a pure evaluator, not a policy definer | ✅ Verified |
| **DecisionProvider abstraction** | Runtime decoupled from HTTP transport; injectable decision source | ✅ Verified |
| **Signature delegation** | `RecoveryValidator` delegates to `LineageVerifier.verify_lineage_signatures()` | ✅ Verified |

### 8.2 Safeguards NOT Yet Implemented

| Safeguard | Gap | Risk |
|---|---|---|
| **External policy store** | Policies are code-level constants, not externally loaded and versioned artifacts | Medium — policy changes require code deployment |
| **Key rotation** | `POLICY_SIGNING_KEY` and `SECRET_KEY` are static environment variables with hardcoded defaults | High — compromised key has no rotation path |
| **Multi-node governance sync** | Governance state is filesystem-local | High in multi-replica deployments |
| **Formal constitutional document** | The "constitution" is distributed across code comments and markdown files, not a single canonical artifact | Medium — interpretive drift risk |
| **External audit log sink** | All logs are local filesystem; no external SIEM or audit log pipeline | Medium — logs can be lost with node failure |

---

## 9. Open Risks

### 9.1 Critical Risks

| # | Risk | Current Mitigation | Residual Exposure |
|---|---|---|---|
| 1 | **Static signing keys** | Environment variable override available | Default key is a plaintext string in source code. Any attacker with code access can forge governance contracts. |
| 2 | **Single-node governance** | Filesystem persistence with thread locks | Split-brain governance in multi-replica deployment. Cooldowns and repetition limits will not be shared across nodes. |
| 3 | **No external policy versioning** | Policy defined in code | Policy changes require full deployment cycle. No independent policy lifecycle management. |

### 9.2 Significant Risks

| # | Risk | Current Mitigation | Residual Exposure |
|---|---|---|---|
| 4 | **Local-only audit logs** | Filesystem JSONL logs | Node failure destroys audit trail. No external sink for compliance or forensics. |
| 5 | **Docker scaling simulation** | Documented in `KNOWN_LIMITATIONS.md` | Scale actions in Docker mode are logged but not executed. Production scaling requires Kubernetes executor. |
| 6 | **Trace sequence interleaving** | `reset_trace()` on each request | Concurrent requests in multi-worker uvicorn can interleave trace sequences. |
| 7 | **Hardcoded monitor targets** | Static dictionary in monitor app | Adding services requires code changes. No dynamic service discovery. |

### 9.3 Low Risks

| # | Risk | Current Mitigation | Residual Exposure |
|---|---|---|---|
| 8 | **Stale bytecode** | Verified source code is authoritative | Self-transition warnings observed from stale `.pyc` files. Not a runtime logic defect. |
| 9 | **Duplicate import** | `from unittest import result` imported twice in `agent_runtime.py` | No functional impact. Code hygiene issue. |

---

## 10. Acceptance Readiness Score

### Scoring Criteria

| Dimension | Weight | Score (0-10) | Evidence |
|---|---|---|---|
| **FSM Correctness** | 15% | **9** | Enumerated transitions, `ValueError` on invalid paths, 10/10 hostile tests pass |
| **Cryptographic Integrity** | 15% | **8** | HMAC signing, hash chains, signature verification delegated to `LineageVerifier`. Static default keys reduce score. |
| **Legitimacy Architecture** | 15% | **9** | Pure evaluator pattern, `DependencyCondition` enum, runtime owns legitimacy, doctrine separation enforced |
| **Failure Handling** | 10% | **9** | Deterministic failure matrix, zero silent continuations, all failures produce auditable doctrine_inputs |
| **Replay Correctness** | 10% | **8** | Full chain verification (sequence, hash, signature, duplicate, timestamp). No quorum-based repair. |
| **Governance Separation** | 10% | **7** | Negative authority locks documented, but constitutional policy is code-embedded, not externally governed |
| **Deployment Maturity** | 10% | **6** | Boot validators work, single-node only, local-only logs, no SIEM integration |
| **Production Readiness** | 10% | **5** | No key rotation, no multi-node sync, Docker scaling simulated, no external policy store |
| **Documentation** | 5% | **8** | Extensive Phase 8 proofs, authority matrices, doctrine documents. Some doc drift from code reality. |

### Weighted Score

```text
FSM:          0.15 × 9 = 1.35
Crypto:       0.15 × 8 = 1.20
Legitimacy:   0.15 × 9 = 1.35
Failure:      0.10 × 9 = 0.90
Replay:       0.10 × 8 = 0.80
Governance:   0.10 × 7 = 0.70
Deployment:   0.10 × 6 = 0.60
Production:   0.10 × 5 = 0.50
Documentation:0.05 × 8 = 0.40
                        ─────
Total:                  7.80 / 10
```

**Acceptance Readiness Score: 7.8 / 10**

---

## 11. Honest Maturity Classification

### Classification: **Late Prototype / Early Production-Candidate**

This system is not a prototype. It has real enforcement, real cryptographic chains, real failure handling, and real hostile validation. However, it is not production-ready.

### What Justifies This Classification

**Mature (production-grade in single-node, controlled environments)**:
- FSM with enumerated, enforced transitions
- Deterministic legitimacy computation with zero policy-definition leakage
- Cryptographic event lineage with hash chains and HMAC signatures
- 10/10 hostile scenario pass rate with zero silent continuations
- DecisionProvider abstraction decoupling runtime from transport
- Negative authority locks with structural enforcement
- Boot-time recovery validation with hash comparison

**Not Yet Mature (gaps that block real production deployment)**:
- Signing keys are static defaults, not rotatable secrets
- Governance state is filesystem-local with no distributed coordination
- No external policy store; policies are code-embedded constants
- No audit log pipeline to external SIEM or compliance system
- Docker scaling is simulated, not physical
- No formal external constitutional document separate from codebase
- No automated key compromise response procedure

### What This System IS

A structurally sound, architecturally principled runtime control plane with real cryptographic enforcement, deterministic failure handling, and verifiable hostile-condition resilience. It is ready for:
- Controlled single-node deployments
- Development and staging environments
- Demonstration and architectural validation
- Further hardening toward production

### What This System IS NOT

A production-hardened, multi-tenant, distributed control plane with key rotation, external governance, audit compliance pipelines, and horizontal scaling. Those capabilities require additional engineering phases.

---

*End of Pravah Sovereign Dossier — Phase 8*
