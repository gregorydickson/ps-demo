"""
Unit tests for HybridRetriever service.

Tests the hybrid retrieval combining semantic search with graph context,
focusing on RRF algorithm correctness and result merging.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass
from typing import List, Dict, Any

from backend.services.hybrid_retriever import (
    HybridRetriever,
    RetrievalResult,
    HybridRetrievalResponse
)


# Mock GraphContext dataclass (matching workplan specification)
@dataclass
class GraphContext:
    """Context retrieved from graph traversal."""
    contract_id: str
    contract_metadata: Dict[str, Any]
    companies: List[Dict[str, Any]]
    related_clauses: List[Dict[str, Any]]
    risk_factors: List[Dict[str, Any]]
    traversal_depth: int


class TestHybridRetriever:
    """Tests for HybridRetriever."""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store with semantic search results."""
        store = AsyncMock()
        store.semantic_search = AsyncMock(return_value=[
            {
                "id": "c1_chunk_0",
                "text": "Payment terms are NET 30 days.",
                "metadata": {"contract_id": "c1", "chunk_index": 0},
                "relevance_score": 0.9
            },
            {
                "id": "c1_chunk_1",
                "text": "Termination clause allows 30-day notice.",
                "metadata": {"contract_id": "c1", "chunk_index": 1},
                "relevance_score": 0.7
            },
            {
                "id": "c2_chunk_0",
                "text": "Payment terms are NET 60 days.",
                "metadata": {"contract_id": "c2", "chunk_index": 0},
                "relevance_score": 0.85
            }
        ])
        return store

    @pytest.fixture
    def mock_graph_retriever(self):
        """Mock graph context retriever."""
        retriever = AsyncMock()

        async def mock_get_context(contract_id, **kwargs):
            """Return different contexts based on contract_id."""
            if contract_id == "c1":
                return GraphContext(
                    contract_id="c1",
                    contract_metadata={
                        "risk_level": "medium",
                        "risk_score": 0.6,
                        "payment_amount": 10000,
                        "payment_frequency": "monthly"
                    },
                    companies=[
                        {"name": "Acme Corp", "role": "vendor"},
                        {"name": "Beta Inc", "role": "client"}
                    ],
                    related_clauses=[
                        {"section_name": "Payment", "content": "Payment is due within 30 days"}
                    ],
                    risk_factors=[
                        {
                            "concern": "Liability cap too low",
                            "risk_level": "high",
                            "recommendation": "Increase liability cap"
                        }
                    ],
                    traversal_depth=1
                )
            elif contract_id == "c2":
                return GraphContext(
                    contract_id="c2",
                    contract_metadata={"risk_level": "low", "risk_score": 0.2},
                    companies=[{"name": "Gamma LLC", "role": "vendor"}],
                    related_clauses=[],
                    risk_factors=[],
                    traversal_depth=1
                )
            else:
                return None

        retriever.get_context_for_contract = AsyncMock(side_effect=mock_get_context)
        return retriever

    @pytest.fixture
    def retriever(self, mock_vector_store, mock_graph_retriever):
        """Create HybridRetriever with mocked dependencies."""
        return HybridRetriever(
            vector_store=mock_vector_store,
            graph_context_retriever=mock_graph_retriever,
            rrf_k=60
        )

    # Test retrieve() method

    @pytest.mark.asyncio
    async def test_retrieve_combines_semantic_and_graph(self, retriever):
        """Should return results from both semantic and graph sources."""
        result = await retriever.retrieve(
            query="payment terms",
            n_semantic=3,
            n_graph=2
        )

        assert isinstance(result, HybridRetrievalResponse)
        assert result.semantic_count == 3
        assert result.graph_count > 0
        assert len(result.results) > 0

        # Verify we have both semantic and graph results
        sources = {r.source for r in result.results}
        assert "semantic" in sources
        assert "graph" in sources

    @pytest.mark.asyncio
    async def test_retrieve_with_specific_contract(self, retriever, mock_vector_store):
        """Should filter by contract_id when specified."""
        mock_vector_store.semantic_search.return_value = [
            {
                "id": "c1_chunk_0",
                "text": "Payment terms...",
                "metadata": {"contract_id": "c1"},
                "relevance_score": 0.9
            }
        ]

        result = await retriever.retrieve(
            query="payment terms",
            contract_id="c1",
            n_semantic=5
        )

        # Verify semantic_search was called with contract_id
        mock_vector_store.semantic_search.assert_called_once()
        call_kwargs = mock_vector_store.semantic_search.call_args.kwargs
        assert call_kwargs["contract_id"] == "c1"

    @pytest.mark.asyncio
    async def test_retrieve_handles_empty_semantic_results(self, retriever, mock_vector_store):
        """Should handle case when semantic search returns no results."""
        mock_vector_store.semantic_search.return_value = []

        result = await retriever.retrieve(query="nonexistent query")

        assert result.semantic_count == 0
        assert result.graph_count == 0
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_retrieve_estimates_tokens(self, retriever):
        """Should provide token estimate for context window management."""
        result = await retriever.retrieve(query="payment terms")

        assert result.total_tokens_estimate > 0
        # Very rough check: should be approximately chars / 4
        total_chars = sum(len(r.content) for r in result.results)
        expected_tokens = total_chars // 4
        assert abs(result.total_tokens_estimate - expected_tokens) < 10

    # Test _merge_results()

    def test_merge_results_converts_semantic_results(self, retriever):
        """Should convert semantic search results to RetrievalResult objects."""
        semantic_results = [
            {
                "id": "c1_chunk_0",
                "text": "Payment terms are NET 30.",
                "metadata": {"contract_id": "c1", "chunk_index": 0},
                "relevance_score": 0.9
            }
        ]
        graph_contexts = {}

        merged = retriever._merge_results(semantic_results, graph_contexts)

        assert len(merged) == 1
        assert merged[0].contract_id == "c1"
        assert merged[0].content == "Payment terms are NET 30."
        assert merged[0].source == "semantic"
        assert merged[0].semantic_score == 0.9
        assert merged[0].graph_relevance is None

    def test_merge_results_converts_graph_contexts(self, retriever):
        """Should convert graph contexts to RetrievalResult objects."""
        semantic_results = []
        graph_contexts = {
            "c1": [
                {"content": "Party: Acme Corp (Role: vendor)", "type": "company", "relevance": 0.7},
                {"content": "Risk (high): Liability cap too low", "type": "risk", "relevance": 0.9}
            ]
        }

        merged = retriever._merge_results(semantic_results, graph_contexts)

        assert len(merged) == 2
        assert merged[0].source == "graph"
        assert merged[0].contract_id == "c1"
        assert merged[0].semantic_score is None
        assert merged[0].graph_relevance in [0.7, 0.9]

    def test_merge_results_combines_both_sources(self, retriever):
        """Should combine semantic and graph results into single list."""
        semantic_results = [
            {
                "id": "c1_chunk_0",
                "text": "Semantic result",
                "metadata": {"contract_id": "c1"},
                "relevance_score": 0.9
            }
        ]
        graph_contexts = {
            "c1": [
                {"content": "Graph result", "type": "company", "relevance": 0.7}
            ]
        }

        merged = retriever._merge_results(semantic_results, graph_contexts)

        assert len(merged) == 2
        sources = [r.source for r in merged]
        assert "semantic" in sources
        assert "graph" in sources

    # Test _rrf_rerank() - CRITICAL for Graph RAG correctness

    def test_rrf_rerank_orders_by_combined_score(self, retriever):
        """RRF should combine rankings from both sources."""
        results = [
            RetrievalResult(
                contract_id="c1",
                content="A",
                source="semantic",
                semantic_score=0.9,
                graph_relevance=None
            ),
            RetrievalResult(
                contract_id="c1",
                content="B",
                source="semantic",
                semantic_score=0.5,
                graph_relevance=None
            ),
            RetrievalResult(
                contract_id="c1",
                content="C",
                source="graph",
                semantic_score=None,
                graph_relevance=0.8
            ),
        ]

        ranked = retriever._rrf_rerank(results)

        # A should be first (highest semantic score)
        assert ranked[0].content == "A"
        # All should have rrf_score > 0
        assert all(r.rrf_score > 0 for r in ranked)
        # Scores should be in descending order
        assert ranked[0].rrf_score >= ranked[1].rrf_score >= ranked[2].rrf_score

    def test_rrf_boosts_results_in_both_lists(self, retriever):
        """Results appearing in both semantic and graph should rank higher."""
        results = [
            # This result appears in both (same content)
            RetrievalResult(
                contract_id="c1",
                content="Both lists result",
                source="semantic",
                semantic_score=0.7,
                graph_relevance=0.7
            ),
            # This only appears in semantic with higher score
            RetrievalResult(
                contract_id="c1",
                content="Semantic only",
                source="semantic",
                semantic_score=0.9,
                graph_relevance=None
            ),
        ]

        ranked = retriever._rrf_rerank(results)

        # Find the results in ranked list
        both_result = next(r for r in ranked if r.content == "Both lists result")
        semantic_only = next(r for r in ranked if r.content == "Semantic only")

        # RRF formula for both lists result:
        # rrf = 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.0328

        # RRF formula for semantic only (ranked 1st):
        # rrf = 1/(60+1) = 1/61 ≈ 0.0164

        # Result in both lists should have higher RRF score
        assert both_result.rrf_score > semantic_only.rrf_score

    def test_rrf_algorithm_correctness(self, retriever):
        """Verify RRF formula: score = 1/(k + rank)."""
        results = [
            RetrievalResult(
                contract_id="c1",
                content="Result1",
                source="semantic",
                semantic_score=0.9  # Rank 1 in semantic
            ),
            RetrievalResult(
                contract_id="c1",
                content="Result2",
                source="semantic",
                semantic_score=0.8  # Rank 2 in semantic
            )
        ]

        ranked = retriever._rrf_rerank(results)

        # k = 60 (default)
        # Result1: rank 1 -> score = 1/(60+1) = 0.01639...
        # Result2: rank 2 -> score = 1/(60+2) = 0.01612...

        expected_score_1 = 1.0 / (60 + 1)
        expected_score_2 = 1.0 / (60 + 2)

        assert abs(ranked[0].rrf_score - expected_score_1) < 0.0001
        assert abs(ranked[1].rrf_score - expected_score_2) < 0.0001

    def test_rrf_handles_only_semantic_results(self, retriever):
        """Should handle case with only semantic results (no graph)."""
        results = [
            RetrievalResult(
                contract_id="c1",
                content="Semantic only",
                source="semantic",
                semantic_score=0.9
            )
        ]

        ranked = retriever._rrf_rerank(results)

        assert len(ranked) == 1
        assert ranked[0].rrf_score > 0
        # Score should be 1/(60+1)
        expected = 1.0 / 61
        assert abs(ranked[0].rrf_score - expected) < 0.0001

    def test_rrf_handles_only_graph_results(self, retriever):
        """Should handle case with only graph results (no semantic)."""
        results = [
            RetrievalResult(
                contract_id="c1",
                content="Graph only",
                source="graph",
                graph_relevance=0.8
            )
        ]

        ranked = retriever._rrf_rerank(results)

        assert len(ranked) == 1
        assert ranked[0].rrf_score > 0
        # Score should be 1/(60+1)
        expected = 1.0 / 61
        assert abs(ranked[0].rrf_score - expected) < 0.0001

    def test_rrf_empty_list(self, retriever):
        """Should handle empty results list gracefully."""
        results = []

        ranked = retriever._rrf_rerank(results)

        assert len(ranked) == 0

    # Test _estimate_tokens()

    def test_estimate_tokens_chars_divided_by_four(self, retriever):
        """Should estimate tokens as chars / 4."""
        results = [
            RetrievalResult(
                contract_id="c1",
                content="A" * 100,  # 100 chars
                source="semantic"
            ),
            RetrievalResult(
                contract_id="c1",
                content="B" * 200,  # 200 chars
                source="graph"
            )
        ]

        tokens = retriever._estimate_tokens(results)

        # 300 chars / 4 = 75 tokens
        assert tokens == 75

    def test_estimate_tokens_empty_results(self, retriever):
        """Should return 0 for empty results."""
        results = []

        tokens = retriever._estimate_tokens(results)

        assert tokens == 0

    # Test _fetch_graph_contexts() - parallel fetching

    @pytest.mark.asyncio
    async def test_fetch_graph_contexts_parallel_fetching(self, retriever):
        """Should fetch graph contexts in parallel using asyncio.gather."""
        contract_ids = {"c1", "c2"}

        contexts = await retriever._fetch_graph_contexts(
            contract_ids=contract_ids,
            include_companies=True,
            include_risks=True,
            max_items=3
        )

        # Should have contexts for both contracts
        assert "c1" in contexts
        assert "c2" in contexts

        # c1 should have multiple context items (companies, clauses, risks, metadata)
        assert len(contexts["c1"]) > 0

        # c2 should have fewer items (only has company)
        assert len(contexts["c2"]) > 0

        # Verify graph retriever was called for both contracts
        assert retriever.graph_retriever.get_context_for_contract.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_graph_contexts_formats_context_items(self, retriever):
        """Should format graph context into readable strings."""
        contract_ids = {"c1"}

        contexts = await retriever._fetch_graph_contexts(
            contract_ids=contract_ids,
            include_companies=True,
            include_risks=True,
            max_items=5
        )

        context_items = contexts["c1"]

        # Should have different types of context
        types = {item['type'] for item in context_items}
        assert 'metadata' in types
        assert 'company' in types
        assert 'risk' in types

        # Check content formatting
        for item in context_items:
            assert 'content' in item
            assert 'type' in item
            assert 'relevance' in item
            assert isinstance(item['content'], str)
            assert len(item['content']) > 0

    @pytest.mark.asyncio
    async def test_fetch_graph_contexts_handles_missing_contract(self, retriever):
        """Should return empty list for non-existent contract."""
        contract_ids = {"nonexistent"}

        contexts = await retriever._fetch_graph_contexts(
            contract_ids=contract_ids,
            include_companies=True,
            include_risks=True,
            max_items=3
        )

        assert "nonexistent" in contexts
        assert contexts["nonexistent"] == []

    @pytest.mark.asyncio
    async def test_fetch_graph_contexts_respects_max_items(self, retriever):
        """Should limit context items per category to max_items."""
        contract_ids = {"c1"}

        contexts = await retriever._fetch_graph_contexts(
            contract_ids=contract_ids,
            include_companies=True,
            include_risks=True,
            max_items=1  # Limit to 1 per category
        )

        context_items = contexts["c1"]

        # Count items by type
        type_counts = {}
        for item in context_items:
            item_type = item['type']
            type_counts[item_type] = type_counts.get(item_type, 0) + 1

        # Each type should have at most max_items (except metadata which is special)
        for item_type, count in type_counts.items():
            if item_type != 'metadata':
                assert count <= 1

    @pytest.mark.asyncio
    async def test_fetch_graph_contexts_filters_by_flags(self, retriever):
        """Should respect include_companies and include_risks flags."""
        contract_ids = {"c1"}

        # Fetch without companies and risks
        contexts = await retriever._fetch_graph_contexts(
            contract_ids=contract_ids,
            include_companies=False,
            include_risks=False,
            max_items=5
        )

        context_items = contexts["c1"]
        types = {item['type'] for item in context_items}

        # Should not have company or risk types
        assert 'company' not in types
        assert 'risk' not in types

        # Verify the call was made with correct flags
        retriever.graph_retriever.get_context_for_contract.assert_called()
        call_kwargs = retriever.graph_retriever.get_context_for_contract.call_args.kwargs
        assert call_kwargs['include_companies'] == False
        assert call_kwargs['include_risks'] == False


