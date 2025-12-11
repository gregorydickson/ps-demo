"""
Unit tests for code style refactorings.

Tests for:
- Error handling decorator
- Service dependency injection
- Parallel enrichment
- Functional data transformations
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
from fastapi import HTTPException
import asyncio


class TestErrorHandlingDecorator:
    """Tests for the @handle_endpoint_errors decorator."""

    @pytest.mark.asyncio
    async def test_decorator_passes_through_successful_result(self):
        """Test that decorator returns result on success."""
        from backend.utils.decorators import handle_endpoint_errors

        @handle_endpoint_errors("TestError")
        async def successful_endpoint():
            return {"status": "success"}

        result = await successful_endpoint()
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_decorator_re_raises_http_exception(self):
        """Test that HTTPException is re-raised unchanged."""
        from backend.utils.decorators import handle_endpoint_errors

        @handle_endpoint_errors("TestError")
        async def endpoint_with_http_error():
            raise HTTPException(status_code=404, detail="Not found")

        with pytest.raises(HTTPException) as exc_info:
            await endpoint_with_http_error()

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Not found"

    @pytest.mark.asyncio
    async def test_decorator_converts_exception_to_500(self):
        """Test that generic exceptions become 500 HTTPException."""
        from backend.utils.decorators import handle_endpoint_errors

        @handle_endpoint_errors("ProcessingError")
        async def endpoint_with_error():
            raise ValueError("Something went wrong")

        with pytest.raises(HTTPException) as exc_info:
            await endpoint_with_error()

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail["error"] == "ProcessingError"
        assert "Something went wrong" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""
        from backend.utils.decorators import handle_endpoint_errors

        @handle_endpoint_errors("TestError")
        async def my_endpoint():
            """My endpoint docstring."""
            return {"data": "test"}

        assert my_endpoint.__name__ == "my_endpoint"
        assert "My endpoint docstring" in my_endpoint.__doc__

    @pytest.mark.asyncio
    async def test_decorator_passes_args_and_kwargs(self):
        """Test that decorator passes arguments correctly."""
        from backend.utils.decorators import handle_endpoint_errors

        @handle_endpoint_errors("TestError")
        async def endpoint_with_args(arg1, arg2, kwarg1=None):
            return {"arg1": arg1, "arg2": arg2, "kwarg1": kwarg1}

        result = await endpoint_with_args("a", "b", kwarg1="c")
        assert result == {"arg1": "a", "arg2": "b", "kwarg1": "c"}

    @pytest.mark.asyncio
    async def test_decorator_logs_error(self):
        """Test that decorator logs the error."""
        from backend.utils.decorators import handle_endpoint_errors

        @handle_endpoint_errors("TestError")
        async def failing_endpoint():
            raise RuntimeError("Test error")

        with patch('backend.utils.decorators.logger') as mock_logger:
            with pytest.raises(HTTPException):
                await failing_endpoint()

            mock_logger.error.assert_called_once()
            assert "failing_endpoint" in str(mock_logger.error.call_args)


class TestServiceDependencies:
    """Tests for FastAPI service dependency injection."""

    def test_get_vector_store_returns_store_when_initialized(self):
        """Test that get_vector_store returns the store when available."""
        from backend.utils.dependencies import get_vector_store

        mock_store = MagicMock()
        with patch('backend.utils.dependencies._vector_store', mock_store):
            result = get_vector_store()
            assert result == mock_store

    def test_get_vector_store_raises_503_when_not_initialized(self):
        """Test that get_vector_store raises 503 when store is None."""
        from backend.utils.dependencies import get_vector_store

        with patch('backend.utils.dependencies._vector_store', None):
            with pytest.raises(HTTPException) as exc_info:
                get_vector_store()

            assert exc_info.value.status_code == 503
            assert "not initialized" in str(exc_info.value.detail).lower()

    def test_get_graph_store_returns_store_when_initialized(self):
        """Test that get_graph_store returns the store when available."""
        from backend.utils.dependencies import get_graph_store

        mock_store = MagicMock()
        with patch('backend.utils.dependencies._graph_store', mock_store):
            result = get_graph_store()
            assert result == mock_store

    def test_get_graph_store_raises_503_when_not_initialized(self):
        """Test that get_graph_store raises 503 when store is None."""
        from backend.utils.dependencies import get_graph_store

        with patch('backend.utils.dependencies._graph_store', None):
            with pytest.raises(HTTPException) as exc_info:
                get_graph_store()

            assert exc_info.value.status_code == 503

    def test_get_qa_workflow_returns_workflow_when_initialized(self):
        """Test that get_qa_workflow returns the workflow when available."""
        from backend.utils.dependencies import get_qa_workflow

        mock_workflow = MagicMock()
        with patch('backend.utils.dependencies._qa_workflow', mock_workflow):
            result = get_qa_workflow()
            assert result == mock_workflow

    def test_get_qa_workflow_raises_503_when_not_initialized(self):
        """Test that get_qa_workflow raises 503 when workflow is None."""
        from backend.utils.dependencies import get_qa_workflow

        with patch('backend.utils.dependencies._qa_workflow', None):
            with pytest.raises(HTTPException) as exc_info:
                get_qa_workflow()

            assert exc_info.value.status_code == 503


class TestParallelEnrichment:
    """Tests for parallel search result enrichment."""

    @pytest.mark.asyncio
    async def test_enrich_search_result_with_graph_data(self):
        """Test enriching a single result with graph data."""
        from backend.utils.functional import enrich_search_result

        mock_graph = MagicMock()
        mock_graph.contract.filename = "test.pdf"
        mock_graph.contract.upload_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_graph.contract.risk_score = 7.5
        mock_graph.contract.risk_level = "high"

        mock_graph_store = MagicMock()
        mock_graph_store.get_contract_relationships = AsyncMock(return_value=mock_graph)

        result = {
            "contract_id": "test-123",
            "matches": [{"text": "sample", "score": 0.9}],
            "best_score": 0.1
        }

        enriched = await enrich_search_result(result, mock_graph_store)

        assert enriched["contract_id"] == "test-123"
        assert enriched["filename"] == "test.pdf"
        assert enriched["risk_score"] == 7.5
        assert enriched["relevance_score"] == 0.9  # 1 - 0.1

    @pytest.mark.asyncio
    async def test_enrich_search_result_handles_missing_graph(self):
        """Test enrichment when contract not in graph store."""
        from backend.utils.functional import enrich_search_result

        mock_graph_store = MagicMock()
        mock_graph_store.get_contract_relationships = AsyncMock(return_value=None)

        result = {
            "contract_id": "orphan-123",
            "matches": [],
            "best_score": 0.2
        }

        enriched = await enrich_search_result(result, mock_graph_store)

        assert enriched["contract_id"] == "orphan-123"
        assert enriched["filename"] == "Unknown"
        assert enriched["risk_score"] is None

    @pytest.mark.asyncio
    async def test_enrich_results_parallel(self):
        """Test parallel enrichment of multiple results."""
        from backend.utils.functional import enrich_results_parallel

        mock_graph = MagicMock()
        mock_graph.contract.filename = "test.pdf"
        mock_graph.contract.upload_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_graph.contract.risk_score = 5.0
        mock_graph.contract.risk_level = "medium"

        mock_graph_store = MagicMock()
        mock_graph_store.get_contract_relationships = AsyncMock(return_value=mock_graph)

        results = [
            {"contract_id": f"contract-{i}", "matches": [], "best_score": 0.1 * i}
            for i in range(5)
        ]

        enriched = await enrich_results_parallel(results, mock_graph_store)

        assert len(enriched) == 5
        # Verify all were called (parallel execution)
        assert mock_graph_store.get_contract_relationships.call_count == 5

    @pytest.mark.asyncio
    async def test_enrich_results_parallel_preserves_order(self):
        """Test that parallel enrichment preserves result order."""
        from backend.utils.functional import enrich_results_parallel

        mock_graph_store = MagicMock()

        async def mock_get(contract_id):
            # Simulate varying response times
            await asyncio.sleep(0.01 if "1" in contract_id else 0)
            mock_graph = MagicMock()
            mock_graph.contract.filename = f"{contract_id}.pdf"
            mock_graph.contract.upload_date = datetime.now(timezone.utc)
            mock_graph.contract.risk_score = 5.0
            mock_graph.contract.risk_level = "medium"
            return mock_graph

        mock_graph_store.get_contract_relationships = mock_get

        results = [
            {"contract_id": f"contract-{i}", "matches": [], "best_score": 0.1}
            for i in range(3)
        ]

        enriched = await enrich_results_parallel(results, mock_graph_store)

        # Order should be preserved despite async timing
        assert enriched[0]["contract_id"] == "contract-0"
        assert enriched[1]["contract_id"] == "contract-1"
        assert enriched[2]["contract_id"] == "contract-2"


class TestFunctionalTransformations:
    """Tests for functional data transformations."""

    def test_transform_contract_records_to_dicts(self):
        """Test transforming database records to dictionaries."""
        from backend.utils.functional import transform_contract_records

        records = [
            ("id-1", "file1.pdf", "2025-01-01", 7.5, "high", 2),
            ("id-2", "file2.pdf", "2025-01-02", 3.0, "low", None),
        ]

        result = transform_contract_records(records)

        assert len(result) == 2
        assert result[0]["contract_id"] == "id-1"
        assert result[0]["party_count"] == 2
        assert result[1]["party_count"] == 0  # None converted to 0

    def test_transform_contract_records_empty_list(self):
        """Test transforming empty record list."""
        from backend.utils.functional import transform_contract_records

        result = transform_contract_records([])
        assert result == []

    def test_transform_contract_records_with_none(self):
        """Test transforming None input."""
        from backend.utils.functional import transform_contract_records

        result = transform_contract_records(None)
        assert result == []

    def test_group_search_results_by_contract(self):
        """Test grouping ChromaDB results by contract_id."""
        from backend.utils.functional import group_search_results

        chroma_results = {
            "ids": [["chunk-1", "chunk-2", "chunk-3"]],
            "documents": [["Doc 1 text", "Doc 2 text", "Doc 3 text"]],
            "metadatas": [[
                {"contract_id": "contract-a"},
                {"contract_id": "contract-a"},
                {"contract_id": "contract-b"}
            ]],
            "distances": [[0.1, 0.2, 0.15]]
        }

        grouped = group_search_results(chroma_results)

        assert len(grouped) == 2
        # Should be sorted by best_score
        assert grouped[0]["contract_id"] == "contract-a"  # best_score 0.1
        assert grouped[0]["best_score"] == 0.1
        assert len(grouped[0]["matches"]) == 2

    def test_group_search_results_handles_empty(self):
        """Test grouping empty results."""
        from backend.utils.functional import group_search_results

        empty_results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        grouped = group_search_results(empty_results)
        assert grouped == []

    def test_group_search_results_skips_missing_contract_id(self):
        """Test that results without contract_id are skipped."""
        from backend.utils.functional import group_search_results

        results = {
            "ids": [["chunk-1", "chunk-2"]],
            "documents": [["Doc 1", "Doc 2"]],
            "metadatas": [[
                {"contract_id": "valid-id"},
                {"other_field": "no contract_id"}
            ]],
            "distances": [[0.1, 0.2]]
        }

        grouped = group_search_results(results)

        assert len(grouped) == 1
        assert grouped[0]["contract_id"] == "valid-id"


class TestDatetimeHandling:
    """Tests for timezone-aware datetime handling."""

    def test_utc_now_returns_timezone_aware(self):
        """Test that utc_now returns timezone-aware datetime."""
        from backend.utils.functional import utc_now

        result = utc_now()

        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_utc_now_iso_format(self):
        """Test that utc_now produces valid ISO format."""
        from backend.utils.functional import utc_now

        result = utc_now()
        iso_string = result.isoformat()

        # Should contain timezone info
        assert "+" in iso_string or "Z" in iso_string

    def test_format_timestamp_returns_iso_string(self):
        """Test formatting datetime to ISO string."""
        from backend.utils.functional import format_timestamp

        dt = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_timestamp(dt)

        assert "2025-06-15" in result
        assert "10:30:00" in result


class TestLiteralTypeValidation:
    """Tests for Literal type validation in endpoints."""

    def test_risk_level_literal_accepts_valid_values(self):
        """Test that valid risk levels are accepted."""
        from backend.utils.validation import validate_risk_level

        assert validate_risk_level("low") == "low"
        assert validate_risk_level("medium") == "medium"
        assert validate_risk_level("high") == "high"
        assert validate_risk_level(None) is None

    def test_sort_by_literal_accepts_valid_values(self):
        """Test that valid sort_by values are accepted."""
        from backend.utils.validation import validate_sort_by

        assert validate_sort_by("upload_date") == "upload_date"
        assert validate_sort_by("risk_score") == "risk_score"
        assert validate_sort_by("filename") == "filename"

    def test_sort_order_literal_accepts_valid_values(self):
        """Test that valid sort_order values are accepted."""
        from backend.utils.validation import validate_sort_order

        assert validate_sort_order("asc") == "asc"
        assert validate_sort_order("desc") == "desc"
