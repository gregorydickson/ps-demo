"""
Graph RAG workflow for enhanced contract Q&A.

Combines hybrid retrieval (semantic + graph) with LLM generation for
superior context-aware question answering.
"""

import os
from typing import TypedDict, Optional, List
import structlog

try:
    from ..services.hybrid_retriever import HybridRetriever, HybridRetrievalResponse
    from ..services.graph_context_retriever import GraphContextRetriever
    from ..services.vector_store import ContractVectorStore
    from ..services.graph_store import ContractGraphStore
    from ..services.gemini_router import GeminiRouter, TaskComplexity
    from ..services.cost_tracker import CostTracker
except ImportError:
    from backend.services.hybrid_retriever import HybridRetriever, HybridRetrievalResponse
    from backend.services.graph_context_retriever import GraphContextRetriever
    from backend.services.vector_store import ContractVectorStore
    from backend.services.graph_store import ContractGraphStore
    from backend.services.gemini_router import GeminiRouter, TaskComplexity
    from backend.services.cost_tracker import CostTracker

logger = structlog.get_logger()


class GraphRAGState(TypedDict):
    """State for Graph RAG workflow."""
    contract_id: Optional[str]
    query: str
    retrieval_response: Optional[HybridRetrievalResponse]
    context_text: str
    answer: Optional[str]
    sources: List[dict]
    cost: float
    error: Optional[str]


