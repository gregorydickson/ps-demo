"""
Unit tests for expert legal instruction integration in workflows.

Verifies that workflows correctly use LegalExpertise personas when making
Gemini API calls, without actually calling external APIs.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from datetime import datetime

from backend.services.gemini_router import LegalExpertise, TaskComplexity
from backend.workflows.contract_analysis_workflow import ContractAnalysisWorkflow
from backend.workflows.qa_workflow import QAWorkflow


@pytest.mark.unit
class TestContractAnalysisExpertIntegration:
    """Test that contract_analysis_workflow uses correct expert personas."""

    @pytest.fixture
    def mock_gemini_router(self):
        """Mock GeminiRouter that tracks generate_with_expertise calls."""
        router = MagicMock()

        # Mock the generate_with_expertise method
        mock_result = MagicMock()
        mock_result.text = '{"risk_score": 5, "risk_level": "medium", "concerning_clauses": [], "key_terms": {"payment_amount": "unknown", "payment_frequency": "unknown", "termination_clause": false, "liability_cap": "unknown"}}'
        mock_result.cost = 0.0001
        mock_result.model_name = "gemini-2.5-flash"
        mock_result.input_tokens = 100
        mock_result.output_tokens = 50

        router.generate_with_expertise = AsyncMock(return_value=mock_result)
        return router

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for workflow tests."""
        store = MagicMock()
        store.store_document_sections = AsyncMock(return_value=["vec1", "vec2"])
        store.semantic_search = AsyncMock(return_value=[
            {"text": "Sample contract text", "metadata": {}}
        ])
        return store

    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store for workflow tests."""
        store = MagicMock()
        store.store_contract = AsyncMock()
        return store

    @pytest.mark.asyncio
    async def test_risk_analysis_uses_risk_analyst_expertise(
        self,
        mock_gemini_router,
        mock_vector_store,
        mock_graph_store
    ):
        """Test that _analyze_risk_node uses RISK_ANALYST expertise."""
        # Create workflow with mocked services
        workflow = ContractAnalysisWorkflow(initialize_stores=False)
        workflow.gemini_router = mock_gemini_router
        workflow.vector_store = mock_vector_store
        workflow.graph_store = mock_graph_store
        workflow.llamaparse = MagicMock()
        workflow.llamaparse.parse_document = AsyncMock(return_value="Parsed contract text")

        # Create initial state
        state = {
            "contract_id": "test-123",
            "file_bytes": b"fake pdf content",
            "filename": "test_contract.pdf",
            "query": None,
            "errors": [],
            "total_cost": 0.0
        }

        # Execute just the analyze_risk node
        state["parsed_document"] = "Parsed contract text"
        result_state = await workflow._analyze_risk_node(state)

        # Verify generate_with_expertise was called with RISK_ANALYST
        mock_gemini_router.generate_with_expertise.assert_called_once()
        call_args = mock_gemini_router.generate_with_expertise.call_args

        # Check that expertise parameter is RISK_ANALYST
        assert call_args.kwargs["expertise"] == LegalExpertise.RISK_ANALYST

        # Check that additional_context includes the filename
        assert "test_contract.pdf" in call_args.kwargs["additional_context"]

        # Verify the prompt is passed
        assert "prompt" in call_args.kwargs
        assert "Analyze this legal contract" in call_args.kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_qa_node_uses_qa_assistant_expertise(
        self,
        mock_vector_store,
        mock_graph_store
    ):
        """Test that _qa_node uses QA_ASSISTANT expertise."""
        # Create a new mock for this test
        mock_gemini_router = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "This is the answer to your question."
        mock_result.cost = 0.00005
        mock_result.model_name = "gemini-2.5-flash-lite"

        mock_gemini_router.generate_with_expertise = AsyncMock(return_value=mock_result)

        # Create workflow with mocked services
        workflow = ContractAnalysisWorkflow(initialize_stores=False)
        workflow.gemini_router = mock_gemini_router
        workflow.vector_store = mock_vector_store
        workflow.graph_store = mock_graph_store

        # Create state with a query
        state = {
            "contract_id": "test-123",
            "filename": "test_contract.pdf",
            "query": "What are the payment terms?",
            "parsed_document": "Contract text",
            "errors": [],
            "total_cost": 0.0
        }

        # Execute the QA node
        result_state = await workflow._qa_node(state)

        # Verify generate_with_expertise was called with QA_ASSISTANT
        mock_gemini_router.generate_with_expertise.assert_called_once()
        call_args = mock_gemini_router.generate_with_expertise.call_args

        # Check that expertise parameter is QA_ASSISTANT
        assert call_args.kwargs["expertise"] == LegalExpertise.QA_ASSISTANT

        # Verify answer was set
        assert result_state["answer"] == "This is the answer to your question."

    @pytest.mark.asyncio
    async def test_qa_node_skips_when_no_query(
        self,
        mock_gemini_router,
        mock_vector_store,
        mock_graph_store
    ):
        """Test that _qa_node skips when no query is provided."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)
        workflow.gemini_router = mock_gemini_router
        workflow.vector_store = mock_vector_store
        workflow.graph_store = mock_graph_store

        # Create state without a query
        state = {
            "contract_id": "test-123",
            "filename": "test_contract.pdf",
            "query": None,  # No query
            "errors": [],
            "total_cost": 0.0
        }

        # Execute the QA node
        result_state = await workflow._qa_node(state)

        # Verify generate_with_expertise was NOT called
        mock_gemini_router.generate_with_expertise.assert_not_called()

        # Verify answer is None
        assert result_state["answer"] is None


