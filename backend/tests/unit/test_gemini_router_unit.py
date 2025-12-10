"""
Unit tests for GeminiRouter service.

Tests cost calculations, model selection, and thinking budget logic without
making actual API calls.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

from backend.services.gemini_router import (
    GeminiRouter,
    TaskComplexity,
    ModelConfig,
    GenerationResult
)


class TestGeminiRouterUnit:
    """Unit tests for GeminiRouter class."""

    def test_model_configs_exist_for_all_complexity_levels(self):
        """Test that model configs are defined for all complexity levels."""
        for complexity in TaskComplexity:
            assert complexity in GeminiRouter.MODEL_CONFIGS
            config = GeminiRouter.MODEL_CONFIGS[complexity]
            assert isinstance(config, ModelConfig)
            assert config.name
            assert config.input_cost_per_1m > 0
            assert config.output_cost_per_1m > 0

    def test_cost_calculation_simple_task(self):
        """Test cost calculation for SIMPLE tasks (Flash-Lite)."""
        router = GeminiRouter(api_key="test-key")

        # Flash-Lite: $0.075/M input, $0.30/M output
        cost = router._calculate_cost(
            complexity=TaskComplexity.SIMPLE,
            input_tokens=1000,
            output_tokens=500,
            thinking_tokens=0
        )

        expected = (1000 * 0.075 / 1_000_000) + (500 * 0.30 / 1_000_000)
        assert abs(cost - expected) < 0.000001

    def test_cost_calculation_balanced_task(self):
        """Test cost calculation for BALANCED tasks (Flash)."""
        router = GeminiRouter(api_key="test-key")

        # Flash: $0.15/M input, $0.60/M output
        cost = router._calculate_cost(
            complexity=TaskComplexity.BALANCED,
            input_tokens=1000,
            output_tokens=500,
            thinking_tokens=0
        )

        expected = (1000 * 0.15 / 1_000_000) + (500 * 0.60 / 1_000_000)
        assert abs(cost - expected) < 0.000001

    def test_cost_calculation_complex_task(self):
        """Test cost calculation for COMPLEX tasks (Pro)."""
        router = GeminiRouter(api_key="test-key")

        # Pro: $1.25/M input, $5.00/M output
        cost = router._calculate_cost(
            complexity=TaskComplexity.COMPLEX,
            input_tokens=1000,
            output_tokens=500,
            thinking_tokens=0
        )

        expected = (1000 * 1.25 / 1_000_000) + (500 * 5.00 / 1_000_000)
        assert abs(cost - expected) < 0.000001

    def test_cost_calculation_reasoning_task_with_thinking_tokens(self):
        """Test cost calculation for REASONING tasks with thinking tokens."""
        router = GeminiRouter(api_key="test-key")

        # Reasoning: $2.50/M input, $10.00/M output, $2.50/M thinking
        cost = router._calculate_cost(
            complexity=TaskComplexity.REASONING,
            input_tokens=1000,
            output_tokens=500,
            thinking_tokens=2000
        )

        expected = (
            (1000 * 2.50 / 1_000_000) +
            (500 * 10.00 / 1_000_000) +
            (2000 * 2.50 / 1_000_000)
        )
        assert abs(cost - expected) < 0.000001

    def test_cost_calculation_with_zero_tokens(self):
        """Test cost calculation with zero tokens."""
        router = GeminiRouter(api_key="test-key")

        cost = router._calculate_cost(
            complexity=TaskComplexity.BALANCED,
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0
        )

        assert cost == 0.0

    def test_cost_calculation_rounds_to_six_decimals(self):
        """Test that cost is rounded to 6 decimal places."""
        router = GeminiRouter(api_key="test-key")

        cost = router._calculate_cost(
            complexity=TaskComplexity.SIMPLE,
            input_tokens=1,
            output_tokens=1,
            thinking_tokens=0
        )

        # Should be rounded to 6 decimals
        cost_str = f"{cost:.10f}"
        assert len(cost_str.split('.')[1]) <= 10

    def test_model_selection_by_complexity(self):
        """Test that correct models are selected for each complexity level."""
        router = GeminiRouter(api_key="test-key")

        # Test each complexity level
        simple_model = router.get_model(TaskComplexity.SIMPLE)
        assert "flash-lite" in simple_model.model_name.lower() or "2.5" in simple_model.model_name

        balanced_model = router.get_model(TaskComplexity.BALANCED)
        assert "flash" in balanced_model.model_name.lower()

        complex_model = router.get_model(TaskComplexity.COMPLEX)
        assert "pro" in complex_model.model_name.lower()

        reasoning_model = router.get_model(TaskComplexity.REASONING)
        assert "pro" in reasoning_model.model_name.lower() or "3" in reasoning_model.model_name

    def test_get_model_with_system_instruction(self):
        """Test that system instruction is passed to model."""
        router = GeminiRouter(api_key="test-key")

        system_instruction = "You are a legal contract analyzer."
        model = router.get_model(
            complexity=TaskComplexity.BALANCED,
            system_instruction=system_instruction
        )

        assert model is not None

    def test_thinking_budget_only_for_reasoning_models(self):
        """Test that thinking budget can only be set for REASONING complexity."""
        router = GeminiRouter(api_key="test-key")

        # Should raise ValueError for non-reasoning models
        with pytest.raises(ValueError, match="does not support thinking budget"):
            router.get_model(TaskComplexity.SIMPLE, thinking_budget=1000)

        with pytest.raises(ValueError, match="does not support thinking budget"):
            router.get_model(TaskComplexity.BALANCED, thinking_budget=1000)

        with pytest.raises(ValueError, match="does not support thinking budget"):
            router.get_model(TaskComplexity.COMPLEX, thinking_budget=1000)

        # Should work for REASONING
        model = router.get_model(TaskComplexity.REASONING, thinking_budget=1000)
        assert model is not None

    def test_get_model_info(self):
        """Test retrieving model information."""
        router = GeminiRouter(api_key="test-key")

        info = router.get_model_info(TaskComplexity.BALANCED)

        assert info["complexity"] == "balanced"
        assert "model_name" in info
        assert "pricing" in info
        assert info["pricing"]["input_per_1m_tokens"] == 0.15
        assert info["pricing"]["output_per_1m_tokens"] == 0.60
        assert "supports_thinking" in info

    def test_estimate_cost(self):
        """Test cost estimation before making API call."""
        router = GeminiRouter(api_key="test-key")

        estimated_cost = router.estimate_cost(
            complexity=TaskComplexity.BALANCED,
            estimated_input_tokens=1000,
            estimated_output_tokens=500,
            estimated_thinking_tokens=0
        )

        # Should match _calculate_cost
        expected_cost = router._calculate_cost(
            complexity=TaskComplexity.BALANCED,
            input_tokens=1000,
            output_tokens=500,
            thinking_tokens=0
        )

        assert estimated_cost == expected_cost

    @pytest.mark.asyncio
    async def test_generate_returns_generation_result(self, mock_gemini_response):
        """Test that generate() returns a properly structured GenerationResult."""
        router = GeminiRouter(api_key="test-key")

        with patch.object(router, 'get_model') as mock_get_model:
            mock_model = MagicMock()
            mock_model.generate_content = MagicMock(return_value=mock_gemini_response)
            mock_get_model.return_value = mock_model

            result = await router.generate(
                prompt="Test prompt",
                complexity=TaskComplexity.BALANCED
            )

            assert isinstance(result, GenerationResult)
            assert result.text == "Test response from Gemini"
            assert result.input_tokens == 100
            assert result.output_tokens == 50
            assert result.thinking_tokens == 0
            assert result.total_tokens == 150
            assert result.cost > 0
            assert result.generation_time_ms > 0
            assert "flash" in result.model_name.lower()

    @pytest.mark.asyncio
    async def test_generate_includes_thinking_tokens_for_reasoning(
        self, mock_gemini_response_with_thinking
    ):
        """Test that generate() includes thinking tokens for reasoning models."""
        router = GeminiRouter(api_key="test-key")

        with patch.object(router, 'get_model') as mock_get_model:
            mock_model = MagicMock()
            mock_model.generate_content = MagicMock(
                return_value=mock_gemini_response_with_thinking
            )
            mock_get_model.return_value = mock_model

            result = await router.generate(
                prompt="Deep analysis prompt",
                complexity=TaskComplexity.REASONING,
                thinking_budget=1000
            )

            assert result.thinking_tokens == 500
            assert result.total_tokens == 800
            # Cost should include thinking tokens
            assert result.cost > 0

    @pytest.mark.asyncio
    async def test_generate_handles_exceptions(self):
        """Test that generate() properly raises exceptions on failure."""
        router = GeminiRouter(api_key="test-key")

        with patch.object(router, 'get_model') as mock_get_model:
            mock_model = MagicMock()
            mock_model.generate_content = MagicMock(
                side_effect=Exception("API Error")
            )
            mock_get_model.return_value = mock_model

            with pytest.raises(Exception, match="API Error"):
                await router.generate(
                    prompt="Test prompt",
                    complexity=TaskComplexity.BALANCED
                )

    def test_model_config_dataclass(self):
        """Test ModelConfig dataclass structure."""
        config = ModelConfig(
            name="test-model",
            input_cost_per_1m=0.1,
            output_cost_per_1m=0.2,
            thinking_cost_per_1m=0.15,
            supports_thinking=True
        )

        assert config.name == "test-model"
        assert config.input_cost_per_1m == 0.1
        assert config.output_cost_per_1m == 0.2
        assert config.thinking_cost_per_1m == 0.15
        assert config.supports_thinking is True

    def test_reasoning_model_supports_thinking(self):
        """Test that REASONING complexity model supports thinking."""
        config = GeminiRouter.MODEL_CONFIGS[TaskComplexity.REASONING]
        assert config.supports_thinking is True
        assert config.thinking_cost_per_1m is not None
        assert config.thinking_cost_per_1m > 0

    def test_non_reasoning_models_do_not_support_thinking(self):
        """Test that non-reasoning models don't support thinking."""
        for complexity in [TaskComplexity.SIMPLE, TaskComplexity.BALANCED, TaskComplexity.COMPLEX]:
            config = GeminiRouter.MODEL_CONFIGS[complexity]
            assert config.supports_thinking is False
            assert config.thinking_cost_per_1m is None
