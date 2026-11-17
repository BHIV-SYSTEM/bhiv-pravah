import pytest
import sys
from pathlib import Path

# Add backend to sys.path so control_plane can be imported
backend_dir = Path(__file__).resolve().parents[2] / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from control_plane.backend.app.main import app

client = TestClient(app)

GROUP2_AUTHORITATIVE_PAYLOAD = {
    "observation_id": "TC-Z03-EXT-OPENMETEO-OBS001",
    "canonical_record_id": "CR-b4615a27-7ab1-4bde-a078-a56fa0f2414c",
    "context_id": None,
    "ruling": "ABSTAIN",
    "action_eligibility": False,
    "abstention_required": True,
    "action_request": None,
    "evidence": {
        "source": "Open-Meteo.com — EXTERNAL LIVE API",
        "confidence": "NOT VERIFIED",
        "missing_critical_data": "NONE_BUT_UNVERIFIED",
        "provenance_reference": "open-meteo:8d26e68328ac160f",
        "artifact_hash": "8d26e68328ac160f7b69f1a24ccb2de4972ff9fc60af11093c246903a7c52502",
        "artifact_type": "sensor_reading",
        "observation_timestamp": "2026-08-25T11:00:00Z",
        "retrieval_timestamp": "2026-08-25T11:04:16Z",
        "attribution": "Weather data by Open-Meteo.com (CC-BY 4.0), aggregating national weather services.",
        "canonical_observation_location": "19.1288, 72.9421"
    },
    "provenance": {
        "group2_decision_time": "2026-08-27T10:15:01.076Z",
        "reason": "CONTEXT_NOT_VERIFIED",
        "message": "Authoritative evidence threshold not met (Context not verified). Failing closed to ABSTAIN."
    }
}

def test_vana_execute_live_payload():
    """
    Test that the /vana/execute endpoint correctly processes the raw Group 2 runtime payload,
    delegates it to the Group4IntakeBoundary, and produces a governed abstention record
    with strict preservation of Group 2 semantics and lineage.
    """
    # First Request
    response1 = client.post("/vana/execute", json=GROUP2_AUTHORITATIVE_PAYLOAD)
    assert response1.status_code == 200, f"Expected 200 OK, got {response1.status_code}. Response: {response1.text}"
    
    data1 = response1.json()
    assert data1["status"] == "governed_abstention", "Endpoint must return governed_abstention for ABSTAIN ruling"
    
    evidence1 = data1["evidence"]
    
    # Verify strict preservation rules
    assert evidence1["context_id"] is None, "context_id must remain null"
    assert evidence1["ruling"] == "ABSTAIN", "Ruling must remain ABSTAIN"
    assert evidence1["observation_id"] == "TC-Z03-EXT-OPENMETEO-OBS001", "Observation ID must be strictly preserved"
    assert evidence1["canonical_record_id"] == "CR-b4615a27-7ab1-4bde-a078-a56fa0f2414c", "Canonical Record ID must be strictly preserved"
    
    # Replay Request (Determinism check)
    response2 = client.post("/vana/execute", json=GROUP2_AUTHORITATIVE_PAYLOAD)
    assert response2.status_code == 200
    
    data2 = response2.json()
    evidence2 = data2["evidence"]
    
    assert evidence1["abstention_record_id"] == evidence2["abstention_record_id"], "Abstention Record ID must be deterministic on replay"
