"""Integration package for shared event schema and adapters."""

from .event_schema import EventValidator, StandardEvent

__all__ = ["StandardEvent", "EventValidator"]
