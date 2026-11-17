import time
from monitoring.runtime_observer import RuntimeObserver
from decision_engine.decision_with_control_plane import DecisionController


class AutonomyLoop:

    def __init__(self):
        self.observer = RuntimeObserver()
        self.controller = DecisionController()

    def run(self):

        print("🧠 Pravah Autonomy Loop Started")

        while True:

            try:
                print("\n🔍 Observing runtime...")
                self.observer.collect_metrics()

                print("🧠 Evaluating decisions...")
                self.controller.evaluate()

                print("⏳ Waiting 30 seconds...\n")
                time.sleep(30)

            except Exception as e:
                print(f"⚠️ Autonomy loop error: {e}")
                time.sleep(10)


if __name__ == "__main__":

    loop = AutonomyLoop()
    loop.run()