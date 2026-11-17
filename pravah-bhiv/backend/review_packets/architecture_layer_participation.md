# Architecture & Layer Participation Documentation

**Date**: 2026-07-25
**Scope**: Pravah Sovereignty and TANTRA Ecosystem Integration

---

## 1. Pravah Layer Map

Pravah is positioned as a **Canonical Runtime Observability and Execution Tracking Layer** within the TANTRA ecosystem.

```mermaid
graph TD
    subgraph TANTRA Ecosystem
        subgraph Observed Products
            Gurukul[gurukul-backend]
            HR[infiverse-hr-platform]
            Sarathi[bhiv-sarathi]
            Other[...20+ Others]
        end
        
        subgraph Pravah Infrastructure
            Obs[Observer Server]
            CP[Control Plane]
            DBrain[Decision Brain]
            Reg[Registry]
            Redis[(Redis Event Bus)]
            AOL[(Append-Only Log)]
        end
        
        subgraph Governance & Authority
            GC[Governance Control]
            TMS[Threat Management System]
            MDU[Master Data Unit]
        end
    end
    
    Gurukul -.-> |Passive Health Probe| Obs
    HR -.-> |Passive Health Probe| Obs
    Sarathi -.-> |Passive Health Probe| Obs
    Other -.-> |Passive Health Probe| Obs
    
    Gurukul --> |Telemetry Push| DBrain
    HR --> |Telemetry Push| DBrain
    
    Obs --> CP
    DBrain --> CP
    CP <--> Redis
    CP --> AOL
    CP <--> Reg
    
    CP -.-> |Escalate Governance| GC
    CP -.-> |Escalate Placement| TMS
    CP -.-> |Escalate Provenance| MDU
```

## 2. Sovereignty Boundaries

Pravah strictly adheres to defined sovereignty boundaries:

- **What Pravah Owns**: Its own runtime execution, internal deterministic policies, replay indexes, and append-only logs.
- **What Pravah Observes**: The external state and telemetry pushed by BHIV products.
- **What Pravah NEVER Does**: Pravah does not mutate the state of external systems, manage their configurations, or make active governance decisions regarding their execution paths.

## 3. Escalation Paths

When Pravah encounters state or decisions that fall outside its constitutional boundaries (i.e., "Unknown Ownership"), it escalates:

1. **Strategic Placement**: Escalated to the **TMS** (Threat Management System).
2. **Governance**: Escalated to the **GC** (Governance Control).
3. **Data / Provenance**: Escalated to the **MDU** (Master Data Unit).

This is programmatically enforced in `validate_constitutional_boundaries.py` ensuring Pravah does not assume authority by default.
