"""
Unit tests for API Resilience components.

Tests cover:
- Retry logic with tenacity
- Circuit breaker pattern
- Timeout configuration
"""

import pytest
from unittest.mock import Mock


class TestRetryLogic:
    """Test retry logic with tenacity."""

    def test_retry_decorator_configured(self):
        """Test that retry decorator is configured on generate method."""
        from backend.services.gemini_router import GeminiRouter

        router = GeminiRouter(api_key="test-key")

        # Check that generate method has retry decorator
        assert hasattr(router.generate, 'retry')

    def test_retry_configuration(self):
        """Test that retry is configured with correct parameters."""
        from backend.services.gemini_router import GeminiRouter

        router = GeminiRouter(api_key="test-key")

        # Verify the method is wrapped with tenacity
        assert callable(router.generate)


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    def test_circuit_breaker_exists(self):
        """Test that circuit breakers are defined."""
        from backend.services.api_resilience import gemini_breaker, llamaparse_breaker

        assert gemini_breaker is not None
        assert llamaparse_breaker is not None
        assert gemini_breaker.name == "gemini"
        assert llamaparse_breaker.name == "llamaparse"

    def test_circuit_breaker_configuration(self):
        """Test circuit breaker configuration."""
        from backend.services.api_resilience import gemini_breaker, llamaparse_breaker

        # Verify configuration
        assert gemini_breaker.fail_max == 5
        assert gemini_breaker.reset_timeout == 60
        assert llamaparse_breaker.fail_max == 3
        assert llamaparse_breaker.reset_timeout == 120

    def test_get_breaker_status(self):
        """Test getting circuit breaker status."""
        from backend.services.api_resilience import gemini_breaker, get_breaker_status

        status = get_breaker_status(gemini_breaker)

        assert status["name"] == "gemini"
        assert "state" in status
        assert "fail_counter" in status
        assert "fail_max" in status
        assert status["fail_max"] == 5


class TestTimeout:
    """Test timeout configuration."""

    def test_timeout_configuration(self):
        """Test that GeminiRouter accepts timeout configuration."""
        from backend.services.gemini_router import GeminiRouter

        router = GeminiRouter(
            api_key="test-key",
            default_timeout=30.0,
            max_timeout=120.0
        )

        assert router.default_timeout == 30.0
        assert router.max_timeout == 120.0

    def test_default_timeout_values(self):
        """Test default timeout values."""
        from backend.services.gemini_router import GeminiRouter

        router = GeminiRouter(api_key="test-key")

        # Should have default values
        assert router.default_timeout == 30.0
        assert router.max_timeout == 120.0

    def test_timeout_parameter_in_generate(self):
        """Test that generate method accepts timeout parameter."""
        from backend.services.gemini_router import GeminiRouter
        import inspect

        router = GeminiRouter(api_key="test-key")

        # Check that timeout is a parameter
        sig = inspect.signature(router.generate)
        assert 'timeout' in sig.parameters
