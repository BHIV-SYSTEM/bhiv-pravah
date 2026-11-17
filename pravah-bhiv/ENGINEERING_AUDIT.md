# BHIV Pravah — Deep Engineering Audit

> **Evidence Standard**: All findings derive from direct source-code inspection, call-chain tracing, and live test execution (pytest 9.0.2 / Python 3.14.3 / Windows). Documentation claims are explicitly distinguished from verified code behaviour.
> **Last Updated**: 2026-08-22. Changes since initial audit are marked **[UPDATED]** or **[NEW]**.

---

## 0. Repository File Structure

> Captured from live filesystem. __pycache__ and .pyc files omitted.

```
pravah-bhiv/                                        <- REPO ROOT
+-- ENGINEERING_AUDIT.md
+-- PHASE12_CROSS_GROUP_CONTRACT_AUDIT.md           <- Cross-group schema (INCOMPATIBLE verdict)
+-- PHASE13_EXTERNAL_CONTRACT_REQUIREMENTS.md
+-- CAPABILITY_REGISTRY.md / DECISION_TRANSLATION_BOUNDARY.md
+-- EXECUTION_RIGHTS_MAPPING_STATUS.md / GROUP1_RUNTIME_VERIFICATION.md
+-- GROUP4_DEPENDENCY_MATRIX.md / GROUP4_INTEGRATION_STATUS.md
+-- PRODUCTION_DEPLOYMENT.md                        <- [NEW] Yotta bare-metal deployment guide
+-- walkthrough.md                                  <- [NEW] Integration walkthrough (4 observed systems)
+-- yotta-deploy.yaml / pravah.service              <- [NEW] Yotta manifest + systemd unit
+-- docker-compose.production.template.yml          <- [NEW]
+-- render.yaml
+-- multi.txt                                       <- STILL COMMITTED -- 3.6 MB artifact (DELETE)
+-- trace_log.jsonl / runtime_rl_proof.log          <- COMMITTED LOG FILES
+-- GROUP4_FINAL_CLOSURE/                           <- [NEW] Phase 16 evidence package
    GROUP4_CLOSURE_REPORT.md (15/15 PASS)
    ACTION_REQUEST/ IDEMPOTENCY/ INPUT/ RETRIEVAL/ TESTS/ TRANSFORMATION/ VALIDATION/ UI/

backend/
|-- agent_runtime.py                                <- Flask runtime (port 7000) [52 KB]
|-- autonomy_loop.py                                <- 904 bytes -- not connected to main path
|-- observer_server.py                              <- Observer server (~44 KB, port 8600)
|-- config.py / wsgi.py
|-- requirements.txt                                <- numpy<2.0.0 -- STILL BREAKS on Python 3.14
|-- docker-compose.yml                              <- [UPDATED] 500 lines; 9 services
|-- Dockerfile / Procfile
|-- trace_log.jsonl / payload_integrity.log / executer.log  <- COMMITTED LOG FILES
|-- mcp_inbox.json / mcp_messages.json / mcp_outbox.json    <- EMPTY [] -- stale
|-- test_execution_flow.py / _local_simulation.py / generate_group4_closure.py  <- [NEW]
|-- (30+ Markdown phase-report .md files -- documentation debt)
|
|-- contracts/                                      <- PRESERVE -- Pydantic v2 models
|   decision_contract.py / execution_contract.py / execution_state.py
|   policy_snapshot.py / runtime_attestation.py / runtime_contract.py
|   semantic_transition_validator.py
|
|-- control_plane/                                  <- CORE SYSTEM
|   |-- multi_app_control_plane.py / app_override_manager.py
|   |-- apps/registry/*.json                        <- [UPDATED] 49 registered apps (was 28)
|   |
|   |-- decision_translation/                       <- [NEW] Phase 15-16 translation boundary
|   |   |-- contextual_result_adapter.py            <- GAP/ALLOW/ADAPT -> DecisionContract
|   |   |-- governed_abstention_recorder.py         <- Writes GOVERNED_ABSTENTION to log
|   |   |-- group4_intake.py                        <- Group4IntakeBoundary + ActionRequestRecorder
|   |   `-- vana_integration.py
|   |
|   |-- backend/app/
|   |   |-- main.py                                 <- 1300 LINES -- all routes still here
|   |   |-- decision_engine.py                      <- PRESERVE -- pure function, correct
|   |   |-- runtime_adapter.py                      <- STILL BROKEN -- NameError (decision at L74)
|   |   |-- execution_simulator.py                  <- DELETE -- dead code
|   |   |-- config.py                               <- CPU_SCALE_UP_THRESHOLD=95 (IGNORED)
|   |   |-- integration_bridge.py / schemas.py / dashboard_api.py / runtime.py
|   |   `-- app_registry.py                         <- [NEW]
|   |
|   |-- capabilities/
|   |   |-- execution_rights_adapter.py             <- DO NOT TOUCH -- VERIFIED_CAPABILITY_MAPPINGS
|   |   |-- capability_registry_manager.py / capability_discovery.py
|   |   |-- capability_schema.py / capability_types.py  <- [NEW]
|   |   |-- test_execution_rights_adapter.py        <- [NEW] 15 KB
|   |   `-- registry/                               <- 8 capability JSON defs
|   |       governed-execution.json (only one with execution mapping)
|   |       vana-environmental_observation.json (mapping exists; BLOCKED by governance)
|   |       (6 others -- NO execution rights)
|   |
|   |-- core/
|   |   |-- action_governance.py                    <- DO NOT TOUCH -- 734 lines
|   |   |-- execution_lineage.py                    <- DO NOT TOUCH -- signed hash-chain
|   |   |-- trace_logger.py                         <- RACE CONDITION -- _last_stage global
|   |   |-- redis_event_bus.py                      <- DISCONNECTED
|   |   |-- redis_demo_behavior.py / redis_stability.py  <- [NEW]
|   |   |-- rl_orchestrator_safe.py                 <- SIGNATURE CHANGED -- breaks Phase 8 tests
|   |   `-- (50+ other modules)
|   |
|   |-- security/
|   |   |-- deterministic_policy_engine.py          <- DO NOT TOUCH -- 668 lines
|   |   `-- semantic_guard_engine.py / legitimacy_doctrine.py
|   |
|   |-- persistence/                                <- PRESERVE
|   |   append_only_log.py / hash_lineage_verifier.py / replay_index.py
|   |
|   |-- executor/                                   <- [UPDATED]
|   |   |-- executor.py                             <- 9.8 KB -- labelled LEGACY
|   |   |-- safe_executor.py                        <- SIGNATURE CHANGED -- breaks P8 tests
|   |   `-- governance_gate.py
|   |
|   `-- agents/ api/ ml/ telemetry/ deployment/ config/
|
|-- security/
|   |-- signed_trace.py                             <- DO NOT TOUCH -- HMAC, default keys
|   |-- signing.py / internal_requests.py
|   `-- nonce_store.py / nonce_store.json           <- file-based (race condition)
|
|-- executer/ sarathi/ pravah_stream/ core_hooks/
|
|-- monitoring/ orchestrator/ runtime/ rl/          <- [NEW]
|-- integration/                                    <- [NEW] group2/fixtures/
|-- environments/ evidence/ scripts/                <- [NEW]
|
|-- tests/
|   |-- test_phase8_execution_closure.py            <- [UPDATED] NOW FAILS 5/5
|   |-- test_phase14_vana_bootstrap.py              <- PASSED 7/7
|   |-- test_phase10_group1_integration.py          <- PASSED 1/1 (live)
|   |-- test_unified_discovery.py                   <- STILL FAILS (assert 0 == 8)
|   |-- test_phase15_gap_governed_abstention.py     <- [NEW] PASSED 21/21
|   |-- test_phase16_group4_action_request.py       <- [NEW] PASSED 15/15
|   |-- test_group4_final_lineage_closure.py        <- [NEW] PASSED 16/16
|   |-- test_phase15_integration_boundary.py        <- [NEW]
|   |-- adversarial_test_suite/                     <- [NEW]
|   `-- (phase 1-6, replay, semantic tests)
|
`-- frontend/                                       <- Next.js 14 + Tailwind CSS dashboard
    src/services/api.ts                             <- Axios client (ports 8000, 7000, 8600)
```

