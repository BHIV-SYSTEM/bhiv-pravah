# Integration Diagram
**Phase 7 — Documentation & Handover | Version 1.0.0**

---

## 1. End-to-End Request Flow

```
External Event / Scheduled Tick
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Control Plane API                            │
│                    (Gunicorn / Flask :7000)                       │
│                                                                   │
│   POST /api/execute  ──────────────────────────────────────────  │
│                                                                   │
│   AgentRuntime.handle_external_event(payload)                     │
│         │                                                         │
│         ▼                                                         │
│   ① _sense()   ─── PerceptionLayer                              │
│         │             ├── RuntimeEventAdapter                     │
│         │             ├── HealthSignalAdapter                     │
│         │             └── SystemAlertAdapter                      │
│         │                                                         │
│         ▼                                                         │
│   ② _validate()  ── RuntimeEventValidator                       │
│         │              └── contract.validate_decision_contract()  │
│         │                                                         │
│         ▼                                                         │
│   ③ _decide()  ──── DecisionProvider                            │
│         │              └── POST /process-runtime → Brain :8000   │
│         │                                                         │
│         ▼                                                         │
│   ④ _enforce()  ─── ActionGovernance                            │
│         │              └── 5-stage governance pipeline            │
│         │                                                         │
│         ▼                                                         │
│   ⑤ _act()   ─────── Sarathi Router                             │
│         │              ├── build_sarathi_headers()                │
│         │              ├── execute(action, headers)               │
│         │              ├── write_proof()                          │
│         │              └── MultiAppControlPlane.append_history()  │
│         │                                                         │
│         ▼                                                         │
│   ⑥ _observe()  ─── System State Check                          │
│         │                                                         │
│         ▼                                                         │
│   ⑦ _explain() ──── Explanation Dict → Response                 │
└───────────────────────────────────────────────────────────────────┘
        │                    │                   │
        ▼                    ▼                   ▼
┌──────────────┐  ┌─────────────────┐  ┌──────────────────┐
│  Redis Event │  │  AppendOnly     │  │  MASTERDB /      │
│  Bus :6380   │  │  Log (JSONL)    │  │  Bucket Store    │
│              │  │  (immutable)    │  │  data/bucket/    │
└──────────────┘  └─────────────────┘  └──────────────────┘
        │                    │
        ▼                    ▼
┌──────────────┐  ┌─────────────────┐
│  Observer    │  │  ReplayIndex +  │
│  Server :8080│  │  SnapshotReg.   │
└──────────────┘  └─────────────────┘
```

---

## 2. Service Integration Map

```
┌─────────────────────────────────────────────────────────────────┐
│                      Pravah-BHIV Ecosystem                      │
│                                                                 │
│  ┌─────────────────┐        ┌──────────────────────────────┐   │
│  │  control-plane  │◄──────►│      decision-brain          │   │
│  │  :7000          │  HTTP  │      :8000 (RL Engine)       │   │
│  └────────┬────────┘        └──────────────────────────────┘   │
│           │                                                     │
│           │ Redis pub/sub                                       │
│           ▼                                                     │
│  ┌─────────────────┐        ┌──────────────────────────────┐   │
│  │  redis          │◄──────►│      observer-server         │   │
│  │  :6380          │  Redis │      :8080                   │   │
│  └─────────────────┘        └──────────────────────────────┘   │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Observed Microservices                    │    │
│  │                                                        │    │
│  │  gurukul-backend :3000    │  infiverse-hr :8000        │    │
│  │  parikshak       :8080    │  crm-api      :8001        │    │
│  │  bhiv-hr-agent   :8000    │  bhiv-langgraph :8000      │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Trace Propagation Flow

```
Ingest Request
    │
    ├── generate trace_id = "trace-<uuid>"
    │
    ▼
control-plane log:   {"service": "control-plane", "trace_id": "trace-abc123", ...}
    │
    ▼
decision-brain log:  {"service": "decision-brain", "trace_id": "trace-abc123", ...}
    │
    ▼
tantra stream log:   {"service": "tantra",         "trace_id": "trace-abc123", ...}
    │
    ▼
sarathi log:         {"service": "sarathi",        "trace_id": "trace-abc123", ...}
    │
    ▼
AppendOnlyLog:       execution_id contains trace_id; all events share it
    │
    ▼
MASTERDB:            {"trace_id": "trace-abc123", "validation_score": 0.97, "status": "CERTIFIED"}
    │
    ▼
Bucket artifact:     data/bucket/<exec-id>.json  → {"trace_id": "trace-abc123", ...}
```

---

## 4. TANTRA Integration Sequence

```
Client                Control Plane             TANTRA Stream
  │                        │                         │
  │── POST /api/execute ──►│                         │
  │                        │── validate payload ─────►
  │                        │◄── validation_ok ────────
  │                        │── sense() ──────────────►
  │                        │◄── perception_signal ────
  │                        │── decide() ─────────────►  Decision Brain
  │                        │◄── action_decision ──────
  │                        │── enforce() ────────────►  Governance
  │                        │◄── allowed ─────────────
  │                        │── act() ────────────────►  Sarathi
  │                        │◄── execution_result ─────
  │                        │── observe() ────────────►  System State
  │                        │◄── system_stable ────────
  │                        │── emit telemetry ────────►  pravah_stream
  │◄── explanation dict ───│                         │
  │                        │── write journal ─────────►  AppendOnlyLog
  │                        │── certify MASTERDB ──────►  MASTERDB
```

---

## 5. Persistence Integration

```
AppendOnlyLog (append_only_log.jsonl)
    │
    ├── get_execution_events(execution_id)
    │       │
    │       ▼
    │   HashLineageVerifier
    │       ├── verify_hash_chain()        → PASS / FAIL
    │       ├── verify_sequence_continuity() → PASS / FAIL
    │       └── compute_execution_state_hash() → sha256 hex
    │
    ├── ReplayIndex (replay_index.json)
    │       ├── update_execution()
    │       └── get_execution_info()
    │
    └── SnapshotRegistry (snapshot_registry.json)
            ├── register_snapshot(snapshot_id, execution_id, at_seq, state_hash)
            └── get_snapshot(execution_id, at_seq)
```

---

## 6. External Service Endpoints Watched

| Service | Environment Variable | Default URL |
|---|---|---|
| Gurukul Backend | `PRAVAH_GURUKUL_API` | `http://gurukul-backend:3000` |
| Infiverse HR | `PRAVAH_HR_API` | `http://infiverse-hr-platform:8000` |
| BHIV HR Agent | `PRAVAH_BHIV_HR_AGENT` | `http://infiverse-hr-agent:8000` |
| BHIV LangGraph | `PRAVAH_BHIV_HR_LANGGRAPH` | `http://infiverse-hr-langgraph:8000` |
| Parikshak | `PRAVAH_PARIKSHAK_API` | `http://parikshak-system:8080` |
| CRM API | `PRAVAH_CRM_API` | `http://crm-api:8001` |
