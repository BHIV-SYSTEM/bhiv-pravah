import glob
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from control_plane.app_override_manager import AppOverrideManager
from core_hooks.signal_builder import build_base_signal
import pathlib
from executer.runner import execute
from sarathi.router import build_sarathi_headers
from control_plane.capabilities.capability_discovery import CapabilityDiscovery

class MultiAppControlPlane:
    """Aggregates registry, health overview, and decision history across apps."""

    def __init__(self, env: str = "dev"):
        self.env = env
        # Resolve path relative to this file to prevent CWD dependency issues
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.registry_dir = os.path.join(base_dir, "apps", "registry")
        self.history_file = os.path.join(os.path.dirname(base_dir), "logs", "control_plane", "decision_history.jsonl")
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        self.override_manager = AppOverrideManager()

    def list_apps(self) -> List[Dict[str, Any]]:
        apps = []
        for file_path in glob.glob(os.path.join(self.registry_dir, "*.json")):
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    spec = json.load(handle)
                file_stem = os.path.splitext(os.path.basename(file_path))[0]
                app_id = spec.get("app_id") or spec.get("id") or file_stem
                app_name = spec.get("name") or file_stem
                apps.append({
                    "app_name": app_name,
                    "app_id": app_id,
                    "id": app_id,
                    "name": app_name,
                    "runtime": spec.get("type"),
                    "source_type": spec.get("source_type"),
                    "health_endpoint": spec.get("health_endpoint"),
                    "port": spec.get("port"),
                    "spec_file": file_path.replace("\\", "/")
                })
            except Exception:
                continue
        apps.sort(key=lambda x: x["app_name"])
        return apps

    def list_runtime_entities(self) -> List[Dict[str, Any]]:
        """
        Return a unified, read-only view of registered applications
        and non-service capabilities.

        Existing application discovery remains unchanged.
        Capabilities are discovered separately and are not treated
        as HTTP services.
        """

        entities = []

        # Existing applications
        for app in self.list_apps():
            entity = dict(app)
            entity["entity_kind"] = "application"
            entities.append(entity)

        # Non-service capabilities
        capability_discovery = CapabilityDiscovery()

        for capability in capability_discovery.discover_all():
            entity = dict(capability)
            entity["entity_kind"] = "capability"
            entities.append(entity)

        return entities

    def append_decision_history(self, record: Dict[str, Any]) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **record
        }
        with open(self.history_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

        # Build and emit a standardized sarathi signal when trace_id is available
        try:
            # Prefer an explicit `event` object if present (useful where action is finalized).
            event = payload.get('event') or payload

            # Use trace_id from the explicit event when available (strict)
            trace_id = event.get('trace_id')
            app_name = payload.get('app_name')
            action = payload.get('executed_action') or payload.get('decision_action') or payload.get('action')

            if trace_id and app_name and action:
                # Build signal using the event's trace id (ensures propagation)
                signal = build_base_signal(trace_id=event["trace_id"], service_id=app_name, action=action)

                # Prefer direct execution via executer with signed Sarathi service headers
                headers = build_sarathi_headers(signal)
                try:
                    execution_result = execute(signal, headers)
                except Exception:
                    # Fallback: persist emitted signals for now (sarathi emitter may pick these up)
                    signals_dir = pathlib.Path("logs/sarathi")
                    signals_dir.mkdir(parents=True, exist_ok=True)
                    signals_file = signals_dir / "signals.jsonl"
                    with open(signals_file, "a", encoding="utf-8") as sf:
                        sf.write(json.dumps(signal) + "\n")
        except Exception:
            # Never let signal emission break the control plane flow
            pass

    def _read_history(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.history_file):
            return []

        rows = []
        with open(self.history_file, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def get_decision_history(self, app_name: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = [row for row in self._read_history() if row.get("app_name") == app_name]
        rows.sort(key=lambda row: row.get("timestamp", ""), reverse=True)
        return rows[: max(1, min(limit, 1000))]

    @staticmethod
    def _norm(s: Optional[str]) -> str:
        import re
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())

    KNOWN_ALIASES = {
        "aicrmsetu": "crmapi",
        "crmapi": "aicrmsetu",
        "shaktigcinfra": "parakosha",
        "parakosha": "shaktigcinfra",
    }

    def _fetch_observer_status(self) -> Dict[str, str]:
        """Fetch live service status from the Observer API (/api/status).

        Returns a mapping of service-name → canonical status string
        (e.g. "healthy", "unreachable", "degraded"). On network failure an
        empty dict is returned so that callers degrade gracefully to
        STATUS NOT REPORTED rather than raising.
        """
        import os
        import requests as _req

        candidates = []
        raw_env = os.getenv("PRAVAH_OBSERVER_URL") or os.getenv("NEXT_PUBLIC_OBSERVER_URL")
        if raw_env:
            clean = raw_env.strip()
            if "/api/" in clean:
                clean = clean.split("/api/")[0]
            clean = clean.rstrip("/")
            candidates.append(clean)

        obs_host = os.getenv("PRAVAH_OBSERVER_HOST")
        obs_port = os.getenv("PRAVAH_OBSERVER_PORT", "8600")
        if obs_host:
            candidates.append(f"http://{obs_host}:{obs_port}")

        # Check environment files for configured host / URLs
        base_dir = os.path.dirname(os.path.abspath(__file__))
        repo_backend = os.path.dirname(base_dir)
        repo_root = os.path.dirname(repo_backend)
        env_files = [
            os.path.join(repo_backend, "environments", f"{self.env}.env"),
            os.path.join(repo_root, ".env.frontend"),
            os.path.join(repo_root, ".env"),
            os.path.join(repo_backend, ".env"),
        ]
        for ef in env_files:
            if os.path.exists(ef):
                try:
                    with open(ef, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                k, v = k.strip(), v.strip().strip('"').strip("'")
                                if k in ("PRAVAH_OBSERVER_URL", "NEXT_PUBLIC_OBSERVER_URL"):
                                    if "/api/" in v:
                                        v = v.split("/api/")[0]
                                    candidates.append(v.rstrip("/"))
                                elif k == "VM_IP" and v:
                                    candidates.append(f"http://{v}:8600")
                except Exception:
                    pass

        # Standard defaults
        candidates.extend([
            "http://163.128.209.18:8600",
            "http://localhost:8600",
            "http://127.0.0.1:8600",
            "http://observer:8600",
        ])

        seen = set()
        unique_candidates = [c for c in candidates if c and not (c in seen or seen.add(c))]

        for base_url in unique_candidates:
            try:
                resp = _req.get(
                    f"{base_url}/api/status",
                    timeout=2,
                    headers={"User-Agent": "Pravah-ControlPlane/1.0"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw_services = data.get("services", {})
                    if raw_services:
                        return {
                            name: (info.get("status") or "unknown").lower()
                            for name, info in raw_services.items()
                        }
            except Exception:
                continue

        return {}

    def _resolve_service_health_url(self, app: Dict[str, Any], file_stem: str) -> Optional[str]:
        """Resolves configured URL or health probe for services with explicit endpoints."""
        import os
        clean_stem = file_stem.upper().replace("-", "_")
        env_keys = [
            f"PRAVAH_{clean_stem}",
            f"PRAVAH_{clean_stem}_API",
            f"PRAVAH_{clean_stem}_URL",
        ]
        base_url = None
        for k in env_keys:
            val = os.getenv(k)
            if val and not val.startswith("##"):
                base_url = val.rstrip("/")
                break

        health_ep = app.get("health_endpoint") or "/health"
        if base_url:
            if health_ep.startswith("/") and base_url.endswith("/"):
                return f"{base_url[:-1]}{health_ep}"
            return f"{base_url}{health_ep}"

        return None

    @staticmethod
    def _probe_live_endpoint(url: str) -> Optional[str]:
        """Performs a lightweight probe of a configured service health URL."""
        import requests as _req
        try:
            r = _req.get(url, timeout=1.5, headers={"User-Agent": "Pravah-ControlPlane-Probe/1.0"})
            if r.status_code == 200:
                return "healthy"
            elif r.status_code >= 500:
                return "degraded"
            else:
                return "unreachable"
        except Exception:
            return "unreachable"

    @staticmethod
    def _derive_runtime_status(
        observer_status,  # type: Optional[str]
        last_history_row,  # type: Optional[Dict[str, Any]]
        probe_status=None,  # type: Optional[str]
    ) -> str:
        """Map observer/probe/history data to one of the four canonical status labels.

        Priority (highest to lowest):
          1. Live observer probe result  → HEALTHY / DEGRADED / UNREACHABLE
          2. Live endpoint probe result   → HEALTHY / DEGRADED / UNREACHABLE
          3. Decision-history success     → HEALTHY
          4. No data available            → STATUS NOT REPORTED (unknown)

        NEVER returns HEALTHY from registry registration alone.
        """
        if observer_status:
            s = observer_status.lower()
            if s in ("healthy", "online", "ok", "running"):
                return "healthy"
            if s in ("degraded", "overloaded", "slow"):
                return "degraded"
            if s in ("unreachable", "offline", "error", "crashed",
                     "connection_refused", "timeout"):
                return "unreachable"

        if probe_status:
            return probe_status

        # Fall back to history only when observer/probe has no data for this app.
        if last_history_row and last_history_row.get("execution_success") is True:
            return "healthy"

        return "unknown"  # maps to "STATUS NOT REPORTED" in the UI

    def get_health_overview(self) -> List[Dict[str, Any]]:
        apps = self.list_apps()
        history_rows = self._read_history()

        # Fetch live status from Observer (non-fatal – empty dict on failure)
        observer_statuses = self._fetch_observer_status()

        latest_by_app: Dict[str, Dict[str, Any]] = {}
        for row in history_rows:
            app_name = row.get("app_name")
            if not app_name:
                continue
            old = latest_by_app.get(app_name)
            if old is None or row.get("timestamp", "") > old.get("timestamp", ""):
                latest_by_app[app_name] = row

        overview = []
        for app in apps:
            app_name = app["app_name"]
            app_id = app.get("app_id") or ""
            file_stem = os.path.splitext(os.path.basename(app.get("spec_file") or ""))[0]
            last = latest_by_app.get(app_name) or latest_by_app.get(app_id) or latest_by_app.get(file_stem)
            override = (
                self.override_manager.get_app_override(app_name)
                or self.override_manager.get_app_override(app_id)
                or self.override_manager.get_app_override(file_stem)
            )

            # Match observer service name accurately across names, IDs, stems, and aliases
            norm_names = {
                self._norm(app_name),
                self._norm(app_id),
                self._norm(file_stem),
            }
            observer_status_raw = None  # type: Optional[str]
            for obs_name, obs_status in observer_statuses.items():
                norm_obs = self._norm(obs_name)
                if (
                    obs_name.lower() in (app_name.lower(), app_id.lower(), file_stem.lower())
                    or norm_obs in norm_names
                    or self.KNOWN_ALIASES.get(norm_obs) in norm_names
                ):
                    observer_status_raw = obs_status
                    break

            # Probe live endpoint if observer has no data but endpoint is configured
            probe_status = None
            if not observer_status_raw:
                endpoint_url = self._resolve_service_health_url(app, file_stem)
                if endpoint_url:
                    probe_status = self._probe_live_endpoint(endpoint_url)

            runtime_status = self._derive_runtime_status(observer_status_raw, last, probe_status=probe_status)

            overview.append({
                "app_name": app_name,
                "app_id": app_id,
                "runtime": app.get("runtime"),
                "source_type": app.get("source_type"),
                "health_endpoint": app.get("health_endpoint"),
                # Canonical runtime status: "healthy"|"degraded"|"unreachable"|"unknown"
                "status": runtime_status,
                # Expose raw observer value for transparency
                "observer_status": observer_status_raw,
                "last_action": (last or {}).get("executed_action"),
                "last_reason": (last or {}).get("reason"),
                "last_seen": (last or {}).get("timestamp"),
                "manual_freeze": bool((override or {}).get("freeze_enabled", False)),
                "freeze_reason": (override or {}).get("reason"),
            })

        overview.sort(key=lambda x: x["app_name"])
        return overview

    def set_manual_override(self, app_name: str, duration_minutes: int, reason: str) -> Dict[str, Any]:
        return self.override_manager.set_temporary_freeze(app_name, duration_minutes, reason)

    def clear_manual_override(self, app_name: str) -> Dict[str, Any]:
        return self.override_manager.clear_freeze(app_name)