### Key Counts [UPDATED]
| Item | Count |
|------|-------|
| Registered applications (apps/registry/) | **49** (was 28) |
| Registered capabilities (capabilities/registry/) | 8 (unchanged) |
| Capabilities with execution rights mappings | 2 (unchanged) |
| Test files (total) | **17+** (was 13) |
| Collected test items (latest run) | **74** |
| Passing / Failing | **58 / 6** (5 Phase8 + 1 unified discovery) |
| Lines in main.py | **1300** (was 1401) |
| Lines in action_governance.py | 734 (unchanged) |
| Lines in deterministic_policy_engine.py | 668 (unchanged) |
| Committed log files | 4+ (unchanged) |
| New modules (decision_translation/) | 4 files |
| Docker Compose services | **9** (was 5) |
| Prometheus integration | YES (new) |

---

## 1. Executive Summary

**Overall Maturity: Early-Integration / Pre-Production [UNCHANGED]**

| Domain | Assessment |
|--------|-----------|
| Overall maturity | Early-Integration -- not production-ready |
| End-to-end control loop | **OPEN-LOOP** -- ingest->decision->governance VERIFIED; execution **ALWAYS FAILS** |
| Security posture | HMAC-chain solid; zero API authentication -- CRITICAL gap unchanged |
| Test suite | **[UPDATED]** P15/P16/Group4 all pass; P8 regressed; unified discovery still broken |
| Decision translation boundary | **[NEW]** GAP->noop abstention fully tested and working |
| External observability | **[NEW]** 4 external systems observed |

