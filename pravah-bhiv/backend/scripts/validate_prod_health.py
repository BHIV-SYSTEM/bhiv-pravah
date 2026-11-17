#!/usr/bin/env python3
"""
Pravah Production Health Validation Script
==========================================
Validates all Pravah production service endpoints and generates a
machine-readable proof log for deployment evidence.

Usage:
    python scripts/validate_prod_health.py
    python scripts/validate_prod_health.py --env prod --output deployment_verification_packet/prod_runtime_health.json

Exit codes:
    0  All checks passed
    1  Partial failure (some services unreachable — check observer targets)
    2  Critical failure (Pravah core services down)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    import requests
except ImportError:
    print("[ERROR] requests not installed. Run: pip install requests")
    sys.exit(2)


# ---------------------------------------------------------------------------
# Service Definitions
# ---------------------------------------------------------------------------

def _get_core_checks(base: Dict[str, str]) -> List[Dict[str, Any]]:
    """Critical Pravah services — failure = exit code 2."""
    return [
        {
            "name": "control-plane",
            "url": f"{base['control_plane']}/api/health",
            "critical": True,
            "description": "Flask/Gunicorn Agent API",
        },
        {
            "name": "decision-brain",
            "url": f"{base['decision_brain']}/health",
            "critical": True,
            "description": "FastAPI Policy Engine",
        },
        {
            "name": "observer",
            "url": f"{base['observer']}/health",
            "critical": True,
            "description": "FastAPI Observer Server",
        },
        {
            "name": "observer-api-status",
            "url": f"{base['observer']}/api/status",
            "critical": True,
            "description": "Observer polling status",
        },
        {
            "name": "observer-metrics",
            "url": f"{base['observer']}/api/metrics",
            "critical": False,
            "description": "Prometheus metrics endpoint",
        },
    ]


def _get_redis_check(redis_host: str, redis_port: int) -> Dict[str, Any]:
    """Redis connectivity check (via TCP, not HTTP)."""
    return {
        "name": "redis",
        "host": redis_host,
        "port": redis_port,
        "critical": True,
        "description": "Redis Event Bus",
    }


# ---------------------------------------------------------------------------
# Probe Functions
# ---------------------------------------------------------------------------

def probe_http(name: str, url: str, timeout: float = 5.0) -> Dict[str, Any]:
    """Probe an HTTP endpoint and return a result dict."""
    start = time.time()
    try:
        resp = requests.get(url, timeout=timeout)
        latency_ms = round((time.time() - start) * 1000, 1)
        ok = resp.status_code < 400
        body_snippet = ""
        try:
            body_snippet = json.dumps(resp.json())[:300]
        except Exception:
            body_snippet = resp.text[:300]
        return {
            "name": name,
            "url": url,
            "status": "PASS" if ok else "FAIL",
            "http_status": resp.status_code,
            "latency_ms": latency_ms,
            "detail": body_snippet,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except requests.ConnectionError as exc:
        return {
            "name": name,
            "url": url,
            "status": "FAIL",
            "http_status": None,
            "latency_ms": round((time.time() - start) * 1000, 1),
            "detail": f"ConnectionError: {str(exc)[:200]}",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except requests.Timeout:
        return {
            "name": name,
            "url": url,
            "status": "FAIL",
            "http_status": None,
            "latency_ms": round((time.time() - start) * 1000, 1),
            "detail": "Timeout",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "name": name,
            "url": url,
            "status": "FAIL",
            "http_status": None,
            "latency_ms": round((time.time() - start) * 1000, 1),
            "detail": str(exc)[:200],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


def probe_redis(host: str, port: int) -> Dict[str, Any]:
    """Probe Redis via TCP socket (no redis-py required at runtime)."""
    import socket

    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=3):
            pass
        latency_ms = round((time.time() - start) * 1000, 1)
        return {
            "name": "redis",
            "url": f"tcp://{host}:{port}",
            "status": "PASS",
            "http_status": None,
            "latency_ms": latency_ms,
            "detail": "TCP connection established",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "name": "redis",
            "url": f"tcp://{host}:{port}",
            "status": "FAIL",
            "http_status": None,
            "latency_ms": round((time.time() - start) * 1000, 1),
            "detail": str(exc)[:200],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Main Validation Logic
# ---------------------------------------------------------------------------

def run_validation(env: str, base_urls: Dict[str, str], redis_host: str, redis_port: int) -> Tuple[Dict[str, Any], int]:
    """
    Run all health checks and return (proof_document, exit_code).
    Exit code: 0=all pass, 1=non-critical fail, 2=critical fail.
    """
    print(f"\n{'='*60}")
    print(f"  Pravah Production Health Validation")
    print(f"  Environment : {env.upper()}")
    print(f"  Timestamp   : {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    results = []
    critical_failures = []
    non_critical_failures = []

    # --- Core HTTP checks ---
    core_checks = _get_core_checks(base_urls)
    for chk in core_checks:
        print(f"  Probing [{chk['description']}] -> {chk['url']}")
        result = probe_http(chk["name"], chk["url"])
        result["critical"] = chk["critical"]
        result["description"] = chk["description"]
        results.append(result)
        status_icon = "[PASS]" if result["status"] == "PASS" else "[FAIL]"
        print(f"  {status_icon} {chk['name']} - {result['status']} ({result['latency_ms']}ms)")
        if result["status"] != "PASS":
            if chk["critical"]:
                critical_failures.append(chk["name"])
            else:
                non_critical_failures.append(chk["name"])

    # --- Redis check ---
    print(f"\n  Probing [Redis Event Bus] -> {redis_host}:{redis_port}")
    redis_result = probe_redis(redis_host, redis_port)
    redis_result["critical"] = True
    redis_result["description"] = "Redis Event Bus (TCP)"
    results.append(redis_result)
    status_icon = "[PASS]" if redis_result["status"] == "PASS" else "[FAIL]"
    print(f"  {status_icon} redis - {redis_result['status']} ({redis_result['latency_ms']}ms)")
    if redis_result["status"] != "PASS":
        critical_failures.append("redis")

    # --- Summary ---
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} PASSED  |  {failed} FAILED")
    if critical_failures:
        print(f"  CRITICAL FAILURES: {', '.join(critical_failures)}")
    if non_critical_failures:
        print(f"  NON-CRITICAL FAILURES: {', '.join(non_critical_failures)}")

    # Determine exit code
    if critical_failures:
        verdict = "FAIL"
        exit_code = 2
    elif non_critical_failures:
        verdict = "PARTIAL"
        exit_code = 1
    else:
        verdict = "PASS"
        exit_code = 0

    print(f"  Overall Verdict: {verdict}")
    print(f"{'='*60}\n")

    proof = {
        "schema_version": "1.0",
        "event": "prod_runtime_health_validation",
        "environment": env,
        "platform": "yotta",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "summary": {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "critical_failures": critical_failures,
            "non_critical_failures": non_critical_failures,
        },
        "checks": results,
        "base_urls": base_urls,
    }
    return proof, exit_code


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Pravah Production Health Validation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--env", default="prod", choices=["dev", "staging", "prod"],
                        help="Target environment")
    parser.add_argument("--control-plane", default=None,
                        help="Control Plane base URL (overrides env var)")
    parser.add_argument("--decision-brain", default=None,
                        help="Decision Brain base URL (overrides env var)")
    parser.add_argument("--observer", default=None,
                        help="Observer base URL (overrides env var)")
    parser.add_argument("--redis-host", default=None,
                        help="Redis host (overrides env var)")
    parser.add_argument("--redis-port", type=int, default=None,
                        help="Redis port (overrides env var)")
    parser.add_argument(
        "--output",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "deployment_verification_packet",
            "prod_runtime_health.json",
        ),
        help="Output path for proof JSON",
    )
    args = parser.parse_args()

    # --- Resolve base URLs from args > env vars > defaults ---
    env_defaults = {
        "dev": {
            "control_plane": "http://localhost:7000",
            "decision_brain": "http://localhost:8000",
            "observer": "http://localhost:8600",
            "redis_host": "localhost",
        },
        "staging": {
            "control_plane": os.getenv("STAGING_CONTROL_PLANE_URL", "http://localhost:7000"),
            "decision_brain": os.getenv("STAGING_DECISION_BRAIN_URL", "http://localhost:8000"),
            "observer": os.getenv("STAGING_OBSERVER_URL", "http://localhost:8600"),
            "redis_host": os.getenv("STAGING_REDIS_HOST", "localhost"),
        },
        "prod": {
            "control_plane": os.getenv("PROD_CONTROL_PLANE_URL", "http://localhost:7000"),
            "decision_brain": os.getenv("PROD_DECISION_BRAIN_URL", "http://localhost:8000"),
            "observer": os.getenv("PROD_OBSERVER_URL", "http://localhost:8600"),
            "redis_host": os.getenv("REDIS_HOST", "localhost"),
        },
    }

    defaults = env_defaults[args.env]

    base_urls = {
        "control_plane": args.control_plane or defaults["control_plane"],
        "decision_brain": args.decision_brain or defaults["decision_brain"],
        "observer": args.observer or defaults["observer"],
    }
    redis_host = args.redis_host or defaults["redis_host"]
    redis_port = args.redis_port or int(os.getenv("REDIS_PORT", "6379"))

    proof, exit_code = run_validation(args.env, base_urls, redis_host, redis_port)

    # --- Write proof log ---
    output_path = args.output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(proof, f, indent=2)
    print(f"  Proof written -> {output_path}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
