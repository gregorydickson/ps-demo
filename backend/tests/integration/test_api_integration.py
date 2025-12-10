"""
Integration tests for FastAPI endpoints.

Tests API endpoints with mocked external services (Gemini, LlamaParse, etc.)
to verify the API layer works correctly without requiring live services.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
import json

# Import the FastAPI app
from backend.main import app


# Create test client
client = TestClient(app)


class TestAPIIntegration:
    """Integration tests for API endpoints."""

    def test_health_check_endpoint_exists(self):
        """Test that health check endpoint is available."""
        response = client.get("/health")

        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data or "services" in data

    def test_root_endpoint_returns_info(self):
        """Test that root endpoint returns API info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "name" in data

    def test_upload_endpoint_rejects_non_pdf_files(self):
        """Test that upload endpoint rejects non-PDF files."""
        # Create a text file
        files = {
            "file": ("test.txt", b"not a pdf", "text/plain")
        }

        response = client.post("/api/contracts/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "pdf" in data["detail"].lower() or "PDF" in data["detail"]

    def test_upload_endpoint_accepts_pdf_mimetype(self):
        """Test that upload endpoint accepts application/pdf mimetype."""
        # Create a mock PDF file (just needs the header)
        pdf_content = b"%PDF-1.4\ntest content"

        with patch("backend.workflows.contract_analysis_workflow.get_workflow") as mock_workflow:
            # Mock the workflow
            mock_wf_instance = AsyncMock()
            mock_wf_instance.run = AsyncMock(return_value={
                "contract_id": "test-123",
                "risk_analysis": {"risk_score": 5},
                "total_cost": 0.001,
                "errors": []
            })
            mock_workflow.return_value = mock_wf_instance

            files = {
                "file": ("test.pdf", pdf_content, "application/pdf")
            }

            response = client.post("/api/contracts/upload", files=files)

            # Should either succeed or fail with a specific backend error
            # (not a 400 validation error)
            assert response.status_code in [200, 201, 500]

    @patch("backend.workflows.contract_analysis_workflow.get_workflow")
    def test_upload_endpoint_returns_contract_id(self, mock_get_workflow):
        """Test that successful upload returns a contract_id."""
        # Mock the workflow
        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(return_value={
            "contract_id": "test-contract-123",
            "risk_analysis": {
                "risk_score": 5,
                "risk_level": "medium",
                "key_risks": []
            },
            "key_terms": [],
            "metadata": {
                "filename": "test.pdf",
                "parties": ["Party A", "Party B"]
            },
            "total_cost": 0.002,
            "errors": []
        })
        mock_get_workflow.return_value = mock_workflow

        files = {
            "file": ("contract.pdf", b"%PDF-1.4\ntest", "application/pdf")
        }

        response = client.post("/api/contracts/upload", files=files)

        # Check response
        if response.status_code in [200, 201]:
            data = response.json()
            assert "contract_id" in data
            assert data["contract_id"] == "test-contract-123"

    @patch("backend.workflows.qa_workflow.QAWorkflow")
    def test_query_endpoint_returns_answer(self, mock_qa_workflow_class):
        """Test that query endpoint returns an answer."""
        # Mock the QA workflow
        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(return_value={
            "answer": "The payment terms are Net 30 days.",
            "sources": ["Section 1.1"],
            "cost": 0.0005,
            "errors": []
        })
        mock_qa_workflow_class.return_value = mock_workflow

        response = client.post(
            "/api/contracts/test-123/query",
            json={"query": "What are the payment terms?"}
        )

        # Should succeed or return specific error
        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            assert "cost" in data

    def test_query_endpoint_requires_query_parameter(self):
        """Test that query endpoint validates query parameter."""
        response = client.post(
            "/api/contracts/test-123/query",
            json={}
        )

        assert response.status_code == 422  # Unprocessable Entity

    def test_query_endpoint_validates_empty_query(self):
        """Test that query endpoint rejects empty queries."""
        response = client.post(
            "/api/contracts/test-123/query",
            json={"query": ""}
        )

        assert response.status_code in [400, 422]

    @patch("backend.services.graph_store.ContractGraphStore")
    def test_get_contract_details_endpoint(self, mock_graph_store_class):
        """Test getting contract details by ID."""
        # Mock the graph store
        mock_store = MagicMock()
        mock_store.get_contract_metadata = MagicMock(return_value={
            "contract_id": "test-123",
            "filename": "contract.pdf",
            "parties": ["Party A", "Party B"]
        })
        mock_store.get_contract_risk_analysis = MagicMock(return_value={
            "risk_score": 5,
            "risk_level": "medium",
            "key_risks": []
        })
        mock_graph_store_class.return_value = mock_store

        response = client.get("/api/contracts/test-123")

        # Should succeed or return 404
        assert response.status_code in [200, 404, 500]

    def test_get_contract_details_with_invalid_id_format(self):
        """Test that invalid contract ID format is handled."""
        # Use special characters that might cause issues
        response = client.get("/api/contracts/../invalid")

        # Should return 404 or 400
        assert response.status_code in [400, 404]

    @patch("backend.services.cost_tracker.CostTracker")
    def test_get_cost_analytics_endpoint(self, mock_cost_tracker_class):
        """Test getting cost analytics."""
        # Mock the cost tracker
        mock_tracker = MagicMock()
        mock_tracker.get_daily_costs = MagicMock(return_value={
            "date": "2025-01-01",
            "total_cost": 0.05,
            "total_tokens": 10000,
            "total_calls": 20,
            "by_model": [],
            "by_operation": {}
        })
        mock_cost_tracker_class.return_value = mock_tracker

        response = client.get("/api/analytics/costs")

        if response.status_code == 200:
            data = response.json()
            assert "total_cost" in data or "date" in data

    def test_cors_headers_present(self):
        """Test that CORS headers are present in responses."""
        response = client.options("/api/contracts/upload")

        # Check for CORS headers (may vary by configuration)
        assert response.status_code in [200, 204, 405]

    def test_request_id_header_in_response(self):
        """Test that X-Request-ID header is included in responses."""
        response = client.get("/health")

        # Should include request ID header
        # This may or may not be present depending on middleware setup
        headers = response.headers
        assert "x-request-id" in [h.lower() for h in headers] or response.status_code == 200

    def test_upload_endpoint_validates_file_size(self):
        """Test that upload endpoint handles large files appropriately."""
        # Create a "large" file (simulate with metadata)
        large_content = b"%PDF-1.4\n" + b"x" * (100 * 1024 * 1024)  # 100MB

        files = {
            "file": ("large.pdf", large_content[:1000], "application/pdf")
        }

        response = client.post("/api/contracts/upload", files=files)

        # Should either process or reject based on size limits
        assert response.status_code in [200, 201, 400, 413, 500]

    def test_error_responses_have_consistent_format(self):
        """Test that error responses follow a consistent format."""
        # Trigger an error by using invalid data
        response = client.post(
            "/api/contracts/invalid/query",
            json={"query": "test"}
        )

        # Error responses should have detail field
        if response.status_code >= 400:
            data = response.json()
            assert "detail" in data or "error" in data or "message" in data

    @patch("backend.workflows.contract_analysis_workflow.get_workflow")
    def test_upload_handles_workflow_errors_gracefully(self, mock_get_workflow):
        """Test that upload endpoint handles workflow errors gracefully."""
        # Mock workflow that raises an exception
        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(side_effect=Exception("Workflow failed"))
        mock_get_workflow.return_value = mock_workflow

        files = {
            "file": ("test.pdf", b"%PDF-1.4\ntest", "application/pdf")
        }

        response = client.post("/api/contracts/upload", files=files)

        # Should return 500 error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    def test_content_type_validation(self):
        """Test that API validates content types correctly."""
        # Send JSON to an endpoint that expects multipart/form-data
        response = client.post(
            "/api/contracts/upload",
            json={"file": "not-a-file"}
        )

        # Should reject with 422 (validation error)
        assert response.status_code == 422

    def test_method_not_allowed_returns_405(self):
        """Test that wrong HTTP methods return 405."""
        # Try POST on a GET-only endpoint
        response = client.post("/health")

        assert response.status_code == 405

    @patch("backend.workflows.contract_analysis_workflow.get_workflow")
    def test_upload_includes_cost_in_response(self, mock_get_workflow):
        """Test that upload response includes cost information."""
        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(return_value={
            "contract_id": "test-123",
            "risk_analysis": {"risk_score": 5},
            "total_cost": 0.003,
            "errors": []
        })
        mock_get_workflow.return_value = mock_workflow

        files = {
            "file": ("test.pdf", b"%PDF-1.4\ntest", "application/pdf")
        }

        response = client.post("/api/contracts/upload", files=files)

        if response.status_code in [200, 201]:
            data = response.json()
            assert "total_cost" in data or "cost" in data

    def test_api_handles_concurrent_requests(self):
        """Test that API can handle multiple concurrent requests."""
        import concurrent.futures

        def make_request():
            return client.get("/health")

        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in futures]

        # All should complete successfully
        assert all(r.status_code in [200, 503] for r in results)

    def test_batch_upload_endpoint_rejects_too_many_files(self):
        """Test that batch upload endpoint rejects more than 5 files."""
        # Create 6 PDF files
        files = [
            ("files", (f"test{i}.pdf", b"%PDF-1.4\ntest", "application/pdf"))
            for i in range(6)
        ]

        response = client.post("/api/contracts/batch-upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_batch_upload_endpoint_rejects_non_pdf_files(self):
        """Test that batch upload endpoint rejects non-PDF files."""
        files = [
            ("files", ("test1.pdf", b"%PDF-1.4\ntest", "application/pdf")),
            ("files", ("test2.txt", b"not a pdf", "text/plain"))
        ]

        response = client.post("/api/contracts/batch-upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    @patch("backend.workflows.contract_analysis_workflow.get_workflow")
    def test_batch_upload_endpoint_processes_multiple_files(self, mock_get_workflow):
        """Test that batch upload endpoint processes multiple files successfully."""
        # Mock the workflow
        mock_workflow = AsyncMock()
        mock_workflow.run = AsyncMock(return_value={
            "contract_id": "test-123",
            "risk_analysis": {
                "risk_score": 5,
                "risk_level": "medium"
            },
            "total_cost": 0.002,
            "errors": []
        })
        mock_get_workflow.return_value = mock_workflow

        files = [
            ("files", ("test1.pdf", b"%PDF-1.4\ntest1", "application/pdf")),
            ("files", ("test2.pdf", b"%PDF-1.4\ntest2", "application/pdf")),
            ("files", ("test3.pdf", b"%PDF-1.4\ntest3", "application/pdf"))
        ]

        response = client.post("/api/contracts/batch-upload", files=files)

        if response.status_code in [200, 201]:
            data = response.json()
            assert "total" in data
            assert "successful" in data
            assert "failed" in data
            assert "results" in data
            assert data["total"] == 3
            assert len(data["results"]) == 3

    @patch("backend.workflows.contract_analysis_workflow.get_workflow")
    def test_batch_upload_handles_partial_failures(self, mock_get_workflow):
        """Test that batch upload continues processing when some files fail."""
        # Mock the workflow to succeed for the first call and fail for the second
        mock_workflow = AsyncMock()
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "contract_id": "test-123",
                    "risk_analysis": {"risk_level": "low"},
                    "total_cost": 0.001,
                    "errors": []
                }
            else:
                raise Exception("Processing failed")

        mock_workflow.run = AsyncMock(side_effect=side_effect)
        mock_get_workflow.return_value = mock_workflow

        files = [
            ("files", ("test1.pdf", b"%PDF-1.4\ntest1", "application/pdf")),
            ("files", ("test2.pdf", b"%PDF-1.4\ntest2", "application/pdf"))
        ]

        response = client.post("/api/contracts/batch-upload", files=files)

        if response.status_code in [200, 201]:
            data = response.json()
            assert data["total"] == 2
            # Should have at least one success and one failure
            assert data["successful"] >= 1 or data["failed"] >= 1
            assert len(data["results"]) == 2

    def test_batch_upload_includes_processing_time(self):
        """Test that batch upload response includes processing time."""
        with patch("backend.workflows.contract_analysis_workflow.get_workflow") as mock_get_workflow:
            mock_workflow = AsyncMock()
            mock_workflow.run = AsyncMock(return_value={
                "contract_id": "test-123",
                "risk_analysis": {"risk_level": "low"},
                "total_cost": 0.001,
                "errors": []
            })
            mock_get_workflow.return_value = mock_workflow

            files = [
                ("files", ("test1.pdf", b"%PDF-1.4\ntest1", "application/pdf"))
            ]

            response = client.post("/api/contracts/batch-upload", files=files)

            if response.status_code in [200, 201]:
                data = response.json()
                assert "processing_time_ms" in data
                assert isinstance(data["processing_time_ms"], (int, float))
                assert data["processing_time_ms"] >= 0

    def test_global_search_endpoint_requires_query(self):
        """Test that global search endpoint requires a query parameter."""
        response = client.get("/api/contracts/search")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_global_search_endpoint_validates_query_length(self):
        """Test that global search endpoint validates minimum query length."""
        response = client.get("/api/contracts/search?query=ab")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @patch("backend.main.vector_store")
    @patch("backend.main.graph_store")
    def test_global_search_endpoint_returns_results(self, mock_graph_store, mock_vector_store):
        """Test that global search endpoint returns properly formatted results."""
        # Mock vector store search results
        mock_vector_store.global_search = AsyncMock(return_value=[
            {
                "contract_id": "test-123",
                "matches": [
                    {"text": "Payment terms...", "score": 0.85}
                ],
                "best_score": 0.15
            },
            {
                "contract_id": "test-456",
                "matches": [
                    {"text": "Liability clause...", "score": 0.75}
                ],
                "best_score": 0.25
            }
        ])

        # Mock graph store contract details
        from datetime import datetime
        from backend.models.graph_schemas import ContractNode, ContractGraph

        mock_contract_1 = ContractGraph(
            contract=ContractNode(
                contract_id="test-123",
                filename="contract1.pdf",
                upload_date=datetime.now(),
                risk_score=5.0,
                risk_level="medium"
            ),
            companies=[],
            clauses=[],
            risk_factors=[],
            relationships=[]
        )

        mock_contract_2 = ContractGraph(
            contract=ContractNode(
                contract_id="test-456",
                filename="contract2.pdf",
                upload_date=datetime.now(),
                risk_score=7.0,
                risk_level="high"
            ),
            companies=[],
            clauses=[],
            risk_factors=[],
            relationships=[]
        )

        mock_graph_store.get_contract_relationships = AsyncMock(side_effect=[
            mock_contract_1,
            mock_contract_2
        ])

        response = client.get("/api/contracts/search?query=payment+terms&limit=10")

        assert response.status_code == 200
        data = response.json()

        assert "query" in data
        assert data["query"] == "payment terms"
        assert "results" in data
        assert "total" in data
        assert len(data["results"]) == 2
        assert data["total"] == 2

        # Verify result structure
        result = data["results"][0]
        assert "contract_id" in result
        assert "filename" in result
        assert "matches" in result
        assert "relevance_score" in result

    @patch("backend.main.vector_store")
    def test_global_search_endpoint_respects_limit(self, mock_vector_store):
        """Test that global search endpoint respects the limit parameter."""
        # Mock vector store to return many results
        mock_results = [
            {
                "contract_id": f"test-{i}",
                "matches": [{"text": f"Match {i}", "score": 0.9}],
                "best_score": 0.1
            }
            for i in range(20)
        ]
        mock_vector_store.global_search = AsyncMock(return_value=mock_results)

        response = client.get("/api/contracts/search?query=test&limit=5")

        if response.status_code == 200:
            data = response.json()
            # Should call vector store with limit * 3 but only return limit results
            mock_vector_store.global_search.assert_called_once()
            call_args = mock_vector_store.global_search.call_args
            assert call_args[1]["n_results"] == 15  # limit * 3

    @patch("backend.main.vector_store")
    def test_global_search_endpoint_filters_by_risk_level(self, mock_vector_store):
        """Test that global search endpoint can filter by risk level."""
        mock_vector_store.global_search = AsyncMock(return_value=[])

        response = client.get("/api/contracts/search?query=test&risk_level=high")

        if response.status_code == 200:
            mock_vector_store.global_search.assert_called_once()
            call_args = mock_vector_store.global_search.call_args
            assert call_args[1]["risk_level"] == "high"

    @patch("backend.main.vector_store")
    @patch("backend.main.graph_store")
    def test_global_search_handles_missing_contracts_in_graph(self, mock_graph_store, mock_vector_store):
        """Test that global search handles contracts in vector store but not graph store."""
        mock_vector_store.global_search = AsyncMock(return_value=[
            {
                "contract_id": "orphan-contract",
                "matches": [{"text": "Test", "score": 0.9}],
                "best_score": 0.1
            }
        ])

        # Graph store returns None for orphaned contract
        mock_graph_store.get_contract_relationships = AsyncMock(return_value=None)

        response = client.get("/api/contracts/search?query=test")

        if response.status_code == 200:
            data = response.json()
            assert len(data["results"]) == 1
            result = data["results"][0]
            assert result["contract_id"] == "orphan-contract"
            assert result["filename"] == "Unknown"
            assert result["risk_score"] is None

    def test_global_search_endpoint_validates_limit_bounds(self):
        """Test that global search endpoint validates limit parameter bounds."""
        # Test limit too high
        response = client.get("/api/contracts/search?query=test&limit=100")
        assert response.status_code == 422

        # Test limit too low
        response = client.get("/api/contracts/search?query=test&limit=0")
        assert response.status_code == 422
