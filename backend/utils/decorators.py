"""
Decorators for FastAPI endpoints.

Provides reusable decorators for common patterns like error handling.
"""

import logging
from functools import wraps
from typing import Callable, TypeVar

from fastapi import HTTPException

logger = logging.getLogger(__name__)

T = TypeVar('T')


def handle_endpoint_errors(error_type: str) -> Callable:
    """
    Decorator for consistent endpoint error handling.

    Wraps async endpoint functions to:
    - Re-raise HTTPException unchanged
    - Convert other exceptions to 500 HTTPException with structured detail
    - Log errors with function name and traceback

    Args:
        error_type: Error type string for the response detail

    Returns:
        Decorated async function

    Example:
        @app.get("/api/items/{id}")
        @handle_endpoint_errors("RetrievalError")
        async def get_item(id: str):
            return await fetch_item(id)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Re-raise HTTP exceptions unchanged
                raise
            except Exception as e:
                # Log and convert to HTTPException
                logger.error(
                    f"Error in {func.__name__}: {e}",
                    exc_info=True
                )
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": error_type,
                        "message": str(e)
                    }
                )
        return wrapper
    return decorator
