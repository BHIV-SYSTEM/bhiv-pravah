# Canonical Architecture Blueprint

This document is the architecture source of truth for the current repository layout.

## Canonical Rules

1. Runtime loop ownership is centralized in AgentRuntime.
2. Runtime payload contract is frozen and validated fail-fast.
3. All action execution flows through the safe orchestrator gate.
4. Governance and safety refusal must be explicit and logged.

## Core Components

- Runtime owner: agent_runtime.py
- Runtime contract: runtime_payload_schema.json
- Runtime to RL bridge: control_plane/core/runtime_rl_pipe.py
- Decision arbitration: control_plane/core/decision_arbitrator.py
- Governance: control_plane/core/action_governance.py
- Safe executor: control_plane/core/rl_orchestrator_safe.py
- Proof logging: control_plane/core/proof_logger.py
- Multi-app control plane: control_plane/multi_app_control_plane.py
- App override manager: control_plane/app_override_manager.py

## API Surfaces

### Flask Control Plane API

- File: control_plane/api/agent_api.py
- Responsibility: canonical runtime intake and control-plane operations
- Endpoints:
  - /api/runtime
  - /api/status
  - /api/health
  - /api/control-plane/apps
  - /api/control-plane/health
  - /api/control-plane/history/<app_name>
  - /api/control-plane/override

### FastAPI Decision Brain API

- File: control_plane/backend/app/main.py
- Responsibility: dashboard payloads, deterministic decision simulation, integration status
- Endpoints include:
  - /health, /action-scope, /decision, /recent-activity
  - /live-dashboard, /decision-summary
  - /control-plane/status, /control-plane/apps, /orchestration/metrics
  - /decision-with-control-plane, /autonomous-status
  - /ingest-link, /remove-link

## Canonical Runtime Loop

1. Sense
2. Validate
3. Decide
4. Enforce
5. Act
6. Observe
7. Explain

## Runtime Contract

Required payload fields:

```json
{
  "app": "string",
  "env": "dev|stage|prod",
  "state": "running|crashed|degraded|starting|stopped",
  "latency_ms": 0,
  "errors_last_min": 0,
  "workers": 0
}
```

Validation is strict:
- Missing required fields are rejected.
- Additional properties are rejected.
- Invalid enum values are rejected.

## Safety and Governance Order

Execution gates are applied in this order:

1. Manual app freeze override
2. Emergency freeze gate
3. Illegal action rejection
4. Demo-mode intake gate
5. Demo safety gate
6. Environment allowlist gate
7. Governance gate (eligibility, cooldown, repetition)

If blocked at any stage:
- Action is refused/nooped.
- Reason and reason_code are returned.
- Proof log event is emitted.

## Environment Action Scope (Implemented)

- dev: restart, scale_up, scale_down, noop, rollback
- stage: restart, noop
- prod: restart, noop

## Production Hardening Modules

- Input validation: control_plane/core/input_validator.py
- Resilience utilities: control_plane/core/resilience.py
- Production logging: control_plane/core/prod_logging.py
- API rate limiting: Flask limiter in control_plane/api/agent_api.py

## Data and Logs

- Control-plane history: logs/control_plane/decision_history.jsonl
- App overrides: logs/control_plane/app_overrides.json
- Orchestrator decisions: logs/<env>/orchestrator_decisions.jsonl
- Proof log stream: logs/day1_proof.log
- Agent state/memory snapshots: logs/agent/*

## Current Architectural Note

Both Flask and FastAPI services are active in the codebase. They cover different responsibilities and are currently complementary, not mutually exclusive.
