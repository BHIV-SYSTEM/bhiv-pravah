import uuid

def attach_execution_id(signal: dict):
    signal_copy = dict(signal)
    if not signal_copy.get("execution_id"):
        signal_copy["execution_id"] = str(uuid.uuid4())
    signal_copy["source"] = "executer"
    return signal_copy
