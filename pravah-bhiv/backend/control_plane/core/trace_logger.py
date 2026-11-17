# import json
# import datetime
# import os

# LOG_FILE = "trace_log.jsonl"

# def log_event(stage, data):
#     entry = {
#         "timestamp": datetime.datetime.now().isoformat(),
#         "stage": stage,
#         "data": data
#     }

#     with open(LOG_FILE, "a") as f:
#         f.write(json.dumps(entry) + "\n")






import json
import datetime

LOG_FILE = "trace_log.jsonl"

ALLOWED_STAGES = {
    "detection",
    "payload_emitted",
    "action_received",
    "execution_result",
    "verification"
}

EXPECTED_FLOW = [
    "detection",
    "payload_emitted",
    "action_received",
    "execution_result",
    "verification"
]

_last_stage = None


def validate_trace_data(data):
    if not isinstance(data, dict):
        raise ValueError("Trace data must be a dictionary")


def log_event(stage, data):
    global _last_stage

    if stage not in ALLOWED_STAGES:
        raise ValueError(f"Invalid stage: {stage}")

    validate_trace_data(data)

    # Enforce correct order
    if _last_stage is not None:
        expected_index = EXPECTED_FLOW.index(_last_stage) + 1

        if expected_index < len(EXPECTED_FLOW):
            expected_next = EXPECTED_FLOW[expected_index]
            if stage != expected_next:
                raise ValueError(
                    f"Invalid stage order: {_last_stage} → {stage}, expected {expected_next}"
                )

    _last_stage = stage

    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "stage": stage,
        "data": data
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def reset_trace():
    global _last_stage
    _last_stage = None


def ensure_complete_trace():
    if _last_stage != "verification":
        raise ValueError("Trace incomplete — missing final verification stage")