"""
Gemini Router Service - Multi-model cost optimization for Google Gemini API.

This service routes requests to the appropriate Gemini model based on task complexity,
tracks token usage and costs, and provides a unified interface for generation.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass

import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse


logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Task complexity levels for model routing."""
    SIMPLE = "simple"        # Quick extractions, simple queries
    BALANCED = "balanced"    # Standard contract analysis
    COMPLEX = "complex"      # Deep legal analysis, reasoning
    REASONING = "reasoning"  # Advanced reasoning with thinking budget


@dataclass
class ModelConfig:
    """Configuration for a Gemini model."""
    name: str
    input_cost_per_1m: float  # Cost per 1M input tokens in USD
    output_cost_per_1m: float  # Cost per 1M output tokens in USD
    thinking_cost_per_1m: Optional[float] = None  # Cost per 1M thinking tokens (for reasoning models)
    supports_thinking: bool = False


@dataclass
class GenerationResult:
    """Result from a generation request."""
    text: str
    model_name: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    total_tokens: int
    cost: float
    generation_time_ms: float


class GeminiRouter:
    """
    Routes requests to appropriate Gemini models based on task complexity.

    Provides cost tracking and optimization for multi-model usage.
    """

    # Model configurations (pricing as of December 2024)
    MODEL_CONFIGS: Dict[TaskComplexity, ModelConfig] = {
        TaskComplexity.SIMPLE: ModelConfig(
            name="gemini-2.5-flash-lite",
            input_cost_per_1m=0.075,   # $0.075 per 1M input tokens
            output_cost_per_1m=0.30,   # $0.30 per 1M output tokens
        ),
        TaskComplexity.BALANCED: ModelConfig(
            name="gemini-2.5-flash",
            input_cost_per_1m=0.15,    # $0.15 per 1M input tokens
            output_cost_per_1m=0.60,   # $0.60 per 1M output tokens
        ),
        TaskComplexity.COMPLEX: ModelConfig(
            name="gemini-2.5-pro",
            input_cost_per_1m=1.25,    # $1.25 per 1M input tokens
            output_cost_per_1m=5.00,   # $5.00 per 1M output tokens
        ),
        TaskComplexity.REASONING: ModelConfig(
            name="gemini-3-pro",
            input_cost_per_1m=2.50,    # $2.50 per 1M input tokens
            output_cost_per_1m=10.00,  # $10.00 per 1M output tokens
            thinking_cost_per_1m=2.50, # $2.50 per 1M thinking tokens
            supports_thinking=True,
        ),
    }

    def __init__(self, api_key: str):
        """
        Initialize the Gemini router.

        Args:
            api_key: Google AI API key for authentication
        """
        genai.configure(api_key=api_key)
        self._api_key = api_key
        logger.info("GeminiRouter initialized with model configurations")

    def get_model(
        self,
        complexity: TaskComplexity,
        thinking_budget: Optional[int] = None,
        system_instruction: Optional[str] = None,
    ) -> genai.GenerativeModel:
        """
        Get the appropriate Gemini model for the given complexity level.

        Args:
            complexity: Task complexity level
            thinking_budget: Token budget for thinking (reasoning models only)
            system_instruction: System instruction to configure model behavior

        Returns:
            Configured GenerativeModel instance

        Raises:
            ValueError: If thinking_budget is provided for non-reasoning models
        """
        config = self.MODEL_CONFIGS[complexity]

        if thinking_budget is not None and not config.supports_thinking:
            raise ValueError(
                f"Model {config.name} does not support thinking budget. "
                f"Use TaskComplexity.REASONING for models with thinking support."
            )

        model_config = {}
        if config.supports_thinking and thinking_budget:
            model_config["thinking_budget"] = thinking_budget

        # Create generation config
        generation_config = genai.GenerationConfig(
            temperature=0.2,  # Lower temperature for legal analysis
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
        )

        model = genai.GenerativeModel(
            model_name=config.name,
            generation_config=generation_config,
            system_instruction=system_instruction,
        )

        logger.debug(
            f"Created model {config.name} for complexity {complexity.value}"
            + (f" with thinking_budget={thinking_budget}" if thinking_budget else "")
        )

        return model

    async def generate(
        self,
        prompt: str,
        complexity: TaskComplexity,
        thinking_budget: Optional[int] = None,
        system_instruction: Optional[str] = None,
    ) -> GenerationResult:
        """
        Generate content using the appropriate model for the task complexity.

        Args:
            prompt: Input prompt for generation
            complexity: Task complexity level
            thinking_budget: Token budget for thinking (reasoning models only)
            system_instruction: System instruction to configure model behavior

        Returns:
            GenerationResult with text, tokens, and cost information

        Raises:
            Exception: If generation fails
        """
        start_time = time.time()

        try:
            model = self.get_model(
                complexity=complexity,
                thinking_budget=thinking_budget,
                system_instruction=system_instruction,
            )

            # Run blocking generate_content in thread pool
            response = await asyncio.to_thread(
                model.generate_content,
                prompt
            )

            # Extract response text
            text = response.text

            # Extract token usage
            usage_metadata = response.usage_metadata
            input_tokens = usage_metadata.prompt_token_count
            output_tokens = usage_metadata.candidates_token_count

            # For reasoning models, check for thinking tokens
            thinking_tokens = 0
            if hasattr(usage_metadata, 'thinking_token_count'):
                thinking_tokens = usage_metadata.thinking_token_count or 0

            total_tokens = usage_metadata.total_token_count

            # Calculate cost
            cost = self._calculate_cost(
                complexity=complexity,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
            )

            generation_time_ms = (time.time() - start_time) * 1000

            config = self.MODEL_CONFIGS[complexity]

            logger.info(
                f"Generated content using {config.name}: "
                f"{input_tokens} input + {output_tokens} output "
                f"+ {thinking_tokens} thinking tokens = ${cost:.6f}"
            )

            return GenerationResult(
                text=text,
                model_name=config.name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                total_tokens=total_tokens,
                cost=cost,
                generation_time_ms=generation_time_ms,
            )

        except Exception as e:
            generation_time_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Generation failed for {complexity.value} task "
                f"after {generation_time_ms:.2f}ms: {e}"
            )
            raise

    def _calculate_cost(
        self,
        complexity: TaskComplexity,
        input_tokens: int,
        output_tokens: int,
        thinking_tokens: int = 0,
    ) -> float:
        """
        Calculate the cost of a generation request.

        Args:
            complexity: Task complexity level
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            thinking_tokens: Number of thinking tokens (for reasoning models)

        Returns:
            Total cost in USD
        """
        config = self.MODEL_CONFIGS[complexity]

        input_cost = (input_tokens / 1_000_000) * config.input_cost_per_1m
        output_cost = (output_tokens / 1_000_000) * config.output_cost_per_1m

        thinking_cost = 0.0
        if thinking_tokens > 0 and config.thinking_cost_per_1m:
            thinking_cost = (thinking_tokens / 1_000_000) * config.thinking_cost_per_1m

        total_cost = input_cost + output_cost + thinking_cost

        return round(total_cost, 6)

    def get_model_info(self, complexity: TaskComplexity) -> Dict[str, Any]:
        """
        Get information about the model for a given complexity level.

        Args:
            complexity: Task complexity level

        Returns:
            Dictionary with model information
        """
        config = self.MODEL_CONFIGS[complexity]

        return {
            "complexity": complexity.value,
            "model_name": config.name,
            "pricing": {
                "input_per_1m_tokens": config.input_cost_per_1m,
                "output_per_1m_tokens": config.output_cost_per_1m,
                "thinking_per_1m_tokens": config.thinking_cost_per_1m,
            },
            "supports_thinking": config.supports_thinking,
        }

    def estimate_cost(
        self,
        complexity: TaskComplexity,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        estimated_thinking_tokens: int = 0,
    ) -> float:
        """
        Estimate the cost of a generation request before making it.

        Args:
            complexity: Task complexity level
            estimated_input_tokens: Estimated number of input tokens
            estimated_output_tokens: Estimated number of output tokens
            estimated_thinking_tokens: Estimated number of thinking tokens

        Returns:
            Estimated cost in USD
        """
        return self._calculate_cost(
            complexity=complexity,
            input_tokens=estimated_input_tokens,
            output_tokens=estimated_output_tokens,
            thinking_tokens=estimated_thinking_tokens,
        )
