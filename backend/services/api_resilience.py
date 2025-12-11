"""
API resilience utilities including circuit breaker pattern.

Provides protection against cascading failures when external services
(like Gemini API or LlamaParse) are experiencing issues.
"""

from pybreaker import CircuitBreaker, CircuitBreakerError, CircuitBreakerListener
import structlog
from functools import wraps
from typing import Callable

logger = structlog.get_logger()


class ServiceUnavailableError(Exception):
    """Raised when a service is unavailable due to circuit breaker."""
    pass


class LoggingCircuitBreakerListener(CircuitBreakerListener):
    """Circuit breaker listener that logs state changes."""

    def state_change(self, cb, old_state, new_state):
        """Called when circuit breaker changes state."""
        logger.warning(
            "circuit_breaker_state_change",
            breaker=cb.name,
            old_state=str(old_state),
            new_state=str(new_state)
        )

    def failure(self, cb, exc):
        """Called when a function wrapped by the circuit breaker fails."""
        logger.debug(
            "circuit_breaker_failure",
            breaker=cb.name,
            error=str(exc),
            fail_counter=cb.fail_counter
        )

    def success(self, cb):
        """Called when a function wrapped by the circuit breaker succeeds."""
        pass  # Don't log successes to avoid noise


# Circuit breakers for external services
gemini_breaker = CircuitBreaker(
    fail_max=5,           # Open after 5 failures
    reset_timeout=60,     # Try again after 60 seconds
    name="gemini",
    listeners=[LoggingCircuitBreakerListener()]
)

llamaparse_breaker = CircuitBreaker(
    fail_max=3,
    reset_timeout=120,
    name="llamaparse",
    listeners=[LoggingCircuitBreakerListener()]
)

falkordb_breaker = CircuitBreaker(
    fail_max=5,           # Open after 5 failures
    reset_timeout=30,     # Try again after 30 seconds (faster recovery for local DB)
    name="falkordb",
    listeners=[LoggingCircuitBreakerListener()]
)


def with_circuit_breaker(breaker: CircuitBreaker):
    """
    Decorator to wrap async functions with circuit breaker.

    Usage:
        @with_circuit_breaker(gemini_breaker)
        async def call_gemini_api(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # pybreaker doesn't natively support async, so we wrap it
                def sync_call():
                    # This will be called by the circuit breaker
                    # We return the coroutine to be awaited
                    return func(*args, **kwargs)

                # Call through circuit breaker
                result_coro = breaker.call(sync_call)

                # Await the coroutine
                result = await result_coro
                return result

            except CircuitBreakerError:
                logger.error(
                    "circuit_breaker_open",
                    breaker=breaker.name,
                    message="Service unavailable, circuit breaker open"
                )
                raise ServiceUnavailableError(
                    f"{breaker.name} service is temporarily unavailable"
                )
        return wrapper
    return decorator


def get_breaker_status(breaker: CircuitBreaker) -> dict:
    """
    Get the current status of a circuit breaker.

    Returns:
        Dict with state, fail_count, and other stats
    """
    return {
        "name": breaker.name,
        "state": str(breaker.current_state),
        "fail_counter": breaker.fail_counter,
        "fail_max": breaker.fail_max,
        "reset_timeout": breaker.reset_timeout,
    }
