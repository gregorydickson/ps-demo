"""
Hybrid retriever combining semantic search with graph context.

Implements Graph RAG pattern:
1. Semantic search finds relevant text chunks
2. Graph traversal expands context with related entities
3. Results merged and re-ranked using RRF (Reciprocal Rank Fusion)
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

try:
    from ..utils.logging import get_logger
    from ..utils.performance import log_execution_time
except ImportError:
    from backend.utils.logging import get_logger
    from backend.utils.performance import log_execution_time

logger = get_logger("hybrid_retriever")


# =============================================================================
# Constants - Extracted magic numbers for easier tuning
# =============================================================================

# RRF (Reciprocal Rank Fusion) constant
# Standard value from research papers; higher = more weight on lower ranks
DEFAULT_RRF_K = 60

# Graph context relevance scores by type
# Higher values = more relevant to typical legal queries
RELEVANCE_METADATA = 0.8    # Contract metadata (risk level, payment terms)
RELEVANCE_COMPANY = 0.7     # Party/company information
RELEVANCE_CLAUSE = 0.6      # Contract clauses
RELEVANCE_RISK = 0.9        # Risk factors (highest priority)
RELEVANCE_DEFAULT = 0.5     # Default fallback

# Token estimation
CHARS_PER_TOKEN = 4  # Rough estimate: 1 token ≈ 4 characters for English text


@dataclass
class RetrievalResult:
    """Single retrieval result with combined scores."""
    contract_id: str
    content: str
    source: str  # "semantic" | "graph"
    semantic_score: Optional[float] = None
    graph_relevance: Optional[float] = None
    rrf_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridRetrievalResponse:
    """Combined retrieval response."""
    results: List[RetrievalResult]
    semantic_count: int
    graph_count: int
    total_tokens_estimate: int


class HybridRetriever:
    """
    Combines vector search with graph traversal for Graph RAG.

    Retrieval Strategy:
    1. Run semantic search on query -> get top-k chunks
    2. Extract contract_ids from semantic results
    3. For each contract_id, fetch graph context
    4. Merge semantic chunks with graph context
    5. Re-rank using Reciprocal Rank Fusion (RRF)
    """

    def __init__(
        self,
        vector_store,
        graph_context_retriever,
        rrf_k: int = DEFAULT_RRF_K
    ):
        """
        Args:
            vector_store: ContractVectorStore instance
            graph_context_retriever: GraphContextRetriever instance
            rrf_k: RRF constant (default 60, standard value)
        """
        self.vector_store = vector_store
        self.graph_retriever = graph_context_retriever
        self.rrf_k = rrf_k
        logger.info(
            "hybrid_retriever_initialized",
            rrf_k=rrf_k
        )

    @log_execution_time("hybrid_retrieve")
    async def retrieve(
        self,
        query: str,
        contract_id: Optional[str] = None,
        n_semantic: int = 5,
        n_graph: int = 3,
        include_companies: bool = True,
        include_risks: bool = True
    ) -> HybridRetrievalResponse:
        """
        Perform hybrid retrieval combining semantic + graph.

        Args:
            query: User's question
            contract_id: Optional specific contract (None = global search)
            n_semantic: Number of semantic results
            n_graph: Max graph context items per contract
            include_companies: Include company context from graph
            include_risks: Include risk factors from graph

        Returns:
            HybridRetrievalResponse with merged, re-ranked results
        """
        # Step 1: Semantic search
        semantic_results = await self.vector_store.semantic_search(
            query=query,
            n_results=n_semantic,
            contract_id=contract_id
        )

        # Step 2: Extract unique contract IDs
        contract_ids = set(r["metadata"]["contract_id"] for r in semantic_results)

        # Step 3: Fetch graph context for each contract (parallel)
        graph_contexts = await self._fetch_graph_contexts(
            contract_ids=contract_ids,
            include_companies=include_companies,
            include_risks=include_risks,
            max_items=n_graph
        )

        # Step 4: Convert to RetrievalResults
        all_results = self._merge_results(semantic_results, graph_contexts)

        # Step 5: Re-rank with RRF
        ranked_results = self._rrf_rerank(all_results)

        return HybridRetrievalResponse(
            results=ranked_results,
            semantic_count=len(semantic_results),
            graph_count=sum(len(gc) for gc in graph_contexts.values()),
            total_tokens_estimate=self._estimate_tokens(ranked_results)
        )

    async def _fetch_graph_contexts(
        self,
        contract_ids: set,
        include_companies: bool,
        include_risks: bool,
        max_items: int
    ) -> Dict[str, List[Dict]]:
        """
        Fetch graph context for multiple contracts in parallel.

        Args:
            contract_ids: Set of contract IDs to fetch context for
            include_companies: Include company context
            include_risks: Include risk factors
            max_items: Maximum items per contract

        Returns:
            Dictionary mapping contract_id to list of context dictionaries
        """
        async def fetch_single_context(contract_id: str) -> Tuple[str, List[Dict]]:
            """Fetch context for a single contract."""
            try:
                # Get graph context from retriever
                graph_context = await self.graph_retriever.get_context_for_contract(
                    contract_id=contract_id,
                    include_companies=include_companies,
                    include_clauses=True,
                    include_risks=include_risks,
                    max_clauses=max_items
                )

                if not graph_context:
                    return (contract_id, [])

                # Convert GraphContext to list of context items
                context_items = []

                # Add contract metadata as context
                if graph_context.contract_metadata:
                    metadata_text = f"Contract Metadata: "
                    metadata_parts = []
                    if 'risk_level' in graph_context.contract_metadata:
                        metadata_parts.append(f"Risk Level: {graph_context.contract_metadata['risk_level']}")
                    if 'risk_score' in graph_context.contract_metadata:
                        metadata_parts.append(f"Risk Score: {graph_context.contract_metadata['risk_score']}")
                    if 'payment_amount' in graph_context.contract_metadata:
                        metadata_parts.append(f"Payment Amount: {graph_context.contract_metadata['payment_amount']}")
                    if 'payment_frequency' in graph_context.contract_metadata:
                        metadata_parts.append(f"Payment Frequency: {graph_context.contract_metadata['payment_frequency']}")

                    if metadata_parts:
                        metadata_text += ", ".join(metadata_parts)
                        context_items.append({
                            'content': metadata_text,
                            'type': 'metadata',
                            'relevance': RELEVANCE_METADATA
                        })

                # Add companies
                if include_companies and graph_context.companies:
                    for company in graph_context.companies[:max_items]:
                        company_text = f"Party: {company.get('name', 'Unknown')} (Role: {company.get('role', 'Unknown')})"
                        context_items.append({
                            'content': company_text,
                            'type': 'company',
                            'relevance': RELEVANCE_COMPANY
                        })

                # Add clauses
                if graph_context.related_clauses:
                    for clause in graph_context.related_clauses[:max_items]:
                        clause_text = f"Clause - {clause.get('section_name', 'Unknown')}: {clause.get('content', '')}"
                        context_items.append({
                            'content': clause_text,
                            'type': 'clause',
                            'relevance': RELEVANCE_CLAUSE
                        })

                # Add risk factors
                if include_risks and graph_context.risk_factors:
                    for risk in graph_context.risk_factors[:max_items]:
                        risk_text = f"Risk ({risk.get('risk_level', 'unknown')}): {risk.get('concern', '')}"
                        if risk.get('recommendation'):
                            risk_text += f" - Recommendation: {risk['recommendation']}"
                        context_items.append({
                            'content': risk_text,
                            'type': 'risk',
                            'relevance': RELEVANCE_RISK
                        })

                return (contract_id, context_items)

            except Exception as e:
                logger.error(
                    "graph_context_fetch_error",
                    contract_id=contract_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    include_companies=include_companies,
                    include_risks=include_risks,
                    max_items=max_items
                )
                return (contract_id, [])

        # Fetch all contexts in parallel using asyncio.gather
        tasks = [fetch_single_context(cid) for cid in contract_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dictionary, filtering out exceptions
        context_dict = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(
                    "parallel_fetch_exception",
                    error=str(result),
                    error_type=type(result).__name__
                )
                continue
            contract_id, contexts = result
            context_dict[contract_id] = contexts

        total_items = sum(len(v) for v in context_dict.values())
        logger.info(
            "graph_contexts_fetched",
            contracts_count=len(context_dict),
            total_items=total_items
        )

        return context_dict

    def _merge_results(
        self,
        semantic_results: List[Dict],
        graph_contexts: Dict[str, List[Dict]]
    ) -> List[RetrievalResult]:
        """
        Convert and merge semantic + graph results into RetrievalResult objects.

        Args:
            semantic_results: Results from vector store semantic_search
            graph_contexts: Dict mapping contract_id to graph context items

        Returns:
            List of RetrievalResult objects
        """
        merged = []

        # Add semantic results
        for result in semantic_results:
            merged.append(RetrievalResult(
                contract_id=result["metadata"]["contract_id"],
                content=result["text"],
                source="semantic",
                semantic_score=result.get("relevance_score", 0.0),
                graph_relevance=None,
                metadata=result["metadata"]
            ))

        # Add graph context results
        for contract_id, contexts in graph_contexts.items():
            for context in contexts:
                merged.append(RetrievalResult(
                    contract_id=contract_id,
                    content=context['content'],
                    source="graph",
                    semantic_score=None,
                    graph_relevance=context.get('relevance', RELEVANCE_DEFAULT),
                    metadata={'type': context.get('type', 'unknown')}
                ))

        graph_count = sum(len(v) for v in graph_contexts.values())
        logger.debug(
            "results_merged",
            semantic_count=len(semantic_results),
            graph_count=graph_count,
            total_count=len(merged)
        )

        return merged

    def _rrf_rerank(
        self,
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """
        Re-rank results using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank_i)) for each ranking list
        Results appearing in only one list get score from that list only.
        Results appearing in both lists get boosted scores.

        Args:
            results: List of RetrievalResult objects

        Returns:
            List of RetrievalResult objects sorted by RRF score descending
        """
        # Create ranking for semantic results (by semantic_score desc)
        semantic_ranked = sorted(
            [r for r in results if r.semantic_score is not None],
            key=lambda x: x.semantic_score,
            reverse=True
        )
        semantic_ranks = {r.content: i + 1 for i, r in enumerate(semantic_ranked)}

        # Create ranking for graph results (by graph_relevance desc)
        graph_ranked = sorted(
            [r for r in results if r.graph_relevance is not None],
            key=lambda x: x.graph_relevance,
            reverse=True
        )
        graph_ranks = {r.content: i + 1 for i, r in enumerate(graph_ranked)}

        # Calculate RRF scores
        for result in results:
            rrf = 0.0
            if result.content in semantic_ranks:
                rrf += 1.0 / (self.rrf_k + semantic_ranks[result.content])
            if result.content in graph_ranks:
                rrf += 1.0 / (self.rrf_k + graph_ranks[result.content])
            result.rrf_score = rrf

        # Sort by RRF score descending
        ranked_results = sorted(results, key=lambda x: x.rrf_score, reverse=True)

        if ranked_results:
            logger.debug(
                "rrf_rerank_complete",
                result_count=len(results),
                top_score=round(ranked_results[0].rrf_score, 4),
                rrf_k=self.rrf_k
            )
        else:
            logger.debug("rrf_rerank_complete", result_count=0)

        return ranked_results

    def _estimate_tokens(self, results: List[RetrievalResult]) -> int:
        """
        Estimate token count for context (chars / 4 approximation).

        This is a rough estimate using the common rule of thumb that
        1 token ≈ 4 characters for English text.

        Args:
            results: List of RetrievalResult objects

        Returns:
            Estimated token count
        """
        total_chars = sum(len(r.content) for r in results)
        estimated_tokens = total_chars // CHARS_PER_TOKEN

        logger.debug(
            "tokens_estimated",
            total_chars=total_chars,
            estimated_tokens=estimated_tokens,
            chars_per_token=CHARS_PER_TOKEN
        )

        return estimated_tokens
