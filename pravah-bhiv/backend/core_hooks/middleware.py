import time

from flask import request

from security.signing import MAX_TRACE_AGE_SECONDS, verify_trace_signature


TRACE_ID_HEADER = "X-Trace-Id"
TRACE_SIGNATURE_HEADER = "X-Trace-Signature"
TRACE_TIMESTAMP_HEADER = "X-Timestamp"


class TraceVerificationError(Exception):
    pass


def verify_request_trace(payload: dict):

    trace_id = request.headers.get(TRACE_ID_HEADER)
    timestamp = request.headers.get(TRACE_TIMESTAMP_HEADER)
    signature = request.headers.get(TRACE_SIGNATURE_HEADER)

    if not trace_id:
        raise TraceVerificationError(
            "Missing trace id"
        )

    if not timestamp:
        raise TraceVerificationError(
            "Missing timestamp"
        )

    if not signature:
        raise TraceVerificationError(
            "Missing trace signature"
        )

    try:
        request_time = int(timestamp)
    except Exception:
        raise TraceVerificationError(
            "Invalid timestamp"
        )

    now = int(time.time())

    if abs(now - request_time) > MAX_TRACE_AGE_SECONDS:
        raise TraceVerificationError(
            "Expired trace"
        )

    verified = verify_trace_signature(
        trace_id=trace_id,
        timestamp=timestamp,
        signature=signature,
        payload_dict=payload
    )

    if not verified:
        raise TraceVerificationError(
            "Invalid trace signature"
        )

    payload["trace_id"] = trace_id
    payload["timestamp"] = timestamp

    return payload