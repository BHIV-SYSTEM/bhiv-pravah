"""
Pravah integration boundary for VANA Governed Abstention.

This module exposes a Pravah-owned integration function that consumes a Group 2 ruling 
and runtime provenance supplied by the external VANA runtime. Pravah does NOT own the 
VANA HTTP endpoint; instead, the external VANA runtime invokes this boundary function.
"""

import os
from typing import Any, Dict, Optional
from control_plane.decision_translation.contextual_result_adapter import ContextualResultAdapter
from control_plane.core.action_governance import ActionGovernance
from control_plane.decision_translation.governed_abstention_recorder import GovernedAbstentionRecorder

def process_vana_governed_abstention(
    ruling: Dict[str, Any],
    trace_id: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Pravah-owned integration function.

    Consumes a Group 2 ruling and runtime provenance supplied by
    the external VANA runtime. Does not own the VANA HTTP endpoint.
    
    Args:
        ruling: The authoritative Group 2 temporal applicability ruling.
        trace_id: The external trace identifier supplied by VANA runtime.
        execution_id: The external execution identifier supplied by VANA runtime.
        
    Returns:
        Dict representing the recorded GOVERNED_ABSTENTION evidence event.
    """
    
    # Create a copy so we don't mutate the original dictionary
    ruling_payload = ruling.copy()
    
    # Merge optional runtime IDs into ruling parameter map
    if trace_id is not None:
        ruling_payload["trace_id"] = trace_id

    if execution_id is not None:
        ruling_payload["execution_id"] = execution_id

    adapter = ContextualResultAdapter()
    contract = adapter.translate(ruling_payload)

    governance = ActionGovernance(
        env=os.getenv("ENVIRONMENT", "dev")
    )

    # NOOP decisions are passed by governance without being blocked
    gov_decision = governance.evaluate_contract(
        decision=contract,
        context={
            "app_name": "vana",
            "env": os.getenv("ENVIRONMENT", "dev"),
            "source": "external_vana_runtime",
        },
    )

    recorder = GovernedAbstentionRecorder()

    return recorder.record(
        contract=contract,
        governance_decision=gov_decision,
    )
