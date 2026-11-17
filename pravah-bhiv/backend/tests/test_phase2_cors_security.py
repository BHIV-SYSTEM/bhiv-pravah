"""
Phase 2.4.1: Control-Plane CORS Security Hardening Regression Test Suite.

Validates the real FastAPI application and Starlette CORSMiddleware boundary:
- Strict explicit approved origins allowlisting
- Rejection of unapproved Vercel subtenants
- Rejection of unapproved localhost ports
- Rejection of arbitrary external and null origins
- Preflight OPTIONS validation on approved vs unapproved origins
- Non-advertisement of credentials (allow_credentials=False)
- Safe, fail-closed environment override parsing without wildcard leakage
"""

from __future__ import annotations

import os
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from control_plane.backend.app.main import (
    app,
    _parse_cors_origins,
    _cors_origin_regex,
    get_cors_middleware_config,
    DEFAULT_APPROVED_CORS_ORIGINS,
)


@pytest.fixture
def client():
    """Real FastAPI TestClient exercising production app and middleware."""
    return TestClient(app)


# ============================================================================
# 1. APPROVED ORIGIN TESTS (CORS-01 through CORS-03)
# ============================================================================

def test_cors_01_approved_localhost_4500_accepted(client):
    """CORS-01: Approved frontend dev port (localhost:4500) receives Access-Control-Allow-Origin."""
    origin = "http://localhost:4500"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_02_approved_localhost_3000_accepted(client):
    """CORS-02: Approved frontend dev port (localhost:3000) receives Access-Control-Allow-Origin."""
    origin = "http://localhost:3000"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_03_approved_localhost_8000_accepted(client):
    """CORS-03: Approved backend self port (localhost:8000) receives Access-Control-Allow-Origin."""
    origin = "http://localhost:8000"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


# ============================================================================
# 2. UNAPPROVED ORIGIN REJECTION TESTS (CORS-04 through CORS-08)
# ============================================================================

def test_cors_04_deprecated_vercel_frontends_rejected(client):
    """CORS-04: Deprecated Vercel frontends are strictly rejected and do NOT receive Access-Control-Allow-Origin."""
    deprecated_origins = [
        "https://multi-agent-control-plane-frontend.vercel.app",
        "https://multi-agent-control-plane-frontend-dev.vercel.app",
    ]
    for origin in deprecated_origins:
        response = client.get("/health", headers={"Origin": origin})
        assert "access-control-allow-origin" not in response.headers, (
            f"Expected deprecated origin {origin} to be rejected, but got allow header: "
            f"{response.headers.get('access-control-allow-origin')}"
        )


def test_cors_05_unapproved_vercel_tenant_rejected(client):
    """CORS-05: Unapproved arbitrary Vercel tenant does NOT receive Access-Control-Allow-Origin."""
    unapproved_origins = [
        "https://evil-attacker.vercel.app",
        "https://random-tenant.vercel.app",
        "https://phishing-site.vercel.app",
        "https://multi-agent-control-plane-frontend-evil.vercel.app",
    ]
    for origin in unapproved_origins:
        response = client.get("/health", headers={"Origin": origin})
        assert "access-control-allow-origin" not in response.headers, (
            f"Expected {origin} to be rejected by CORS, but got allow header: "
            f"{response.headers.get('access-control-allow-origin')}"
        )


def test_cors_06_unapproved_localhost_ports_rejected(client):
    """CORS-06: Unapproved localhost ports do NOT receive Access-Control-Allow-Origin."""
    unapproved_ports = [
        "http://localhost:9999",
        "http://localhost:8080",
        "http://localhost:5000",
        "http://localhost:1337",
        "http://localhost:8888",
    ]
    for origin in unapproved_ports:
        response = client.get("/health", headers={"Origin": origin})
        assert "access-control-allow-origin" not in response.headers, (
            f"Expected unapproved port {origin} to be rejected, but got: "
            f"{response.headers.get('access-control-allow-origin')}"
        )


def test_cors_07_unrelated_external_https_rejected(client):
    """CORS-07: Arbitrary external HTTPS origins do NOT receive Access-Control-Allow-Origin."""
    external_origins = [
        "https://evil.com",
        "https://attacker.org",
        "https://google.com",
        "http://192.168.1.100:8000",
    ]
    for origin in external_origins:
        response = client.get("/health", headers={"Origin": origin})
        assert "access-control-allow-origin" not in response.headers


