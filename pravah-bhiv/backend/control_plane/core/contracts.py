# from typing import Dict

# REQUIRED_MONITOR_FIELDS = {
#     "service_id",
#     "status",
#     "issue_detected",
#     "issue_type"
# }

# REQUIRED_EXECUTION_FIELDS = {
#     "service_id",
#     "action"
# }


# def validate_monitor_output(data: Dict):
#     missing = REQUIRED_MONITOR_FIELDS - data.keys()
#     if missing:
#         raise ValueError(f"Missing monitor fields: {missing}")
#     return True


# def validate_execution_input(data: Dict):
#     missing = REQUIRED_EXECUTION_FIELDS - data.keys()
#     if missing:
#         raise ValueError(f"Missing execution fields: {missing}")
#     return True
















from typing import Dict

REQUIRED_MONITOR_FIELDS = {
    "service_id",
    "status",
    "issue_detected",
    "issue_type"
}

REQUIRED_EXECUTION_FIELDS = {
    "service_id",
    "action"
}


def validate_monitor_output(data: Dict):
    if not isinstance(data, dict):
        raise ValueError("Monitor output must be a dictionary")

    missing = REQUIRED_MONITOR_FIELDS - data.keys()
    if missing:
        raise ValueError(f"Missing monitor fields: {missing}")

    return True


def validate_execution_input(data: Dict):
    if not isinstance(data, dict):
        raise ValueError("Execution input must be a dictionary")

    missing = REQUIRED_EXECUTION_FIELDS - data.keys()
    if missing:
        raise ValueError(f"Missing execution fields: {missing}")

    return True