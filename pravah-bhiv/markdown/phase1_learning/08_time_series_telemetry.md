# 08. Time-Series Telemetry

Time-series data is a sequence of data points indexed in time order. In observability, almost all passive metrics (CPU usage, memory consumption, request counts) are time-series data.

## Characteristics of Time-Series Data
1. **Append-Only:** Data arrives continuously and is almost never updated or deleted (until it expires).
2. **High Write Volume:** Thousands of data points are ingested per second.
3. **Timestamp-Centric:** The primary index for all queries is the timestamp.

## The Role of Prometheus
Prometheus is a purpose-built Time-Series Database (TSDB).
- **Labels:** Time-series data is highly dimensional. A single metric like `http_requests_total` might have labels like `method="GET"` and `status="200"`.
- **Downsampling (Rollups):** To save space, older high-resolution data (e.g., 1-second intervals) is often "downsampled" into lower resolution (e.g., 5-minute averages) after a few weeks.

## PRAVAH's Use of Time-Series
While PRAVAH uses event streaming (Redis) for instantaneous ML decisions, it uses Prometheus for its long-term memory and human visibility.
The `pravah-observer` converts the real-time health polling results into time-series formats, allowing Prometheus to scrape them and operators to build Grafana dashboards showing the historical context of the system's health.
