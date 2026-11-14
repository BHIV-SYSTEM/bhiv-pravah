"""
Regression and Verification Test Suite for PRAVAH Health Status Stability & Hysteresis
Validates:
1. Hysteresis damping against rapid HEALTHY <-> DEGRADED status oscillation.
2. Consecutive degradation threshold prevents single-probe transient spikes from altering status.
3. Sustained failures preserve genuine UNREACHABLE state.
4. Recovery threshold requires consecutive successful checks before restoring HEALTHY.
5. Rolling latency smoothing prevents latency-jitter flapping.
6. Stale data detection flags STALE and never displays stale data as HEALTHY.
7. Raw probe result and stabilized display status are both cleanly exposed.
8. Latency and last_checked timestamps remain visible at all times.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta
import pytest

# Ensure backend directory in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from health_engine import ServiceState, FailureCategory, ServiceHealthTracker


class TestHealthStatusStability:
    """Validates health state stability, hysteresis, and threshold mechanics."""

    def test_transient_latency_spike_does_not_flip_healthy_status(self):
        """A single high-latency probe on a healthy service must be damped by hysteresis."""
        tracker = ServiceHealthTracker(
            poll_interval_sec=10.0,
            sla_latency_ms=500.0,
            degradation_threshold=3,
            recovery_threshold=2,
            unreachable_threshold=2,
        )
        url = "http://localhost:8001"
        tracker.register_service("crm-api", url)

        # Baseline: Healthy probe
        s1 = tracker.record_probe_result("crm-api", url, ok=True, http_status=200, raw_detail="OK", latency_ms=120.0)
        assert s1["status"] == ServiceState.HEALTHY.value
        assert s1["raw_status"] == ServiceState.HEALTHY.value

        # Single transient latency spike (650ms > 500ms SLA)
        s2 = tracker.record_probe_result("crm-api", url, ok=True, http_status=200, raw_detail="OK", latency_ms=650.0)
        # Raw status notes degraded, but stabilized status remains HEALTHY (damped!)
        assert s2["raw_status"] == ServiceState.DEGRADED.value
        assert s2["status"] == ServiceState.HEALTHY.value
        assert s2["consecutive_degraded"] == 1
        assert s2["latency_ms"] == 650.0

        # Normal probe immediately follows (110ms)
        s3 = tracker.record_probe_result("crm-api", url, ok=True, http_status=200, raw_detail="OK", latency_ms=110.0)
        assert s3["raw_status"] == ServiceState.HEALTHY.value
        assert s3["status"] == ServiceState.HEALTHY.value
        assert s3["consecutive_degraded"] == 0

    def test_alternating_probes_prevent_status_flapping(self):
        """Alternating healthy/degraded probes must not oscillate stabilized status."""
        tracker = ServiceHealthTracker(
            poll_interval_sec=10.0,
            sla_latency_ms=500.0,
            degradation_threshold=3,
            recovery_threshold=2,
        )
        url = "https://gurukul-up9j.onrender.com"
        tracker.register_service("gurukul", url)

        # Establish Healthy
        tracker.record_probe_result("gurukul", url, ok=True, http_status=200, raw_detail="OK", latency_ms=250.0)

        # Sequence of jittery alternating probes
        # Probe 1: slow (530ms) -> damped, status stays HEALTHY
        p1 = tracker.record_probe_result("gurukul", url, ok=True, http_status=200, raw_detail="OK", latency_ms=530.0)
        assert p1["status"] == ServiceState.HEALTHY.value
        assert p1["raw_status"] == ServiceState.DEGRADED.value

        # Probe 2: fast (240ms) -> status stays HEALTHY
        p2 = tracker.record_probe_result("gurukul", url, ok=True, http_status=200, raw_detail="OK", latency_ms=240.0)
        assert p2["status"] == ServiceState.HEALTHY.value
        assert p2["raw_status"] == ServiceState.HEALTHY.value

        # Probe 3: slow (550ms) -> damped, status stays HEALTHY
        p3 = tracker.record_probe_result("gurukul", url, ok=True, http_status=200, raw_detail="OK", latency_ms=550.0)
        assert p3["status"] == ServiceState.HEALTHY.value
        assert p3["raw_status"] == ServiceState.DEGRADED.value

        # Probe 4: fast (260ms) -> status stays HEALTHY
        p4 = tracker.record_probe_result("gurukul", url, ok=True, http_status=200, raw_detail="OK", latency_ms=260.0)
        assert p4["status"] == ServiceState.HEALTHY.value
        assert p4["raw_status"] == ServiceState.HEALTHY.value

        # Stabilized status never flipped to DEGRADED across alternating jitter!
        assert tracker.services["gurukul"]["status"] == ServiceState.HEALTHY.value

    def test_sustained_failures_trigger_degradation_and_unreachable(self):
        """Sustained consecutive failures transition to DEGRADED and then UNREACHABLE."""
        tracker = ServiceHealthTracker(
            poll_interval_sec=10.0,
            sla_latency_ms=500.0,
            degradation_threshold=2,
            recovery_threshold=2,
            unreachable_threshold=2,
        )
        url = "http://localhost:8004"
        tracker.register_service("blockchain", url)

        # Establish Healthy
        tracker.record_probe_result("blockchain", url, ok=True, http_status=200, raw_detail="OK", latency_ms=50.0)
        assert tracker.services["blockchain"]["status"] == ServiceState.HEALTHY.value

        # Failure 1 (HTTP 500) -> Damped (threshold is 2)
        f1 = tracker.record_probe_result("blockchain", url, ok=False, http_status=500, raw_detail="Error", latency_ms=60.0)
        assert f1["status"] == ServiceState.HEALTHY.value
        assert f1["consecutive_degraded"] == 1

        # Failure 2 (HTTP 500) -> Sustained! Transitions to DEGRADED
        f2 = tracker.record_probe_result("blockchain", url, ok=False, http_status=500, raw_detail="Error", latency_ms=65.0)
        assert f2["status"] == ServiceState.DEGRADED.value
        assert f2["consecutive_degraded"] == 2

        # Sustained connection refused -> Transitions to UNREACHABLE
        f3 = tracker.record_probe_result("blockchain", url, ok=False, http_status=None, raw_detail="Connection refused", latency_ms=0.0, error_type="connection_refused")
        # 3 consecutive failures + connection refused -> UNREACHABLE
        assert f3["status"] == ServiceState.UNREACHABLE.value
        assert f3["consecutive_failures"] == 3

    def test_recovery_requires_consecutive_successes(self):
        """Recovering from DEGRADED requires multiple consecutive healthy probes."""
        tracker = ServiceHealthTracker(
            poll_interval_sec=10.0,
            sla_latency_ms=500.0,
            degradation_threshold=2,
            recovery_threshold=2,
            unreachable_threshold=2,
        )
        url = "http://localhost:8002"
        tracker.register_service("trade-bot", url)

        # Force DEGRADED state
        tracker.record_probe_result("trade-bot", url, ok=False, http_status=503, raw_detail="Unavailable", latency_ms=40.0)
        tracker.record_probe_result("trade-bot", url, ok=False, http_status=503, raw_detail="Unavailable", latency_ms=40.0)
        assert tracker.services["trade-bot"]["status"] == ServiceState.DEGRADED.value

        # First successful probe (1/2 required) -> remains DEGRADED (recovering)
        r1 = tracker.record_probe_result("trade-bot", url, ok=True, http_status=200, raw_detail="OK", latency_ms=45.0)
        assert r1["status"] == ServiceState.DEGRADED.value
        assert r1["consecutive_successes"] == 1
        assert "Recovering" in r1["failure_reason"]

        # Second successful probe (2/2 required) -> fully recovers to HEALTHY
        r2 = tracker.record_probe_result("trade-bot", url, ok=True, http_status=200, raw_detail="OK", latency_ms=42.0)
        assert r2["status"] == ServiceState.HEALTHY.value
        assert r2["consecutive_successes"] == 2
        assert r2["failure_reason"] is None
        assert r2["consecutive_failures"] == 0

    def test_stale_data_is_never_shown_as_healthy(self):
        """Services with no probe for > 2.5x poll_interval must be marked STALE."""
        tracker = ServiceHealthTracker(poll_interval_sec=10.0)
        url = "http://localhost:8080"
        tracker.register_service("parikshak", url)

        # Establish Healthy
        tracker.record_probe_result("parikshak", url, ok=True, http_status=200, raw_detail="OK", latency_ms=30.0)
        assert tracker.services["parikshak"]["status"] == ServiceState.HEALTHY.value

        # Artificially age the last_checked timestamp to 30 seconds ago (poll_interval is 10s -> threshold is 25s)
        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=35)).isoformat()
        tracker.services["parikshak"]["last_checked"] = stale_time

        # Run staleness audit
        tracker.check_staleness()

        assert tracker.services["parikshak"]["status"] == ServiceState.STALE.value
        assert "stale" in tracker.services["parikshak"]["failure_reason"].lower()
        # Verify unified health also reflects STALE, not HEALTHY
        unified = tracker.get_unified_product_health()
        prod = next(p for p in unified["products"] if p["name"] == "parikshak")
        assert prod["status"] == ServiceState.STALE.value

    def test_raw_probe_and_stabilized_status_separation(self):
        """Verifies both raw probe metrics and stabilized status are exposed simultaneously."""
        tracker = ServiceHealthTracker(
            poll_interval_sec=10.0,
            sla_latency_ms=500.0,
            degradation_threshold=3,
        )
        url = "http://localhost:8000"
        tracker.register_service("main-api", url)

        # Establish Healthy
        tracker.record_probe_result("main-api", url, ok=True, http_status=200, raw_detail="OK", latency_ms=80.0)

        # Single HTTP 500 error
        res = tracker.record_probe_result("main-api", url, ok=False, http_status=500, raw_detail="Internal Server Error", latency_ms=90.0)

        # Stabilized status is damped (remains HEALTHY)
        assert res["status"] == ServiceState.HEALTHY.value
        # Raw status accurately reports the error
        assert res["raw_status"] == ServiceState.DEGRADED.value
        assert res["raw_detail"] == "Internal Server Error"
        assert res["raw_category"] == FailureCategory.HTTP_ERROR.value
        assert res["http_status"] == 500
        assert res["latency_ms"] == 90.0
        assert res["rolling_avg_latency_ms"] is not None
        assert res["last_checked"] is not None
