import pytest
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from control_plane.capabilities.capability_discovery import CapabilityDiscovery

def test_group1_observation_api():
    """
    TEST 1: group1-observation-api
    Expected: registry discovery + live runtime verification
    """
    discovery = CapabilityDiscovery()
    cap = discovery.discover_by_id("group1-observation-api")
    
    assert cap is not None
    assert cap["capability_id"] == "group1-observation-api"
    # Verify the runtime metadata based on recent LIVE updates
    assert cap["endpoint"] == "http://163.128.209.18:8013"

def test_group3_field_edge():
    """
    TEST 2: group3-field-edge
    Expected: discovered but unavailable (service_hosted is false/null endpoint)
    """
    discovery = CapabilityDiscovery()
    cap = discovery.discover_by_id("group3-field-edge")
    
    assert cap is not None
    assert cap["capability_id"] == "group3-field-edge"
    assert cap["status"] == "DOCUMENTED"
    assert cap["service_hosted"] is False

def test_group2_scientific_context():
    """
    TEST 3: group2-scientific-context
    Expected: discovered but blocked
    """
    discovery = CapabilityDiscovery()
    cap = discovery.discover_by_id("group2-scientific-context")
    
    assert cap is not None
    assert cap["capability_id"] == "group2-scientific-context"
    assert cap["status"] == "BLOCKED"

def test_governed_execution():
    """
    TEST 4: governed-execution
    Expected: present + execution rights verified (rights are verified elsewhere, check present here)
    """
    discovery = CapabilityDiscovery()
    cap = discovery.discover_by_id("governed-execution")
    
    assert cap is not None
    assert cap["capability_id"] == "governed-execution"
    assert cap["status"] == "PRESENT"

def test_bucket_evidence():
    """
    TEST 5: bucket-evidence
    Expected: discovered + blocked status based on HTTP 503 evidence in registry
    """
    discovery = CapabilityDiscovery()
    cap = discovery.discover_by_id("bucket-evidence")
    
    assert cap is not None
    assert cap["capability_id"] == "bucket-evidence"
    assert cap["status"] == "BLOCKED"

def test_replay_runtime():
    """
    TEST 6: replay-runtime
    Expected: implementation present + endpoint verification required
    """
    discovery = CapabilityDiscovery()
    cap = discovery.discover_by_id("replay-runtime")
    
    assert cap is not None
    assert cap["capability_id"] == "replay-runtime"
    assert cap["status"] == "PRESENT"
    assert cap["endpoint"] is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
