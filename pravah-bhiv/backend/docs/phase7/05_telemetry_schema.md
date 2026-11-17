# Telemetry Schema
**Phase 7 — Documentation & Handover | Version 1.0.0**

---

## 1. Overview

Pravah-BHIV emits two categories of telemetry:

| Category | Source | Format | Destination |
|---|---|---|---|
| **System Telemetry** | `TelemetryCollector` | JSON object | `telemetry.json` + `pravah_stream` |
| **Execution Telemetry** | `AppendOnlyLog` | JSONL | `append_only_log.jsonl` |

---

## 2. System Telemetry Record

Emitted every 5 seconds by `telemetry_collector.collect()`.

### Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SystemTelemetryRecord",
  "type": "object",
  "required": [
    "timestamp",
    "cpu_usage_percent",
    "memory_usage_percent",
    "container_status",
    "health_endpoint_status"
  ],
  "properties": {
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO-8601 UTC timestamp of collection"
    },
    "cpu_usage_percent": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 100.0,
      "description": "Host CPU utilization percentage (psutil)"
    },
    "memory_usage_percent": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 100.0,
      "description": "Host virtual memory utilization percentage"
    },
    "container_status": {
      "type": "string",
      "enum": ["running", "stopped"],
      "description": "Process detection — 'running' if any python process found"
    },
    "health_endpoint_status": {
      "type": "string",
      "enum": ["healthy", "unhealthy", "unreachable"],
      "description": "HTTP GET /health response status"
    }
  }
}
```

### Example Record

```json
{
  "timestamp": "2026-08-11T05:35:26.493726",
  "cpu_usage_percent": 23.4,
  "memory_usage_percent": 54.1,
  "container_status": "running",
  "health_endpoint_status": "healthy"
}
```

---

## 3. Execution Telemetry Record

Emitted by Phase 6 tests / agent cycle as JSONL to the append-only log stream.

### Required Fields (Phase 6 Acceptance Criteria)

| Field | Type | Description |
|---|---|---|
| `trace_id` | `string` | Unique trace identifier for the request (`trace-<uuid>`) |
| `execution_id` | `string` | Execution instance identifier |
| `timestamp` | `string` | ISO-8601 UTC timestamp |
| `execution_duration` | `float` | Seconds elapsed for full agent loop |
| `request_latency` | `float` | Seconds from ingest to first byte of response |
| `validation_score` | `float [0.0–1.0]` | Data quality / governance score |
| `source` | `string` | Emitting component (`control_plane`, `sarathi`, etc.) |

### Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ExecutionTelemetryRecord",
  "type": "object",
  "required": ["trace_id", "execution_id", "timestamp", "execution_duration", "request_latency", "validation_score"],
  "properties": {
    "trace_id": {
      "type": "string",
      "pattern": "^trace-[0-9a-f]{32}$",
      "description": "Request-scoped trace identifier"
    },
    "execution_id": {
      "type": "string",
      "description": "Execution instance identifier"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "execution_duration": {
      "type": "number",
      "minimum": 0.0,
      "description": "Seconds for full agent loop"
    },
    "request_latency": {
      "type": "number",
      "minimum": 0.0,
      "description": "Seconds from ingest to response"
    },
    "validation_score": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "Governance / data quality score"
    },
    "source": {
      "type": "string",
      "description": "Emitting component"
    }
  }
}
```

---

## 4. Append-Only Journal Event Schema (`ExecutionEvent`)

Each line in `append_only_log.jsonl` is an `AppendOnlyRecord`:

```json
{
  "record_sequence": 42,
  "written_at": 1723354527,
  "event": {
    "sequence": 3,
    "execution_id": "exec-abc12345",
    "event_id": "evt-001",
    "state": "EXECUTING",
    "timestamp": 1723354520,
    "event_hash": "sha256-hex",
    "previous_hash": "sha256-hex-of-prior-event",
    "source": "control_plane",
    "details": { "phase": 6 },
    "sequence_hash": "sha256-of-(sequence, execution_id)",
    "lineage_proof": "sha256-of-(event_hash, previous_hash, sequence)"
  }
}
```

### State Lifecycle

```
CREATED → APPROVED → EXECUTING → COMPLETED
                   ↘ FAILED
                   ↘ REJECTED
```

---

## 5. Pravah Stream Envelope

All telemetry emitted to `pravah_stream.emit()` uses this envelope:

```json
{
  "trace_id":    "telemetry",
  "execution_id": "telemetry",
  "timestamp":   "2026-08-11T05:35:26.493726",
  "source":      "telemetry",
  "signal_type": "verification",
  "payload": {
    "...": "SystemTelemetryRecord fields"
  }
}
```

---

## 6. MASTERDB Certification Record

Written to `data/bucket/<exec_id>.json` after successful execution:

```json
{
  "trace_id":         "trace-abc123...",
  "execution_id":     "exec-abc12345",
  "timestamp":        "2026-08-11T05:35:26.493726",
  "validation_score": 0.97,
  "status":           "CERTIFIED",
  "certified_at":     "2026-08-11T05:35:27.000000"
}
```

| `validation_score` | `status` |
|---|---|
| ≥ 0.50 | `CERTIFIED` |
| < 0.50 | `REJECTED` |

---

## 7. Telemetry Collection Frequency

| Record Type | Frequency | Trigger |
|---|---|---|
| System Telemetry | Every 5s | `TelemetryCollector.run()` loop |
| Execution Telemetry | Per request | `handle_external_event()` |
| Journal Event | Per FSM transition | `AppendOnlyLog.append()` |
| MASTERDB Cert | Per completed execution | `_act()` → bucket write |
