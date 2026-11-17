"""
Capability Registry Manager.

Handles validation, storage, and retrieval of capability
definitions independently from the legacy application registry.
"""

import json
from pathlib import Path

from control_plane.capabilities.capability_schema import validate_capability_spec


class CapabilityRegistryManager:
    def __init__(self):
        self.registry_dir = (
            Path(__file__).parent / "registry"
        )
        self.vana_registry_dir = (
            Path(__file__).resolve().parents[3] / "VANA"
        )

        self.registry_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    def register_capability(self, spec: dict) -> dict:
        """
        Validate and store a capability specification.

        Raises:
            ValueError: If validation fails.
            FileExistsError: If capability already exists.
        """

        errors = validate_capability_spec(spec)

        if errors:
            raise ValueError(
                "; ".join(errors)
            )

        capability_id = spec["capability_id"]

        file_path = (
            self.registry_dir /
            f"{capability_id}.json"
        )

        if file_path.exists():
            raise FileExistsError(
                f"Capability already exists: "
                f"{capability_id}"
            )

        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as handle:
            json.dump(
                spec,
                handle,
                indent=4
            )

        return {
            "status": "REGISTERED",
            "capability_id": capability_id,
            "registry_path": str(file_path)
        }

    def get_capability(
        self,
        capability_id: str
    ) -> dict | None:
        """
        Retrieve a capability by ID.
        """

        file_path = (
            self.registry_dir /
            f"{capability_id}.json"
        )
        vana_path = (
            self.vana_registry_dir /
            f"{capability_id}.json"
        )

        if file_path.exists():
            target_path = file_path
        elif vana_path.exists():
            target_path = vana_path
        else:
            return None

        with open(
            target_path,
            "r",
            encoding="utf-8"
        ) as handle:
            return json.load(handle)

    def list_capabilities(self) -> list[dict]:
        """
        Retrieve all registered capabilities.
        """

        capabilities = []
        
        all_paths = list(self.registry_dir.glob("*.json"))
        if self.vana_registry_dir.exists():
            all_paths.extend(self.vana_registry_dir.glob("*.json"))

        for file_path in all_paths:
            if file_path.name == ".gitkeep":
                continue
            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as handle:
                capabilities.append(
                    json.load(handle)
                )

        return capabilities
