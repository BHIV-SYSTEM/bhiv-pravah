# PHASE 13 — EXTERNAL CONTRACT REQUIREMENTS

This document outlines the exact contract requirements and authoritative schemas needed from external teams to responsibly implement the VANA pipeline boundaries.

## 1. Group 3 → Group 1
- **Producer**: Group 3 (`group3-field-edge`)
- **Consumer**: Group 1 (`group1-observation-api`)
- **Known Artifact Names**: `observation_mission_package` → `POST /observations`
- **Currently Available Schema Evidence**: None. Only abstract naming exists in the registry.
- **Missing Schema Information**: Full JSON/Pydantic schema definition, exact required/optional fields, semantics.
- **Exact Contract Artifacts Required**:
  1. Exact `observation_mission_package` schema and `POST /observations` request JSON schema or Pydantic model
  2. Semantics for `observation_id`, timestamp format, location format, and environmental sensor payload structure
  3. Validation constraints and rules
- **Minimum Sample Payload Required**: Yes, valid example payload.
- **Runtime Endpoint Required**: `POST /observations`
- **Authentication Information Required**: Required (authorization mechanism to POST).
- **Health/Readiness Evidence Required**: Required to verify Group 3 can successfully call Group 1 API.

## 2. Group 1 → Group 2
- **Producer**: Group 1 (`group1-observation-api`)
- **Consumer**: Group 2 (`group2-scientific-context`)
- **Known Artifact Names**: `canonical_observation_record` → `POST /api/v1/group2/context/resolve`
- **Currently Available Schema Evidence**: None.
- **Missing Schema Information**: Request/response schemas for context resolution.
- **Exact Contract Artifacts Required**:
  1. Request and response JSON/Pydantic schemas for Context Resolution.
  2. Required inputs, confidence fields, and recommendation fields (if any).
  3. Semantic meaning of `contextual_result`.
  4. Clarification: Does Group 2 produce only scientific context, or can it also produce a recommended action?
- **Minimum Sample Payload Required**: Yes, valid example `canonical_observation_record` and `contextual_result`.
- **Runtime Endpoint Required**: `POST /api/v1/group2/context/resolve`
- **Authentication Information Required**: Required.
- **Health/Readiness Evidence Required**: Required.

## 3. governed-execution → Bucket
- **Producer**: Group 4 (`governed-execution`)
- **Consumer**: Bucket Evidence (`bucket-evidence`)
- **Known Artifact Names**: `execution_result`
- **Currently Available Schema Evidence**: None.
- **Missing Schema Information**: Bucket HTTP PUT contract.
- **Exact Contract Artifacts Required**:
  1. HTTP endpoint, HTTP method (e.g. PUT), request schema.
  2. Evidence object format and expected response.
- **Minimum Sample Payload Required**: Yes.
- **Runtime Endpoint Required**: Bucket endpoint URL.
- **Authentication Information Required**: Required.
- **Health/Readiness Evidence Required**: Health endpoint required (currently returning 503).

## 4. governed-execution → Replay
- **Producer**: Group 4 (`governed-execution`)
- **Consumer**: Replay Runtime (`replay-runtime`)
- **Known Artifact Names**: execution trace / artifacts
- **Currently Available Schema Evidence**: None.
- **Missing Schema Information**: Replay state ingestion schema.
- **Exact Contract Artifacts Required**:
  1. Replay input schema, required trace fields, and required execution fields.
  2. Expected replay output.
- **Minimum Sample Payload Required**: Yes.
- **Runtime Endpoint Required**: Invocation endpoint/interface.
- **Authentication Information Required**: Required.
- **Health/Readiness Evidence Required**: Required.
