from __future__ import annotations

from enum import Enum
import hashlib
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from security.lineage_verifier import LineageVerifier, LineagePersistenceCorruptionError
from security.signed_trace import build_signed_trace, trace_hash

logger = logging.getLogger(__name__)


class LineageJournalState(str, Enum):
    UNINITIALIZED = "UNINITIALIZED"
    HEALTHY = "HEALTHY"
    CORRUPTION_DETECTED = "CORRUPTION_DETECTED"
    WRITE_BLOCKED = "WRITE_BLOCKED"


_LINEAGE_LOCK = threading.Lock()
_LINEAGE_INDEX: Dict[str, str] = {}
_LINEAGE_INDEX_LOADED = False
_LINEAGE_STATE: LineageJournalState = LineageJournalState.UNINITIALIZED


def get_lineage_log_path() -> Path:
    return Path("logs") / "control_plane" / "execution_lineage.jsonl"


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_payload(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _ensure_parent_dir() -> None:
    get_lineage_log_path().parent.mkdir(parents=True, exist_ok=True)


def reset_lineage_journal_state() -> None:
    """Reset in-memory journal state caches. Used for testing and post-repair validation."""
    global _LINEAGE_INDEX_LOADED, _LINEAGE_INDEX, _LINEAGE_STATE
    with _LINEAGE_LOCK:
        _LINEAGE_INDEX = {}
        _LINEAGE_INDEX_LOADED = False
        _LINEAGE_STATE = LineageJournalState.UNINITIALIZED


def _read_events() -> List[Dict[str, Any]]:
    global _LINEAGE_STATE
    path = get_lineage_log_path()
    if not path.exists():
        _LINEAGE_STATE = LineageJournalState.HEALTHY
        return []

    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                _LINEAGE_STATE = LineageJournalState.WRITE_BLOCKED
                line_digest = hashlib.sha256(raw_line.encode("utf-8", errors="replace")).hexdigest()
                sanitized_excerpt = repr(raw_line[:48])[1:-1]
                logger.error(
                    "CRITICAL: Lineage journal persistence corruption at line %d (hash=%s)",
                    line_no,
                    line_digest,
                )
                raise LineagePersistenceCorruptionError(
                    f"Corrupted record in {path} at line {line_no}: {exc.msg}",
                    line_number=line_no,
                    line_hash=line_digest,
                    excerpt=sanitized_excerpt,
                ) from exc

    _LINEAGE_STATE = LineageJournalState.HEALTHY
    return rows


def _rebuild_index() -> Dict[str, str]:
    index: Dict[str, str] = {}
    for event in _read_events():
        execution_id = event.get("execution_id")
        event_hash = event.get("trace_hash") or event.get("event_hash")
        if execution_id and event_hash:
            index[execution_id] = event_hash
    return index


def _ensure_index_loaded() -> None:
    global _LINEAGE_INDEX_LOADED, _LINEAGE_INDEX, _LINEAGE_STATE
    if _LINEAGE_STATE == LineageJournalState.WRITE_BLOCKED:
        raise LineagePersistenceCorruptionError(
            "Lineage index unavailable: journal is in WRITE_BLOCKED state due to corruption"
        )
    if _LINEAGE_INDEX_LOADED and _LINEAGE_STATE == LineageJournalState.HEALTHY:
        return

    try:
        _LINEAGE_INDEX = _rebuild_index()
        _LINEAGE_INDEX_LOADED = True
        _LINEAGE_STATE = LineageJournalState.HEALTHY
    except LineagePersistenceCorruptionError:
        _LINEAGE_INDEX = {}
        _LINEAGE_INDEX_LOADED = False
        _LINEAGE_STATE = LineageJournalState.WRITE_BLOCKED
        raise


def _event_payload(
    execution_id: str,
    state: str,
    execution_hash: str,
    source: str,
    previous_hash: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "execution_id": execution_id,
        "state": state,
        "execution_hash": execution_hash,
        "source": source,
        "details": details or {},
    }


def append_lineage_event(
    execution_id: str,
    state: str,
    execution_hash: str,
    source: str,
    *,
    previous_hash: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not execution_id:
        raise ValueError("execution_id is required for lineage events")

    _ensure_index_loaded()
    with _LINEAGE_LOCK:
        if _LINEAGE_STATE != LineageJournalState.HEALTHY:
            raise LineagePersistenceCorruptionError(
                f"Cannot append event for execution '{execution_id}': journal state is {_LINEAGE_STATE.value}"
            )
        prev_hash = previous_hash if previous_hash is not None else _LINEAGE_INDEX.get(execution_id, "")
        timestamp = datetime.now(timezone.utc).timestamp()
        event_id = str(uuid.uuid4())
        event = _event_payload(
            execution_id=execution_id,
            state=state,
            execution_hash=execution_hash,
            source=source,
            previous_hash=prev_hash,
            details=details,
        )
        signed_trace = build_signed_trace(
            trace_id=event_id,
            execution_id=execution_id,
            payload=event,
            parent_hash=prev_hash,
            signer=source,
            timestamp=timestamp,
        )
        event_hash = trace_hash(signed_trace)
        record = {
            "event_id": event_id,
            "trace_id": signed_trace.trace_id,
            "execution_id": execution_id,
            "previous_hash": prev_hash,
            "parent_hash": prev_hash,
            "timestamp": timestamp,
            "state": state,
            "execution_hash": execution_hash,
            "source": source,
            "details": details or {},
            "payload_hash": signed_trace.payload_hash,
            "signer": signed_trace.signer,
            "signature": signed_trace.signature,
            "trace_hash": event_hash,
            "event_hash": event_hash,
        }

        _ensure_parent_dir()
        path = get_lineage_log_path()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":"), default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

        _LINEAGE_INDEX[execution_id] = event_hash
        return record


def replay_execution_lineage(execution_id: str) -> Dict[str, Any]:
    from contracts.execution_contract import TERMINAL_EXECUTION_STATES, validate_state_transition
    # Import semantic replay validator here to avoid circular imports at module import time
    from control_plane.security.semantic_guard_engine import validate_replay_chain

    if not execution_id:
        raise ValueError("execution_id is required for lineage replay")

    events = [event for event in _read_events() if event.get("execution_id") == execution_id]
    if not events:
        return {
            "execution_id": execution_id,
            "events": [],
            "execution_state_history": [],
            "final_state": None,
            "execution_hash": None,
            "valid": False,
            "error": "EXECUTION_NOT_FOUND",
        }

    payloads = [
        {
            "execution_id": event.get("execution_id"),
            "state": event.get("state"),
            "execution_hash": event.get("execution_hash"),
            "source": event.get("source"),
            "details": event.get("details") or {},
        }
        for event in events
    ]

    LineageVerifier.verify_replay_chain(events, payloads)

    # Phase 4: Semantic replay validation - ensure replayed lineage is semantically valid
    # This prevents crafted replay streams from bypassing semantic guards
    validate_replay_chain(execution_id=execution_id, replay_events=events)

    ordered_events: List[Dict[str, Any]] = []
    execution_hash = None
    previous_state: Optional[str] = None

    for event in events:
        payload = dict(event)

        current_state = payload.get("state")
        if previous_state is None:
            if current_state != "CREATED":
                raise ValueError(f"Illegal replay start state for execution_id={execution_id}: {current_state}")
        else:
            validate_state_transition(previous_state, current_state)

        if previous_state in TERMINAL_EXECUTION_STATES:
            raise ValueError(f"Illegal replay continuation after terminal state for execution_id={execution_id}")

        execution_hash = payload.get("execution_hash")
        previous_state = current_state
        ordered_events.append(event)

    return {
        "execution_id": execution_id,
        "events": ordered_events,
        "execution_state_history": [event["state"] for event in ordered_events],
        "final_state": ordered_events[-1]["state"],
        "execution_hash": execution_hash,
        "valid": True,
    }


def verify_execution_lineage(execution_id: str) -> bool:
    replay_execution_lineage(execution_id)
    return True