class TestRetrievalResultDataclass:
    """Tests for RetrievalResult dataclass."""

    def test_retrieval_result_creation(self):
        """Should create RetrievalResult with required fields."""
        result = RetrievalResult(
            contract_id="c1",
            content="Test content",
            source="semantic"
        )

        assert result.contract_id == "c1"
        assert result.content == "Test content"
        assert result.source == "semantic"
        assert result.semantic_score is None
        assert result.graph_relevance is None
        assert result.rrf_score == 0.0
        assert result.metadata == {}

    def test_retrieval_result_with_all_fields(self):
        """Should create RetrievalResult with all optional fields."""
        result = RetrievalResult(
            contract_id="c1",
            content="Test content",
            source="semantic",
            semantic_score=0.9,
            graph_relevance=0.8,
            rrf_score=0.015,
            metadata={"key": "value"}
        )

        assert result.semantic_score == 0.9
        assert result.graph_relevance == 0.8
        assert result.rrf_score == 0.015
        assert result.metadata == {"key": "value"}


class TestHybridRetrievalResponseDataclass:
    """Tests for HybridRetrievalResponse dataclass."""

    def test_hybrid_retrieval_response_creation(self):
        """Should create HybridRetrievalResponse with required fields."""
        response = HybridRetrievalResponse(
            results=[],
            semantic_count=5,
            graph_count=3,
            total_tokens_estimate=100
        )

        assert response.results == []
        assert response.semantic_count == 5
        assert response.graph_count == 3
        assert response.total_tokens_estimate == 100
