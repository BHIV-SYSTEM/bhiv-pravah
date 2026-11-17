# 07. ML Anomaly Detection Fundamentals

Anomaly detection is the identification of rare items, events, or observations which raise suspicions by differing significantly from the majority of the data. In the context of PRAVAH, this means detecting when a microservice starts acting erratically (e.g., sudden latency spikes, weird error patterns) before a human operator notices.

## Common Algorithms in Observability

### 1. Isolation Forests
An Isolation Forest is an unsupervised learning algorithm for anomaly detection that works on the principle of isolating anomalies. 
- **How it works:** It builds random decision trees. Anomalies are data points that are "few and different". Therefore, they are easier to isolate (they require fewer splits in the tree to reach a leaf node).
- **Use in PRAVAH:** The Decision Brain uses Isolation Forests on the vectorized feature state (see Doc 06) to score incoming telemetry. If the anomaly score is too high, the Brain flags it as a drift.

### 2. Autoencoders (Deep Learning)
An autoencoder is a neural network designed to compress data down to a small latent space, and then reconstruct it back to the original format.
- **How it works:** It is trained only on "normal" healthy telemetry. When anomalous telemetry is fed into the network, the autoencoder will struggle to reconstruct it properly. The "Reconstruction Error" becomes the anomaly score.

### 3. Statistical Thresholds
The simplest form of anomaly detection. If a value exceeds a hardcoded threshold (e.g., Error Rate > 5%), alert.
- **Why it fails at scale:** Thresholds must be manually tuned. A sudden traffic spike might naturally increase latency, causing false alarms. PRAVAH moves away from static thresholds toward dynamic, context-aware ML models.
