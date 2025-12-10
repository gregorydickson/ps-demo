"""
Unit tests for list contracts functionality.

Tests pagination, filtering, sorting, and error handling for the
GET /api/contracts endpoint and graph_store.list_contracts method.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone


class TestGraphStoreListContracts:
    """Unit tests for ContractGraphStore.list_contracts method."""

    @pytest.fixture
    def mock_graph(self):
        """Mock FalkorDB graph instance."""
        graph = MagicMock()
        return graph

    @pytest.fixture
    def graph_store(self, mock_graph):
        """Create graph store with mocked dependencies."""
        with patch('backend.services.graph_store.FalkorDB') as mock_falkor:
            mock_db = MagicMock()
            mock_db.select_graph.return_value = mock_graph
            mock_falkor.return_value = mock_db

            from backend.services.graph_store import ContractGraphStore
            store = ContractGraphStore()
            store.graph = mock_graph
            return store

    @pytest.mark.asyncio
    async def test_list_contracts_returns_correct_structure(self, graph_store, mock_graph):
        """Test that list_contracts returns tuple of (contracts, total)."""
        # Mock count query result
        count_result = MagicMock()
        count_result.result_set = [[5]]

        # Mock list query result
        list_result = MagicMock()
        list_result.result_set = [
            ["contract-1", "file1.pdf", "2025-01-01T10:00:00", 7.5, "high", 2],
            ["contract-2", "file2.pdf", "2025-01-02T10:00:00", 3.0, "low", 1],
        ]

        mock_graph.query.side_effect = [count_result, list_result]

        contracts, total = await graph_store.list_contracts(skip=0, limit=10)

        assert total == 5
        assert len(contracts) == 2
        assert contracts[0]['contract_id'] == "contract-1"
        assert contracts[0]['filename'] == "file1.pdf"
        assert contracts[0]['risk_score'] == 7.5
        assert contracts[0]['party_count'] == 2

    @pytest.mark.asyncio
    async def test_list_contracts_with_pagination(self, graph_store, mock_graph):
        """Test pagination parameters are passed correctly."""
        count_result = MagicMock()
        count_result.result_set = [[100]]

        list_result = MagicMock()
        list_result.result_set = []

        mock_graph.query.side_effect = [count_result, list_result]

        await graph_store.list_contracts(skip=20, limit=10)

        # Verify second query (list query) has correct skip/limit
        list_call = mock_graph.query.call_args_list[1]
        params = list_call[0][1]
        assert params['skip'] == 20
        assert params['limit'] == 10

    @pytest.mark.asyncio
    async def test_list_contracts_with_risk_level_filter(self, graph_store, mock_graph):
        """Test filtering by risk_level adds WHERE clause."""
        count_result = MagicMock()
        count_result.result_set = [[3]]

        list_result = MagicMock()
        list_result.result_set = []

        mock_graph.query.side_effect = [count_result, list_result]

        await graph_store.list_contracts(skip=0, limit=10, risk_level="high")

        # Both queries should have risk_level in params
        for call in mock_graph.query.call_args_list:
            query_string = call[0][0]
            params = call[0][1]
            assert "WHERE c.risk_level = $risk_level" in query_string
            assert params.get('risk_level') == "high"

    @pytest.mark.asyncio
    async def test_list_contracts_sorting_by_risk_score(self, graph_store, mock_graph):
        """Test sorting by risk_score field."""
        count_result = MagicMock()
        count_result.result_set = [[10]]

        list_result = MagicMock()
        list_result.result_set = []

        mock_graph.query.side_effect = [count_result, list_result]

        await graph_store.list_contracts(
            skip=0, limit=10, sort_by="risk_score", sort_order="asc"
        )

        # Verify ORDER BY clause
        list_call = mock_graph.query.call_args_list[1]
        query_string = list_call[0][0]
        assert "ORDER BY c.risk_score ASC" in query_string

    @pytest.mark.asyncio
    async def test_list_contracts_sorting_by_filename_desc(self, graph_store, mock_graph):
        """Test sorting by filename in descending order."""
        count_result = MagicMock()
        count_result.result_set = [[10]]

        list_result = MagicMock()
        list_result.result_set = []

        mock_graph.query.side_effect = [count_result, list_result]

        await graph_store.list_contracts(
            skip=0, limit=10, sort_by="filename", sort_order="desc"
        )

        list_call = mock_graph.query.call_args_list[1]
        query_string = list_call[0][0]
        assert "ORDER BY c.filename DESC" in query_string

    @pytest.mark.asyncio
    async def test_list_contracts_handles_empty_results(self, graph_store, mock_graph):
        """Test handling when no contracts exist."""
        count_result = MagicMock()
        count_result.result_set = [[0]]

        list_result = MagicMock()
        list_result.result_set = []

        mock_graph.query.side_effect = [count_result, list_result]

        contracts, total = await graph_store.list_contracts(skip=0, limit=10)

        assert total == 0
        assert contracts == []

    @pytest.mark.asyncio
    async def test_list_contracts_handles_null_party_count(self, graph_store, mock_graph):
        """Test that null party_count is converted to 0."""
        count_result = MagicMock()
        count_result.result_set = [[1]]

        list_result = MagicMock()
        list_result.result_set = [
            ["contract-1", "file1.pdf", "2025-01-01T10:00:00", 5.0, "medium", None],
        ]

        mock_graph.query.side_effect = [count_result, list_result]

        contracts, total = await graph_store.list_contracts(skip=0, limit=10)

        assert contracts[0]['party_count'] == 0

    @pytest.mark.asyncio
    async def test_list_contracts_raises_on_query_error(self, graph_store, mock_graph):
        """Test that database errors are propagated."""
        mock_graph.query.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception) as exc_info:
            await graph_store.list_contracts(skip=0, limit=10)

        assert "Database connection failed" in str(exc_info.value)


class TestListContractsEndpoint:
    """Unit tests for the /api/contracts endpoint."""

    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store."""
        store = MagicMock()
        store.list_contracts = AsyncMock()
        return store

    @pytest.mark.asyncio
    async def test_endpoint_calculates_skip_correctly(self, mock_graph_store):
        """Test that skip is calculated from page number correctly."""
        mock_graph_store.list_contracts.return_value = ([], 0)

        with patch('backend.main.graph_store', mock_graph_store):
            from backend.main import list_contracts

            # Page 1 should have skip=0
            await list_contracts(page=1, page_size=20)
            call_args = mock_graph_store.list_contracts.call_args
            assert call_args.kwargs['skip'] == 0

            # Page 3 with page_size 20 should have skip=40
            await list_contracts(page=3, page_size=20)
            call_args = mock_graph_store.list_contracts.call_args
            assert call_args.kwargs['skip'] == 40

    @pytest.mark.asyncio
    async def test_endpoint_has_more_calculation(self, mock_graph_store):
        """Test has_more flag calculation."""
        # Total 25, page_size 10, page 1 -> has_more=True (10 < 25)
        mock_graph_store.list_contracts.return_value = ([
            {'contract_id': f'c{i}', 'filename': f'f{i}.pdf',
             'upload_date': '2025-01-01', 'risk_score': 5.0,
             'risk_level': 'medium', 'party_count': 1}
            for i in range(10)
        ], 25)

        with patch('backend.main.graph_store', mock_graph_store):
            from backend.main import list_contracts

            response = await list_contracts(page=1, page_size=10)
            assert response.has_more is True

            # Page 3, skip=20, 20+10=30 > 25, so has_more=False
            response = await list_contracts(page=3, page_size=10)
            assert response.has_more is False

    @pytest.mark.asyncio
    async def test_endpoint_validates_risk_level(self):
        """Test that invalid risk_level raises 400."""
        from fastapi import HTTPException

        with patch('backend.main.graph_store'):
            from backend.main import list_contracts

            with pytest.raises(HTTPException) as exc_info:
                await list_contracts(
                    page=1, page_size=20, risk_level="invalid"
                )

            assert exc_info.value.status_code == 400
            assert "risk_level" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_endpoint_validates_sort_by(self):
        """Test that invalid sort_by raises 400."""
        from fastapi import HTTPException

        with patch('backend.main.graph_store'):
            from backend.main import list_contracts

            with pytest.raises(HTTPException) as exc_info:
                await list_contracts(
                    page=1, page_size=20, sort_by="invalid_field"
                )

            assert exc_info.value.status_code == 400
            assert "sort_by" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_endpoint_validates_sort_order(self):
        """Test that invalid sort_order raises 400."""
        from fastapi import HTTPException

        with patch('backend.main.graph_store'):
            from backend.main import list_contracts

            with pytest.raises(HTTPException) as exc_info:
                await list_contracts(
                    page=1, page_size=20, sort_order="random"
                )

            assert exc_info.value.status_code == 400
            assert "sort_order" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_endpoint_handles_database_error(self, mock_graph_store):
        """Test that database errors return 500."""
        from fastapi import HTTPException

        mock_graph_store.list_contracts.side_effect = Exception("DB error")

        with patch('backend.main.graph_store', mock_graph_store):
            from backend.main import list_contracts

            with pytest.raises(HTTPException) as exc_info:
                await list_contracts(page=1, page_size=20)

            assert exc_info.value.status_code == 500
