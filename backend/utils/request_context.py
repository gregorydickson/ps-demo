"""
Request context management for tracking requests across the application.
"""

import uuid
from contextvars import ContextVar
from typing import Optional
import structlog

# Context variable for request ID
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID."""
    return request_id_var.get()


def set_request_id(request_id: str = None) -> str:
    """
    Set the request ID for the current context.

    Args:
        request_id: Optional ID to use. If None, generates a UUID.

    Returns:
        The request ID that was set.
    """
    if request_id is None:
        request_id = str(uuid.uuid4())

    request_id_var.set(request_id)

    # Also bind to structlog context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    return request_id


def clear_request_context():
    """Clear the request context at end of request."""
    request_id_var.set(None)
    structlog.contextvars.clear_contextvars()