def test_cors_08_null_origin_rejected(client):
    """CORS-08: Null origin (e.g. file:// or sandboxed iframe) does NOT receive Access-Control-Allow-Origin."""
    response = client.get("/health", headers={"Origin": "null"})
    assert "access-control-allow-origin" not in response.headers


# ============================================================================
# 3. PREFLIGHT OPTIONS TESTS (CORS-09 and CORS-10)
# ============================================================================

def test_cors_09_approved_preflight_succeeds(client):
    """CORS-09: Preflight OPTIONS on approved origin returns 200 with allowed methods and headers."""
    origin = "http://localhost:4500"
    response = client.options(
        "/control-plane/runtime-ingest",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin

    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "POST" in allow_methods or "*" in allow_methods

    allow_headers = response.headers.get("access-control-allow-headers", "")
    assert "content-type" in allow_headers.lower() or "*" in allow_headers


def test_cors_10_unapproved_preflight_rejected(client):
    """CORS-10: Preflight OPTIONS on unapproved Vercel origin does not grant CORS access."""
    origin = "https://malicious.vercel.app"
    response = client.options(
        "/control-plane/runtime-ingest",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert "access-control-allow-origin" not in response.headers


# ============================================================================
# 4. CREDENTIALS POLICY TEST (CORS-11)
# ============================================================================

def test_cors_11_credentials_not_advertised(client):
    """CORS-11: Response to approved origin must NOT advertise Access-Control-Allow-Credentials: true."""
    origin = "http://localhost:4500"
    response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") != "true"
    assert "access-control-allow-credentials" not in response.headers


# ============================================================================
# 5. ENVIRONMENT OVERRIDE & FAIL-CLOSED PARSING (CORS-12)
# ============================================================================

def test_cors_12_environment_override_explicit_origin(monkeypatch):
    """CORS-12: Environment variable BACKEND_CORS_ORIGINS correctly overrides allowed origins."""
    custom_origin = "https://partner-portal.custom-domain.org"
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", f"{custom_origin}, https://another-portal.org")
    monkeypatch.delenv("BACKEND_CORS_ORIGIN_REGEX", raising=False)

    parsed = _parse_cors_origins()
    assert parsed == [custom_origin, "https://another-portal.org"]
    assert _cors_origin_regex() is None

    # Test with a real FastAPI instance configured using get_cors_middleware_config
    test_app = FastAPI()
    test_app.add_middleware(CORSMiddleware, **get_cors_middleware_config())

    @test_app.get("/test-endpoint")
    def test_endpoint():
        return {"ok": True}

    override_client = TestClient(test_app)

    # Approved custom origin succeeds
    resp_custom = override_client.get("/test-endpoint", headers={"Origin": custom_origin})
    assert resp_custom.headers.get("access-control-allow-origin") == custom_origin

    # Unapproved origin is rejected
    resp_evil = override_client.get("/test-endpoint", headers={"Origin": "https://evil.com"})
    assert "access-control-allow-origin" not in resp_evil.headers

    # Previously default origin is no longer trusted when override replaces it
    resp_default = override_client.get("/test-endpoint", headers={"Origin": "http://localhost:4500"})
    assert "access-control-allow-origin" not in resp_default.headers


def test_cors_wildcard_in_env_is_rejected_and_fails_closed(monkeypatch):
    """Accidental or intentional wildcard '*' in BACKEND_CORS_ORIGINS must NOT permit wildcard access."""
    # Test setting wildcard alone
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "*")
    parsed = _parse_cors_origins()
    assert "*" not in parsed
    assert parsed == DEFAULT_APPROVED_CORS_ORIGINS

    # Test setting wildcard mixed with legitimate origins
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "*, https://legit.org, *")
    parsed_mixed = _parse_cors_origins()
    assert "*" not in parsed_mixed
    assert parsed_mixed == ["https://legit.org"]


def test_cors_origin_deduplication(monkeypatch):
    """Explicit origins must be cleanly deduplicated while preserving order."""
    monkeypatch.setenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:4500, http://localhost:4500, https://app.org, https://app.org",
    )
    parsed = _parse_cors_origins()
    assert parsed == ["http://localhost:4500", "https://app.org"]
