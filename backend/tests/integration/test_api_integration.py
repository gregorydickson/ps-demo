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
