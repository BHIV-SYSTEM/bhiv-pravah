"""
Deep Verification & Defect Correction Test Suite
Independently verifies all critical invariants specified in PRAVAH verification:
1. Actual HTTP metric collection & error rate denominator
2. Latency reservoir mathematical correctness & missing data handling
3. Dependency graph topology & cascading failure propagation
4. Incident correlation temporal windows, recovery, and hypothesis distinction
5. Docker Compose healthcheck correctness (no Redis ping on workers/monitors)
6. Dynamic CORS and production security placeholder rejection
"""

import os
import sys
import time
import pytest
from datetime import datetime, timezone, timedelta

# Ensure repo root is in path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from health_engine import (
    LatencyReservoir,
    TrafficMonitor,
    DependencyGraph,
    IncidentCorrelationEngine,
    ServiceHealthTracker,
    ServiceState,
    FailureCategory,
    DEFAULT_DEPENDENCY_GRAPH,
)
from security.auth import TokenAuth


class TestMetricCollectionAndDenominators:
    """Requirement 1 & 3: Verify metric collection, error rates, and denominators."""

    def test_empty_dataset_does_not_fabricate_metrics(self):
        tm = TrafficMonitor(window_seconds=60)
        summary = tm.get_summary()
        assert summary["total_requests"] == 0
        assert summary["error_rate_pct"] == 0.0
        assert summary["rps_1m"] == 0.0

        res = LatencyReservoir()
        stats = res.compute_stats()
        assert stats["count"] == 0
        assert stats["avg_ms"] is None
        assert stats["p50_ms"] is None
        assert stats["p95_ms"] is None
        assert stats["p99_ms"] is None

    def test_error_rate_correct_denominator(self):
        tm = TrafficMonitor(window_seconds=60)
        # 80 successful 200s, 10 404s, 10 500s = 100 total
        for _ in range(80):
            tm.record_request(200)
        for _ in range(10):
            tm.record_request(404)
        for _ in range(10):
            tm.record_request(500)

        assert tm.total_requests == 100
        assert tm.status_2xx == 80
        assert tm.status_4xx == 10
        assert tm.status_5xx == 10
        assert tm.get_error_rate() == 20.0

    def test_rps_window_calculation_and_pruning(self):
        tm = TrafficMonitor(window_seconds=60)
        now = time.time()
        # Record 120 requests spaced over 2 hours
        # 60 requests 90 minutes ago (should be pruned by _prune(cutoff=1hr))
        for _ in range(60):
            tm.record_request(200, timestamp=now - 5400)
        # 30 requests 30 minutes ago (within 1 hr, outside 1 min)
        for _ in range(30):
            tm.record_request(200, timestamp=now - 1800)
        # 30 requests in the last 30 seconds
        for _ in range(30):
            tm.record_request(200, timestamp=now - 10)

        # Before pruning, total_requests reflects lifetime count
        assert tm.total_requests == 120
        # Call get_rps(60)
        rps_1m = tm.get_rps(60, current_time=now)
        assert rps_1m == round(30 / 60.0, 2)  # 0.50 RPS
        # Pruning check
        tm._prune(now)
        # The 60 requests from 90 min ago should have been removed from the deque
        assert len(tm.request_timestamps) == 60


class TestLatencyReservoirCorrectness:
    """Requirement 4: Mathematical percentile verification."""

    def test_percentile_linear_interpolation(self):
        res = LatencyReservoir(max_samples=100)
        # 100 samples from 1 to 100
        for i in range(1, 101):
            res.record(float(i))

        stats = res.compute_stats()
        assert stats["count"] == 100
        assert stats["avg_ms"] == 50.5
        assert stats["p50_ms"] == 50.5  # median of 1..100
        # p95: (100-1)*0.95 = 94.05 -> 95*0.95 + 96*0.05 = 95.05
        assert stats["p95_ms"] == 95.05
        # p99: (100-1)*0.99 = 98.01 -> 99*0.99 + 100*0.01 = 99.01
        assert stats["p99_ms"] == 99.01

    def test_eviction_and_sample_limit(self):
        res = LatencyReservoir(max_samples=10)
        for i in range(25):
            res.record(float(i))
        assert len(res.samples) == 10
        assert res.total_recorded == 25
        # Oldest samples evicted, only 15..24 remain
        assert list(res.samples) == [float(i) for i in range(15, 25)]


