from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from control_plane.core.execution_lineage import replay_execution_lineage

from .helpers import append_valid_lineage


def test_concurrent_replay_is_deterministic(monkeypatch, tmp_path, phase6_artifact_dir):
    log_path = tmp_path / "execution_lineage.jsonl"
    execution_id = "phase6-concurrent-replay"

    append_valid_lineage(execution_id, log_path, monkeypatch, states=("CREATED", "APPROVED"))

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(replay_execution_lineage, [execution_id] * 6))

    first = results[0]
    assert all(result["execution_state_history"] == first["execution_state_history"] for result in results)
    assert all(result["final_state"] == first["final_state"] for result in results)
    assert all(result["execution_hash"] == first["execution_hash"] for result in results)