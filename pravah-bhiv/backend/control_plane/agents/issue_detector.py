import pandas as pd
import os
import csv
import datetime
from control_plane.core.redis_event_bus import get_redis_bus
from control_plane.core.base_agent import BaseAgent
from integration.event_schema import StandardEvent

class IssueDetector(BaseAgent):
    """Detects failures based on configurable thresholds from config.py."""

    def __init__(self, log_file, data_file, issue_log_file, config, env='dev'):
        self.data_file = data_file
        self.env = env
        # Demo-safe Redis behavior - no silent mock mode
        from control_plane.core.redis_demo_behavior import get_redis_bus_demo_safe, RedisUnavailableError
        
        try:
            # Try Redis with explicit stub fallback for demo
            self.redis_bus = get_redis_bus_demo_safe(env, use_stub=True)
        except RedisUnavailableError as e:
            print(f"CRITICAL: {e}")
            raise  # Fail deterministically
        self.latency_threshold_ms = config.get("latency_ms", 16000)
        self.low_score_threshold = config.get("low_score_avg", 40)
        self.high_hr_threshold = config.get("high_heart_rate", 120)
        self.low_o2_threshold = config.get("low_oxygen_level", 95)
        
        super().__init__(issue_log_file, "IssueDetector")
        self.logger.info("Agent configured", 
                        latency_threshold=self.latency_threshold_ms,
                        score_threshold=self.low_score_threshold)
    
    def get_log_headers(self) -> list:
        return ["timestamp", "failure_state", "reason"]
    
    def run(self):
        return self.detect_failure_type()

    def _log_issue(self, state, reason):
        """Log detected issue and publish to bus."""
        # Guaranteed event emission - no silent failures
        from control_plane.core.guaranteed_events import emit_crash_event, emit_overload_event
        
        try:
            if state == "deployment_failure":
                emit_crash_event(self.env, "detected", 0, "deployment", error_message=reason)
            elif state == "latency_issue":
                emit_overload_event(self.env, "detected", self.latency_threshold_ms, "system", load_level=self.latency_threshold_ms)
            else:
                # Generic issue detection
                from control_plane.core.guaranteed_events import get_guaranteed_emitter
                from control_plane.core.redis_event_bus import get_redis_bus
                from control_plane.core.metrics_collector import get_metrics_collector
                emitter = get_guaranteed_emitter(self.env, get_redis_bus(self.env), get_metrics_collector(self.env))
                emitter.emit_runtime_event("issue", "detected", 0, failure_type=state, reason=reason)
        except Exception as e:
            print(f"CRITICAL: Event emission failed for {state}: {e}")
            # Re-raise to ensure no silent failures
            raise
        
        self._log_entry({"failure_state": state, "reason": reason})
        self.logger.log_action("issue_detected", state, reason=reason, dataset=self.data_file)
        
        # Publish standardized event
        std_event = StandardEvent.from_issue(self.env, state, reason)
        self.redis_bus.publish("issue.detected", std_event.to_dict())

    def detect_failure_type(self):
        """Check data anomalies first, then deployment issues."""
        try:
            # === 1️⃣ Data-based anomaly detection ===
            if os.path.exists(self.data_file):
                if "student_scores" in self.data_file:
                    df = self._safe_read_csv(self.data_file)
                    if df.empty:
                        return "no_failure", "Data file corrupted or inaccessible"
                    
                    if not df.empty and "score" in df.columns:
                        try:
                            avg_score = pd.to_numeric(df["score"], errors='coerce').mean()
                            if pd.isna(avg_score):
                                return "no_failure", "Invalid score data format"
                            if avg_score < self.low_score_threshold:
                                state, reason = "anomaly_score", f"Low student performance (avg={avg_score:.2f})"
                                self._log_issue(state, reason)
                                return state, reason
                        except Exception as e:
                            return "no_failure", f"Score calculation error: {e}"

                elif "patient_health" in self.data_file:
                    df = self._safe_read_csv(self.data_file)
                    if df.empty:
                        return "no_failure", "Health data file corrupted or inaccessible"
                    
                    if not df.empty:
                        try:
                            last_row = df.iloc[-1]
                            hr = pd.to_numeric(last_row.get("heart_rate", 0), errors='coerce')
                            o2 = pd.to_numeric(last_row.get("oxygen_level", 100), errors='coerce')
                            
                            if pd.isna(hr) or pd.isna(o2):
                                return "no_failure", "Invalid health data format"
                            
                            if hr > self.high_hr_threshold:
                                state, reason = "anomaly_health", f"High heart rate detected ({hr})."
                                self._log_issue(state, reason)
                                return state, reason
                            if o2 < self.low_o2_threshold:
                                state, reason = "anomaly_health", f"Low oxygen detected ({o2})."
                                self._log_issue(state, reason)
                                return state, reason
                        except Exception as e:
                            return "no_failure", f"Health data processing error: {e}"

            # === 2️⃣ Deployment-based issue detection ===
            if hasattr(self, 'log_file') and os.path.exists(self.log_file):
                df = self._safe_read_csv(self.log_file)
                if df.empty:
                    return "no_failure", "Deployment log corrupted or inaccessible"
                
                if not df.empty:
                    try:
                        last = df.iloc[-1]
                        status = str(last.get("status", "")).lower().strip()
                        resp_val = last.get("response_time_ms")
                        rt = pd.to_numeric(resp_val, errors="coerce") if resp_val is not None else None
                        
                        if status == "failure":
                            state, reason = "deployment_failure", "Last deployment attempt failed."
                            self._log_issue(state, reason)
                            return state, reason
                        if pd.notna(rt) and rt > self.latency_threshold_ms:
                            state, reason = "latency_issue", f"High latency detected: {rt:.2f} ms."
                            self._log_issue(state, reason)
                            return state, reason
                    except Exception as e:
                        return "no_failure", f"Deployment log processing error: {e}"

            return "no_failure", "No issues detected."

        except (FileNotFoundError, pd.errors.EmptyDataError):
            return "no_failure", "Log or data file not found or empty."
        except PermissionError as e:
            return "no_failure", f"File access permission denied: {e}"
        except Exception as e:
            return "no_failure", f"Unexpected error in IssueDetector: {e}"
