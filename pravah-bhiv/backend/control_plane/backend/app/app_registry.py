import json
from pathlib import Path

# Locate the control_plane directory
CONTROL_PLANE_ROOT = Path(__file__).resolve().parents[2]

REGISTRY_PATH = CONTROL_PLANE_ROOT / "config" / "apps_registry.json"


def load_apps():
    """Load application registry."""

    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"apps_registry.json not found at {REGISTRY_PATH}")

    with open(REGISTRY_PATH, "r") as f:
        data = json.load(f)

    return data["apps"]