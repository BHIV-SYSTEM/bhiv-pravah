from __future__ import annotations

import json
from pathlib import Path

from control_plane.core import execution_lineage as lineage_module
from control_plane.core.execution_lineage import append_lineage_event


def reset_lineage_module(monkeypatch, log_path: Path) -> None:
    monkeypatch.setattr(lineage_module, "get_lineage_log_path", lambda: log_path)
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX", {})
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX_LOADED", False)


def append_valid_lineage(execution_id: str, log_path: Path, monkeypatch, *, states: tuple[str, ...]) -> None:
    reset_lineage_module(monkeypatch, log_path)
    for state in states:
        append_lineage_event(
            execution_id,
            state,
            "hash-a",
            "runtime",
            details={"execution_id": execution_id, "state": state},
        )


def read_jsonl_records(log_path: Path) -> list[dict]:
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl_records(log_path: Path, records: list[dict]) -> None:
    log_path.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")