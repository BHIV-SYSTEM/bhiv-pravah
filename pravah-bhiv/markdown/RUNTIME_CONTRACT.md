# Canonical Runtime Contract

## Purpose

This document defines the **single runtime payload contract** used for Runtime → RL decision intake.

Canonical source of truth:

- `runtime_payload_schema.json`

This contract is frozen and must not be reshaped at runtime.

Current implementation notes:

- Main schema file at repo root: `runtime_payload_schema.json`
- Mirror copy used by contracts package: `contracts/runtime_payload_schema.json`
- Flask runtime intake validates at `control_plane/api/agent_api.py`

---

## Schema (Single JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Runtime Payload Contract",
  "type": "object",
  "required": ["app", "env", "state", "latency_ms", "errors_last_min", "workers"],
  "properties": {
    "app": { "type": "string", "minLength": 1 },
    "env": { "type": "string", "enum": ["dev", "stage", "prod"] },
    "state": { "type": "string", "enum": ["running", "crashed", "degraded", "starting", "stopped"] },
    "latency_ms": { "type": "number", "minimum": 0 },
    "errors_last_min": { "type": "integer", "minimum": 0 },
    "workers": { "type": "integer", "minimum": 0 }
  },
  "additionalProperties": false
}
```

---

## Field Requirements

### Required Fields

| Field | Type | Constraints | Description |
|---|---|---|---|
| `app` | `string` | `minLength: 1` | Application identifier |
| `env` | `string` | One of: `dev`, `stage`, `prod` | Runtime environment |
| `state` | `string` | One of: `running`, `crashed`, `degraded`, `starting`, `stopped` | Current app state |
| `latency_ms` | `number` | `>= 0` | Response latency in ms |
| `errors_last_min` | `integer` | `>= 0` | Error count in last minute |
| `workers` | `integer` | `>= 0` | Current worker count |

### Optional Fields

There are **no optional fields** in the canonical payload.

- Any missing required field is invalid.
- Any extra field is invalid (`additionalProperties: false`).

---

## Valid Example

```json
{
  "app": "billing-api",
  "env": "stage",
  "state": "degraded",
  "latency_ms": 185.3,
  "errors_last_min": 7,
  "workers": 2
}
```

---

## Error Cases (Defined)

All errors are **fail-fast**. Invalid payloads must be refused and not executed.

| Error Case | Example | Expected Outcome |
|---|---|---|
| Missing required field | Missing `workers` | Validation fails; payload rejected |
| Empty `app` | `"app": ""` | Validation fails; payload rejected |
| Invalid `env` enum | `"env": "qa"` | Validation fails; payload rejected |
| Invalid `state` enum | `"state": "recovering"` | Validation fails; payload rejected |
| Wrong type (`latency_ms`) | `"latency_ms": "120"` | Validation fails; payload rejected |
| Wrong type (`errors_last_min`) | `"errors_last_min": 1.5` | Validation fails; payload rejected |
| Negative numeric value | `"workers": -1` | Validation fails; payload rejected |
| Unexpected extra field | `"region": "us-east-1"` | Validation fails; payload rejected |
| Non-object payload | `[]` or `"text"` | Validation fails; payload rejected |

---

## Runtime Handling Rules

1. Validate against `runtime_payload_schema.json`.
2. If invalid, return explicit refusal/error (no silent fallback).
3. If valid, pass payload unchanged to decision path.
4. Log validation outcome for auditability.

Validation modules used in runtime path:

- `control_plane/core/input_validator.py`
- `control_plane/core/runtime_event_validator.py`

---

## Compatibility Note

Some runtime modules also validate event-shaped envelopes for internal transport (`event_id`, `event_type`, `timestamp`).
That envelope is an integration concern and does **not** replace this canonical payload contract.
-=-=-=-