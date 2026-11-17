import logging
import os
from datetime import datetime

class AgentLogger:
    """Standardized logging for all agents."""
    
    def __init__(self, agent_name: str, log_level: str = "INFO"):
        self.agent_name = agent_name
        self.logger = logging.getLogger(f"agent.{agent_name}")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup console and file handlers with consistent formatting."""
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler(os.path.join("logs", f"{self.agent_name}_debug.log"))
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    def info(self, message: str, **kwargs):
        """Log info message with optional context."""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with optional context."""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with optional context."""
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with optional context."""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log message with optional context data."""
        if kwargs:
            context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
            message = f"{message} | {context}"
        self.logger.log(level, message)
    
    def log_action(self, action: str, status: str, **kwargs):
        """Standardized action logging."""
        self.info(f"Action: {action} | Status: {status}", **kwargs)
    
    def log_error(self, error: Exception, context: str = ""):
        """Standardized error logging."""
        self.error(f"Error in {context}: {str(error)}", error_type=type(error).__name__)