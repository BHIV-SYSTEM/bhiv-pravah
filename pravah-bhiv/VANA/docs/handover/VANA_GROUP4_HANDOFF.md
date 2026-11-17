# VANA Group 4 Handoff

This document describes the interface and contract between Group 2 and Group 4 (Governed Execution).

## Deployed Group 4 Endpoint
- **Endpoint:** `POST http://163.128.209.18:8010/vana/execute`
- **Method:** POST
- **Status:** **LIVE VERIFIED** (via `curl` and frontend proxy)

## Incoming Contract (Group 2 → Group 4)
The deployed endpoint expects a JSON payload representing the Group 2 Contextual Result (Temporal Applicability Ruling). 
As verified in `ContextualResultAdapter`, the following fields are processed:

**Required:**
- `ruling` (e.g. "GAP", "ALLOW")
- `action_eligibility` (boolean)
- `abstention_required` (boolean)
- `observation_id` (string)
- `context_id` (string or null)

**Optional/Preserved Provenance:**
- `canonical_record_id` (string)
- `trace_id` (string)
- `execution_id` (string)
- `contract_version` (string)
- `authority` (string)
- `evidence` (object)

## Outgoing Response (Group 4)
The deployed endpoint returns the final governed outcome.

For a `GAP` ruling (which mandates `ABSTAIN`), the response structure is:
```json
{
  "status": "governed_abstention",
  "evidence": {
    "event_type": "GOVERNED_ABSTENTION",
    "abstention_record_id": "abstention-<sha256 hash>",
    "event_id": "<uuid>",
    "execution_id": "<uuid>",
    "observation_id": "<string>",
    "context_id": null,
    "ruling": "ABSTAIN",
    "decision_action": "noop",
    "governance_allowed": true,
    "recorded_at": "<iso_timestamp>",
    "canonical_record_id": "<string>"
  }
}
```

- `abstention_record_id` is a stable deterministic ID derived from `observation_id`, `context_id`, and `ruling`.
- `event_id` and `execution_id` are runtime generated UUIDs and differ on every call.
