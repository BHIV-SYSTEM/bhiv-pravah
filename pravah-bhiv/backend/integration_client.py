"""Integration client for canonical Pravah control-plane API."""

from typing import Any, Dict, List, Optional

import requests


class OrchestratorClient:
    """Client for canonical API endpoints exposed by api.agent_api."""

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip('/')
        self.timeout = max(1, int(timeout))

    def health(self) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/api/health", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def status(self) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/api/status", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def process_runtime_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/runtime",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def list_apps(self) -> List[Dict[str, Any]]:
        response = requests.get(f"{self.base_url}/api/control-plane/apps", timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        return result.get("apps", [])

    def health_overview(self) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/api/control-plane/health", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def app_history(self, app_name: str, limit: int = 100) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/api/control-plane/history/{app_name}",
            params={"limit": limit},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def set_freeze(self, app_name: str, duration_minutes: int, reason: str = "manual_override") -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/control-plane/override",
            json={
                "app_name": app_name,
                "action": "set_freeze",
                "duration_minutes": duration_minutes,
                "reason": reason,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def clear_freeze(self, app_name: str, reason: str = "manual_unfreeze") -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/control-plane/override",
            json={
                "app_name": app_name,
                "action": "clear_freeze",
                "duration_minutes": 1,
                "reason": reason,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    client = OrchestratorClient("http://localhost:7000")

    print("Health:")
    print(client.health())

    print("\nStatus:")
    print(client.status())

    sample_payload: Dict[str, Any] = {
        "app": "sample-backend",
        "env": "dev",
        "state": "running",
        "latency_ms": 120,
        "errors_last_min": 0,
        "workers": 2,
    }

    print("\nRuntime decision:")
    print(client.process_runtime_payload(sample_payload))
