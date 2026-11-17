import datetime

def build_base_signal(trace_id: str, service_id: str, action: str):
    return {
        "trace_id": trace_id,
        "execution_id": None,  # filled by executer
        "service_id": service_id,
        "action": action,
        "status": "pending",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "source": "sarathi",
        "signal_type": "execution",
        "type": "execution"
    }