# =====================================================================
# ⚠️ LEGACY EXECUTION PATH
# DEPRECATED: DO NOT USE FOR ACTIVE RUNTIME INGESTION/EXECUTION LIFE-CYCLES
# SCHEDULED FOR REMOVAL IN PHASE 7.
# =====================================================================

import uuid
import subprocess
import json
from control_plane.core.trace_logger import log_event
import threading
import time
from contracts.execution_contract import validate_execution_contract, advance_execution_state

LOCK = threading.Lock()
# -------------------------
# GLOBALS
# -------------------------
EXECUTION_LOCKS = {}
EXECUTION_MODE = "docker"   # docker | kubernetes
LOCK_TTL_SECONDS = 10


def cleanup_all_expired(now=None):
    # Must be called with LOCK held.
    if now is None:
        now = time.time()
    keys_to_delete = [
        k for k, v in EXECUTION_LOCKS.items()
        if now - v["timestamp"] > LOCK_TTL_SECONDS
    ]
    for k in keys_to_delete:
        del EXECUTION_LOCKS[k]


# -------------------------
# MAIN EXECUTION FUNCTION
# -------------------------

def execute(payload):
    execution_contract_data = payload.get("execution_contract")
    execution_contract = None
    if execution_contract_data:
        execution_contract = validate_execution_contract(execution_contract_data, payload)

    execution_id = (
        payload.get("execution_id")
        or (execution_contract.execution_id if execution_contract else None)
        or str(uuid.uuid4())
    )

    trace_id = payload.get("trace_id")
    service_id = payload.get("service_id")
    action = payload.get("action")

        # ✅ NOW variables exist → safe to log
    log_event(
        "execution_received",
        {
            "service_id": service_id,
            "action": action
        },
        trace_id=trace_id
    )

    lock_key = f"{service_id}:{action}"

    # -------------------------
    # IDEMPOTENCY CHECK
    # -------------------------
    with LOCK:
        now = time.time()
        if len(EXECUTION_LOCKS) > 100:
            cleanup_all_expired(now)

        if lock_key in EXECUTION_LOCKS:
            entry = EXECUTION_LOCKS[lock_key]
            if now - entry["timestamp"] > LOCK_TTL_SECONDS:
                del EXECUTION_LOCKS[lock_key]

        if lock_key in EXECUTION_LOCKS:
            existing = EXECUTION_LOCKS[lock_key]

            # ✅ ONLY block if execution is ongoing
            if existing["status"] == "in_progress":
                return {
                    "execution_id": existing["execution_id"],
                    "status": "duplicate_blocked",
                    "verified": None,
                    "trace_id": trace_id
                }

        # set execution start
        EXECUTION_LOCKS[lock_key] = {
            "execution_id": execution_id,
            "status": "in_progress",
            "timestamp": now
        }

        

        

    # If failed → allow retry (DO NOTHING, continue execution)

    # LOCK BEFORE EXECUTION (important)
    # EXECUTION_LOCKS[lock_key] = {
    # "execution_id": execution_id,
    # "status": "in_progress"
    #                     }
   

    try:
        # -------------------------
        # EXECUTION
        # -------------------------
        perform_execution(service_id, action)

        # -------------------------
        # VERIFICATION
        # -------------------------
        verified = verify_execution(service_id, action)

        status = "success" if verified else "failed"
        execution_state = "COMPLETED" if verified else "FAILED"
        with LOCK:
            EXECUTION_LOCKS[lock_key]["status"] = status
            EXECUTION_LOCKS[lock_key]["timestamp"] = time.time()

        # ✅ LOG execution_result
        log_event(
            "execution_result",
            {
                "service_id": service_id,
                "action": action,
                "status": status
            },
            trace_id=trace_id,
            execution_id=execution_id
        )

        # ✅ LOG verification
        log_event(
            "verification",
            {
                "service_id": service_id,
                "action": action,
                "verified": verified
            },
            trace_id=trace_id,
            execution_id=execution_id
        )

        return {
            "execution_id": execution_id,
            "status": status,
            "verified": verified,
            "execution_state": execution_state,
            "execution_contract": (
                advance_execution_state(execution_contract, execution_state).model_dump(mode="json")
                if execution_contract else None
            ),
            "trace_id": trace_id
        }

    except Exception as e:
        error_msg = str(e).lower()

        if "no such container" in error_msg:
            reason = "container_not_found"
        else:
            reason = "execution_error"

        with LOCK:
            EXECUTION_LOCKS[lock_key]["status"] = "failed"
            EXECUTION_LOCKS[lock_key]["timestamp"] = time.time()

        # ✅ LOG execution_result (FAILED)
        log_event(
            "execution_result",
            {
                "service_id": service_id,
                "action": action,
                "status": "failed"
            },
            trace_id=trace_id,
            execution_id=execution_id
        )

        # ✅ LOG verification (FAILED)
        log_event(
            "verification",
            {
                "service_id": service_id,
                "action": action,
                "verified": False
            },
            trace_id=trace_id,
            execution_id=execution_id
        )

        return {
            "execution_id": execution_id,
            "status": "failed",
            "reason": reason,
            "verified": False,
            "execution_state": "FAILED",
            "execution_contract": (
                advance_execution_state(execution_contract, "FAILED").model_dump(mode="json")
                if execution_contract else None
            ),
            "trace_id": trace_id
        }

    # except Exception:
    #     EXECUTION_LOCKS[lock_key]["status"] = "failed"

    #     return {
    #         "execution_id": execution_id,
    #         "status": "failed",
    #         "reason": "unknown_error",
    #         "verified": False,
    #         "trace_id": trace_id
    #     }




    # except Exception:
    #     return {
    #         "execution_id": execution_id,
    #         "status": "failed",
    #         "reason": "unknown_error",
    #         "verified": False,
    #         "trace_id": trace_id
    #     }