@pytest.mark.unit
class TestQAWorkflowExpertIntegration:
    """Test that qa_workflow uses correct expert personas."""

    @pytest.fixture
    def mock_gemini_router(self):
        """Mock GeminiRouter for QA workflow."""
        router = MagicMock()

        mock_result = MagicMock()
        mock_result.text = "The payment terms are Net 30 days."
        mock_result.cost = 0.00004
        mock_result.model_name = "gemini-2.5-flash-lite"

        router.generate_with_expertise = AsyncMock(return_value=mock_result)
        return router

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store."""
        store = MagicMock()
        store.semantic_search = AsyncMock(return_value=[
            {
                "text": "Payment shall be made within 30 days of invoice.",
                "metadata": {"section": "Payment Terms"}
            }
        ])
        return store

    @pytest.mark.asyncio
    async def test_qa_workflow_uses_qa_assistant_expertise(
        self,
        mock_gemini_router,
        mock_vector_store
    ):
        """Test that QAWorkflow uses QA_ASSISTANT expertise."""
        # Create QA workflow with mocked services
        workflow = QAWorkflow(
            vector_store=mock_vector_store,
            gemini_router=mock_gemini_router,
            cost_tracker=None
        )

        # Run the workflow
        result = await workflow.run(
            contract_id="test-contract-123",
            query="What are the payment terms?"
        )

        # Verify generate_with_expertise was called
        mock_gemini_router.generate_with_expertise.assert_called_once()
        call_args = mock_gemini_router.generate_with_expertise.call_args

        # Check that expertise parameter is QA_ASSISTANT
        assert call_args.kwargs["expertise"] == LegalExpertise.QA_ASSISTANT

        # Verify the prompt contains the query
        assert "What are the payment terms?" in call_args.kwargs["prompt"]

        # Verify result contains the answer
        assert result["answer"] == "The payment terms are Net 30 days."
        assert result["cost"] == 0.00004

    @pytest.mark.asyncio
    async def test_qa_workflow_handles_no_context(
        self,
        mock_gemini_router,
        mock_vector_store
    ):
        """Test QA workflow when no context is found."""
        # Mock empty search results
        mock_vector_store.semantic_search = AsyncMock(return_value=[])

        workflow = QAWorkflow(
            vector_store=mock_vector_store,
            gemini_router=mock_gemini_router,
            cost_tracker=None
        )

        # Run the workflow
        result = await workflow.run(
            contract_id="test-contract-123",
            query="What are the payment terms?"
        )

        # Verify generate_with_expertise was NOT called (no context found)
        mock_gemini_router.generate_with_expertise.assert_not_called()

        # Verify the fallback message
        assert "couldn't find relevant information" in result["answer"]


@pytest.mark.unit
class TestExpertSystemInstructions:
    """Test that expert system instructions are properly formatted."""

    def test_all_expertise_types_have_instructions(self):
        """Verify all LegalExpertise enum values have system instructions."""
        from backend.services.gemini_router import LEGAL_SYSTEM_INSTRUCTIONS

        for expertise in LegalExpertise:
            assert expertise in LEGAL_SYSTEM_INSTRUCTIONS
            assert len(LEGAL_SYSTEM_INSTRUCTIONS[expertise]) > 0

    def test_risk_analyst_instruction_content(self):
        """Verify RISK_ANALYST instruction has expected content."""
        from backend.services.gemini_router import LEGAL_SYSTEM_INSTRUCTIONS

        instruction = LEGAL_SYSTEM_INSTRUCTIONS[LegalExpertise.RISK_ANALYST]

        # Check for key phrases that should be in risk analyst instructions
        assert "Senior Legal Risk Analyst" in instruction
        assert "indemnification" in instruction.lower()
        assert "liability" in instruction.lower()
        assert "risk" in instruction.lower()

    def test_qa_assistant_instruction_content(self):
        """Verify QA_ASSISTANT instruction has expected content."""
        from backend.services.gemini_router import LEGAL_SYSTEM_INSTRUCTIONS

        instruction = LEGAL_SYSTEM_INSTRUCTIONS[LegalExpertise.QA_ASSISTANT]

        # Check for key phrases
        assert "Legal Research Assistant" in instruction
        assert "answer questions" in instruction.lower()
        assert "contract" in instruction.lower()

    def test_get_legal_system_instruction_with_context(self):
        """Test that additional_context is properly appended."""
        from backend.services.gemini_router import get_legal_system_instruction

        instruction = get_legal_system_instruction(
            expertise=LegalExpertise.RISK_ANALYST,
            additional_context="Contract: test_agreement.pdf"
        )

        # Verify base instruction is included
        assert "Senior Legal Risk Analyst" in instruction

        # Verify additional context is appended
        assert "ADDITIONAL CONTEXT:" in instruction
        assert "Contract: test_agreement.pdf" in instruction

    def test_get_legal_system_instruction_without_context(self):
        """Test get_legal_system_instruction without additional context."""
        from backend.services.gemini_router import get_legal_system_instruction

        instruction = get_legal_system_instruction(
            expertise=LegalExpertise.QA_ASSISTANT
        )

        # Verify base instruction is included
        assert "Legal Research Assistant" in instruction

        # Verify no ADDITIONAL CONTEXT section
        assert "ADDITIONAL CONTEXT:" not in instruction
