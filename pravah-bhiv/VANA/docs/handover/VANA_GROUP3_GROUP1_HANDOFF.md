# VANA Group 3 → Group 1 Handoff

This document describes the interface between Group 3 (Sensor / External Data) and Group 1 (Ingestion & Canonicalization).

## Source Identity
- **Source:** Open-Meteo.com (External live API)
- **Status:** **LIVE VERIFIED**
- **Important Classification:** This is an *external data provider / API*, not a physical sensor. 
- **Physical Sensor:** **NOT VERIFIED**. Physical field sensor ingestion is not currently verified in the repository.

## Ingestion Interface (Group 1)
- **Endpoint:** `POST /observations`
- **Verified via:** OpenAPI schema (`openapi.json` from `163.128.209.18:8013`)

### Canonical Identity Generation
During ingestion, Group 1 is responsible for assigning a permanent identity to the observation:
1. `observation_id` (e.g. `TC-Z03-EXT-OPENMETEO-OBS001`)
2. `canonical_record_id` (e.g. `CR-b4615a27-7ab1-4bde-a078-a56fa0f2414c`)

These IDs are preserved and passed down through the entire VANA pipeline to Group 4.

## Retrieval Interface (Group 1)
- **Endpoint:** `GET http://163.128.209.18:8013/observations/{observation_id}`
- **Verified via:** Live `curl` to deployed VM.

The retrieval endpoint provides the full canonical record necessary to initiate Group 2 and Group 4 processing.
