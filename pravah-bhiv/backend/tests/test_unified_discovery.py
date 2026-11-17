import pytest
from control_plane.multi_app_control_plane import MultiAppControlPlane
from control_plane.capabilities.capability_discovery import CapabilityDiscovery

def test_unified_discovery():
    print("\nStarting unified discovery tests...")
    
    # 1. Check existing applications
    cp = MultiAppControlPlane(env="dev")
    apps = cp.list_apps()
    
    # Assert that list_apps doesn't include the non-service capability
    for app in apps:
        assert app.get("app_name") != "group3-field-edge", "list_apps should ignore capabilities"
    print(f"[PASS] Found {len(apps)} legacy apps.")

    # 2. Check standalone capability discovery
    discovery = CapabilityDiscovery()
    capabilities = discovery.discover_all()
    group3_cap = next((c for c in capabilities if c.get("capability_id") == "group3-field-edge"), None)
    
    assert group3_cap is not None, "group3-field-edge capability should be found"
    assert group3_cap["service_hosted"] is False, "service_hosted should be False"
    print(f"[PASS] Capability discovery works separately.")

    # 3. Check unified entities list
    entities = cp.list_runtime_entities()
    
    found_apps = [e for e in entities if e.get("entity_kind") == "application"]
    found_caps = [e for e in entities if e.get("entity_kind") == "capability"]
    
    assert len(found_apps) == len(apps), "Entity list should contain all apps"
    assert len(found_caps) == len(capabilities), "Entity list should contain all capabilities"
    print(f"[PASS] Unified list works (Apps: {len(found_apps)}, Caps: {len(found_caps)}).")

    # 4. Verify health overview is unaffected
    overview = cp.get_health_overview()
    for item in overview:
        assert item.get("app_name") != "group3-field-edge", "Health overview should completely ignore capabilities"
    print("[PASS] Health overview ignores capabilities.")

    print("\n--- ALL UNIFIED DISCOVERY ASSERTIONS PASSED ---")
