# Pravah-BHIV Mermaid Diagrams

Here are the Mermaid.js equivalents of the ASCII diagrams found in the Phase 7 documentation. You can view these diagrams in GitHub, Notion, or any Markdown viewer that supports Mermaid.

## 1. Agent Loop State Machine
*(From 03_runtime_architecture.md)*

```mermaid
stateDiagram-v2
    direction TB
    IDLE --> OBSERVING
    OBSERVING --> VALIDATING
    VALIDATING --> DECIDING
    DECIDING --> ENFORCING
    ENFORCING --> ACTING
    ACTING --> OBSERVING_RESULTS
    OBSERVING_RESULTS --> EXPLAINING
    EXPLAINING --> IDLE
```

## 2. Component Architecture
*(From 03_runtime_architecture.md)*

```mermaid
graph TB
    subgraph AgentRuntime["AgentRuntime"]
        direction TB
        subgraph Core["Core State & Logging"]
            ASM["AgentStateManager <br/> FSM"]
            AM["AgentMemory <br/> Decision History"]
            AL["AgentLogger <br/> Structured JSON"]
        end

        PL["Perception Layer <br/> Adapters"]
        
        subgraph Decision["Decision & Governance"]
            DP["DecisionProvider <br/> HTTP Brain"]
            AG["ActionGovernance <br/> 5-Stage Check"]
        end

        subgraph Execution["Execution Engine"]
            SR["Sarathi Router"]
            WP["ProofLogger"]
            REB["RedisEventBus"]
        end
    end

    subgraph Persistence["Persistence Layer"]
        AOL["AppendOnlyLog"]
        RI["ReplayIndex"]
        SReg["SnapshotRegistry"]
        HLV["HashLineageVerifier"]
    end

    AgentRuntime --> Persistence
```

## 3. End-to-End Request Flow (TANTRA Integration)
*(From 04_integration_diagram.md)*

```mermaid
sequenceDiagram
    participant Client as External Event
    participant CP as Control Plane API
    participant PL as PerceptionLayer
    participant REV as RuntimeEventValidator
    participant DP as DecisionProvider (Brain)
    participant AG as ActionGovernance
    participant SR as Sarathi Router
    participant DB as Persistence / Storage

    Client->>CP: POST /api/execute
    CP->>PL: ① _sense()
    PL-->>CP: perception_signal
    CP->>REV: ② _validate()
    REV-->>CP: validation_ok
    CP->>DP: ③ _decide()
    DP-->>CP: action_decision
    CP->>AG: ④ _enforce()
    AG-->>CP: allowed (GovernanceDecision)
    CP->>SR: ⑤ _act()
    SR->>DB: execute() & write_proof()
    SR-->>CP: execution_result
    CP->>CP: ⑥ _observe() (System State Check)
    CP-->>Client: ⑦ _explain() (Explanation Dict)
    CP->>DB: Write Journal (AppendOnlyLog)
    CP->>DB: Certify (MASTERDB / Bucket)
```

## 4. Service Integration Map
*(From 04_integration_diagram.md)*

```mermaid
graph LR
    CP["control-plane :7000"] <-->|HTTP| DBrain["decision-brain :8000"]
    CP <-->|Redis pub/sub| Redis["redis :6380"]
    Redis <-->|Redis| Obs["observer-server :8080"]

    subgraph Observed_Microservices [Observed Microservices]
        GB["gurukul-backend :3000"]
        HR["infiverse-hr :8000"]
        CRM["crm-api :8001"]
        PX["parikshak :8080"]
        BHA["bhiv-hr-agent :8000"]
        BHL["bhiv-langgraph :8000"]
    end
    
    CP -.->|Monitors| Observed_Microservices
```

## 5. Trace Propagation Flow
*(From 04_integration_diagram.md)*

```mermaid
flowchart TD
    Ingest["Ingest Request: generate trace_id = trace-uuid"] --> CP["control-plane log"]
    CP --> DB["decision-brain log"]
    DB --> TS["tantra stream log"]
    TS --> SR["sarathi log"]
    SR --> AOL["AppendOnlyLog: execution_id contains trace_id"]
    AOL --> MDB["MASTERDB: trace_id, validation_score, status"]
    MDB --> BKT["Bucket artifact: data/bucket/exec-id.json"]
```

## 6. Replay Subsystem & Persistence
*(From 07_replay_mapping.md)*

```mermaid
graph TD
    AOL["AppendOnlyLog <br/> logs/control_plane/append_only_log.jsonl"] -->|read events by execution_id| HLV
    
    subgraph Verifier["HashLineageVerifier"]
        C1["verify_sequence_continuity"]
        C2["verify_hash_chain"]
        C3["compute_execution_state_hash"]
    end
    HLV -.-> Verifier
    
    HLV -->|state_hash| RI["ReplayIndex <br/> data/replay_index.json"]
    RI -->|execution metadata| SReg["SnapshotRegistry <br/> data/snapshot_registry.json"]
```

## 7. Hash Chain Structure
*(From 07_replay_mapping.md)*

```mermaid
graph TD
    E1["Event 1: CREATED"] -->|previous_hash| NULL["Genesis"]
    E2["Event 2: APPROVED"] -->|previous_hash| E1
    E3["Event 3: EXECUTING"] -->|previous_hash| E2
    E4["Event 4: COMPLETED"] -->|previous_hash| E3
    
    SH["State Hash = SHA256"] -.-> E1
    SH -.-> E2
    SH -.-> E3
    SH -.-> E4
```
