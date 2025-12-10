"""
Unit tests for QA Workflow.

Tests the lightweight Q&A workflow that retrieves context and generates answers.
"""

import pytest
from unittest.mock import Mock, AsyncMock


class TestQAWorkflow:
    """Test lightweight Q&A workflow."""

    @pytest.mark.asyncio
    async def test_qa_workflow_retrieves_context(self):
        """Test that QA workflow retrieves relevant context."""
        from backend.workflows.qa_workflow import QAWorkflow

        # Mock dependencies
        mock_vector_store = AsyncMock()
        mock_vector_store.semantic_search = AsyncMock(return_value=[
            {"text": "Section 1 content", "metadata": {}},
            {"text": "Section 2 content", "metadata": {}}
        ])

        mock_router = AsyncMock()
        mock_response = Mock()
        mock_response.text = "Answer to query"
        mock_response.cost = 0.001
        mock_response.model_name = "test-model"
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50
        mock_router.generate = AsyncMock(return_value=mock_response)

        workflow = QAWorkflow(
            vector_store=mock_vector_store,
            gemini_router=mock_router
        )

        result = await workflow.run(
            contract_id="test-123",
            query="What are the terms?"
        )

        assert result["answer"] == "Answer to query"
        assert result["cost"] == 0.001
        assert len(result["context_chunks"]) == 2
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_qa_workflow_handles_no_context(self):
        """Test that QA workflow handles case with no relevant context."""
        from backend.workflows.qa_workflow import QAWorkflow

        mock_vector_store = AsyncMock()
        mock_vector_store.semantic_search = AsyncMock(return_value=[])

        workflow = QAWorkflow(vector_store=mock_vector_store)

        result = await workflow.run(
            contract_id="test-123",
            query="What are the terms?"
        )

        assert "couldn't find relevant information" in result["answer"]
        assert result["cost"] == 0.0
        assert len(result["context_chunks"]) == 0

    @pytest.mark.asyncio
    async def test_qa_workflow_uses_flash_lite(self):
        """Test that QA workflow uses SIMPLE complexity (Flash-Lite)."""
        from backend.workflows.qa_workflow import QAWorkflow, TaskComplexity

        mock_vector_store = AsyncMock()
        mock_vector_store.semantic_search = AsyncMock(return_value=[
            {"text": "Content", "metadata": {}}
        ])

        mock_router = AsyncMock()
        mock_response = Mock()
        mock_response.text = "Answer"
        mock_response.cost = 0.001
        mock_router.generate = AsyncMock(return_value=mock_response)

        workflow = QAWorkflow(
            vector_store=mock_vector_store,
            gemini_router=mock_router
        )

        await workflow.run(
            contract_id="test-123",
            query="Test query"
        )

        # Verify generate was called with SIMPLE complexity
        mock_router.generate.assert_called_once()
        call_kwargs = mock_router.generate.call_args[1]
        assert call_kwargs["complexity"] == TaskComplexity.SIMPLE

    @pytest.mark.asyncio
    async def test_qa_workflow_tracks_cost(self):
        """Test that QA workflow tracks cost if tracker provided."""
        from backend.workflows.qa_workflow import QAWorkflow

        mock_vector_store = AsyncMock()
        mock_vector_store.semantic_search = AsyncMock(return_value=[
            {"text": "Content", "metadata": {}}
        ])

        mock_router = AsyncMock()
        mock_response = Mock()
        mock_response.text = "Answer"
        mock_response.cost = 0.001
        mock_response.model_name = "test-model"
        mock_response.input_tokens = 100
        mock_response.output_tokens = 50
        mock_router.generate = AsyncMock(return_value=mock_response)

        mock_cost_tracker = AsyncMock()

        workflow = QAWorkflow(
            vector_store=mock_vector_store,
            gemini_router=mock_router,
            cost_tracker=mock_cost_tracker
        )

        await workflow.run(
            contract_id="test-123",
            query="Test query"
        )

        # Verify cost was tracked
        mock_cost_tracker.track_api_call.assert_called_once()
