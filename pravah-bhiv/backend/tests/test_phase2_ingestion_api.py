"""
Phase 2.3: Ingestion API Contract, Authentication, Enrichment, and Persistence Regression Test Suite.

Exercises the real control plane endpoint boundary (POST /ingest-link, POST /remove-link)
and security primitives (TokenAuth JWT validation, authenticated HMAC append-only journal persistence).
"""

from __future__ import annotations

import builtins
from collections import deque
import concurrent.futures
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict
import uuid
import pytest
from fastapi.testclient import TestClient

from control_plane.backend.app.main import (
    app,
    _INGESTED_LINKS,
    _LINK_METADATA,
    _LINK_EVENTS,
    _generate_link_metadata,
)
from control_plane.persistence import monitored_links_journal as journal_module
from control_plane.persistence.monitored_links_journal import (
    append_link_ingested,
    append_link_removed,
    replay_monitored_links,
)
from security.auth import TokenAuth, get_auth
from security.lineage_verifier import LineagePersistenceCorruptionError
from security.signing import PayloadSigner


@pytest.fixture
def test_env(monkeypatch, tmp_path: Path):
    """Setup isolated append-only journal and clean state for each test."""
    journal_path = tmp_path / "monitored_links.jsonl"
    monkeypatch.setattr(journal_module, "get_monitored_links_log_path", lambda: journal_path)

    import control_plane.backend.app.main as main_module
    monkeypatch.setattr(main_module, "_INGESTED_LINKS", [])
    monkeypatch.setattr(main_module, "_LINK_METADATA", {})
    monkeypatch.setattr(main_module, "_LINK_EVENTS", deque(maxlen=20))
    monkeypatch.setattr(main_module, "_IN_FLIGHT_INGESTIONS", set())

    return journal_path


@pytest.fixture
def client():
    """TestClient instance for the FastAPI application."""
    return TestClient(app)


def _auth_headers(user_id: str = "security_operator") -> Dict[str, str]:
    """Generate authentic JWT token headers using the authoritative TokenAuth mechanism."""
    token = get_auth().generate_token(user_id=user_id, expires_in=3600)
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. AUTHENTICATION & AUTHORIZATION TESTS
# ============================================================================

def test_missing_authentication_rejected_401(client, test_env):
    """Missing Authorization header on /ingest-link must yield HTTP 401."""
    resp = client.post("/ingest-link", json={"link": "https://github.com/torvalds/linux"})
    assert resp.status_code == 401
    assert "missing token" in resp.json().get("detail", "").lower()
    assert not test_env.exists()


def test_invalid_authentication_token_rejected_401(client, test_env):
    """Invalid token on /ingest-link must yield HTTP 401."""
    resp = client.post(
        "/ingest-link",
        json={"link": "https://github.com/torvalds/linux"},
        headers={"Authorization": "Bearer invalid.bogus.jwt.token"},
    )
    assert resp.status_code == 401
    assert "authentication failed" in resp.json().get("detail", "").lower()
    assert not test_env.exists()


