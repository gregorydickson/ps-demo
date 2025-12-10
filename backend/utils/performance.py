"""
Performance monitoring utilities.
"""

import time
import asyncio
from functools import wraps
from typing import Callable
import structlog

logger = structlog.get_logger()


def log_execution_time(operation_name: str = None):
    """
    Decorator to log execution time of functions.

    Usage:
        @log_execution_time("process_document")
        async def process_document(...):
            ...
    """
    def decorator(func: Callable):
        name = operation_name or func.__name__

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    "operation_complete",
                    operation=name,
                    duration_ms=round(duration_ms, 2),
                    status="success"
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    "operation_failed",
                    operation=name,
                    duration_ms=round(duration_ms, 2),
                    status="error",
                    error=str(e)
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.info(
                    "operation_complete",
                    operation=name,
                    duration_ms=round(duration_ms, 2),
                    status="success"
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    "operation_failed",
                    operation=name,
                    duration_ms=round(duration_ms, 2),
                    status="error",
                    error=str(e)
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
