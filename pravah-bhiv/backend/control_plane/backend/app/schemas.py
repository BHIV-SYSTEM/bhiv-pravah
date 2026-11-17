
"""Pydantic schemas for the stateless RL-style Decision Brain API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional
import urllib.parse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Environment(str, Enum):
    """Supported deployment environments."""

    DEV = "DEV"
    STAGE = "STAGE"
    PROD = "PROD"


class EventType(str, Enum):
    """Supported event classifications used by the decision engine."""

    HIGH_CPU = "HIGH_CPU"
    HIGH_MEMORY = "HIGH_MEMORY"
    LATENCY = "LATENCY"


class HealthResponse(BaseModel):
    """Health response model exposed by the API."""

    status: Literal["healthy"] = "healthy"
    demo_frozen: bool = True
    stateless: bool = True
    success_rate: float = 1.0


class ActionScopeResponse(BaseModel):
    """Environment to action-scope mapping response."""

    DEV: list[str]
    STAGE: list[str]
    PROD: list[str]


class DecisionRequest(BaseModel):
    """Input payload for deterministic decision generation."""

    model_config = ConfigDict(extra="forbid")

    environment: Environment
    event_type: EventType
    cpu: int = Field(ge=0, le=100)
    memory: int = Field(ge=0, le=100)


class DecisionResponse(BaseModel):
    """Decision output returned by the API."""

    decision_id: UUID
    environment: Environment
    selected_action: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime
    version: str


class RecentActivityResponse(BaseModel):
    """Container for last ten in-memory decisions."""

    items: list[DecisionResponse]


class DashboardMetric(BaseModel):
    """Generic metric item used across dashboard sections."""

    label: str
    value: str
    tone: str | None = None


class DashboardHeader(BaseModel):
    """Header metadata for the RL Reality dashboard."""

    title: str
    subtitle: str


class LiveDomainStatus(BaseModel):
    """Live status card payload for each monitored domain."""

    name: str
    domain: str
    url: str
    status: str
    health_score: float
    response_time_ms: int
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    uptime_percent: float
    last_action: str
    errors_24h: int


class LiveDashboardResponse(BaseModel):
    """Top-level response model for the real-time Control Plane Dashboard."""

    generated_at: datetime
    environment: str
    system_health: dict
    ml_intelligence: dict
    recent_decisions: list[DecisionResponse]
    monitored_services: list[LiveDomainStatus]


class DecisionDashboardSummary(BaseModel):
    """Aggregated summary for the RL Decision Brain UI."""

    total_decisions: int
    last_action: str
    success_rate: float
    demo_frozen: bool
    stateless: bool


class LinkIngestRequest(BaseModel):
    """Payload for ingesting a repository or website link for monitoring."""

    model_config = ConfigDict(extra="forbid")

    link: str = Field(
        ...,
        min_length=8,
        max_length=2048,
        description="Fully qualified HTTP or HTTPS URL to repository or website",
    )

    @field_validator("link")
    @classmethod
    def validate_url(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("URL cannot be empty")
        if any(c.isspace() or ord(c) < 32 for c in clean):
            raise ValueError("URL contains illegal whitespace or control characters")
        parsed = urllib.parse.urlsplit(clean)
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError("URL scheme must be http or https")
        if not parsed.netloc:
            raise ValueError("URL must include a valid network location (hostname)")
        try:
            port = parsed.port
            if port is not None and not (1 <= port <= 65535):
                raise ValueError("Port out of range (1-65535)")
        except ValueError as e:
            raise ValueError(f"URL contains invalid port: {e}")
        host = parsed.netloc.split(":")[0]
        if not host or ("." not in host and host != "localhost"):
            raise ValueError("URL must have a valid host (e.g., domain or localhost)")
        return clean


class LinkRemoveRequest(BaseModel):
    """Payload for removing a monitored link."""

    model_config = ConfigDict(extra="forbid")

    link: str = Field(
        ...,
        min_length=8,
        max_length=2048,
        description="Fully qualified HTTP or HTTPS URL to remove",
    )

    @field_validator("link")
    @classmethod
    def validate_url(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("URL cannot be empty")
        if any(c.isspace() or ord(c) < 32 for c in clean):
            raise ValueError("URL contains illegal whitespace or control characters")
        parsed = urllib.parse.urlsplit(clean)
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError("URL scheme must be http or https")
        if not parsed.netloc:
            raise ValueError("URL must include a valid network location (hostname)")
        try:
            port = parsed.port
            if port is not None and not (1 <= port <= 65535):
                raise ValueError("Port out of range (1-65535)")
        except ValueError as e:
            raise ValueError(f"URL contains invalid port: {e}")
        host = parsed.netloc.split(":")[0]
        if not host or ("." not in host and host != "localhost"):
            raise ValueError("URL must have a valid host (e.g., domain or localhost)")
        return clean


class LinkMetadataResponse(BaseModel):
    """Enrichment metadata for an ingested link."""

    model_config = ConfigDict(extra="ignore")

    type: str
    commits: int
    branches: int
    pull_requests: int
    stars: int
    files: int
    contributors: int
    last_commit: str
    test_coverage: float
    ci_status: str
    deployment_frequency: Optional[int] = None
    avg_response_time: int
    error_rate: float
    active_issues: Optional[int] = None
    code_quality_score: Optional[int] = None
    enrichment_status: Literal["enriched", "fallback_heuristic", "offline"]
    enrichment_error: Optional[str] = None


class MonitoredLinkItem(BaseModel):
    """Active monitored link item stored in control plane state."""

    link: str
    name: str
    added_at: str
    status: str
    response_time_ms: int
    uptime_percent: float
    errors_24h: int


class LinkIngestResponse(BaseModel):
    """Formal response returned upon link ingestion."""

    success: bool
    message: str
    ingested_link: Optional[MonitoredLinkItem] = None
    metadata: Optional[LinkMetadataResponse] = None
    enrichment_status: Optional[str] = None
    error: Optional[str] = None


class LinkRemoveResponse(BaseModel):
    """Formal response returned upon link removal."""

    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


class IngestionErrorResponse(BaseModel):
    """Standard structured error response model."""

    success: Literal[False] = False
    error: str
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

