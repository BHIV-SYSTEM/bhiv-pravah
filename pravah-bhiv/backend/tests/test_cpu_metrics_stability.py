"""
Test suite for CPU metrics sampling, debouncing, and dashboard stability.

Covers:
1. psutil sampling debounce: Rapid successive calls do not produce 0% or 100% microsecond artifacts.
2. Consistency: _build_live_dashboard_payload system_health and ml_intelligence report consistent CPU values.
3. System status logic: HEALTHY on normal CPU, DEGRADED on threshold breach (>= 80%).
4. Unavailability handling: When psutil fails, returns None and collection_status='unavailable' (N/A in UI).
5. Repeated readings stability: Verification over multiple rapid calls.
"""

import sys
import os
import time
from unittest.mock import patch, MagicMock
import pytest

# Ensure backend root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from control_plane.backend.app.main import (
    get_debounced_system_metrics,
    _build_live_dashboard_payload,
    _calculate_aggregate_metrics,
    _LAST_SYSTEM_METRICS,
)


class TestCpuMetricsDebounce:
    """Verifies that rapid successive calls to get_debounced_system_metrics are debounced."""

    def test_rapid_calls_do_not_flap(self):
        """Two calls in rapid succession must return consistent, non-flapping values."""
        # Reset cache state
        _LAST_SYSTEM_METRICS["timestamp"] = 0.0
        _LAST_SYSTEM_METRICS["cpu"] = None

        val1_cpu, val1_mem = get_debounced_system_metrics()
        assert val1_cpu is not None
        assert 0.0 <= val1_cpu <= 100.0

        # Immediate second call (< 100ms)
        val2_cpu, val2_mem = get_debounced_system_metrics()
        assert val2_cpu is not None
        # Must NOT jump to 100% or 0% due to microsecond delta artifact
        assert val2_cpu == val1_cpu, f"Expected debounced cache, got {val2_cpu} != {val1_cpu}"

    def test_mocked_cgroup_error_propagates(self):
        """When psutil raises an exception (cgroup error), get_debounced_system_metrics raises."""
        with patch("psutil.cpu_percent", side_effect=Exception("cgroup error")):
            with pytest.raises(Exception, match="cgroup error"):
                get_debounced_system_metrics()

    def test_payload_consistent_between_ml_and_system_health(self):
        """ml_intelligence and system_health within the same payload must be consistent."""
        payload = _build_live_dashboard_payload()
        sh = payload.get("system_health", {})
        ml = payload.get("ml_intelligence", {})

        system_cpu = sh.get("cpu_utilization_pct")
        ml_cpu = ml.get("cpu_utilization_pct")

        if system_cpu is not None and ml_cpu is not None:
            # Both should reflect the same sampled range (within integer rounding difference)
            assert abs(system_cpu - ml_cpu) <= 1.0, (
                f"system_health CPU ({system_cpu}) and ml_intelligence CPU ({ml_cpu}) diverged!"
            )

    def test_system_status_healthy_under_threshold(self):
        """CPU < 80 must report status HEALTHY."""
        with patch("psutil.cpu_percent", return_value=42.0):
            with patch("psutil.virtual_memory", return_value=MagicMock(percent=50.0)):
                payload = _build_live_dashboard_payload()
                assert payload["system_health"]["status"] == "HEALTHY"
                assert payload["system_health"]["cpu_utilization_pct"] == 42

    def test_system_status_degraded_over_threshold(self):
        """CPU >= 80 must report status DEGRADED."""
        with patch("psutil.cpu_percent", return_value=85.0):
            with patch("psutil.virtual_memory", return_value=MagicMock(percent=50.0)):
                payload = _build_live_dashboard_payload()
                assert payload["system_health"]["status"] == "DEGRADED"
                assert payload["system_health"]["cpu_utilization_pct"] == 85

    def test_unavailable_metrics_return_none(self):
        """When psutil fails, cpu_utilization_pct must be None (rendering N/A in UI) and UNKNOWN."""
        with patch("psutil.cpu_percent", side_effect=Exception("metric error")):
            payload = _build_live_dashboard_payload()
            assert payload["system_health"]["cpu_utilization_pct"] is None
            assert payload["system_health"]["status"] == "UNKNOWN"
            assert payload["system_health"]["collection_status"] == "unavailable"

    def test_repeated_readings_stability(self):
        """Run 5 rapid direct calls and verify exact debounce identity."""
        direct_readings = []
        for _ in range(5):
            cpu, _ = get_debounced_system_metrics()
            direct_readings.append(cpu)

        assert len(set(direct_readings)) == 1, (
            f"Direct debounced calls fluctuated within debounce window: {direct_readings}"
        )

        # Also test repeated full payload calls: verify all values are valid percentages
        payload_cpus = []
        for _ in range(5):
            p = _build_live_dashboard_payload()
            cpu = p["system_health"]["cpu_utilization_pct"]
            status = p["system_health"]["status"]
            payload_cpus.append(cpu)
            # Verify status is consistent with CPU
            if cpu < 80:
                assert status == "HEALTHY"
            else:
                assert status == "DEGRADED"

        assert all(c is not None for c in payload_cpus)

    def test_runtime_metrics_unit_conversion_ratio_vs_percentage(self):
        """0-1 float ratio is converted to 0-100, but integer 1 is not converted to 100."""
        from control_plane.backend.app.main import INGESTED_RUNTIME_STATE

        # Test ratio 0.45 -> 45%
        INGESTED_RUNTIME_STATE["svc_ratio"] = {
            "status": "RUNNING",
            "metrics": {"cpu": 0.45, "memory": 0.60, "latency": 80},
        }
        # Test integer 1 -> 1% (not 100%)
        INGESTED_RUNTIME_STATE["svc_one_pct"] = {
            "status": "RUNNING",
            "metrics": {"cpu": 1, "memory": 1, "latency": 50},
        }
        # Test already 0-100 (e.g. 75 -> 75%)
        INGESTED_RUNTIME_STATE["svc_pct"] = {
            "status": "RUNNING",
            "metrics": {"cpu": 75, "memory": 82, "latency": 120},
        }
        # Test missing / None metric
        INGESTED_RUNTIME_STATE["svc_none"] = {
            "status": "RUNNING",
            "metrics": {"cpu": None, "memory": None, "latency": 90},
        }

        try:
            payload = _build_live_dashboard_payload()
            svc_map = {s["name"]: s for s in payload["monitored_services"]}

            assert svc_map["SVC_RATIO"]["cpu_percent"] == 45
            assert svc_map["SVC_RATIO"]["memory_percent"] == 60

            # 1% must remain 1%, NOT 100%
            assert svc_map["SVC_ONE_PCT"]["cpu_percent"] == 1
            assert svc_map["SVC_ONE_PCT"]["memory_percent"] == 1

            assert svc_map["SVC_PCT"]["cpu_percent"] == 75
            assert svc_map["SVC_PCT"]["memory_percent"] == 82

            # None remains None (renders as N/A in UI)
            assert svc_map["SVC_NONE"]["cpu_percent"] is None
            assert svc_map["SVC_NONE"]["memory_percent"] is None
        finally:
            INGESTED_RUNTIME_STATE.clear()

    def test_decision_request_metric_normalization(self):
        """build_decision_request safely normalizes float ratio to 0-100 and clamps."""
        from control_plane.backend.app.main import build_decision_request, RuntimeIngestPayload

        # Ratio payload
        p_ratio = RuntimeIngestPayload(
            service_id="test_srv",
            timestamp="2026-11-13T10:00:00Z",
            status="healthy",
            metrics={"cpu": 0.65, "memory": 0.80},
            issue_detected=False,
            issue_type="normal",
            recommended_action="noop",
        )
        req_ratio = build_decision_request(p_ratio)
        assert req_ratio.cpu == 65
        assert req_ratio.memory == 80

        # Integer 1 payload -> 1%
        p_one = RuntimeIngestPayload(
            service_id="test_srv",
            timestamp="2026-11-13T10:00:00Z",
            status="healthy",
            metrics={"cpu": 1, "memory": 1},
            issue_detected=False,
            issue_type="normal",
            recommended_action="noop",
        )
        req_one = build_decision_request(p_one)
        assert req_one.cpu == 1
        assert req_one.memory == 1
