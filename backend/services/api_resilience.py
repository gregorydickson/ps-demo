"""
API resilience utilities including circuit breaker pattern.

Provides protection against cascading failures when external services
(like Gemini API or LlamaParse) are experiencing issues.
"""

from pybreaker import CircuitBreaker, CircuitBreakerError
import structlog
from functools import wraps
from typing import Callable

logger = structlog.get_logger()


class ServiceUnavailableError(Exception):
    """Raised when a service is unavailable due to circuit breaker."""
    pass


# Circuit breakers for external services
gemini_breaker = CircuitBreaker(
    fail_max=5,           # Open after 5 failures
    reset_timeout=60,     # Try again after 60 seconds
    name="gemini",
    listeners=[
        lambda cb, old_state, new_state: logger.warning(
            "circuit_breaker_state_change",
            breaker=cb.name,
            old_state=str(old_state),
            new_state=str(new_state)
        )
    ]
)

llamaparse_breaker = CircuitBreaker(
    fail_max=3,
    reset_timeout=120,
    name="llamaparse",
    listeners=[
        lambda cb, old_state, new_state: logger.warning(
            "circuit_breaker_state_change",
            breaker=cb.name,
            old_state=str(old_state),
            new_state=str(new_state)
        )
    ]
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
