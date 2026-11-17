"""
Test the Phase 15 Pravah Integration Boundary.

This tests the internal callable service (`process_vana_governed_abstention`)
which Karan's VANA runtime will invoke. This proves the *local integration*
of the governed abstention flow without usurping ownership of the `/vana/execute`
HTTP endpoint.
"""

import json
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[2] / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
from VANA.vana_integration import process_vana_governed_abstention
from control_plane.core.action_governance import ActionGovernance

def test_vana_integration_boundary_processes_local_ruling_correctly(tmp_path):
    """
    Simulate Karan's system passing the authoritative ruling to the Pravah
    governed boundary.
    """
    
    # 1. Load the real Group 2 ruling as an external system would (using GAP fixture for Phase 15 isolation)
    ruling_path = Path(__file__).resolve().parents[2] / "backend" / "integration" / "group2" / "fixtures" / "temporal_ruling_gap.json"
    ruling = json.loads(ruling_path.read_text(encoding="utf-8"))
    
    # 2. To avoid shared persistent governance state exhaustion in pytest,
    # we mock the governance call, as the governance policy itself is not under test here.
    from unittest.mock import patch
    from control_plane.core.action_governance import GovernanceDecision
    
    approved_decision = GovernanceDecision(
        should_block=False,
        policy_id="action_governance_v1",
        policy_version="v1",
        admission_state="POLICY_ADMITTED",
    )
    
    with patch("VANA.vana_integration.ActionGovernance.evaluate_contract", return_value=approved_decision):
        # 3. Process via the Pravah boundary, injecting runtime provenance
        evidence_1 = process_vana_governed_abstention(
            ruling=ruling,
            trace_id="trace-123",
            execution_id="exec-abc"
        )
        
        assert evidence_1["event_type"] == "GOVERNED_ABSTENTION"
        assert evidence_1["abstention_record_id"].startswith("abstention-")
        assert evidence_1["decision_action"] == "noop"
        
        # 4. Prove replay safety and deterministic identity through the boundary
        evidence_2 = process_vana_governed_abstention(
            ruling=ruling,
            trace_id="trace-456",  # Different trace
            execution_id="exec-def" # Different execution
        )
        
        assert evidence_1["abstention_record_id"] == evidence_2["abstention_record_id"], (
            "Replaying the same ruling through the boundary must yield identical abstention_record_id"
        )
        assert evidence_1["event_id"] != evidence_2["event_id"], (
            "Replaying must yield distinct ledger event_ids"
        )
        
        # Check that provenance was merged properly in the event output
        assert evidence_1["execution_id"] == "exec-abc"
        assert evidence_2["execution_id"] == "exec-def"
