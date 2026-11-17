"""
Capability Taxonomy Definitions for Group 4 Registry.
Establishes the central taxonomy for capability types, starting with edge_robotics.
"""

VALID_CAPABILITY_TYPES = {
    "edge_robotics": {
        "description": (
            "Capabilities that produce, process, or manage "
            "observations from edge devices, robotics systems, "
            "field sensors, or controlled mission packages."
        )
    }
}

def is_valid_capability_type(capability_type: str) -> bool:
    """Check if the given capability type exists in the taxonomy."""
    return capability_type in VALID_CAPABILITY_TYPES
