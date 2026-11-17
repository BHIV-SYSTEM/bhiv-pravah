# 02. OpenTelemetry Concepts

OpenTelemetry (OTel) is an open-source observability framework made up of a collection of tools, APIs, and SDKs. It is used to instrument, generate, collect, and export telemetry data (metrics, logs, and traces) for analysis in order to understand software performance and behavior.

## The Three Pillars of Observability

### 1. Traces
A trace tracks the progression of a single user request as it is handled by the services that make up an application. 
- **Spans:** A trace is made of one or more "spans". A span represents a single operation within a trace (e.g., a database query, an HTTP request to another microservice).
- **Context Propagation:** Passing the trace context (Trace ID, Span ID) from one service to another via HTTP headers.

### 2. Metrics
Metrics are numeric data points aggregated over a period of time. 
- **Counters:** A value that only goes up (e.g., total HTTP requests).
- **Gauges:** A value that can go up and down (e.g., CPU utilization, memory usage).
- **Histograms:** A distribution of values (e.g., response times mapped into buckets).

### 3. Logs
Logs are timestamped text records, either structured (JSON) or unstructured, containing metadata and context about discrete events. OpenTelemetry helps correlate logs with traces by injecting the `trace_id` directly into the log output.

## How PRAVAH Uses OpenTelemetry Principles
While PRAVAH doesn't force standard OTel collectors everywhere (due to the need for cryptographic signing), it adopts the fundamental concepts:
1. **Trace Continuity:** PRAVAH adapters require upstream components (like TANTRA) to pass a correlation `trace_id` downstream.
2. **Standardized Attributes:** Telemetry payloads use standardized fields (`latency_ms`, `errors`, `state`) much like OTel semantic conventions.
3. **Metrics Exporting:** The PRAVAH Observer exposes standard Prometheus-format metrics, aligning with OTel metrics standards.