# -------------------------
# EXECUTION ROUTER
# -------------------------
def perform_execution(service_id, action):
    if EXECUTION_MODE == "docker":
        docker_execute(service_id, action)
    elif EXECUTION_MODE == "kubernetes":
        k8s_execute(service_id, action)
    else:
        raise Exception("Invalid EXECUTION_MODE")


# -------------------------
# DOCKER EXECUTION
# -------------------------

def docker_execute(service_id, action):
    result = subprocess.run(
        ["docker", action, service_id],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(result.stderr or result.stdout or "docker_error")






# def docker_execute(service_id, action):
#     if action == "restart":
#         subprocess.run(
#             ["docker", "restart", service_id],
#             check=True,
#             capture_output=True,
#             text=True
#         )

#     elif action == "start":
#         subprocess.run(
#             ["docker", "start", service_id],
#             check=True,
#             capture_output=True,
#             text=True
#         )

#     elif action == "stop":
#         subprocess.run(
#             ["docker", "stop", service_id],
#             check=True,
#             capture_output=True,
#             text=True
#         )

#     # elif action == "start":
#     #     subprocess.run(["docker", "start", service_id], check=True)

#     # elif action == "stop":
#     #     subprocess.run(["docker", "stop", service_id], check=True)

#     else:
#         raise Exception(f"Unsupported action: {action}")


# -------------------------
# K8S EXECUTION (stub)
# -------------------------
def k8s_execute(service_id, action):
    raise NotImplementedError("Kubernetes not implemented yet")


# -------------------------
# VERIFICATION ROUTER
# -------------------------
def verify_execution(service_id, action):
    if EXECUTION_MODE == "docker":
        return docker_verify(service_id, action)
    elif EXECUTION_MODE == "kubernetes":
        return k8s_verify(service_id, action)
    return False


# -------------------------
# DOCKER VERIFICATION
# -------------------------
def docker_verify(service_id, action):
    try:
        result = subprocess.check_output(["docker", "inspect", service_id])
        data = json.loads(result)[0]

        running = data["State"]["Running"]

        if action == "restart":
            return running
        elif action == "start":
            return running
        elif action == "stop":
            return not running

        return False

    except Exception:
        return False


# -------------------------
# K8S VERIFICATION (stub)
# -------------------------
def k8s_verify(service_id, action):
    raise NotImplementedError("Kubernetes verification not implemented")
