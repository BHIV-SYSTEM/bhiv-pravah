from typing import List, Dict, Any
from pydantic import BaseModel, Field

class TelemetryFeatureVector(BaseModel):
    """
    ML-ready feature vector containing pre-processed telemetry dimensions.
    This vector is designed to be fed directly into anomaly detection or predictive maintenance models.
    """
    # 1. Latency Trends
    latency_ema_p50: float = Field(0.0, description="Exponential moving average of p50 latency")
    latency_ema_p95: float = Field(0.0, description="Exponential moving average of p95 latency")
    latency_ema_p99: float = Field(0.0, description="Exponential moving average of p99 latency")
    
    # 2. Failure Frequency
    failure_rate_15m: float = Field(0.0, description="Failure rate in the last 15 minutes")
    error_velocity: float = Field(0.0, description="Rate of change of errors (errors/sec^2)")
    
    # 3. Retry Patterns
    avg_retries_per_event: float = Field(0.0, description="Average number of retries required per event")
    max_retry_chain: int = Field(0, description="Maximum retry chain depth observed")
    
    # 4. Certification Success Rate
    cert_success_rate_rolling: float = Field(1.0, description="Rolling success rate of MasterDB certifications")
    
    # 5. Validation Score Distributions
    validation_score_mean: float = Field(1.0, description="Mean data validation score")
    validation_score_variance: float = Field(0.0, description="Variance in data validation scores")
    
    # 6. Execution Bottlenecks
    bottleneck_component_encoded: int = Field(0, description="Integer encoded component causing highest latency")
    bottleneck_latency_ms: float = Field(0.0, description="Latency of the bottleneck component")
    
    # 7. Anomaly Indicators
    queue_depth_zscore: float = Field(0.0, description="Z-score of queue depth compared to historical mean")
    latency_zscore: float = Field(0.0, description="Z-score of latency compared to historical mean")
    
    # 8. Dependency Failures
    correlated_failure_index: float = Field(0.0, description="Index measuring cascading failure across dependencies")
    
    # 9. Throughput
    throughput_rps_1m: float = Field(0.0, description="Requests per second over the last minute")
    throughput_rps_5m: float = Field(0.0, description="Requests per second over the last 5 minutes")
    
    # 10. Resource Utilization
    cpu_utilization_pct: float = Field(0.0, description="Current CPU utilization percentage")
    memory_utilization_pct: float = Field(0.0, description="Current Memory utilization percentage")
    
    class Config:
        json_schema_extra = {
            "example": {
                "latency_ema_p50": 45.2,
                "latency_ema_p95": 120.5,
                "latency_ema_p99": 350.1,
                "failure_rate_15m": 0.02,
                "error_velocity": 0.001,
                "avg_retries_per_event": 0.1,
                "max_retry_chain": 2,
                "cert_success_rate_rolling": 0.98,
                "validation_score_mean": 0.95,
                "validation_score_variance": 0.002,
                "bottleneck_component_encoded": 4,
                "bottleneck_latency_ms": 115.0,
                "queue_depth_zscore": 0.5,
                "latency_zscore": 1.2,
                "correlated_failure_index": 0.0,
                "throughput_rps_1m": 45.3,
                "throughput_rps_5m": 42.1,
                "cpu_utilization_pct": 35.5,
                "memory_utilization_pct": 60.2
            }
        }
