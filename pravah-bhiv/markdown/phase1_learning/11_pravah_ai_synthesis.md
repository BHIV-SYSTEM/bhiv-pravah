# PRAVAH AI Runtime Learning: A Synthesis

This document provides a concise, high-level synthesis of how PRAVAH integrates observability with machine learning to create an autonomous, self-learning enterprise monitoring system.

---

## 1. How Telemetry Becomes ML Features

Raw telemetry (e.g., `{"latency_ms": 250, "errors": 1}`) provides an instantaneous snapshot of a system, but machine learning models require context to make decisions. In PRAVAH, this transformation happens in the **Decision Brain**:

1. **Ingestion:** Raw payloads arrive via the Redis Event Bus in real-time.
2. **State Feature Extraction:** The data is passed through an extractor that maintains a sliding window of recent history.
3. **Statistical Derivation:** Instead of feeding `250ms` directly to the ML model, the extractor calculates the moving average ($\mu$) and standard deviation ($\sigma$), converting the raw value into a **Z-Score** (e.g., $+2.5$ standard deviations above normal).
4. **Vectorization:** These derived metrics (Z-scores, error rates, worker saturation ratios) are flattened into a numerical array (a "Feature State" vector). This vector is what the ML model actually "sees".

---

## 2. How Replay Datasets Are Created

To improve ML models over time, PRAVAH must remember exactly what it saw and what it decided to do. This is achieved through **Replay Ledgers** (such as Parikshak's `pravah_replay.jsonl`).

1. **Event Capture:** When the Decision Brain makes a choice (e.g., `throttle`), it captures the exact Feature State (`intake_payload`) and the decision made (`review_payload`).
2. **Trace Correlation:** This captured data is tagged with the original `trace_id` from the OpenTelemetry context, linking the ML decision directly to the user request that triggered it.
3. **Cryptographic Chaining:** To ensure the dataset is tamper-proof, each entry is cryptographically hashed (`event_hash`) and linked to the previous event (`parent_hash`). 
4. **Storage:** The data is appended atomically to an immutable JSONL file, creating a perfect, chronological dataset of the system's runtime life.

---

## 3. How Anomaly Detection Operates on Production Traces

Anomaly detection in PRAVAH happens in real-time, directly on the live production traffic stream.

1. **Scoring:** As the vectorized Feature State enters the Decision Brain, it is fed into an unsupervised ML model, typically an **Isolation Forest** or an **Autoencoder**.
2. **Isolation vs. Normality:** The model evaluates the vector against its trained understanding of "normal" traffic. If the vector represents a rare or highly unusual state (e.g., an unprecedented combination of high latency and low CPU usage), it generates a high **Anomaly Score**.
3. **Autonomous Action:** If the anomaly score exceeds a dynamic threshold, the Decision Brain doesn't just send an alert—it acts. It immediately returns an action payload (e.g., `freeze` or `throttle`) back to the Control Plane, which enforces the restriction on the misbehaving microservice to prevent cascading failures.

---

## 4. How Enterprise AI Systems Learn from Runtime Behavior

The ultimate goal of an enterprise AI monitoring system is continuous improvement without human intervention. PRAVAH achieves this by closing the feedback loop:

1. **Active Control (Online):** The Decision Brain makes real-time anomaly and reinforcement learning (RL) decisions, which are recorded in the Replay Ledger.
2. **Reward Calculation:** The system later evaluates the consequence of those decisions. (e.g., *Did applying a throttle successfully reduce the error rate over the next 5 minutes?*) This establishes a "Reward".
3. **Offline Retraining:** Periodically, an offline training pipeline ingests the Replay Ledger. It feeds the historical states, actions, and calculated rewards into the Reinforcement Learning models to update their policies.
4. **Redeployment:** The newly fine-tuned models are hot-swapped into the Decision Brain.

Through this cycle, PRAVAH evolves from a system that simply triggers alerts into an **autonomic nervous system** that learns how to heal and protect the enterprise infrastructure based on actual runtime experience.
