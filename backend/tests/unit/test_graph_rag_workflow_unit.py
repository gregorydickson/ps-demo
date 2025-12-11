"""
Unit tests for GraphRAGWorkflow.

Following TDD methodology: Tests written first to define expected behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.workflows.graph_rag_workflow import GraphRAGWorkflow, GraphRAGState
from backend.services.hybrid_retriever import HybridRetrievalResponse, RetrievalResult
from backend.services.gemini_router import GenerationResult


class TestGraphRAGWorkflow:
    """Tests for GraphRAGWorkflow."""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock ContractVectorStore."""
        store = MagicMock()
        store.semantic_search = AsyncMock(return_value=[
            {
                "id": "1",
                "text": "Payment terms: Net 30 days after invoice",
                "metadata": {"contract_id": "c1", "section": "Payment"},
                "relevance_score": 0.9
            },
            {
                "id": "2",
                "text": "Termination requires 30 days notice",
                "metadata": {"contract_id": "c1", "section": "Termination"},
                "relevance_score": 0.7
            }
        ])
        return store

    @pytest.fixture
    def mock_graph_store(self):
        """Mock ContractGraphStore."""
        store = MagicMock()
        store.graph = MagicMock()
        return store

    @pytest.fixture
    def mock_gemini_router(self):
        """Mock GeminiRouter."""
        router = AsyncMock()
        router.generate = AsyncMock(return_value=GenerationResult(
            text="The payment terms are Net 30 days after invoice as stated in [Source 1].",
            model_name="gemini-2.5-flash-lite",
            input_tokens=150,
            output_tokens=25,
            thinking_tokens=0,
            total_tokens=175,
            cost=0.00002,
            generation_time_ms=500.0
        ))
        return router

    @pytest.fixture
    def mock_cost_tracker(self):
        """Mock CostTracker."""
        tracker = AsyncMock()
        tracker.track_cost = AsyncMock()
        return tracker

    @pytest.fixture
    def mock_hybrid_retriever(self):
        """Mock HybridRetriever with pre-configured response."""
        retriever = AsyncMock()
        retriever.retrieve = AsyncMock(return_value=HybridRetrievalResponse(
            results=[
                RetrievalResult(
                    contract_id="c1",
                    content="Payment terms: Net 30 days after invoice",
                    source="semantic",
                    semantic_score=0.9,
                    graph_relevance=None,
                    rrf_score=0.016,
                    metadata={"section": "Payment"}
                ),
                RetrievalResult(
                    contract_id="c1",
                    content="Party: Acme Corp (Role: Vendor)",
                    source="graph",
                    semantic_score=None,
                    graph_relevance=0.7,
                    rrf_score=0.012,
                    metadata={"type": "company"}
                ),
                RetrievalResult(
                    contract_id="c1",
                    content="Risk (high): No liability cap specified",
                    source="graph",
                    semantic_score=None,
                    graph_relevance=0.9,
                    rrf_score=0.015,
                    metadata={"type": "risk"}
                )
            ],
            semantic_count=2,
            graph_count=2,
            total_tokens_estimate=200
        ))
        return retriever

    @pytest.fixture
    def workflow(self, mock_vector_store, mock_graph_store, mock_gemini_router, mock_cost_tracker):
        """Create GraphRAGWorkflow with mocked dependencies."""
        workflow = GraphRAGWorkflow(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            gemini_router=mock_gemini_router,
            cost_tracker=mock_cost_tracker
        )
        return workflow

    @pytest.mark.asyncio
    async def test_workflow_initialization(self, workflow):
        """Should initialize with all required components."""
        assert workflow.vector_store is not None
        assert workflow.graph_store is not None
        assert workflow.gemini_router is not None
        assert workflow.cost_tracker is not None
        assert workflow.hybrid_retriever is not None
        assert workflow.graph_retriever is not None

    @pytest.mark.asyncio
    async def test_run_returns_complete_state(
        self,
        workflow,
        mock_hybrid_retriever,
        mock_gemini_router
    ):
        """Should execute full workflow and return complete state."""
        # Patch hybrid_retriever on the workflow instance
        workflow.hybrid_retriever = mock_hybrid_retriever

        result = await workflow.run(
            query="What are the payment terms?",
            contract_id="c1",
            n_results=5,
            include_sources=True
        )

        # Assert state structure
        assert isinstance(result, dict)
        assert "contract_id" in result
        assert "query" in result
        assert "retrieval_response" in result
        assert "context_text" in result
        assert "answer" in result
        assert "sources" in result
        assert "cost" in result
        assert "error" in result

        # Assert values
        assert result["contract_id"] == "c1"
        assert result["query"] == "What are the payment terms?"
        assert result["answer"] is not None
        assert result["error"] is None
        assert result["cost"] > 0

    @pytest.mark.asyncio
    async def test_run_with_global_search(
        self,
        workflow,
        mock_hybrid_retriever,
        mock_gemini_router
    ):
        """Should support global search when contract_id is None."""
        workflow.hybrid_retriever = mock_hybrid_retriever

        result = await workflow.run(
            query="Find all liability clauses",
            contract_id=None,  # Global search
            n_results=10
        )

        assert result["contract_id"] is None
        assert result["answer"] is not None
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_retrieve_step_calls_hybrid_retriever(
        self,
        workflow,
        mock_hybrid_retriever
    ):
        """_retrieve should call hybrid_retriever with correct parameters."""
        workflow.hybrid_retriever = mock_hybrid_retriever

        state: GraphRAGState = {
            "contract_id": "c1",
            "query": "What are payment terms?",
            "retrieval_response": None,
            "context_text": "",
            "answer": None,
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        result = await workflow._retrieve(state, n_results=5)

        # Verify hybrid retriever was called
        mock_hybrid_retriever.retrieve.assert_called_once()
        call_args = mock_hybrid_retriever.retrieve.call_args

        assert call_args.kwargs["query"] == "What are payment terms?"
        assert call_args.kwargs["contract_id"] == "c1"
        assert call_args.kwargs["n_semantic"] == 5
        assert call_args.kwargs["n_graph"] == 3
        assert call_args.kwargs["include_companies"] is True
        assert call_args.kwargs["include_risks"] is True

        # Verify state was updated
        assert result["retrieval_response"] is not None

    @pytest.mark.asyncio
    async def test_format_context_creates_source_sections(self, workflow):
        """_format_context should format results with source attribution."""
        state: GraphRAGState = {
            "contract_id": "c1",
            "query": "test query",
            "retrieval_response": HybridRetrievalResponse(
                results=[
                    RetrievalResult(
                        contract_id="c1",
                        content="Payment terms content",
                        source="semantic",
                        semantic_score=0.9,
                        rrf_score=0.016,
                        metadata={}
                    ),
                    RetrievalResult(
                        contract_id="c1",
                        content="Company: Acme",
                        source="graph",
                        graph_relevance=0.7,
                        rrf_score=0.012,
                        metadata={}
                    )
                ],
                semantic_count=1,
                graph_count=1,
                total_tokens_estimate=100
            ),
            "context_text": "",
            "answer": None,
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        result = workflow._format_context(state)

        # Check context_text was populated
        assert result["context_text"] != ""
        assert "[Source 1 - Document]" in result["context_text"]
        assert "[Source 2 - Knowledge Graph]" in result["context_text"]
        assert "Payment terms content" in result["context_text"]
        assert "Company: Acme" in result["context_text"]

    @pytest.mark.asyncio
    async def test_format_context_handles_empty_response(self, workflow):
        """_format_context should handle empty retrieval response."""
        state: GraphRAGState = {
            "contract_id": "c1",
            "query": "test query",
            "retrieval_response": None,
            "context_text": "",
            "answer": None,
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        result = workflow._format_context(state)

        assert result["context_text"] == ""

    @pytest.mark.asyncio
    async def test_generate_step_uses_simple_complexity(
        self,
        workflow,
        mock_gemini_router
    ):
        """_generate should use TaskComplexity.SIMPLE for cost optimization."""
        from backend.services.gemini_router import TaskComplexity

        state: GraphRAGState = {
            "contract_id": "c1",
            "query": "What are payment terms?",
            "retrieval_response": None,
            "context_text": "Payment terms: Net 30",
            "answer": None,
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        result = await workflow._generate(state)

        # Verify generate was called with SIMPLE complexity
        mock_gemini_router.generate.assert_called_once()
        call_args = mock_gemini_router.generate.call_args

        assert call_args.kwargs["complexity"] == TaskComplexity.SIMPLE
        assert call_args.kwargs["max_tokens"] == 1024

        # Verify state was updated
        assert result["answer"] is not None
        assert result["cost"] > 0

    @pytest.mark.asyncio
    async def test_generate_includes_context_and_query_in_prompt(
        self,
        workflow,
        mock_gemini_router
    ):
        """_generate should include context and query in prompt."""
        state: GraphRAGState = {
            "contract_id": "c1",
            "query": "What are the payment terms?",
            "retrieval_response": None,
            "context_text": "[Source 1]\nPayment: Net 30 days",
            "answer": None,
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        await workflow._generate(state)

        # Check prompt includes context and query
        mock_gemini_router.generate.assert_called_once()
        call_args = mock_gemini_router.generate.call_args
        prompt = call_args.kwargs["prompt"]

        assert "Payment: Net 30 days" in prompt
        assert "What are the payment terms?" in prompt
        assert "CONTEXT:" in prompt
        assert "QUESTION:" in prompt

    @pytest.mark.asyncio
    async def test_generate_tracks_cost(
        self,
        workflow,
        mock_gemini_router,
        mock_cost_tracker
    ):
        """_generate should track cost when cost_tracker is available."""
        state: GraphRAGState = {
            "contract_id": "c1",
            "query": "test query",
            "retrieval_response": None,
            "context_text": "test context",
            "answer": None,
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        await workflow._generate(state)

        # Verify cost tracker was called
        mock_cost_tracker.track_cost.assert_called_once()
        call_args = mock_cost_tracker.track_cost.call_args

        assert call_args.kwargs["model"] == "gemini-2.5-flash-lite"
        assert call_args.kwargs["input_tokens"] == 150
        assert call_args.kwargs["output_tokens"] == 25
        assert call_args.kwargs["cost"] == 0.00002

    @pytest.mark.asyncio
    async def test_extract_sources_builds_source_list(self, workflow):
        """_extract_sources should build list of source attributions."""
        state: GraphRAGState = {
            "contract_id": "c1",
            "query": "test query",
            "retrieval_response": HybridRetrievalResponse(
                results=[
                    RetrievalResult(
                        contract_id="c1",
                        content="Payment terms: Net 30 days after invoice date",
                        source="semantic",
                        semantic_score=0.9,
                        rrf_score=0.016,
                        metadata={"section": "Payment"}
                    ),
                    RetrievalResult(
                        contract_id="c1",
                        content="Party: Acme Corporation (Role: Vendor)",
                        source="graph",
                        graph_relevance=0.7,
                        rrf_score=0.012,
                        metadata={"type": "company"}
                    )
                ],
                semantic_count=1,
                graph_count=1,
                total_tokens_estimate=100
            ),
            "context_text": "",
            "answer": "Answer text",
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        result = workflow._extract_sources(state)

        # Check sources were populated
        assert len(result["sources"]) == 2

        # Check first source
        source1 = result["sources"][0]
        assert source1["index"] == 1
        assert source1["type"] == "semantic"
        assert source1["contract_id"] == "c1"
        assert source1["score"] == 0.016
        assert "Payment terms" in source1["preview"]

        # Check second source
        source2 = result["sources"][1]
        assert source2["index"] == 2
        assert source2["type"] == "graph"
        assert source2["contract_id"] == "c1"
        assert source2["score"] == 0.012
        assert "Acme Corporation" in source2["preview"]

    @pytest.mark.asyncio
    async def test_extract_sources_truncates_long_content(self, workflow):
        """_extract_sources should truncate content longer than 100 chars."""
        long_content = "A" * 150

        state: GraphRAGState = {
            "contract_id": "c1",
            "query": "test",
            "retrieval_response": HybridRetrievalResponse(
                results=[
                    RetrievalResult(
                        contract_id="c1",
                        content=long_content,
                        source="semantic",
                        semantic_score=0.9,
                        rrf_score=0.016,
                        metadata={}
                    )
                ],
                semantic_count=1,
                graph_count=0,
                total_tokens_estimate=50
            ),
            "context_text": "",
            "answer": "Answer",
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        result = workflow._extract_sources(state)

        preview = result["sources"][0]["preview"]
        assert len(preview) == 103  # 100 chars + "..."
        assert preview.endswith("...")

    @pytest.mark.asyncio
    async def test_extract_sources_handles_empty_response(self, workflow):
        """_extract_sources should handle missing retrieval_response."""
        state: GraphRAGState = {
            "contract_id": "c1",
            "query": "test",
            "retrieval_response": None,
            "context_text": "",
            "answer": "Answer",
            "sources": [],
            "cost": 0.0,
            "error": None
        }

        result = workflow._extract_sources(state)

        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_run_handles_errors_gracefully(
        self,
        workflow,
        mock_hybrid_retriever
    ):
        """run should catch exceptions and populate error field."""
        # Make hybrid retriever raise an exception
        mock_hybrid_retriever.retrieve = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        workflow.hybrid_retriever = mock_hybrid_retriever

        result = await workflow.run(
            query="test query",
            contract_id="c1"
        )

        # Should not raise exception, but populate error field
        assert result["error"] is not None
        assert "Database connection failed" in result["error"]
        assert result["answer"] is None

    @pytest.mark.asyncio
    async def test_run_without_sources(
        self,
        workflow,
        mock_hybrid_retriever,
        mock_gemini_router
    ):
        """run with include_sources=False should skip source extraction."""
        workflow.hybrid_retriever = mock_hybrid_retriever

        result = await workflow.run(
            query="test query",
            contract_id="c1",
            include_sources=False
        )

        # Sources should be empty list
        assert result["sources"] == []
        # But answer should still be present
        assert result["answer"] is not None

    @pytest.mark.asyncio
    async def test_workflow_uses_correct_retrieval_parameters(
        self,
        workflow,
        mock_hybrid_retriever
    ):
        """Workflow should pass correct parameters to hybrid retriever."""
        workflow.hybrid_retriever = mock_hybrid_retriever

        await workflow.run(
            query="What are the risks?",
            contract_id="c1",
            n_results=8
        )

        # Verify hybrid retriever was called with correct params
        call_args = mock_hybrid_retriever.retrieve.call_args

        assert call_args.kwargs["n_semantic"] == 8
        assert call_args.kwargs["n_graph"] == 3  # Fixed at 3 per workplan
        assert call_args.kwargs["include_companies"] is True
        assert call_args.kwargs["include_risks"] is True

    @pytest.mark.asyncio
    async def test_full_workflow_integration(
        self,
        workflow,
        mock_hybrid_retriever,
        mock_gemini_router,
        mock_cost_tracker
    ):
        """Test complete workflow with all steps."""
        workflow.hybrid_retriever = mock_hybrid_retriever

        result = await workflow.run(
            query="What are the payment terms and associated risks?",
            contract_id="c1",
            n_results=5,
            include_sources=True
        )

        # Verify all steps completed
        assert result["retrieval_response"] is not None
        assert result["retrieval_response"].semantic_count == 2
        assert result["retrieval_response"].graph_count == 2

        assert result["context_text"] != ""
        assert "[Source 1 - Document]" in result["context_text"]
        assert "[Source 2 - Knowledge Graph]" in result["context_text"]

        assert result["answer"] is not None
        assert len(result["answer"]) > 0

        assert len(result["sources"]) == 3  # 3 results from mock
        assert result["sources"][0]["type"] == "semantic"
        assert result["sources"][1]["type"] == "graph"

        assert result["cost"] > 0
        assert result["error"] is None

        # Verify cost tracking
        mock_cost_tracker.track_cost.assert_called_once()
