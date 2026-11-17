from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Tuple
import uuid

try:
    from security.lineage_verifier import LineagePersistenceCorruptionError
    from security.signing import PayloadSigner
except ImportError:
    from backend.security.lineage_verifier import LineagePersistenceCorruptionError
    from backend.security.signing import PayloadSigner

logger = logging.getLogger(__name__)

_MONITORED_LINKS_LOCK = threading.RLock()


def get_monitored_links_log_path() -> Path:
    """Return authoritative path for monitored links append-only journal."""
    override = os.getenv("MONITORED_LINKS_LOG_PATH")
    if override:
        return Path(override)
    return Path("logs") / "control_plane" / "monitored_links.jsonl"


def _canonical_json(payload: Dict[str, Any]) -> str:
    """Serialize dictionary canonically for deterministic hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_record(record: Dict[str, Any]) -> str:
    """Generate SHA256 record digest over canonical payload."""
    return hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()


def _get_last_signature(target_path: Path) -> str:
    """Read and verify the signature of the last committed record in target_path, or 'GENESIS'.

    Validates that the existing journal is completely uncorrupted, cryptographically authentic,
    and has continuous chain integrity. Recovers torn EOF fragments if preceded by valid records.
    Fails closed with LineagePersistenceCorruptionError if any corruption or invalid records exist.
    """
    if not target_path.exists() or target_path.stat().st_size == 0:
        return "GENESIS"

    # Validate existing journal integrity before appending
    replay_monitored_links(target_path)

    # Read the signature of the last verified record
    with open(target_path, "rb") as f:
        lines = f.read().splitlines()
        for line_bytes in reversed(lines):
            stripped = line_bytes.decode("utf-8", errors="replace").strip()
            if stripped:
                data = json.loads(stripped)
                sig = data.get("signature")
                if sig:
                    return sig

    raise LineagePersistenceCorruptionError(
        f"Corrupt existing journal in {target_path}: non-empty file contains no valid signed records"
    )


def append_link_ingested(
    link: str,
    name: str,
    caller_id: str,
    ingested_item: Dict[str, Any],
    metadata: Dict[str, Any],
    log_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append an authenticated LINK_INGESTED event to the durable journal."""
    target_path = log_path or get_monitored_links_log_path()

    with _MONITORED_LINKS_LOCK:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        previous_hash = _get_last_signature(target_path)
        initial_size = target_path.stat().st_size if target_path.exists() else 0

        payload: Dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "LINK_INGESTED",
            "link": link,
            "name": name,
            "caller_id": caller_id,
            "ingested_item": ingested_item,
            "metadata": metadata,
            "previous_hash": previous_hash,
        }
        payload["record_hash"] = _hash_record(payload)

        signer = PayloadSigner()
        signed_record = signer.sign_payload(payload)

        line = _canonical_json(signed_record) + "\n"
        try:
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        except Exception as exc:
            if target_path.exists():
                try:
                    if initial_size == 0:
                        target_path.unlink(missing_ok=True)
                    else:
                        with open(target_path, "a", encoding="utf-8") as f_trunc:
                            f_trunc.truncate(initial_size)
                except Exception as trunc_exc:
                    logger.critical(
                        "CRITICAL: Failed to rollback journal %s to size %d: %s",
                        target_path,
                        initial_size,
                        trunc_exc,
                    )
            raise exc

    return signed_record


def append_link_removed(
    link: str,
    caller_id: str,
    log_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append an authenticated LINK_REMOVED event to the durable journal."""
    target_path = log_path or get_monitored_links_log_path()

    with _MONITORED_LINKS_LOCK:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        previous_hash = _get_last_signature(target_path)
        initial_size = target_path.stat().st_size if target_path.exists() else 0

        payload: Dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "LINK_REMOVED",
            "link": link,
            "caller_id": caller_id,
            "previous_hash": previous_hash,
        }
        payload["record_hash"] = _hash_record(payload)

        signer = PayloadSigner()
        signed_record = signer.sign_payload(payload)

        line = _canonical_json(signed_record) + "\n"
        try:
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        except Exception as exc:
            if target_path.exists():
                try:
                    if initial_size == 0:
                        target_path.unlink(missing_ok=True)
                    else:
                        with open(target_path, "a", encoding="utf-8") as f_trunc:
                            f_trunc.truncate(initial_size)
                except Exception as trunc_exc:
                    logger.critical(
                        "CRITICAL: Failed to rollback journal %s to size %d: %s",
                        target_path,
                        initial_size,
                        trunc_exc,
                    )
            raise exc

    return signed_record


def replay_monitored_links(
    log_path: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], deque[Dict[str, Any]]]:
    """Replay journal to reconstruct active monitored links, metadata, and event history.

    Validates cryptographic HMAC signatures, hash chaining, and record integrity.
    Recovers from torn final EOF records by truncating uncommitted tail bytes.
    Fails closed with LineagePersistenceCorruptionError on malformed or corrupted records.
    """
    target_path = log_path or get_monitored_links_log_path()
    if not target_path.exists():
        return [], {}, deque(maxlen=20)

    active_links_map: Dict[str, Dict[str, Any]] = {}
    active_metadata: Dict[str, Dict[str, Any]] = {}
    events: deque[Dict[str, Any]] = deque(maxlen=20)

    signer = PayloadSigner()
    expected_previous_hash = "GENESIS"

    with _MONITORED_LINKS_LOCK:
        with open(target_path, "rb") as f:
            raw_bytes = f.read()

        if not raw_bytes:
            return [], {}, deque(maxlen=20)

        raw_line_chunks = raw_bytes.splitlines(keepends=True)
        total_lines = len(raw_line_chunks)
        valid_byte_offset = 0

        for line_idx, line_chunk in enumerate(raw_line_chunks, start=1):
            line_str = line_chunk.decode("utf-8", errors="replace").strip()
            if not line_str:
                valid_byte_offset += len(line_chunk)
                continue

            is_terminal_line = (line_idx == total_lines) or not any(
                chunk.decode("utf-8", errors="replace").strip()
                for chunk in raw_line_chunks[line_idx:]
            )

            try:
                record = json.loads(line_str)
            except json.JSONDecodeError as exc:
                line_digest = hashlib.sha256(line_chunk).hexdigest()
                sanitized_excerpt = repr(line_str[:48])[1:-1]

                # Torn EOF Recovery (Section 6): applies ONLY if preceding records exist and were valid!
                if is_terminal_line and valid_byte_offset > 0:
                    logger.warning(
                        "CRITICAL: Detected torn trailing record at EOF in %s at line %d (hash=%s); "
                        "recovering by truncating uncommitted tail bytes to offset %d",
                        target_path,
                        line_idx,
                        line_digest,
                        valid_byte_offset,
                    )
                    try:
                        with open(target_path, "a", encoding="utf-8") as f_trunc:
                            f_trunc.truncate(valid_byte_offset)
                    except Exception as trunc_exc:
                        logger.critical(
                            "CRITICAL: Failed to truncate torn tail from %s at line %d (offset %d): %s",
                            target_path,
                            line_idx,
                            valid_byte_offset,
                            trunc_exc,
                        )
                        raise LineagePersistenceCorruptionError(
                            f"Failed to truncate torn trailing record at EOF in {target_path} at line {line_idx}: {trunc_exc}",
                            line_number=line_idx,
                            line_hash=line_digest,
                            excerpt=sanitized_excerpt,
                        ) from trunc_exc
                    break

                # Non-terminal line corruption fails closed
                logger.error(
                    "CRITICAL: Monitored links journal persistence corruption at line %d (hash=%s)",
                    line_idx,
                    line_digest,
                )
                raise LineagePersistenceCorruptionError(
                    f"Corrupted record in {target_path} at line {line_idx}: {exc.msg}",
                    line_number=line_idx,
                    line_hash=line_digest,
                    excerpt=sanitized_excerpt,
                ) from exc

            line_digest = hashlib.sha256(line_chunk).hexdigest()
            sanitized_excerpt = repr(line_str[:48])[1:-1]

            # 1. Structure validation
            if not isinstance(record, dict) or "event_type" not in record or "link" not in record:
                raise LineagePersistenceCorruptionError(
                    f"Corrupted record structure in {target_path} at line {line_idx}: missing required fields",
                    line_number=line_idx,
                    line_hash=line_digest,
                    excerpt=sanitized_excerpt,
                )

            # 2. Record Hash validation
            persisted_hash = record.get("record_hash")
            if not persisted_hash or not isinstance(persisted_hash, str):
                raise LineagePersistenceCorruptionError(
                    f"Corrupted record in {target_path} at line {line_idx}: missing record_hash",
                    line_number=line_idx,
                    line_hash=line_digest,
                    excerpt=sanitized_excerpt,
                )

            # Recompute unkeyed SHA-256 over core payload (excluding signature keys and record_hash)
            core_payload = {
                k: v for k, v in record.items()
                if k not in ("record_hash", "signature", "signature_algorithm")
            }
            expected_record_hash = _hash_record(core_payload)
            if not hmac.compare_digest(persisted_hash, expected_record_hash):
                raise LineagePersistenceCorruptionError(
                    f"Tampered record in {target_path} at line {line_idx}: hash mismatch",
                    line_number=line_idx,
                    line_hash=line_digest,
                    excerpt=sanitized_excerpt,
                )

            # 3. Signature presence & algorithm validation
            persisted_sig = record.get("signature")
            sig_alg = record.get("signature_algorithm")
            if not persisted_sig or not isinstance(persisted_sig, str):
                raise LineagePersistenceCorruptionError(
                    f"Corrupted record in {target_path} at line {line_idx}: missing signature",
                    line_number=line_idx,
                    line_hash=line_digest,
                    excerpt=sanitized_excerpt,
                )
            if sig_alg != "HMAC-SHA256":
                raise LineagePersistenceCorruptionError(
                    f"Corrupted record in {target_path} at line {line_idx}: invalid signature_algorithm '{sig_alg}'",
                    line_number=line_idx,
                    line_hash=line_digest,
                    excerpt=sanitized_excerpt,
                )

            # 4. Sequential Chain (previous_hash) validation
            persisted_prev_hash = record.get("previous_hash")
            if persisted_prev_hash != expected_previous_hash:
                raise LineagePersistenceCorruptionError(
                    f"Chain violation in {target_path} at line {line_idx}: "
                    f"expected previous_hash '{expected_previous_hash}', got '{persisted_prev_hash}'",
                    line_number=line_idx,
                    line_hash=line_digest,
                    excerpt=sanitized_excerpt,
                )

            # 5. Cryptographic Signature verification via PayloadSigner
            if not signer.verify_payload(record):
                raise LineagePersistenceCorruptionError(
                    f"Tampered record in {target_path} at line {line_idx}: invalid signature",
                    line_number=line_idx,
                    line_hash=line_digest,
                    excerpt=sanitized_excerpt,
                )

            # Record is fully verified. Update chain pointer and byte offset.
            expected_previous_hash = persisted_sig
            valid_byte_offset += len(line_chunk)

            event_type = record["event_type"]
            link = record["link"]

            if event_type == "LINK_INGESTED":
                ingested_item = record.get("ingested_item")
                if not ingested_item:
                    ingested_item = {
                        "link": link,
                        "name": record.get("name") or "Service",
                        "added_at": record.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                        "status": "HEALTHY",
                        "response_time_ms": 150,
                        "uptime_percent": 99.5,
                        "errors_24h": 0,
                    }
                active_links_map[link] = ingested_item
                if "metadata" in record and record["metadata"]:
                    active_metadata[link] = record["metadata"]
                events.appendleft({
                    "type": "link_added",
                    "link": link,
                    "timestamp": record.get("timestamp"),
                    "details": f"Recovered {link} from journal",
                })
            elif event_type == "LINK_REMOVED":
                active_links_map.pop(link, None)
                active_metadata.pop(link, None)
                events.appendleft({
                    "type": "link_removed",
                    "link": link,
                    "timestamp": record.get("timestamp"),
                    "details": f"Removed {link} (from journal)",
                })
            else:
                raise LineagePersistenceCorruptionError(
                    f"Unknown event type '{event_type}' in {target_path} at line {line_idx}",
                    line_number=line_idx,
                    line_hash=line_digest,
                    excerpt=sanitized_excerpt,
                )

    active_links = list(active_links_map.values())
    return active_links, active_metadata, events
