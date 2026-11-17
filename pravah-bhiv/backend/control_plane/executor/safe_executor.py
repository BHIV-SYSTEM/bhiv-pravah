import subprocess
import json
from datetime import datetime
import os

# SERVICE_COMMANDS = {
#     "sample-frontend": ["npm", "start"],
#     "apps02": ["python", "backend/run.py"]
# }

SERVICE_COMMANDS = {
    "sample-frontend": ["python", "backend/run.py"],
    "apps02": ["python", "backend/run.py"]
}
LOG_FILE = "logs/orchestrator/execution_log.json"

def log_execution(action, success, state):

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action_requested": action,
        "execution_success": success,
        "system_state_after_action": state
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    print("Execution Log:", log_entry)


def _stop_service_process(service_name):
    """Best-effort stop for known services prior to restart."""
    # For app aliases, kill the Python runner; otherwise treat input as image name.
    image_name = "python.exe" if service_name in SERVICE_COMMANDS else service_name
    subprocess.run(["taskkill", "/F", "/IM", image_name], check=False)


def restart_service(service_name):

    try:

        _stop_service_process(service_name)

        if service_name in SERVICE_COMMANDS:

            env = os.environ.copy()
            env["PYTHONPATH"] = os.getcwd()

            subprocess.Popen(
                SERVICE_COMMANDS[service_name],
                shell=False,
                cwd=os.getcwd(),
                env=env
            )

        else:
            print(f"⚠ No start command defined for {service_name}")

        log_execution(
            action="restart_service",
            success=True,
            state=f"{service_name}_restarted"
        )

    except Exception as e:

        log_execution(
            action="restart_service",
            success=False,
            state=str(e)
        )

def execute_action(action: str, service_name: str):
    """
    Map decision engine actions to executor operations.
    """

    if action == "restart":
        restart_service(service_name)

    elif action == "scale_up":
        print(f"[EXECUTOR] Scale up requested for {service_name}")

    elif action == "scale_down":
        print(f"[EXECUTOR] Scale down requested for {service_name}")

    elif action == "noop":
        print(f"[EXECUTOR] No action required for {service_name}")

    else:
        print(f"[EXECUTOR] Unknown action: {action}")

if __name__ == "__main__":

    restart_service("apps02")