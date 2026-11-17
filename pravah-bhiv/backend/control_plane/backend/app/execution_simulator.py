# def execute_action(decision):
#     action = decision.selected_action

#     if action == "restart":
#         print("[EXECUTION] Simulated restart triggered")

#     elif action == "scale_up":
#         print("[EXECUTION] Simulated scale-up triggered")

#     elif action == "scale_down":
#         print("[EXECUTION] Simulated scale-down triggered")

#     else:
#         print("[EXECUTION] No action required")








import subprocess

def execute_action(decision):

    action = decision.selected_action

    if action == "scale_up":
        print("[EXECUTION] Scaling backend")

        subprocess.run([
            "docker",
            "compose",
            "up",
            "--scale",
            "backend=3",
            "-d"
        ])

    elif action == "scale_down":
        print("[EXECUTION] Scaling down backend")

        subprocess.run([
            "docker",
            "compose",
            "up",
            "--scale",
            "backend=1",
            "-d"
        ])

    elif action == "restart":
        print("[EXECUTION] Restarting backend")

        subprocess.run([
            "docker",
            "compose",
            "restart",
            "backend"
        ])

    else:
        print("[EXECUTION] No action required")