import json
import os

DECISION_LOG = "logs/decisions/decision_log.json"
EXECUTION_LOG = "logs/orchestrator/execution_log.json"


def read_last_lines(file_path, n=10):
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r") as f:
        lines = f.readlines()

    return [json.loads(line) for line in lines[-n:]]


def get_dashboard_state():
    return {
        "recent_decisions": read_last_lines(DECISION_LOG),
        "recent_executions": read_last_lines(EXECUTION_LOG),
    }


from fastapi import APIRouter
import json
from pathlib import Path

router = APIRouter()

# paths
LOG_DIR = Path("logs")
DECISION_LOG = LOG_DIR / "decisions" / "decision_log.json"
RUNTIME_LOG = LOG_DIR / "runtime_payload_poller.csv"


@router.get("/control-plane/apps")
def list_apps():
    """
    Return all registered services.
    """
    from .app_registry import load_apps

    apps = load_apps()

    return {
        "apps": apps,
        "total": len(apps)
    }


@router.get("/orchestration/metrics")
def get_orchestration_metrics():
    """
    Return latest decision metrics.
    """
    if not DECISION_LOG.exists():
        return {"total_decisions": 0, "recent": [], "decisions": []}

    decisions = []

    with open(DECISION_LOG) as f:
        for line in f:
            decisions.append(json.loads(line))

    return {
        "total_decisions": len(decisions),
        "recent": decisions[-10:]
    }

# @router.get("/live-dashboard")
# def live_dashboard():
#     """
#     Aggregated control-plane state for UI.
#     """

#     apps_data = list_apps()
#     metrics = get_orchestration_metrics()

#     return {
#         "header": {
#             "title": "🚀 Pravah Dashboard",
#             "subtitle": "Real-time Production Monitoring"
#         },
#         "rl_brain": {
#             "status": "running"
#         },
#         "control_plane": {
#             "control_plane_status": "active"
#         },
#         "unified": {
#             "integration_enabled": True,
#             "total_entities_monitored": len(apps_data["apps"])
#         },
#         "apps": apps_data["apps"],
#         "decisions": metrics["recent"],
#         "total_decisions": metrics["total_decisions"]
#     }

@router.get("/live-dashboard")
def live_dashboard():
    apps_data = list_apps()
    metrics = get_orchestration_metrics()

    total_decisions = metrics["total_decisions"]

    return {
        "header": {
            "title": "🚀 Pravah Dashboard",
            "subtitle": "Real-time Production Monitoring"
        },

        "rl_brain": {
            "status": "running"
        },

        "control_plane": {
            "control_plane_status": "active",
            "total_apps_monitored": len(apps_data["apps"])
        },

        "unified": {
            "integration_enabled": True,
            "total_entities_monitored": len(apps_data["apps"]),
            "total_decisions_made": total_decisions,
            "system_status": "Healthy"
        },
        "policy_evolution": {
    "title": "Q-Table Evolution",
    "metrics": [
        {"label": "States", "value": "120"},
        {"label": "Actions", "value": "5"},
        {"label": "Episodes", "value": "320"}
    ]
},
"error_analytics": {
    "recent_errors": [
        {"code": "HTTP_500", "severity": "critical"},
        {"code": "TIMEOUT", "severity": "warning"},
        {"code": "HIGH_LATENCY", "severity": "warning"}
    ]
},

        "apps": apps_data["apps"],
        "decisions": metrics["recent"],
        "total_decisions": total_decisions
    }