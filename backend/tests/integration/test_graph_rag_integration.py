"""
Integration tests for Graph RAG API endpoint.

Tests the /api/contracts/graph-query endpoint with mocked GraphRAGWorkflow.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_graph_rag_workflow():
    """Mock GraphRAGWorkflow for testing."""
    workflow = AsyncMock()

    # Mock successful response
    workflow.run.return_value = {
        "answer": "The payment terms are net 30 days from invoice date.",
        "sources": [
            {
                "index": 1,
                "type": "semantic",
                "contract_id": "test-contract-123",
                "score": 0.92,
                "preview": "Payment shall be made within thirty (30) days of invoice date..."
            },
            {
                "index": 2,
                "type": "graph",
                "contract_id": "test-contract-123",
                "score": 0.85,
                "preview": "Company: Acme Corp, Role: Vendor"
            }
        ],
        "retrieval_response": MagicMock(
            semantic_count=3,
            graph_count=2
        ),
        "cost": 0.0015,
        "error": None
    }

    return workflow


@pytest.mark.asyncio
async def test_graph_query_returns_answer_with_sources(test_client, mock_graph_rag_workflow):
    """Should return answer with source attribution."""
    with patch("backend.main.graph_rag_workflow", mock_graph_rag_workflow):
        response = test_client.post(
            "/api/contracts/graph-query",
            json={
                "query": "What are the payment terms?",
                "contract_id": "test-contract-123",
                "n_results": 5
            }
        )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "answer" in data
    assert "sources" in data
    assert "semantic_results" in data
    assert "graph_results" in data
    assert "cost" in data

    # Verify answer content
    assert data["answer"] == "The payment terms are net 30 days from invoice date."

    # Verify sources
    assert len(data["sources"]) == 2
    assert data["sources"][0]["type"] == "semantic"
    assert data["sources"][1]["type"] == "graph"

    # Verify counts
    assert data["semantic_results"] == 3
    assert data["graph_results"] == 2

    # Verify cost
    assert data["cost"] == 0.0015

    # Verify workflow was called correctly
    mock_graph_rag_workflow.run.assert_called_once_with(
        query="What are the payment terms?",
        contract_id="test-contract-123",
        n_results=5,
        include_sources=True
    )


@pytest.mark.asyncio
async def test_graph_query_global_search(test_client, mock_graph_rag_workflow):
    """Should search across all contracts when contract_id is None."""
    with patch("backend.main.graph_rag_workflow", mock_graph_rag_workflow):
        response = test_client.post(
            "/api/contracts/graph-query",
            json={
                "query": "Find all liability clauses",
                "contract_id": None,
                "n_results": 10
            }
        )

    assert response.status_code == 200

    # Verify workflow was called with None for contract_id
    mock_graph_rag_workflow.run.assert_called_once_with(
        query="Find all liability clauses",
        contract_id=None,
        n_results=10,
        include_sources=True
    )


@pytest.mark.asyncio
async def test_graph_query_validates_min_length(test_client):
    """Should reject queries that are too short."""
    response = test_client.post(
        "/api/contracts/graph-query",
        json={
            "query": "ab",  # Too short (min_length=3)
            "n_results": 5
        }
    )

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_graph_query_validates_max_length(test_client):
    """Should reject queries that are too long."""
    response = test_client.post(
        "/api/contracts/graph-query",
        json={
            "query": "x" * 1001,  # Too long (max_length=1000)
            "n_results": 5
        }
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_graph_query_validates_n_results_range(test_client):
    """Should reject n_results outside valid range."""
    # Test n_results too small
    response = test_client.post(
        "/api/contracts/graph-query",
        json={
            "query": "valid query",
            "n_results": 0  # Below minimum (ge=1)
        }
    )
    assert response.status_code == 422

    # Test n_results too large
    response = test_client.post(
        "/api/contracts/graph-query",
        json={
            "query": "valid query",
            "n_results": 21  # Above maximum (le=20)
        }
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_graph_query_uses_defaults(test_client, mock_graph_rag_workflow):
    """Should use default values when optional params not provided."""
    with patch("backend.main.graph_rag_workflow", mock_graph_rag_workflow):
        response = test_client.post(
            "/api/contracts/graph-query",
            json={
                "query": "What is the governing law?"
                # contract_id and n_results not provided
            }
        )

    assert response.status_code == 200

    # Verify defaults were used
    mock_graph_rag_workflow.run.assert_called_once_with(
        query="What is the governing law?",
        contract_id=None,  # Default
        n_results=5,  # Default
        include_sources=True
    )


@pytest.mark.asyncio
async def test_graph_query_handles_workflow_error(test_client):
    """Should return 500 when workflow returns error."""
    mock_workflow = AsyncMock()
    mock_workflow.run.return_value = {
        "answer": None,
        "sources": [],
        "retrieval_response": MagicMock(semantic_count=0, graph_count=0),
        "cost": 0.0,
        "error": "Failed to retrieve context from vector store"
    }

    with patch("backend.main.graph_rag_workflow", mock_workflow):
        response = test_client.post(
            "/api/contracts/graph-query",
            json={
                "query": "What are the payment terms?",
                "contract_id": "test-contract-123"
            }
        )

    assert response.status_code == 500
    data = response.json()
    assert data["detail"]["error"] == "GraphRAGError"
    assert "Failed to retrieve context" in data["detail"]["message"]


@pytest.mark.asyncio
async def test_graph_query_handles_workflow_exception(test_client):
    """Should return 500 when workflow raises exception."""
    mock_workflow = AsyncMock()
    mock_workflow.run.side_effect = Exception("Database connection failed")

    with patch("backend.main.graph_rag_workflow", mock_workflow):
        response = test_client.post(
            "/api/contracts/graph-query",
            json={
                "query": "What are the payment terms?",
                "contract_id": "test-contract-123"
            }
        )

    assert response.status_code == 500
    data = response.json()
    assert data["detail"]["error"] == "GraphRAGError"


@pytest.mark.asyncio
async def test_graph_query_service_unavailable(test_client):
    """Should return 503 when workflow is not initialized."""
    with patch("backend.main.graph_rag_workflow", None):
        response = test_client.post(
            "/api/contracts/graph-query",
            json={
                "query": "What are the payment terms?",
                "contract_id": "test-contract-123"
            }
        )

    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["error"] == "ServiceUnavailable"
    assert "not initialized" in data["detail"]["message"]


@pytest.mark.asyncio
async def test_graph_query_with_multiple_sources(test_client, mock_graph_rag_workflow):
    """Should handle responses with multiple sources correctly."""
    # Update mock to return more sources
    mock_graph_rag_workflow.run.return_value["sources"] = [
        {"index": i, "type": "semantic" if i % 2 == 0 else "graph",
         "contract_id": f"contract-{i}", "score": 0.9 - (i * 0.1),
         "preview": f"Source {i} preview..."}
        for i in range(1, 11)
    ]
    mock_graph_rag_workflow.run.return_value["retrieval_response"] = MagicMock(
        semantic_count=5,
        graph_count=5
    )

    with patch("backend.main.graph_rag_workflow", mock_graph_rag_workflow):
        response = test_client.post(
            "/api/contracts/graph-query",
            json={
                "query": "Complex query with many results",
                "n_results": 10
            }
        )

    assert response.status_code == 200
    data = response.json()

    # Verify all sources returned
    assert len(data["sources"]) == 10
    assert data["semantic_results"] == 5
    assert data["graph_results"] == 5

    # Verify sources have correct structure
    for source in data["sources"]:
        assert "index" in source
        assert "type" in source
        assert "contract_id" in source
        assert "score" in source
        assert "preview" in source
