import os
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import psutil

from .feature_schema import TelemetryFeatureVector
from control_plane.core.env_config import EnvironmentConfig

class MLFeatureExtractor:
    """
    Extracts ML-ready features from raw telemetry data.
    These features support Anomaly Detection, Predictive Maintenance, and Capacity Forecasting.
    """

    def __init__(self, env='prod'):
        self.env = env
        self.env_config = EnvironmentConfig(env)
        self.metrics_dir = self.env_config.get_log_path("metrics")

    def _read_csv_safe(self, filename: str) -> pd.DataFrame:
        """Safely read a CSV file into a Pandas DataFrame."""
        file_path = os.path.join(self.metrics_dir, filename)
        if not os.path.exists(file_path):
            return pd.DataFrame()
        try:
            return pd.read_csv(file_path)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            return pd.DataFrame()

    def extract_features(self) -> TelemetryFeatureVector:
        """
        Extracts 10 dimensions of telemetry features and returns a strongly-typed TelemetryFeatureVector.
        """
        # Load Raw Data
        df_latency = self._read_csv_safe("latency_metrics.csv")
        df_error = self._read_csv_safe("error_metrics.csv")
        df_queue = self._read_csv_safe("queue_depth.csv")
        df_deploy = self._read_csv_safe("deploy_success_rate.csv")
        df_cert = self._read_csv_safe("certification_metrics.csv")
        df_val = self._read_csv_safe("validation_scores.csv")
        df_retry = self._read_csv_safe("retry_metrics.csv")

        # 1. Latency Trends (EMA of p50, p95, p99)
        latency_p50 = 0.0
        latency_p95 = 0.0
        latency_p99 = 0.0
        if not df_latency.empty and 'latency_ms' in df_latency.columns:
            recent_latencies = df_latency.tail(100)['latency_ms']
            if len(recent_latencies) > 0:
                latency_p50 = float(np.percentile(recent_latencies, 50))
                latency_p95 = float(np.percentile(recent_latencies, 95))
                latency_p99 = float(np.percentile(recent_latencies, 99))

        # 2. Failure Frequency & Error Velocity
        failure_rate_15m = 0.0
        error_velocity = 0.0
        if not df_error.empty and 'timestamp' in df_error.columns:
            df_error['timestamp'] = pd.to_datetime(df_error['timestamp'], errors='coerce')
            now = pd.Timestamp.now()
            recent_15m = df_error[df_error['timestamp'] >= (now - pd.Timedelta(minutes=15))]
            recent_30m = df_error[df_error['timestamp'] >= (now - pd.Timedelta(minutes=30))]

            count_15m = len(recent_15m)
            count_prev_15m = len(recent_30m) - count_15m
            failure_rate_15m = count_15m / 900.0

            rate_prev = count_prev_15m / 900.0
            error_velocity = (failure_rate_15m - rate_prev) / 900.0

        # 3. Retry Patterns (Real data from retry_metrics.csv)
        avg_retries_per_event = 0.0
        max_retry_chain = 0
        if not df_retry.empty and 'retry_count' in df_retry.columns:
            recent_retries = df_retry.tail(50)
            avg_retries_per_event = float(recent_retries['retry_count'].mean())
            max_retry_chain = int(recent_retries['retry_count'].max())

        # 4. Certification Success Rate (Real data from certification_metrics.csv)
        cert_success = 0.0
        if not df_cert.empty and 'success_rate_percent' in df_cert.columns:
            recent_success = df_cert.tail(10)['success_rate_percent'].mean()
            if not np.isnan(recent_success):
                cert_success = float(recent_success) / 100.0

        # 5. Validation Score Distributions (Real data from validation_scores.csv)
        val_mean = 0.0
        val_variance = 0.0
        if not df_val.empty and 'score' in df_val.columns:
            recent_scores = df_val.tail(50)['score']
            if not recent_scores.empty:
                val_mean = float(recent_scores.mean())
                val_variance = float(recent_scores.var())
                if np.isnan(val_variance):
                    val_variance = 0.0

        # 6. Execution Bottlenecks (Find component with max latency)
        bottleneck_comp = 0
        bottleneck_lat = 0.0
        if not df_latency.empty and 'service_name' in df_latency.columns:
            recent_window = df_latency.tail(50)
            if not recent_window.empty:
                max_row = recent_window.loc[recent_window['latency_ms'].idxmax()]
                bottleneck_lat = float(max_row['latency_ms'])
                # Simple hash encode for component
                bottleneck_comp = hash(str(max_row['service_name'])) % 100

        # 7. Anomaly Indicators (Z-Score of current vs historical)
        queue_zscore = 0.0
        if not df_queue.empty and 'depth' in df_queue.columns:
            depths = df_queue['depth']
            if len(depths) > 10:
                mean_q = depths.mean()
                std_q = depths.std()
                current_q = depths.iloc[-1]
                if std_q > 0:
                    queue_zscore = float((current_q - mean_q) / std_q)

        latency_zscore = 0.0
        if not df_latency.empty and 'latency_ms' in df_latency.columns:
            lats = df_latency['latency_ms']
            if len(lats) > 10:
                mean_l = lats.mean()
                std_l = lats.std()
                current_l = lats.iloc[-1]
                if std_l > 0:
                    latency_zscore = float((current_l - mean_l) / std_l)

        # 8. Dependency Failures
        correlated_failure_index = 0.0
        df_deps = self._read_csv_safe("dependency_failures.csv")
        if not df_deps.empty and 'failure_index' in df_deps.columns:
            recent_deps = df_deps.tail(10)
            correlated_failure_index = float(recent_deps['failure_index'].mean())

        # 9. Throughput (derived from latency events as proxy for requests)
        throughput_1m = 0.0
        throughput_5m = 0.0
        if not df_latency.empty and 'timestamp' in df_latency.columns:
            df_latency['timestamp'] = pd.to_datetime(df_latency['timestamp'], errors='coerce')
            now = pd.Timestamp.now()
            count_1m = len(df_latency[df_latency['timestamp'] >= (now - pd.Timedelta(minutes=1))])
            count_5m = len(df_latency[df_latency['timestamp'] >= (now - pd.Timedelta(minutes=5))])
            throughput_1m = count_1m / 60.0
            throughput_5m = count_5m / 300.0

        # 10. Resource Utilization
        try:
            try:
                from control_plane.backend.app.main import get_debounced_system_metrics
            except ImportError:
                from backend.app.main import get_debounced_system_metrics
            cpu_val, mem_val = get_debounced_system_metrics()
            cpu_pct = float(cpu_val) if cpu_val is not None else 0.0
            mem_pct = float(mem_val) if mem_val is not None else 0.0
        except Exception:
            cpu_pct = 0.0
            try:
                mem_pct = float(psutil.virtual_memory().percent)
            except Exception:
                mem_pct = 0.0

        return TelemetryFeatureVector(
            latency_ema_p50=round(latency_p50, 2),
            latency_ema_p95=round(latency_p95, 2),
            latency_ema_p99=round(latency_p99, 2),
            failure_rate_15m=round(failure_rate_15m, 2),
            error_velocity=round(error_velocity, 2),
            avg_retries_per_event=round(avg_retries_per_event, 2),
            max_retry_chain=max_retry_chain,
            cert_success_rate_rolling=round(cert_success, 2),
            validation_score_mean=round(val_mean, 2),
            validation_score_variance=round(val_variance, 2),
            bottleneck_component_encoded=bottleneck_comp,
            bottleneck_latency_ms=round(bottleneck_lat, 2),
            queue_depth_zscore=round(queue_zscore, 2),
            latency_zscore=round(latency_zscore, 2),
            correlated_failure_index=round(correlated_failure_index, 2),
            throughput_rps_1m=round(throughput_1m, 2),
            throughput_rps_5m=round(throughput_5m, 2),
            cpu_utilization_pct=round(cpu_pct, 2),
            memory_utilization_pct=round(mem_pct, 2)
        )

# Ensure the module exports the extractor
__all__ = ['MLFeatureExtractor', 'TelemetryFeatureVector']