**Biggest Strengths [UPDATED]**
- ActionGovernance + DeterministicPolicyEngine -- cryptographic, deterministic, well-engineered
- ExecutionRightsAdapter -- properly fail-closed with evidence-based capability mappings
- AppendOnlyLog + execution_lineage.py -- real signed hash-chain integrity
- DecisionEngine.decide() -- pure stateless function, fully correct
- **[NEW]** ContextualResultAdapter + GovernedAbstentionRecorder -- deterministic, safety-invariant
- **[NEW]** Group4IntakeBoundary -- idempotent, lineage-preserving action request intake
- **[NEW]** 49-app registry + 4-system external observability

**Top Risks [UPDATED]**
1. **Executor always fails** -- main.py:661 POSTs to localhost:5003; no service there
2. **Phase 8 test regression** -- 5/5 previously-passing tests now fail (signature mismatch)
3. **No API authentication** -- all endpoints completely open
4. **runtime_adapter.py NameError** -- decision used at L74, set is commented out at L68
5. **test_unified_discovery.py STILL FAILS** -- assert 0 == 8
6. **VANA trust gap** -- passes execution rights but governance blocks it

---

## 2. Actual Control Loop (Verified) [UPDATED]

```
POST /control-plane/runtime-ingest
  |
  v
RuntimeIngestPayload (Pydantic) -> INGESTED_RUNTIME_STATE[service_id]  [IN-MEMORY]
  |
  v
DecisionEngine.decide()  [PURE FUNCTION, CORRECT]
  |
  v
execute_action(action, service_id)  [main.py:608]
  |
  v
ActionGovernance.evaluate_contract()  [VERIFIED]
  | trusted_signers = {sarathi, governance, policy-authority}
  | source "backend_api" NOT IN SET -> ALWAYS BLOCKED HERE
  | (VANA also not in set; cooldown/repetition/policy gate also apply)
  |
  v (unreachable from runtime-ingest -- source "backend_api" always blocked)
requests.post("http://localhost:5003/execute-action")
  |
  X  ConnectionRefusedError ALWAYS -- NO SERVICE ON PORT 5003
  |
  v
Exception -> (False, str(exception))  [ACTION SILENTLY DROPPED]

[NEW] Parallel path: Group 2 ALLOW ruling -> ContextualResultAdapter
  -> Group4IntakeBoundary.process() -> ActionRequest("VALIDATED")
  -> append_only_log [VERIFIED, NO operational execution triggered]
```

**VERDICT: OPEN-LOOP. Execution always fails at two layers.**

> **[NEW CRITICAL FINDING]**: `execute_action()` calls governance with `source="backend_api"`. This is NOT in `trusted_signers`. Every non-noop action is **governance-blocked before reaching localhost:5003**. Port 5003 is a secondary failure.

---

## 3. Control Loop Step-by-Step Evidence [UPDATED]

