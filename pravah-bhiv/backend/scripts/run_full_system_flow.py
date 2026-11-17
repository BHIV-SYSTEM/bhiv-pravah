#!/usr/bin/env python3
"""Run a local end-to-end demo of execution -> Pravah -> observation.

This script keeps the current architecture intact:
- optional service startup
- trigger one runtime event
- observe the Pravah stream passively
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from collections import Counter
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agent_runtime import AgentRuntime
from monitoring.consumer import consume_stream
from pravah_stream.stream import clear_stream, read_stream


def _start_services(services: list[str]) -> None:
    if not services:
        return

    command = ["docker", "compose", "up", "-d", *services]
    print(f"[DEMO] Starting services: {' '.join(services)}")

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        print("[DEMO] Docker is not available, skipping service startup")
    except subprocess.CalledProcessError as exc:
        print(f"[DEMO] Service startup failed: {exc}")


def _watch_pravah_stream(stop_event: threading.Event, poll_interval: float = 0.25) -> None:
    seen = 0

    while not stop_event.is_set():
        events = read_stream()
        while seen < len(events):
            event = events[seen]
            signal_type = event.get("signal_type", "unknown")
            trace_id = event.get("trace_id", "missing")
            execution_id = event.get("execution_id", "missing")
            source = event.get("source", "unknown")
            print(
                f"[PRAVAH WATCH] [{signal_type}] trace_id={trace_id} "
                f"execution_id={execution_id} source={source}"
            )
            print(event)
            seen += 1

        time.sleep(poll_interval)


def _build_demo_event(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "trace_id": args.trace_id,
        "app_id": args.app_id,
        "event_type": args.event_type,
        "cpu_percent": args.cpu_percent,
        "memory_percent": args.memory_percent,
        "error_rate": args.error_rate,
        "workers": args.workers,
    }


def _summarize_stream() -> None:
    events = read_stream()
    counts = Counter(event.get("signal_type", "unknown") for event in events)

    print("[DEMO] Pravah stream summary:")
    print(f"[DEMO] Total events: {len(events)}")
    for signal_type, count in sorted(counts.items()):
        print(f"[DEMO]   {signal_type}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full local integration flow")
    parser.add_argument("--start-services", action="store_true", help="Start selected docker services first")
    parser.add_argument(
        "--services",
        nargs="*",
        default=["redis", "queue-monitor", "health-monitor"],
        help="Docker services to start when --start-services is set",
    )
    parser.add_argument("--env", default="dev", choices=["dev", "stage", "prod"], help="Runtime environment")
    parser.add_argument("--trace-id", default="demo-trace-001", help="Trace id used for the demo event")
    parser.add_argument("--app-id", default="demo-app", help="Application id used for the demo event")
    parser.add_argument("--event-type", default="manual_trigger", help="Event type for the demo trigger")
    parser.add_argument("--cpu-percent", type=float, default=55.0, help="CPU metric for the demo event")
    parser.add_argument("--memory-percent", type=float, default=48.0, help="Memory metric for the demo event")
    parser.add_argument("--error-rate", type=float, default=0.0, help="Error rate for the demo event")
    parser.add_argument("--workers", type=int, default=1, help="Worker count for the demo event")
    parser.add_argument("--post-run-wait", type=float, default=1.0, help="Seconds to wait after execution before final snapshot")
    args = parser.parse_args()

    if args.start_services:
        _start_services(args.services)

    clear_stream()
    print("[DEMO] Pravah stream cleared")

    runtime = AgentRuntime(env=args.env)
    demo_event = _build_demo_event(args)

    stop_event = threading.Event()
    watcher = threading.Thread(target=_watch_pravah_stream, args=(stop_event,), daemon=True)
    watcher.start()

    print("[DEMO] Triggering runtime event")
    print(demo_event)

    try:
        result = runtime.handle_external_event(demo_event)
        print("[DEMO] Runtime result:")
        print(result)
    finally:
        time.sleep(args.post_run_wait)
        stop_event.set()
        watcher.join(timeout=2)

    print("[DEMO] Final passive snapshot:")
    consume_stream()
    _summarize_stream()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
