"""Configuration constants for the stateless Decision Brain backend."""

import os

DEMO_FROZEN = True
STATELESS = True
SUCCESS_RATE = 1.0

CPU_SCALE_UP_THRESHOLD = 95
CPU_SCALE_DOWN_THRESHOLD = 30
MEMORY_SCALE_UP_THRESHOLD = 85

ACTION_SCOPE: dict[str, list[str]] = {
    "DEV": ["noop", "scale_up", "scale_down", "restart"],
    "STAGE": ["noop", "scale_up", "scale_down"],
    "PROD": ["noop", "restart"],
}


class BackendConfig:
    """Runtime host/port config for local serving."""

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("BACKEND_PORT", os.getenv("PORT", "7999")))
