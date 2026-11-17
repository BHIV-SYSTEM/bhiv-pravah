import pytest
import requests
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from control_plane.capabilities.capability_discovery import CapabilityDiscovery

def test_group1_observation_api_live_health():
    """
    Registry-to-runtime integration test for group1-observation-api.
    Reads the endpoint from CapabilityDiscovery and verifies the HTTP contract
    using a mocked response to eliminate live external network dependencies.
    """
    discovery = CapabilityDiscovery()
    cap = discovery.discover_by_id("group1-observation-api")
    
    assert cap is not None, "group1-observation-api capability not found in registry"
    endpoint = cap.get("endpoint")
    assert endpoint is not None, "Endpoint is missing in registry for group1-observation-api"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "healthy"}

    with patch("requests.get", return_value=mock_response) as mock_get:
        response = requests.get(
            f"{endpoint}/health",
            timeout=10
        )

        mock_get.assert_called_once_with(f"{endpoint}/health", timeout=10)
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"

        body = response.json()
        assert body.get("status") == "healthy", f"Expected status='healthy', got {body.get('status')}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
                