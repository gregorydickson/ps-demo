"""
Unit tests for ContractVectorStore service.

Tests chunking logic, sentence boundaries, and metadata handling without
requiring ChromaDB or actual embeddings.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import os

from backend.services.vector_store import ContractVectorStore


class TestVectorStoreUnit:
    """Unit tests for ContractVectorStore class."""

    def test_chunking_creates_correct_sizes(self):
        """Test text chunking with specified size and overlap."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient'):
                with patch('backend.services.vector_store.genai.configure'):
                    store = ContractVectorStore(persist_directory="./test_db")

                    # Create text that should be split into multiple chunks
                    text = "A" * 2500  # 2.5x the default chunk size
                    chunks = store._chunk_text(text, chunk_size=1000, overlap=200)

                    # Should create 3 chunks
                    assert len(chunks) == 3
                    # Each chunk should be <= chunk_size
                    assert all(len(chunk) <= 1000 for chunk in chunks)

    def test_chunking_respects_overlap(self):
        """Test that chunks have the specified overlap."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient'):
                with patch('backend.services.vector_store.genai.configure'):
                    store = ContractVectorStore(persist_directory="./test_db")

                    text = "A" * 1500
                    chunks = store._chunk_text(text, chunk_size=1000, overlap=200)

                    # First chunk should be 1000 chars
                    assert len(chunks[0]) == 1000
                    # Should have created 2 chunks with overlap
                    assert len(chunks) == 2

    def test_chunking_preserves_sentence_boundaries(self):
        """Test that chunks prefer to break at sentence boundaries."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient'):
                with patch('backend.services.vector_store.genai.configure'):
                    store = ContractVectorStore(persist_directory="./test_db")

                    text = (
                        "First sentence that is quite long and detailed. "
                        "Second sentence with more information. "
                        "Third sentence continues the discussion. "
                        "Fourth sentence adds even more context. "
                        "Fifth sentence wraps things up nicely."
                    )

                    chunks = store._chunk_text(text, chunk_size=100, overlap=20)

                    # Most chunks should end with a period (sentence boundary)
                    # Allow last chunk to not end with period
                    for chunk in chunks[:-1]:
                        stripped = chunk.strip()
                        # Either ends with period or is exactly chunk_size
                        assert stripped.endswith('.') or len(chunk) == 100

    def test_chunking_handles_empty_text(self):
        """Test chunking with empty string."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient'):
                with patch('backend.services.vector_store.genai.configure'):
                    store = ContractVectorStore(persist_directory="./test_db")

                    chunks = store._chunk_text("", chunk_size=1000, overlap=200)
                    assert chunks == []

    def test_chunking_handles_small_text(self):
        """Test chunking with text smaller than chunk_size."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient'):
                with patch('backend.services.vector_store.genai.configure'):
                    store = ContractVectorStore(persist_directory="./test_db")

                    text = "Short text."
                    chunks = store._chunk_text(text, chunk_size=1000, overlap=200)

                    assert len(chunks) == 1
                    assert chunks[0] == "Short text."

    def test_chunking_handles_newlines(self):
        """Test that chunking respects newline boundaries."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient'):
                with patch('backend.services.vector_store.genai.configure'):
                    store = ContractVectorStore(persist_directory="./test_db")

                    text = (
                        "Section 1: This is a long section with lots of text that goes on and on\n"
                        "Section 2: Another section with more content that continues for a while\n"
                        "Section 3: Final section with concluding thoughts and information"
                    )

                    chunks = store._chunk_text(text, chunk_size=80, overlap=10)

                    # Should break at logical boundaries
                    assert len(chunks) > 1

    @pytest.mark.asyncio
    async def test_store_document_sections_chunks_and_stores(
        self, mock_chroma_collection, mock_genai_embed_content, sample_contract_text
    ):
        """Test that store_document_sections chunks, embeds, and stores."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    with patch('backend.services.vector_store.genai.embed_content', mock_genai_embed_content):
                        mock_client_instance = MagicMock()
                        mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                        mock_client.return_value = mock_client_instance

                        store = ContractVectorStore(persist_directory="./test_db")
                        store.collection = mock_chroma_collection

                        chunk_ids = await store.store_document_sections(
                            contract_id="test-123",
                            document_text=sample_contract_text,
                            metadata={"filename": "contract.pdf"}
                        )

                        # Should have stored chunks
                        assert len(chunk_ids) > 0
                        # Collection.add should have been called
                        assert mock_chroma_collection.add.called
                        # Verify call structure
                        call_args = mock_chroma_collection.add.call_args
                        assert 'ids' in call_args[1]
                        assert 'embeddings' in call_args[1]
                        assert 'documents' in call_args[1]
                        assert 'metadatas' in call_args[1]

    @pytest.mark.asyncio
    async def test_store_document_sections_includes_metadata(
        self, mock_chroma_collection, mock_genai_embed_content
    ):
        """Test that metadata is preserved in stored chunks."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    with patch('backend.services.vector_store.genai.embed_content', mock_genai_embed_content):
                        mock_client_instance = MagicMock()
                        mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                        mock_client.return_value = mock_client_instance

                        store = ContractVectorStore(persist_directory="./test_db")
                        store.collection = mock_chroma_collection

                        metadata = {"filename": "test.pdf", "user_id": "user-123"}

                        await store.store_document_sections(
                            contract_id="test-123",
                            document_text="Test document text.",
                            metadata=metadata
                        )

                        # Verify metadata was passed
                        call_args = mock_chroma_collection.add.call_args[1]
                        metadatas = call_args['metadatas']

                        # All chunks should have the metadata
                        assert all('contract_id' in m for m in metadatas)
                        assert all(m['contract_id'] == 'test-123' for m in metadatas)
                        assert all('filename' in m for m in metadatas)
                        assert all(m['filename'] == 'test.pdf' for m in metadatas)

    @pytest.mark.asyncio
    async def test_store_document_sections_handles_empty_text(
        self, mock_chroma_collection, mock_genai_embed_content
    ):
        """Test handling of empty document text."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    with patch('backend.services.vector_store.genai.embed_content', mock_genai_embed_content):
                        mock_client_instance = MagicMock()
                        mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                        mock_client.return_value = mock_client_instance

                        store = ContractVectorStore(persist_directory="./test_db")
                        store.collection = mock_chroma_collection

                        chunk_ids = await store.store_document_sections(
                            contract_id="test-123",
                            document_text="",
                            metadata={}
                        )

                        assert chunk_ids == []
                        # Should not have called add
                        assert not mock_chroma_collection.add.called

    @pytest.mark.asyncio
    async def test_semantic_search_returns_formatted_results(
        self, mock_chroma_collection, mock_genai_embed_content
    ):
        """Test that semantic search returns properly formatted results."""
        # Setup mock search results
        mock_chroma_collection.query.return_value = {
            'ids': [['chunk-1', 'chunk-2']],
            'documents': [['Payment terms text', 'Liability clause text']],
            'metadatas': [[
                {'contract_id': 'test-123', 'chunk_index': 0},
                {'contract_id': 'test-123', 'chunk_index': 1}
            ]],
            'distances': [[0.15, 0.25]]
        }

        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    with patch('backend.services.vector_store.genai.embed_content', mock_genai_embed_content):
                        mock_client_instance = MagicMock()
                        mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                        mock_client.return_value = mock_client_instance

                        store = ContractVectorStore(persist_directory="./test_db")
                        store.collection = mock_chroma_collection

                        results = await store.semantic_search(
                            query="What are the payment terms?",
                            n_results=5
                        )

                        assert len(results) == 2
                        assert all('id' in r for r in results)
                        assert all('text' in r for r in results)
                        assert all('metadata' in r for r in results)
                        assert all('relevance_score' in r for r in results)

    @pytest.mark.asyncio
    async def test_semantic_search_filters_by_contract_id(
        self, mock_chroma_collection, mock_genai_embed_content
    ):
        """Test that semantic search can filter by contract_id."""
        mock_chroma_collection.query.return_value = {
            'ids': [['chunk-1']],
            'documents': [['Filtered result']],
            'metadatas': [[{'contract_id': 'test-123'}]],
            'distances': [[0.1]]
        }

        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    with patch('backend.services.vector_store.genai.embed_content', mock_genai_embed_content):
                        mock_client_instance = MagicMock()
                        mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                        mock_client.return_value = mock_client_instance

                        store = ContractVectorStore(persist_directory="./test_db")
                        store.collection = mock_chroma_collection

                        await store.semantic_search(
                            query="Test query",
                            n_results=5,
                            contract_id="test-123"
                        )

                        # Verify where filter was used
                        call_args = mock_chroma_collection.query.call_args[1]
                        assert 'where' in call_args
                        assert call_args['where'] == {"contract_id": "test-123"}

    def test_delete_contract_removes_all_chunks(self, mock_chroma_collection):
        """Test that delete_contract removes all chunks for a contract."""
        mock_chroma_collection.get.return_value = {
            'ids': ['chunk-1', 'chunk-2', 'chunk-3']
        }

        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    mock_client_instance = MagicMock()
                    mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                    mock_client.return_value = mock_client_instance

                    store = ContractVectorStore(persist_directory="./test_db")
                    store.collection = mock_chroma_collection

                    deleted_count = store.delete_contract("test-123")

                    assert deleted_count == 3
                    mock_chroma_collection.delete.assert_called_once()

    def test_delete_contract_returns_zero_when_no_chunks(self, mock_chroma_collection):
        """Test that delete_contract returns 0 when no chunks found."""
        mock_chroma_collection.get.return_value = {'ids': []}

        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    mock_client_instance = MagicMock()
                    mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                    mock_client.return_value = mock_client_instance

                    store = ContractVectorStore(persist_directory="./test_db")
                    store.collection = mock_chroma_collection

                    deleted_count = store.delete_contract("nonexistent")

                    assert deleted_count == 0

    def test_get_collection_stats_returns_info(self, mock_chroma_collection):
        """Test getting collection statistics."""
        mock_chroma_collection.count.return_value = 42

        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    mock_client_instance = MagicMock()
                    mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                    mock_client.return_value = mock_client_instance

                    store = ContractVectorStore(persist_directory="./test_db")
                    store.collection = mock_chroma_collection

                    stats = store.get_collection_stats()

                    assert stats["total_chunks"] == 42
                    assert stats["collection_name"] == "legal_contracts"
                    assert "persist_directory" in stats

    def test_initialization_requires_google_api_key(self):
        """Test that initialization fails without GOOGLE_API_KEY."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('backend.services.vector_store.chromadb.PersistentClient'):
                with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
                    ContractVectorStore(persist_directory="./test_db")

    def test_generate_embeddings_batches_large_inputs(self, mock_genai_embed_content):
        """Test that _generate_embeddings processes in batches."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient'):
                with patch('backend.services.vector_store.genai.configure'):
                    with patch('backend.services.vector_store.genai.embed_content', mock_genai_embed_content):
                        store = ContractVectorStore(persist_directory="./test_db")

                        # Create 150 texts (more than batch size of 100)
                        texts = [f"Text {i}" for i in range(150)]

                        embeddings = store._generate_embeddings(texts)

                        # Should return embeddings for all texts
                        assert len(embeddings) == 150
                        # Each embedding should be a list of floats
                        assert all(isinstance(e, list) for e in embeddings)

    @pytest.mark.asyncio
    async def test_global_search_groups_by_contract_id(
        self, mock_chroma_collection, mock_genai_embed_content
    ):
        """Test that global_search groups results by contract_id."""
        # Setup mock search results with multiple contracts
        mock_chroma_collection.query.return_value = {
            'ids': [['chunk-1', 'chunk-2', 'chunk-3', 'chunk-4']],
            'documents': [[
                'Contract A payment clause',
                'Contract B payment clause',
                'Contract A termination clause',
                'Contract C payment clause'
            ]],
            'metadatas': [[
                {'contract_id': 'contract-a', 'chunk_index': 0},
                {'contract_id': 'contract-b', 'chunk_index': 0},
                {'contract_id': 'contract-a', 'chunk_index': 1},
                {'contract_id': 'contract-c', 'chunk_index': 0}
            ]],
            'distances': [[0.15, 0.25, 0.30, 0.35]]
        }

        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    with patch('backend.services.vector_store.genai.embed_content', mock_genai_embed_content):
                        mock_client_instance = MagicMock()
                        mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                        mock_client.return_value = mock_client_instance

                        store = ContractVectorStore(persist_directory="./test_db")
                        store.collection = mock_chroma_collection

                        results = await store.global_search(
                            query="payment terms",
                            n_results=20
                        )

                        # Should group into 3 contracts
                        assert len(results) == 3

                        # Contract A should have 2 matches
                        contract_a = next(r for r in results if r["contract_id"] == "contract-a")
                        assert len(contract_a["matches"]) == 2

                        # Should be sorted by best score
                        assert results[0]["best_score"] < results[1]["best_score"]

    @pytest.mark.asyncio
    async def test_global_search_filters_by_risk_level(
        self, mock_chroma_collection, mock_genai_embed_content
    ):
        """Test that global_search can filter by risk level."""
        mock_chroma_collection.query.return_value = {
            'ids': [['chunk-1']],
            'documents': [['Filtered result']],
            'metadatas': [[{'contract_id': 'test-123', 'risk_level': 'high'}]],
            'distances': [[0.1]]
        }

        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    with patch('backend.services.vector_store.genai.embed_content', mock_genai_embed_content):
                        mock_client_instance = MagicMock()
                        mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                        mock_client.return_value = mock_client_instance

                        store = ContractVectorStore(persist_directory="./test_db")
                        store.collection = mock_chroma_collection

                        await store.global_search(
                            query="Test query",
                            n_results=20,
                            risk_level="high"
                        )

                        # Verify where filter was used
                        call_args = mock_chroma_collection.query.call_args[1]
                        assert 'where' in call_args
                        assert call_args['where'] == {"risk_level": "high"}

    @pytest.mark.asyncio
    async def test_global_search_truncates_match_text(
        self, mock_chroma_collection, mock_genai_embed_content
    ):
        """Test that global_search truncates match text to 200 chars."""
        long_text = "A" * 500
        mock_chroma_collection.query.return_value = {
            'ids': [['chunk-1']],
            'documents': [[long_text]],
            'metadatas': [[{'contract_id': 'test-123'}]],
            'distances': [[0.1]]
        }

        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    with patch('backend.services.vector_store.genai.embed_content', mock_genai_embed_content):
                        mock_client_instance = MagicMock()
                        mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                        mock_client.return_value = mock_client_instance

                        store = ContractVectorStore(persist_directory="./test_db")
                        store.collection = mock_chroma_collection

                        results = await store.global_search(
                            query="Test query",
                            n_results=20
                        )

                        # Match text should be truncated to 200 chars
                        assert len(results[0]["matches"][0]["text"]) == 200

    @pytest.mark.asyncio
    async def test_global_search_handles_empty_results(
        self, mock_chroma_collection, mock_genai_embed_content
    ):
        """Test that global_search handles empty search results."""
        mock_chroma_collection.query.return_value = {
            'ids': [[]],
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }

        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            with patch('backend.services.vector_store.chromadb.PersistentClient') as mock_client:
                with patch('backend.services.vector_store.genai.configure'):
                    with patch('backend.services.vector_store.genai.embed_content', mock_genai_embed_content):
                        mock_client_instance = MagicMock()
                        mock_client_instance.get_or_create_collection.return_value = mock_chroma_collection
                        mock_client.return_value = mock_client_instance

                        store = ContractVectorStore(persist_directory="./test_db")
                        store.collection = mock_chroma_collection

                        results = await store.global_search(
                            query="nonexistent query",
                            n_results=20
                        )

                        assert results == []
