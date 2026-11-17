#!/usr/bin/env python3
"""
verify_shakti_observability.py
==============================
Standalone verification script to validate GC-Shakti endpoints in Pravah:
  1. POST /pravah/events
  2. POST /evidence
  3. GET /evidence/{evidence_ref}
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
    print("[ERROR] 'requests' library not found. Run: pip install requests")
    sys.exit(1)

# Configuration
BASE_URL = os.getenv("PRAVAH_URL", "http://localhost:7000")
API_KEY = os.getenv("PRAVAH_API_KEY", "shakti-secret-key-change-in-prod")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
    "X-Source-System": "SHAKTI"
}

def log_test_case(name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    if details:
        print(f"         {details}")

def main():
    print("=" * 70)
    print("  Pravah Observer -- GC-Shakti Integration verification script")
    print("=" * 70)
    print(f"  Target Base URL : {BASE_URL}")
    print(f"  Auth Token Key  : Bearer {API_KEY[:8]}...")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # TEST CASE 1: Unauthorized Check (POST /pravah/events)
    # -------------------------------------------------------------------------
    print("\n[Running Test 1] POST /pravah/events with invalid headers...")
    bad_headers = HEADERS.copy()
    bad_headers["Authorization"] = "Bearer wrong-key-123"
    
    try:
        resp = requests.post(f"{BASE_URL}/pravah/events", json={}, headers=bad_headers, timeout=5)
        log_test_case("POST /pravah/events (Unauthorized Check)", resp.status_code == 401, f"Response: {resp.status_code} - {resp.text.strip()}")
    except Exception as exc:
        log_test_case("POST /pravah/events (Unauthorized Check)", False, f"Error: {exc}")

    # -------------------------------------------------------------------------
    # TEST CASE 2: Publish Ecosystem Event (POST /pravah/events)
    # -------------------------------------------------------------------------
    print("\n[Running Test 2] POST /pravah/events (Publish Ecosystem Event)...")
    trace_id = f"shakti-trace-{uuid.uuid4().hex[:12]}"
    correlation_id = f"shakti-corr-{uuid.uuid4().hex[:12]}"
    
    event_payload = {
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "source": "SHAKTI_GC",
        "action": "pravah_publish_compliance_check",
        "event_type": "compliance_check",
        "payload": {
            "component": "ledger",
            "decision": "commit",
            "block_index": 4820
        },
        "source_system": "SHAKTI",
        "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    try:
        resp = requests.post(f"{BASE_URL}/pravah/events", json=event_payload, headers=HEADERS, timeout=5)
        passed = resp.status_code == 200
        details = ""
        if passed:
            res_json = resp.json()
            passed = res_json.get("status") == "CONNECTED" and "pipeline_latency_ms" in res_json
            details = json.dumps(res_json, indent=2)
        log_test_case("POST /pravah/events (Ecosystem Event Publish)", passed, f"Response {resp.status_code}:\n{details}")
    except Exception as exc:
        log_test_case("POST /pravah/events (Ecosystem Event Publish)", False, f"Error: {exc}")

    # -------------------------------------------------------------------------
    # TEST CASE 3: Publish Evidence Bundle (POST /evidence)
    # -------------------------------------------------------------------------
    print("\n[Running Test 3] POST /evidence (Publish Evidence Bundle)...")
    bundle_id = f"bundle-{uuid.uuid4().hex[:12]}"
    execution_id = f"exec-{uuid.uuid4().hex[:12]}"
    decision_id = f"dec-{uuid.uuid4().hex[:12]}"
    
    evidence_payload = {
        "bundle_id": bundle_id,
        "trace_id": trace_id,
        "execution_id": execution_id,
        "decision_id": decision_id,
        "decision_type": "constitutional_compliance",
        "authority_chain": ["SHAKTI_ORCHESTRATOR", "SHAKTI_GC_VALIDATOR"],
        "evidence": [
            {
                "rule_id": "rule-40",
                "status": "PASS",
                "provenance_signature": "0x48f98ab12"
            }
        ],
        "replay_reference": "ref-98204",
        "constitutional_hash": "sha256-f8319ab921b72a0f8",
        "produced_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "correlation_id": correlation_id,
        "source": "SHAKTI_GC",
        "action": "publish_evidence"
    }

    evidence_ref = None
    try:
        resp = requests.post(f"{BASE_URL}/evidence", json=evidence_payload, headers=HEADERS, timeout=5)
        passed = resp.status_code == 200
        details = ""
        if passed:
            res_json = resp.json()
            evidence_ref = res_json.get("evidence_ref")
            passed = bool(evidence_ref)
            details = json.dumps(res_json, indent=2)
        log_test_case("POST /evidence (Publish Evidence Bundle)", passed, f"Response {resp.status_code}:\n{details}")
    except Exception as exc:
        log_test_case("POST /evidence (Publish Evidence Bundle)", False, f"Error: {exc}")

    # -------------------------------------------------------------------------
    # TEST CASE 4: Retrieve Evidence Bundle (GET /evidence/{evidence_ref})
    # -------------------------------------------------------------------------
    if not evidence_ref:
        print("\n[Skipping Test 4] Evidence reference not available because Test 3 failed.")
        sys.exit(1)
        
    print(f"\n[Running Test 4] GET /evidence/{evidence_ref} (Retrieve Evidence)...")
    try:
        resp = requests.get(f"{BASE_URL}/evidence/{evidence_ref}", headers=HEADERS, timeout=5)
        passed = resp.status_code == 200
        details = ""
        if passed:
            res_json = resp.json()
            passed = res_json.get("bundle_id") == bundle_id
            details = json.dumps(res_json, indent=2)
        log_test_case("GET /evidence/{evidence_ref} (Retrieve Evidence Bundle)", passed, f"Response {resp.status_code}:\n{details[:300]}...")
    except Exception as exc:
        log_test_case("GET /evidence/{evidence_ref} (Retrieve Evidence Bundle)", False, f"Error: {exc}")

    print("\n" + "=" * 70)
    print("  GC-Shakti End-to-End Integration Verification Complete!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
