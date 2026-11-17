# 05. Event Streaming

Event streaming is the practice of capturing data in real-time from event sources (like databases, sensors, or microservices) in the form of a stream of events. These events are stored durably for later retrieval or processed in real-time.

## Messaging vs. Streaming
- **Message Queues (e.g., RabbitMQ, SQS):** Designed for discrete tasks. A consumer reads a message, processes it, and acknowledges it, causing it to be deleted from the queue. Excellent for task distribution.
- **Event Streams (e.g., Kafka, Redis Streams):** Designed for continuous logs of events. Multiple different consumers can read the same stream independently without deleting the events. Excellent for telemetry and analytics.

## Redis Event Bus in PRAVAH

PRAVAH requires extremely low-latency communication between the Control Plane (receiving data) and the Decision Brain (analyzing data). For this, it uses a **Redis Event Bus**.

### The Flow:
1. The **Control Plane** acts as the *Producer*. Upon validating a telemetry payload, it publishes a JSON-encoded event to a specific Redis channel (e.g., `pravah_telemetry_stream`).
2. The **Decision Brain** acts as the *Consumer*. It runs a persistent background thread (`RedisEventBus`) that subscribes to this channel.
3. As soon as the event hits Redis, it is immediately pushed to the Decision Brain in memory.

### Fallback & Resilience
If the Redis connection drops, PRAVAH implements a **Mock Mode** fallback (`_setup_mock_mode()`). The Control Plane will gracefully log the failure but continue to acknowledge incoming HTTP requests, ensuring that downstream services are not blocked by the monitoring system's internal queuing issues.
