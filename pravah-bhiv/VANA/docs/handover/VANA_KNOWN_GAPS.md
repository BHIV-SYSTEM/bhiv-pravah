# VANA Known Gaps and Unverified Components

This document lists elements of the VANA integration that are either intentionally missing, require further integration, or lack definitive verified evidence in the current repository state.

## 1. Group 2 Endpoint 400 Errors
While the Group 2 context resolution endpoint (`https://niyantran.blackholeinfiverse.com/api/group2/context/resolve`) is deployed, it currently returns `HTTP 400 Bad Request: {"error":"Something went wrong!"}` even when provided the exact canonical observation JSON. The VANA UI gracefully handles this by rendering an error state, but the endpoint's internal logic needs investigation by the Group 2 team.

## 2. No External Ledger Retrieval Endpoint
The `GovernedAbstentionRecorder` successfully persists abstention records to the `AppendOnlyLog` (e.g., `logs/control_plane/append_only_log.jsonl`). However, there is no verified, externally exposed API endpoint that allows retrieving a log entry by `abstention_record_id`. The existing `/evidence/{evidence_ref}` endpoint queries an in-memory `_EVIDENCE_STORE` which is separate from the append-only ledger.

## 3. Automated Group 2 → Group 4 Dispatcher
Currently, the frontend VANA Control Center orchestrates the pipeline (calling Group 1, then Group 2, then Group 4). There is no verified background worker, dispatcher, or message queue in the codebase that automatically routes a Group 2 temporal ruling to the Group 4 `/vana/execute` endpoint without UI involvement.

## 4. Deployed Ledger Persistence Visibility
The code confirms that `GovernedAbstentionRecorder` writes to `append_only_log.jsonl`. However, without shell access to the deployed VM or a retrieval endpoint (see Gap #2), it is not possible to externally verify that the filesystem persistence is succeeding on the production container (e.g., verifying Docker volumes are mapped correctly).

## 5. Physical Sensor Integration
The current verified data source is the Open-Meteo external API (`TC-Z03-EXT-OPENMETEO-OBS001`). There is no verified evidence of physical field sensor data successfully ingesting into the live Group 1 endpoint in the current repository state.

## 6. Strict Duplicate Suppression (Idempotency)
The system has **replay-stable semantics** (replaying the same observation produces the exact same `abstention_record_id`). However, the system does not exhibit **strict idempotency** in terms of state mutability—each replay currently writes a completely new `event_id` and `execution_id` to the ledger.
