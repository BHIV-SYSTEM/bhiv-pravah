"""
Control Plane Override & Health Overview Test Suite
Covers:
  - InputValidator: app_name spaces, action freeze→set_freeze, duration seconds→minutes
  - AppOverrideManager: set/clear/get with fuzzy matching
  - MultiAppControlPlane.get_health_overview: observer matching and status derivation
  - _derive_runtime_status priority order
"""

import json
import os
import sys
import tempfile
import pytest

# Ensure backend root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from control_plane.core.input_validator import InputValidator, ValidationError
from control_plane.app_override_manager import AppOverrideManager
from control_plane.multi_app_control_plane import MultiAppControlPlane


# ---------------------------------------------------------------------------
# InputValidator tests
# ---------------------------------------------------------------------------

class TestValidateAppName:
    def test_simple_name(self):
        assert InputValidator.validate_app_name("bhiv-bucket") == "bhiv-bucket"

    def test_name_with_spaces(self):
        """App names like 'BHIV Mitra' must pass validation."""
        assert InputValidator.validate_app_name("BHIV Mitra") == "BHIV Mitra"

    def test_name_with_all_allowed_chars(self):
        assert InputValidator.validate_app_name("Core-Integrator_v2.0 Beta") == "Core-Integrator_v2.0 Beta"

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_app_name("")

    def test_none_name_raises(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_app_name(None)

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_app_name("   ")

    def test_invalid_chars_raises(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_app_name("app<script>")

    def test_max_length_ok(self):
        name = "a" * 100
        assert InputValidator.validate_app_name(name) == name

    def test_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_app_name("a" * 101)


class TestValidateAction:
    def test_set_freeze_passthrough(self):
        assert InputValidator.validate_action("set_freeze") == "set_freeze"

    def test_clear_freeze_passthrough(self):
        assert InputValidator.validate_action("clear_freeze") == "clear_freeze"

    def test_freeze_normalized_to_set_freeze(self):
        """Frontend sends 'freeze'; backend must normalize it to 'set_freeze'."""
        assert InputValidator.validate_action("freeze") == "set_freeze"

    def test_freeze_case_insensitive(self):
        assert InputValidator.validate_action("FREEZE") == "set_freeze"

    def test_invalid_action_raises(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_action("delete")

    def test_empty_action_defaults_to_set_freeze(self):
        # validate_action uses `action or "set_freeze"` default
        assert InputValidator.validate_action("") == "set_freeze"


class TestValidateControlPlaneOverridePayload:
    def test_full_payload_seconds_duration(self):
        """duration in seconds should be converted to minutes."""
        payload = {
            "app_name": "bhiv-bucket",
            "action": "freeze",
            "duration": 300,     # 5 minutes in seconds
            "reason": "Test freeze"
        }
        app_name, action, duration, reason = InputValidator.validate_control_plane_override_payload(payload)
        assert app_name == "bhiv-bucket"
        assert action == "set_freeze"
        assert duration == 5   # 300 // 60
        assert reason == "Test freeze"

    def test_full_payload_minutes_duration(self):
        payload = {
            "app_name": "bhiv-bucket",
            "action": "set_freeze",
            "duration_minutes": 15,
            "reason": "Planned maintenance"
        }
        app_name, action, duration, reason = InputValidator.validate_control_plane_override_payload(payload)
        assert duration == 15

    def test_duration_minutes_takes_precedence_over_duration(self):
        payload = {
            "app_name": "bhiv-bucket",
            "action": "freeze",
            "duration_minutes": 10,
            "duration": 3600,
        }
        _, _, duration, _ = InputValidator.validate_control_plane_override_payload(payload)
        assert duration == 10  # duration_minutes wins

    def test_clear_freeze_no_duration(self):
        payload = {"app_name": "bhiv-bucket", "action": "clear_freeze"}
        app_name, action, duration, reason = InputValidator.validate_control_plane_override_payload(payload)
        assert action == "clear_freeze"
        assert duration == 30   # default

    def test_space_in_app_name(self):
        """BHIV Mitra has a space — must NOT raise."""
        payload = {"app_name": "BHIV Mitra", "action": "freeze", "duration": 60}
        app_name, action, _, _ = InputValidator.validate_control_plane_override_payload(payload)
        assert app_name == "BHIV Mitra"
        assert action == "set_freeze"

    def test_missing_app_name_raises(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_control_plane_override_payload({"action": "freeze"})

    def test_non_dict_raises(self):
        with pytest.raises(ValidationError):
            InputValidator.validate_control_plane_override_payload("not a dict")


# ---------------------------------------------------------------------------
# AppOverrideManager tests
# ---------------------------------------------------------------------------

class TestAppOverrideManager:
    def _make_manager(self):
        """Create a manager with a temp store file for isolation."""
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.write(json.dumps({"apps": {}}).encode())
        tmp.close()
        mgr = AppOverrideManager(store_file=tmp.name)
        return mgr, tmp.name

    def test_store_file_is_absolute(self):
        mgr, path = self._make_manager()
        assert os.path.isabs(mgr.store_file), "store_file must be an absolute path"
        os.unlink(path)

    def test_set_and_get_freeze(self):
        mgr, path = self._make_manager()
        try:
            result = mgr.set_temporary_freeze("bhiv-bucket", 30, "test reason")
            assert result["freeze_enabled"] is True
            assert result["app_name"] == "bhiv-bucket"

            override = mgr.get_app_override("bhiv-bucket")
            assert override is not None
            assert override["freeze_enabled"] is True
            assert override["reason"] == "test reason"
        finally:
            os.unlink(path)

    def test_clear_freeze(self):
        mgr, path = self._make_manager()
        try:
            mgr.set_temporary_freeze("bhiv-bucket", 30, "test")
            mgr.clear_freeze("bhiv-bucket")
            override = mgr.get_app_override("bhiv-bucket")
            assert override is None or override["freeze_enabled"] is False
        finally:
            os.unlink(path)

    def test_fuzzy_match_normalized_key(self):
        """'BHIV-Mitra' and 'bhivmitra' and 'BHIV Mitra' should all match."""
        mgr, path = self._make_manager()
        try:
            mgr.set_temporary_freeze("BHIV Mitra", 30, "space test")
            # Lookup by normalized variant
            override = mgr.get_app_override("bhiv-mitra")
            assert override is not None
            assert override["freeze_enabled"] is True
        finally:
            os.unlink(path)

    def test_get_nonexistent_app_returns_none(self):
        mgr, path = self._make_manager()
        try:
            result = mgr.get_app_override("does-not-exist")
            assert result is None
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# MultiAppControlPlane._derive_runtime_status tests
# ---------------------------------------------------------------------------

class TestDeriveRuntimeStatus:
    def test_observer_healthy_wins(self):
        status = MultiAppControlPlane._derive_runtime_status(
            observer_status="Healthy",
            last_history_row=None,
        )
        assert status == "healthy"

    def test_observer_online_wins(self):
        assert MultiAppControlPlane._derive_runtime_status("online", None) == "healthy"

    def test_observer_running_wins(self):
        assert MultiAppControlPlane._derive_runtime_status("running", None) == "healthy"

    def test_observer_degraded(self):
        assert MultiAppControlPlane._derive_runtime_status("degraded", None) == "degraded"

    def test_observer_overloaded(self):
        assert MultiAppControlPlane._derive_runtime_status("overloaded", None) == "degraded"

    def test_observer_unreachable(self):
        assert MultiAppControlPlane._derive_runtime_status("unreachable", None) == "unreachable"

    def test_observer_offline(self):
        assert MultiAppControlPlane._derive_runtime_status("offline", None) == "unreachable"

    def test_observer_crashed(self):
        assert MultiAppControlPlane._derive_runtime_status("crashed", None) == "unreachable"

    def test_no_observer_probe_healthy(self):
        """When observer has no data, probe status is used."""
        status = MultiAppControlPlane._derive_runtime_status(
            observer_status=None,
            last_history_row=None,
            probe_status="healthy",
        )
        assert status == "healthy"

    def test_no_observer_probe_degraded(self):
        status = MultiAppControlPlane._derive_runtime_status(None, None, probe_status="degraded")
        assert status == "degraded"

    def test_history_success_fallback(self):
        """History execution_success=True → healthy when no observer/probe data."""
        row = {"execution_success": True, "timestamp": "2025-01-01T00:00:00Z"}
        status = MultiAppControlPlane._derive_runtime_status(None, row)
        assert status == "healthy"

    def test_history_failure_no_effect(self):
        row = {"execution_success": False, "timestamp": "2025-01-01T00:00:00Z"}
        status = MultiAppControlPlane._derive_runtime_status(None, row)
        assert status == "unknown"

    def test_no_data_returns_unknown(self):
        """No observer, no probe, no history → STATUS NOT REPORTED (unknown)."""
        assert MultiAppControlPlane._derive_runtime_status(None, None) == "unknown"

    def test_observer_takes_priority_over_probe(self):
        """Observer data must win over probe result."""
        status = MultiAppControlPlane._derive_runtime_status(
            observer_status="healthy",
            last_history_row=None,
            probe_status="unreachable",  # probe says bad but observer says good
        )
        assert status == "healthy"

    def test_observer_takes_priority_over_history(self):
        row = {"execution_success": True}
        status = MultiAppControlPlane._derive_runtime_status("crashed", row)
        assert status == "unreachable"


# ---------------------------------------------------------------------------
# MultiAppControlPlane._norm tests
# ---------------------------------------------------------------------------

class TestNorm:
    def test_strips_non_alphanumeric(self):
        assert MultiAppControlPlane._norm("BHIV-Mitra") == "bhivmitra"

    def test_lowercase(self):
        assert MultiAppControlPlane._norm("BHIV") == "bhiv"

    def test_empty(self):
        assert MultiAppControlPlane._norm("") == ""

    def test_none(self):
        assert MultiAppControlPlane._norm(None) == ""

    def test_spaces_stripped(self):
        assert MultiAppControlPlane._norm("ai crm setu") == "aicrmsetu"


# ---------------------------------------------------------------------------
# MultiAppControlPlane.get_health_overview integration test (mocked observer)
# ---------------------------------------------------------------------------

class TestGetHealthOverviewMocked:
    """Test get_health_overview with a mocked _fetch_observer_status."""

    def _make_cp(self):
        """Create a MultiAppControlPlane pointing to actual backend registry."""
        cp = MultiAppControlPlane()
        return cp

    def test_known_status_values(self, monkeypatch):
        """With mocked observer, matched apps should report correct status."""
        cp = self._make_cp()
        apps = cp.list_apps()
        if not apps:
            pytest.skip("No apps in registry — skipping integration test")

        # Pick the first app and mock observer to report it healthy
        first_app = apps[0]
        first_name = first_app["app_name"]

        # Mock observer to return first_name as healthy
        monkeypatch.setattr(cp, "_fetch_observer_status", lambda: {first_name: "healthy"})

        overview = cp.get_health_overview()
        matched = next((x for x in overview if x["app_name"] == first_name), None)
        assert matched is not None
        assert matched["status"] == "healthy"
        assert matched["observer_status"] == "healthy"

    def test_unmatched_app_returns_unknown(self, monkeypatch):
        """Apps not in observer data show unknown (STATUS NOT REPORTED)."""
        cp = self._make_cp()
        apps = cp.list_apps()
        if not apps:
            pytest.skip("No apps in registry")

        # Observer returns a completely different service
        monkeypatch.setattr(cp, "_fetch_observer_status", lambda: {"totally-unrelated-service": "healthy"})
        # Also mock probe to return None (no env URL)
        monkeypatch.setattr(cp, "_resolve_service_health_url", lambda app, stem: None)

        overview = cp.get_health_overview()
        # All apps should be unknown since observer matches nothing
        statuses = {x["status"] for x in overview}
        assert "healthy" not in statuses, "Should not show healthy when observer has no match"

    def test_degraded_observer_status(self, monkeypatch):
        """Observer degraded → app card shows degraded."""
        cp = self._make_cp()
        apps = cp.list_apps()
        if not apps:
            pytest.skip("No apps in registry")

        first_name = apps[0]["app_name"]
        monkeypatch.setattr(cp, "_fetch_observer_status", lambda: {first_name: "degraded"})

        overview = cp.get_health_overview()
        matched = next((x for x in overview if x["app_name"] == first_name), None)
        assert matched["status"] == "degraded"

    def test_observer_empty_all_unknown(self, monkeypatch):
        """When observer returns {}, all apps should be unknown (unless they have probe URLs)."""
        cp = self._make_cp()
        monkeypatch.setattr(cp, "_fetch_observer_status", lambda: {})
        monkeypatch.setattr(cp, "_resolve_service_health_url", lambda app, stem: None)

        overview = cp.get_health_overview()
        for app in overview:
            # Without observer data or probe or history, everything is unknown
            assert app["status"] in ("unknown", "healthy"), \
                f"{app['app_name']} unexpected status: {app['status']}"

    def test_all_apps_have_required_fields(self, monkeypatch):
        """Every app card must have the required display fields."""
        cp = self._make_cp()
        monkeypatch.setattr(cp, "_fetch_observer_status", lambda: {})

        overview = cp.get_health_overview()
        required_keys = {"app_name", "app_id", "status"}
        for app in overview:
            missing = required_keys - set(app.keys())
            assert not missing, f"{app.get('app_name')} missing fields: {missing}"

    def test_known_aliases_crm(self, monkeypatch):
        """ai-crm-setu ↔ crm-api alias matching."""
        cp = self._make_cp()
        # Ensure ai-crm-setu exists in registry — if not, skip
        apps = cp.list_apps()
        crm_app = next((a for a in apps if "crm" in a["app_name"].lower() or "crm" in a["app_id"].lower()), None)
        if not crm_app:
            pytest.skip("No CRM app in registry")

        # Observer reports under alias "crm-api"
        monkeypatch.setattr(cp, "_fetch_observer_status", lambda: {"crm-api": "healthy"})

        overview = cp.get_health_overview()
        crm_overview = next((x for x in overview if x["app_name"] == crm_app["app_name"]), None)
        assert crm_overview is not None
        # Should match via KNOWN_ALIASES
        assert crm_overview["status"] == "healthy", \
            f"CRM alias not matched: observer_status={crm_overview.get('observer_status')}"
