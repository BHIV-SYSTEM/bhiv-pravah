import os
import csv
import datetime
from control_plane.core.logger import AgentLogger

class UptimeMonitor:
    """Maintains a synthetic uptime/downtime timeline."""
    def __init__(self, timeline_file):
        self.timeline_file = os.path.normpath(timeline_file)
        self.logger = AgentLogger("UptimeMonitor")
        self.last_status = self._get_initial_status()
        if self.last_status is None:
            self.update_status("UP", "Initial status check")
        self.logger.info("Agent monitoring started", initial_status=self.last_status or "UP")

    def _get_initial_status(self):
        """Reads the last known status from the timeline file."""
        # Ensure the directory for the log file exists.
        os.makedirs(os.path.dirname(self.timeline_file), exist_ok=True)

        if not os.path.exists(self.timeline_file):
            with open(self.timeline_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'status', 'event'])
            return None
        else:
            try:
                with open(self.timeline_file, 'r', newline='') as f:
                    # Read all rows and get the last one's status
                    rows = list(csv.reader(f))
                    # Handle empty file or header-only file
                    if len(rows) > 1:
                        return rows[-1][1]
                    else:
                        return None
            except (IOError, IndexError):
                return None

    def update_status(self, new_status, event_description):
        """Logs a status change to the timeline if the status is different."""
        if new_status != self.last_status:
            # Guaranteed event emission - no silent failures
            from control_plane.core.guaranteed_events import emit_restart_event
            
            try:
                if new_status == "UP":
                    emit_restart_event('dev', "success", 0, "uptime_monitor")
                else:
                    emit_restart_event('dev', "failure", 0, "uptime_monitor")
            except Exception as e:
                print(f"CRITICAL: Event emission failed for status change: {e}")
                # Re-raise to ensure no silent failures
                raise
            
            timestamp = datetime.datetime.now().isoformat()
            with open(self.timeline_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, new_status, event_description])
            self.logger.log_action("status_change", new_status, 
                                 previous_status=self.last_status,
                                 reason=event_description)
            self.last_status = new_status
            
            # Use Redis stability manager for event publishing
            try:
                from control_plane.core.redis_stability import RedisStabilityManager
                redis_bus = RedisStabilityManager.get_redis_connection('dev', allow_stub=True)
                redis_bus.publish(f"system.{new_status.lower()}", {"reason": event_description})
            except Exception as e:
                print(f"WARNING: Could not publish status event: {e}")
        else:
            self.logger.debug("Status unchanged", status=self.last_status)