| Stage | File:Line | Status | Evidence |
|-------|-----------|--------|---------| 
| Ingestion | main.py:1089 | VERIFIED | Pydantic schema validated |
| Runtime state | main.py:1101 | PARTIAL | In-memory dict, lost on restart |
| Decision | decision_engine.py:20 | VERIFIED | Pure function; CPU threshold bug |
| Execution rights | execution_rights_adapter.py:203 | VERIFIED | Phase 14 PASSED |
| Governance | action_governance.py:293 | VERIFIED | Crypto sig; source "backend_api" NOT trusted |
| Executor dispatch | main.py:661 | **BROKEN** | localhost:5003 -- no service |
| Execution result | -- | **NOT IMPLEMENTED** | No feedback |
| State update | -- | **NOT IMPLEMENTED** | No post-exec state update |
| Telemetry feedback | -- | **NOT IMPLEMENTED** | No loop closure |
| **[NEW]** Group2->Group4 translation | decision_translation/ | **VERIFIED** | P15+16 PASSED 36/36 |
| **[NEW]** Group4 Action Request intake | decision_translation/group4_intake.py | **VERIFIED** | Closure PASSED 16/16 |

---

## 4. Trace Sovereignty Matrix [UNCHANGED]

| Claim | Code Location | Status |
|-------|--------------|--------|
| Traces HMAC-signed | signed_trace.py:41 | VERIFIED |
| Signature verified before execution | action_governance.py:332-336 | VERIFIED |
| Unsigned authorization rejected | action_governance.py:320 | VERIFIED |
| LINEAGE_SIGNING_KEY required in prod | signed_trace.py:14 | VERIFIED |
| Default dev key hardcoded | signed_trace.py:16 | SECURITY RISK |
| Nonce replay protection | executer/guard.py:33 | VERIFIED (not in main path) |
| Two disconnected trace systems | trace_logger.py vs execution_lineage.py | FRAGMENTATION |
| No trace_id in ingest payload | RuntimeIngestPayload schema | UNTRACED |

trace_logger.py: module-global `_last_stage = None` -- RACE CONDITION under concurrent requests.

---

## 5. Decision Engine Audit [UNCHANGED]

| Decision | Trigger | Config Read? | Status |
|---------|---------|-------------|--------|
| scale_up | cpu >= 90 (HARDCODED) | NO -- config.py says 95 | **BUG** |
| scale_down | cpu < 30 | YES | CORRECT |
| scale_up (mem) | memory > 85 | YES | CORRECT |
| noop | no threshold | -- | CORRECT |
| env override | action not in ACTION_SCOPE[env] | YES | CORRECT |

---

## 6. Capability Mapping Coverage [UNCHANGED]

| Capability | Execution Rights Mapping | Can Execute? |
|-----------|------------------------|-------------|
| governed-execution | YES (source_id: governance) | NO (governance blocks "backend_api"; port 5003 fails) |
| vana-environmental_observation | YES (source_id: VANA) | **NO -- VANA not in trusted_signers** |
| group1-observation-api | **NO** | NO |
| group2-scientific-context | **NO** | NO |
| group3-field-edge | **NO** | NO |
| bucket-evidence | **NO** | NO |
| replay-runtime | **NO** | NO |
| svacs-runtime | **NO** | NO |

6 of 8 capabilities cannot execute. `execute_action()` calls governance with `source="backend_api"`, which is also not in trusted_signers, so even `governed-execution` is blocked before port 5003.

---

## 7. API & Endpoint Audit [UPDATED]

All endpoints: ZERO authentication required.

| Endpoint | Status |
|----------|--------|
| POST /control-plane/runtime-ingest (main.py:1089) | ACTIVE, unauthenticated |
| POST /process-runtime (main.py:1038) | ACTIVE, disconnected from governance |
| GET /live-dashboard | PARTIAL -- real psutil + git data + synthetic ML |
| GET /autonomous-status | MOCK -- loop_running:True hardcoded |
| POST /pravah/events | PLACEHOLDER -- does nothing |
| POST /api/control-plane/override | **STILL BROKEN -- route not implemented** |
| GET /api/lineage/:id | REAL -- reads signed JSONL |
| GET /control-plane/apps | REAL -- reads registry JSON |
| GET /api/health | REAL |
| POST /ingest-link | **[NEW]** ACTIVE -- in-memory link monitoring |
| POST /remove-link | **[NEW]** ACTIVE |
| GET /orchestration/metrics | **[NEW]** ACTIVE |
| GET /metrics | **[NEW]** ACTIVE -- psutil |
| GET /dashboard/state | **[NEW]** ACTIVE |
| POST /evidence / GET /evidence/{ref} | **[NEW]** ACTIVE -- in-memory |
| GET /api/ml/features/latest | **[NEW]** ACTIVE |

