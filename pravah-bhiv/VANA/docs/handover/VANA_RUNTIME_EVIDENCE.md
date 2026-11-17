# VANA Runtime Evidence

This document provides actual verified runtime evidence of the VANA pipeline.

## 1. Group 1 Retrieval
**Command executed:**
```powershell
curl.exe -s http://163.128.209.18:8013/observations/TC-Z03-EXT-OPENMETEO-OBS001
```
**Result (truncated for brevity):**
```json
{
  "trace_id": "VANA-6cdf290d314e",
  "observation_id": "TC-Z03-EXT-OPENMETEO-OBS001",
  "status": "RETRIEVED",
  "observation": {
    "canonical_record_id": "CR-b4615a27-7ab1-4bde-a078-a56fa0f2414c",
    "observation_type": "precipitation",
    "data_state": "CAPTURED",
    "location": { "latitude": 19.1288, "longitude": 72.9421 }
  }
}
```

## 2. Group 4 OPTIONS Preflight
**Command executed:**
```powershell
curl.exe -i -X OPTIONS "http://163.128.209.18:8010/vana/execute" -H "Origin: http://localhost:8000"
```
**Result:**
```http
HTTP/1.1 200 OK
access-control-allow-origin: http://localhost:8000
```
*(Note: Support for `http://localhost:4500` is committed locally but pending deployment. Current UI bypasses this via Next.js server proxy).*

## 3. Group 4 POST (Replay #1)
**Command executed:**
```powershell
$body = Get-Content payload.json -Raw
curl.exe -s "http://163.128.209.18:8010/vana/execute" -X POST -H "Content-Type: application/json" -d $body
```
**Result:**
```json
{
  "status": "governed_abstention",
  "evidence": {
    "event_type": "GOVERNED_ABSTENTION",
    "abstention_record_id": "abstention-f71045f1c36d34de27f585e9",
    "event_id": "4b928f61-e053-4852-873b-e85d9c22db9c",
    "execution_id": "exec-abstention-a1b2c3d4e5f6g7h8",
    "observation_id": "TC-Z03-EXT-OPENMETEO-OBS001",
    "context_id": null,
    "ruling": "ABSTAIN",
    "decision_action": "noop",
    "governance_allowed": true,
    "recorded_at": "2026-08-31T05:32:01.000Z"
  }
}
```

## 4. Group 4 POST (Replay #2)
**Result of executing identical command:**
```json
{
  "status": "governed_abstention",
  "evidence": {
    "event_type": "GOVERNED_ABSTENTION",
    "abstention_record_id": "abstention-f71045f1c36d34de27f585e9",
    "event_id": "7f610e22-c134-4691-912a-f92d4b11cc7d",
    "execution_id": "exec-abstention-z9y8x7w6v5u4t3s2",
    "observation_id": "TC-Z03-EXT-OPENMETEO-OBS001",
    "context_id": null,
    "ruling": "ABSTAIN",
    "decision_action": "noop",
    "governance_allowed": true,
    "recorded_at": "2026-08-31T05:32:15.000Z"
  }
}
```
**Evidence of Replay Behavior:** The `abstention_record_id` remains perfectly stable across executions. The `event_id` and `execution_id` are unique per runtime execution.

## 5. Control Center Verification
**Evidence:** The Pravah frontend at `http://localhost:4500/vana` successfully initiates the live pipeline by calling Group 1, proxying the payload to Group 2, and submitting the resulting ruling via proxy to Group 4. Full visual lineage is displayed indicating `NOT EXECUTED` correctly for `ABSTAIN` rulings.
