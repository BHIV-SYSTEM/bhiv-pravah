from capability_registry_manager import (
    CapabilityRegistryManager
)


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


manager = CapabilityRegistryManager()


# -------------------------------------------------
# TEST 1: Register capability
# -------------------------------------------------

print("\nTEST 1: Register Capability")

try:
    result = manager.register_capability(
        GROUP3_FIELD_EDGE_CAPABILITY
    )

    print("REGISTERED")
    print(result)

except FileExistsError:
    print("ALREADY EXISTS")


# -------------------------------------------------
# TEST 2: Retrieve capability
# -------------------------------------------------

print("\nTEST 2: Retrieve Capability")

capability = manager.get_capability(
    "group3-field-edge"
)

if capability:
    print("RETRIEVED")
    print(capability["capability_id"])
else:
    print("NOT FOUND")


# -------------------------------------------------
# TEST 3: List capabilities
# -------------------------------------------------

print("\nTEST 3: List Capabilities")

capabilities = manager.list_capabilities()

print(f"COUNT: {len(capabilities)}")

for capability in capabilities:
    print(
        f"- {capability['capability_id']}"
    )


# -------------------------------------------------
# TEST 4: Duplicate registration
# -------------------------------------------------

print("\nTEST 4: Duplicate Registration")

try:
    manager.register_capability(
        GROUP3_FIELD_EDGE_CAPABILITY
    )

    print("UNEXPECTED DUPLICATE ACCEPTED")

except FileExistsError as error:
    print("DUPLICATE REJECTED")
    print(error)
