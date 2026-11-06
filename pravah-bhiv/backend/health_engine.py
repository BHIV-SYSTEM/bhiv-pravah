"""
Pravah Canonical Health, Telemetry, Traffic, Performance & Incident Engine.

Implements requirements 1, 2, 3, 4, 6, and 7:
- Canonical 5-state health lifecycle (Healthy, Degraded, Unreachable, Stale, Not Monitored)
- Safe telemetry parsing with HTML sanitization and failure categorization
- Real-time traffic monitoring (total requests, 2xx/4xx/5xx status codes, sliding-window RPS, trends)
- Performance latency percentiles (P50, P95, P99, avg), timeout tracking, and slow endpoint detection
- Dependency graph with cascading failure impact
- Incident correlation engine with temporal grouping and probable cause synthesis
- Unified product health aggregation separating platform from product tiers
"""

import re
import time
import uuid
from collections import deque, defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ServiceState(str, Enum):
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    UNREACHABLE = "Unreachable"
    STALE = "Stale"
    NOT_MONITORED = "Not Monitored"


class FailureCategory(str, Enum):
    NONE = "none"
    HTTP_ERROR = "http_error"
    CONNECTION_REFUSED = "connection_refused"
    TIMEOUT = "timeout"
    INVALID_HEALTH_RESPONSE = "invalid_health_response"
    DEPENDENCY_FAILURE = "dependency_failure"
    UNKNOWN = "unknown"


