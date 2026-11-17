from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

CONTROL_PLANE_ROOT = REPO_ROOT / "control_plane"
if str(CONTROL_PLANE_ROOT) not in sys.path:
    sys.path.append(str(CONTROL_PLANE_ROOT))
from .config import CPU_SCALE_UP_THRESHOLD
from monitoring.runtime_poller import RuntimePoller
from .decision_engine import DecisionEngine
from .schemas import DecisionRequest, Environment, EventType
# from .schemas import DecisionRequest
from executor.safe_executor import execute_action
import json, os
from datetime import datetime
from .app_registry import load_apps
from monitoring.runtime_poller import poll_all_services

def map_runtime_to_decision(runtime_payload: dict) -> DecisionRequest:
    """
    Convert runtime payload into DecisionRequest contract.
    """

    env_map = {
        "dev": Environment.DEV,
        "stage": Environment.STAGE,
        "prod": Environment.PROD,
    }

    # Determine event type
    if runtime_payload["latency_ms"] > 2000:
        event_type = EventType.LATENCY
    elif runtime_payload["state"] != "running":
        event_type = EventType.HIGH_MEMORY  # temporary mapping
    else:
        event_type = EventType.HIGH_CPU  # default fallback

    # Fake CPU/memory for now (we will improve later)
    cpu = 100 if runtime_payload["state"] != "running" else 30
    memory = 75 if runtime_payload["errors_last_min"] > 0 else 40

    return DecisionRequest(
        environment=env_map.get(runtime_payload["env"].lower(), Environment.DEV),
        event_type=event_type,
        cpu=cpu,
        memory=memory,
    )


def runtime_decision_cycle(service_name: str, base_url: str):
    """
    One full runtime → decision integration test.
    """
    poller = RuntimePoller(env="dev")

    poll_result = poller.poll_service(service_name, base_url)
    runtime_payload = poller.build_runtime_payload(poll_result)

    decision_request = map_runtime_to_decision(runtime_payload)
    print("CPU:", decision_request.cpu)
    print("MEMORY:", decision_request.memory)
    print("CPU:", decision_request.cpu)
    print("CPU_THRESHOLD:", CPU_SCALE_UP_THRESHOLD)
    print("DecisionRequest:", decision_request)
    # decision = DecisionEngine.decide(decision_request)  # ⚠️ DISABLED: Decision must ONLY be triggered via runtime-ingest endpoint
    

    decision_log = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": service_name,
        "action": decision.selected_action,
        "reason": decision.reason,
        "confidence": decision.confidence
    }
    os.makedirs("logs/decisions", exist_ok=True)

    with open("logs/decisions/decision_log.json", "a") as f:
        f.write(json.dumps(decision_log) + "\n")


    execute_action(decision.selected_action, service_name)
    print("Decision:", decision.selected_action, "| Reason:", decision.reason)

    return {
    "runtime_payload": runtime_payload,
    "decision_action": decision.selected_action,
    "decision_reason": decision.reason,
    "confidence": decision.confidence,
    }


def run_control_plane_cycle():
    """
    Poll all services and run decision cycle for each.
    """

    services = poll_all_services()

    results = []

    for service in services:
        decision = runtime_decision_cycle(
            service_name=service["service_name"],
            base_url=service["target_url"]
        )

        results.append(decision)

    return results





import time

def run_autonomous_control_plane(interval=10):
    """
    Continuous autonomous control loop.
    """

    while True:
        print("Running control plane cycle...")

        results = run_control_plane_cycle()

        print("Cycle results:", results)

        time.sleep(interval)






def runtime_cycle_all():
    apps = load_apps()

    results = []

    for app in apps:
        result = runtime_decision_cycle(app["name"], app["url"])
        results.append(result)

    return results