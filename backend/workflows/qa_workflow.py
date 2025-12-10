"""
Lightweight Q&A workflow for querying existing contracts.

This workflow skips parse/analyze/store steps and only:
1. Retrieves relevant context from vector store
2. Generates answer using Gemini Flash-Lite

Much more efficient than running full contract_analysis_workflow.
"""

import os
from typing import TypedDict, Optional
import structlog

try:
    from ..services.vector_store import ContractVectorStore
    from ..services.gemini_router import GeminiRouter, TaskComplexity, LegalExpertise
    from ..services.cost_tracker import CostTracker
except ImportError:
    from backend.services.vector_store import ContractVectorStore
    from backend.services.gemini_router import GeminiRouter, TaskComplexity, LegalExpertise
    from backend.services.cost_tracker import CostTracker

logger = structlog.get_logger()


class QAState(TypedDict):
    """Minimal state for Q&A operations."""
    contract_id: str
    query: str
    context_chunks: list
    answer: Optional[str]
    cost: float
    error: Optional[str]


class QAWorkflow:
    """
    Lightweight workflow for contract Q&A.

    Usage:
        workflow = QAWorkflow()
        result = await workflow.run(
            contract_id="abc-123",
            query="What are the payment terms?"
        )
        print(result["answer"])
    """

    def __init__(
        self,
        vector_store: Optional[ContractVectorStore] = None,
        gemini_router: Optional[GeminiRouter] = None,
        cost_tracker: Optional[CostTracker] = None
    ):
        """
        Initialize QA workflow with required services.

        Args:
            vector_store: ContractVectorStore instance (creates new if None)
            gemini_router: GeminiRouter instance (creates new if None)
            cost_tracker: Optional CostTracker for cost tracking
        """
        self.vector_store = vector_store or ContractVectorStore()
        self.gemini_router = gemini_router or GeminiRouter(
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        self.cost_tracker = cost_tracker

        logger.info("QAWorkflow initialized")

    async def run(
        self,
        contract_id: str,
        query: str,
        n_chunks: int = 5
    ) -> QAState:
        """
        Execute Q&A workflow.

        Args:
            contract_id: ID of the contract to query
            query: User's question
            n_chunks: Number of context chunks to retrieve

        Returns:
            QAState with answer, cost, and any errors
        """
        state: QAState = {
            "contract_id": contract_id,
            "query": query,
            "context_chunks": [],
            "answer": None,
            "cost": 0.0,
            "error": None
        }

        try:
            # Step 1: Retrieve relevant context
            logger.info(
                "qa_retrieve_context",
                contract_id=contract_id,
                query=query[:50]
            )

            chunks = await self.vector_store.semantic_search(
                query=query,
                contract_id=contract_id,
                n_results=n_chunks
            )
            state["context_chunks"] = chunks

            if not chunks:
                state["answer"] = "I couldn't find relevant information in this contract."
                logger.warning(
                    "qa_no_context",
                    contract_id=contract_id
                )
                return state

            # Step 2: Generate answer
            context_text = "\n\n".join([
                f"[Section {i+1}]: {chunk['text']}"
                for i, chunk in enumerate(chunks)
            ])

            prompt = self._build_qa_prompt(query, context_text)

            logger.info("qa_generate_answer", contract_id=contract_id)

            response = await self.gemini_router.generate_with_expertise(
                prompt=prompt,
                expertise=LegalExpertise.QA_ASSISTANT
            )

            state["answer"] = response.text
            state["cost"] = response.cost

            # Track cost if tracker available
            if self.cost_tracker:
                await self.cost_tracker.track_api_call(
                    model_name=response.model_name,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost=response.cost,
                    operation="qa_query"
                )

            logger.info(
                "qa_complete",
                contract_id=contract_id,
                cost=state["cost"]
            )

        except Exception as e:
            logger.error(
                "qa_error",
                contract_id=contract_id,
                error=str(e)
            )
            state["error"] = str(e)

        return state

    def _build_qa_prompt(self, query: str, context: str) -> str:
        """Build prompt for Q&A generation."""
        return f"""Based on the following contract excerpts, answer the user's question.

CONTRACT EXCERPTS:
{context}

USER QUESTION: {query}

Provide a clear, concise answer based only on the information in the contract excerpts above. If the answer cannot be determined from the provided context, say "This information is not found in the provided contract sections."

ANSWER:"""
