# from monitoring.watchdog import ContainerWatchdog
# from control_plane.core.verification import verify_container_running

# # Step 1: define action
# payload = {
#     "service_id": "youthful_dubinsky",  # use existing container name from your docker ps -a
#     "action": "start"
# }

# # Step 2: execute
# watchdog = ContainerWatchdog()
# result = watchdog.execute_action(payload)

# print("EXECUTION RESULT:", result)

# # Step 3: verify
# if result["status"] == "success":
#     verification = verify_container_running(payload["service_id"])
#     print("VERIFICATION RESULT:", verification)
# else:
#     print("Skipping verification due to execution failure")

# from control_plane.core.trace_logger import log_event

# # after execution
# log_event("execution", result)

# # after verification
# log_event("verification", verification)









# from monitoring.watchdog import ContainerWatchdog
# from control_plane.core.verification import verify_container_running
# from control_plane.core.trace_logger import log_event

# # STEP 1 — Detection (simulate monitoring signal)
# detection_data = {"issue": "manual_trigger"}
# log_event("detection", detection_data)

# # STEP 2 — Payload emission (decision output simulation)
# payload = {
#     "service_id": "youthful_dubinsky",
#     "action": "start"
# }
# log_event("payload_emitted", payload)

# # STEP 3 — Execution receives action
# log_event("action_received", payload)

# watchdog = ContainerWatchdog()
# result = watchdog.execute_action(payload)

# # STEP 4 — Execution result
# log_event("execution_result", result)
# print("EXECUTION RESULT:", result)

# # STEP 5 — Verification
# if result["status"] == "success":
#     verification = verify_container_running(payload["service_id"])
# else:
#     verification = {"verified": False, "reason": "execution_failed"}

# log_event("verification", verification)
# print("VERIFICATION RESULT:", verification)




























from monitoring.watchdog import ContainerWatchdog
from control_plane.core.verification import verify_container_running
from control_plane.core.trace_logger import (
    log_event,
    reset_trace,
    ensure_complete_trace
)

# Reset trace session
reset_trace()

# STEP 1 — Detection
detection_data = {"issue": "manual_trigger"}
log_event("detection", detection_data)

# STEP 2 — Payload emission
payload = {
    "service_id": "youthful_dubinsky",
    "action": "start"
}
log_event("payload_emitted", payload)

# STEP 3 — Action received
log_event("action_received", payload)

# STEP 4 — Execution
watchdog = ContainerWatchdog()
result = watchdog.execute_action(payload)
log_event("execution_result", result)

print("EXECUTION RESULT:", result)

# STEP 5 — Verification
if result["status"] == "success":
    verification = verify_container_running(payload["service_id"])
else:
    verification = {"verified": False, "reason": "execution_failed"}

log_event("verification", verification)

print("VERIFICATION RESULT:", verification)

# Ensure trace integrity
ensure_complete_trace()