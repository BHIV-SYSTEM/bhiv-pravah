"""
Capability Registry -> Execution Rights Adapter

This module bridges the Capability Registry and the Execution Rights/Constitutional Boundary System.
"""
import sys
from pathlib import Path

# Add the 'backend' directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

PROJECT_ROOT = Path(__file__).resolve().parents[3]

from typing import Dict, Any
from copy import deepcopy
from control_plane.capabilities.capability_discovery import CapabilityDiscovery

class CapabilityNotFound(Exception):
    pass

class MappingNotFound(Exception):
    pass

# The mapping must remain empty unless there is explicit repository evidence.
# Future mapping entries must support evidence metadata.
# Expected structure:
# VERIFIED_CAPABILITY_MAPPINGS = {
#     "some-capability": {
#         "source_id": "actual-existing-identifier",
#         "role": "actual-existing-role",
#         "evidence": {
#             "file": "path/to/file",
#             "line": 123
#         }
#     }
# }
VERIFIED_CAPABILITY_MAPPINGS = {
    "governed-execution": {
        "source_id": "governance",
        "role": "execution_authority",
        "allowed_actions": [
            "restart",
            "scale_up",
            "scale_down",
            "rollback"
        ],
        "verification": {
            "status": "VERIFIED"
        },
        "evidence": {
            "file": "backend/contracts/execution_contract.py",
            "line": 194
        }
    },
    "vana-environmental_observation": {
        "source_id": "VANA",
        "role": "environmental_observation",
        "allowed_actions": [
            "environmental_observation"
        ],
        "verification": {
            "status": "VERIFIED"
        },
        "evidence": {
            "file": "VANA/vana-environmental_observation.json",
            "line": 1
        }
    }
}

class ExecutionRightsAdapter:
    def __init__(self, discovery: CapabilityDiscovery = None, mappings: Dict[str, Any] = None):
        self.discovery = discovery or CapabilityDiscovery()
        if mappings is not None:
            self.verified_mappings = deepcopy(mappings)
        else:
            self.verified_mappings = deepcopy(VERIFIED_CAPABILITY_MAPPINGS)

    def _validate_mapping(self, capability_id: str, mapping: Dict[str, Any]) -> None:
        if not isinstance(mapping, dict):
            raise MappingNotFound(
                f"Invalid mapping structure for capability: {capability_id}"
            )

        source_id = mapping.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise MappingNotFound(
                f"Incomplete or invalid mapping for capability "
                f"{capability_id}: 'source_id' must be a non-empty string."
            )

        allowed_actions = mapping.get("allowed_actions")
        if not isinstance(allowed_actions, list) or not allowed_actions:
            raise MappingNotFound(
                f"Incomplete mapping for capability "
                f"{capability_id}: missing 'allowed_actions'."
            )
        for act in allowed_actions:
            if not isinstance(act, str) or not act.strip():
                raise MappingNotFound(
                    f"Invalid allowed_action in mapping for capability {capability_id}"
                )

        verification = mapping.get("verification", {})
        if verification.get("status") != "VERIFIED":
            raise MappingNotFound(
                f"Execution mapping is not verified: {capability_id}"
            )

        evidence = mapping.get("evidence")
        if not isinstance(evidence, dict):
            raise MappingNotFound(
                f"Incomplete or invalid mapping for capability "
                f"{capability_id}: 'evidence' must be a dictionary."
            )

        evidence_file = evidence.get("file")
        if not isinstance(evidence_file, str) or not evidence_file.strip():
            raise MappingNotFound(
                f"Invalid evidence.file for capability: {capability_id}"
            )

        project_root = PROJECT_ROOT.resolve()
        candidate = (project_root / evidence_file).resolve()

        try:
            candidate.relative_to(project_root)
        except ValueError:
            raise MappingNotFound(
                f"Evidence file escapes repository root: {evidence_file}"
            )

        if not candidate.is_file():
            raise MappingNotFound(
                f"Evidence file does not exist: {evidence_file}"
            )

        evidence_line = evidence.get("line")
        if not isinstance(evidence_line, int):
            raise MappingNotFound(
                f"Invalid evidence line for {capability_id}"
            )
        if evidence_line < 1:
            raise MappingNotFound(
                f"Evidence line must be >= 1 for {capability_id}"
            )

        with candidate.open("r", encoding="utf-8") as f:
            total_lines = sum(1 for _ in f)

        if evidence_line > total_lines:
            raise MappingNotFound(
                f"Evidence line {evidence_line} exceeds file length {total_lines}"
            )

    def resolve_mapping(self, capability_id: str) -> Dict[str, Any]:
        """
        Resolves a capability into its verified Execution Rights mapping.
        """
        capability = self.discovery.discover_by_id(capability_id)
        if capability is None:
            raise CapabilityNotFound(
                f"Capability not found in Capability Registry: {capability_id}"
            )
            
        mapping = self.verified_mappings.get(capability_id)
        if mapping is None:
            raise MappingNotFound(
                f"No verified Execution Rights mapping exists for "
                f"capability: {capability_id}"
            )
            
        self._validate_mapping(capability_id, mapping)
            
        return deepcopy({
            "capability_id": capability_id,
            "authorized_source_id": mapping["source_id"],
            "role": mapping.get("role"),
            "allowed_actions": mapping["allowed_actions"],
            "mapping_status": "VERIFIED",
            "evidence": mapping["evidence"]
        })

    def generate_execution_payload(self, capability_id: str, action: str, service_id: str, trace_id: str, caller_source_id: str) -> Dict[str, Any]:
        """
        Generates the required metadata for governance_gate and the executor
        based on the verified capability mapping.
        """
        mapping = self.resolve_mapping(capability_id)
        
        return {
            "service_id": service_id,
            "action": action,
            "trace_id": trace_id,
            "source": caller_source_id,
            "authorized_source_id": mapping["authorized_source_id"],
            "capability_id": capability_id,
            "role": mapping.get("role"),
            "allowed_actions": mapping["allowed_actions"]
        }

