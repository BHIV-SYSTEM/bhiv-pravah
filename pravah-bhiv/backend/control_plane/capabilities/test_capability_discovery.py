from capability_discovery import CapabilityDiscovery

discovery = CapabilityDiscovery()

print("\n--- Testing Capability Discovery ---")

print("\n1. Discover All:")
all_caps = discovery.discover_all()
for c in all_caps:
    print(f"- {c['capability_id']} ({c['capability_type']})")

print("\n2. Discover By Type (edge_robotics):")
edge_caps = discovery.discover_by_type("edge_robotics")
for c in edge_caps:
    print(f"- {c['capability_id']}")

print("\n3. Discover By Type (unknown_type):")
unknown_caps = discovery.discover_by_type("unknown_type")
print(f"Found: {len(unknown_caps)}")

print("\n4. Discover By Status (DOCUMENTED):")
doc_caps = discovery.discover_by_status("DOCUMENTED")
for c in doc_caps:
    print(f"- {c['capability_id']}")

print("\n5. Discover By Group (group3):")
group_caps = discovery.discover_by_group("group3")
for c in group_caps:
    print(f"- {c['capability_id']}")
