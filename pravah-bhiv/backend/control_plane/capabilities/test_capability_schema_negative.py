from capability_schema import validate_capability_spec


BASE_CAPABILITY = {
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
    ]
}


def run_test(test_name, payload):
    errors = validate_capability_spec(payload)

    print(f"\n{test_name}")

    if errors:
        print("REJECTED")
        for error in errors:
            print(f"- {error}")
    else:
        print("UNEXPECTED PASS")


# Test 1: Invalid capability type
invalid_type = BASE_CAPABILITY.copy()
invalid_type["capability_type"] = "random_robotics"

run_test(
    "TEST 1: Invalid Capability Type",
    invalid_type
)


# Test 2: Invalid maturity
invalid_maturity = BASE_CAPABILITY.copy()
invalid_maturity["maturity"] = "V99"

run_test(
    "TEST 2: Invalid Maturity",
    invalid_maturity
)


# Test 3: Invalid status
invalid_status = BASE_CAPABILITY.copy()
invalid_status["status"] = "LIVE"

run_test(
    "TEST 3: Invalid Status",
    invalid_status
)


# Test 4: Owner is not an object
invalid_owner = BASE_CAPABILITY.copy()
invalid_owner["owner"] = "group3"

run_test(
    "TEST 4: Invalid Owner Structure",
    invalid_owner
)


# Test 5: Runtime service_hosted is not boolean
invalid_runtime = BASE_CAPABILITY.copy()
invalid_runtime["runtime"] = {
    "service_hosted": "false"
}

run_test(
    "TEST 5: Invalid Runtime Structure",
    invalid_runtime
)


# Test 6: Produces is not a list
invalid_produces = BASE_CAPABILITY.copy()
invalid_produces["produces"] = "observation_mission_package"

run_test(
    "TEST 6: Invalid Produces Structure",
    invalid_produces
)


# Test 7: Missing required field
missing_field = BASE_CAPABILITY.copy()
del missing_field["capability_id"]

run_test(
    "TEST 7: Missing Required Field",
    missing_field
)
