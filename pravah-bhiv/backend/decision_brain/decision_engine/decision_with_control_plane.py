import json
import os
import sys
from control_plane.executor.safe_executor import restart_service
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from orchestrator.app_orchestrator import AppOrchestrator

METRICS_FILE = "data/runtime_metrics.json"


class DecisionController:

    def __init__(self):
        self.orchestrator = AppOrchestrator()

    # def evaluate(self):

    #     with open(METRICS_FILE) as f:
    #         metrics = json.load(f)

    #     for app_name, data in metrics.items():

    #         cpu = data["cpu_percent"]
    #         status = data["status"]
    #         workers = data["workers"]

    #         # Decision rules (temporary until RL brain connected)

    #         if status != "running":
    #             print(f"⏸ Skipping {app_name} (status={status})")
    #             continue

    #         elif cpu > 70 and workers < 3:
    #             print(f"📈 Scaling {app_name}")
    #             self.orchestrator.scale_app(app_name, workers + 1)

    #         elif cpu < 10 and workers > 1:
    #             print(f"📉 Scaling down {app_name}")
    #             self.orchestrator.scale_app(app_name, workers - 1)

    #         else:
    #             print(f"🟢 No action needed for {app_name}")
    def evaluate(self):

        with open(METRICS_FILE) as f:
            metrics = json.load(f)

        for app_name, data in metrics.items():

            cpu = data["cpu_percent"]
            status = data["status"]
            workers = data["workers"]

            # Failure detection

            if status != "running":

                print(f"⚠ {app_name} is not running")

                if app_name == "apps02":   # restart only backend
                    print("🔄 Restarting backend service")
                    restart_service(app_name)

                continue

            # Scaling rules

            elif cpu > 70 and workers < 3:
                print(f"📈 Scaling {app_name}")
                self.orchestrator.scale_app(app_name, workers + 1)

            elif cpu < 10 and workers > 1:
                print(f"📉 Scaling down {app_name}")
                self.orchestrator.scale_app(app_name, workers - 1)

            else:
                print(f"🟢 No action needed for {app_name}")

if __name__ == "__main__":

    controller = DecisionController()
    controller.evaluate()