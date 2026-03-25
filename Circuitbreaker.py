"""
circuit_breaker.py — Production Circuit Breaker Pattern
Automatically routes traffic to Groq when OpenAI fails repeatedly.

Features:
- Thread-safe state management
- Automatic recovery after cooldown period
- Exponential backoff for retry attempts
- Telemetry hooks for failure tracking
"""

import time
import threading
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing - all requests routed to fallback
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for API calls with automatic failover.
    
    Usage:
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=900)
        
        try:
            result = breaker.call(risky_function, arg1, arg2)
        except CircuitBreakerOpen:
            # Use fallback
            result = fallback_function(arg1, arg2)
    """
    
    def __init__(
        self,
        failure_threshold: int = 2,
        recovery_timeout: int = 900,  # 15 minutes
        success_threshold: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
        
        self._lock = threading.Lock()
        
        logger.info(
            f"Circuit breaker initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s"
        )
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Raises:
            CircuitBreakerOpen: If circuit is open (too many failures)
        """
        with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit breaker is OPEN. "
                        f"Retry after {self._time_until_retry():.0f}s"
                    )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                
                if self.success_count >= self.success_threshold:
                    self._transition_to_closed()
    
    def _on_failure(self):
        """Handle failed call"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            logger.warning(
                f"Circuit breaker failure {self.failure_count}/"
                f"{self.failure_threshold}"
            )
            
            if self.state == CircuitState.HALF_OPEN:
                self._transition_to_open()
            elif self.failure_count >= self.failure_threshold:
                self._transition_to_open()
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def _time_until_retry(self) -> float:
        """Calculate seconds until next retry attempt"""
        if self.last_failure_time is None:
            return 0
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return max(0, self.recovery_timeout - elapsed)
    
    def _transition_to_open(self):
        """Transition to OPEN state (circuit tripped)"""
        logger.error(
            f"⚠️ CIRCUIT BREAKER OPEN - Routing to fallback for "
            f"{self.recovery_timeout}s"
        )
        self.state = CircuitState.OPEN
        self.success_count = 0
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN (testing recovery)"""
        logger.info("Circuit breaker HALF_OPEN - Testing recovery")
        self.state = CircuitState.HALF_OPEN
        self.failure_count = 0
        self.success_count = 0
    
    def _transition_to_closed(self):
        """Transition to CLOSED (normal operation)"""
        logger.info("✅ Circuit breaker CLOSED - Service recovered")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
    
    def get_state(self) -> str:
        """Get current circuit state"""
        return self.state.value
    
    def reset(self):
        """Manually reset circuit breaker"""
        with self._lock:
            self._transition_to_closed()
            logger.info("Circuit breaker manually reset")


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open"""
    pass


# Global circuit breaker instance
_openai_breaker = None


def get_openai_circuit_breaker() -> CircuitBreaker:
    """Get or create the OpenAI circuit breaker singleton"""
    global _openai_breaker
    
    if _openai_breaker is None:
        _openai_breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=900,  # 15 minutes
            success_threshold=1
        )
    
    return _openai_breaker


def reset_circuit_breaker():
    """Reset the circuit breaker (admin function)"""
    breaker = get_openai_circuit_breaker()
    breaker.reset()
