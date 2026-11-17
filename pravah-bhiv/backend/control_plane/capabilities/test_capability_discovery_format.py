import json
from capability_discovery import CapabilityDiscovery

discovery = CapabilityDiscovery()

print("\n--- Testing Runtime-Friendly Discovery ---")

print("\n1. Discover All:")
all_caps = discovery.discover_all()
print(json.dumps(all_caps, indent=4))

print("\n2. Discover By ID (group3-field-edge):")
cap = discovery.discover_by_id("group3-field-edge")
if cap:
    print(f"Found capability_id: {cap['capability_id']}")
    print(f"Service Hosted: {cap['service_hosted']}")
else:
    print("NOT FOUND")

print("\n3. Discover By Type (edge_robotics):")
type_caps = discovery.discover_by_type("edge_robotics")
print(f"Count: {len(type_caps)}")