def test_expired_authentication_token_rejected_401(client, test_env):
    """Expired token on /ingest-link must yield HTTP 401."""
    token = get_auth().generate_token(user_id="expired_user", expires_in=-60)
    resp = client.post(
        "/ingest-link",
        json={"link": "https://github.com/torvalds/linux"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401
    assert "token expired" in resp.json().get("detail", "").lower()


def test_x_api_token_header_accepted(client, test_env):
    """X-API-Token header with valid JWT is accepted equivalently to Bearer token."""
    token = get_auth().generate_token(user_id="api_key_user", expires_in=3600)
    resp = client.post(
        "/ingest-link",
        json={"link": "https://github.com/torvalds/linux"},
        headers={"X-API-Token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_unauthorized_removal_rejected_401(client, test_env):
    """Missing auth on /remove-link must yield HTTP 401."""
    resp = client.post("/remove-link", json={"link": "https://github.com/torvalds/linux"})
    assert resp.status_code == 401


# ============================================================================
# 2. CONTRACT & SCHEMA VALIDATION TESTS
# ============================================================================

def test_valid_authenticated_ingestion(client, test_env):
    """Valid ingestion succeeds with full schema conformity, HMAC signature, and hash chaining."""
    headers = _auth_headers(user_id="admin_user")
    url = "https://github.com/torvalds/linux"
    resp = client.post("/ingest-link", json={"link": url}, headers=headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["success"] is True
    assert "Link ingested" in data["message"]
    assert data["ingested_link"]["link"] == url
    assert data["ingested_link"]["name"] == "linux"
    assert data["ingested_link"]["status"] in ("HEALTHY", "DEGRADED")
    assert "commits" in data["metadata"]
    assert "enrichment_status" in data["metadata"]

    # Verify persistent journal record
    assert test_env.exists()
    lines = [json.loads(l) for l in test_env.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    rec = lines[0]
    assert rec["event_type"] == "LINK_INGESTED"
    assert rec["link"] == url
    assert rec["caller_id"] == "admin_user"
    assert rec["previous_hash"] == "GENESIS"
    assert len(rec["record_hash"]) == 64
    assert len(rec["signature"]) == 64
    assert rec["signature_algorithm"] == "HMAC-SHA256"
    assert uuid.UUID(rec["event_id"])
    assert PayloadSigner().verify_payload(rec) is True


@pytest.mark.parametrize(
    "malformed_url",
    [
        "not-a-valid-url",
        "ftp://downloads.example.org/archive.tar.gz",
        "http://",
        "https://",
        "javascript:alert(1)",
        "https://invalid url with spaces.com",
        "http://localhost:invalidport",
        "http:///foo",
        "http://nosuchdomain",
    ],
)
def test_malformed_url_rejected_422(client, test_env, malformed_url):
    """Malformed and non-HTTP URLs must be rejected with HTTP 422 Unprocessable Entity."""
    headers = _auth_headers()
    resp = client.post("/ingest-link", json={"link": malformed_url}, headers=headers)
    assert resp.status_code == 422


def test_wrong_field_name_rejected_422(client, test_env):
    """Payload with wrong field name ('url' instead of 'link') must be rejected with 422."""
    headers = _auth_headers()
    resp = client.post(
        "/ingest-link",
        json={"url": "https://github.com/torvalds/linux"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_wrong_type_rejected_422(client, test_env):
    """Payload with non-string type for 'link' must be rejected with 422."""
    headers = _auth_headers()
    resp = client.post("/ingest-link", json={"link": 12345}, headers=headers)
    assert resp.status_code == 422


def test_unexpected_fields_rejected_422(client, test_env):
    """Extra unexpected fields must be rejected with 422 (extra='forbid')."""
    headers = _auth_headers()
    resp = client.post(
        "/ingest-link",
        json={"link": "https://github.com/torvalds/linux", "extra_param": "forbidden"},
        headers=headers,
    )
    assert resp.status_code == 422


# ============================================================================
# 3. IDEMPOTENT INGESTION & REMOVAL TESTS (Requirement 7 & Proof 10)
# ============================================================================

def test_duplicate_ingestion_returns_success_without_duplicate_journal_event(client, test_env):
    """Attempting to ingest an already-monitored link returns success=True idempotently without duplicate journal event."""
    headers = _auth_headers()
    url = "https://github.com/torvalds/linux"

    resp1 = client.post("/ingest-link", json={"link": url}, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["success"] is True

    # Second ingestion must return success=True with existing state and no new event
    resp2 = client.post("/ingest-link", json={"link": url}, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["success"] is True
    assert "Link already monitored" in data2["message"]
    assert data2["ingested_link"]["link"] == url

    # Journal must contain exactly one ingestion event
    lines = [json.loads(l) for l in test_env.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    assert lines[0]["link"] == url


def test_authenticated_removal_success(client, test_env):
    """Authenticated removal deactivates link and records durable authenticated LINK_REMOVED event."""
    headers = _auth_headers(user_id="remover_admin")
    url = "https://github.com/torvalds/linux"

    # First ingest
    client.post("/ingest-link", json={"link": url}, headers=headers)

    # Now remove
    resp = client.post("/remove-link", json={"link": url}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert f"Link removed: {url}" in data["message"]

    # Verify journal has INGESTED then REMOVED properly chained
    lines = [json.loads(l) for l in test_env.read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    assert lines[0]["event_type"] == "LINK_INGESTED"
    assert lines[0]["previous_hash"] == "GENESIS"
    assert lines[1]["event_type"] == "LINK_REMOVED"
    assert lines[1]["caller_id"] == "remover_admin"
    assert lines[1]["link"] == url
    assert lines[1]["previous_hash"] == lines[0]["signature"]
    assert PayloadSigner().verify_payload(lines[1]) is True


def test_nonexistent_removal(client, test_env):
    """Removing a link that is not monitored returns success=False cleanly."""
    headers = _auth_headers()
    resp = client.post(
        "/remove-link",
        json={"link": "https://github.com/unknown/nonexistent-repo"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert resp.json()["error"] == "Link not found"


# ============================================================================
# 4. METADATA ERROR BOUNDARY & ENRICHMENT TESTS
# ============================================================================

def test_metadata_enrichment_success_github(client, test_env, monkeypatch):
    """Successful external GitHub API response produces 'enriched' status with real metrics."""
    class MockSuccessResponse:
        status_code = 200

        def json(self):
            return {
                "stargazers_count": 8888,
                "open_issues_count": 42,
                "network_count": 120,
                "forks_count": 120,
                "size": 50000,
            }

    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockSuccessResponse())

    headers = _auth_headers()
    url = "https://github.com/mock-org/mock-repo"
    resp = client.post("/ingest-link", json={"link": url}, headers=headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["success"] is True
    assert data["metadata"]["enrichment_status"] == "enriched"
    assert data["metadata"]["stars"] == 8888
    assert data["metadata"]["pull_requests"] == 42
    assert data["metadata"]["branches"] == 120
    assert data["metadata"]["enrichment_error"] is None


def test_metadata_enrichment_network_failure_produces_fallback(client, test_env, monkeypatch, caplog):
    """Network failure during enrichment sets 'fallback_heuristic' without crashing ingestion."""
    import requests

    def mock_failing_get(*args, **kwargs):
        raise requests.exceptions.ConnectTimeout("Connection timed out to GitHub API")

    monkeypatch.setattr(requests, "get", mock_failing_get)

    headers = _auth_headers()
    url = "https://github.com/failing-org/timeout-repo"

    with caplog.at_level(logging.WARNING):
        resp = client.post("/ingest-link", json={"link": url}, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["metadata"]["enrichment_status"] == "fallback_heuristic"
    assert "ConnectTimeout" in data["metadata"]["enrichment_error"]
    assert any("External enrichment network failure" in record.message for record in caplog.records)


def test_metadata_enrichment_rate_limit_produces_fallback(client, test_env, monkeypatch, caplog):
    """Rate limiting (HTTP 429) during enrichment sets 'fallback_heuristic' and logs warning."""
    class MockRateLimitResponse:
        status_code = 429

    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockRateLimitResponse())

    headers = _auth_headers()
    url = "https://github.com/rate-limited-org/repo"

    with caplog.at_level(logging.WARNING):
        resp = client.post("/ingest-link", json={"link": url}, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["metadata"]["enrichment_status"] == "fallback_heuristic"
    assert "rate limit" in data["metadata"]["enrichment_error"].lower()


def test_unexpected_programming_exception_not_swallowed(monkeypatch):
    """An unexpected internal bug/programming error is NOT silently caught."""
    def broken_link_hash(link):
        raise TypeError("Unexpected type error in hash calculation")

    import control_plane.backend.app.main as main_module
    monkeypatch.setattr(main_module, "_get_link_hash", broken_link_hash)

    with pytest.raises(TypeError, match="Unexpected type error"):
        _generate_link_metadata("https://github.com/foo/bar")


# ============================================================================
# 5. DURABLE PERSISTENCE & STARTUP RECOVERY TESTS
# ============================================================================

def test_persistence_journal_records_deterministic_events(client, test_env):
    """Ingestion and removal append deterministic records with canonical hashes, HMAC signatures, and chaining."""
    headers = _auth_headers(user_id="auditor_user")

    url1 = "https://github.com/org1/repo1"
    url2 = "https://github.com/org2/repo2"

    client.post("/ingest-link", json={"link": url1}, headers=headers)
    client.post("/ingest-link", json={"link": url2}, headers=headers)
    client.post("/remove-link", json={"link": url1}, headers=headers)

    lines = [json.loads(l) for l in test_env.read_text().splitlines() if l.strip()]
    assert len(lines) == 3
    assert lines[0]["event_type"] == "LINK_INGESTED"
    assert lines[0]["link"] == url1
    assert lines[1]["event_type"] == "LINK_INGESTED"
    assert lines[1]["link"] == url2
    assert lines[2]["event_type"] == "LINK_REMOVED"
    assert lines[2]["link"] == url1

    # Verify cryptographic signature, algorithm, uuid, and hash chain continuity
    signer = PayloadSigner()
    for r in lines:
        assert "record_hash" in r
        assert len(r["record_hash"]) == 64
        assert "signature" in r
        assert len(r["signature"]) == 64
        assert r["signature_algorithm"] == "HMAC-SHA256"
        assert uuid.UUID(r["event_id"])
        assert signer.verify_payload(r) is True

    assert lines[0]["previous_hash"] == "GENESIS"
    assert lines[1]["previous_hash"] == lines[0]["signature"]
    assert lines[2]["previous_hash"] == lines[1]["signature"]


def test_startup_recovery_restores_active_monitored_links(test_env):
    """Replaying journal accurately reconstructs active links and skips removed links."""
    # Write events to journal directly:
    # 1. Ingest A
    # 2. Ingest B
    # 3. Remove A
    # 4. Ingest C
    append_link_ingested("https://github.com/a/a", "A", "caller1", {"link": "https://github.com/a/a", "name": "A"}, {"stars": 10}, log_path=test_env)
    append_link_ingested("https://github.com/b/b", "B", "caller1", {"link": "https://github.com/b/b", "name": "B"}, {"stars": 20}, log_path=test_env)
    append_link_removed("https://github.com/a/a", "caller2", log_path=test_env)
    append_link_ingested("https://github.com/c/c", "C", "caller1", {"link": "https://github.com/c/c", "name": "C"}, {"stars": 30}, log_path=test_env)

    # Replay journal
    active_links, metadata_map, events = replay_monitored_links(log_path=test_env)

    active_urls = {item["link"] for item in active_links}
    assert active_urls == {"https://github.com/b/b", "https://github.com/c/c"}
    assert "https://github.com/a/a" not in active_urls
    assert "https://github.com/a/a" not in metadata_map
    assert metadata_map["https://github.com/b/b"]["stars"] == 20
    assert metadata_map["https://github.com/c/c"]["stars"] == 30


# ============================================================================
# 6. TORN EOF RECOVERY & NON-TERMINAL CORRUPTION (Proofs 8 & 9)
# ============================================================================

def test_replay_torn_trailing_record_recovers_gracefully(test_env):
    """Proof 8: Torn final JSON record is recovered safely during replay and invalid tail is removed."""
    append_link_ingested("https://github.com/valid/one", "one", "caller", {}, {}, log_path=test_env)
    append_link_ingested("https://github.com/valid/two", "two", "caller", {}, {}, log_path=test_env)
    valid_size = test_env.stat().st_size
    assert valid_size > 0

    # Append a torn, incomplete trailing JSON fragment without valid syntax or closing newline
    with open(test_env, "ab") as f:
        f.write(b'{"event_id": "torn-eof-record", "link": "https://github.com/torn-link", "event_type": "LINK_')

    torn_size = test_env.stat().st_size
    assert torn_size > valid_size

    # Replay must recover without error and return both valid preceding records
    active_links, _, _ = replay_monitored_links(log_path=test_env)
    assert len(active_links) == 2
    assert {it["link"] for it in active_links} == {"https://github.com/valid/one", "https://github.com/valid/two"}

    # File must be physically truncated to strip uncommitted tail bytes
    assert test_env.stat().st_size == valid_size


def test_replay_non_terminal_malformed_record_fails_closed(test_env):
    """Proof 9: Malformed/corrupted record that is NOT at EOF must FAIL CLOSED and NOT be truncated."""
    append_link_ingested("https://github.com/valid/one", "one", "caller", {}, {}, log_path=test_env)

    # Append corrupted line followed by another line (making the corrupted line non-terminal)
    with open(test_env, "a", encoding="utf-8") as f:
        f.write('{"event_type": "LINK_INGESTED", CORRUPTED_NON_TERMINAL_LINE\n')
        f.write('{"event_type": "LINK_INGESTED", "link": "https://github.com/valid/two"}\n')

    pre_replay_size = test_env.stat().st_size

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert exc_info.value.line_number == 2
    assert "Corrupted record" in str(exc_info.value)
    # File must NOT be truncated around intermediate corruption
    assert test_env.stat().st_size == pre_replay_size


def test_journal_schema_corruption_fails_closed(test_env):
    """Missing mandatory schema fields in journal record raises LineagePersistenceCorruptionError."""
    broken_record = {"timestamp": "2026-09-04T12:00:00Z", "data": "no event type"}
    test_env.write_text(json.dumps(broken_record) + "\n", encoding="utf-8")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert exc_info.value.line_number == 1
    assert "missing required fields" in str(exc_info.value)


# ============================================================================
# 7. CRYPTOGRAPHIC AUTHENTICITY & TAMPER DETECTION (Proofs 1, 2, 3, 4, 5)
# ============================================================================

def test_replay_missing_record_hash_fails_closed(test_env):
    """Persisted record without record_hash raises LineagePersistenceCorruptionError fail-closed."""
    record = {
        "event_type": "LINK_INGESTED",
        "timestamp": "2026-09-04T12:00:00Z",
        "link": "https://github.com/missing-hash/repo",
        "name": "repo",
        "caller_id": "test",
    }
    test_env.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert "missing record_hash" in str(exc_info.value)
    assert exc_info.value.line_number == 1


def test_replay_missing_signature_fails_closed(test_env):
    """Persisted record missing signature raises LineagePersistenceCorruptionError fail-closed."""
    record = {
        "event_id": str(uuid.uuid4()),
        "event_type": "LINK_INGESTED",
        "timestamp": "2026-09-04T12:00:00Z",
        "link": "https://github.com/missing-sig/repo",
        "name": "repo",
        "caller_id": "test",
        "previous_hash": "GENESIS",
    }
    record["record_hash"] = journal_module._hash_record(record)
    test_env.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert "missing signature" in str(exc_info.value).lower()
    assert exc_info.value.line_number == 1


def test_replay_invalid_signature_algorithm_fails_closed(test_env):
    """Persisted record with unsupported signature_algorithm fails closed."""
    append_link_ingested("https://github.com/alg-test/repo", "repo", "test", {}, {}, log_path=test_env)
    raw = test_env.read_text().strip()
    record = json.loads(raw)
    record["signature_algorithm"] = "MD5"
    test_env.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert "invalid signature_algorithm" in str(exc_info.value).lower()
    assert exc_info.value.line_number == 1


def test_replay_forged_payload_recomputed_hash_fails_closed(test_env):
    """Proof 1: Forged payload + recomputed unkeyed record_hash is rejected because authenticated signature is invalid."""
    append_link_ingested("https://github.com/original/repo", "repo", "test", {}, {}, log_path=test_env)
    raw = test_env.read_text().strip()
    record = json.loads(raw)

    # Attacker tampers with payload data
    record["link"] = "https://github.com/attacker/forged-repo"

    # Attacker recomputes unkeyed record_hash to match the tampered payload
    core_payload = {
        k: v for k, v in record.items()
        if k not in ("record_hash", "signature", "signature_algorithm")
    }
    record["record_hash"] = journal_module._hash_record(core_payload)

    # Save tampered record (signature is still from original payload)
    test_env.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert "invalid signature" in str(exc_info.value).lower()
    assert exc_info.value.line_number == 1


def test_replay_signed_payload_modification_rejected(test_env):
    """Proof 2: Signed payload modification is rejected."""
    append_link_ingested("https://github.com/original/repo", "repo", "test", {}, {}, log_path=test_env)
    raw = test_env.read_text().strip()
    record = json.loads(raw)

    # Modify caller_id without altering signature
    record["caller_id"] = "unauthorized_caller"
    test_env.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert exc_info.value.line_number == 1


def test_replay_signature_modification_rejected(test_env):
    """Proof 3: Signature modification is rejected."""
    append_link_ingested("https://github.com/original/repo", "repo", "test", {}, {}, log_path=test_env)
    raw = test_env.read_text().strip()
    record = json.loads(raw)

    # Tamper with HMAC signature
    record["signature"] = "deadbeef" * 8
    test_env.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert "invalid signature" in str(exc_info.value).lower()
    assert exc_info.value.line_number == 1


def test_replay_reordered_records_rejected(test_env):
    """Proof 4: Reordered records are rejected by sequential previous_hash chain validation."""
    append_link_ingested("https://github.com/repo/one", "one", "caller1", {}, {}, log_path=test_env)
    append_link_ingested("https://github.com/repo/two", "two", "caller2", {}, {}, log_path=test_env)

    lines = [l.strip() for l in test_env.read_text().splitlines() if l.strip()]
    assert len(lines) == 2

    # Swap the two records
    test_env.write_text(lines[1] + "\n" + lines[0] + "\n", encoding="utf-8")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert "chain violation" in str(exc_info.value).lower()
    assert exc_info.value.line_number == 1


def test_replay_deleted_intermediate_record_rejected(test_env):
    """Proof 5: Deleted intermediate record is rejected by broken chain pointer."""
    append_link_ingested("https://github.com/repo/one", "one", "caller", {}, {}, log_path=test_env)
    append_link_ingested("https://github.com/repo/two", "two", "caller", {}, {}, log_path=test_env)
    append_link_ingested("https://github.com/repo/three", "three", "caller", {}, {}, log_path=test_env)

    lines = [l.strip() for l in test_env.read_text().splitlines() if l.strip()]
    assert len(lines) == 3

    # Delete intermediate record (line 2)
    test_env.write_text(lines[0] + "\n" + lines[2] + "\n", encoding="utf-8")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert "chain violation" in str(exc_info.value).lower()
    assert exc_info.value.line_number == 2


def test_replay_tampered_metadata_fails_closed(test_env):
    """Persisted record with tampered metadata raises LineagePersistenceCorruptionError fail-closed."""
    append_link_ingested("https://github.com/original/repo", "repo", "test", {}, {"stars": 10}, log_path=test_env)
    raw = test_env.read_text().strip()
    record = json.loads(raw)
    record["metadata"]["stars"] = 999999
    test_env.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    assert "hash mismatch" in str(exc_info.value) or "invalid signature" in str(exc_info.value)


# ============================================================================
# 8. FILESYSTEM FAILURE HANDLING & ROLLBACK (Proofs 6 & 7)
# ============================================================================

def test_persistence_injected_write_failure_rolls_back_file_size(test_env, monkeypatch):
    """Proof 6: Injected failure inside f.write() causes journal length to return to exact pre-write size."""
    # Write initial valid record
    append_link_ingested("https://github.com/existing/repo", "existing", "caller", {}, {}, log_path=test_env)
    initial_size = test_env.stat().st_size
    assert initial_size > 0

    real_open = builtins.open

    class PartialWriteFailingWrapper:
        def __init__(self, real_file):
            self._file = real_file

        def write(self, s):
            # Write 20 partial bytes to dirty the file, then simulate mid-write failure
            self._file.write(s[:20])
            self._file.flush()
            raise OSError("Disk write failed midway through write")

        def __getattr__(self, name):
            return getattr(self._file, name)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return self._file.__exit__(exc_type, exc_val, exc_tb)

    open_calls = 0

    def mock_open(file, *args, **kwargs):
        nonlocal open_calls
        f = real_open(file, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "")
        if Path(file).resolve() == test_env.resolve() and "a" in mode:
            open_calls += 1
            if open_calls == 1:
                return PartialWriteFailingWrapper(f)
        return f

    monkeypatch.setattr(builtins, "open", mock_open)

    # append_link_ingested must catch the failure, rollback file to initial_size, and re-raise
    with pytest.raises(OSError, match="Disk write failed midway"):
        append_link_ingested("https://github.com/failing/write-repo", "fail", "caller", {}, {}, log_path=test_env)

    # Exact pre-write size must be restored
    assert test_env.stat().st_size == initial_size

    # Replay succeeds cleanly
    monkeypatch.setattr(builtins, "open", real_open)
    active_links, _, _ = replay_monitored_links(log_path=test_env)
    assert len(active_links) == 1
    assert active_links[0]["link"] == "https://github.com/existing/repo"


def test_persistence_injected_fsync_failure_rolls_back_file_size(test_env, monkeypatch):
    """Proof 7: Injected fsync failure exercises the real append path and verifies documented post-failure rollback state."""
    # Write initial record
    append_link_ingested("https://github.com/existing/repo", "existing", "caller", {}, {}, log_path=test_env)
    initial_size = test_env.stat().st_size
    assert initial_size > 0

    real_fsync = os.fsync

    def broken_fsync(fd):
        raise OSError("Simulated fsync EIO disk sync failure")

    monkeypatch.setattr(os, "fsync", broken_fsync)

    with pytest.raises(OSError, match="Simulated fsync EIO disk sync failure"):
        append_link_ingested("https://github.com/fsync-fail/repo", "fail", "caller", {}, {}, log_path=test_env)

    # Rollback must restore exact pre-write size
    assert test_env.stat().st_size == initial_size

    # Replay functions without corruption
    monkeypatch.setattr(os, "fsync", real_fsync)
    active_links, _, _ = replay_monitored_links(log_path=test_env)
    assert len(active_links) == 1
    assert active_links[0]["link"] == "https://github.com/existing/repo"


def test_persistence_failure_on_ingest_leaves_memory_unmodified_and_retriable(client, test_env, monkeypatch):
    """If journal append raises OSError via fsync, in-memory state is NOT modified and retry succeeds."""
    headers = _auth_headers()
    url = "https://github.com/failure/repo"

    real_fsync = os.fsync

    def broken_fsync(fd):
        raise OSError("Disk full: fsync persistence write failed")

    monkeypatch.setattr(os, "fsync", broken_fsync)

    import control_plane.backend.app.main as main_module

    # Must fail with the persistence exception
    with pytest.raises(OSError, match="Disk full: fsync persistence write failed"):
        client.post("/ingest-link", json={"link": url}, headers=headers)

    # In-memory state must remain completely unmodified
    assert not any(it["link"] == url for it in main_module._INGESTED_LINKS)
    assert url not in main_module._LINK_METADATA
    assert url not in main_module._IN_FLIGHT_INGESTIONS

    # No journal record should exist (unlinked or 0 bytes)
    assert not test_env.exists() or test_env.stat().st_size == 0

    # Restore fsync and retry: must succeed cleanly!
    monkeypatch.setattr(os, "fsync", real_fsync)
    resp = client.post("/ingest-link", json={"link": url}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert any(it["link"] == url for it in main_module._INGESTED_LINKS)
    assert url in main_module._LINK_METADATA


def test_persistence_failure_on_remove_leaves_memory_unmodified_and_retriable(client, test_env, monkeypatch):
    """If journal append raises OSError on removal via fsync, in-memory link remains active and retry succeeds."""
    headers = _auth_headers()
    url = "https://github.com/failure/remove-repo"

    # First ingest successfully
    resp = client.post("/ingest-link", json={"link": url}, headers=headers)
    assert resp.status_code == 200

    import control_plane.backend.app.main as main_module
    assert any(it["link"] == url for it in main_module._INGESTED_LINKS)

    real_fsync = os.fsync

    def broken_fsync(fd):
        raise OSError("Read-only filesystem: removal persistence failed")

    monkeypatch.setattr(os, "fsync", broken_fsync)

    with pytest.raises(OSError, match="Read-only filesystem: removal persistence failed"):
        client.post("/remove-link", json={"link": url}, headers=headers)

    # In-memory state must STILL contain the link!
    assert any(it["link"] == url for it in main_module._INGESTED_LINKS)
    assert url in main_module._LINK_METADATA

    # Restore fsync and retry: must succeed!
    monkeypatch.setattr(os, "fsync", real_fsync)
    resp2 = client.post("/remove-link", json={"link": url}, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["success"] is True
    assert not any(it["link"] == url for it in main_module._INGESTED_LINKS)


# ============================================================================
# 9. CONCURRENCY SYNCHRONIZATION (Proof 11)
# ============================================================================

def test_concurrent_ingestion_same_url_exactly_one_succeeds(client, test_env):
    """Proof 11: 10 simultaneous concurrent requests for the exact same URL yield exactly 1 success."""
    headers = _auth_headers()
    url = "https://github.com/concurrent/single-repo"

    def fire_ingest():
        return client.post("/ingest-link", json={"link": url}, headers=headers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fire_ingest) for _ in range(10)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r.status_code == 200 and r.json().get("success") is True]
    duplicates = [r for r in results if r.status_code == 200 and r.json().get("success") is False]

    assert len(successes) == 1
    assert len(duplicates) == 9
    for r in duplicates:
        assert r.json().get("error") == "Link already being monitored"

    # Verify in-memory state has exactly 1 entry
    import control_plane.backend.app.main as main_module
    matched = [it for it in main_module._INGESTED_LINKS if it["link"] == url]
    assert len(matched) == 1

    # Verify journal file has exactly 1 LINK_INGESTED event
    lines = [json.loads(l) for l in test_env.read_text().splitlines() if l.strip()]
    ingest_events = [l for l in lines if l.get("link") == url and l.get("event_type") == "LINK_INGESTED"]
    assert len(ingest_events) == 1

    # Verify startup replay reconstructs exactly 1 active entry
    active_links, _, _ = replay_monitored_links(log_path=test_env)
    assert len([it for it in active_links if it["link"] == url]) == 1


def test_concurrent_ingestion_different_urls_all_succeed(client, test_env):
    """Concurrent requests for distinct URLs execute without blocking or data corruption."""
    headers = _auth_headers()
    urls = [f"https://github.com/concurrent/repo-{i}" for i in range(5)]

    def fire_ingest(u):
        return client.post("/ingest-link", json={"link": u}, headers=headers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fire_ingest, u) for u in urls]
        results = [f.result() for f in futures]

    for r in results:
        assert r.status_code == 200
        assert r.json()["success"] is True

    import control_plane.backend.app.main as main_module
    for u in urls:
        assert any(it["link"] == u for it in main_module._INGESTED_LINKS)

    active_links, _, _ = replay_monitored_links(log_path=test_env)
    assert len(active_links) == 5


# ============================================================================
# 10. PHASE 2.3.5.2: JOURNAL CORRUPTION APPEND & TORN-EOF BOUNDARY CLOSURE
# ============================================================================

def test_corrupt_existing_journal_cannot_append_from_genesis(test_env):
    """Test 1: An existing non-empty journal containing only corrupt bytes must NOT be appended from GENESIS."""
    test_env.write_text("corrupted_non_json_garbage_data\n", encoding="utf-8")
    assert test_env.stat().st_size > 0

    with pytest.raises(LineagePersistenceCorruptionError):
        append_link_ingested("https://github.com/new/repo", "repo", "caller", {}, {}, log_path=test_env)

    # Invariant: Must fail closed and not write an event with previous_hash="GENESIS"
    lines = test_env.read_text().splitlines()
    assert len(lines) == 1
    assert "corrupted_non_json_garbage_data" in lines[0]


def test_non_terminal_malformed_journal_cannot_be_appended_to(test_env):
    """Test 2: A journal containing non-terminal malformed data cannot be appended to."""
    append_link_ingested("https://github.com/valid/one", "one", "caller", {}, {}, log_path=test_env)
    with open(test_env, "a", encoding="utf-8") as f:
        f.write('{"event_type": "LINK_INGESTED", CORRUPT_LINE\n')
    append_raw_line = json.dumps({
        "event_id": str(uuid.uuid4()),
        "timestamp": "2026-09-07T12:00:00Z",
        "event_type": "LINK_INGESTED",
        "link": "https://github.com/valid/two",
        "name": "two",
        "caller_id": "caller",
        "previous_hash": "GENESIS",
        "record_hash": "a" * 64,
        "signature": "b" * 64,
        "signature_algorithm": "HMAC-SHA256",
    })
    with open(test_env, "a", encoding="utf-8") as f:
        f.write(append_raw_line + "\n")

    with pytest.raises(LineagePersistenceCorruptionError):
        append_link_ingested("https://github.com/new/three", "three", "caller", {}, {}, log_path=test_env)


def test_invalid_hmac_existing_journal_cannot_be_appended_to(test_env):
    """Test 3: A journal containing a valid-JSON record with invalid HMAC cannot be appended to."""
    append_link_ingested("https://github.com/valid/one", "one", "caller", {}, {}, log_path=test_env)
    raw = test_env.read_text().strip()
    rec = json.loads(raw)

    rec2 = {
        "event_id": str(uuid.uuid4()),
        "timestamp": "2026-09-07T12:00:00Z",
        "event_type": "LINK_INGESTED",
        "link": "https://github.com/invalid-hmac/two",
        "name": "two",
        "caller_id": "caller",
        "previous_hash": rec["signature"],
    }
    rec2["record_hash"] = journal_module._hash_record(rec2)
    rec2["signature"] = "deadbeef" * 8
    rec2["signature_algorithm"] = "HMAC-SHA256"

    with open(test_env, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec2) + "\n")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        append_link_ingested("https://github.com/new/three", "three", "caller", {}, {}, log_path=test_env)

    assert "invalid signature" in str(exc_info.value).lower()


def test_broken_chain_existing_journal_cannot_be_appended_to(test_env):
    """Test 4: A journal containing a broken chain cannot be appended to."""
    append_link_ingested("https://github.com/valid/one", "one", "caller", {}, {}, log_path=test_env)

    signer = PayloadSigner()
    rec2_payload = {
        "event_id": str(uuid.uuid4()),
        "timestamp": "2026-09-07T12:00:00Z",
        "event_type": "LINK_INGESTED",
        "link": "https://github.com/broken-chain/two",
        "name": "two",
        "caller_id": "caller",
        "previous_hash": "WRONG_PREVIOUS_SIGNATURE",
    }
    rec2_payload["record_hash"] = journal_module._hash_record(rec2_payload)
    rec2_signed = signer.sign_payload(rec2_payload)

    with open(test_env, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec2_signed) + "\n")

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        append_link_ingested("https://github.com/new/three", "three", "caller", {}, {}, log_path=test_env)

    assert "chain violation" in str(exc_info.value).lower()


def test_genuine_terminal_incomplete_json_recoverable_and_appends(test_env):
    """Test 5: Genuine terminal incomplete JSON is truncated and subsequent append succeeds cleanly."""
    append_link_ingested("https://github.com/valid/one", "one", "caller", {}, {}, log_path=test_env)
    append_link_ingested("https://github.com/valid/two", "two", "caller", {}, {}, log_path=test_env)

    lines = [json.loads(l) for l in test_env.read_text().splitlines() if l.strip()]
    rec2_sig = lines[1]["signature"]

    # Append a torn/incomplete terminal record at EOF
    with open(test_env, "ab") as f:
        f.write(b'{"event_id": "torn-tail-record", "event_type": "LINK_INGESTED", "link": "https://github.com/torn')

    # Append must detect the torn tail, truncate it back to record 2, and cleanly append record 3!
    rec3 = append_link_ingested("https://github.com/valid/three", "three", "caller", {}, {}, log_path=test_env)
    assert rec3["previous_hash"] == rec2_sig

    # Replay must recover all 3 valid records
    active_links, _, _ = replay_monitored_links(log_path=test_env)
    assert len(active_links) == 3
    assert [it["link"] for it in active_links] == [
        "https://github.com/valid/one",
        "https://github.com/valid/two",
        "https://github.com/valid/three",
    ]


def test_terminal_valid_json_tampering_remains_fail_closed(test_env):
    """Test 6: Terminal valid-JSON record with tampered content fails closed and is NOT truncated."""
    append_link_ingested("https://github.com/valid/one", "one", "caller", {}, {}, log_path=test_env)
    append_link_ingested("https://github.com/valid/two", "two", "caller", {}, {}, log_path=test_env)

    # Tamper with the terminal record's link while preserving valid JSON syntax
    raw_lines = [l.strip() for l in test_env.read_text().splitlines() if l.strip()]
    rec2 = json.loads(raw_lines[1])
    rec2["link"] = "https://github.com/tampered/two"
    test_env.write_text(raw_lines[0] + "\n" + json.dumps(rec2) + "\n", encoding="utf-8")
    pre_replay_size = test_env.stat().st_size

    with pytest.raises(LineagePersistenceCorruptionError):
        replay_monitored_links(log_path=test_env)

    # Must NOT truncate or discard the tampered record
    assert test_env.stat().st_size == pre_replay_size


def test_existing_valid_journal_can_still_append_normally(test_env):
    """Test 7: Normal sequential appends continue to chain and persist cleanly."""
    r1 = append_link_ingested("https://github.com/seq/one", "one", "caller", {}, {}, log_path=test_env)
    r2 = append_link_ingested("https://github.com/seq/two", "two", "caller", {}, {}, log_path=test_env)
    r3 = append_link_removed("https://github.com/seq/one", "caller", log_path=test_env)

    assert r1["previous_hash"] == "GENESIS"
    assert r2["previous_hash"] == r1["signature"]
    assert r3["previous_hash"] == r2["signature"]

    active_links, _, _ = replay_monitored_links(log_path=test_env)
    assert len(active_links) == 1
    assert active_links[0]["link"] == "https://github.com/seq/two"


def test_existing_valid_journal_can_still_replay_normally(test_env):
    """Test 8: Existing valid journal replays active links and metadata accurately."""
    append_link_ingested("https://github.com/replay/one", "one", "caller", {"link": "https://github.com/replay/one", "name": "one"}, {"stars": 42}, log_path=test_env)
    append_link_ingested("https://github.com/replay/two", "two", "caller", {"link": "https://github.com/replay/two", "name": "two"}, {"stars": 99}, log_path=test_env)

    active_links, meta, events = replay_monitored_links(log_path=test_env)
    assert len(active_links) == 2
    assert meta["https://github.com/replay/one"]["stars"] == 42
    assert meta["https://github.com/replay/two"]["stars"] == 99


# ============================================================================
# 11. PHASE 2.3.5.3: TORN-EOF TRUNCATION FAILURE FAIL-CLOSED REGRESSION TESTS
# ============================================================================

class FailingTruncateFileWrapper:
    """Simulates an OS/filesystem-level truncation failure (e.g. EIO, EPERM, EACCES) during ftruncate."""

    def __init__(self, real_file):
        self._real_file = real_file

    def truncate(self, *args, **kwargs):
        raise OSError("Injected filesystem truncation failure: disk I/O error during ftruncate")

    def __enter__(self):
        self._real_file.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._real_file.__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name):
        return getattr(self._real_file, name)


def test_terminal_torn_eof_successful_truncation_removes_tail_and_allows_append(test_env):
    """Phase 2.3.5.3 Test 1: Successful truncation removes torn tail, leaves valid records, and allows subsequent append."""
    append_link_ingested("https://github.com/valid/one", "one", "caller", {}, {}, log_path=test_env)
    append_link_ingested("https://github.com/valid/two", "two", "caller", {}, {}, log_path=test_env)

    clean_bytes = test_env.read_bytes()
    clean_size = test_env.stat().st_size

    # Append torn bytes at terminal EOF
    torn_bytes = b'{"event_id": "torn-tail-record", "event_type": "LINK_INGESTED", "link": "https://github.com/torn'
    with open(test_env, "ab") as f:
        f.write(torn_bytes)

    assert test_env.stat().st_size == clean_size + len(torn_bytes)

    # Replay must recover and truncate
    active_links, _, _ = replay_monitored_links(log_path=test_env)
    assert len(active_links) == 2
    assert [it["link"] for it in active_links] == [
        "https://github.com/valid/one",
        "https://github.com/valid/two",
    ]

    # File on disk must be physically truncated back to clean_size
    assert test_env.stat().st_size == clean_size
    assert test_env.read_bytes() == clean_bytes
    assert b"torn-tail-record" not in test_env.read_bytes()

    # Subsequent append must succeed normally
    rec3 = append_link_ingested("https://github.com/valid/three", "three", "caller", {}, {}, log_path=test_env)
    lines = [json.loads(l) for l in test_env.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3
    assert rec3["previous_hash"] == lines[1]["signature"]


def test_terminal_torn_eof_truncation_failure_fails_closed(monkeypatch, test_env):
    """Phase 2.3.5.3 Test 2: Truncation failure on torn EOF fails closed with LineagePersistenceCorruptionError."""
    append_link_ingested("https://github.com/valid/one", "one", "caller", {}, {}, log_path=test_env)
    append_link_ingested("https://github.com/valid/two", "two", "caller", {}, {}, log_path=test_env)

    torn_bytes = b'{"event_id": "torn-tail-record", "event_type": "LINK_INGESTED", "link": "https://github.com/torn'
    with open(test_env, "ab") as f:
        f.write(torn_bytes)

    pre_replay_bytes = test_env.read_bytes()
    pre_replay_size = test_env.stat().st_size

    # Inject fault at filesystem boundary on truncate
    real_open = builtins.open

    def faulty_open(file, *args, **kwargs):
        mode = args[0] if len(args) > 0 else kwargs.get("mode", "r")
        f = real_open(file, *args, **kwargs)
        if "a" in mode and str(test_env) in str(file):
            return FailingTruncateFileWrapper(f)
        return f

    monkeypatch.setattr(builtins, "open", faulty_open)

    # Replay must fail closed
    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        replay_monitored_links(log_path=test_env)

    err = exc_info.value
    # Original truncation failure must be chained
    assert err.__cause__ is not None
    assert isinstance(err.__cause__, OSError)
    assert "Injected filesystem truncation failure" in str(err.__cause__)

    # Forensics must be captured
    assert "Failed to truncate torn trailing record at EOF" in str(err)
    assert str(test_env) in str(err)
    assert err.line_number == 3
    assert err.line_hash is not None
    assert "torn" in err.excerpt

    # File must NOT be falsely reported as recovered; corrupted bytes remain untouched
    assert test_env.stat().st_size == pre_replay_size
    assert test_env.read_bytes() == pre_replay_bytes


def test_terminal_torn_eof_truncation_failure_through_last_signature_prevents_append(monkeypatch, test_env):
    """Phase 2.3.5.3 Test 3: Truncation failure during _get_last_signature prevents append_link_ingested and append_link_removed."""
    append_link_ingested("https://github.com/valid/one", "one", "caller", {}, {}, log_path=test_env)
    append_link_ingested("https://github.com/valid/two", "two", "caller", {}, {}, log_path=test_env)

    torn_bytes = b'{"event_id": "torn-tail-record", "event_type": "LINK_INGESTED", "link": "https://github.com/torn'
    with open(test_env, "ab") as f:
        f.write(torn_bytes)

    pre_append_bytes = test_env.read_bytes()
    pre_append_size = test_env.stat().st_size

    # Inject fault at filesystem boundary on truncate
    real_open = builtins.open

    def faulty_open(file, *args, **kwargs):
        mode = args[0] if len(args) > 0 else kwargs.get("mode", "r")
        f = real_open(file, *args, **kwargs)
        if "a" in mode and str(test_env) in str(file):
            return FailingTruncateFileWrapper(f)
        return f

    monkeypatch.setattr(builtins, "open", faulty_open)

    # append_link_ingested must fail closed and NOT append after torn bytes
    with pytest.raises(LineagePersistenceCorruptionError) as exc_ingest:
        append_link_ingested("https://github.com/valid/three", "three", "caller", {}, {}, log_path=test_env)

    assert exc_ingest.value.__cause__ is not None
    assert isinstance(exc_ingest.value.__cause__, OSError)
    assert test_env.stat().st_size == pre_append_size
    assert test_env.read_bytes() == pre_append_bytes

    # append_link_removed must also fail closed and NOT append after torn bytes
    with pytest.raises(LineagePersistenceCorruptionError) as exc_remove:
        append_link_removed("https://github.com/valid/one", "caller", log_path=test_env)

    assert exc_remove.value.__cause__ is not None
    assert isinstance(exc_remove.value.__cause__, OSError)
    assert test_env.stat().st_size == pre_append_size
    assert test_env.read_bytes() == pre_append_bytes

