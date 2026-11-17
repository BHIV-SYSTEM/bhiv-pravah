def validate_trace(data: dict):
    if "trace_id" not in data:
        raise ValueError("Missing trace_id")