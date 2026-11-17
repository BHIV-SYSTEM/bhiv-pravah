import os
import sys
import time
import pytest

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from health_engine import ServiceHealthTracker
from telemetry_client import normalize_path, emit_application_telemetry, FastAPITelemetryMiddleware, setup_flask_telemetry

def test_path_normalization_and_privacy():
    """Verify that paths are normalized and sensitive parameters/IDs are not retained."""
    # Test query params stripped
    assert normalize_path("/api/v1/users?token=secret123&admin=true") == "/api/v1/users"

    # Test trailing slash normalization
    assert normalize_path("/api/services/") == "/api/services"

    # Test UUID replacement
    assert normalize_path("/api/v1/orders/123e4567-e89b-12d3-a456-426614174000") == "/api/v1/orders/:uuid"

    # Test integer ID replacement
    assert normalize_path("/api/v1/items/98765/details") == "/api/v1/items/:id/details"

    # Root path
    assert normalize_path("/") == "/"
    assert normalize_path("") == "/"


def test_telemetry_client_sanitization_rules():
    """Verify telemetry emission excludes sensitive headers and fields."""
    event = {
        "service": "test-service",
        "endpoint": normalize_path("/api/secure/data?key=123"),
        "method": "POST",
        "status_code": 200,
        "duration_ms": 45.2,
        "timestamp": time.time(),
        "source": "application"
    }

    assert "authorization" not in event
    assert "token" not in event
    assert "headers" not in event
    assert "body" not in event
    assert event["endpoint"] == "/api/secure/data"


def test_population_isolation_and_no_probe_pollution():
    """
    Verify that background socket probe timeouts (8000ms) do NOT pollute
    application user latency (P50/P95/P99).
    """
    tracker = ServiceHealthTracker()

    # Record fast application requests (e.g., 20ms, 25ms, 30ms, 40ms, 50ms)
    for latency in [20.0, 25.0, 30.0, 40.0, 50.0]:
        tracker.record_application_request(
            service="decision-brain",
            method="GET",
            endpoint="/live-dashboard",
            http_status=200,
            latency_ms=latency,
            source="application"
        )

    # Record slow external probe timeouts (8000ms unreachable socket checks)
    for _ in range(10):
        tracker.probe_traffic.record_request(504)
        tracker.probe_latency.record(8000.0)

    # Check application traffic summary
    traffic = tracker.get_traffic_summary()
    assert traffic["has_application_traffic"] is True
    assert traffic["total_requests"] == 5
    assert traffic["success_2xx"] == 5
    assert traffic["error_rate_pct"] == 0.0

    # Check sources dictionary
    assert traffic["sources"]["application"]["total_requests"] == 5
    assert traffic["sources"]["probe"]["total_requests"] == 10
    assert traffic["sources"]["probe"]["server_error_5xx"] == 10
    assert traffic["sources"]["probe"]["error_rate_pct"] == 100.0

    # Check performance summary isolation
    perf = tracker.get_performance_summary()
    assert perf["has_application_data"] is True

    # Application P95 must reflect application requests (~50ms), NOT 8000ms probe timeouts!
    assert perf["overall_p95_ms"] is not None
    assert perf["overall_p95_ms"] < 100.0
    assert perf["sources"]["application"]["p95_ms"] < 100.0

    # Probe P95 should reflect the probe timeouts (8000ms)
    assert perf["probe_p95_ms"] == 8000.0
    assert perf["sources"]["probe"]["p95_ms"] == 8000.0


def test_application_error_rates_4xx_5xx():
    """Verify application 4xx and 5xx error distributions are accurately tallied."""
    tracker = ServiceHealthTracker()

    # 7 x 200 OK
    for _ in range(7):
        tracker.record_application_request("decision-brain", "GET", "/api/data", 200, 15.0)
    # 2 x 400 Bad Request
    for _ in range(2):
        tracker.record_application_request("decision-brain", "POST", "/api/data", 400, 10.0)
    # 1 x 500 Internal Error
    tracker.record_application_request("decision-brain", "GET", "/api/data", 500, 50.0)

    summary = tracker.get_traffic_summary()

    assert summary["total_requests"] == 10
    assert summary["success_2xx"] == 7
    assert summary["client_error_4xx"] == 2
    assert summary["server_error_5xx"] == 1
    # Error rate = (2 + 1) / 10 = 30.0%
    assert summary["error_rate_pct"] == 30.0


def test_empty_state_graceful_handling():
    """
    Verify that when no application requests have occurred,
    the system reports explicit empty state (None / False) without inventing fake numbers.
    """
    tracker = ServiceHealthTracker()

    traffic = tracker.get_traffic_summary()
    assert traffic["has_application_traffic"] is False
    assert traffic["total_requests"] == 0
    assert traffic["rps_1m"] == 0.0

    perf = tracker.get_performance_summary()
    assert perf["has_application_data"] is False
    assert perf["overall_p50_ms"] is None
    assert perf["overall_p95_ms"] is None
    assert perf["overall_p99_ms"] is None
    assert len(perf["sources"]["application"]["slow_endpoints"]) == 0
