from __future__ import annotations

import hashlib
import hmac
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from security.signed_trace import SECRET_KEY, canonicalize, payload_hash as compute_payload_hash, trace_hash
MAX_CLOCK_SKEW_SECONDS = 300


class ReplayIntegrityError(Exception):
    pass


class UnsignedReplayEventError(ReplayIntegrityError):
    pass


class PayloadHashMismatchError(ReplayIntegrityError):
    pass


class LineageBreakError(ReplayIntegrityError):
    pass


class SequenceViolationError(ReplayIntegrityError):
    pass


class DuplicateReplayError(ReplayIntegrityError):
    pass


class TimestampSanityError(ReplayIntegrityError):
    pass


class LineagePersistenceCorruptionError(ReplayIntegrityError):
    """Raised when persistence storage contains malformed, unparseable, or truncated records."""

    def __init__(
        self,
        message: str,
        line_number: Optional[int] = None,
        line_hash: Optional[str] = None,
        excerpt: Optional[str] = None,
    ):
        super().__init__(message)
        self.line_number = line_number
        self.line_hash = line_hash
        if excerpt is not None:
            clean = repr(str(excerpt)[:48])[1:-1]
            self.excerpt = clean
        else:
            self.excerpt = None


def _event_dict(event: Mapping[str, Any] | Any) -> Dict[str, Any]:
    if is_dataclass(event):
        return asdict(event)
    if isinstance(event, Mapping):
        return dict(event)
    raise TypeError("Replay events must be mapping objects or dataclasses")


def _payload_dict(payload: Mapping[str, Any] | Any) -> Dict[str, Any]:
    if is_dataclass(payload):
        return asdict(payload)
    if isinstance(payload, Mapping):
        return dict(payload)
    raise TypeError("Replay payloads must be mapping objects or dataclasses")


def verify_signature(event_material: str, signature: str) -> bool:
    expected = hmac.new(SECRET_KEY, event_material.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _signed_material(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "trace_id": event.get("trace_id"),
        "execution_id": event.get("execution_id"),
        "parent_hash": event.get("parent_hash", event.get("previous_hash", "")),
        "payload_hash": event.get("payload_hash"),
        "timestamp": event.get("timestamp"),
        "signer": event.get("signer"),
    }


def _verify_timestamp_sanity(timestamp_value: Any, previous_timestamp: float | None = None) -> float:
    try:
        numeric_timestamp = float(timestamp_value)
    except Exception as exc:
        raise TimestampSanityError("REPLAY_REJECTED_INVALID_TIMESTAMP") from exc

    now = datetime.now(timezone.utc).timestamp()
    if numeric_timestamp < 0:
        raise TimestampSanityError("REPLAY_REJECTED_INVALID_TIMESTAMP")
    if numeric_timestamp > now + MAX_CLOCK_SKEW_SECONDS:
        raise TimestampSanityError("REPLAY_REJECTED_TIMESTAMP_IN_FUTURE")
    if previous_timestamp is not None and numeric_timestamp < previous_timestamp:
        raise SequenceViolationError("REPLAY_REJECTED_NON_DETERMINISTIC_ORDER")
    return numeric_timestamp


class LineageVerifier:

    @staticmethod
    def verify_event_signature(event: Dict[str, Any]):
        signature = event.get("signature")
        if not signature:
            raise UnsignedReplayEventError("REPLAY_REJECTED_UNSIGNED_EVENT")

        trace_material = _signed_material(event)
        if any(trace_material.get(field) is None for field in ("trace_id", "execution_id", "payload_hash", "timestamp", "signer")):
            raise UnsignedReplayEventError("REPLAY_REJECTED_UNSIGNED_EVENT")

        valid = verify_signature(canonicalize(trace_material), signature)
        if not valid:
            raise UnsignedReplayEventError("REPLAY_REJECTED_INVALID_SIGNATURE")

        stored_trace_hash = event.get("trace_hash") or event.get("event_hash")
        if stored_trace_hash and stored_trace_hash != trace_hash(trace_material):
            raise UnsignedReplayEventError("REPLAY_REJECTED_INVALID_SIGNATURE")

    @classmethod
    def verify_lineage_signatures(cls, journal_events: List[Dict[str, Any]]) -> bool:
        """Verify the cryptographic signatures of a sequence of journal events.
        
        Raises UnsignedReplayEventError/ReplayIntegrityError if any signature is invalid.
        """
        for ev in journal_events:
            sig_event = {
                "trace_id": ev.get("event_id"),
                "execution_id": ev.get("execution_id"),
                "parent_hash": ev.get("previous_hash"),
                "payload_hash": ev.get("event_hash"),
                "timestamp": float(ev.get("timestamp")) if ev.get("timestamp") is not None else None,
                "signer": ev.get("source"),
                "signature": ev.get("details", {}).get("signature") if ev.get("details") else None,
            }
            cls.verify_event_signature(sig_event)
        return True

    @staticmethod
    def verify_payload_integrity(payload: Dict[str, Any], expected_payload_hash: str):
        actual_hash = compute_payload_hash(payload)
        if actual_hash != expected_payload_hash:
            raise PayloadHashMismatchError("REPLAY_REJECTED_PAYLOAD_HASH_MISMATCH")

    @staticmethod
    def verify_lineage_chain(previous_event: Dict[str, Any], current_event: Dict[str, Any]):
        expected_parent = previous_event.get("trace_hash") or previous_event.get("event_hash")
        current_parent = current_event.get("parent_hash", current_event.get("previous_hash"))
        if current_parent != expected_parent:
            raise LineageBreakError("REPLAY_REJECTED_LINEAGE_BREAK")

    @classmethod
    def verify_replay_chain(
        cls,
        replay_events: List[Mapping[str, Any] | Any],
        replay_payloads: List[Mapping[str, Any] | Any],
    ):
        if len(replay_events) != len(replay_payloads):
            raise ReplayIntegrityError("Replay payload mismatch")

        previous_event = None
        previous_timestamp = None
        seen_trace_ids = set()
        seen_trace_hashes = set()
        seen_event_ids = set()

        for index, raw_event in enumerate(replay_events):
            event = _event_dict(raw_event)
            payload = _payload_dict(replay_payloads[index])

            if index == 0 and event.get("state") != "CREATED":
                raise SequenceViolationError("REPLAY_REJECTED_MUST_START_WITH_CREATED")

            cls.verify_event_signature(event)
            cls.verify_payload_integrity(payload, event["payload_hash"])

            event_timestamp = _verify_timestamp_sanity(event.get("timestamp"), previous_timestamp)
            previous_timestamp = event_timestamp

            trace_id = event.get("trace_id")
            trace_digest = event.get("trace_hash") or event.get("event_hash") or trace_hash(_signed_material(event))
            event_id = event.get("event_id") or trace_id

            if trace_id in seen_trace_ids or trace_digest in seen_trace_hashes or event_id in seen_event_ids:
                raise DuplicateReplayError("REPLAY_REJECTED_DUPLICATE_EVENT")

            seen_trace_ids.add(trace_id)
            seen_trace_hashes.add(trace_digest)
            seen_event_ids.add(event_id)

            if previous_event is not None:
                cls.verify_lineage_chain(previous_event, event)

            previous_event = {**event, "trace_hash": trace_digest}

        return True