"""
Unit tests for delete contract functionality.

Tests cascade deletion from vector store and graph store, error handling,
and the DELETE /api/contracts/{contract_id} endpoint.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestGraphStoreDeleteContract:
    """Unit tests for ContractGraphStore.delete_contract method."""

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
    async def test_delete_contract_returns_true_when_found(self, graph_store, mock_graph):
        """Test delete returns True when contract is deleted."""
        result = MagicMock()
        result.result_set = [[1]]  # 1 contract deleted
        mock_graph.query.return_value = result

        deleted = await graph_store.delete_contract("contract-123")

        assert deleted is True
        mock_graph.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_contract_returns_false_when_not_found(self, graph_store, mock_graph):
        """Test delete returns False when contract doesn't exist."""
        result = MagicMock()
        result.result_set = [[0]]  # 0 contracts deleted
        mock_graph.query.return_value = result

        deleted = await graph_store.delete_contract("nonexistent")

        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_contract_uses_correct_cypher(self, graph_store, mock_graph):
        """Test that delete uses correct Cypher query structure."""
        result = MagicMock()
        result.result_set = [[1]]
        mock_graph.query.return_value = result

        await graph_store.delete_contract("contract-123")

        call_args = mock_graph.query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Verify query structure
        assert "MATCH (c:Contract {contract_id: $contract_id})" in query
        assert "OPTIONAL MATCH (c)-[r]->(n)" in query
        assert "DELETE r, n, c" in query
        assert params['contract_id'] == "contract-123"

    @pytest.mark.asyncio
    async def test_delete_contract_handles_empty_result_set(self, graph_store, mock_graph):
        """Test handling when result_set is empty."""
        result = MagicMock()
        result.result_set = []
        mock_graph.query.return_value = result

        deleted = await graph_store.delete_contract("contract-123")

        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_contract_raises_on_error(self, graph_store, mock_graph):
        """Test that database errors are propagated."""
        mock_graph.query.side_effect = Exception("Connection lost")

        with pytest.raises(Exception) as exc_info:
            await graph_store.delete_contract("contract-123")

        assert "Connection lost" in str(exc_info.value)


class TestVectorStoreDeleteContract:
    """Unit tests for ContractVectorStore.delete_contract method."""

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
    async def test_delete_contract_removes_all_chunks(self, vector_store, mock_collection):
        """Test that all chunks for a contract are deleted."""
        mock_collection.get.return_value = {
            'ids': ['chunk-1', 'chunk-2', 'chunk-3']
        }

        deleted_count = await vector_store.delete_contract("contract-123")

        assert deleted_count == 3
        mock_collection.get.assert_called_once_with(
            where={"contract_id": "contract-123"}
        )
        mock_collection.delete.assert_called_once_with(
            ids=['chunk-1', 'chunk-2', 'chunk-3']
        )

    @pytest.mark.asyncio
    async def test_delete_contract_returns_zero_when_no_chunks(self, vector_store, mock_collection):
        """Test that deleting non-existent contract returns 0."""
        mock_collection.get.return_value = {'ids': []}

        deleted_count = await vector_store.delete_contract("nonexistent")

        assert deleted_count == 0
        mock_collection.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_contract_handles_error(self, vector_store, mock_collection):
        """Test that ChromaDB errors are propagated."""
        mock_collection.get.side_effect = Exception("ChromaDB error")

        with pytest.raises(Exception) as exc_info:
            await vector_store.delete_contract("contract-123")

        assert "ChromaDB error" in str(exc_info.value)


class TestDeleteContractEndpoint:
    """Unit tests for DELETE /api/contracts/{contract_id} endpoint."""

    @pytest.fixture
    def mock_graph_store(self):
        """Mock graph store."""
        store = MagicMock()
        store.get_contract_relationships = AsyncMock()
        store.delete_contract = AsyncMock()
        return store

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store."""
        store = MagicMock()
        store.delete_contract = AsyncMock(return_value=5)
        return store

    @pytest.mark.asyncio
    async def test_delete_returns_404_when_not_found(self, mock_graph_store, mock_vector_store):
        """Test that 404 is returned when contract doesn't exist."""
        from fastapi import HTTPException

        mock_graph_store.get_contract_relationships.return_value = None

        with patch('backend.main.graph_store', mock_graph_store):
            with patch('backend.main.vector_store', mock_vector_store):
                from backend.main import delete_contract

                with pytest.raises(HTTPException) as exc_info:
                    await delete_contract("nonexistent")

                assert exc_info.value.status_code == 404
                assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_delete_removes_from_both_stores(self, mock_graph_store, mock_vector_store):
        """Test that deletion happens from both vector and graph stores."""
        # Contract exists
        mock_contract = MagicMock()
        mock_graph_store.get_contract_relationships.return_value = mock_contract
        mock_graph_store.delete_contract.return_value = True

        with patch('backend.main.graph_store', mock_graph_store):
            with patch('backend.main.vector_store', mock_vector_store):
                from backend.main import delete_contract

                response = await delete_contract("contract-123")

                # Verify both stores were called
                mock_vector_store.delete_contract.assert_called_once_with("contract-123")
                mock_graph_store.delete_contract.assert_called_once_with("contract-123")

    @pytest.mark.asyncio
    async def test_delete_returns_204_on_success(self, mock_graph_store, mock_vector_store):
        """Test that successful deletion returns 204 No Content."""
        mock_contract = MagicMock()
        mock_graph_store.get_contract_relationships.return_value = mock_contract
        mock_graph_store.delete_contract.return_value = True

        with patch('backend.main.graph_store', mock_graph_store):
            with patch('backend.main.vector_store', mock_vector_store):
                from backend.main import delete_contract

                response = await delete_contract("contract-123")

                assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_handles_vector_store_error(self, mock_graph_store, mock_vector_store):
        """Test error handling when vector store deletion fails."""
        from fastapi import HTTPException

        mock_contract = MagicMock()
        mock_graph_store.get_contract_relationships.return_value = mock_contract
        mock_vector_store.delete_contract.side_effect = Exception("Vector DB error")

        with patch('backend.main.graph_store', mock_graph_store):
            with patch('backend.main.vector_store', mock_vector_store):
                from backend.main import delete_contract

                with pytest.raises(HTTPException) as exc_info:
                    await delete_contract("contract-123")

                assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_delete_handles_graph_store_error(self, mock_graph_store, mock_vector_store):
        """Test error handling when graph store deletion fails."""
        from fastapi import HTTPException

        mock_contract = MagicMock()
        mock_graph_store.get_contract_relationships.return_value = mock_contract
        mock_graph_store.delete_contract.side_effect = Exception("Graph DB error")

        with patch('backend.main.graph_store', mock_graph_store):
            with patch('backend.main.vector_store', mock_vector_store):
                from backend.main import delete_contract

                with pytest.raises(HTTPException) as exc_info:
                    await delete_contract("contract-123")

                assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_delete_logs_chunk_count(self, mock_graph_store, mock_vector_store):
        """Test that chunk deletion count is logged."""
        mock_contract = MagicMock()
        mock_graph_store.get_contract_relationships.return_value = mock_contract
        mock_graph_store.delete_contract.return_value = True
        mock_vector_store.delete_contract.return_value = 10  # 10 chunks deleted

        with patch('backend.main.graph_store', mock_graph_store):
            with patch('backend.main.vector_store', mock_vector_store):
                with patch('backend.main.logger') as mock_logger:
                    from backend.main import delete_contract

                    await delete_contract("contract-123")

                    # Verify logging occurred (at least one info call)
                    assert mock_logger.info.called
