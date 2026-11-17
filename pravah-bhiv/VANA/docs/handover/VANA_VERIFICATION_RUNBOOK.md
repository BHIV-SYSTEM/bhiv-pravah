# VANA Verification Runbook

This runbook provides exact, reproducible commands to verify the VANA pipeline behavior.

## A. Group 1 Retrieval
```powershell
curl.exe -s http://163.128.209.18:8013/observations/TC-Z03-EXT-OPENMETEO-OBS001
```
*Expected: Returns a JSON object with `observation_id`, `canonical_record_id`, and measurement details.*

## B. Group 4 OPTIONS Preflight
```powershell
curl.exe -i -X OPTIONS "http://163.128.209.18:8010/vana/execute" -H "Origin: http://localhost:8000"
```
*Expected: Returns `HTTP/1.1 200 OK` with `access-control-allow-origin: http://localhost:8000`.*

## C. Group 4 POST Verification
First, create a `payload.json` file in your current directory:
```json
{
  "ruling": "GAP",
  "action_eligibility": false,
  "abstention_required": true,
  "observation_id": "TC-Z03-EXT-OPENMETEO-OBS001",
  "canonical_record_id": "CR-b4615a27-7ab1-4bde-a078-a56fa0f2414c",
  "context_id": null
}
```

Then run the request:
```powershell
$body = Get-Content payload.json -Raw
curl.exe -s "http://163.128.209.18:8010/vana/execute" -X POST -H "Content-Type: application/json" -d $body
```
*Expected: Returns `status: governed_abstention` with a stable `abstention_record_id` and unique `event_id`.*

## D. Replay Verification
Execute the exact same Group 4 POST command from Step C again.

**Compare the output from Step C and Step D:**
- `abstention_record_id`: MUST be identical.
- `event_id`: MUST be different.
- `execution_id`: MUST be different.

## E. Frontend E2E Verification
1. Start the frontend:
```powershell
cd frontend
npm run dev
```
2. Open a browser to `http://localhost:4500/vana`
3. Expand the region dropdown and select `Zone 3 — Open-Meteo Precipitation (TC-Z03)`.
4. The pipeline will automatically run.
5. Verify the visual output matches the expected JSON contracts and the final Group 4 badge says `NOT EXECUTED`.
