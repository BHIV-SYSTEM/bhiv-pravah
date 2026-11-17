#!/usr/bin/env python3
"""Pravah Security - Trace Consumption Registry for Single-Use Trace Protection"""
import logging
import os
import json
import time
from typing import Set

logger = logging.getLogger("security.trace_consumption")

class TraceConsumptionRegistry:
    """Stores consumed trace IDs to prevent duplicate actions using the same trace context."""
    
    def __init__(self, store_file: str = 'security/trace_consumption.json', ttl: int = 86400):
        # Resolve store file path relative to multi-agent-control-plane-main root if needed,
        # but absolute/relative workspace paths are fine.
        self.store_file = store_file
        self.ttl = ttl  # Trace retention in seconds (default 24 hours)
        self.consumed_traces: Set[str] = set()
        self.timestamps = {}
        self._load_store()
    
    def _load_store(self):
        """Load consumed traces from disk. Fails closed on corruption or read errors."""
        if os.path.exists(self.store_file):
            try:
                with open(self.store_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("Store root must be a JSON object")
                    traces = data.get('traces')
                    timestamps = data.get('timestamps')
                    if not isinstance(traces, list) or not isinstance(timestamps, dict):
                        raise ValueError("Store missing valid 'traces' list or 'timestamps' dict")
                    self.consumed_traces = set(traces)
                    self.timestamps = dict(timestamps)
                    self._cleanup_expired()
            except Exception as exc:
                logger.critical("Trace consumption store corrupted or unreadable at '%s': %s", self.store_file, exc)
                raise RuntimeError(f"Trace consumption store unreadable or corrupted: {exc}") from exc
    
    def _save_store(self):
        """Save consumed traces to disk atomically. Fails closed on write errors."""
        store_dir = os.path.dirname(self.store_file)
        if store_dir:
            os.makedirs(store_dir, exist_ok=True)
        temp_file = f"{self.store_file}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'traces': list(self.consumed_traces),
                    'timestamps': self.timestamps
                }, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, self.store_file)
        except Exception as exc:
            logger.critical("Failed to persist trace consumption store to '%s': %s", self.store_file, exc)
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            raise RuntimeError(f"Trace consumption persistence failed: {exc}") from exc
    
    def _cleanup_expired(self):
        """Remove trace IDs older than TTL."""
        current_time = time.time()
        expired = [
            trace_id for trace_id, timestamp in self.timestamps.items()
            if current_time - timestamp > self.ttl
        ]
        for trace_id in expired:
            self.consumed_traces.discard(trace_id)
            self.timestamps.pop(trace_id, None)
    
    def is_consumed(self, trace_id: str) -> bool:
        """Check if a trace ID has already been consumed."""
        if not trace_id:
            return True
        self._cleanup_expired()
        return trace_id in self.consumed_traces
    
    def consume(self, trace_id: str) -> bool:
        """
        Record trace ID consumption.
        Returns True if successfully consumed (first time), False if already consumed.
        Rolls back complete in-memory state and raises RuntimeError if persistence fails.
        """
        if not trace_id:
            return False
        
        # Complete pre-operation snapshot to ensure exact rollback on save failure
        pre_traces = set(self.consumed_traces)
        pre_timestamps = dict(self.timestamps)

        self._cleanup_expired()
        if trace_id in self.consumed_traces:
            return False
        
        self.consumed_traces.add(trace_id)
        self.timestamps[trace_id] = time.time()
        try:
            self._save_store()
        except Exception:
            self.consumed_traces = pre_traces
            self.timestamps = pre_timestamps
            raise
        return True

# Global registry instance
_registry = None
_default_store_file = None

def get_trace_registry() -> TraceConsumptionRegistry:
    """Get or create global trace consumption registry."""
    global _registry
    if _registry is None:
        if _default_store_file is not None:
            _registry = TraceConsumptionRegistry(store_file=_default_store_file)
        else:
            _registry = TraceConsumptionRegistry()
    return _registry

def is_trace_consumed(trace_id: str) -> bool:
    """Check if a trace has already been consumed."""
    return get_trace_registry().is_consumed(trace_id)

def consume_trace(trace_id: str) -> bool:
    """Record trace ID as consumed."""
    return get_trace_registry().consume(trace_id)

def reset_trace_registry(store_file: str | None = None) -> None:
    """Reset global trace registry singleton (for testing)."""
    global _registry, _default_store_file
    _registry = None
    _default_store_file = store_file

