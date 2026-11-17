"""
Ecosystem Registry Integration Manager.
Binds Evidence Registry, Replay Registry, and Execution Registry.
Ensures participation is strictly bounded by constitutional ownership (passive observation).
"""

import os
import json
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# Relative imports to control plane persistence
from control_plane.persistence.append_only_log import AppendOnlyLog
from control_plane.persistence.replay_index import ReplayIndex

class ConstitutionalRegistryError(Exception):
    """Raised when governance boundary is violated."""
    pass

class RegistryManager:
    """
    Unified manager for TANTRA Ecosystem Registries.
    Maintains clean boundaries:
    - Execution Registry (Append-Only Log)
    - Replay Registry (Replay Index)
    - Evidence Registry (Evidence Bundles JSON store)
    """
    
    def __init__(
        self,
        base_dir: Optional[str] = None,
        env: str = "dev"
    ):
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        self.base_dir = Path(base_dir)
        self.env = env
        
        # Initialize Execution Registry (Append-Only Journal)
        log_path = self.base_dir / "logs" / "control_plane" / "append_only_log.jsonl"
        self.execution_registry = AppendOnlyLog(log_path=str(log_path))
        
        # Initialize Replay Registry (Replay Index)
        index_path = self.base_dir / "logs" / "control_plane" / "replay_index.json"
        self.replay_registry = ReplayIndex(index_path=str(index_path))
        
        # Evidence Registry Path
        self.evidence_path = self.base_dir / "data" / "evidence_bundles.json"
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        
    def _get_provenance_metadata(self, source: str) -> Dict[str, Any]:
        """
        Generate passive provenance metadata.
        Constitutional enforcement: authority_level is strictly 'passive_observer'.
        """
        config_hash = hashlib.sha256(source.encode()).hexdigest()[:16]
        return {
            "authority_level": "passive_observer",
            "governance_role": "observability_only",
            "system_origin": source,
            "operator_hash": f"prov-{config_hash}",
            "ingested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "environment": self.env
        }
        
    def register_execution_event(
        self,
        execution_id: str,
        event_id: str,
        state: str,
        timestamp: int,
        event_hash: str,
        previous_hash: str,
        source: str,
        details: Dict[str, Any]
    ) -> None:
        """
        Append event to the Execution Registry.
        Enforces passive observation boundaries on incoming payloads.
        """
        # Inject passive observer tag into details to prevent governance escalation
        details_copy = dict(details)
        details_copy["provenance"] = self._get_provenance_metadata(source)
        
        self.execution_registry.append(
            execution_id=execution_id,
            event_id=event_id,
            state=state,
            timestamp=timestamp,
            event_hash=event_hash,
            previous_hash=previous_hash,
            source=source,
            details=details_copy
        )
        
    def update_replay_index(
        self,
        execution_id: str,
        start_sequence: int,
        end_sequence: int,
        event_count: int,
        first_event_hash: str,
        last_event_hash: str,
        last_timestamp: int,
        source_ids: List[str]
    ) -> None:
        """
        Update the Replay Registry index for fast reconstructability checks.
        """
        self.replay_registry.update_execution(
            execution_id=execution_id,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            event_count=event_count,
            first_event_hash=first_event_hash,
            last_event_hash=last_event_hash,
            last_timestamp=last_timestamp,
            source_ids=source_ids
        )
        
    def publish_evidence_bundle(self, bundle: Dict[str, Any]) -> str:
        """
        Publish a signed compliance bundle to the Evidence Registry.
        Adds structural provenance tags.
        """
        import uuid
        evidence_ref = f"ev-{uuid.uuid4().hex[:16]}"
        
        # Load existing evidence bundles
        bundles = {}
        if self.evidence_path.exists():
            try:
                with open(self.evidence_path, "r", encoding="utf-8") as f:
                    bundles = json.load(f)
            except Exception:
                bundles = {}
                
        # Inject provenance metadata block
        bundle_copy = dict(bundle)
        bundle_copy["evidence_ref"] = evidence_ref
        bundle_copy["provenance"] = self._get_provenance_metadata(bundle.get("source", "unknown"))
        
        bundles[evidence_ref] = bundle_copy
        
        with open(self.evidence_path, "w", encoding="utf-8") as f:
            json.dump(bundles, f, indent=2)
            
        return evidence_ref
        
    def query_trace_lineage(self, trace_id: str) -> Dict[str, Any]:
        """
        Perform a unified runtime evidence index lookup.
        Correlates a trace_id across all 3 registries (Execution, Replay, and Evidence).
        """
        result = {
            "trace_id": trace_id,
            "execution_records": [],
            "replay_index_entry": None,
            "evidence_bundles": [],
            "provenance_summary": None
        }
        
        # 1. Query Execution Registry (Append-Only Log events)
        # Scan log for events where details contain matching trace_id
        if self.execution_registry.log_path.exists():
            try:
                with open(self.execution_registry.log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        record = json.loads(line)
                        event = record.get("event", {})
                        details = event.get("details", {})
                        # Match trace_id either as top-level or in details
                        if details.get("trace_id") == trace_id or event.get("execution_id") == trace_id:
                            result["execution_records"].append(event)
            except Exception:
                pass
                
        # 2. Query Replay Registry
        replay_entry = self.replay_registry.get_execution(trace_id)
        if replay_entry:
            result["replay_index_entry"] = {
                "execution_id": replay_entry.execution_id,
                "start_sequence": replay_entry.start_sequence,
                "end_sequence": replay_entry.end_sequence,
                "event_count": replay_entry.event_count,
                "first_event_hash": replay_entry.first_event_hash,
                "last_event_hash": replay_entry.last_event_hash,
                "last_timestamp": replay_entry.last_timestamp,
                "source_ids": replay_entry.source_ids
            }
            
        # 3. Query Evidence Registry
        if self.evidence_path.exists():
            try:
                with open(self.evidence_path, "r", encoding="utf-8") as f:
                    bundles = json.load(f)
                    for ref, b in bundles.items():
                        if b.get("trace_id") == trace_id or b.get("correlation_id") == trace_id:
                            result["evidence_bundles"].append(b)
            except Exception:
                pass
                
        # 4. Extract Provenance Summary
        origins = set()
        authority_levels = set()
        for rec in result["execution_records"]:
            prov = rec.get("details", {}).get("provenance", {})
            if prov:
                origins.add(prov.get("system_origin"))
                authority_levels.add(prov.get("authority_level"))
                
        for b in result["evidence_bundles"]:
            prov = b.get("provenance", {})
            if prov:
                origins.add(prov.get("system_origin"))
                authority_levels.add(prov.get("authority_level"))
                
        result["provenance_summary"] = {
            "contributing_systems": list(origins),
            "consolidated_authority_levels": list(authority_levels),
            "governance_adherence": "COMPLIANT" if "active_governance" not in authority_levels else "VIOLATION"
        }
        
        return result
