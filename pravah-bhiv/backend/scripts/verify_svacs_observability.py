#!/usr/bin/env python3
"""
verify_svacs_observability.py
=============================
Verification script to validate `bhiv-svacs-unified-core` 
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
SVACS_URL = os.getenv("SVACS_URL", "http://localhost:8000")

def log_test_case(name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    if details:
        print(f"         {details}")

def main():
    print("=" * 75)
    print("  Pravah Observer -- BHIV SVACS Unified Core Integration Verification")
    print("=" * 75)
    print(f"  Target Pravah Base URL : {PRAVAH_URL}")
    print(f"  Target SVACS Base URL  : {SVACS_URL}")
    print("=" * 75)

    # 1. Test direct telemetry signal from bhiv-svacs adapter logic
    print("\n[Test 1] Emitting direct telemetry signal via bhiv-svacs pravah_adapter...")
    try:
        svacs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "bhiv-svacs-unified-core"))
        if svacs_path not in sys.path:
            sys.path.insert(0, svacs_path)
        from observability.pravah_adapter import emit_pravah_signal
        
        emit_pravah_signal(
            state="running",
            latency_ms=18.6,
            errors_last_min=0,
            workers=1,
            extra={"test_event": "svacs_observability_verification"}
        )
        log_test_case("BHIV-SVACS Pravah Telemetry Signal Emitter", True, "Dispatched fire-and-forget signal without exception")
    except Exception as exc:
        log_test_case("BHIV-SVACS Pravah Telemetry Signal Emitter", False, f"Failed: {exc}")

    # 2. Test publishing bhiv-svacs ecosystem event to Pravah
    print("\n[Test 2] POST /pravah/events (Publish SVACS Maritime Track Ecosystem Event)...")
    trace_id = f"svacs-trace-{uuid.uuid4().hex[:12]}"
    correlation_id = f"svacs-corr-{uuid.uuid4().hex[:12]}"
    
    event_payload = {
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "source": "BHIV_SVACS",
        "action": "vessel_track_processed",
        "event_type": "track_normalized",
        "payload": {
            "vessel_id": "V-MARITIME-8092",
            "lat": 18.92,
            "lon": 72.83,
            "risk": "LOW"
        },
        "source_system": "SHAKTI",
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
        log_test_case("POST /pravah/events (SVACS Event Publish)", passed, f"Response {resp.status_code}:\n{details}")
    except Exception as exc:
        log_test_case("POST /pravah/events (SVACS Event Publish)", False, f"Error reaching Pravah at {PRAVAH_URL}: {exc}")

    print("\n" + "=" * 75)
    print("  BHIV SVACS - Pravah Observability Integration Verification Complete!")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    main()
