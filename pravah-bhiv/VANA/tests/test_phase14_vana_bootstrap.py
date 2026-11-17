import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

backend_dir = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_dir))

import control_plane.multi_app_control_plane
control_plane.multi_app_control_plane.MultiAppControlPlane = MagicMock()

from control_plane.capabilities.execution_rights_adapter import ExecutionRightsAdapter, authorize_execution, MappingNotFound, CapabilityNotFound
from control_plane.capabilities.capability_discovery import CapabilityDiscovery
from control_plane.capabilities.capability_registry_manager import CapabilityRegistryManager

@pytest.fixture
def registry_manager():
    return CapabilityRegistryManager()

@pytest.fixture
def discovery():
    return CapabilityDiscovery()

@pytest.fixture
def rights_adapter(discovery):
    return ExecutionRightsAdapter(discovery=discovery)

def test_deterministic_id(registry_manager):
    # In Pravah, the capability_id acts as the deterministic ID
    cap = registry_manager.get_capability("vana-environmental_observation")
    assert cap is not None
    assert cap["capability_id"] == "vana-environmental_observation"

def test_correct_registration(registry_manager):
    cap = registry_manager.get_capability("vana-environmental_observation")
    assert cap is not None
    assert cap["owner"]["module_id"] == "VANA"
    assert cap["metadata"]["operation"] == "environmental_observation"
    assert cap["metadata"]["resource_scope"] == "mangrove_site_*"
    assert cap["metadata"]["risk_classification"] == "LOW"

def test_capability_rights_linkage(rights_adapter):
    mapping = rights_adapter.verified_mappings.get("vana-environmental_observation")
    assert mapping is not None
    assert mapping["source_id"] == "VANA"
    assert mapping["role"] == "environmental_observation"
    assert "environmental_observation" in mapping["allowed_actions"]
    assert mapping["verification"]["status"] == "VERIFIED"
    assert "VANA/vana-environmental_observation.json" in mapping["evidence"]["file"]

def test_valid_execution_permission(rights_adapter):
    # This should succeed and return the authorization object
    auth = authorize_execution("vana-environmental_observation", "environmental_observation", adapter=rights_adapter)
    assert auth is not None
    assert auth["authorized_source_id"] == "VANA"
    assert auth["action"] == "environmental_observation"

def test_invalid_holder_rejection(rights_adapter):
    # We pass a wrong capability ID which means holder/mapping won't match
    with pytest.raises(CapabilityNotFound):
        authorize_execution("invalid-holder", "environmental_observation", adapter=rights_adapter)

def test_invalid_action_rejection(rights_adapter):
    # Valid holder, but invalid action
    with pytest.raises(MappingNotFound):
        authorize_execution("vana-environmental_observation", "invalid_action", adapter=rights_adapter)

def test_idempotency_behavior(registry_manager):
    # Ensure retrieving multiple times yields the same object, representing idempotent behavior in read
    cap1 = registry_manager.get_capability("vana-environmental_observation")
    cap2 = registry_manager.get_capability("vana-environmental_observation")
    assert cap1 == cap2
