import requests
import time
import json
import os

def run_test():
    print("--- STEP 1: Verifying services are reachable ---")
    try:
        res = requests.get("http://localhost:5001/health", timeout=3)
        print(f"Web1 health: {res.status_code} {res.json()}")
        res = requests.get("http://localhost:5004/health", timeout=3)
        print(f"Monitor health: {res.status_code} {res.json()}")
        res = requests.get("http://localhost:5003/health", timeout=3)
        print(f"Executor health: {res.status_code} {res.json()}")
        res = requests.get("http://localhost:8000/health", timeout=3)
        print(f"Control Plane health: {res.status_code} {res.json()}")
    except Exception as e:
        print(f"Error reaching services: {e}")
        return

    print("\n--- STEP 2: Triggering simulated failure on web1 ---")
    try:
        res = requests.post("http://localhost:5001/simulate-failure", timeout=3)
        print(f"Simulate-failure response: {res.status_code} {res.json()}")
    except Exception as e:
        print(f"Error triggering failure: {e}")
        return

    print("\n--- STEP 3: Waiting for monitor to poll and detect issue ---")
    # Wait for 3 seconds to ensure monitor has polled web1 (polls every 1-2 seconds)
    time.sleep(3.0)

    print("\n--- STEP 4: Fetching metrics from monitor ---")
    degraded_payload = None
    try:
        res = requests.get("http://localhost:5004/metrics", timeout=10)
        metrics = res.json()
        print("Metrics received from monitor:")
        print(json.dumps(metrics, indent=2))
        
        for item in metrics:
            if item.get("service_id") == "web1" and item.get("issue_detected") is True:
                degraded_payload = item
                break
    except Exception as e:
        print(f"Error fetching metrics: {e}")
        return

    if not degraded_payload:
        print("Failed to find degraded web1 payload in metrics!")
        return

    print("\n--- STEP 5: Forwarding monitor telemetry to Control Plane runtime-ingest ---")
    try:
        print("Sending payload:")
        print(json.dumps(degraded_payload, indent=2))
        res = requests.post("http://localhost:8000/control-plane/runtime-ingest", json=degraded_payload, timeout=5)
        print(f"Control Plane Response ({res.status_code}):")
        print(json.dumps(res.json(), indent=2))
    except Exception as e:
        print(f"Error posting to Control Plane: {e}")
        return

    print("\n--- STEP 6: Reading trace_log.jsonl to confirm logs ---")
    log_file_path = "trace_log.jsonl"
    if os.path.exists(log_file_path):
        with open(log_file_path, "r") as f:
            lines = f.readlines()
        print("Last 5 entries in trace_log.jsonl:")
        for line in lines[-5:]:
            print(line.strip())
    else:
        print(f"trace_log.jsonl not found at {os.path.abspath(log_file_path)}!")

if __name__ == "__main__":
    run_test()
