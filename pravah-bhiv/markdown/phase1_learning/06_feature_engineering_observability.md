# 06. Feature Engineering for Observability Data

Feature engineering is the process of using domain knowledge to extract features (characteristics, properties, attributes) from raw data. In machine learning for observability, raw telemetry is rarely fed directly into an algorithm. It must be shaped into a statistical representation first.

## Why Raw Telemetry is Insufficient
A raw payload like `{"latency_ms": 150, "errors_last_min": 2}` tells you the state at a single millisecond. To an ML model, this is useless without historical context. Is 150ms good or bad? We don't know without a baseline.

## Feature Extraction in PRAVAH

When the PRAVAH Decision Brain receives a payload, it passes it through the `StateFeatureExtractor`.

### 1. Sliding Windows
Instead of looking at a single request, the system maintains a rolling window of the last $N$ requests or the last $T$ seconds. 
- Example: "Average latency over the last 60 seconds."

### 2. Statistical Derivations (Z-Scores)
The system calculates the moving average ($\mu$) and standard deviation ($\sigma$) of the latency. 
When a new latency $x$ arrives, it calculates the **Z-Score**: 
$Z = \frac{x - \mu}{\sigma}$

A high Z-score (e.g., > 3) indicates that the current latency is a statistical outlier compared to recent history.

### 3. Vectorization
The extracted features (Z-score of latency, current error rate, active worker ratio) are combined into a flat numerical vector (e.g., `[3.2, 0.05, 0.8]`). This numerical array is the actual "Feature State" that is fed into the Reinforcement Learning policy or Anomaly Detection model.
