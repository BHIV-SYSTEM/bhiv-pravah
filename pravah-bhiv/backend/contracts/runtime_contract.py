from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime


class RuntimeTelemetry(BaseModel):
    timestamp: datetime
    service_name: str
    cpu_percent: float
    memory_percent: float
    response_time_ms: float
    error_rate: float


class RuntimeState(BaseModel):
    telemetry: RuntimeTelemetry
    metadata: Dict[str, Any] = {}


class DecisionOutput(BaseModel):
    action: str
    target_service: str
    confidence: float
    reason: str