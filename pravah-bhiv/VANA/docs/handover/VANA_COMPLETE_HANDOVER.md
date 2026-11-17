# VANA Complete Handover

This is the definitive handover document for the VANA (Visibility & Auditing Network Architecture) pipeline integration. It is based solely on empirical evidence verified in the repository and deployed runtime.

## 1. Executive Summary
The VANA pipeline successfully traces an environmental observation from ingestion (Group 1) through contextual verification (Group 2) to a governed operational outcome (Group 4). The current verified implementation utilizes external weather data, enforces strict action-eligibility boundaries, and visualizes the complete temporal lineage via a unified UI Control Center.

## 2. Architecture
The integration relies on three primary external/deployed API endpoints orchestrated by the Pravah Next.js Control Center:
- **Group 1:** FastAPI (Port 8013)
- **Group 2:** Niyantran API (External)
- **Group 4:** FastAPI (Port 8010)

## 3. Real Source
- **Provider:** Open-Meteo.com (External API)
- **Identity:** `TC-Z03-EXT-OPENMETEO-OBS001`
- **Data:** Precipitation (mm), timestamp, location.
- *Note: Physical field sensors are not currently verified in the repository.*

## 4. Group 3 → Group 1
Group 1 handles data ingestion via `POST /observations` and retrieval via `GET /observations/{observation_id}`. It is responsible for wrapping the raw source data in a VANA-compliant payload.

## 5. Group 1 Canonical Record
During ingestion, Group 1 mints the `canonical_record_id` (e.g., `CR-b4615a27-7ab1-4bde-a078-a56fa0f2414c`). This acts as the immutable identity of the observation throughout the rest of the pipeline.

## 6. Group 2
Group 2 evaluates the context (e.g., historical LIDAR overlays) of the canonical observation. 
- **Endpoint:** `POST https://niyantran.blackholeinfiverse.com/api/group2/context/resolve`
- **Current Status:** Endpoint is deployed and reachable, but currently returns `400 Bad Request` regardless of payload validity.

## 7. Group 2 → Group 4
When Context is unavailable or invalid, Group 2 (or a local derivation acting as Group 2) yields a `GAP` ruling. This ruling is explicitly structured with `action_eligibility = false` and `abstention_required = true`.

## 8. Group 4 Contract
The Group 4 endpoint (`POST /vana/execute`) accepts the Group 2 ruling. The payload must contain the `ruling`, `action_eligibility`, `abstention_required`, `observation_id`, and `context_id`.

## 9. ABSTAIN Semantics
The `ContextualResultAdapter` strictly enforces safety constraints. Any payload marked as a `GAP`, or lacking `action_eligibility`, is deterministically converted into an `abstention` Decision Contract with action `noop`. The `GovernedAbstentionRecorder` ensures this `noop` action yields a `NOT EXECUTED` final outcome. An `ABSTAIN` ruling can never be escalated to `ALLOW` or `BLOCK`.

## 10. Replay Behavior
The system guarantees **Replay-Stable Correlation**. Sending the identical Group 2 ruling to Group 4 multiple times will always yield the exact same `abstention_record_id` (deterministic sha256 hash). However, it will generate a new `event_id` and `execution_id` for every write.

## 11. Ledger
The `GovernedAbstentionRecorder` serializes the abstention event, calculates a hash lineage via `HashLineageVerifier`, and writes it to the local `AppendOnlyLog` (`logs/control_plane/append_only_log.jsonl`).

## 12. Retrieval
- `GET /api/lineage/{execution_id}` exists.
- `GET /evidence/{evidence_ref}` exists but queries an isolated in-memory store.
- *Gap: No endpoint currently exists to retrieve a ledger entry specifically by its `abstention_record_id`.*

## 13. Control Center
The VANA Control Center is an operational dashboard built directly into the Pravah Console (`http://localhost:4500/vana`). It uses React state reducers to orchestrate API calls, presenting a clear step-by-step lineage of the canonical observation, context decision, and governed outcome. It does not use mock data.

## 14. Frontend Proxies
To bypass restrictive browser CORS policies on the remote APIs (`niyantran` and `163...`), the frontend utilizes two server-side Next.js proxies:
- `/api/vana/group2/route.ts` -> Proxies to Group 2.
- `/api/vana/group4/route.ts` -> Proxies to Group 4.

## 15. Runtime Endpoints
- Group 1: `http://163.128.209.18:8013`
- Group 2: `https://niyantran.blackholeinfiverse.com/api/group2/context/resolve`
- Group 4: `http://163.128.209.18:8010`

## 16. Configuration
The backend requires `PRAVAH_MAIN_API` in the environment to instantiate the `HTTPDecisionProvider`. The CORS configuration in `main.py` explicitly allows `http://localhost:8000` (and `http://localhost:4500` locally, pending push).

## 17. Exact Files
- UI: `frontend/src/app/vana/page.tsx`
- Types: `frontend/src/types/index.ts`
- Services: `frontend/src/services/api.ts`
- Proxies: `frontend/src/app/api/vana/group2/route.ts`, `frontend/src/app/api/vana/group4/route.ts`
- Translation: `backend/control_plane/decision_translation/contextual_result_adapter.py`
- Recording: `backend/control_plane/decision_translation/governed_abstention_recorder.py`
- Router: `backend/control_plane/backend/app/main.py`

## 18. How to Run
```powershell
cd frontend
npm run dev
# Then open http://localhost:4500/vana
```

## 19. How to Verify
See `VANA_VERIFICATION_RUNBOOK.md` for exact `curl` commands to manually step through the pipeline.

## 20. Current Status
See `VANA_CURRENT_STATUS.md` for the exact matrix of what is live vs. unverified.

## 21. Known Gaps
See `VANA_KNOWN_GAPS.md`. (Notable items: Group 2 `400` errors, lack of ledger retrieval endpoint, lack of physical sensors).

## 22. Handover Checklist
- [x] Backend constraints enforced
- [x] Front-end proxy established
- [x] Visual lineage completed
- [x] Live APIs queried
- [x] Documentation compiled

---

### CURRENT VERIFIED LINEAGE

Real external source (Open-Meteo)
↓
Observation (`TC-Z03-EXT-OPENMETEO-OBS001`)
↓
Group 1
↓
`canonical_record_id` (`CR-b4615a27...`)
↓
Group 2 decision (`ABSTAIN`)
↓
Group 4 `/vana/execute`
↓
`GOVERNED_ABSTENTION`
↓
`noop`
↓
`NOT EXECUTED`
↓
VANA Control Center