frontend/src/services/api.ts:146 calls POST /api/control-plane/override -- gets 404. Still unimplemented.

---

## 8. Broken Functionality (Evidence-Based) [UPDATED]

### P0: Executor dispatch always fails (localhost:5003)
- main.py:661: `requests.post("http://localhost:5003/execute-action")`
- docker-compose.yml: 9 services defined -- port 5003 still NOT DEFINED ANYWHERE
- **[NEW]**: Governance blocks `source="backend_api"` before port 5003 is reached

### P0: runtime_adapter.py NameError [UNCHANGED]
- Line 68 COMMENTED OUT: `# decision = DecisionEngine.decide(decision_request)`
- Lines 74+: `decision.selected_action` -- NameError at runtime
- runtime_decision_cycle() and run_autonomous_control_plane() both crash

### P0: No API authentication [UNCHANGED]
- No auth middleware, no JWT, no API key on any route

### P0 [NEW]: Phase 8 test regression
- test_phase8_execution_closure.py -- all 5 previously-passing tests now FAIL
- `execute_action()` refactored; test uses old `requested_capability` kwarg -- TypeError
- `SafeOrchestrator.__init__()` no longer accepts `execution_mode` kwarg -- TypeError

### P1: VANA blocked by governance trust model [UNCHANGED]
- execution_rights_adapter.py: authorized_source_id = "VANA"
- deterministic_policy_engine.py:143: trusted_signers excludes VANA

### P1: test_unified_discovery.py STILL FAILS [UNCHANGED]
- assert 0 == 8 -- list_runtime_entities() returns 0 capabilities from test context

### P1: Override endpoint still missing [UNCHANGED]
- frontend calls POST /api/control-plane/override -- main.py has no handler

### P2: CPU threshold config bug [UNCHANGED]
- config.py: CPU_SCALE_UP_THRESHOLD = 95; decision_engine.py: hardcodes >= 90

### P2: Module-global race condition in trace_logger [UNCHANGED]
- `_last_stage = None` -- module global, corrupted by concurrent requests

### P2 [NEW]: "backend_api" not in trusted_signers
- execute_action() in main.py:634: `source="backend_api"`
- Every non-noop is governance-blocked independently of port 5003

---

## 9. Data & Persistence [UPDATED]

| Data | Persistent? | Signed? | Race-safe? |
|------|------------|---------|-----------|
| INGESTED_RUNTIME_STATE | NO -- in-memory | No | No |
| _RECENT_DECISIONS deque | NO -- in-memory | No | No |
| decision_history.jsonl | YES | No | Partial |
| execution_lineage.jsonl | YES | YES (HMAC) | YES (locked) |
| governance_state.json | YES | No | YES (locked) |
| append_only_log.jsonl | YES | YES (HMAC) | YES (locked) |
| trace_log.jsonl | YES (in CWD!) | No | NO (module global) |
| pravah_stream buffer | NO -- in-memory | No | YES (locked) |
| **[NEW]** _INGESTED_LINKS | NO -- in-memory | No | No |
| **[NEW]** _EVIDENCE_STORE | NO -- in-memory | No | No |
| **[NEW]** GovernedAbstentionRecorder | YES (append_only_log) | YES (HMAC) | YES |

Redis declared in docker-compose; redis_event_bus.py exists; Redis NOT used in main path.

---

## 10. Security Audit [UPDATED]

| Finding | Severity | Evidence |
|---------|---------|---------| 
| No authentication on any endpoint | CRITICAL | No auth middleware in main.py |
| Default HMAC keys in dev/stage | HIGH | signed_trace.py:16 |
| VANA not in trusted_signers | MEDIUM | deterministic_policy_engine.py:143 |
| "backend_api" not in trusted_signers | MEDIUM | main.py:634 |
| Executor port hardcoded | MEDIUM | main.py:661 localhost:5003 |
| Nonce store is a JSON file | MEDIUM | security/nonce_store.json -- not atomic |
| CORS allows all localhost ports | LOW | main.py:108 |

---

## 11. Test Suite Results [UPDATED]

