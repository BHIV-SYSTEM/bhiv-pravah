#!/usr/bin/env python3
"""
verify_masterdb_observability.py
=================================
Verification script to validate `bhiv-masterdb-ingestion-certification-service` 
runtime telemetry & ecosystem event integration with Pravah.
"""

import os
import sys
import time
import uuid
import json
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' library not found. Install via: pip install requests")
    sys.exit(1)

PRAVAH_URL = os.getenv("PRAVAH_URL", "http://localhost:7000")
MASTERDB_URL = os.getenv("MASTERDB_URL", "http://localhost:8000")
SSPL_SECRET = os.getenv("SSPL_SECRET_KEY", "default-secret-key-change-in-prod")

def log_test_case(name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    if details:
        print(f"         {details}")

def main():
    print("=" * 75)
    print("  Pravah Observer -- BHIV MasterDB Service Integration Verification")
    print("=" * 75)
    print(f"  Target Pravah Base URL   : {PRAVAH_URL}")
    print(f"  Target MasterDB Base URL : {MASTERDB_URL}")
    print("=" * 75)

    # 1. Test direct telemetry signal from MasterDB adapter logic
    print("\n[Test 1] Emitting direct telemetry signal via pravah_adapter...")
    try:
        masterdb_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "bhiv-masterdb-ingestion-certification-service"))
        if masterdb_path not in sys.path:
            sys.path.insert(0, masterdb_path)
        from observability.pravah_adapter import emit_pravah_signal
        
        emit_pravah_signal(
            state="running",
            latency_ms=12.5,
            errors_last_min=0,
            workers=2,
            extra={"test_event": "masterdb_observability_verification"}
        )
        log_test_case("MasterDB Pravah Telemetry Signal Emitter", True, "Dispatched fire-and-forget signal without exception")
    except Exception as exc:
        log_test_case("MasterDB Pravah Telemetry Signal Emitter", False, f"Failed: {exc}")

    # 2. Test publishing masterdb ecosystem event to Pravah
    print("\n[Test 2] POST /pravah/events (Publish MasterDB Certification Ecosystem Event)...")
    trace_id = f"masterdb-trace-{uuid.uuid4().hex[:12]}"
    correlation_id = f"masterdb-corr-{uuid.uuid4().hex[:12]}"
    
    event_payload = {
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "source": "BHIV_MASTERDB",
        "action": "masterdb_ingestion_certification",
        "event_type": "dataset_certified",
        "payload": {
            "dataset_id": "ds-sample-001",
            "certification_status": "CERTIFIED",
            "risk_score": 0.05
        },
        "source_system": "BHIV_MASTERDB",
        "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer shakti-secret-key-change-in-prod",
        "X-Source-System": "SHAKTI"
    }

    try:
        resp = requests.post(f"{PRAVAH_URL}/pravah/events", json=event_payload, headers=headers, timeout=5)
        passed = resp.status_code == 200
        details = ""
        if passed:
            res_json = resp.json()
            passed = res_json.get("status") == "CONNECTED" and "pipeline_latency_ms" in res_json
            details = json.dumps(res_json, indent=2)
        log_test_case("POST /pravah/events (MasterDB Event Publish)", passed, f"Response {resp.status_code}:\n{details}")
    except Exception as exc:
        log_test_case("POST /pravah/events (MasterDB Event Publish)", False, f"Error reaching Pravah at {PRAVAH_URL}: {exc}")

    print("\n" + "=" * 75)
    print("  BHIV MasterDB - Pravah Observability Integration Verification Complete!")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    main()
