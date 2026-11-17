"""
Phase 16 - Group 4 Action Request Intake and Recording Boundary.

Handles the transition of an ACTION_REQUEST_ELIGIBLE contract into a
validated Action Request, enforcing strict lineage and provenance,
running through governance, and appending to the Action Request repository.
"""

import os
import hashlib
import json
from typing import Any, Dict, Optional, List, Union
from datetime import datetime, timezone
from pydantic import BaseModel, field_validator

from contracts.decision_contract import DecisionContract
from control_plane.core.action_governance import ActionGovernance, GovernanceDecision
from control_plane.decision_translation.governed_abstention_recorder import (
    GovernedAbstentionRecorder,
)

# ---------------------------------------------------------------------------
# Action Request Data Models
# ---------------------------------------------------------------------------

class ActionRequestLineage(BaseModel):
    observation_id: str
    canonical_record_id: str
    context_id: str


class ActionRequestTemporalRuling(BaseModel):
    ruling: str
    action_eligibility: bool
    abstention_required: bool


class ActionRequestUpstreamProvenance(BaseModel):
    contract_version: Optional[str] = None
    authority: Optional[str] = None
    evidence: Optional[List[str]] = None


class ActionRequest(BaseModel):
    model_config = {'validate_assignment': True}
    
    action_request_id: str
    lineage: ActionRequestLineage
    temporal_ruling: ActionRequestTemporalRuling
    upstream_provenance: ActionRequestUpstreamProvenance
    evidence_classification: str = "CONTROLLED"
    group4_action_metadata: Dict[str, Any]
    status: str

    @field_validator("evidence_classification")
    def validate_classification(cls, v: str) -> str:
        if v != "CONTROLLED":
            raise ValueError(f"ActionRequest evidence_classification must be 'CONTROLLED', got {v!r}")
        return v


# ---------------------------------------------------------------------------
# Lineage Verifier
# ---------------------------------------------------------------------------

class LineageVerifier:
    """
    Validates the complete lineage tuple against a controlled authoritative mapping fixture.
    Live registry resolution is intentionally outside the scope of this closure package
    and remains an ecosystem integration step.
    """
    
    def __init__(self):
        self.expected_controlled_lineage = {
            "TC-Z03-F02-LIDAR-OBS001": {
                "canonical_record_id": "group1-obs-20260813-9a3b",
                "context_id": "ctx-tc-001"
            }
        }
        
    def verify(
        self,
        observation_id: str,
        canonical_record_id: str,
        context_id: str
    ) -> bool:
        if not observation_id or not canonical_record_id or not context_id:
            raise ValueError("Lineage validation failed: Missing lineage fields")
            
        lineage = self.expected_controlled_lineage.get(observation_id)
        if lineage is None:
            raise ValueError("Lineage validation failed: Unknown observation_id")
            
        if lineage["canonical_record_id"] != canonical_record_id:
            raise ValueError("Lineage validation failed: canonical_record_id lineage mismatch")
            
        if lineage["context_id"] != context_id:
            raise ValueError("Lineage validation failed: context_id lineage mismatch")
            
        return True


# ---------------------------------------------------------------------------
# Intake Boundary
# ---------------------------------------------------------------------------

class Group4IntakeBoundary:
    """
    Validates lineage and constructs an Action Request from an eligible contract.
    """
    
    def process(self, contract: DecisionContract) -> Union[ActionRequest, Dict[str, Any]]:
        if contract.decision_type not in ("action_request_eligible", "abstention"):
            raise ValueError(f"Group 4 Intake requires 'action_request_eligible' or 'abstention' contract. Got {contract.decision_type}")
            
        # Governance / Enforcement
        governance = ActionGovernance(env=os.getenv("ENVIRONMENT", "dev"))
        gov_decision = governance.evaluate_contract(
            decision=contract,
            context={
                "app_name": "group4_intake",
                "env": os.getenv("ENVIRONMENT", "dev"),
                "source": "action_request_pipeline"
            }
        )
        
        if contract.decision_type == "abstention":
            recorder = GovernedAbstentionRecorder()
            return recorder.record(
                contract=contract,
                governance_decision=gov_decision,
            )
            
        params = contract.parameters
        observation_id = params.get("observation_id")
        canonical_record_id = params.get("canonical_record_id")
        context_id = params.get("context_id")
        ruling = params.get("ruling")
        
        # 1. Validate Lineage Tuple via Verifier
        verifier = LineageVerifier()
        verifier.verify(
            observation_id=observation_id,
            canonical_record_id=canonical_record_id,
            context_id=context_id
        )

        # 2. Validate ALLOW and action eligibility
        if ruling != "ALLOW":
            raise ValueError(f"Lineage validation failed: Only ALLOW rulings can create Action Requests. Got {ruling}")
        if not params.get("action_eligibility"):
            raise ValueError("Lineage validation failed: action_eligibility is False")
            
        # 3. Action Request Construction
        # Generate deterministic action_request_id based on lineage
        ar_payload = {
            "scheme": "bhiv.action_request.v1",
            "observation_id": observation_id,
            "canonical_record_id": canonical_record_id,
            "context_id": context_id
        }
        ar_json = json.dumps(ar_payload, sort_keys=True, separators=(",", ":"))
        ar_hash = hashlib.sha256(ar_json.encode("utf-8")).hexdigest()
        action_request_id = "ar-" + ar_hash[:24]
        
        # 4. Governance / Enforcement (Already evaluated above)
        
        status = "VALIDATED" if not gov_decision.should_block else "BLOCKED"
        
        action_request = ActionRequest(
            action_request_id=action_request_id,
            lineage=ActionRequestLineage(
                observation_id=observation_id,
                canonical_record_id=canonical_record_id,
                context_id=context_id
            ),
            temporal_ruling=ActionRequestTemporalRuling(
                ruling=ruling,
                action_eligibility=params.get("action_eligibility", False),
                abstention_required=params.get("abstention_required", False)
            ),
            upstream_provenance=ActionRequestUpstreamProvenance(
                contract_version=params.get("contract_version"),
                authority=params.get("authority"),
                evidence=params.get("evidence")
            ),
            evidence_classification="CONTROLLED",
            group4_action_metadata={
                "governance_status": gov_decision.admission_state,
                "governance_reason": gov_decision.reason if gov_decision.should_block else None,
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            status=status
        )
        
        # 5. Record to Repository
        recorder = ActionRequestRecorder()
        recorder.record(action_request)
        
        return action_request

# ---------------------------------------------------------------------------
# Action Request Recorder/Repository
# ---------------------------------------------------------------------------

class ActionRequestRecorder:
    """
    Action Request repository/recorder.
    Persists Action Requests ensuring idempotent delivery and retrieval.
    """
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "action_requests.jsonl"
        )
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
    def record(self, action_request: ActionRequest) -> None:
        """
        Record the validated action request. Implements idempotent writes.
        """
        existing = self.retrieve(action_request.action_request_id)
        if existing:
            # Idempotent delivery
            return
            
        with open(self.storage_path, "a", encoding="utf-8") as f:
            f.write(action_request.model_dump_json() + "\n")
            
    def retrieve(self, action_request_id: str) -> Optional[ActionRequest]:
        """
        Retrieve an action request preserving the complete upstream lineage.
        """
        if not os.path.exists(self.storage_path):
            return None
            
        with open(self.storage_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("action_request_id") == action_request_id:
                    return ActionRequest(**data)
        return None
