import sys
import os

# Add the control_plane directory to sys.path to allow relative imports if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capability_schema import validate_capability_spec


GROUP3_FIELD_EDGE_CAPABILITY = {
    "registry_version": "1.0",
    "registry_kind": "capability",

    "capability_id": "group3-field-edge",

    "capability_name": "field_observation_producer",

    "capability_type": "edge_robotics",

    "owner": {
        "group": "group3",
        "module_id": "group3-field-edge"
    },

    "maturity": "V1",

    "status": "DOCUMENTED",

    "runtime": {
        "service_hosted": False,
        "endpoint": None
    },

    "produces": [
        "observation_mission_package"
    ],

    "device": {
        "device_id": "G3-LIDAR-001",
        "hardware_verified": False,
        "calibration_status": "NOT_VERIFIED",
        "testing_status": "NOT_TESTED"
    },

    "source": {
        "is_synthetic": True,
        "source_type": "SYNTHETIC_TEST"
    }
}


errors = validate_capability_spec(
    GROUP3_FIELD_EDGE_CAPABILITY
)

if errors:
    print("VALIDATION FAILED")
    for error in errors:
        print(f"- {error}")
else:
    print("VALIDATION PASSED")
