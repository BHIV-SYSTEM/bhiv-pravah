# 04. Metrics Pipelines

A metrics pipeline handles the ingestion, processing, aggregation, and storage of numerical time-series data. In large-scale systems, metrics provide the high-level operational view (the "what is happening") before drilling down into traces or logs (the "why is it happening").

## Push vs. Pull Architectures

### The Pull Model (Prometheus)
In a pull model, the centralized metrics server (e.g., Prometheus) scrapes target services at a defined interval (e.g., every 15 seconds) over HTTP.
- **Pros:** The target services don't need to know where the central server is. If the central server goes down, the targets are unaffected.
- **Cons:** The central server must have network access to all targets and must maintain a registry of what to scrape.

### The Push Model (StatsD / PRAVAH Active Telemetry)
In a push model, the target services actively fire their metrics to a central ingestion endpoint.
- **Pros:** Ideal for ephemeral services, serverless functions, or heavily firewalled environments where incoming HTTP scraping is difficult.
- **Cons:** If the central endpoint goes down, metrics are dropped unless buffered.

## PRAVAH's Hybrid Pipeline
PRAVAH uses a highly robust hybrid model to guarantee both active ML evaluation and passive dashboard visibility.

1. **Active Push (The ML Pipeline):**
   - Services push structured JSON telemetry directly to the `pravah-control-plane`.
   - This ensures the Decision Brain gets immediate, low-latency data to make real-time autonomic decisions (like rate-limiting).
   
2. **Passive Pull (The Metrics Pipeline):**
   - The `pravah-observer` independently polls the `/health` endpoints of all services.
   - It exposes a `/metrics` endpoint in the standard OpenMetrics/Prometheus format.
   - A standard Prometheus server scrapes the `pravah-observer`, providing a decoupled, highly available pipeline for Grafana dashboards without burdening the active ML loops.