def authorize_execution(
    capability_id: str,
    action: str,
    adapter: ExecutionRightsAdapter = None
) -> Dict[str, Any]:
    """
    Central fail-closed execution authorization boundary.

    Every state-changing execution path must pass through here
    before ActionGovernance or a downstream executor is reached.
    """
    if not isinstance(capability_id, str) or not capability_id.strip():
        raise CapabilityNotFound(
            "Execution blocked: capability_id is required."
        )

    if not isinstance(action, str) or not action.strip():
        raise MappingNotFound(
            "Execution blocked: action is required."
        )

    adapter = adapter or ExecutionRightsAdapter()
    mapping = adapter.resolve_mapping(capability_id)

    normalized_action = action.strip().lower()
    allowed = [a.strip().lower() for a in mapping["allowed_actions"]]
    if normalized_action not in allowed:
        raise MappingNotFound(
            f"Action '{action}' is not authorized for capability "
            f"'{capability_id}'."
        )

    from security.signed_trace import sign_trace, canonicalize

    auth_payload = {
        "capability_id": capability_id,
        "action": normalized_action,
        "authorized_source_id": mapping["authorized_source_id"],
        "role": mapping.get("role"),
        "allowed_actions": mapping["allowed_actions"],
        "mapping_status": mapping["mapping_status"],
        "evidence": mapping["evidence"],
    }

    # Cryptographically sign the authorization to prevent upstream forgery
    signature = sign_trace(canonicalize(auth_payload))
    auth_payload["signature"] = signature

    return deepcopy(auth_payload)

if __name__ == "__main__":
    adapter = ExecutionRightsAdapter()
    print("\n--- Testing Execution Rights Adapter (Fail-Closed) ---")
    
    # Test 1: Known capability with no mapping
    print("\n1. Testing known capability (governed-execution) with no mapping:")
    try:
        adapter.resolve_mapping("governed-execution")
    except MappingNotFound as e:
        print(f"EXPECTED: {e}")
        
    # Test 2: Unknown capability
    print("\n2. Testing unknown capability (non-existent-capability):")
    try:
        adapter.resolve_mapping("non-existent-capability")
    except CapabilityNotFound as e:
        print(f"EXPECTED: {e}")
        
    # Test 3: generate_execution_payload fails closed
    print("\n3. Testing generate_execution_payload on unmapped capability:")
    try:
        adapter.generate_execution_payload("governed-execution", "restart", "apps02", "trace-1")
    except MappingNotFound as e:
        print(f"EXPECTED: No payload generated. Failed closed with: {e}")
