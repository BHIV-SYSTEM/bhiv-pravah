"""
Replay Index Generation for Deterministic Reconstruction.

Fast lookup of execution snapshots and event ranges without rescanning.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, List


@dataclass(frozen=True)
class ExecutionIndex:
    """Index entry for fast execution lookup."""
    
    execution_id: str
    start_sequence: int  # First sequence number
    end_sequence: int  # Last sequence number
    event_count: int
    first_event_hash: str
    last_event_hash: str  # Latest hash in chain
    last_timestamp: int
    source_ids: List[str]  # Unique source IDs (e.g., ['governance', 'test'])


class ReplayIndex:
    """
    Fast deterministic replay index.
    
    Maps execution_id -> ExecutionIndex for O(1) lookups.
    Eliminates need to scan entire journal for reconstruction.
    """
    
    def __init__(self, index_path: str = "logs/control_plane/replay_index.json"):
        """Initialize replay index."""
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory index
        self._index: Dict[str, ExecutionIndex] = {}
        
        # Load existing index if present
        self._load_index()
    
    def _load_index(self) -> None:
        """Load index from file."""
        if not self.index_path.exists():
            return
        
        try:
            with open(self.index_path, 'r') as f:
                data = json.load(f)
                for exec_id, entry in data.items():
                    self._index[exec_id] = ExecutionIndex(
                        execution_id=entry['execution_id'],
                        start_sequence=entry['start_sequence'],
                        end_sequence=entry['end_sequence'],
                        event_count=entry['event_count'],
                        first_event_hash=entry['first_event_hash'],
                        last_event_hash=entry['last_event_hash'],
                        last_timestamp=entry['last_timestamp'],
                        source_ids=entry['source_ids']
                    )
        except (json.JSONDecodeError, KeyError):
            # Corrupted index, start fresh
            self._index.clear()
    
    def update_execution(
        self,
        execution_id: str,
        start_sequence: int,
        end_sequence: int,
        event_count: int,
        first_event_hash: str,
        last_event_hash: str,
        last_timestamp: int,
        source_ids: List[str]
    ) -> ExecutionIndex:
        """
        Update execution index entry.
        
        Called after each event append or batch update.
        """
        entry = ExecutionIndex(
            execution_id=execution_id,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            event_count=event_count,
            first_event_hash=first_event_hash,
            last_event_hash=last_event_hash,
            last_timestamp=last_timestamp,
            source_ids=list(set(source_ids))  # Deduplicate
        )
        
        self._index[execution_id] = entry
        self._save_index()
        return entry
    
    def get_execution(self, execution_id: str) -> Optional[ExecutionIndex]:
        """Get index entry for execution (O(1) lookup)."""
        return self._index.get(execution_id)
    
    def get_all_executions(self) -> List[ExecutionIndex]:
        """Get all indexed executions."""
        return list(self._index.values())
    
    def has_execution(self, execution_id: str) -> bool:
        """Check if execution is indexed."""
        return execution_id in self._index
    
    def _save_index(self) -> None:
        """Persist index to file."""
        data = {
            exec_id: asdict(entry)
            for exec_id, entry in self._index.items()
        }
        
        with open(self.index_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def rebuild_from_events(self, get_execution_events_fn) -> None:
        """
        Rebuild index from all events.
        
        Takes a function that accepts execution_id and returns sorted events.
        """
        execution_ids = set()
        
        # This is a bit of a hack - we'd normally scan the journal
        # For now, assume we're called after updating with known execution_id
        # In real usage, would rebuild from append_only_log.get_all_execution_ids()
        pass


@dataclass(frozen=True)
class SnapshotIndex:
    """Index entry for snapshot lookup."""
    
    snapshot_id: str
    execution_id: str
    at_sequence: int
    state_hash: str
    created_at: int


class SnapshotRegistry:
    """
    Registry of deterministic replay snapshots.
    
    Snapshots are acceleration points, not authority.
    Authority remains: append-only event chain.
    """
    
    def __init__(self, registry_path: str = "logs/control_plane/snapshot_registry.json"):
        """Initialize snapshot registry."""
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Snapshots: snapshot_id -> SnapshotIndex
        self._snapshots: Dict[str, SnapshotIndex] = {}
        
        # Execution -> latest snapshot_id
        self._execution_latest: Dict[str, str] = {}
        
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load registry from file."""
        if not self.registry_path.exists():
            return
        
        try:
            with open(self.registry_path, 'r') as f:
                data = json.load(f)
                for snap_id, entry in data.get('snapshots', {}).items():
                    self._snapshots[snap_id] = SnapshotIndex(
                        snapshot_id=entry['snapshot_id'],
                        execution_id=entry['execution_id'],
                        at_sequence=entry['at_sequence'],
                        state_hash=entry['state_hash'],
                        created_at=entry['created_at']
                    )
                self._execution_latest = data.get('execution_latest', {})
        except (json.JSONDecodeError, KeyError):
            self._snapshots.clear()
            self._execution_latest.clear()
    
    def register_snapshot(
        self,
        snapshot_id: str,
        execution_id: str,
        at_sequence: int,
        state_hash: str,
        created_at: int
    ) -> SnapshotIndex:
        """Register new snapshot."""
        snapshot = SnapshotIndex(
            snapshot_id=snapshot_id,
            execution_id=execution_id,
            at_sequence=at_sequence,
            state_hash=state_hash,
            created_at=created_at
        )
        
        self._snapshots[snapshot_id] = snapshot
        self._execution_latest[execution_id] = snapshot_id
        self._save_registry()
        return snapshot
    
    def get_snapshot(self, snapshot_id: str) -> Optional[SnapshotIndex]:
        """Get snapshot by ID."""
        return self._snapshots.get(snapshot_id)
    
    def get_latest_snapshot(self, execution_id: str) -> Optional[SnapshotIndex]:
        """Get latest snapshot for execution."""
        snapshot_id = self._execution_latest.get(execution_id)
        if snapshot_id:
            return self._snapshots.get(snapshot_id)
        return None
    
    def get_snapshots_for_execution(self, execution_id: str) -> List[SnapshotIndex]:
        """Get all snapshots for execution, in sequence order."""
        snapshots = [
            s for s in self._snapshots.values()
            if s.execution_id == execution_id
        ]
        return sorted(snapshots, key=lambda s: s.at_sequence)
    
    def _save_registry(self) -> None:
        """Persist registry to file."""
        data = {
            'snapshots': {
                snap_id: asdict(snapshot)
                for snap_id, snapshot in self._snapshots.items()
            },
            'execution_latest': self._execution_latest
        }
        
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2)