class GraphRAGWorkflow:
    """
    Graph RAG workflow combining hybrid retrieval with LLM generation.

    Flow:
    1. Hybrid retrieval (semantic + graph)
    2. Context formatting with source attribution
    3. LLM generation with legal expertise
    4. Response with sources

    Cost Optimization:
    - Uses TaskComplexity.SIMPLE (Flash-Lite) for Q&A to minimize costs
    - Estimated cost: ~$0.0001 per query (vs $0.001 with Pro)
    """

    def __init__(
        self,
        vector_store: Optional[ContractVectorStore] = None,
        graph_store: Optional[ContractGraphStore] = None,
        gemini_router: Optional[GeminiRouter] = None,
        cost_tracker: Optional[CostTracker] = None
    ):
        """
        Initialize Graph RAG workflow.

        Args:
            vector_store: ContractVectorStore instance (creates new if None)
            graph_store: ContractGraphStore instance (creates new if None)
            gemini_router: GeminiRouter instance (creates new if None)
            cost_tracker: Optional CostTracker for cost tracking
        """
        self.vector_store = vector_store or ContractVectorStore()
        self.graph_store = graph_store or ContractGraphStore()
        self.gemini_router = gemini_router or GeminiRouter(
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        self.cost_tracker = cost_tracker

        # Initialize hybrid retriever components
        self.graph_retriever = GraphContextRetriever(self.graph_store)
        self.hybrid_retriever = HybridRetriever(
            vector_store=self.vector_store,
            graph_context_retriever=self.graph_retriever
        )

        logger.info("graph_rag_workflow_initialized")

    async def run(
        self,
        query: str,
        contract_id: Optional[str] = None,
        n_results: int = 5,
        include_sources: bool = True
    ) -> GraphRAGState:
        """
        Execute Graph RAG workflow.

        Args:
            query: User's question
            contract_id: Optional specific contract (None = search all)
            n_results: Number of context items to retrieve
            include_sources: Whether to include source attribution

        Returns:
            GraphRAGState with answer, sources, and cost
        """
        state: GraphRAGState = {
            "contract_id": contract_id,
            "query": query,
            "retrieval_response": None,
            "context_text": "",
            "answer": None,
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        try:
            # Step 1: Hybrid retrieval
            logger.info("graph_rag_start", query=query[:50], contract_id=contract_id)
            state = await self._retrieve(state, n_results)

            # Step 2: Format context
            state = self._format_context(state)

            # Step 3: Generate answer
            state = await self._generate(state)

            # Step 4: Extract sources
            if include_sources:
                state = self._extract_sources(state)

            logger.info(
                "graph_rag_complete",
                contract_id=contract_id,
                cost=state["cost"],
                sources=len(state["sources"])
            )

        except Exception as e:
            logger.error("graph_rag_error", error=str(e), query=query[:50])
            state["error"] = str(e)

        return state

    async def _retrieve(self, state: GraphRAGState, n_results: int) -> GraphRAGState:
        """
        Step 1: Hybrid retrieval combining semantic + graph.

        Args:
            state: Current workflow state
            n_results: Number of semantic results to retrieve

        Returns:
            Updated state with retrieval_response
        """
        logger.info("graph_rag_retrieve", query=state["query"][:50])

        response = await self.hybrid_retriever.retrieve(
            query=state["query"],
            contract_id=state["contract_id"],
            n_semantic=n_results,
            n_graph=3,  # Fixed at 3 per workplan
            include_companies=True,
            include_risks=True
        )

        state["retrieval_response"] = response

        logger.info(
            "graph_rag_retrieved",
            semantic_count=response.semantic_count,
            graph_count=response.graph_count,
            total_results=len(response.results)
        )

        return state

    def _format_context(self, state: GraphRAGState) -> GraphRAGState:
        """
        Step 2: Format retrieved context for LLM.

        Creates numbered source sections with type attribution:
        - Document sources (from semantic search)
        - Knowledge Graph sources (from graph traversal)

        Args:
            state: Current workflow state

        Returns:
            Updated state with context_text
        """
        if not state["retrieval_response"]:
            return state

        context_parts = []
        for i, result in enumerate(state["retrieval_response"].results, 1):
            source_type = "Document" if result.source == "semantic" else "Knowledge Graph"
            context_parts.append(
                f"[Source {i} - {source_type}]\n{result.content}\n"
            )

        state["context_text"] = "\n".join(context_parts)

        logger.debug(
            "graph_rag_context_formatted",
            context_length=len(state["context_text"])
        )

        return state

    async def _generate(self, state: GraphRAGState) -> GraphRAGState:
        """
        Step 3: Generate answer using Gemini.

        Uses TaskComplexity.SIMPLE (Flash-Lite) for cost optimization:
        - Q&A is a simple task (no deep reasoning required)
        - Flash-Lite is 5x cheaper than Pro
        - Provides sufficient quality for question answering

        Args:
            state: Current workflow state

        Returns:
            Updated state with answer and cost
        """
        logger.info("graph_rag_generate")

        prompt = f"""You are a legal contract analyst. Answer the question based ONLY on the provided context.

CONTEXT:
{state["context_text"]}

QUESTION: {state["query"]}

INSTRUCTIONS:
- Answer based only on the provided context
- If the context doesn't contain the answer, say "I cannot find this information in the provided context"
- Cite source numbers [Source N] when referencing specific information
- Be concise but thorough

ANSWER:"""

        response = await self.gemini_router.generate(
            prompt=prompt,
            complexity=TaskComplexity.SIMPLE,  # Use Flash-Lite for Q&A
            max_tokens=1024
        )

        state["answer"] = response.text
        state["cost"] = response.cost

        # Track cost if tracker available
        if self.cost_tracker:
            await self.cost_tracker.track_cost(
                model=response.model_name,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=response.cost
            )

        logger.info(
            "graph_rag_generated",
            model=response.model_name,
            cost=response.cost,
            tokens=response.total_tokens
        )

        return state

    def _extract_sources(self, state: GraphRAGState) -> GraphRAGState:
        """
        Step 4: Build source attribution list.

        Creates a list of source references with:
        - Source index (matches [Source N] in context)
        - Source type (semantic or graph)
        - Contract ID
        - Relevance score (RRF score)
        - Preview of content (first 100 chars)

        Args:
            state: Current workflow state

        Returns:
            Updated state with sources list
        """
        if not state["retrieval_response"]:
            return state

        state["sources"] = [
            {
                "index": i + 1,
                "type": r.source,
                "contract_id": r.contract_id,
                "score": r.rrf_score,
                "preview": r.content[:100] + "..." if len(r.content) > 100 else r.content
            }
            for i, r in enumerate(state["retrieval_response"].results)
        ]

        logger.debug("graph_rag_sources_extracted", count=len(state["sources"]))

        return state
