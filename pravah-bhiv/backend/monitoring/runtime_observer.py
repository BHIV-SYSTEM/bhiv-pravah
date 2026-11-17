# import psutil
# import json
# import time
# import os
# import sys

# # Ensure project-root imports work when executing this file directly.
# PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)

# from orchestrator.app_orchestrator import AppOrchestrator

# METRICS_FILE = "data/runtime_metrics.json"


# class RuntimeObserver:

#     def __init__(self):
#         self.orchestrator = AppOrchestrator()
#         os.makedirs("data", exist_ok=True)

#     def collect_metrics(self):

#         apps = self.orchestrator.list_apps()

#         runtime_metrics = {}

#         for app_name, state in apps.items():

#             cpu = psutil.cpu_percent(interval=1)
#             memory = psutil.virtual_memory().percent

#             runtime_metrics[app_name] = {
#                 "cpu_percent": cpu,
#                 "memory_percent": memory,
#                 "workers": state.get("workers", 1),
#                 "status": state.get("status"),
#                 "timestamp": time.time()
#             }

#         with open(METRICS_FILE, "w") as f:
#             json.dump(runtime_metrics, f, indent=2)

#         print("📊 Runtime metrics updated")

#     def run(self):

#         for _ in range(1):
#             self.collect_metrics()
#             time.sleep(30)


# if __name__ == "__main__":
#     observer = RuntimeObserver()
#     observer.run()



















import json
import os

TELEMETRY_FILE = "telemetry.json"


class RuntimeObserver:

    def __init__(self):
        self.runtime_state = {}

    def collect_metrics(self):

        if not os.path.exists(TELEMETRY_FILE):
            print("⚠ telemetry.json not found")
            return

        with open(TELEMETRY_FILE, "r") as f:
            telemetry = json.load(f)

        self.runtime_state = telemetry

        print("📊 Runtime metrics updated")
        print(self.runtime_state)

    def get_state(self):
        return self.runtime_state