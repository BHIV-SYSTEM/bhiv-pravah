"""
Capability Discovery Module.

Reads from the Capability Registry Manager and provides a runtime-friendly
flattened format for the Control Plane.
"""
from control_plane.capabilities.capability_registry_manager import CapabilityRegistryManager

class CapabilityDiscovery:
    def __init__(self):
        self.registry_manager = CapabilityRegistryManager()

    def _format_for_runtime(self, spec: dict) -> dict:
        """Flattens the nested capability spec into a runtime-friendly dictionary."""
        owner = spec.get("owner", {})
        runtime = spec.get("runtime", {})
        
        return {
            "capability_id": spec.get("capability_id"),
            "capability_name": spec.get("capability_name"),
            "capability_type": spec.get("capability_type"),
            "status": spec.get("status"),
            "maturity": spec.get("maturity"),
            "service_hosted": runtime.get("service_hosted", False),
            "endpoint": runtime.get("endpoint"),
            "owner_group": owner.get("group"),
            "module_id": owner.get("module_id"),
            "produces": spec.get("produces", [])
        }

    def discover_all(self) -> list[dict]:
        """Discover all registered capabilities in runtime-friendly format."""
        specs = self.registry_manager.list_capabilities()
        return [self._format_for_runtime(spec) for spec in specs]

    def discover_by_id(self, capability_id: str) -> dict | None:
        """Discover a specific capability by ID."""
        spec = self.registry_manager.get_capability(capability_id)
        if spec:
            return self._format_for_runtime(spec)
        return None

    def discover_by_type(self, capability_type: str) -> list[dict]:
        """Discover capabilities matching a specific type."""
        capabilities = self.discover_all()
        return [c for c in capabilities if c.get("capability_type") == capability_type]

    def discover_by_status(self, status: str) -> list[dict]:
        """Discover capabilities matching a specific status."""
        capabilities = self.discover_all()
        return [
            c for c in capabilities
            if c.get("status") == status
        ]

    def discover_by_group(self, group: str) -> list[dict]:
        """Discover capabilities owned by a specific group."""
        capabilities = self.discover_all()
        return [
            c for c in capabilities
            if c.get("owner_group") == group
        ]
