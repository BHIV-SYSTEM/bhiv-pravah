import os
import psutil
import json
import time
import requests
from datetime import datetime

from pravah_stream.stream import emit

TELEMETRY_FILE = "telemetry.json"

_main_api = os.getenv("PRAVAH_MAIN_API", "http://decision-brain:8000" if os.getenv("ENVIRONMENT") == "prod" else "http://127.0.0.1:8000").rstrip("/")
HEALTH_URL = os.getenv("PRAVAH_DECISION_BRAIN_HEALTH_URL", f"{_main_api}/health")

def get_cpu():
    return psutil.cpu_percent(interval=1)


def get_memory():
    return psutil.virtual_memory().percent


def get_process_status():
    for p in psutil.process_iter(['name']):
        if "python" in p.info['name'].lower():
            return "running"
    return "stopped"


def get_health():
    try:
        r = requests.get(HEALTH_URL, timeout=2)
        if r.status_code == 200:
            return "healthy"
        return "unhealthy"
    except:
        return "unreachable"


def collect():

    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "cpu_usage_percent": get_cpu(),
        "memory_usage_percent": get_memory(),
        "container_status": get_process_status(),
        "health_endpoint_status": get_health()
    }

    emit({
        "trace_id": "telemetry",
        "execution_id": "telemetry",
        "timestamp": data["timestamp"],
        "source": "telemetry",
        "signal_type": "verification",
        "payload": data,
    })

    return data


def run(iterations=1, interval_seconds=5):

    if iterations <= 0:
        raise ValueError("iterations must be >= 1 in loopless mode")

    for i in range(iterations):
        telemetry = collect()

        with open(TELEMETRY_FILE, "w") as f:
            json.dump(telemetry, f, indent=2)

        print("Telemetry Updated:", telemetry)

        if i < iterations - 1:
            time.sleep(interval_seconds)


if __name__ == "__main__":
    run(iterations=1)