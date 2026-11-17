# Phase 1 Final Convergence

## Trace Contract

The runtime endpoint now requires these headers on every request:

- `X-Trace-Id`
- `X-Timestamp`
- `X-Trace-Signature`

The request body is accepted only after the trace signature is verified, the timestamp is within the allowed age window, and the payload still validates against the runtime schema.

## Client Proof Flow

```python
trace_id = str(uuid.uuid4())
timestamp = str(int(time.time()))
signature = sign_trace(trace_id, timestamp, payload)
```

## Curl Proofs

### 1. Valid request

```bash
curl -X POST http://localhost:7000/api/runtime ^
  -H "Content-Type: application/json" ^
  -H "X-Trace-Id: <trace-id>" ^
  -H "X-Timestamp: <unix-timestamp>" ^
  -H "X-Trace-Signature: <signature>" ^
  -d "{\"state\":\"running\",\"env\":\"dev\",\"app\":\"demo-app\",\"latency_ms\":10,\"errors_last_min\":0,\"workers\":1}"
```

Expected result: `200 OK`

### 2. Missing signature

```bash
curl -X POST http://localhost:7000/api/runtime ^
  -H "Content-Type: application/json" ^
  -H "X-Trace-Id: <trace-id>" ^
  -H "X-Timestamp: <unix-timestamp>" ^
  -d "{\"state\":\"running\",\"env\":\"dev\",\"app\":\"demo-app\",\"latency_ms\":10,\"errors_last_min\":0,\"workers\":1}"
```

Expected result: `401` with `Missing trace signature`

### 3. Tampered body

```bash
curl -X POST http://localhost:7000/api/runtime ^
  -H "Content-Type: application/json" ^
  -H "X-Trace-Id: <trace-id>" ^
  -H "X-Timestamp: <unix-timestamp>" ^
  -H "X-Trace-Signature: <signature-for-original-body>" ^
  -d "{\"state\":\"running\",\"env\":\"dev\",\"app\":\"demo-app\",\"latency_ms\":999,\"errors_last_min\":0,\"workers\":1}"
```

Expected result: `401` with `Invalid trace signature`

### 4. Expired trace

```bash
curl -X POST http://localhost:7000/api/runtime ^
  -H "Content-Type: application/json" ^
  -H "X-Trace-Id: <trace-id>" ^
  -H "X-Timestamp: <old-unix-timestamp>" ^
  -H "X-Trace-Signature: <expired-signature>" ^
  -d "{\"state\":\"running\",\"env\":\"dev\",\"app\":\"demo-app\",\"latency_ms\":10,\"errors_last_min\":0,\"workers\":1}"
```

Expected result: `401` with `Expired trace`

## Freeze State

Phase 1 is functionally complete and verified. The remaining work should be treated as Phase 2 only after this packet is preserved.