| Test File | Items | Result | Notes |
|-----------|-------|--------|-------|
| test_phase8_execution_closure.py | 5 | **FAILED 5/5 -- REGRESSION** | Signatures changed |
| test_phase14_vana_bootstrap.py | 7 | PASSED 7/7 | |
| test_phase10_group1_integration.py | 1 | PASSED (requires live service) | |
| test_unified_discovery.py | 1 | **FAILED** | assert 0 == 8 |
| **[NEW]** test_phase15_gap_governed_abstention.py | 21 | **PASSED 21/21** | GAP->noop; safety invariant |
| **[NEW]** test_phase16_group4_action_request.py | 15 | **PASSED 15/15** | ALLOW->ActionRequest; idempotency |
| **[NEW]** test_group4_final_lineage_closure.py | 16 | **PASSED 16/16** | End-to-end lineage closure |

**Total: 74 collected, 58 passed, 6 failed.**

---

## 12. Feature Maturity Matrix [UPDATED]

| Feature | Exists | Integrated | Working | Prod-Ready | Classification |
|---------|--------|-----------|---------|-----------|---------------|
| Runtime ingestion | YES | YES | YES | NO (no auth) | Partially Working |
| HMAC signing | YES | YES | YES | NO (default keys) | Mostly Working |
| Decision engine | YES | YES | YES | NO (CPU bug) | Mostly Working |
| Governance | YES | YES | YES | NO (no auth) | Mostly Working |
| Execution rights | YES | YES | YES | NO (2/8 mapped) | Mostly Working |
| Capability registry | YES | YES | YES | NO | Mostly Working |
| Executor dispatch | YES | BROKEN | NO | NO | **BROKEN** |
| Execution feedback | NO | NO | NO | NO | **Not Implemented** |
| Closed-loop control | NO | NO | NO | NO | **Not Implemented** |
| Autonomous loop | NO | NO | NO | NO | **Not Implemented** (NameError) |
| Execution lineage | YES | YES | YES | NO | Mostly Working |
| Unified discovery | NO | NO | NO | NO | **BROKEN** |
| API authentication | NO | NO | NO | NO | **Not Implemented** |
| Override endpoint | NO | NO | NO | NO | **Not Implemented** |
| **[NEW]** GAP->noop abstention | YES | YES | YES | YES (tested) | **Working** |
| **[NEW]** Group4 ActionRequest intake | YES | YES | YES | PARTIAL | **Working** |
| **[NEW]** External observability (4 systems) | YES | YES | YES | PARTIAL | **Mostly Working** |
| **[NEW]** Observer health polling (20+ services) | YES | YES | YES | PARTIAL | **Mostly Working** |
| **[NEW]** Prometheus metrics scraping | YES | YES | UNKNOWN | NO | **Configured** |
| **[NEW]** Link monitoring (ingest-link API) | YES | YES | YES | NO (in-memory) | Partially Working |

---

## 13. Prioritized Backlog [UPDATED]

### P0 -- Critical
1. **Phase 8 test regression** -- test_phase8_execution_closure.py fails 5/5; update tests OR revert signature change
2. **Executor source not trusted** -- main.py:634 `source="backend_api"` not in trusted_signers
3. **Executor missing (localhost:5003)** -- create executor service OR add EXECUTOR_URL env var
4. **No API authentication** -- add JWT/API-key middleware to all routes

### P1 -- High
5. **NameError in runtime_adapter.py** -- uncomment DecisionEngine.decide() call or delete dead function
6. **VANA not in trusted_signers** -- add "VANA" to trusted_signers or make configurable
7. **Override endpoint missing** -- implement POST /api/control-plane/override in main.py
8. **CPU threshold config ignored** -- read CPU_SCALE_UP_THRESHOLD from config.py
9. **trace_logger race condition** -- use thread-local or request-scoped context instead of module global
10. **test_unified_discovery FAILS** -- fix registry JSON path resolution in test context

### P2 -- Medium
11. **numpy Python 3.14 incompatibility** -- pin numpy>=2.0.0 or use Python<=3.12
12. **No feedback loop after execution** -- update INGESTED_RUNTIME_STATE post-execution
13. **Missing execution rights for 6 capabilities** -- add mappings to execution_rights_adapter.py
14. **Refactor 1300-line main.py** -- split into routes/ package
15. **Make executor URL configurable** -- EXECUTOR_URL env var replacing hardcoded localhost:5003

### P3 -- Low
16. Remove committed log files + multi.txt artifact (3.6 MB)
17. Replace datetime.utcnow() with datetime.now(timezone.utc) (deprecation warnings)
18. Replace on_event("startup") with lifespan context manager (main.py:159)
19. Move 30+ Markdown phase reports from backend/ to docs/
20. Persist _INGESTED_LINKS and _EVIDENCE_STORE (lost on restart)

