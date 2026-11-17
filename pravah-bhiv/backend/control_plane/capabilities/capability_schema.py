"""
Capability Registry Schema Definitions.

Defines the required and optional fields for capabilities
registered in the Group 4 Capability Registry.
"""
from control_plane.capabilities.capability_types import is_valid_capability_type

REQUIRED_CAPABILITY_FIELDS = [
    "registry_version",
    "registry_kind",
    "capability_id",
    "capability_name",
    "capability_type",
    "owner",
    "maturity",
    "status",
    "runtime",
    "produces"
]

OPTIONAL_CAPABILITY_FIELDS = [
    "device",
    "source",
    "metadata"
]

VALID_REGISTRY_KINDS = [
    "capability"
]

VALID_MATURITY_LEVELS = [
    "V1",
    "V2",
    "V3",
    "V4"
]

VALID_CAPABILITY_STATUSES = [
    "DOCUMENTED",
    "PRESENT",
    "TESTED",
    "VERIFIED",
    "ACTIVE",
    "BLOCKED",
    "DEPRECATED"
]

def validate_capability_spec(spec: dict) -> list[str]:
    """
    Validate a capability specification.

    Returns:
        A list of validation errors.
        Empty list means validation passed.
    """

    errors = []

    # Required fields
    for field in REQUIRED_CAPABILITY_FIELDS:
        if field not in spec:
            errors.append(
                f"Missing required field: {field}"
            )

    # Stop deeper validation if required fields are missing
    if errors:
        return errors

    # Registry kind
    if spec["registry_kind"] not in VALID_REGISTRY_KINDS:
        errors.append(
            f"Invalid registry_kind: {spec['registry_kind']}"
        )

    # Capability type must exist in central taxonomy
    if not is_valid_capability_type(spec["capability_type"]):
        errors.append(
            f"Invalid capability_type: "
            f"{spec['capability_type']}"
        )

    # Maturity validation
    if spec["maturity"] not in VALID_MATURITY_LEVELS:
        errors.append(
            f"Invalid maturity level: "
            f"{spec['maturity']}"
        )

    # Capability status validation
    if spec["status"] not in VALID_CAPABILITY_STATUSES:
        errors.append(
            f"Invalid capability status: "
            f"{spec['status']}"
        )

    # Owner must be structured
    if not isinstance(spec["owner"], dict):
        errors.append(
            "owner must be an object"
        )
    else:
        if "group" not in spec["owner"]:
            errors.append(
                "owner.group is required"
            )

    # Runtime must be structured
    if not isinstance(spec["runtime"], dict):
        errors.append(
            "runtime must be an object"
        )
    else:
        if "service_hosted" not in spec["runtime"]:
            errors.append(
                "runtime.service_hosted is required"
            )

        if not isinstance(
            spec["runtime"].get("service_hosted"),
            bool
        ):
            errors.append(
                "runtime.service_hosted must be boolean"
            )

    # Produces must be a list
    if not isinstance(spec["produces"], list):
        errors.append(
            "produces must be a list"
        )

    return errors
