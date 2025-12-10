"""
Unit tests for ContractComparisonService.

Tests comparison logic, prompt building, error handling, and cost tracking
for the contract comparison feature.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


class TestContractComparisonService:
    """Unit tests for ContractComparisonService class."""

    @pytest.fixture
    def mock_gemini_router(self):
        """Mock GeminiRouter."""
        router = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "Comparison analysis text"
        mock_result.cost = 0.001
        router.generate_with_expertise = AsyncMock(return_value=mock_result)
        return router

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store with semantic search."""
        store = MagicMock()
        store.semantic_search = AsyncMock(return_value=[
            {"text": "Sample contract text from section 1", "metadata": {}},
            {"text": "Sample contract text from section 2", "metadata": {}},
        ])
        return store

    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store."""
        store = MagicMock()

        # Create mock contract graphs
        def create_mock_graph(contract_id, filename):
            mock_contract = MagicMock()
            mock_contract.contract_id = contract_id
            mock_contract.filename = filename

            mock_graph = MagicMock()
            mock_graph.contract = mock_contract
            return mock_graph

        store.get_contract_relationships = AsyncMock(side_effect=lambda cid: {
            "contract-a": create_mock_graph("contract-a", "contract_a.pdf"),
            "contract-b": create_mock_graph("contract-b", "contract_b.pdf"),
        }.get(cid))

        return store

    @pytest.fixture
    def comparison_service(self, mock_gemini_router, mock_vector_store, mock_graph_store):
        """Create comparison service with mocked dependencies."""
        from backend.services.contract_comparison import ContractComparisonService
        return ContractComparisonService(
            gemini_router=mock_gemini_router,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store
        )

    @pytest.mark.asyncio
    async def test_compare_returns_correct_structure(self, comparison_service):
        """Test that compare returns expected response structure."""
        result = await comparison_service.compare(
            contract_id_a="contract-a",
            contract_id_b="contract-b",
            aspects=["payment_terms"]
        )

        assert "contract_a" in result
        assert "contract_b" in result
        assert "comparisons" in result
        assert "total_cost" in result

        assert result["contract_a"]["id"] == "contract-a"
        assert result["contract_a"]["filename"] == "contract_a.pdf"
        assert result["contract_b"]["id"] == "contract-b"
        assert result["contract_b"]["filename"] == "contract_b.pdf"

    @pytest.mark.asyncio
    async def test_compare_processes_all_aspects(self, comparison_service, mock_gemini_router):
        """Test that all aspects are processed."""
        aspects = ["payment_terms", "liability", "termination"]

        result = await comparison_service.compare(
            contract_id_a="contract-a",
            contract_id_b="contract-b",
            aspects=aspects
        )

        # Should have one comparison per aspect
        assert len(result["comparisons"]) == 3

        # Gemini should be called once per aspect
        assert mock_gemini_router.generate_with_expertise.call_count == 3

        # Each comparison should have the aspect name
        aspect_names = [c["aspect"] for c in result["comparisons"]]
        assert aspect_names == aspects

    @pytest.mark.asyncio
    async def test_compare_uses_contract_reviewer_expertise(
        self, comparison_service, mock_gemini_router
    ):
        """Test that CONTRACT_REVIEWER expertise is used."""
        from backend.services.gemini_router import LegalExpertise

        await comparison_service.compare(
            contract_id_a="contract-a",
            contract_id_b="contract-b",
            aspects=["payment_terms"]
        )

        call_args = mock_gemini_router.generate_with_expertise.call_args
        assert call_args.kwargs["expertise"] == LegalExpertise.CONTRACT_REVIEWER

    @pytest.mark.asyncio
    async def test_compare_accumulates_costs(self, comparison_service, mock_gemini_router):
        """Test that costs are accumulated across aspects."""
        # Each call costs 0.001
        result = await comparison_service.compare(
            contract_id_a="contract-a",
            contract_id_b="contract-b",
            aspects=["payment_terms", "liability", "termination"]
        )

        # 3 aspects * 0.001 = 0.003
        assert result["total_cost"] == pytest.approx(0.003)

    @pytest.mark.asyncio
    async def test_compare_raises_for_missing_contract_a(
        self, mock_gemini_router, mock_vector_store, mock_graph_store
    ):
        """Test ValueError when contract A not found."""
        mock_graph_store.get_contract_relationships = AsyncMock(side_effect=lambda cid: {
            "contract-b": MagicMock(),
        }.get(cid))

        from backend.services.contract_comparison import ContractComparisonService
        service = ContractComparisonService(
            gemini_router=mock_gemini_router,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store
        )

        with pytest.raises(ValueError) as exc_info:
            await service.compare(
                contract_id_a="nonexistent",
                contract_id_b="contract-b",
                aspects=["payment_terms"]
            )

        assert "nonexistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_compare_raises_for_missing_contract_b(
        self, mock_gemini_router, mock_vector_store, mock_graph_store
    ):
        """Test ValueError when contract B not found."""
        mock_graph_store.get_contract_relationships = AsyncMock(side_effect=lambda cid: {
            "contract-a": MagicMock(),
        }.get(cid))

        from backend.services.contract_comparison import ContractComparisonService
        service = ContractComparisonService(
            gemini_router=mock_gemini_router,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store
        )

        with pytest.raises(ValueError) as exc_info:
            await service.compare(
                contract_id_a="contract-a",
                contract_id_b="nonexistent",
                aspects=["payment_terms"]
            )

        assert "nonexistent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_compare_performs_semantic_search_for_each_contract(
        self, comparison_service, mock_vector_store
    ):
        """Test that semantic search is performed for both contracts."""
        await comparison_service.compare(
            contract_id_a="contract-a",
            contract_id_b="contract-b",
            aspects=["payment_terms"]
        )

        # Should have 2 calls (one per contract for the aspect)
        assert mock_vector_store.semantic_search.call_count == 2

        calls = mock_vector_store.semantic_search.call_args_list
        contract_ids = [call.kwargs['contract_id'] for call in calls]
        assert "contract-a" in contract_ids
        assert "contract-b" in contract_ids


class TestBuildComparisonPrompt:
    """Unit tests for _build_comparison_prompt method."""

    @pytest.fixture
    def comparison_service(self):
        """Create comparison service for prompt testing."""
        from backend.services.contract_comparison import ContractComparisonService
        return ContractComparisonService(
            gemini_router=MagicMock(),
            vector_store=MagicMock(),
            graph_store=MagicMock()
        )

    def test_prompt_includes_aspect(self, comparison_service):
        """Test that prompt includes the aspect being compared."""
        prompt = comparison_service._build_comparison_prompt(
            aspect="payment_terms",
            contract_a_name="contract_a.pdf",
            contract_b_name="contract_b.pdf",
            chunks_a=[{"text": "A text"}],
            chunks_b=[{"text": "B text"}]
        )

        assert "payment_terms" in prompt

    def test_prompt_includes_contract_names(self, comparison_service):
        """Test that prompt includes both contract filenames."""
        prompt = comparison_service._build_comparison_prompt(
            aspect="liability",
            contract_a_name="vendor_agreement.pdf",
            contract_b_name="service_contract.pdf",
            chunks_a=[{"text": "A text"}],
            chunks_b=[{"text": "B text"}]
        )

        assert "vendor_agreement.pdf" in prompt
        assert "service_contract.pdf" in prompt

    def test_prompt_includes_chunk_text(self, comparison_service):
        """Test that prompt includes text from chunks."""
        prompt = comparison_service._build_comparison_prompt(
            aspect="termination",
            contract_a_name="a.pdf",
            contract_b_name="b.pdf",
            chunks_a=[{"text": "Termination clause text from contract A"}],
            chunks_b=[{"text": "Termination clause text from contract B"}]
        )

        assert "Termination clause text from contract A" in prompt
        assert "Termination clause text from contract B" in prompt

    def test_prompt_truncates_long_chunks(self, comparison_service):
        """Test that chunks are truncated to 500 characters."""
        long_text = "A" * 1000

        prompt = comparison_service._build_comparison_prompt(
            aspect="indemnification",
            contract_a_name="a.pdf",
            contract_b_name="b.pdf",
            chunks_a=[{"text": long_text}],
            chunks_b=[{"text": "Short text"}]
        )

        # Full 1000-char text should not be in prompt
        assert long_text not in prompt
        # But truncated version should be
        assert "A" * 500 in prompt

    def test_prompt_handles_empty_chunks_a(self, comparison_service):
        """Test prompt generation when contract A has no chunks."""
        prompt = comparison_service._build_comparison_prompt(
            aspect="payment",
            contract_a_name="a.pdf",
            contract_b_name="b.pdf",
            chunks_a=[],
            chunks_b=[{"text": "B has content"}]
        )

        assert "[No relevant sections found for this aspect]" in prompt
        assert "B has content" in prompt

    def test_prompt_handles_empty_chunks_b(self, comparison_service):
        """Test prompt generation when contract B has no chunks."""
        prompt = comparison_service._build_comparison_prompt(
            aspect="payment",
            contract_a_name="a.pdf",
            contract_b_name="b.pdf",
            chunks_a=[{"text": "A has content"}],
            chunks_b=[]
        )

        assert "A has content" in prompt
        assert "[No relevant sections found for this aspect]" in prompt

    def test_prompt_includes_comparison_instructions(self, comparison_service):
        """Test that prompt includes structured comparison instructions."""
        prompt = comparison_service._build_comparison_prompt(
            aspect="liability",
            contract_a_name="a.pdf",
            contract_b_name="b.pdf",
            chunks_a=[{"text": "A"}],
            chunks_b=[{"text": "B"}]
        )

        # Should include key sections
        assert "Key Differences" in prompt
        assert "Risk Implications" in prompt
        assert "Recommendation" in prompt

    def test_prompt_numbers_multiple_chunks(self, comparison_service):
        """Test that multiple chunks are numbered."""
        prompt = comparison_service._build_comparison_prompt(
            aspect="payment",
            contract_a_name="a.pdf",
            contract_b_name="b.pdf",
            chunks_a=[
                {"text": "First section"},
                {"text": "Second section"},
                {"text": "Third section"}
            ],
            chunks_b=[{"text": "B content"}]
        )

        assert "Section 1:" in prompt
        assert "Section 2:" in prompt
        assert "Section 3:" in prompt


class TestCompareContractsEndpoint:
    """Unit tests for POST /api/contracts/compare endpoint."""

    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store."""
        store = MagicMock()

        def create_mock_graph(contract_id, filename):
            mock_contract = MagicMock()
            mock_contract.contract_id = contract_id
            mock_contract.filename = filename

            mock_graph = MagicMock()
            mock_graph.contract = mock_contract
            return mock_graph

        store.get_contract_relationships = AsyncMock(side_effect=lambda cid: {
            "contract-a": create_mock_graph("contract-a", "a.pdf"),
            "contract-b": create_mock_graph("contract-b", "b.pdf"),
        }.get(cid))

        return store

    @pytest.fixture
    def mock_qa_workflow(self):
        """Mock QA workflow with gemini_router."""
        workflow = MagicMock()
        workflow.gemini_router = MagicMock()

        mock_result = MagicMock()
        mock_result.text = "Analysis"
        mock_result.cost = 0.001
        workflow.gemini_router.generate_with_expertise = AsyncMock(return_value=mock_result)

        return workflow

    @pytest.mark.asyncio
    async def test_endpoint_returns_404_for_missing_contract_a(self, mock_graph_store):
        """Test that 404 is returned when contract A doesn't exist."""
        from fastapi import HTTPException
        from backend.models.schemas import ContractComparisonRequest

        mock_graph_store.get_contract_relationships = AsyncMock(return_value=None)

        with patch('backend.main.graph_store', mock_graph_store):
            with patch('backend.main.qa_workflow', MagicMock()):
                from backend.main import compare_contracts

                request = ContractComparisonRequest(
                    contract_id_a="nonexistent",
                    contract_id_b="contract-b"
                )

                with pytest.raises(HTTPException) as exc_info:
                    await compare_contracts(request)

                assert exc_info.value.status_code == 404
                assert "nonexistent" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_endpoint_returns_404_for_missing_contract_b(self, mock_graph_store):
        """Test that 404 is returned when contract B doesn't exist."""
        from fastapi import HTTPException
        from backend.models.schemas import ContractComparisonRequest

        # A exists, B doesn't
        mock_graph_store.get_contract_relationships = AsyncMock(side_effect=lambda cid:
            MagicMock() if cid == "contract-a" else None
        )

        with patch('backend.main.graph_store', mock_graph_store):
            with patch('backend.main.qa_workflow', MagicMock()):
                from backend.main import compare_contracts

                request = ContractComparisonRequest(
                    contract_id_a="contract-a",
                    contract_id_b="nonexistent"
                )

                with pytest.raises(HTTPException) as exc_info:
                    await compare_contracts(request)

                assert exc_info.value.status_code == 404
                assert "nonexistent" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_endpoint_returns_503_when_qa_not_initialized(self):
        """Test that 503 is returned when QA workflow not initialized."""
        from fastapi import HTTPException
        from backend.models.schemas import ContractComparisonRequest

        with patch('backend.main.qa_workflow', None):
            from backend.main import compare_contracts

            request = ContractComparisonRequest(
                contract_id_a="contract-a",
                contract_id_b="contract-b"
            )

            with pytest.raises(HTTPException) as exc_info:
                await compare_contracts(request)

            assert exc_info.value.status_code == 503
            assert "not initialized" in str(exc_info.value.detail).lower()
