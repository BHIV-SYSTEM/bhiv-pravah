#!/usr/bin/env python3
"""
Container Watchdog
Monitors Docker container status and performs auto-restart actions
"""

import subprocess
from control_plane.core.env_config import EnvironmentConfig

# class ContainerWatchdog:
#     """Monitors and manages Docker container health."""
    
#     def __init__(self, env='dev'):
#         self.env_config = EnvironmentConfig(env)
        























#     def execute_action(self, payload: dict):

#         from control_plane.core.contracts import validate_execution_input

#         validate_execution_input(payload)
#         ALLOWED_ACTIONS = {"start", "restart"}

#         if payload["action"] not in ALLOWED_ACTIONS:
#             return {
#                 "service_id": payload["service_id"],
#                 "action": payload["action"],
#                 "status": "failed",
#                 "error": "invalid_action"
#             }

#         service_id = payload["service_id"]
#         action = payload["action"]

#         try:
#             if action == "restart":
#                 cmd = ["docker", "restart", service_id]

#             elif action == "start":
#                 cmd = ["docker", "start", service_id]

#             else:
#                 return {
#                     "service_id": service_id,
#                     "action": action,
#                     "status": "failed",
#                     "error": "unsupported_action"
#                 }

#             result = subprocess.run(
#                 cmd,
#                 capture_output=True,
#                 text=True,
#                 timeout=30
#             )

#             if result.returncode != 0:
#                 return {
#                     "service_id": service_id,
#                     "action": action,
#                     "status": "failed",
#                     "error": result.stderr.strip() or "command_failed"
#                 }

#             return {
#                 "service_id": service_id,
#                 "action": action,
#                 "status": "success"
#             }

#         except subprocess.TimeoutExpired:
#             return {
#                 "service_id": service_id,
#                 "action": action,
#                 "status": "failed",
#                 "error": "timeout"
#             }

#         except FileNotFoundError:
#             return {
#                 "service_id": service_id,
#                 "action": action,
#                 "status": "failed",
#                 "error": "docker_not_installed"
#             }

#         except Exception as e:
#             return {
#                 "service_id": service_id,
#                 "action": action,
#                 "status": "failed",
#                 "error": str(e)
#             }
        






import subprocess
from control_plane.core.env_config import EnvironmentConfig


class ContainerWatchdog:

    def __init__(self, env='dev'):
        self.env_config = EnvironmentConfig(env)

    def execute_action(self, payload: dict):

        from control_plane.core.contracts import validate_execution_input

        validate_execution_input(payload)

        service_id = payload["service_id"]
        action = payload["action"]

        ALLOWED_ACTIONS = {"start", "restart"}

        if action not in ALLOWED_ACTIONS:
            return {
                "service_id": service_id,
                "action": action,
                "status": "failed",
                "error": "invalid_action"
            }

        try:
            if action == "restart":
                cmd = ["docker", "restart", service_id]

            elif action == "start":
                cmd = ["docker", "start", service_id]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return {
                    "service_id": service_id,
                    "action": action,
                    "status": "failed",
                    "error": result.stderr.strip() or "command_failed"
                }

            return {
                "service_id": service_id,
                "action": action,
                "status": "success"
            }

        except subprocess.TimeoutExpired:
            return {
                "service_id": service_id,
                "action": action,
                "status": "failed",
                "error": "timeout"
            }

        except FileNotFoundError:
            return {
                "service_id": service_id,
                "action": action,
                "status": "failed",
                "error": "docker_not_installed"
            }

        except Exception as e:
            return {
                "service_id": service_id,
                "action": action,
                "status": "failed",
                "error": str(e)
            }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Execution Service")
    parser.add_argument("--env", choices=['dev', 'stage', 'prod'], default='dev')
    parser.add_argument("--service_id", required=True)
    parser.add_argument("--action", required=True)

    args = parser.parse_args()

    watchdog = ContainerWatchdog(args.env)

    result = watchdog.execute_action({
        "service_id": args.service_id,
        "action": args.action
    })

    print(result)

