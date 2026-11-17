from flask import Flask, jsonify
import requests
import time
import json
import logging
import psutil
import os

app = Flask(__name__)

ENV = os.getenv("ENV", "DEV")

services = {
    "web1": "http://localhost:5001/health",
    "executer": "http://localhost:5003/health"
}

# ---------------- LOGGING ----------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

if not logger.handlers:
    fh = logging.FileHandler("monitor.log")
    ch = logging.StreamHandler()

    formatter = logging.Formatter('%(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)


# ---------------- METRICS ----------------
@app.route("/metrics")
def metrics():
    results = []

    system_cpu = psutil.cpu_percent(interval=1) / 100
    system_memory = psutil.virtual_memory().percent / 100

    for service_id in sorted(services.keys()):
        url = services[service_id]

        status = "healthy"
        error_rate = 0.0
        issue_detected = False
        issue_type = "none"
        recommended_action = "noop"

        try:
            start = time.time()
            response = requests.get(url, timeout=3)
            latency = int((time.time() - start) * 1000)

            if response.status_code != 200:
                status = "critical"
                error_rate = 1.0
                issue_detected = True
                issue_type = "crash"
                recommended_action = "restart"

            elif latency > 500:
                status = "degraded"
                issue_detected = True
                issue_type = "cpu_spike"
                recommended_action = "scale_up"

        except:
            status = "critical"
            error_rate = 1.0
            issue_detected = True
            issue_type = "crash"
            recommended_action = "restart"

        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        output = {
            "service_id": service_id,
            "timestamp": timestamp,
            "status": status,
            "metrics": {
                "cpu": round(system_cpu, 2) if issue_type != "cpu_spike" else 0.95,
                "memory": round(system_memory, 2),
                "error_rate": error_rate,
                "uptime": int(time.time())
            },
            "issue_detected": issue_detected,
            "issue_type": issue_type,
            "recommended_action": recommended_action
        }

        logging.info(json.dumps({
            "timestamp": timestamp,
            "event": "DETECTION",
            "service_id": service_id,
            "metrics": output["metrics"],
            "status": status,
            "issue_type": issue_type,
            "action": recommended_action
        }))

        results.append(output)

    return jsonify(results)


# ---------------- RUNTIME PAYLOAD ----------------
@app.route("/internal/runtime-payload")
def runtime_payload():
    cpu = psutil.cpu_percent(interval=1) / 100
    memory = psutil.virtual_memory().percent / 100

    status = "healthy"
    if cpu > 0.85 or memory > 0.85:
        status = "degraded"

    payload = {
        "app_id": "monitor-service",
        "cpu_usage": round(cpu, 2),
        "memory_usage": round(memory, 2),
        "error_rate": 0.0,
        "health_score": 1.0 if status == "healthy" else 0.5,
        "environment": ENV.lower()
    }

    return jsonify(payload)


# ---------------- HEALTH ----------------
@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004)