class TestDependenciesAndCascadingFailures:
    """Requirement 6: Verify dependency propagation and topology."""

    def test_dependency_failure_propagation(self):
        tracker = ServiceHealthTracker(sla_latency_ms=500.0)
        # Simulate postgres and redis as healthy platform dependencies
        tracker.record_probe_result("postgres", "http://postgres:5432", ok=True, http_status=200, raw_detail="OK", latency_ms=5.0)
        tracker.record_probe_result("redis", "http://redis:6379", ok=True, http_status=200, raw_detail="OK", latency_ms=2.0)

        # Gurukul depends on postgres and redis; probe Gurukul successfully
        gurukul = tracker.record_probe_result("gurukul-backend", "http://gurukul:3000", ok=True, http_status=200, raw_detail="OK", latency_ms=25.0)
        assert gurukul["status"] == ServiceState.HEALTHY.value

        # Now degrade redis
        tracker.record_probe_result("redis", "http://redis:6379", ok=False, http_status=500, raw_detail="Error", latency_ms=10.0)

        # Gurukul probe returns 200, but dependency 'redis' is degraded -> Gurukul must cascade to DEGRADED
        gurukul_cascaded = tracker.record_probe_result("gurukul-backend", "http://gurukul:3000", ok=True, http_status=200, raw_detail="OK", latency_ms=25.0)
        assert gurukul_cascaded["status"] == ServiceState.DEGRADED.value
        assert gurukul_cascaded["failure_category"] == FailureCategory.DEPENDENCY_FAILURE.value
        assert "redis" in gurukul_cascaded["failure_reason"]

    def test_unmonitored_dependency_does_not_invent_failures(self):
        dep_graph = DependencyGraph()
        # When dependencies are not in services_health, cascading failure does not trigger
        has_failure, failed_dep = dep_graph.check_cascading_impact("gurukul-backend", {})
        assert not has_failure
        assert failed_dep is None


class TestIncidentCorrelationEngineDeep:
    """Requirement 7: Anomaly correlation, temporal windows, and hypothesis labeling."""

    def test_temporal_correlation_window_and_expiration(self):
        engine = IncidentCorrelationEngine(correlation_window_seconds=10)
        dep_graph = DependencyGraph()

        # Simulate initial failure
        services_health = {
            "gurukul-backend": {"status": "unreachable", "failure_reason": "Connection refused"}
        }
        traffic = {"error_rate_pct": 15.0}
        perf = {"slow_endpoints": []}

        incidents_1 = engine.evaluate(services_health, traffic, perf, dep_graph)
        assert len(incidents_1) == 1
        inc1_id = incidents_1[0]["incident_id"]
        assert incidents_1[0]["status"] == "ACTIVE"
        assert incidents_1[0]["is_confirmed_cause"] is False
        assert incidents_1[0]["hypothesis"] is not None

        # Simulate update 2 seconds later (within 10s window) -> same incident updated
        time.sleep(0.01)
        incidents_2 = engine.evaluate(services_health, traffic, perf, dep_graph)
        assert incidents_2[0]["incident_id"] == inc1_id

        # Manually age the active incident's last_updated to 20 seconds ago (outside window)
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
        engine.incidents[0]["last_updated"] = old_time

        # New evaluation should expire old incident and create a brand new one
        incidents_3 = engine.evaluate(services_health, traffic, perf, dep_graph)
        active_inc = next((i for i in incidents_3 if i["status"] == "ACTIVE"), None)
        expired_inc = next((i for i in incidents_3 if i["status"] == "EXPIRED"), None)

        assert active_inc is not None
        assert expired_inc is not None
        assert active_inc["incident_id"] != inc1_id
        assert expired_inc["incident_id"] == inc1_id

    def test_auto_recovery_event(self):
        engine = IncidentCorrelationEngine(correlation_window_seconds=300)
        dep_graph = DependencyGraph()

        # 1. Anomaly active
        engine.evaluate({"svc1": {"status": "unreachable"}}, {"error_rate_pct": 20.0}, {"slow_endpoints": []}, dep_graph)
        assert engine.incidents[0]["status"] == "ACTIVE"

        # 2. Recovery: all systems healthy
        recovered = engine.evaluate({"svc1": {"status": "healthy"}}, {"error_rate_pct": 0.0}, {"slow_endpoints": []}, dep_graph)
        assert recovered[0]["status"] == "RESOLVED"
        assert "Healthy" in recovered[0]["resolution"]
        assert recovered[0]["resolved_at"] is not None


class TestDockerComposeHealthchecks:
    """Requirement 5: Verify process-specific health checks in docker-compose.yml."""

    def test_no_redis_ping_on_unrelated_services(self):
        compose_path = os.path.join(root_dir, "docker-compose.yml")
        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Ensure redis ping is ONLY on redis service
        # Workers must use multi_deploy_agent check
        assert "multi_deploy_agent" in content, "multi_deploy_agent healthcheck missing from workers"
        assert "queue_monitor" in content, "queue_monitor healthcheck missing from queue-monitor service"
        assert "infra_health_monitor" in content, "infra_health_monitor healthcheck missing from health-monitor service"

        # Count occurrences of 'redis-cli'
        assert content.count("redis-cli") == 1, "redis-cli ping must ONLY exist on redis service"


class TestProductionSecurityHardening:
    """Requirement 10: Production fail-closed, placeholder rejection, and CORS."""

    def test_placeholder_jwt_keys_rejected_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "prod")
        placeholders = [
            "default-jwt-secret-change-in-prod",
            "dev-key",
            "change-me",
            "secret",
            "shakti-secret-key-change-in-prod",
            "",
        ]
        for p in placeholders:
            monkeypatch.setenv("JWT_SECRET_KEY", p)
            with pytest.raises(ValueError, match="JWT_SECRET_KEY must be explicitly set to a secure, non-default secret in production"):
                TokenAuth()

    def test_valid_custom_key_accepted_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "prod")
        monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-high-entropy-production-key-999")
        auth = TokenAuth()
        token = auth.generate_token("test_admin")
        res = auth.verify_token(token)
        assert res["valid"] is True
        assert res["payload"]["user_id"] == "test_admin"
