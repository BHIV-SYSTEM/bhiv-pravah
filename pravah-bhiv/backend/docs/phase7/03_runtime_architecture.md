# Runtime Architecture
**Phase 7 — Documentation & Handover | Version 1.0.0**

---

## 1. System Overview

Pravah-BHIV is an **autonomous AI agent runtime** that continuously monitors, decides, and acts on the health of registered microservices. It implements a 7-phase agent loop backed by an immutable event journal, governed by a cryptographic hash chain.

---

## 2. Agent Loop State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                        AgentRuntime                             │
│                                                                 │
│   ┌───────┐   ┌─────────────┐   ┌──────────────┐              │
│   │ IDLE  │──▶│  OBSERVING  │──▶│  VALIDATING  │              │
│   └───────┘   └─────────────┘   └──────┬───────┘              │
│       ▲                                 │                       │
│       │                         ┌───────▼──────┐               │
│       │                         │   DECIDING   │               │
│       │                         └───────┬──────┘               │
│       │                                 │                       │
│       │                         ┌───────▼──────┐               │
│       │                         │  ENFORCING   │               │
│       │                         └───────┬──────┘               │
│       │                                 │                       │
│       │                         ┌───────▼──────┐               │
│       │                         │    ACTING    │               │
│       │                         └───────┬──────┘               │
│       │                                 │                       │
│       │                    ┌────────────▼──────────┐           │
│       │                    │  OBSERVING_RESULTS    │           │
│       │                    └────────────┬──────────┘           │
│       │                                 │                       │
│       │                         ┌───────▼──────┐               │
│       └─────────────────────────│  EXPLAINING  │               │
│                                 └──────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### Phase Descriptions

| Phase | Class Method | Responsibility |
|---|---|---|
| **OBSERVING** | `_sense()` | Collect runtime signals via `PerceptionLayer` adapters |
| **VALIDATING** | `_validate()` | Schema + contract validation via `RuntimeEventValidator` |
| **DECIDING** | `_decide()` | Call `DecisionProvider` (HTTP brain or RL engine) |
| **ENFORCING** | `_enforce()` | `ActionGovernance.evaluate_action()` — allows or blocks |
| **ACTING** | `_act()` | Execute action via `Sarathi` executor + write proof |
| **OBSERVING_RESULTS** | `_observe()` | Measure system response post-action |
| **EXPLAINING** | `_explain()` | Produce structured explanation dict, update memory |

---

## 3. Component Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AgentRuntime                               │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │AgentState    │  │AgentMemory   │  │AgentLogger               │  │
│  │Manager       │  │(decision     │  │(structured JSON           │  │
│  │(FSM)         │  │ history)     │  │ logs)                    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Perception Layer                          │   │
│  │  RuntimeEventAdapter │ HealthSignalAdapter │ SystemAlert     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────┐  ┌─────────────────────────────────────────┐  │
│  │DecisionProvider  │  │          ActionGovernance               │  │
│  │(HTTP Brain /     │  │  eligibility → cooldown → repetition    │  │
│  │ RL Orchestrator) │  │  → policy → admission check            │  │
│  └──────────────────┘  └─────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────┐  ┌────────────────┐  ┌──────────────────────┐   │
│  │Sarathi Router │  │  write_proof() │  │  RedisEventBus /     │   │
│  │(action exec)  │  │  ProofLogger   │  │  EventBus (fallback) │   │
│  └───────────────┘  └────────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────▼──────────────────┐
              │       Persistence Layer           │
              │                                   │
              │  AppendOnlyLog (JSONL journal)    │
              │  ReplayIndex   (execution index)  │
              │  SnapshotRegistry (state hashes)  │
              │  HashLineageVerifier (chain proof) │
              └───────────────────────────────────┘
```

---

## 4. Module Inventory

| Module | Path | Role |
|---|---|---|
| `AgentRuntime` | `agent_runtime.py` | Central agent loop |
| `AgentStateManager` | `control_plane/core/agent_state.py` | FSM transitions |
| `AgentMemory` | `control_plane/core/agent_memory.py` | Decision history |
| `AgentLogger` | `control_plane/core/agent_logger.py` | Structured logging |
| `PerceptionLayer` | `control_plane/core/perception.py` | Signal ingestion |
| `ActionGovernance` | `control_plane/core/action_governance.py` | 5-stage governance |
| `SelfRestraint` | `control_plane/core/self_restraint.py` | Rate-limit guard |
| `AppendOnlyLog` | `control_plane/persistence/append_only_log.py` | Immutable journal |
| `HashLineageVerifier` | `control_plane/persistence/hash_lineage_verifier.py` | Chain verification |
| `ReplayIndex` | `control_plane/persistence/replay_index.py` | Fast replay lookup |
| `SnapshotRegistry` | `control_plane/persistence/replay_index.py` | State hash registry |
| `StartupValidator` | `control_plane/deployment/startup_validator.py` | Boot-time gate |
| `ReadinessValidator` | `control_plane/deployment/readiness_validator.py` | Traffic gate |
| `RecoveryValidator` | `control_plane/deployment/recovery_validator.py` | Restart recovery |
| `TelemetryCollector` | `control_plane/telemetry/telemetry_collector.py` | System metrics |
| `MLFeatureExtractor` | `control_plane/ml/ml_feature_extractor.py` | RL feature prep |
| `MultiAppControlPlane` | `control_plane/multi_app_control_plane.py` | Multi-tenant registry |

---

## 5. Decision Brain Interface

```
POST http://127.0.0.1:{DECISION_BRAIN_PORT}/process-runtime
Content-Type: application/json

Request:
{
  "trace_id":       "<uuid>",
  "app_id":         "<app-name>",
  "event_type":     "runtime_signal",
  "workers":        4,
  "cpu_percent":    35.0,
  "memory_percent": 60.0,
  "error_rate":     0.02
}

Response:
{
  "action_requested": "scale_up",
  "confidence":       0.87,
  "reason":           "high_cpu_utilization"
}
```

---

## 6. Governance Pipeline

```
evaluate_action(action, context, source)
        │
        ▼
  ① Eligibility Check    — Is this action type permitted in current state?
        │
        ▼
  ② Cooldown Check       — Has enough time elapsed since last execution?
        │
        ▼
  ③ Repetition Check     — Is this action being repeated too frequently?
        │
        ▼
  ④ Policy Engine        — Does the action pass all governance policies?
        │
        ▼
  ⑤ Admission Control    — Final admission gate (resource + safety)
        │
        ▼
  GovernanceDecision(should_block=True/False, reason, legitimacy)
```

---

## 7. Key Design Principles

1. **Immutability** — Journal events are never updated or deleted; only appended
2. **Determinism** — Replay of the same journal always produces the same state hash
3. **Sovereignty** — Every action is cryptographically signed and proof-logged
4. **Resilience** — Redis failure falls back to local `EventBus`; service continues
5. **Governance First** — No action executes without passing all 5 governance stages
6. **Observability** — Every loop cycle produces structured telemetry and proof records