---

## 14. Preserve / Refactor / Delete [UPDATED]

### PRESERVE
- ExecutionRightsAdapter + authorize_execution -- fail-closed, HMAC-signed
- DeterministicPolicyEngine -- deterministic, auditable
- ActionGovernance.evaluate_contract() -- cryptographic verification chain
- AppendOnlyLog + HashLineageVerifier -- real integrity
- execution_lineage.py -- signed hash-chain
- contracts/ package -- Pydantic v2 models
- signed_trace.py -- HMAC, compare_digest
- DecisionEngine.decide() -- pure function
- **[NEW]** ContextualResultAdapter -- deterministic, tested, safety-invariant
- **[NEW]** GovernedAbstentionRecorder -- correct ledger integration
- **[NEW]** Group4IntakeBoundary -- idempotent, lineage-preserving

### REFACTOR
- main.py (1300 lines) -> routes/ package
- action_governance.py (734 lines) -> separate persistence layer
- trace_logger.py -> request-scoped context
- execute_action() -> EXECUTOR_URL env var + fix trusted source

### REWRITE
- Executor dispatch layer (retry, circuit breaker, service discovery, correct source_id)
- pravah_stream (replace in-memory with Redis Streams)

### DELETE
- execution_simulator.py -- dead code
- control_plane/executor/executor.py -- deprecated LEGACY (self-labelled)
- multi.txt, committed log files, empty JSON stubs
- 30+ Markdown phase reports from backend/ root

---

## 15. DO NOT TOUCH List [UNCHANGED]

| Component | Why |
|-----------|-----|
| execution_rights_adapter.py:VERIFIED_CAPABILITY_MAPPINGS | Evidence file path checked on disk |
| deterministic_policy_engine.py:trusted_signers | Gatekeeper for execution; wrong values = privilege escalation |
| action_governance.py:evaluate_contract() | Crypto signature verification |
| execution_lineage.py | Signed hash-chain -- changing serialization invalidates all records |
| contracts/execution_contract.py | FSM transitions -- changes break lineage replay |
| security/signed_trace.py:sign_trace() | Changing canonicalization breaks all existing signatures |

---

## 16. New Contributor Quick Start [UPDATED]

### What Pravah Does
1. Receives telemetry via POST /control-plane/runtime-ingest
2. Decides action (scale_up/scale_down/restart/noop) deterministically
3. Validates via capability-based HMAC-signed execution rights
4. Gates through governance (cooldowns, repetition, policy engine, crypto)
5. Dispatches to executor -- **BROKEN** (localhost:5003; also blocked by source trust gap)
6. Records decisions in JSONL; provides Next.js dashboard
7. **[NEW]** Translates Group2 ALLOW rulings to Group4 ActionRequests (working, tested)
8. **[NEW]** Passively observes 4+ external systems via push telemetry + Observer poll

