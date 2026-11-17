# ML Feature Specification
**Phase 7 — Documentation & Handover | Version 1.0.0**

Source: `control_plane/ml/feature_schema.py` + `control_plane/ml/ml_feature_extractor.py`

---

## 1. Overview

The ML subsystem converts raw telemetry signals into a **20-dimensional feature vector** (`TelemetryFeatureVector`) that is consumed by the RL decision engine and anomaly detection models.

---

## 2. Feature Vector: `TelemetryFeatureVector`

| # | Field Name | Type | Default | Unit | Description |
|---|---|---|---|---|---|
| 1 | `latency_ema_p50` | `float` | `0.0` | ms | Exponential moving average of p50 (median) request latency |
| 2 | `latency_ema_p95` | `float` | `0.0` | ms | EMA of p95 latency — captures tail latency trend |
| 3 | `latency_ema_p99` | `float` | `0.0` | ms | EMA of p99 latency — extreme outlier signal |
| 4 | `failure_rate_15m` | `float` | `0.0` | ratio | Failure rate over rolling 15-minute window `[0.0–1.0]` |
| 5 | `error_velocity` | `float` | `0.0` | errors/s² | Rate of change of error count (derivative of error rate) |
| 6 | `avg_retries_per_event` | `float` | `0.0` | count | Average retry depth per processed event |
| 7 | `max_retry_chain` | `int` | `0` | count | Maximum retry chain depth observed in window |
| 8 | `cert_success_rate_rolling` | `float` | `1.0` | ratio | Rolling MASTERDB certification success rate `[0.0–1.0]` |
| 9 | `validation_score_mean` | `float` | `1.0` | ratio | Mean data validation / governance score |
| 10 | `validation_score_variance` | `float` | `0.0` | ratio² | Variance in validation scores (instability signal) |
| 11 | `bottleneck_component_encoded` | `int` | `0` | enum | Integer-encoded component with highest observed latency |
| 12 | `bottleneck_latency_ms` | `float` | `0.0` | ms | Latency of the bottleneck component |
| 13 | `queue_depth_zscore` | `float` | `0.0` | σ | Z-score of current queue depth vs. historical mean |
| 14 | `latency_zscore` | `float` | `0.0` | σ | Z-score of current latency vs. historical mean |
| 15 | `correlated_failure_index` | `float` | `0.0` | index | Cascading failure correlation across dependent services |
| 16 | `throughput_rps_1m` | `float` | `0.0` | req/s | Requests per second — 1-minute rolling window |
| 17 | `throughput_rps_5m` | `float` | `0.0` | req/s | Requests per second — 5-minute rolling window |
| 18 | `cpu_utilization_pct` | `float` | `0.0` | % | Current host CPU utilization |
| 19 | `memory_utilization_pct` | `float` | `0.0` | % | Current host virtual memory utilization |

> **Note:** The feature vector has 19 named fields. The final dimensionality fed to the RL model may include additional derived or one-hot encoded fields; check `ml_feature_extractor.py` for runtime transformations.

---

## 3. Feature Groups

### Group 1: Latency Trends (Features 1–3)
Used for: latency anomaly detection, SLA breach prediction.
- EMA smooths transient spikes; p99 captures worst-case user experience.

### Group 2: Failure Signals (Features 4–5)
Used for: early warning of cascading failures.
- `error_velocity > 0` with `failure_rate_15m > 0.05` triggers `scale_up` or `restart`.

### Group 3: Retry Patterns (Features 6–7)
Used for: detecting downstream service degradation.
- High `max_retry_chain` with low `failure_rate_15m` indicates intermittent failures.

### Group 4: Quality Metrics (Features 8–10)
Used for: MASTERDB certification gating, governance scoring.
- `cert_success_rate_rolling < 0.9` may trigger `alert` or `freeze` action.

### Group 5: Bottleneck Analysis (Features 11–12)
Used for: targeted scaling decisions.
- `bottleneck_component_encoded` encodes: `{0: none, 1: db, 2: redis, 3: api, 4: worker, 5: network}`.

### Group 6: Anomaly Indicators (Features 13–14)
Used for: anomaly detection models (Isolation Forest, Z-score threshold).
- `|zscore| > 3.0` triggers governance review.

### Group 7: Dependency Health (Feature 15)
Used for: multi-service incident correlation.
- Computed as Pearson correlation of failure events across registered services.

### Group 8: Throughput (Features 16–17)
Used for: auto-scaling decisions.
- `throughput_rps_1m / throughput_rps_5m > 1.5` = traffic surge → `scale_up`.

### Group 9: Resource Utilization (Features 18–19)
Used for: resource exhaustion prevention.
- `cpu_utilization_pct > 80` sustained for 3 loops → `scale_up` action.

---

## 4. Canonical Example Vector

```json
{
  "latency_ema_p50":              45.2,
  "latency_ema_p95":             120.5,
  "latency_ema_p99":             350.1,
  "failure_rate_15m":              0.02,
  "error_velocity":                0.001,
  "avg_retries_per_event":         0.1,
  "max_retry_chain":               2,
  "cert_success_rate_rolling":     0.98,
  "validation_score_mean":         0.95,
  "validation_score_variance":     0.002,
  "bottleneck_component_encoded":  4,
  "bottleneck_latency_ms":       115.0,
  "queue_depth_zscore":            0.5,
  "latency_zscore":                1.2,
  "correlated_failure_index":      0.0,
  "throughput_rps_1m":            45.3,
  "throughput_rps_5m":            42.1,
  "cpu_utilization_pct":          35.5,
  "memory_utilization_pct":       60.2
}
```

---

## 5. Runtime Signal → Feature Mapping

| Runtime Payload Field | Feature Field(s) |
|---|---|
| `latency_ms` | `latency_ema_p50`, `latency_ema_p95`, `latency_ema_p99`, `latency_zscore` |
| `errors_last_min` | `failure_rate_15m`, `error_velocity` |
| `workers` | `throughput_rps_1m`, `throughput_rps_5m` |
| `cpu_percent` | `cpu_utilization_pct` |
| `memory_percent` | `memory_utilization_pct` |
| `validation_score` (telemetry) | `validation_score_mean`, `validation_score_variance` |
| Derived from history | `queue_depth_zscore`, `correlated_failure_index`, `cert_success_rate_rolling` |

---

## 6. RL Action Space

| Action Index | Action Name | Trigger Condition |
|---|---|---|
| 0 | `noop` | System stable; no action required |
| 1 | `scale_up` | High CPU/memory or throughput surge |
| 2 | `scale_down` | Low utilization sustained > 5 loops |
| 3 | `restart` | Error velocity spike or crash detected |
| 4 | `alert` | Anomaly Z-score > 3.0 |
| 5 | `freeze` | cert_success_rate < 0.5 or governance block |
