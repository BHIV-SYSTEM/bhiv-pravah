# PHASE 12 — CROSS-GROUP CONTRACT AND DEPENDENCY RECONCILIATION AUDIT

This audit represents a read-only evidence search of schemas, capabilities, and contracts across the repository.

## A. Group 3 → Group 1
- **Producer Capability**: `group3-field-edge`
- **Exact Output Artifact/Schema**: `observation_mission_package` (Abstract string in registry; no Pydantic/JSON schema defined in repo)
- **Consumer Capability**: `group1-observation-api`
- **Exact Input Artifact/Schema**: `POST /observations` input contract (No payload schema defined in repo)
- **Field Compatibility**: UNKNOWN
- **Missing Fields**: UNKNOWN
- **Extra Required Fields**: UNKNOWN
- **Adapter Currently Exists**: NO
- **Runtime Dependency Status**: Group 3 is `NOT_TESTED` / `DOCUMENTED`, Group 1 is `LIVE`
- **Evidence File/Location**: `group3-field-edge.json`
- **Classification**: **UNKNOWN**

## B. Group 1 → Group 2
- **Producer Capability**: `group1-observation-api`
- **Exact Output Artifact/Schema**: `canonical_observation_record` (Abstract string in registry; no schema defined in repo)
- **Consumer Capability**: `group2-scientific-context`
- **Exact Input Artifact/Schema**: Context resolution input contract (No schema defined in repo)
- **Field Compatibility**: UNKNOWN
- **Missing Fields**: UNKNOWN
- **Extra Required Fields**: UNKNOWN
- **Adapter Currently Exists**: NO
- **Runtime Dependency Status**: Group 1 is `LIVE`, Group 2 is `LOCAL_NOT_LIVE` / `BLOCKED`
- **Evidence File/Location**: `group1-observation-api.json`, `group2-scientific-context.json`
- **Classification**: **UNKNOWN**

## C. Group 2 → Decision/Governance layer
- **Producer Capability**: `group2-scientific-context`
- **Exact Output Artifact/Schema**: `contextual_result` (Abstract string in registry)
- **Consumer Capability**: Decision/Governance Engine (`deterministic_policy_engine.py` / `rl_orchestrator_safe.py`)
- **Exact Input Artifact/Schema**: `DecisionContract` (requires `decision_type`, `action`, `parameters`, `version`)
- **Scientific Context to Decision Conversion**: **NO** repository component exists that maps a scientific context or `contextual_result` into a valid `DecisionContract`.
- **Field Compatibility**: INCOMPATIBLE
- **Missing Fields**: `decision_type`, `action`, `parameters`, `version`
- **Extra Required Fields**: None (Strictly missing required DecisionContract schema fields)
- **Adapter Currently Exists**: NO
- **Runtime Dependency Status**: Group 2 is `LOCAL_NOT_LIVE`, Governance is heavily strictly validated locally.
- **Evidence File/Location**: `backend/contracts/decision_contract.py`
- **Classification**: **INCOMPATIBLE**

## D. Decision/Governance → governed-execution
- **Producer Capability**: Decision/Governance Engine
- **Exact Output Artifact/Schema**: `DecisionContract` → `ExecutionContract`
- **Consumer Capability**: `governed-execution`
- **Exact Input Artifact/Schema**: `ExecutionContract` and execution authorization rights payload
- **Field Compatibility**: COMPATIBLE
- **Missing Fields**: None
- **Extra Required Fields**: None
- **Adapter Currently Exists**: YES (`deterministic_policy_engine.py`, `action_governance.py`)
- **Runtime Dependency Status**: `INTEGRATED`
- **Evidence File/Location**: `governed-execution.json`, `backend/contracts/execution_contract.py`
- **Classification**: **COMPATIBLE**

## E. governed-execution → Bucket Evidence
- **Producer Capability**: `governed-execution`
- **Exact Output Artifact/Schema**: `execution_result`
- **Consumer Capability**: `bucket-evidence`
- **Exact Input Artifact/Schema**: Bucket HTTP PUT contract (Schema undefined locally)
- **Field Compatibility**: UNKNOWN
- **Missing Fields**: UNKNOWN
- **Extra Required Fields**: UNKNOWN
- **Adapter Currently Exists**: NO
- **Runtime Dependency Status**: `UNAVAILABLE` (`BLOCKED` due to HTTP 503)
- **Evidence File/Location**: `bucket-evidence.json`
- **Classification**: **UNKNOWN**

## F. governed-execution → Replay Runtime
- **Producer Capability**: `governed-execution`
- **Exact Output Artifact/Schema**: trace/execution artifacts
- **Consumer Capability**: `replay-runtime`
- **Exact Input Artifact/Schema**: Replay state ingestion (Schema undefined locally)
- **Field Compatibility**: UNKNOWN
- **Missing Fields**: UNKNOWN
- **Extra Required Fields**: UNKNOWN
- **Adapter Currently Exists**: NO
- **Runtime Dependency Status**: `PRESENT` (No endpoint available)
- **Evidence File/Location**: `replay-runtime.json`
- **Classification**: **UNKNOWN**
