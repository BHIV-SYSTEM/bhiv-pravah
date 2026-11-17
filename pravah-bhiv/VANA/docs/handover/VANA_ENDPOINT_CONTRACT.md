# VANA Endpoint Contracts

This document outlines the exact, verified contracts of the live deployed APIs in the VANA pipeline.

## 1. Group 1: Canonical Observation Retrieval
**Live Endpoint:** `GET http://163.128.209.18:8013/observations/{observation_id}`
**CORS Status:** Open (`Access-Control-Allow-Origin: *`)

### Request
```http
GET /observations/TC-Z03-EXT-OPENMETEO-OBS001 HTTP/1.1
```

### Verified Response Shape
```json
{
  "trace_id": "VANA-6cdf290d314e",
  "observation_id": "TC-Z03-EXT-OPENMETEO-OBS001",
  "status": "RETRIEVED",
  "observation": {
    "observation_id": "TC-Z03-EXT-OPENMETEO-OBS001",
    "canonical_record_id": "CR-b4615a27-7ab1-4bde-a078-a56fa0f2414c",
    "dataset_id": "DS-GROUP3-TC-Z03-F02",
    "observation_type": "precipitation",
    "data_state": "CAPTURED",
    "measurements": [
      {
        "metric_name": "precipitation",
        "value": 0.1,
        "unit": "mm"
      }
    ],
    "field_observation_meta": {
      "device_id": "G3-EXT-OPENMETEO-01",
      "operator": "Open-Meteo.com (external data provider)"
    }
  }
}
```

## 2. Group 2: Context Resolution
**Live Endpoint:** `POST https://niyantran.blackholeinfiverse.com/api/group2/context/resolve`
**CORS Status:** Restricted to specific frontend origins (Proxied by VANA Next.js)

### Expected Request
Group 2 expects the `observation` object from Group 1.
```json
{
  "observation_id": "TC-Z03-EXT-OPENMETEO-OBS001",
  "canonical_record_id": "CR-b4615a27-7ab1-4bde-a078-a56fa0f2414c",
  "...": "rest of observation object"
}
```

## 3. Group 4: Governed Execution
**Live Endpoint:** `POST http://163.128.209.18:8010/vana/execute`
**CORS Status:** Restricted to `http://localhost:8000` (Fix for `4500` pending deployment, currently proxied by VANA Next.js)

### Request Contract
The exact Group 2 temporal applicability ruling must be passed to Group 4.
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

### Verified Response Shape (Governed Abstention)
```json
{
  "status": "governed_abstention",
  "evidence": {
    "event_type": "GOVERNED_ABSTENTION",
    "abstention_record_id": "abstention-f71045f1c36d34de27f585e9",
    "event_id": "8f830c25-bb39-4447-9759-1e1cf913501a",
    "execution_id": "exec-abstention-9a3b2184ff",
    "observation_id": "TC-Z03-EXT-OPENMETEO-OBS001",
    "context_id": null,
    "ruling": "ABSTAIN",
    "decision_action": "noop",
    "governance_allowed": true,
    "recorded_at": "2026-08-31T05:31:00.000Z",
    "canonical_record_id": "CR-b4615a27-7ab1-4bde-a078-a56fa0f2414c"
  }
}
```

**ID Semantics:**
- `abstention_record_id`: Stable correlation identity across replays.
- `event_id`: Unique UUID generated at runtime per execution.
- `execution_id`: Unique UUID generated at runtime.
