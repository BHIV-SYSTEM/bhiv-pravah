from __future__ import annotations

from control_plane.deployment.readiness_validator import ReadinessValidator
from control_plane.deployment.startup_validator import DeploymentPaths


def test_dependency_failures_are_handled(tmp_path, phase6_artifact_dir):
    paths = DeploymentPaths(
        append_only_log_path=tmp_path / "append_only_log.jsonl",
        replay_index_path=tmp_path / "replay_index.json",
        snapshot_directory=tmp_path / "snapshots",
    )
    paths.snapshot_directory.mkdir(parents=True, exist_ok=True)
    paths.append_only_log_path.write_text("{}\n", encoding="utf-8")
    paths.replay_index_path.mkdir(parents=True, exist_ok=True)

    result = ReadinessValidator(paths=paths).validate()

    assert result.ready is False
    assert result.readiness["replay_index_loaded"] is False