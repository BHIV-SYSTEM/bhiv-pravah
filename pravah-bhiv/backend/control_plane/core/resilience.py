"""
Timeout & Failure Escalation Module

Production-grade resilience for:
- Function timeouts with graceful degradation
- Retry logic with exponential backoff
- Failure tracking and escalation
- Circuit breaker pattern
"""

import functools
import logging
import time
from typing import Any, Callable, Optional, TypeVar, DefaultDict
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class TimeoutError(Exception):
    """Raised when function execution exceeds timeout."""
    pass


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is in open state."""
    pass


def timeout(seconds: int) -> Callable[[F], F]:
    """
    Decorator that enforces a timeout on function execution.
    
    WARNING: On Windows/non-Unix, this is a best-effort timeout only.
    For true timeouts, use asyncio.wait_for or signal-based approaches.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            
            if elapsed > seconds:
                logger.warning(
                    f"Function {func.__name__} exceeded timeout: {elapsed:.2f}s > {seconds}s",
                    extra={"elapsed_seconds": elapsed, "timeout_seconds": seconds}
                )
            
            return result
        
        return wrapper  # type: ignore
    
    return decorator


def retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 0.1,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """
    Decorator that retries function on failure with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Multiplier for delay between retries
        initial_delay: Initial delay in seconds
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        delay = initial_delay * (backoff_factor ** attempt)
                        logger.info(
                            f"Retry {attempt + 1}/{max_attempts} for {func.__name__} "
                            f"after {delay:.2f}s delay due to: {str(e)}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_attempts} retry attempts exhausted for {func.__name__}",
                            extra={"exception": str(e), "function": func.__name__}
                        )
            
            raise last_exception or Exception(f"Failed after {max_attempts} attempts")
        
        return wrapper  # type: ignore
    
    return decorator


class CircuitBreaker:
    """
    Circuit breaker implementation for failure escalation.
    
    States: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        """
        Args:
            name: Circuit breaker name for logging
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting half-open state
            expected_exception: Exception type to track
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.success_count = 0

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function through circuit breaker."""
        if self.state == self.OPEN:
            if self._should_attempt_reset():
                self.state = self.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is OPEN; "
                    f"recovery in {self._time_until_reset():.1f}s"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if recovery timeout has elapsed."""
        if not self.last_failure_time:
            return False
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _time_until_reset(self) -> float:
        """Calculate seconds until recovery attempt."""
        if not self.last_failure_time:
            return 0.0
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return max(0.0, self.recovery_timeout - elapsed)

    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == self.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 2:
                self.state = self.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"Circuit breaker '{self.name}' CLOSED after recovery")
        else:
            self.failure_count = max(0, self.failure_count - 1)

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == self.HALF_OPEN:
            self.state = self.OPEN
            logger.warning(f"Circuit breaker '{self.name}' re-opened after HALF_OPEN failure")
        elif self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logger.error(
                f"Circuit breaker '{self.name}' OPENED after {self.failure_count} failures",
                extra={
                    "circuit_name": self.name,
                    "failure_count": self.failure_count,
                    "threshold": self.failure_threshold
                }
            )


class FailureTracker:
    """Track failures across multiple operations for escalation."""
    
    def __init__(self, max_recent_failures: int = 100):
        self.max_recent_failures = max_recent_failures
        self.failures: DefaultDict[str, list] = defaultdict(list)
    
    def record_failure(self, operation: str, error: Exception) -> None:
        """Record a failure for an operation."""
        timestamp = datetime.utcnow().isoformat()
        self.failures[operation].append({
            "timestamp": timestamp,
            "error": str(error),
            "error_type": type(error).__name__,
        })
        
        # Keep only recent failures
        if len(self.failures[operation]) > self.max_recent_failures:
            self.failures[operation] = self.failures[operation][-self.max_recent_failures:]
        
        logger.error(
            f"Operation '{operation}' failed: {str(error)}",
            extra={
                "operation": operation,
                "error_type": type(error).__name__,
                "failure_count": len(self.failures[operation])
            }
        )
    
    def get_failure_rate(self, operation: str, window_seconds: int = 300) -> float:
        """Get failure rate for operation in recent time window."""
        if operation not in self.failures:
            return 0.0
        
        cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
        recent_failures = [
            f for f in self.failures[operation]
            if datetime.fromisoformat(f["timestamp"]) > cutoff
        ]
        
        return len(recent_failures)
    
    def should_escalate(self, operation: str, escalation_threshold: int = 5) -> bool:
        """Check if failure rate warrants escalation (alert/circuit break)."""
        return self.get_failure_rate(operation, window_seconds=60) >= escalation_threshold
    
    def get_status(self, operation: str) -> dict:
        """Get failure tracking status for operation."""
        failures = self.failures.get(operation, [])
        recent_rate = self.get_failure_rate(operation)
        
        return {
            "operation": operation,
            "total_failures": len(failures),
            "recent_failures_1min": recent_rate,
            "should_escalate": self.should_escalate(operation),
            "last_failure": failures[-1]["timestamp"] if failures else None,
            "last_error": failures[-1]["error"] if failures else None,
        }
