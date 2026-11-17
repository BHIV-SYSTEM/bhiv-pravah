# TASK PHASE 1.3: Pravah Group1 Integration Contract Forensics

## 1. Objective
To forensically investigate the documented architectural requirement for Pravah's integration with the Group 1 Observation API. Specifically, to determine whether Pravah is actually required to invoke the `POST /observations` ingestion endpoint, or if this capability is solely owned by an external producer.

## 2. Baseline
Execution Root: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`
- **Tests Collected**: 216
- **Passed**: 216
- **Failed**: 0
- **Errors**: 0

The baseline is flawlessly green and matches the expected state.

## 3. Authoritative Contract Sources
A thorough review of the repository yielded the following authoritative documents governing the Group 1 capability:
- `PHASE13_EXTERNAL_CONTRACT_REQUIREMENTS.md` (Definitive pipeline boundaries)
- `VANA/docs/handover/VANA_GROUP3_GROUP1_HANDOFF.md` (Producer-Consumer contract)
- `VANA/docs/handover/VANA_COMPLETE_HANDOVER.md` (End-to-End orchestration context)
- `backend/control_plane/capabilities/registry/group1-observation-api.json` (Pravah capability registry)

## 4. Group 1 Ownership
The evidence unequivocally proves that observation ingestion is an **external responsibility**:
- **Producer (Creator & POSTer)**: Group 3 (`group3-field-edge`). As per `PHASE13_EXTERNAL_CONTRACT_REQUIREMENTS.md`, Group 3 produces the `observation_mission_package` and calls `POST /observations`.
- **Ingestor & Canonicalizer**: Group 1 (`group1-observation-api`). Group 1 validates, assigns the `observation_id`, and persists it.
- **Consumer**: Pravah Next.js Frontend and Group 2. They retrieve the data via `GET /observations/{observation_id}`.
- **Pravah Backend Responsibility**: The Pravah backend (control plane) governs subsequent execution and capabilities. It is **not** responsible for observation generation or ingestion.

## 5. Current Pravah Data Flow
- The **Pravah Next.js Control Center** (`frontend/src/services/api.ts`) explicitly orchestrates the VANA pipeline by executing a `GET http://163.128.209.18:8013/observations/{observation_id}` call to fetch the canonical record.
- The **Pravah backend** does not utilize any HTTP client (`requests`, `httpx`, etc.) to contact Group 1. The registry merely tracks the capability's existence for transparency and potential metadata linkage.

## 6. Required Request/Response Contract
For the `POST /observations` endpoint:
- **HTTP Method**: POST
- **Path**: `/observations`
- **Request/Response Schema**: Unknown / Undefined in Pravah.
- **Irrelevance**: Because Pravah is not the producer, Pravah does not require the POST request schema. This schema belongs strictly to the Group 3 → Group 1 handoff.

## 7. Security Boundary
- For the POST ingestion, security enforcement belongs to Group 1 validating Group 3.
- Pravah operates downstream of ingestion and is insulated from the ingestion security boundary.

## 8. Failure Handling
- **Ingestion Failure**: Handled by Group 3. If Group 3 fails to POST, no `observation_id` is generated, and the Pravah orchestration never begins.
- **Retrieval Failure**: Handled by Pravah frontend (surfaces error UI) and downstream governance boundaries if malformed.

## 9. Safe Testing Assessment
- **Safe Live POST mechanism**: No sandbox or idempotency token is documented. 
- However, since Pravah is not required to POST, the absence of a sandbox is irrelevant to Pravah's completion of Phase 1. Live GET checks are sufficient and permitted.

## 10. Correct Implementation Location
**NOT APPLICABLE.** 
Because Pravah is not the producer of observations, no implementation for `POST /observations` should exist within the Pravah backend codebase.

## 11. Registry Sufficiency
The current capability registry (`group1-observation-api.json`) correctly lists the endpoint (`http://163.128.209.18:8013`), the capability type (`observation_ingestion`), and the artifact it produces (`canonical_observation_record`). 
This is **sufficient** for Pravah to be aware of the capability without requiring Pravah to invoke the ingestion.

## 12. Proof Matrix

| Question | Evidence | Status | Gap |
|---|---|---|---|
| Is Group1 capability registered? | `group1-observation-api.json` | PROVEN | None |
| Can Pravah discover it? | `CapabilityDiscovery.discover_by_id` | PROVEN | None |
| Is endpoint live? | `curl` Health GET | PROVEN | None |
| Is Group1 contract documented? | `PHASE13_EXTERNAL_CONTRACT_REQUIREMENTS.md` | PROVEN | None |
| Is Pravah required to invoke POST? | explicitly assigned to Group 3 | NOT REQUIRED | None |
| Is POST implementation present? | N/A | N/A | None |
| Is request schema known? | Abstract in Phase 13 | NOT PROVEN | Irrelevant to Pravah |
| Is response schema known? | Abstract in Phase 13 | NOT PROVEN | Irrelevant to Pravah |
| Is persistence proven? | Handled by Group 1 | PROVEN EXTERNAL | None |
| Is safe live testing possible? | No POST sandbox | NOT PROVEN | Irrelevant to Pravah |
| Is failure handling defined? | Implicit to Group 3 | PARTIALLY PROVEN | Irrelevant to Pravah |
| Is security boundary defined? | Handled by Group 1 | PROVEN EXTERNAL | None |
| Is correct implementation location known? | N/A | NOT APPLICABLE | None |

## 13. Final Classification
**D. GROUP1 IS EXTERNAL-ONLY AND PRAVAH INVOCATION IS NOT REQUIRED**

*Explanation*: The architecture documents (`PHASE13_EXTERNAL_CONTRACT_REQUIREMENTS.md`) unequivocally prove that Group 3 (`group3-field-edge`) owns observation generation and ingestion (the `POST /observations`). Pravah acts as an orchestrator and governance layer *after* the observation exists, using the Group 1 `GET` endpoint. Therefore, the "missing" POST implementation in Pravah is not a defect; it is architecturally correct.

## 14. Recommended Next Action
No further development on the Group 1 POST integration is needed for Pravah. 
The audit should now shift focus to resolving the other Phase 1.2 gaps:
1. The **mock-heavy Executor/Governance E2E boundary** (which actually belongs to Pravah).
2. The **silent fail-open read behavior** in `ExecutionLineage` (`json.JSONDecodeError` handling).
