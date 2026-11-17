# VANA Pipeline — Current Verified Status Matrix

This matrix documents the actual, currently verified status of the VANA integration pipeline.

| Component | Status | Evidence | Environment | Owner / Next Step |
|---|---|---|---|---|
| Open-Meteo source | LIVE VERIFIED | Real external weather API | External | - |
| Physical sensor | **NOT VERIFIED** | No physical hardware verified in repo | - | Group 3 |
| Group 1 ingestion | CODE VERIFIED | Code exists, tested via fixtures | Backend / VM | Verification required on VM |
| Group 1 retrieval | LIVE VERIFIED | `GET http://163.128.209.18:8013/observations/{id}` returns data | Deployed VM | - |
| `canonical_record_id` | LIVE VERIFIED | Present in Group 1 JSON (`CR-b4615a27...`) | Deployed VM | - |
| Group 2 runtime | LIVE VERIFIED | Endpoint `https://niyantran.blackholeinfiverse.com/api/group2/context/resolve` | Niyantran VM | Investigate 400 errors |
| Group 2 decision | LIVE VERIFIED | Evaluated dynamically via UI | VANA Control Center | - |
| Group 4 `/vana/execute` | LIVE VERIFIED | `POST http://163.128.209.18:8010/vana/execute` processes requests | Deployed VM | - |
| ABSTAIN semantics | CODE VERIFIED | `ContextualResultAdapter` handles `GAP` -> `noop` | Backend | - |
| `noop` behavior | CODE VERIFIED | Action Governance allows `noop` | Backend | - |
| Ledger persistence | LOCAL VERIFIED | Writes to `append_only_log.jsonl` | Local / Backend | Validate VM persistent volume |
| Ledger retrieval | **NOT VERIFIED** | No endpoint exposes `abstention_record_id` | Backend | Define retrieval contract if needed |
| Replay behavior | CODE VERIFIED | `abstention_record_id` is stable, `event_id` changes | Backend | - |
| Internal dispatcher | **NOT VERIFIED** | No automatic Group 2 -> Group 4 dispatcher exists | Backend | Assign ownership of automated dispatch |
| Frontend | LOCAL VERIFIED | VANA Control Center running at `localhost:4500` | Local Frontend | Deploy Next.js app |
| Group 4 CORS | PENDING | `main.py` updated to allow `4500`; awaiting deploy | GitHub / VM | Push code and restart VM service |
| Browser E2E | LIVE VERIFIED | Pipeline succeeds via Next.js API proxy | Local Frontend | - |
| Provenance | LIVE VERIFIED | Trace IDs, auth, and external links preserved | Deployed VM | - |
| Lineage | LIVE VERIFIED | Full Group 1 -> 2 -> 4 displayed in UI | VANA Control Center | - |
| Samachar integration | **NOT VERIFIED** | Not identified in current codebase | - | - |
| Physical sensor integration | **NOT VERIFIED** | Not identified in current codebase | - | - |
