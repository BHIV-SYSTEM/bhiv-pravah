from contracts.runtime_contract import RuntimeTelemetry


def parse_runtime_payload(payload: dict) -> RuntimeTelemetry:
    return RuntimeTelemetry(**payload)