def sanitize_html_detail(raw_text: str, status_code: Optional[int] = None) -> str:
    """
    Sanitize raw HTML or unstructured response bodies.
    Extracts title or status descriptions without leaking HTML tags or internal stack traces.
    """
    if not raw_text:
        return f"HTTP {status_code}" if status_code else "No response body"

    # Check if text looks like HTML
    if "<html" in raw_text.lower() or "<!doctype" in raw_text.lower() or "<head" in raw_text.lower():
        title_match = re.search(r"<title>(.*?)</title>", raw_text, re.IGNORECASE | re.DOTALL)
        if title_match:
            clean_title = re.sub(r"\s+", " ", title_match.group(1)).strip()
            return f"HTML Error Page: {clean_title} (HTTP {status_code})" if status_code else f"HTML Error Page: {clean_title}"

        # Strip tags if no title
        stripped = re.sub(r"<[^>]+>", " ", raw_text)
        cleaned = re.sub(r"\s+", " ", stripped).strip()[:100]
        return f"HTML Response (HTTP {status_code}): {cleaned}" if status_code else f"HTML Response: {cleaned}"

    # Plain text / JSON snippet
    cleaned = raw_text.strip().replace("\r", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > 200:
        cleaned = cleaned[:197] + "..."
    return cleaned


# =============================================================================
# Latency Reservoir & Percentile Calculator
# =============================================================================

class LatencyReservoir:
    """Maintains a rolling sample of response latencies and computes statistical percentiles."""

    def __init__(self, max_samples: int = 500):
        self.max_samples = max_samples
        self.samples: deque = deque(maxlen=max_samples)
        self.total_recorded = 0

    def record(self, latency_ms: float) -> None:
        if latency_ms >= 0:
            self.samples.append(float(latency_ms))
            self.total_recorded += 1

    def compute_stats(self) -> Dict[str, Optional[float]]:
        """Computes count, avg, p50, p95, and p99. Returns None for empty datasets."""
        if not self.samples:
            return {
                "count": 0,
                "avg_ms": None,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
            }

        sorted_samples = sorted(self.samples)
        n = len(sorted_samples)

        def _percentile(p: float) -> float:
            k = (n - 1) * p
            f = int(k)
            c = f + 1
            if c < n:
                d = k - f
                return sorted_samples[f] * (1 - d) + sorted_samples[c] * d
            return float(sorted_samples[f])

        avg = sum(sorted_samples) / n
        return {
            "count": n,
            "avg_ms": round(avg, 2),
            "p50_ms": round(_percentile(0.50), 2),
            "p95_ms": round(_percentile(0.95), 2),
            "p99_ms": round(_percentile(0.99), 2),
        }


# =============================================================================
# Traffic Monitor & RPS Calculator
# =============================================================================

class TrafficMonitor:
    """Tracks total requests, status codes, error rate, and sliding-window RPS."""

    def __init__(self, window_seconds: int = 60):
        self.total_requests = 0
        self.status_2xx = 0
        self.status_3xx = 0
        self.status_4xx = 0
        self.status_5xx = 0
        self.request_timestamps: deque = deque()  # (epoch_ts, status_code)
        self.window_seconds = window_seconds
        self.hourly_trend: Dict[str, Dict[str, int]] = {}

    def record_request(self, status_code: int, timestamp: Optional[float] = None) -> None:
        now = timestamp or time.time()
        self.total_requests += 1

        if 200 <= status_code < 300:
            self.status_2xx += 1
        elif 300 <= status_code < 400:
            self.status_3xx += 1
        elif 400 <= status_code < 500:
            self.status_4xx += 1
        elif status_code >= 500 or status_code == 0:
            self.status_5xx += 1

        self.request_timestamps.append((now, status_code))
        self._prune(now)

        # Record to hourly trend
        hour_key = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d %H:00")
        if hour_key not in self.hourly_trend:
            self.hourly_trend[hour_key] = {"total": 0, "errors": 0}
        self.hourly_trend[hour_key]["total"] += 1
        if status_code >= 400 or status_code == 0:
            self.hourly_trend[hour_key]["errors"] += 1

    def _prune(self, now: float) -> None:
        cutoff = now - 3600  # keep up to 1 hour in fine-grained queue
        while self.request_timestamps and self.request_timestamps[0][0] < cutoff:
            self.request_timestamps.popleft()

    def get_rps(self, window_sec: int = 60, current_time: Optional[float] = None) -> float:
        now = current_time or time.time()
        cutoff = now - window_sec
        recent_count = sum(1 for ts, _ in self.request_timestamps if ts >= cutoff)
        return round(recent_count / max(1, window_sec), 2)

    def get_error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(((self.status_4xx + self.status_5xx) / self.total_requests) * 100, 2)

    def get_summary(self) -> Dict[str, Any]:
        now = time.time()
        self._prune(now)
        return {
            "total_requests": self.total_requests,
            "success_2xx": self.status_2xx,
            "redirect_3xx": self.status_3xx,
            "client_error_4xx": self.status_4xx,
            "server_error_5xx": self.status_5xx,
            "error_rate_pct": self.get_error_rate(),
            "rps_1m": self.get_rps(60, now),
            "rps_5m": self.get_rps(300, now),
            "rps_1h": self.get_rps(3600, now),
            "hourly_trend": [
                {"hour": k, "total": v["total"], "errors": v["errors"]}
                for k, v in sorted(self.hourly_trend.items())[-24:]
            ],
        }


# =============================================================================
# Dependency Graph & Cascading Failure Engine
# =============================================================================

DEFAULT_DEPENDENCY_GRAPH: Dict[str, Dict[str, Any]] = {
    "gurukul-backend": {
        "product": "Gurukul",
        "tier": "product",
        "dependencies": ["postgres", "redis"],
    },
    "infiverse-hr-platform": {
        "product": "INFIVERSE HR",
        "tier": "product",
        "dependencies": ["bhiv-core", "bhiv-masterdb-ingestion-certification-service"],
    },
    "bhiv-hr-agent": {
        "product": "INFIVERSE HR",
        "tier": "product",
        "dependencies": ["infiverse-hr-platform", "control-plane"],
    },
    "bhiv-hr-langgraph": {
        "product": "INFIVERSE HR",
        "tier": "product",
        "dependencies": ["bhiv-hr-agent"],
    },
    "crm-api": {
        "product": "AI CRM",
        "tier": "product",
        "dependencies": ["postgres", "redis"],
    },
    "parikshak-system": {
        "product": "Parikshak",
        "tier": "product",
        "dependencies": ["bhiv-core"],
    },
    "ttg": {
        "product": "TTG",
        "tier": "product",
        "dependencies": ["redis"],
    },
    "samruddhi": {
        "product": "Samruddhi",
        "tier": "product",
        "dependencies": ["samruddhi-hft"],
    },
    "uniguru_ai": {
        "product": "UniGuru AI",
        "tier": "product",
        "dependencies": ["redis"],
    },
    "uniguru-ai": {
        "product": "UniGuru AI",
        "tier": "product",
        "dependencies": ["redis"],
    },
    "prompt-runner01": {
        "product": "Prompt Runner",
        "tier": "product",
        "dependencies": ["control-plane"],
    },
    "trade-bot": {
        "product": "Trade Bot",
        "tier": "product",
        "dependencies": ["redis"],
    },
    "workflow-blackhole": {
        "product": "Workflow Blackhole",
        "tier": "product",
        "dependencies": ["bhiv-core"],
    },
    "block-chain": {
        "product": "Blockchain",
        "tier": "product",
        "dependencies": [],
    },
    "bhiv-sarathi": {
        "product": "Sarathi",
        "tier": "product",
        "dependencies": ["bhiv-core"],
    },
    "control-plane": {
        "product": "Pravah Platform",
        "tier": "platform",
        "dependencies": ["redis"],
    },
    "decision-brain": {
        "product": "Pravah Platform",
        "tier": "platform",
        "dependencies": ["control-plane", "redis"],
    },
    "observer": {
        "product": "Pravah Platform",
        "tier": "platform",
        "dependencies": [],
    },
}


class DependencyGraph:
    """Tracks known dependencies and evaluates cascading failures."""

    def __init__(self, graph: Optional[Dict[str, Dict[str, Any]]] = None):
        self.graph = graph or DEFAULT_DEPENDENCY_GRAPH.copy()

    def get_dependencies_for(self, service_name: str) -> List[str]:
        return self.graph.get(service_name, {}).get("dependencies", [])

    def check_cascading_impact(
        self, service_name: str, services_health: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, Optional[str]]:
        """
        Determines whether any direct or indirect dependency is unreachable or degraded.
        Returns (has_dependency_failure, failed_dependency_name).
        """
        deps = self.get_dependencies_for(service_name)
        for dep in deps:
            dep_info = services_health.get(dep)
            if dep_info:
                st = dep_info.get("status")
                if st in (ServiceState.UNREACHABLE.value, ServiceState.DEGRADED.value, "unreachable", "degraded"):
                    return True, dep
        return False, None

    def get_full_topology(self, services_health: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        topology = []
        for svc_name, meta in self.graph.items():
            deps = meta.get("dependencies", [])
            dep_statuses = []
            for d in deps:
                d_health = services_health.get(d, {})
                dep_statuses.append({
                    "dependency": d,
                    "status": d_health.get("status", ServiceState.NOT_MONITORED.value),
                    "last_checked": d_health.get("last_checked"),
                })
            topology.append({
                "service": svc_name,
                "product": meta.get("product", svc_name),
                "tier": meta.get("tier", "product"),
                "dependencies": dep_statuses,
            })
        return topology


# =============================================================================
# Incident Correlation Engine
# =============================================================================

class IncidentCorrelationEngine:
    """Correlates anomalies within defensible temporal windows into cohesive Incident objects."""

    def __init__(self, correlation_window_seconds: int = 300):
        self.window_seconds = correlation_window_seconds
        self.incidents: List[Dict[str, Any]] = []

    def evaluate(
        self,
        services_health: Dict[str, Dict[str, Any]],
        traffic_summary: Dict[str, Any],
        perf_summary: Dict[str, Any],
        dep_graph: DependencyGraph,
    ) -> List[Dict[str, Any]]:
        """
        Evaluates current system state and generates/updates incidents.
        Correlates: Error spikes + Latency surges + Unreachable services + Cascading dependencies.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Identify failing services
        failing_services = []
        unreachable_services = []
        for name, info in services_health.items():
            st = info.get("status")
            if st == ServiceState.UNREACHABLE.value or st == "unreachable":
                unreachable_services.append(name)
            elif st == ServiceState.DEGRADED.value or st == "degraded":
                failing_services.append(name)

        error_rate = traffic_summary.get("error_rate_pct", 0.0)
        p95_latency = perf_summary.get("overall_p95_ms") or 0.0
        slow_endpoints = perf_summary.get("slow_endpoints", [])

        symptoms = []
        severity = "LOW"
        affected_products = set()
        probable_causes = []

        if unreachable_services:
            symptoms.append(f"{len(unreachable_services)} services unreachable ({', '.join(unreachable_services[:3])})")
            severity = "CRITICAL"
            for s in unreachable_services:
                meta = dep_graph.graph.get(s, {})
                affected_products.add(meta.get("product", s))
                # Check if this unreachable service affects others
                cascades = [k for k, v in dep_graph.graph.items() if s in v.get("dependencies", [])]
                if cascades:
                    probable_causes.append(f"Infrastructure outage on core dependency '{s}' impacting: {', '.join(cascades)}")

        if error_rate > 5.0:
            symptoms.append(f"Elevated HTTP error rate ({error_rate}%)")
            if severity != "CRITICAL":
                severity = "HIGH"

        if p95_latency > 2000.0 or len(slow_endpoints) > 2:
            symptoms.append(f"High latency detected (P95: {p95_latency}ms)")
            if severity == "LOW":
                severity = "MEDIUM"

        if failing_services:
            for s in failing_services:
                meta = dep_graph.graph.get(s, {})
                affected_products.add(meta.get("product", s))

        # Check if an incident should be active
        if symptoms and (unreachable_services or error_rate > 5.0 or len(failing_services) >= 2):
            probable_source = "; ".join(probable_causes) if probable_causes else (
                f"Downstream service degradation in {', '.join(failing_services[:3])}" if failing_services else "Traffic surge causing resource contention"
            )

            # Check if existing active incident matches within temporal correlation window
            active_incident = next((inc for inc in self.incidents if inc.get("status") == "ACTIVE"), None)
            within_window = False
            if active_incident:
                try:
                    last_up = active_incident.get("last_updated", "")
                    last_up_dt = datetime.fromisoformat(last_up.replace("Z", "+00:00"))
                    within_window = (datetime.now(timezone.utc) - last_up_dt).total_seconds() <= self.window_seconds
                except Exception:
                    within_window = False

            if active_incident and within_window:
                # Update existing active incident within temporal correlation window
                active_incident["last_updated"] = now_iso
                active_incident["symptoms"] = sorted(list(set(active_incident.get("symptoms", []) + symptoms)))
                active_incident["affected_products"] = sorted(list(set(active_incident.get("affected_products", []) + list(affected_products))))
                active_incident["severity"] = severity
                active_incident["probable_source"] = probable_source
                active_incident["hypothesis"] = probable_source
                active_incident["is_confirmed_cause"] = False
            else:
                if active_incident and not within_window:
                    # Previous incident expired outside the correlation window
                    active_incident["status"] = "EXPIRED"
                    active_incident["resolution"] = "Anomaly activity exceeded temporal correlation window without recurrence."
                    active_incident["resolved_at"] = now_iso

                # Create new incident
                new_incident = {
                    "incident_id": f"INC-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}",
                    "started_at": now_iso,
                    "last_updated": now_iso,
                    "status": "ACTIVE",
                    "severity": severity,
                    "symptoms": sorted(symptoms),
                    "affected_products": sorted(list(affected_products)),
                    "probable_source": probable_source,
                    "hypothesis": probable_source,
                    "is_confirmed_cause": False,
                    "resolution": None,
                }
                self.incidents.append(new_incident)
        else:
            # Auto-resolve any active incidents if healthy
            for inc in self.incidents:
                if inc.get("status") == "ACTIVE":
                    inc["status"] = "RESOLVED"
                    inc["resolved_at"] = now_iso
                    inc["resolution"] = "All services returned to Healthy operational parameters."

        return list(reversed(self.incidents[-20:]))


# =============================================================================
# Service Health Tracker (Unified Manager)
# =============================================================================

class ServiceHealthTracker:
    """
    Centralized health tracking engine implementing the 5 canonical states,
    telemetry diagnostics, performance tracking, traffic counters, and incident correlation.
    """

    def __init__(self, poll_interval_sec: float = 10.0, sla_latency_ms: float = 500.0):
        self.poll_interval = poll_interval_sec
        self.sla_latency = sla_latency_ms
        self.services: Dict[str, Dict[str, Any]] = {}

        # Dedicated Traffic Monitors per event source
        self.application_traffic = TrafficMonitor()
        self.probe_traffic = TrafficMonitor()
        self.agent_traffic = TrafficMonitor()
        self.synthetic_traffic = TrafficMonitor()

        # Dedicated Latency Reservoirs per event source
        self.application_latency = LatencyReservoir()
        self.probe_latency = LatencyReservoir()
        self.agent_latency = LatencyReservoir()
        self.synthetic_latency = LatencyReservoir()

        # Per-endpoint and per-service reservoirs
        self.application_endpoints: Dict[str, LatencyReservoir] = defaultdict(lambda: LatencyReservoir())
        self.latency_reservoirs: Dict[str, LatencyReservoir] = {}

        # Backward compatibility aliases for existing test suites
        self.traffic_monitor = self.probe_traffic
        self.overall_latency = self.probe_latency

        self.dep_graph = DependencyGraph()
        self.incident_engine = IncidentCorrelationEngine()
        self.timeout_count = 0

    def record_application_request(
        self,
        service: str,
        method: str,
        endpoint: str,
        http_status: int,
        latency_ms: float,
        timestamp: Optional[float] = None,
        source: str = "application",
    ) -> None:
        """
        Records an application HTTP request into isolated application traffic and latency reservoirs.
        Strictly separated from background health probes and synthetic tests.
        """
        now = timestamp or time.time()
        endpoint_key = f"{service}:{method.upper()} {endpoint}"

        if source == "synthetic":
            self.synthetic_traffic.record_request(http_status, now)
            if latency_ms >= 0:
                self.synthetic_latency.record(latency_ms)
        elif source == "agent":
            self.agent_traffic.record_request(http_status, now)
            if latency_ms >= 0:
                self.agent_latency.record(latency_ms)
        elif source == "probe":
            self.probe_traffic.record_request(http_status, now)
            if latency_ms >= 0:
                self.probe_latency.record(latency_ms)
        else:
            # Standard application user/client traffic
            self.application_traffic.record_request(http_status, now)
            if latency_ms >= 0:
                self.application_latency.record(latency_ms)
                self.application_endpoints[endpoint_key].record(latency_ms)

    def register_service(self, name: str, url: str, tier: str = "product") -> None:
        if name not in self.services:
            self.services[name] = {
                "name": name,
                "url": url,
                "tier": tier,
                "status": ServiceState.NOT_MONITORED.value,
                "consecutive_failures": 0,
                "first_failure_time": None,
                "last_successful_check": None,
                "last_checked": None,
                "failure_reason": None,
                "failure_category": FailureCategory.NONE.value,
                "failure_duration_seconds": 0.0,
                "http_status": None,
                "content_type": None,
                "latency_ms": None,
            }
            self.latency_reservoirs[name] = LatencyReservoir()

    def record_probe_result(
        self,
        name: str,
        url: str,
        ok: bool,
        http_status: Optional[int],
        raw_detail: str,
        latency_ms: float,
        error_type: Optional[str] = None,
        content_type: Optional[str] = None,
        tier: str = "product",
    ) -> Dict[str, Any]:
        """Processes and records a single health check probe."""
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        if name not in self.services:
            self.register_service(name, url, tier)

        svc = self.services[name]
        svc["url"] = url
        svc["last_checked"] = now_iso
        svc["latency_ms"] = round(latency_ms, 1)
        svc["content_type"] = content_type or "application/json"

        # Record to traffic and latency reservoirs
        status_code = http_status or (200 if ok else 0)
        self.traffic_monitor.record_request(status_code)
        if latency_ms >= 0:
            self.latency_reservoirs[name].record(latency_ms)
            self.overall_latency.record(latency_ms)

        clean_detail = sanitize_html_detail(raw_detail, http_status)

        # Categorize failure & evaluate canonical state
        if error_type == "connection_refused" or (not ok and http_status is None and error_type != "timeout"):
            new_status = ServiceState.UNREACHABLE.value
            cat = FailureCategory.CONNECTION_REFUSED.value
            reason = f"Connection refused to {url}"
        elif error_type == "timeout" or (http_status is None and "timed out" in str(raw_detail).lower()):
            new_status = ServiceState.DEGRADED.value
            cat = FailureCategory.TIMEOUT.value
            reason = f"Request timed out after {latency_ms:.1f}ms"
            self.timeout_count += 1
        elif not ok:
            new_status = ServiceState.DEGRADED.value
            cat = FailureCategory.HTTP_ERROR.value
            reason = f"HTTP {http_status}: {clean_detail}"
        else:
            # Response was HTTP 2xx/3xx
            # Check if dependencies are degraded (cascading check)
            has_dep_failure, failed_dep = self.dep_graph.check_cascading_impact(name, self.services)
            if has_dep_failure:
                new_status = ServiceState.DEGRADED.value
                cat = FailureCategory.DEPENDENCY_FAILURE.value
                reason = f"Dependency '{failed_dep}' is currently degraded or unreachable"
            elif latency_ms > self.sla_latency:
                new_status = ServiceState.DEGRADED.value
                cat = FailureCategory.NONE.value
                reason = f"High latency ({latency_ms:.1f}ms exceeds {self.sla_latency:.0f}ms SLA)"
            else:
                new_status = ServiceState.HEALTHY.value
                cat = FailureCategory.NONE.value
                reason = None

        svc["status"] = new_status
        svc["failure_category"] = cat
        svc["failure_reason"] = reason
        svc["http_status"] = http_status

        if new_status == ServiceState.HEALTHY.value:
            svc["consecutive_failures"] = 0
            svc["first_failure_time"] = None
            svc["failure_duration_seconds"] = 0.0
            svc["last_successful_check"] = now_iso
        else:
            svc["consecutive_failures"] = svc.get("consecutive_failures", 0) + 1
            if not svc.get("first_failure_time"):
                svc["first_failure_time"] = now_iso
                svc["failure_duration_seconds"] = 0.0
            else:
                try:
                    first_dt = datetime.fromisoformat(svc["first_failure_time"].replace("Z", "+00:00"))
                    svc["failure_duration_seconds"] = round((now_dt - first_dt).total_seconds(), 1)
                except Exception:
                    svc["failure_duration_seconds"] = 0.0

        return svc

    def check_staleness(self) -> None:
        """Flags services as STALE if their last check exceeds 2x the polling interval."""
        now_dt = datetime.now(timezone.utc)
        threshold_seconds = 2.5 * self.poll_interval

        for name, svc in self.services.items():
            last_checked = svc.get("last_checked")
            if not last_checked:
                svc["status"] = ServiceState.NOT_MONITORED.value
                continue
            try:
                last_dt = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
                if (now_dt - last_dt).total_seconds() > threshold_seconds:
                    svc["status"] = ServiceState.STALE.value
                    svc["failure_reason"] = f"Monitoring data is stale (last checked {(now_dt - last_dt).total_seconds():.0f}s ago)"
                    svc["failure_category"] = FailureCategory.UNKNOWN.value
            except Exception:
                pass

    def get_traffic_summary(self) -> Dict[str, Any]:
        """
        Returns traffic summaries strictly separated across event populations:
        - Application HTTP traffic (user/client requests)
        - Observer automated health probes
        - Agent autonomous execution events
        - Synthetic benchmark tests
        """
        app_sum = self.application_traffic.get_summary()
        probe_sum = self.probe_traffic.get_summary()
        agent_sum = self.agent_traffic.get_summary()
        synth_sum = self.synthetic_traffic.get_summary()

        has_app_traffic = bool(app_sum["total_requests"] > 0)
        # Use application traffic as primary when present, otherwise present explicit empty application state
        primary = app_sum if has_app_traffic else {
            "total_requests": 0,
            "success_2xx": 0,
            "redirect_3xx": 0,
            "client_error_4xx": 0,
            "server_error_5xx": 0,
            "error_rate_pct": 0.0,
            "rps_1m": 0.0,
            "rps_5m": 0.0,
            "rps_1h": 0.0,
            "hourly_trend": [],
        }

        return {
            "has_application_traffic": has_app_traffic,
            # Primary application traffic metrics
            **primary,
            # Distinct source populations (Requirement 3 & Phase 3)
            "sources": {
                "application": app_sum,
                "probe": probe_sum,
                "agent": agent_sum,
                "synthetic": synth_sum,
            },
            # Explicit probe metrics for console display
            "probe_total_requests": probe_sum["total_requests"],
            "probe_rps_1m": probe_sum["rps_1m"],
            "probe_rps_5m": probe_sum["rps_5m"],
            "probe_rps_1h": probe_sum["rps_1h"],
            "probe_error_rate_pct": probe_sum["error_rate_pct"],
        }

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Calculates separate percentiles and slow endpoints for application traffic vs probes.
        Guarantees that socket probe timeouts are never presented as end-user application latency.
        """
        app_stats = self.application_latency.compute_stats()
        probe_stats = self.probe_latency.compute_stats()
        agent_stats = self.agent_latency.compute_stats()
        synth_stats = self.synthetic_latency.compute_stats()

        slow_app_endpoints = []
        for ep_key, res in self.application_endpoints.items():
            st = res.compute_stats()
            p95 = st.get("p95_ms")
            if p95 is not None and p95 > self.sla_latency:
                slow_app_endpoints.append({
                    "service": ep_key,
                    "p95_ms": p95,
                    "avg_ms": st.get("avg_ms"),
                    "sla_ms": self.sla_latency,
                    "type": "application",
                })

        slow_probe_endpoints = []
        for name, reservoir in self.latency_reservoirs.items():
            svc_stats = reservoir.compute_stats()
            p95 = svc_stats.get("p95_ms")
            if p95 is not None and p95 > self.sla_latency:
                slow_probe_endpoints.append({
                    "service": name,
                    "p95_ms": p95,
                    "avg_ms": svc_stats.get("avg_ms"),
                    "sla_ms": self.sla_latency,
                    "type": "probe",
                })

        has_app_data = bool(app_stats["count"] > 0)
        # Select slow endpoints: application when present; probe when testing probe simulation
        active_slow_endpoints = slow_app_endpoints if has_app_data else slow_probe_endpoints

        return {
            "has_application_data": has_app_data,
            # Top-level application latency metrics (None when no user samples exist)
            "overall_avg_ms": app_stats.get("avg_ms") if has_app_data else None,
            "overall_p50_ms": app_stats.get("p50_ms") if has_app_data else None,
            "overall_p95_ms": app_stats.get("p95_ms") if has_app_data else None,
            "overall_p99_ms": app_stats.get("p99_ms") if has_app_data else None,
            "total_samples": app_stats.get("count", 0),
            "slow_endpoints": active_slow_endpoints,
            # Distinct source breakdowns (Requirement 4 & Phase 3)
            "sources": {
                "application": {
                    **app_stats,
                    "slow_endpoints": slow_app_endpoints,
                },
                "probe": {
                    **probe_stats,
                    "timeout_count": self.timeout_count,
                    "slow_endpoints": slow_probe_endpoints,
                },
                "agent": agent_stats,
                "synthetic": synth_stats,
            },
            # Explicit probe latency fields
            "probe_p50_ms": probe_stats.get("p50_ms"),
            "probe_p95_ms": probe_stats.get("p95_ms"),
            "probe_p99_ms": probe_stats.get("p99_ms"),
            "probe_timeout_count": self.timeout_count,
            "probe_total_samples": probe_stats.get("count", 0),
        }

    def get_unified_product_health(self) -> Dict[str, Any]:
        """Returns consolidated product-level health scorecard separated from platform health."""
        self.check_staleness()
        perf = self.get_performance_summary()
        traffic = self.traffic_monitor.get_summary()
        incidents = self.incident_engine.evaluate(self.services, traffic, perf, self.dep_graph)

        products = []
        platform_services = []

        for name, info in self.services.items():
            tier = info.get("tier", "product")
            reservoir = self.latency_reservoirs.get(name)
            svc_perf = reservoir.compute_stats() if reservoir else {}

            item = {
                "name": name,
                "url": info.get("url"),
                "status": info.get("status"),
                "tier": tier,
                "consecutive_failures": info.get("consecutive_failures", 0),
                "last_successful_check": info.get("last_successful_check"),
                "last_checked": info.get("last_checked"),
                "failure_reason": info.get("failure_reason"),
                "failure_category": info.get("failure_category"),
                "failure_duration_seconds": info.get("failure_duration_seconds", 0.0),
                "http_status": info.get("http_status"),
                "latency_p95_ms": svc_perf.get("p95_ms") if svc_perf.get("p95_ms") is not None else info.get("latency_ms"),
                "latency_avg_ms": svc_perf.get("avg_ms"),
                "dependencies": self.dep_graph.get_dependencies_for(name),
            }

            if tier == "platform":
                platform_services.append(item)
            else:
                products.append(item)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "products": products,
            "platform_health": {
                "status": "Healthy" if all(s["status"] == "Healthy" for s in platform_services) else (
                    "Degraded" if any(s["status"] == "Degraded" for s in platform_services) else "Unreachable"
                ),
                "services": platform_services,
            },
            "traffic": traffic,
            "performance": perf,
            "active_incidents": [i for i in incidents if i.get("status") == "ACTIVE"],
            "all_incidents": incidents,
        }
