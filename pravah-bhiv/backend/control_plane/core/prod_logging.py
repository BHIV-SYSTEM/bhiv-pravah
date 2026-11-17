"""
Production Logging Configuration

Provides structured, clean logging appropriate for production:
- Minimal debug output
- Structured JSON logging option
- Log levels: CRITICAL, ERROR, WARNING, INFO only (no DEBUG)
- Metric-friendly output
"""

import logging
import json
import sys
from typing import Optional


class ProductionFormatter(logging.Formatter):
    """Clean production formatter without excessive debug info."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for production."""
        # Skip trace/stack info for cleaner output
        if record.levelno <= logging.WARNING:
            return self._format_info_or_lower(record)
        else:
            return self._format_error_or_higher(record)
    
    def _format_info_or_lower(self, record: logging.LogRecord) -> str:
        """Format info/warning level logs."""
        return f"{record.levelname}:{record.name}: {record.getMessage()}"
    
    def _format_error_or_higher(self, record: logging.LogRecord) -> str:
        """Format error/critical level logs with context."""
        msg = f"{record.levelname}:{record.name}: {record.getMessage()}"
        
        if record.exc_info:
            msg += f" [exception: {record.exc_info[0].__name__}]"
        
        return msg


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields from record
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in [
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "message", "pathname", "process", "processName", "relativeCreated",
                    "thread", "threadName", "exc_info", "exc_text", "stack_info"
                ]:
                    if isinstance(value, (str, int, float, bool, type(None))):
                        log_obj[key] = value
        
        return json.dumps(log_obj)


def configure_production_logging(
    level: str = "INFO",
    format_style: str = "text",
    log_file: Optional[str] = None,
) -> None:
    """
    Configure production-grade logging.
    
    Args:
        level: Log level (INFO, WARNING, ERROR, CRITICAL)
        format_style: "text" or "json"
        log_file: Optional file path for log output
    """
    # Ensure level is uppercase and valid
    level_upper = level.upper()
    if level_upper not in ["INFO", "WARNING", "ERROR", "CRITICAL"]:
        level_upper = "INFO"
    
    numeric_level = getattr(logging, level_upper, logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Choose formatter
    if format_style == "json":
        formatter = JsonFormatter()
    else:
        formatter = ProductionFormatter()
    
    # Console handler (always on)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode="a")
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (IOError, OSError) as e:
            root_logger.error(f"Failed to configure file logging to {log_file}: {e}")
    
    # Suppress verbose third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("flask").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with production configuration applied."""
    return logging.getLogger(name)
