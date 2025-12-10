"""
Unit tests for Observability components.

Tests cover:
- Structured logging setup
- Request ID tracking
- Performance logging decorator
"""

import pytest
import asyncio
import time


class TestStructuredLogging:
    """Test structured logging setup."""

    def test_logging_setup_json_format(self):
        """Test that logging can be configured for JSON output."""
        from backend.utils.logging import setup_logging
        import structlog

        setup_logging(log_level="INFO", json_format=True)

        logger = structlog.get_logger()
        assert logger is not None

    def test_logging_setup_pretty_format(self):
        """Test that logging can be configured for pretty console output."""
        from backend.utils.logging import setup_logging
        import structlog

        setup_logging(log_level="INFO", json_format=False)

        logger = structlog.get_logger()
        assert logger is not None

    def test_get_logger_with_name(self):
        """Test getting logger with component name."""
        from backend.utils.logging import get_logger

        logger = get_logger("test_component")
        assert logger is not None


class TestRequestContext:
    """Test request ID tracking."""

    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        from backend.utils.request_context import set_request_id, get_request_id

        request_id = set_request_id("test-123")
        assert request_id == "test-123"
        assert get_request_id() == "test-123"

    def test_generate_request_id_if_none(self):
        """Test that request ID is generated if not provided."""
        from backend.utils.request_context import set_request_id, get_request_id

        request_id = set_request_id()
        assert request_id is not None
        assert len(request_id) > 0
        assert get_request_id() == request_id

    def test_clear_request_context(self):
        """Test clearing request context."""
        from backend.utils.request_context import (
            set_request_id,
            get_request_id,
            clear_request_context
        )

        set_request_id("test-123")
        clear_request_context()
        # After clear, should be None
        assert get_request_id() is None


class TestPerformanceLogging:
    """Test performance logging decorator."""

    @pytest.mark.asyncio
    async def test_log_execution_time_async(self):
        """Test that execution time is logged for async functions."""
        from backend.utils.performance import log_execution_time

        @log_execution_time("test_operation")
        async def test_function():
            await asyncio.sleep(0.01)
            return "result"

        result = await test_function()
        assert result == "result"

    def test_log_execution_time_sync(self):
        """Test that execution time is logged for sync functions."""
        from backend.utils.performance import log_execution_time

        @log_execution_time("test_operation")
        def test_function():
            time.sleep(0.01)
            return "result"

        result = test_function()
        assert result == "result"

    @pytest.mark.asyncio
    async def test_log_execution_time_on_error(self):
        """Test that execution time is logged even on error."""
        from backend.utils.performance import log_execution_time

        @log_execution_time("test_operation")
        async def test_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await test_function()
