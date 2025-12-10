"""
Unit tests for global search functionality.

Tests the vector store global_search method and the
GET /api/contracts/search endpoint.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


class TestVectorStoreGlobalSearch:
    """Unit tests for ContractVectorStore.global_search method."""

    @pytest.fixture
    def mock_collection(self):
        """Mock ChromaDB collection."""
        collection = MagicMock()
        return collection

    @pytest.fixture
    def vector_store(self, mock_collection):
        """Create vector store with mocked dependencies."""
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    mock_client_instance = MagicMock()
                    mock_client_instance.get_or_create_collection.return_value = mock_collection
                    mock_client.return_value = mock_client_instance

                    from backend.services.vector_store import ContractVectorStore
                    store = ContractVectorStore(persist_directory="./test_db")
                    store.collection = mock_collection
                    return store

    @pytest.mark.asyncio
    async def test_global_search_groups_by_contract_id(self, vector_store, mock_collection):
        """Test that results are grouped by contract_id."""
        mock_collection.query.return_value = {
            "documents": [[
                "Text from contract 1, chunk 1",
                "Text from contract 1, chunk 2",
                "Text from contract 2, chunk 1"
            ]],
            "metadatas": [[
                {"contract_id": "contract-1"},
                {"contract_id": "contract-1"},
                {"contract_id": "contract-2"}
            ]],
            "distances": [[0.1, 0.2, 0.3]]
        }

        results = await vector_store.global_search(query="payment terms", n_results=10)

        # Should have 2 unique contracts
        assert len(results) == 2

        contract_ids = [r["contract_id"] for r in results]
        assert "contract-1" in contract_ids
        assert "contract-2" in contract_ids

    @pytest.mark.asyncio
    async def test_global_search_calculates_best_score(self, vector_store, mock_collection):
        """Test that best_score is the minimum distance for each contract."""
        mock_collection.query.return_value = {
            "documents": [[
                "Chunk 1",
                "Chunk 2",
                "Chunk 3"
            ]],
            "metadatas": [[
                {"contract_id": "contract-1"},
                {"contract_id": "contract-1"},
                {"contract_id": "contract-1"}
            ]],
            "distances": [[0.3, 0.1, 0.2]]  # Best is 0.1
        }

        results = await vector_store.global_search(query="test", n_results=10)

        assert len(results) == 1
        assert results[0]["best_score"] == 0.1

    @pytest.mark.asyncio
    async def test_global_search_sorts_by_best_score(self, vector_store, mock_collection):
        """Test that results are sorted by best_score (lowest first)."""
        mock_collection.query.return_value = {
            "documents": [[
                "Contract 2 text",
                "Contract 1 text",
                "Contract 3 text"
            ]],
            "metadatas": [[
                {"contract_id": "contract-2"},
                {"contract_id": "contract-1"},
                {"contract_id": "contract-3"}
            ]],
            "distances": [[0.3, 0.1, 0.5]]
        }

        results = await vector_store.global_search(query="test", n_results=10)

        # Should be sorted: contract-1 (0.1), contract-2 (0.3), contract-3 (0.5)
        assert results[0]["contract_id"] == "contract-1"
        assert results[1]["contract_id"] == "contract-2"
        assert results[2]["contract_id"] == "contract-3"

    @pytest.mark.asyncio
    async def test_global_search_truncates_match_text(self, vector_store, mock_collection):
        """Test that match text is truncated to 200 characters."""
        long_text = "A" * 500

        mock_collection.query.return_value = {
            "documents": [[long_text]],
            "metadatas": [[{"contract_id": "contract-1"}]],
            "distances": [[0.1]]
        }

        results = await vector_store.global_search(query="test", n_results=10)

        match_text = results[0]["matches"][0]["text"]
        assert len(match_text) == 200

    @pytest.mark.asyncio
    async def test_global_search_calculates_score_from_distance(self, vector_store, mock_collection):
        """Test that score is calculated as 1 - distance."""
        mock_collection.query.return_value = {
            "documents": [["Test text"]],
            "metadatas": [[{"contract_id": "contract-1"}]],
            "distances": [[0.2]]  # Distance 0.2 -> Score 0.8
        }

        results = await vector_store.global_search(query="test", n_results=10)

        score = results[0]["matches"][0]["score"]
        assert score == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_global_search_with_risk_level_filter(self, vector_store, mock_collection):
        """Test that risk_level filter is passed to query."""
        mock_collection.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }

        await vector_store.global_search(
            query="test",
            n_results=10,
            risk_level="high"
        )

        call_args = mock_collection.query.call_args
        assert call_args.kwargs.get("where") == {"risk_level": "high"}

    @pytest.mark.asyncio
    async def test_global_search_without_filter(self, vector_store, mock_collection):
        """Test that no filter is applied when risk_level is None."""
        mock_collection.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }

        await vector_store.global_search(query="test", n_results=10)

        call_args = mock_collection.query.call_args
        assert call_args.kwargs.get("where") is None

    @pytest.mark.asyncio
    async def test_global_search_handles_empty_results(self, vector_store, mock_collection):
        """Test handling of empty search results."""
        mock_collection.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }

        results = await vector_store.global_search(query="nonexistent", n_results=10)

        assert results == []

    @pytest.mark.asyncio
    async def test_global_search_handles_error(self, vector_store, mock_collection):
        """Test that ChromaDB errors are propagated."""
        mock_collection.query.side_effect = Exception("Search failed")

        with pytest.raises(Exception) as exc_info:
            await vector_store.global_search(query="test", n_results=10)

        assert "Search failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_global_search_aggregates_multiple_matches(self, vector_store, mock_collection):
        """Test that multiple matches per contract are aggregated."""
        mock_collection.query.return_value = {
            "documents": [[
                "First match for contract 1",
                "Second match for contract 1",
                "Third match for contract 1"
            ]],
            "metadatas": [[
                {"contract_id": "contract-1"},
                {"contract_id": "contract-1"},
                {"contract_id": "contract-1"}
            ]],
            "distances": [[0.1, 0.2, 0.3]]
        }

        results = await vector_store.global_search(query="test", n_results=10)

        assert len(results) == 1
        assert len(results[0]["matches"]) == 3


class TestGlobalSearchEndpoint:
    """Unit tests for GET /api/contracts/search endpoint."""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store."""
        store = MagicMock()
        store.global_search = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store."""
        store = MagicMock()

        def create_mock_graph(contract_id, filename, risk_score, risk_level):
            mock_contract = MagicMock()
            mock_contract.contract_id = contract_id
            mock_contract.filename = filename
            mock_contract.upload_date = datetime(2025, 1, 1)
            mock_contract.risk_score = risk_score
            mock_contract.risk_level = risk_level

            mock_graph = MagicMock()
            mock_graph.contract = mock_contract
            return mock_graph

        store.get_contract_relationships = AsyncMock(side_effect=lambda cid: {
            "contract-1": create_mock_graph("contract-1", "file1.pdf", 7.5, "high"),
            "contract-2": create_mock_graph("contract-2", "file2.pdf", 3.0, "low"),
        }.get(cid))

        return store

    @pytest.mark.asyncio
    async def test_endpoint_returns_503_when_not_initialized(self):
        """Test that 503 is returned when vector store not initialized."""
        from fastapi import HTTPException

        with patch('backend.main.vector_store', None):
            from backend.main import search_contracts

            with pytest.raises(HTTPException) as exc_info:
                await search_contracts(query="test query")

            assert exc_info.value.status_code == 503
            assert "not initialized" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_endpoint_enriches_with_graph_data(
        self, mock_vector_store, mock_graph_store
    ):
        """Test that results are enriched with graph store metadata."""
        mock_vector_store.global_search.return_value = [
            {
                "contract_id": "contract-1",
                "matches": [{"text": "Match text", "score": 0.9}],
                "best_score": 0.1
            }
        ]

        with patch('backend.main.vector_store', mock_vector_store):
            with patch('backend.main.graph_store', mock_graph_store):
                from backend.main import search_contracts

                response = await search_contracts(query="test query")

                assert len(response.results) == 1
                result = response.results[0]
                assert result["filename"] == "file1.pdf"
                assert result["risk_score"] == 7.5
                assert result["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_endpoint_handles_orphaned_contracts(
        self, mock_vector_store, mock_graph_store
    ):
        """Test handling when contract exists in vector store but not graph."""
        mock_vector_store.global_search.return_value = [
            {
                "contract_id": "orphaned-contract",
                "matches": [{"text": "Orphan text", "score": 0.8}],
                "best_score": 0.2
            }
        ]

        # Return None for orphaned contract
        mock_graph_store.get_contract_relationships = AsyncMock(return_value=None)

        with patch('backend.main.vector_store', mock_vector_store):
            with patch('backend.main.graph_store', mock_graph_store):
                from backend.main import search_contracts

                response = await search_contracts(query="test query")

                # Should still include the result with "Unknown" filename
                assert len(response.results) == 1
                result = response.results[0]
                assert result["filename"] == "Unknown"
                assert result["risk_score"] is None

    @pytest.mark.asyncio
    async def test_endpoint_calculates_relevance_score(
        self, mock_vector_store, mock_graph_store
    ):
        """Test that relevance_score is 1 - best_score."""
        mock_vector_store.global_search.return_value = [
            {
                "contract_id": "contract-1",
                "matches": [],
                "best_score": 0.3  # relevance = 1 - 0.3 = 0.7
            }
        ]

        with patch('backend.main.vector_store', mock_vector_store):
            with patch('backend.main.graph_store', mock_graph_store):
                from backend.main import search_contracts

                response = await search_contracts(query="test query")

                assert response.results[0]["relevance_score"] == pytest.approx(0.7)

    @pytest.mark.asyncio
    async def test_endpoint_respects_limit(self, mock_vector_store, mock_graph_store):
        """Test that limit parameter is respected."""
        # Return 10 results
        mock_vector_store.global_search.return_value = [
            {"contract_id": f"contract-{i}", "matches": [], "best_score": 0.1 * i}
            for i in range(10)
        ]

        with patch('backend.main.vector_store', mock_vector_store):
            with patch('backend.main.graph_store', mock_graph_store):
                from backend.main import search_contracts

                response = await search_contracts(query="test query", limit=5)

                assert len(response.results) <= 5

    @pytest.mark.asyncio
    async def test_endpoint_passes_risk_level_filter(
        self, mock_vector_store, mock_graph_store
    ):
        """Test that risk_level filter is passed to vector store."""
        mock_vector_store.global_search.return_value = []

        with patch('backend.main.vector_store', mock_vector_store):
            with patch('backend.main.graph_store', mock_graph_store):
                from backend.main import search_contracts

                await search_contracts(query="test query", risk_level="high")

                call_args = mock_vector_store.global_search.call_args
                assert call_args.kwargs.get("risk_level") == "high"

    @pytest.mark.asyncio
    async def test_endpoint_multiplies_limit_for_better_grouping(
        self, mock_vector_store, mock_graph_store
    ):
        """Test that endpoint requests more results for better grouping."""
        mock_vector_store.global_search.return_value = []

        with patch('backend.main.vector_store', mock_vector_store):
            with patch('backend.main.graph_store', mock_graph_store):
                from backend.main import search_contracts

                await search_contracts(query="test query", limit=10)

                call_args = mock_vector_store.global_search.call_args
                # Should request limit * 3 = 30 results
                assert call_args.kwargs.get("n_results") == 30

    @pytest.mark.asyncio
    async def test_endpoint_handles_search_error(self, mock_vector_store, mock_graph_store):
        """Test error handling when search fails."""
        from fastapi import HTTPException

        mock_vector_store.global_search.side_effect = Exception("Search error")

        with patch('backend.main.vector_store', mock_vector_store):
            with patch('backend.main.graph_store', mock_graph_store):
                from backend.main import search_contracts

                with pytest.raises(HTTPException) as exc_info:
                    await search_contracts(query="test query")

                assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_endpoint_returns_correct_response_structure(
        self, mock_vector_store, mock_graph_store
    ):
        """Test that response has correct structure."""
        mock_vector_store.global_search.return_value = [
            {
                "contract_id": "contract-1",
                "matches": [{"text": "Match", "score": 0.9}],
                "best_score": 0.1
            }
        ]

        with patch('backend.main.vector_store', mock_vector_store):
            with patch('backend.main.graph_store', mock_graph_store):
                from backend.main import search_contracts

                response = await search_contracts(query="payment terms")

                assert response.query == "payment terms"
                assert hasattr(response, 'results')
                assert hasattr(response, 'total')
                assert response.total == len(response.results)
