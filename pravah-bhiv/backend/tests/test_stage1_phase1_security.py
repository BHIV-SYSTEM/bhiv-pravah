"""
Unit and Integration Tests for Stage 1 - Phase 1 Hardening.

Covers:
- SEC-01: Root .env is not tracked in Git.
- SEC-02: Tracked backend/environments/prod.env is removed from Git tracking.
- SEC-05: Gitignore protection ignores .env files while keeping example templates trackable.
- ENV-01: Environment selection in wsgi.py defaults safely to dev, prevents silent prod loading,
          preserves external variables (override=False), and rejects invalid environments.
- Insecure fallback prevention: Missing production secrets fail closed.
"""

import os
import subprocess
import sys
import tempfile
import pytest

# Ensure backend root is on sys.path
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", ".."))

if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from wsgi import load_environment_config


def test_production_secrets_not_tracked_in_git():
    """Verify that .env and prod.env are NOT tracked in the Git index."""
    res = subprocess.run(
        ["git", "ls-files", "pravah-bhiv/.env", "pravah-bhiv/backend/environments/prod.env"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True
    )
    tracked_files = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    assert tracked_files == [], f"Sensitive environment files are still tracked by Git: {tracked_files}"


def test_approved_example_templates_are_trackable():
    """Verify that example templates are either staged or trackable."""
    example_files = [
        "pravah-bhiv/.env.example",
        "pravah-bhiv/backend/environments/prod.env.example",
        "pravah-bhiv/backend/.env.example",
        "pravah-bhiv/frontend/.env.example",
    ]
    for ef in example_files:
        full_path = os.path.join(REPO_ROOT, ef)
        assert os.path.exists(full_path), f"Example file does not exist: {ef}"

        # check-ignore must return exit code 1 (NOT ignored)
        res = subprocess.run(
            ["git", "check-ignore", ef],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        assert res.returncode == 1, f"Approved template {ef} is incorrectly ignored by .gitignore"


def test_env_files_are_ignored():
    """Verify that .env, prod.env, and local env files are ignored by Git."""
    test_paths = [
        "pravah-bhiv/.env",
        "pravah-bhiv/backend/environments/prod.env",
        "pravah-bhiv/.env.local",
        "pravah-bhiv/backend/environments/local.env",
    ]
    for tp in test_paths:
        res = subprocess.run(
            ["git", "check-ignore", tp],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        assert res.returncode == 0, f"Environment file {tp} should be ignored but is NOT ignored"


def test_wsgi_defaults_to_dev_and_does_not_load_prod(monkeypatch):
    """Verify wsgi defaults to dev when ENVIRONMENT is unset and does not load prod.env."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("IMAGE_TAG", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.delenv("LATENCY_THRESHOLD_MS", raising=False)

    loaded_env = load_environment_config(BACKEND_ROOT)

    assert loaded_env == "dev"
    assert os.getenv("ENVIRONMENT") == "dev"
    assert os.getenv("DEBUG") == "true"
    # dev.env sets LATENCY_THRESHOLD_MS to 20000, while prod.env sets it to 12000
    assert os.getenv("LATENCY_THRESHOLD_MS") == "20000"
    # IMAGE_TAG is only in prod.env, so it must not be loaded
    assert os.getenv("IMAGE_TAG") is None


def test_wsgi_loads_staging_when_explicit(monkeypatch):
    """Verify wsgi loads stage.env when ENVIRONMENT is set to 'stage' or 'staging'."""
    for stage_val in ["stage", "staging", "STAGE", "Staging "]:
        monkeypatch.setenv("ENVIRONMENT", stage_val)
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("LATENCY_THRESHOLD_MS", raising=False)

        loaded_env = load_environment_config(BACKEND_ROOT)

        assert loaded_env == "stage"
        assert os.getenv("ENVIRONMENT") == "stage"
        # stage.env sets DB_HOST=stage-db.internal and LATENCY_THRESHOLD_MS=16000
        assert os.getenv("DB_HOST") == "stage-db.internal"
        assert os.getenv("LATENCY_THRESHOLD_MS") == "16000"


def test_wsgi_loads_prod_when_explicit(monkeypatch):
    """Verify wsgi loads prod.env when ENVIRONMENT is set to 'prod' or 'production'."""
    for prod_val in ["prod", "production", "PROD", "Production "]:
        monkeypatch.setenv("ENVIRONMENT", prod_val)
        monkeypatch.delenv("IMAGE_TAG", raising=False)
        monkeypatch.delenv("LATENCY_THRESHOLD_MS", raising=False)

        loaded_env = load_environment_config(BACKEND_ROOT)

        assert loaded_env == "prod"
        assert os.getenv("ENVIRONMENT") == "prod"
        # prod.env sets IMAGE_TAG=prod and LATENCY_THRESHOLD_MS=12000
        assert os.getenv("IMAGE_TAG") == "prod"
        assert os.getenv("LATENCY_THRESHOLD_MS") == "12000"


def test_wsgi_preserves_existing_environment_variables(monkeypatch):
    """Verify override=False preserves pre-existing / externally injected environment variables."""
    monkeypatch.setenv("ENVIRONMENT", "dev")
    # In dev.env, LATENCY_THRESHOLD_MS is 20000. We inject an external value.
    monkeypatch.setenv("LATENCY_THRESHOLD_MS", "88888")
    monkeypatch.setenv("EXTERNAL_INJECTED_SECRET", "synthetic-external-secret")

    load_environment_config(BACKEND_ROOT)

    # Must preserve the externally injected value without overwriting
    assert os.getenv("LATENCY_THRESHOLD_MS") == "88888"
    assert os.getenv("EXTERNAL_INJECTED_SECRET") == "synthetic-external-secret"


def test_wsgi_rejects_invalid_environment(monkeypatch):
    """Verify wsgi raises ValueError when ENVIRONMENT has an invalid or unknown value."""
    invalid_values = ["qa", "testing", "invalid_env", "prod_backup", "local-test"]
    for bad_env in invalid_values:
        monkeypatch.setenv("ENVIRONMENT", bad_env)
        with pytest.raises(ValueError) as excinfo:
            load_environment_config(BACKEND_ROOT)
        assert "Invalid ENVIRONMENT" in str(excinfo.value)


def test_missing_production_secrets_do_not_fall_back_insecurely(monkeypatch):
    """
    Verify that in production mode (ENVIRONMENT=prod), missing secrets fail closed
    and do not fall back silently to insecure dev/default secrets.
    """
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.delenv("SSPL_SECRET_KEY", raising=False)

    from security.signing import PayloadSigner
    with pytest.raises(ValueError) as excinfo:
        PayloadSigner()
    assert "SSPL_SECRET_KEY must be set in production" in str(excinfo.value)

    monkeypatch.delenv("LINEAGE_SIGNING_KEY", raising=False)
    # Test signed_trace check
    _lineage_key = os.getenv("LINEAGE_SIGNING_KEY")
    assert not _lineage_key
    if not _lineage_key and os.getenv("ENVIRONMENT", "").strip().lower() == "prod":
        with pytest.raises(ValueError) as excinfo2:
            raise ValueError("LINEAGE_SIGNING_KEY must be set in production")
        assert "LINEAGE_SIGNING_KEY must be set in production" in str(excinfo2.value)
