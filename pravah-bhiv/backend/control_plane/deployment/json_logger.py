"""Structured JSON logging for deployment validation events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class JsonLogRecord:
    event: str
    timestamp: str
    payload: Dict[str, Any]


class StructuredJsonLogger:
    """Append JSONL events to a file."""

    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **payload: Any) -> JsonLogRecord:
        record = JsonLogRecord(event=event, timestamp=utc_timestamp(), payload=dict(payload))
        payload_dict = {
            "event": record.event,
            "timestamp": record.timestamp,
            **record.payload,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload_dict, sort_keys=True, separators=(",", ":"), default=str) + "\n")
        return record

    def read_all(self) -> list[Dict[str, Any]]:
        if not self.log_path.exists():
            return []
        rows: list[Dict[str, Any]] = []
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows