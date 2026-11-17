# VANA Control Center Integration

This document outlines the architecture and behavior of the VANA Control Center.

## Architecture
- **Location:** The VANA Control Center is an integrated page within the existing Pravah Console Next.js application.
- **URL:** `http://localhost:4500/vana`
- **File Structure:**
  - Page: `frontend/src/app/vana/page.tsx`
  - Navigation: `frontend/src/components/Layout.tsx`
  - Types: `frontend/src/types/index.ts`
  - API Client: `frontend/src/services/api.ts`

It is **NOT** a separate backend service or competing dashboard. It directly extends the existing port 4500 console.

## Display & Lineage Features
The Control Center visually traces the complete pipeline from Source to Governed Outcome:

**A. Observation (Group 1)**
Displays real data fetched from `http://163.128.209.18:8013/observations/{observation_id}`
- Observation ID
- Canonical Record ID
- Source / Provider
- Observation Type
- Measurement
- Timestamp
- Location
- Provenance Reference

**B. Context & Decision (Group 2)**
Evaluates Contextual applicability via Next.js proxy to Niyantran API.
- Context ID
- Context Status
- Decision Ruling (e.g., `ABSTAIN`)
- Decision Reason (e.g., `CONTEXT_NOT_VERIFIED`)
- Action Eligibility
- Abstention Required
- Action Request

**C. Governance (Group 4)**
Displays outcome fetched from `http://163.128.209.18:8010/vana/execute` via Next.js proxy.
- Group 4 Status
- Ruling
- Decision Action
- `abstention_record_id` (deterministic)
- `event_id` (unique)
- `execution_id` (unique)

## API Proxies and CORS
Because the Pravah Console runs on `localhost:4500` and the remote APIs (`niyantran.blackholeinfiverse.com` and `163.128.209.18:8010`) enforce strict CORS policies, the frontend utilizes two Next.js server-side proxies to prevent browser CORS (`Failed to fetch`) errors:
1. `frontend/src/app/api/vana/group2/route.ts` -> Proxies to Group 2.
2. `frontend/src/app/api/vana/group4/route.ts` -> Proxies to Group 4.

## No Fallback or Fake Data
The UI exclusively displays data returned by the live endpoints.
- Observation data is not hardcoded.
- Group 4 IDs are read directly from the real HTTP response.
- Missing data states are explicitly handled (e.g., Zones 1, 2, 4, 5, and 6 are marked `UNAVAILABLE` because they lack live data).
