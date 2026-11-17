from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def phase6_artifact_dir(tmp_path: Path) -> Path:
    artifact_dir = tmp_path / "phase6"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir