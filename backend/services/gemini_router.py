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
import google.api_core.exceptions

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

try:
    from ..services.api_resilience import gemini_breaker, with_circuit_breaker
except ImportError:
    from backend.services.api_resilience import gemini_breaker, with_circuit_breaker


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Expert Legal System Instructions
# ═══════════════════════════════════════════════════════════════════════════════

class LegalExpertise(str, Enum):
    """Pre-defined legal expertise personas for contract analysis."""
    RISK_ANALYST = "risk_analyst"
    CONTRACT_REVIEWER = "contract_reviewer"
    QA_ASSISTANT = "qa_assistant"
    COMPLIANCE_EXPERT = "compliance_expert"


LEGAL_SYSTEM_INSTRUCTIONS: Dict[LegalExpertise, str] = {
    LegalExpertise.RISK_ANALYST: """You are a Senior Legal Risk Analyst with 20+ years of experience analyzing complex commercial contracts, M&A agreements, and corporate transactions.

EXPERTISE AREAS:
- Mergers & Acquisitions (M&A) agreements and deal structures
- Indemnification provisions and liability allocation
- Limitation of liability and cap structures
- Termination rights and change of control provisions
- Regulatory compliance (antitrust, securities, CFIUS)
- Material adverse change (MAC) clauses
- Representations and warranties analysis
- Disclosure schedules and carve-outs

ANALYSIS FRAMEWORK:
1. IDENTIFY key risk provisions: indemnification, limitation of liability, termination, dispute resolution
2. ASSESS risk allocation between parties - who bears what risks?
3. FLAG unusual or one-sided provisions that deviate from market standards
4. EVALUATE enforceability concerns and potential litigation exposure
5. QUANTIFY financial exposure where possible (caps, baskets, deductibles)

OUTPUT STANDARDS:
- Always cite specific section numbers (e.g., "Section 8.2(a)")
- Use precise legal terminology
- Distinguish between "representations" vs "warranties" vs "covenants"
- Note any missing standard provisions (e.g., no liability cap = unlimited exposure)
- Provide risk ratings: LOW (routine), MEDIUM (requires attention), HIGH (critical concern)

COMMON RED FLAGS TO IDENTIFY:
- Unlimited or uncapped liability exposure
- One-sided indemnification obligations
- Broad "material adverse effect" definitions favoring one party
- Missing or weak termination rights
- Unusual survival periods for representations/warranties
- Non-standard dispute resolution (e.g., arbitration in foreign jurisdictions)
- Broad assignment rights without consent requirements
- Missing insurance requirements for indemnification""",

    LegalExpertise.CONTRACT_REVIEWER: """You are an Expert Contract Attorney specializing in commercial agreement review and negotiation with 15+ years at top-tier law firms.

REVIEW METHODOLOGY:
1. STRUCTURE ANALYSIS: Verify all standard sections are present and properly organized
2. PARTY IDENTIFICATION: Confirm all parties, signatories, and their roles
3. TERM EXTRACTION: Identify key commercial terms (price, duration, deliverables)
4. OBLIGATION MAPPING: Who must do what, when, and under what conditions?
5. RISK ALLOCATION: How are liabilities, indemnities, and insurance handled?
6. EXIT ANALYSIS: Termination rights, survival provisions, post-termination obligations

KEY PROVISIONS TO EXTRACT:
- Effective date and term/duration
- Payment terms and pricing structure
- Scope of work/services/deliverables
- Performance standards and SLAs
- Intellectual property ownership and licenses
- Confidentiality and non-disclosure terms
- Insurance requirements
- Governing law and jurisdiction
- Amendment and waiver procedures

OUTPUT FORMAT:
- Organize findings by contract section
- Use bullet points for clarity
- Highlight ambiguous language that could lead to disputes
- Note any provisions that require negotiation
- Provide plain-English summaries alongside legal citations""",

    LegalExpertise.QA_ASSISTANT: """You are a Legal Research Assistant helping users understand contract terms and provisions.

RESPONSE GUIDELINES:
- Answer questions directly and concisely
- Quote relevant contract language when available
- Explain legal terms in plain English
- If information is not in the provided contract excerpts, clearly state this
- Do not speculate or make assumptions beyond the contract text
- Provide section references for your answers

WHEN ANSWERING:
- Start with a direct answer to the question
- Support with specific contract language
- Note any related provisions the user should be aware of
- Flag if the answer requires legal interpretation vs. being explicitly stated

LIMITATIONS:
- Do not provide legal advice - only information from the contract
- Clarify when provisions are ambiguous or subject to interpretation
- Recommend consulting an attorney for important decisions""",

    LegalExpertise.COMPLIANCE_EXPERT: """You are a Regulatory Compliance Specialist with expertise in corporate governance, securities law, and regulatory requirements.

COMPLIANCE AREAS:
- Antitrust/Competition law (HSR Act, EU Merger Regulation)
- Securities regulations (SEC, disclosure requirements)
- CFIUS and foreign investment review
- Industry-specific regulations (healthcare, financial services, energy)
- Data privacy (GDPR, CCPA, HIPAA)
- Anti-corruption (FCPA, UK Bribery Act)
- Export controls and sanctions (OFAC, EAR)

ANALYSIS APPROACH:
1. IDENTIFY regulatory triggers in the transaction
2. MAP required approvals and filing obligations
3. ASSESS timeline implications for closing conditions
4. FLAG potential regulatory concerns or deal blockers
5. RECOMMEND mitigation strategies

OUTPUT REQUIREMENTS:
- List all applicable regulatory regimes
- Note filing deadlines and required approvals
- Identify conditions precedent related to regulatory matters
- Highlight risk allocation for regulatory failures
- Assess likelihood of regulatory challenge""",
}


def get_legal_system_instruction(
    expertise: LegalExpertise,
    additional_context: Optional[str] = None
) -> str:
    """
    Get the system instruction for a specific legal expertise.

    Args:
        expertise: The type of legal expertise to apply
        additional_context: Optional additional context to append

    Returns:
        Complete system instruction string
    """
    instruction = LEGAL_SYSTEM_INSTRUCTIONS[expertise]

    if additional_context:
        instruction = f"{instruction}\n\nADDITIONAL CONTEXT:\n{additional_context}"

    return instruction


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

    def __init__(
        self,
        api_key: str,
        default_timeout: float = 30.0,  # 30 seconds default
        max_timeout: float = 120.0      # 2 minutes max
    ):
        """
        Initialize the Gemini router.

        Args:
            api_key: Google AI API key for authentication
            default_timeout: Default timeout in seconds for API calls
            max_timeout: Maximum allowed timeout in seconds
        """
        genai.configure(api_key=api_key)
        self._api_key = api_key
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout
        logger.info(
            f"GeminiRouter initialized with model configurations "
            f"(timeout: {default_timeout}s, max: {max_timeout}s)"
        )

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

    @with_circuit_breaker(gemini_breaker)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            google.api_core.exceptions.ServiceUnavailable,
            google.api_core.exceptions.ResourceExhausted,
            google.api_core.exceptions.DeadlineExceeded,
            ConnectionError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def generate(
        self,
        prompt: str,
        complexity: TaskComplexity,
        thinking_budget: Optional[int] = None,
        system_instruction: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> GenerationResult:
        """
        Generate content using the appropriate model for the task complexity.

        Features:
        - Automatic retry on transient failures (up to 3 attempts)
        - Circuit breaker to prevent cascading failures
        - Configurable timeout with exponential backoff

        Args:
            prompt: Input prompt for generation
            complexity: Task complexity level
            thinking_budget: Token budget for thinking (reasoning models only)
            system_instruction: System instruction to configure model behavior
            timeout: Optional timeout in seconds (defaults to default_timeout)

        Returns:
            GenerationResult with text, tokens, and cost information

        Raises:
            TimeoutError: If generation exceeds timeout
            ServiceUnavailableError: If circuit breaker is open
            Exception: If generation fails after retries
        """
        start_time = time.time()

        # Calculate effective timeout
        effective_timeout = min(
            timeout or self.default_timeout,
            self.max_timeout
        )

        try:
            model = self.get_model(
                complexity=complexity,
                thinking_budget=thinking_budget,
                system_instruction=system_instruction,
            )

            # Run blocking generate_content in thread pool with timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    prompt
                ),
                timeout=effective_timeout
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

        except asyncio.TimeoutError:
            generation_time_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Gemini API call timed out after {effective_timeout}s "
                f"for {complexity.value} task"
            )
            raise TimeoutError(
                f"Gemini API call timed out after {effective_timeout}s"
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

    async def generate_with_expertise(
        self,
        prompt: str,
        expertise: LegalExpertise,
        complexity: Optional[TaskComplexity] = None,
        additional_context: Optional[str] = None,
        thinking_budget: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> GenerationResult:
        """
        Generate content using a pre-defined legal expertise persona.

        This is a convenience method that automatically applies the appropriate
        system instruction for the specified legal expertise.

        Args:
            prompt: Input prompt for generation
            expertise: Type of legal expertise to apply
            complexity: Task complexity level (defaults based on expertise)
            additional_context: Optional additional context for the system instruction
            thinking_budget: Token budget for thinking (reasoning models only)
            timeout: Optional timeout in seconds

        Returns:
            GenerationResult with text, tokens, and cost information

        Example:
            result = await router.generate_with_expertise(
                prompt="Analyze the indemnification provisions in this contract...",
                expertise=LegalExpertise.RISK_ANALYST,
            )
        """
        # Default complexity based on expertise type
        if complexity is None:
            complexity_map = {
                LegalExpertise.RISK_ANALYST: TaskComplexity.BALANCED,
                LegalExpertise.CONTRACT_REVIEWER: TaskComplexity.BALANCED,
                LegalExpertise.QA_ASSISTANT: TaskComplexity.SIMPLE,
                LegalExpertise.COMPLIANCE_EXPERT: TaskComplexity.COMPLEX,
            }
            complexity = complexity_map.get(expertise, TaskComplexity.BALANCED)

        # Get the system instruction for this expertise
        system_instruction = get_legal_system_instruction(
            expertise=expertise,
            additional_context=additional_context,
        )

        logger.info(
            f"Generating with {expertise.value} expertise using {complexity.value} model"
        )

        return await self.generate(
            prompt=prompt,
            complexity=complexity,
            thinking_budget=thinking_budget,
            system_instruction=system_instruction,
            timeout=timeout,
        )

    @staticmethod
    def get_available_expertise() -> Dict[str, str]:
        """
        Get a dictionary of available legal expertise types and their descriptions.

        Returns:
            Dictionary mapping expertise names to brief descriptions
        """
        return {
            LegalExpertise.RISK_ANALYST.value: "Senior Legal Risk Analyst - M&A, indemnification, liability analysis",
            LegalExpertise.CONTRACT_REVIEWER.value: "Expert Contract Attorney - commercial agreement review",
            LegalExpertise.QA_ASSISTANT.value: "Legal Research Assistant - answering contract questions",
            LegalExpertise.COMPLIANCE_EXPERT.value: "Regulatory Compliance Specialist - antitrust, securities, CFIUS",
        }

    @staticmethod
    def get_expertise_system_instruction(expertise: LegalExpertise) -> str:
        """
        Get the full system instruction for a specific expertise.

        Args:
            expertise: The type of legal expertise

        Returns:
            The complete system instruction string
        """
        return LEGAL_SYSTEM_INSTRUCTIONS[expertise]
