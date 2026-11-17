# import subprocess
# import json


# def verify_container_running(service_id: str):
#     try:
#         result = subprocess.run(
#             ["docker", "inspect", service_id],
#             capture_output=True,
#             text=True,
#             timeout=10
#         )

#         if result.returncode != 0:
#             return {
#                 "verified": False,
#                 "reason": "container_not_found"
#             }

#         info = json.loads(result.stdout)[0]
#         is_running = info["State"]["Running"]

#         return {
#             "verified": is_running,
#             "reason": None if is_running else "not_running"
#         }

#     except Exception as e:
#         return {
#             "verified": False,
#             "reason": str(e)
#         }











import subprocess
import json


def verify_container_running(service_id: str):
    try:
        result = subprocess.run(
            ["docker", "inspect", service_id],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return {
                "verified": False,
                "reason": "container_not_found"
            }

        info = json.loads(result.stdout)[0]
        is_running = info["State"]["Running"]

        return {
            "verified": is_running,
            "reason": None if is_running else "not_running"
        }

    except Exception as e:
        return {
            "verified": False,
            "reason": str(e)
        }