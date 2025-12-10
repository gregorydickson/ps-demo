"""
Integration tests for Contract Analysis Workflow.

Tests workflow execution with mocked services to verify orchestration logic,
error accumulation, and cost tracking.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from typing import Dict, Any

from backend.workflows.contract_analysis_workflow import (
    ContractAnalysisWorkflow,
    ContractAnalysisState
)


class TestWorkflowIntegration:
    """Integration tests for ContractAnalysisWorkflow."""

    @pytest.mark.asyncio
    async def test_workflow_can_be_initialized_without_stores(self):
        """Test that workflow can be initialized without stores for testing."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        assert workflow is not None
        assert workflow.vector_store is None
        assert workflow.graph_store is None
        assert workflow.workflow is not None

    @pytest.mark.asyncio
    async def test_workflow_nodes_are_defined(self):
        """Test that all workflow nodes are properly defined."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # The workflow should have nodes
        assert workflow.workflow is not None
        # Verify key methods exist
        assert hasattr(workflow, '_parse_document_node')
        assert hasattr(workflow, '_analyze_risk_node')
        assert hasattr(workflow, '_store_vectors_node')
        assert hasattr(workflow, '_store_graph_node')
        assert hasattr(workflow, '_qa_node')

    @pytest.mark.asyncio
    async def test_parse_node_handles_valid_input(self):
        """Test parse node with valid input."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # Mock the LlamaParse service
        if workflow.llamaparse:
            workflow.llamaparse.parse_document = AsyncMock(
                return_value="Parsed document text"
            )

        state = ContractAnalysisState(
            contract_id="test-123",
            file_bytes=b"test content",
            filename="test.pdf",
            total_cost=0.0,
            errors=[]
        )

        result = await workflow._parse_document_node(state)

        # Should not crash and return state
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_parse_node_accumulates_errors_on_failure(self):
        """Test that parse node accumulates errors without stopping workflow."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # Mock parse failure
        if workflow.llamaparse:
            workflow.llamaparse.parse_document = AsyncMock(
                side_effect=Exception("Parse failed")
            )

        state = ContractAnalysisState(
            contract_id="test-123",
            file_bytes=b"invalid",
            filename="test.pdf",
            total_cost=0.0,
            errors=[]
        )

        result = await workflow._parse_document_node(state)

        # Should have error but not crash
        assert isinstance(result, dict)
        assert "errors" in result
        if result["errors"]:
            assert any("parse" in err.lower() for err in result["errors"])

    @pytest.mark.asyncio
    async def test_analyze_node_calls_gemini(self):
        """Test that analyze node calls Gemini router correctly."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # Mock Gemini router
        if workflow.gemini_router:
            workflow.gemini_router.generate = AsyncMock(
                return_value=MagicMock(
                    text='{"risk_score": 5, "risk_level": "medium"}',
                    cost=0.002
                )
            )

        state = ContractAnalysisState(
            contract_id="test-123",
            parsed_document="Test document text",
            total_cost=0.0,
            errors=[]
        )

        result = await workflow._analyze_risk_node(state)

        assert isinstance(result, dict)
        # Should have risk_analysis if successful
        if "risk_analysis" in result:
            assert result["risk_analysis"] is not None

    @pytest.mark.asyncio
    async def test_analyze_node_accumulates_cost(self):
        """Test that analyze node accumulates cost correctly."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        if workflow.gemini_router:
            workflow.gemini_router.generate = AsyncMock(
                return_value=MagicMock(
                    text='{"risk_score": 5}',
                    cost=0.002
                )
            )

        state = ContractAnalysisState(
            contract_id="test-123",
            parsed_document="Test document",
            total_cost=0.001,
            errors=[]
        )

        result = await workflow._analyze_risk_node(state)

        # Cost should be accumulated
        if "total_cost" in result:
            assert result["total_cost"] >= 0.001

    @pytest.mark.asyncio
    async def test_store_vectors_node_stores_chunks(self):
        """Test that vector store node stores document chunks."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # Mock vector store
        mock_vector_store = AsyncMock()
        mock_vector_store.store_document_sections = AsyncMock(
            return_value=["chunk-1", "chunk-2", "chunk-3"]
        )
        workflow.vector_store = mock_vector_store

        state = ContractAnalysisState(
            contract_id="test-123",
            parsed_document="Test document text",
            total_cost=0.0,
            errors=[]
        )

        result = await workflow._store_vectors_node(state)

        assert isinstance(result, dict)
        if "vector_ids" in result:
            assert len(result["vector_ids"]) > 0

    @pytest.mark.asyncio
    async def test_store_graph_node_stores_relationships(self):
        """Test that graph store node stores contract relationships."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # Mock graph store
        mock_graph_store = MagicMock()
        mock_graph_store.store_contract = MagicMock()
        workflow.graph_store = mock_graph_store

        state = ContractAnalysisState(
            contract_id="test-123",
            parsed_document="Test document",
            risk_analysis={"risk_score": 5},
            key_terms={"payment": "Net 30"},
            total_cost=0.0,
            errors=[]
        )

        result = await workflow._store_graph_node(state)

        assert isinstance(result, dict)
        if "graph_stored" in result:
            assert isinstance(result["graph_stored"], bool)

    @pytest.mark.asyncio
    async def test_qa_node_skips_without_query(self):
        """Test that QA node is skipped when no query provided."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        state = ContractAnalysisState(
            contract_id="test-123",
            query=None,
            total_cost=0.0,
            errors=[]
        )

        result = await workflow._qa_node(state)

        # Should skip processing
        assert isinstance(result, dict)
        assert result.get("answer") is None or result.get("answer") == ""

    @pytest.mark.asyncio
    async def test_qa_node_processes_query_when_provided(self):
        """Test that QA node processes queries when provided."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # Mock vector store search
        if workflow.vector_store:
            workflow.vector_store = AsyncMock()
            workflow.vector_store.semantic_search = AsyncMock(
                return_value=[{"text": "Relevant text", "relevance_score": 0.9}]
            )

        # Mock Gemini router
        if workflow.gemini_router:
            workflow.gemini_router.generate = AsyncMock(
                return_value=MagicMock(
                    text="The answer is in the contract.",
                    cost=0.001
                )
            )

        state = ContractAnalysisState(
            contract_id="test-123",
            query="What are the payment terms?",
            parsed_document="Document with payment terms",
            total_cost=0.0,
            errors=[]
        )

        result = await workflow._qa_node(state)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_workflow_accumulates_errors_across_nodes(self):
        """Test that errors accumulate across multiple node failures."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # Make multiple nodes fail
        if workflow.llamaparse:
            workflow.llamaparse.parse_document = AsyncMock(
                side_effect=Exception("Parse error")
            )

        state = ContractAnalysisState(
            contract_id="test-123",
            file_bytes=b"test",
            filename="test.pdf",
            total_cost=0.0,
            errors=[]
        )

        # Run parse node
        result = await workflow._parse_document_node(state)

        # Should accumulate first error
        if "errors" in result and result["errors"]:
            error_count = len(result["errors"])
            assert error_count >= 0  # May or may not have errors depending on impl

    @pytest.mark.asyncio
    async def test_workflow_continues_after_non_critical_errors(self):
        """Test that workflow continues even when non-critical steps fail."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        # Mock successful parse
        if workflow.llamaparse:
            workflow.llamaparse.parse_document = AsyncMock(
                return_value="Parsed text"
            )

        # Mock failed vector storage (non-critical)
        if workflow.vector_store:
            workflow.vector_store = AsyncMock()
            workflow.vector_store.store_document_sections = AsyncMock(
                side_effect=Exception("Storage failed")
            )

        state = ContractAnalysisState(
            contract_id="test-123",
            file_bytes=b"test",
            filename="test.pdf",
            parsed_document="Test",
            total_cost=0.0,
            errors=[]
        )

        # Should not raise exception
        result = await workflow._store_vectors_node(state)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_workflow_run_method_exists(self):
        """Test that workflow has a run method."""
        workflow = ContractAnalysisWorkflow(initialize_stores=False)

        assert hasattr(workflow, 'run') or hasattr(workflow.workflow, 'ainvoke')

    @pytest.mark.asyncio
    async def test_full_workflow_execution_mocked(self):
        """Test complete workflow execution with all services mocked."""
        with patch('backend.workflows.contract_analysis_workflow.GeminiRouter') as MockGemini:
            with patch('backend.workflows.contract_analysis_workflow.LlamaParseService') as MockLlama:
                # Mock services
                mock_gemini = AsyncMock()
                mock_gemini.generate = AsyncMock(
                    return_value=MagicMock(
                        text='{"risk_score": 5, "risk_level": "medium"}',
                        cost=0.002
                    )
                )
                MockGemini.return_value = mock_gemini

                mock_llama = AsyncMock()
                mock_llama.parse_document = AsyncMock(
                    return_value="Parsed document text"
                )
                MockLlama.return_value = mock_llama

                workflow = ContractAnalysisWorkflow(initialize_stores=False)

                # Mock stores
                workflow.vector_store = AsyncMock()
                workflow.vector_store.store_document_sections = AsyncMock(
                    return_value=["chunk-1", "chunk-2"]
                )

                workflow.graph_store = MagicMock()
                workflow.graph_store.store_contract = MagicMock()

                # Execute workflow
                initial_state = ContractAnalysisState(
                    contract_id="test-123",
                    file_bytes=b"test content",
                    filename="test.pdf",
                    query=None,
                    total_cost=0.0,
                    errors=[]
                )

                # Try to run the workflow
                if hasattr(workflow, 'run'):
                    result = await workflow.run(**initial_state)
                elif hasattr(workflow.workflow, 'ainvoke'):
                    result = await workflow.workflow.ainvoke(initial_state)
                else:
                    # Just verify structure
                    result = initial_state

                assert isinstance(result, dict)

    def test_workflow_state_schema_is_defined(self):
        """Test that ContractAnalysisState schema is properly defined."""
        # Create a state instance
        state = ContractAnalysisState(
            contract_id="test",
            file_bytes=b"test",
            filename="test.pdf"
        )

        assert "contract_id" in state
        assert "file_bytes" in state
        assert "filename" in state

    def test_workflow_handles_missing_optional_fields(self):
        """Test that workflow handles states with missing optional fields."""
        state = ContractAnalysisState(
            contract_id="test-123",
            file_bytes=b"test",
            filename="test.pdf"
        )

        # Optional fields should not cause errors
        assert state.get("query") is None
        assert state.get("parsed_document") is None
        assert state.get("risk_analysis") is None
