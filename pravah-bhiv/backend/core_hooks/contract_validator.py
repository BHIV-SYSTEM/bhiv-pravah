REQUIRED_FIELDS = [
    "trace_id",
    "execution_id",
    "service_id",
    "action",
    "status",
    "timestamp",
    "source",
    "type"
]

def validate_signal(signal: dict):
    for field in REQUIRED_FIELDS:
        if field not in signal:
            raise ValueError(f"Missing field: {field}")