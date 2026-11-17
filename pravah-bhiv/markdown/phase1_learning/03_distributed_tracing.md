# 03. Distributed Tracing & Cryptographic Signatures

Distributed tracing is the method of tracking a single request as it travels through a distributed system. In microservice environments, a single user action might touch 10 different backend services before returning a response.

## Core Trace Mechanisms

### 1. The Trace ID
A Trace ID is a unique identifier (usually a UUID or a 128-bit hex string) generated at the edge of the system (e.g., the API Gateway). This ID is passed along to every downstream service. When examining logs or telemetry, filtering by this Trace ID provides the exact chronological path of that specific request.

### 2. Context Propagation
To maintain trace continuity, services inject the Trace ID into outbound HTTP headers (e.g., `X-Trace-Id` or the W3C standard `traceparent`). Downstream services extract this header and attach it to their own telemetry.

## Security & Sovereign Signatures in PRAVAH (SSPL)

In typical distributed tracing (like standard Jaeger or Zipkin implementations), tracing data is unauthenticated. Any service can emit any trace payload.

PRAVAH fundamentally changes this by enforcing **Cryptographic Trace Provenance** using Sovereign System Provenance Ledger (SSPL) signatures.

### The HMAC Process
1. The downstream service constructs a telemetry payload.
2. It generates a canonical string representation of that payload and hashes it (SHA-256).
3. It creates a signature string combining the `trace_id`, `timestamp`, and the payload hash.
4. Using a shared symmetric secret (`SSPL_SECRET_KEY`), it generates an HMAC-SHA256 signature.
5. The signature is sent in the `X-Trace-Signature` header.

### The Verification
When the PRAVAH Control Plane receives the telemetry, it immediately drops the packet if:
- The timestamp is too old (preventing replay attacks).
- The HMAC signature does not match the recomputed signature using the Control Plane's own `SSPL_SECRET_KEY`.

This guarantees that all telemetry processed by the Decision Brain is authentic and originates from a trusted, authorized service within the ecosystem.
