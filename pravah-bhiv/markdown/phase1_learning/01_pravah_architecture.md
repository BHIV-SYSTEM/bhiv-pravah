# 01. PRAVAH Architecture

PRAVAH (Predictive Runtime Autonomy & Visibility Architecture Hub) is a comprehensive observability, telemetry, and machine-learning control system designed for distributed microservice ecosystems. 

## Core Philosophy
Unlike traditional passive monitoring systems (like Datadog or New Relic), PRAVAH is an **active, autonomous control plane**. It not only gathers telemetry from downstream services but also actively analyzes it using machine learning to make real-time decisions, such as rate limiting, throttling, or triggering emergency freezes.

## Architectural Components

The PRAVAH ecosystem is broken down into three primary microservices:

### 1. Control Plane (`pravah-control-plane`)
- **Role:** The central nervous system and API gateway.
- **Port:** `7000`
- **Functions:** 
  - Receives incoming telemetry from all integrated apps (the "Adapter" layer).
  - Validates cryptographic signatures (HMAC/SSPL) to ensure trace provenance.
  - Manages the Service Registry (adding/removing integrated apps).
  - Pushes validated telemetry to the Redis Event Bus for asynchronous processing.

### 2. Decision Brain (`pravah-decision-brain`)
- **Role:** The Machine Learning and Policy Engine.
- **Port:** `8000`
- **Functions:**
  - Consumes telemetry events from the Redis Event Bus.
  - Extracts features (latency, error rates, worker counts).
  - Runs reinforcement learning (RL) policies and anomaly detection algorithms (e.g., Isolation Forests).
  - Decides on actions (e.g., `noop`, `throttle`, `freeze`) and logs decisions.

### 3. Observer (`pravah-observer`)
- **Role:** Passive Health Probing and Metrics Aggregation.
- **Port:** `8600`
- **Functions:**
  - Periodically polls the `/health` or `/status` endpoints of all registered services.
  - Aggregates uptime, latency, and system health.
  - Provides a Prometheus-compatible metrics endpoint for dashboards.

## Data Flow
1. A downstream service (e.g., `bhiv-karma`) signs and sends a telemetry payload to the **Control Plane**.
2. The Control Plane validates the signature and puts the payload on **Redis**.
3. The **Decision Brain** reads from Redis, analyzes the data, and stores its decision.
4. Concurrently, the **Observer** pings `bhiv-karma` to ensure it is actually online.

> [!NOTE]
> The decoupling via Redis ensures that even if the Decision Brain is overwhelmed or undergoing training, the Control Plane can continue ingesting high-throughput telemetry without dropping packets.
