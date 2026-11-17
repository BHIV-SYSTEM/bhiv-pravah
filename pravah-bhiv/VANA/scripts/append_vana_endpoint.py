"""
Script to append VANA governed abstention API endpoint to main.py
"""
import pathlib

f = pathlib.Path(__file__).parents[2] / "backend" / "control_plane" / "backend" / "app" / "main.py"
content = f.read_text(encoding="utf-8")

NEW_ENDPOINT = """

# ===========================================================================
# Phase 15 - VANA Governed Abstention Integration (Live Group 2 Consumption)
# ===========================================================================

@app.post("/vana/execute")
def vana_execute(request: dict):
    \"\"\"
    Endpoint to process live Group 2 runtime responses for VANA.
    
    This fulfills the integration requirement to consume a real Group 2 
    ruling from the HTTP POST body, translate it into a DecisionContract,
    and process it through the Group4IntakeBoundary. For ABSTAIN rulings,
    it records a governed abstention without executing any operational action.
    \"\"\"
    from control_plane.decision_translation.contextual_result_adapter import ContextualResultAdapter
    from control_plane.decision_translation.group4_intake import Group4IntakeBoundary
    
    # 1. Translate the raw Group 2 JSON payload to a DecisionContract
    adapter = ContextualResultAdapter()
    contract = adapter.translate(request)
    
    # 2. Process through the Group 4 Intake Boundary
    intake = Group4IntakeBoundary()
    result = intake.process(contract)
    
    # 3. Return the exact governed abstention (or action request) structure
    if isinstance(result, dict) and "abstention_record_id" in result:
        # Explicitly preserve the canonical_record_id from the incoming contract
        result["canonical_record_id"] = contract.parameters.get("canonical_record_id")
        return {
            "status": "governed_abstention",
            "evidence": result
        }
    else:
        # If it was an ALLOW (not expected for this abstention test)
        return {
            "status": "action_request_generated",
            "evidence": result.model_dump() if hasattr(result, "model_dump") else result
        }
"""

if "vana_execute" not in content:
    f.write_text(content + NEW_ENDPOINT, encoding="utf-8")
    print("Endpoint appended.")
else:
    print("Endpoint already exists.")
