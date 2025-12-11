"""
Validation utilities using Literal types.

Provides validation functions that work with FastAPI's Literal types
for compile-time and runtime type checking.
"""

from typing import Literal, Optional


# Type aliases for Literal types
RiskLevel = Literal["low", "medium", "high"]
SortByField = Literal["upload_date", "risk_score", "filename"]
SortOrder = Literal["asc", "desc"]


def validate_risk_level(value: Optional[str]) -> Optional[RiskLevel]:
    """
    Validate and return risk level.

    Args:
        value: Risk level string or None

    Returns:
        Validated risk level or None

    Note:
        This function is mainly for documentation/testing.
        In FastAPI endpoints, use Literal types directly in signatures.
    """
    if value is None:
        return None
    if value in ("low", "medium", "high"):
        return value  # type: ignore
    raise ValueError(f"Invalid risk_level: {value}")


def validate_sort_by(value: str) -> SortByField:
    """
    Validate and return sort_by field.

    Args:
        value: Sort field string

    Returns:
        Validated sort_by field

    Note:
        This function is mainly for documentation/testing.
        In FastAPI endpoints, use Literal types directly in signatures.
    """
    if value in ("upload_date", "risk_score", "filename"):
        return value  # type: ignore
    raise ValueError(f"Invalid sort_by: {value}")


def validate_sort_order(value: str) -> SortOrder:
    """
    Validate and return sort order.

    Args:
        value: Sort order string

    Returns:
        Validated sort order

    Note:
        This function is mainly for documentation/testing.
        In FastAPI endpoints, use Literal types directly in signatures.
    """
    if value in ("asc", "desc"):
        return value  # type: ignore
    raise ValueError(f"Invalid sort_order: {value}")
