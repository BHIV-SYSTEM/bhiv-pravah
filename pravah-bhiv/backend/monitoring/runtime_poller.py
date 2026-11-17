#!/usr/bin/env python3
"""
Runtime Poller
HTTP-based runtime polling with latency capture and basic error detection.
"""

import os
import sys

# Make backend root importable
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

import csv
import datetime
import time
from typing import Dict, Any, Optional
from urllib.parse import urljoin

import requests

from control_plane.backend.app.app_registry import load_apps
from control_plane.core.env_config import EnvironmentConfig

class RuntimePoller:
    """Poll runtime health endpoints and emit deterministic status signals."""

    def __init__(
        self,
        env: str = "dev",
        timeout_seconds: float = 5.0,
        latency_warn_ms: float = 2000.0,
        unhealthy_statuses: Optional[set[str]] = None,
    ):
        self.env_config = EnvironmentConfig(env)
        self.timeout_seconds = timeout_seconds
        self.latency_warn_ms = latency_warn_ms
        self.unhealthy_statuses = unhealthy_statuses or {"unhealthy", "error", "critical", "down"}
        self.log_file = self.env_config.get_log_path("runtime_poller.csv")
        self.runtime_payload_log_file = self.env_config.get_log_path("runtime_payload_poller.csv")
        self._initialize_log()

    def _initialize_log(self) -> None:
        """Initialize runtime poller log file."""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", newline="", encoding="utf-8") as file_handle:
                writer = csv.writer(file_handle)
                writer.writerow([
                    "timestamp",
                    "service_name",
                    "target_url",
                    "http_status",
                    "healthy",
                    "latency_ms",
                    "error_detected",
                    "error_type",
                    "error_message",
                    "environment",
                ])

        if not os.path.exists(self.runtime_payload_log_file):
            with open(self.runtime_payload_log_file, "w", newline="", encoding="utf-8") as file_handle:
                writer = csv.writer(file_handle)
                writer.writerow([
                    "timestamp",
                    "app",
                    "env",
                    "state",
                    "latency_ms",
                    "errors_last_min",
                    "workers",
                ])

    def poll_once(self, service_name: str, target_url: str) -> Dict[str, Any]:
        """Poll one endpoint and return normalized runtime signal."""
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        start = time.perf_counter()

        http_status: Optional[int] = None
        healthy = False
        error_detected = False
        error_type = "none"
        error_message = ""

        try:
            response = requests.get(target_url, timeout=self.timeout_seconds)
            http_status = response.status_code
            latency_ms = (time.perf_counter() - start) * 1000.0

            if response.status_code != 200:
                error_detected = True
                error_type = "http_error"
                error_message = f"HTTP {response.status_code}"

            # Basic response-body health signal detection
            body_status = None
            try:
                payload = response.json()
                body_status = str(payload.get("status", "")).strip().lower() if isinstance(payload, dict) else None
            except ValueError:
                body_status = None

            if body_status in self.unhealthy_statuses:
                error_detected = True
                error_type = "body_status_unhealthy"
                error_message = f"status={body_status}"

            if latency_ms > self.latency_warn_ms:
                error_detected = True
                if error_type == "none":
                    error_type = "high_latency"
                error_message = (
                    f"{error_message}; latency_ms={latency_ms:.2f}".strip("; ")
                    if error_message else f"latency_ms={latency_ms:.2f}"
                )

            healthy = (response.status_code == 200) and (not error_detected)

        except requests.Timeout:
            latency_ms = (time.perf_counter() - start) * 1000.0
            error_detected = True
            error_type = "timeout"
            error_message = f"Request timed out after {self.timeout_seconds}s"
            healthy = False

        except requests.RequestException as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            error_detected = True
            error_type = "request_exception"
            error_message = str(exc)
            healthy = False

        result = {
            "timestamp": timestamp,
            "service_name": service_name,
            "target_url": target_url,
            "http_status": http_status,
            "healthy": healthy,
            "latency_ms": round(latency_ms, 2),
            "error_detected": error_detected,
            "error_type": error_type,
            "error_message": error_message,
            "environment": self.env_config.get("environment"),
        }

        self._log_result(result)
        return result

    def poll_service(self, service_name: str, base_url: str, health_endpoint: str = "/api/health") -> Dict[str, Any]:
        """Poll service health endpoint from base URL."""
        normalized_base = base_url if base_url.endswith("/") else f"{base_url}/"
        target_url = urljoin(normalized_base, health_endpoint.lstrip("/"))
        return self.poll_once(service_name=service_name, target_url=target_url)

    def build_runtime_payload(self, poll_result: Dict[str, Any], workers: int = 1) -> Dict[str, Any]:
        """Convert poll result to canonical runtime payload contract."""
        state = "running"
        errors_last_min = 0

        if not poll_result.get("healthy", False):
            if poll_result.get("error_type") in {"timeout", "request_exception"}:
                state = "crashed"
            else:
                state = "degraded"
            errors_last_min = 1

        runtime_payload = {
            "app": poll_result.get("service_name", "unknown-service"),
            "env": self.env_config.get("environment", "dev"),
            "state": state,
            "latency_ms": float(poll_result.get("latency_ms", 0.0)),
            "errors_last_min": int(errors_last_min),
            "workers": int(workers),
        }

        self._log_runtime_payload(runtime_payload)
        return runtime_payload

    def run_monitoring_loop(
        self,
        service_name: str,
        base_url: str,
        health_endpoint: str = "/api/health",
        workers: int = 1,
        interval_seconds: float = 10.0,
        iterations: Optional[int] = 1,
    ) -> None:
        """Run bounded polling and emit runtime contract payloads."""
        if iterations is None or iterations <= 0:
            raise ValueError("iterations must be a positive integer in loopless mode")

        for count in range(iterations):
            poll_result = self.poll_service(
                service_name=service_name,
                base_url=base_url,
                health_endpoint=health_endpoint,
            )
            runtime_payload = self.build_runtime_payload(poll_result, workers=workers)

            print({
                "poll_result": poll_result,
                "runtime_payload": runtime_payload,
            })

            if count < iterations - 1:
                time.sleep(interval_seconds)

    def _log_result(self, result: Dict[str, Any]) -> None:
        """Persist poll result to CSV."""
        with open(self.log_file, "a", newline="", encoding="utf-8") as file_handle:
            writer = csv.writer(file_handle)
            writer.writerow([
                result["timestamp"],
                result["service_name"],
                result["target_url"],
                result["http_status"],
                result["healthy"],
                result["latency_ms"],
                result["error_detected"],
                result["error_type"],
                result["error_message"],
                result["environment"],
            ])

    def _log_runtime_payload(self, runtime_payload: Dict[str, Any]) -> None:
        """Persist generated runtime payload contract to CSV."""
        with open(self.runtime_payload_log_file, "a", newline="", encoding="utf-8") as file_handle:
            writer = csv.writer(file_handle)
            writer.writerow([
                datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
                runtime_payload["app"],
                runtime_payload["env"],
                runtime_payload["state"],
                runtime_payload["latency_ms"],
                runtime_payload["errors_last_min"],
                runtime_payload["workers"],
            ])


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Runtime Poller")
    parser.add_argument("--env", choices=["dev", "stage", "prod"], default="dev")
    parser.add_argument("--service", required=True, help="Service name")
    parser.add_argument("--base-url", required=True, help="Service base URL")
    parser.add_argument("--health-endpoint", default="/api/health", help="Health endpoint path")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds")
    parser.add_argument("--latency-warn-ms", type=float, default=2000.0, help="Latency warning threshold")
    parser.add_argument("--workers", type=int, default=1, help="Worker count for runtime payload")
    parser.add_argument("--interval-seconds", type=float, default=10.0, help="Polling interval in seconds")
    parser.add_argument("--iterations", type=int, default=1, help="Number of polls (must be >=1)")

    args = parser.parse_args()

    poller = RuntimePoller(
        env=args.env,
        timeout_seconds=args.timeout,
        latency_warn_ms=args.latency_warn_ms,
    )

    if args.iterations <= 0:
        raise ValueError("--iterations must be >= 1 in loopless mode")
    elif args.iterations == 1:
        poll_result = poller.poll_service(
            service_name=args.service,
            base_url=args.base_url,
            health_endpoint=args.health_endpoint,
        )
        runtime_payload = poller.build_runtime_payload(poll_result, workers=args.workers)

        print(json.dumps({
            "poll_result": poll_result,
            "runtime_payload": runtime_payload,
        }, indent=2))
    else:
        poller.run_monitoring_loop(
            service_name=args.service,
            base_url=args.base_url,
            health_endpoint=args.health_endpoint,
            workers=args.workers,
            interval_seconds=args.interval_seconds,
            iterations=args.iterations,
        )





def poll_all_services(env="dev"):
    poller = RuntimePoller(env=env)

    apps = load_apps()
    results = []

    for app in apps:
        service = app["name"]
        url = app["url"]

        result = poller.poll_service(service, url)
        results.append(result)

    return results