### Safe to Modify
- decision_engine.py / contracts/*.py / capabilities/registry/*.json
- decision_translation/ -- well-tested, safe to extend
- frontend/src/ / tests/

### Required Environment Variables
| Var | Default | Required in Prod? |
|-----|---------|-----------------|
| LINEAGE_SIGNING_KEY | "pravah-sovereign-lineage-key" | YES |
| POLICY_SIGNING_KEY | "pravah-deterministic-policy-key" | YES |
| ENVIRONMENT | "dev" | YES |
| EXECUTOR_URL | NOT YET IMPLEMENTED | Must be added |
| SSPL_SECRET_KEY | "dev-key" | YES in prod |
| REDIS_HOST / REDIS_PORT | "redis" / 6379 | YES (Docker) |
| PRAVAH_GURUKUL_API / PRAVAH_HR_API / etc. | Docker DNS defaults | YES in prod |

### To Run (Python 3.12 recommended -- numpy<2.0.0 breaks on 3.14)
```bash
cd backend/
pip install fastapi pydantic uvicorn requests psutil pytest
python -m uvicorn control_plane.backend.app.main:app --port 8000 --reload   # Decision Brain
gunicorn wsgi:app --bind 0.0.0.0:7000                                        # Control Plane
uvicorn observer_server:app --port 8600                                      # Observer

# Run passing tests
python -m pytest tests/test_phase14_vana_bootstrap.py \
  tests/test_phase15_gap_governed_abstention.py \
  tests/test_phase16_group4_action_request.py \
  tests/test_group4_final_lineage_closure.py -v
```

### Docker Compose (9 services)
```bash
cd backend/
docker compose --profile dev up -d
# redis, control-plane (7000), decision-brain (8000), observer (8600),
# 3x deploy-workers, queue-monitor, health-monitor, prometheus (9093)
```

---

## 17. Final Scorecard [UPDATED]

| Area | Score | Reason |
|------|------:|--------|
| Architecture design | 6/10 | Thoughtful; executor missing; Group4 boundary clean |
| Governance | 7/10 | Well-engineered; VANA and "backend_api" trust gaps |
| Execution rights | 7/10 | Fail-closed; only 2/8 mapped |
| Decision engine | 7/10 | Pure function; CPU config bug |
| Executor integration | 1/10 | Always fails; port 5003 non-existent; source not trusted |
| Closed-loop control | 1/10 | No feedback; no post-execution state update |
| Trace sovereignty | 6/10 | HMAC chain correct; two disconnected systems |
| Security | 2/10 | Crypto solid; zero API auth; default keys |
| Test suite | 6/10 (was 5) | New P15/P16/Group4 suites excellent; P8 regressed |
| Decision translation boundary | 8/10 (NEW) | GAP/ALLOW/ADAPT deterministic, safety-invariant, fully tested |
| External observability | 6/10 (NEW) | 4 systems observed; push + poll paths |
| Frontend | 5/10 | Mostly connected; missing override; synthetic data |
| Persistence | 5/10 | JSONL durable; in-memory state lost on restart |
| Reliability | 3/10 | Race conditions; no retry; no circuit breaker |
| Deployment | 5/10 (was 3) | 9-service docker compose; Yotta/systemd artifacts; dep conflicts remain |
| Docs accuracy | 4/10 | Phase reports improving; some claims still overclaim |
| Dev experience | 3/10 | Dep install fails on Py3.14; no working E2E guide |
| **Overall** | **4.5/10** (was 4) | Decision translation solid; execution and security gaps critical |

---

## 18. Final Verdict [UPDATED]

**Is the control loop genuinely closed?** NO. Execution dispatch always fails at two layers:
1. `source="backend_api"` is not in trusted_signers -- governance blocks every non-noop action
2. localhost:5003 does not exist -- even if governance passed, no executor is running

No feedback loop exists. The system decides and validates -- it cannot act.

**What works?** DecisionEngine, ExecutionRightsAdapter, ActionGovernance, DeterministicPolicyEngine, AppendOnlyLog, execution lineage, capability registry, dashboard read endpoints. **[NEW]** ContextualResultAdapter, GovernedAbstentionRecorder, Group4IntakeBoundary, external observability (push + Observer poll), docker-compose multi-service definition.

**What is broken?** Executor dispatch (port 5003 + source trust gap), runtime_adapter.py autonomous loop (NameError), VANA governance integration, unified discovery, override endpoint. **[NEW]** Phase 8 tests broken by signature changes.

**What is not implemented?** API authentication, execution feedback loop, closed-loop control, execution rights for 6/8 capabilities, persistent link/evidence store.

**What is falsely claimed?** Closed-loop control. Autonomous loop running. test_unified_discovery passing. **[NEW]** Phase 8 test passage (5/5 now fail).

**What must be fixed before production?**
- P0: Fix Phase 8 test regression; add "backend_api" to trusted_signers OR redesign execution source; create executor service; add API authentication; fix runtime_adapter NameError.
- P1: VANA trust, override endpoint, CPU threshold bug, trace_logger race.

**What is production-ready?** Nothing. Core components are well-implemented and the decision translation boundary is genuinely solid, but the system is not secure, not complete, and not end-to-end integrated.

**What has meaningfully improved since the initial audit?**
- Phase 15-16 and Group4 decision translation: 52 tests passing across 3 new suites
- External observability: 4 real systems connected (push telemetry + Observer health polls)
- App registry: 49 apps (was 28)
- Docker Compose: 9 named services with profiles, health checks, log rotation, Prometheus
- Production deployment artifacts: Yotta systemd, prod.env, startup scripts, health validator

**What has regressed since the initial audit?**
- Phase 8 test suite: was 5/5 PASS, now 5/5 FAIL
- "backend_api" source trust gap is newly identified -- the executor was ALWAYS governance-blocked before reaching localhost:5003
