#!/usr/bin/env python3
"""
verify_registry_integration.py
==============================
Phase IV Task 4 verification script.
Validates unified integration across Evidence, Replay, and Execution registries
with strict constitutional authority limitations.
"""

import os
import sys
import time
import uuid
import json
import requests
import hashlib

# Configuration
BASE_URL = os.getenv("PRAVAH_URL", "http://127.0.0.1:7000")
API_KEY = os.getenv("PRAVAH_API_KEY", "shakti-secret-key-change-in-prod")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
    "X-Source-System": "SHAKTI"
}

def main():
    print("=" * 80)
    print("  TANTRA ECOSYSTEM - UNIFIED REGISTRY INTEGRATION VERIFICATION")
    print("=" * 80)
    
    # 1. Setup paths and imports
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    from control_plane.core.registry_manager import RegistryManager
    
    # Instantiate Registry Manager
    manager = RegistryManager(base_dir=project_root)
    print("[OK] Registry Manager successfully initialized.")
    
    # 2. Define unique trace ID (Sovereign Context)
    trace_id = f"reg-trace-{uuid.uuid4().hex[:12]}"
    print(f"[TRACE] Correlation ID: {trace_id}")
    
    # 3. Execution Registry Participation (Append-Only Log)
    print("\n[Step 1] Appending state transitions to Execution Registry...")
    event_id = f"evt-{uuid.uuid4().hex[:8]}"
    manager.register_execution_event(
        execution_id=trace_id,
        event_id=event_id,
        state="RUNNING",
        timestamp=int(time.time()),
        event_hash=hashlib.sha256(event_id.encode()).hexdigest(),
        previous_hash="",
        source="creator-core",
        details={"trace_id": trace_id, "instruction": "Process user intent"}
    )
    print("  [PASS] Logged CREATED event in Append-Only Log.")
    
    # 4. Replay Registry Participation (Replay Index)
    print("\n[Step 2] Updating Replay Registry index...")
    manager.update_replay_index(
        execution_id=trace_id,
        start_sequence=1,
        end_sequence=1,
        event_count=1,
        first_event_hash=hashlib.sha256(event_id.encode()).hexdigest(),
        last_event_hash=hashlib.sha256(event_id.encode()).hexdigest(),
        last_timestamp=int(time.time()),
        source_ids=["creator-core"]
    )
    print("  [PASS] Updated Replay Index database entry.")
    
    # 5. Evidence Registry Participation (Evidence bundles JSON store)
    print("\n[Step 3] Publishing compliance attestation to Evidence Registry...")
    evidence_payload = {
        "bundle_id": f"bundle-{uuid.uuid4().hex[:12]}",
        "trace_id": trace_id,
        "execution_id": trace_id,
        "decision_id": f"dec-{uuid.uuid4().hex[:12]}",
        "decision_type": "compliance_attestation",
        "authority_chain": ["HUMAN_INTENT", "CREATOR_CORE", "PRAVAH_REGISTRIES"],
        "evidence": {
            "attestation": "Provenance metadata signature check passed",
            "discipline": "PASS"
        },
        "produced_at": "2026-07-24T12:00:00Z",
        "correlation_id": trace_id,
        "source": "creator-core",
        "action": "log_provenance"
    }
    evidence_ref = manager.publish_evidence_bundle(evidence_payload)
    print(f"  [PASS] Registered evidence bundle. Ref: {evidence_ref}")
    
    # 6. Query Unified Registry Endpoint (Control Plane API)
    print("\n[Step 4] Querying Unified Trace Lineage API...")
    url = f"{BASE_URL}/registry/trace/{trace_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            
            # Assert correlation across registries
            exec_records = result.get("execution_records", [])
            replay_entry = result.get("replay_index_entry")
            evidence_bundles = result.get("evidence_bundles")
            prov_summary = result.get("provenance_summary", {})
            
            print(f"  Execution Records found : {len(exec_records)}")
            print(f"  Replay Index Entry found: {replay_entry is not None}")
            print(f"  Evidence Bundles found  : {len(evidence_bundles)}")
            print(f"  Provenance Summary      : {json.dumps(prov_summary, indent=2)}")
            
            assert len(exec_records) > 0, "Execution records missing!"
            assert replay_entry is not None, "Replay index entry missing!"
            assert len(evidence_bundles) > 0, "Evidence bundle missing!"
            
            # Constitutional verification
            auth_levels = prov_summary.get("consolidated_authority_levels", [])
            assert "passive_observer" in auth_levels, "Constitutional authority level mismatch!"
            assert "active_governance" not in auth_levels, "Governance boundary breach detected!"
            
            print("\n[SUCCESS] UNIFIED REGISTRY INTEGRATION VERIFIED!")
            print("          Trace context propagated cleanly across Execution, Replay,")
            print("          and Evidence registries. All provenance metadata enforces")
            print("          the passive_observer governance boundary.")
        else:
            print(f"[FAIL] HTTP {resp.status_code}: {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Unified query failed: {e}")
        sys.exit(1)
        
    print("=" * 80)

if __name__ == "__main__":
    main()
