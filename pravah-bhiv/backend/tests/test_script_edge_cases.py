"""Focused tests for edge cases in smoke_runtime_attestation and run_full_system_flow."""

import pytest
from typing import Any, Dict

from scripts.run_full_system_flow import (
    DemoEventArgs,
    SystemFlowArgs,
    _build_demo_event,
)


def _has_attestation(event: object) -> bool:
    """Mirrors the exact defensive check in smoke_runtime_attestation.py."""
    if isinstance(event, dict):
        details = event.get("details")
        if isinstance(details, dict):
            return bool(details.get("runtime_attestation"))
    return False


class TestAttestationSafety:
    def test_none_event(self):
        assert _has_attestation(None) is False

    def test_non_dict_event(self):
        assert _has_attestation("event-string") is False
        assert _has_attestation(12345) is False
        assert _has_attestation([{"details": {}}]) is False

    def test_missing_details(self):
        assert _has_attestation({"event_id": "ev-1"}) is False

    def test_none_details(self):
        assert _has_attestation({"event_id": "ev-1", "details": None}) is False

    def test_non_dict_details(self):
        assert _has_attestation({"event_id": "ev-1", "details": "not-a-dict"}) is False
        assert _has_attestation({"event_id": "ev-1", "details": [1, 2, 3]}) is False

    def test_empty_details(self):
        assert _has_attestation({"event_id": "ev-1", "details": {}}) is False

    def test_valid_runtime_attestation(self):
        event = {
            "event_id": "ev-1",
            "details": {
                "runtime_attestation": {
                    "runtime_hash": "abc123hash",
                    "runtime_version": "3.12.7",
                }
            },
        }
        assert _has_attestation(event) is True


class DummyArgs:
    def __init__(self, trace_id, app_id, event_type, cpu, mem, err, workers):
        self.trace_id = trace_id
        self.app_id = app_id
        self.event_type = event_type
        self.cpu_percent = cpu
        self.memory_percent = mem
        self.error_rate = err
        self.workers = workers


class TestRunFullSystemFlowTyping:
    def test_system_flow_args_conforms_to_protocol(self):
        args = SystemFlowArgs(
            start_services=False,
            services=["redis"],
            env="dev",
            trace_id="trace-test-1",
            app_id="app-test-1",
            event_type="alert",
            cpu_percent=42.5,
            memory_percent=78.2,
            error_rate=0.01,
            workers=4,
            post_run_wait=0.5,
        )
        assert isinstance(args, SystemFlowArgs)
        payload = _build_demo_event(args)
        assert payload["trace_id"] == "trace-test-1"
        assert payload["app_id"] == "app-test-1"
        assert payload["event_type"] == "alert"
        assert payload["cpu_percent"] == 42.5
        assert payload["memory_percent"] == 78.2
        assert payload["error_rate"] == 0.01
        assert payload["workers"] == 4

    def test_custom_dummy_args_protocol_compliance(self):
        dummy = DummyArgs("tr-99", "app-99", "custom", 10.0, 20.0, 0.05, 2)
        payload = _build_demo_event(dummy)
        assert payload["trace_id"] == "tr-99"
        assert payload["workers"] == 2
