"""
Phase 3: Persistence Sovereignty Layer - Public API.

Append-only immutable event sourcing with deterministic replay.
"""

from .append_only_log import (
    AppendOnlyLog,
    ExecutionEvent,
    AppendOnlyRecord,
    OrderingViolation,
    HashChainBreak
)

from .replay_index import (
    ReplayIndex,
    ExecutionIndex,
    SnapshotRegistry,
    SnapshotIndex
)

from .hash_lineage_verifier import (
    HashLineageVerifier,
    VerificationStatus,
    VerificationResult
)

from .monitored_links_journal import (
    get_monitored_links_log_path,
    append_link_ingested,
    append_link_removed,
    replay_monitored_links,
)

__all__ = [
    # Append-only log
    "AppendOnlyLog",
    "ExecutionEvent",
    "AppendOnlyRecord",
    "OrderingViolation",
    "HashChainBreak",
    
    # Replay index
    "ReplayIndex",
    "ExecutionIndex",
    "SnapshotRegistry",
    "SnapshotIndex",
    
    # Hash lineage verifier
    "HashLineageVerifier",
    "VerificationStatus",
    "VerificationResult",

    # Monitored links journal
    "get_monitored_links_log_path",
    "append_link_ingested",
    "append_link_removed",
    "replay_monitored_links",
]
