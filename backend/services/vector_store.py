"""
ChromaDB vector store for semantic search over legal contracts.

Provides persistent storage and retrieval of document sections using
Google's text-embedding-004 model for embeddings.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import google.generativeai as genai

logger = logging.getLogger(__name__)


class ContractVectorStore:
    """
    Vector store for legal contract sections using ChromaDB.

    Features:
    - Persistent storage with ChromaDB
    - Google text-embedding-004 embeddings
    - Semantic search with relevance scoring
    - Document filtering by contract ID
    """

    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "legal_contracts"
    ):
        """
        Initialize the vector store with persistent ChromaDB client.

        Args:
            persist_directory: Directory for persistent ChromaDB storage
            collection_name: Name of the ChromaDB collection
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name

        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Configure Google embedding model
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        genai.configure(api_key=api_key)

        # Initialize collection with cosine similarity
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None  # We'll handle embeddings manually
        )

        logger.info(
            f"Vector store initialized with collection '{collection_name}' "
            f"at {persist_directory}"
        )

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts using Google's embedding model.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        try:
            embeddings = []
            # Process in batches to handle rate limits
            batch_size = 100

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]

                # Generate embeddings using Google's API
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=batch,
                    task_type="retrieval_document"
                )

                embeddings.extend(result['embedding'])
                logger.debug(f"Generated embeddings for batch {i//batch_size + 1}")

            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk
            chunk_size: Maximum characters per chunk
            overlap: Number of overlapping characters between chunks

        Returns:
            List of text chunks
        """
        if not text:
            return []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Try to break at sentence or word boundary
            if end < len(text):
                # Look for sentence break
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')

                if last_period > chunk_size * 0.7:
                    chunk = chunk[:last_period + 1]
                elif last_newline > chunk_size * 0.7:
                    chunk = chunk[:last_newline]

            chunks.append(chunk.strip())

            # Move start position with overlap
            start = start + len(chunk) - overlap

            # Prevent infinite loop
            if start >= len(text):
                break

        logger.debug(f"Split text into {len(chunks)} chunks")
        return chunks

    async def store_document_sections(
        self,
        contract_id: str,
        document_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Chunk document, generate embeddings, and store in vector database.

        Args:
            contract_id: Unique identifier for the contract
            document_text: Full text of the document
            metadata: Additional metadata to store with each chunk

        Returns:
            List of chunk IDs that were stored
        """
        try:
            # Chunk the document
            chunks = self._chunk_text(document_text)

            if not chunks:
                logger.warning(f"No chunks generated for contract {contract_id}")
                return []

            # Generate embeddings
            embeddings = self._generate_embeddings(chunks)

            # Prepare metadata for each chunk
            base_metadata = metadata or {}
            chunk_metadata = [
                {
                    **base_metadata,
                    "contract_id": contract_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
                for i in range(len(chunks))
            ]

            # Generate unique IDs for each chunk
            chunk_ids = [f"{contract_id}_chunk_{i}" for i in range(len(chunks))]

            # Store in ChromaDB
            self.collection.add(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=chunk_metadata
            )

            logger.info(
                f"Stored {len(chunks)} chunks for contract {contract_id} "
                f"in vector store"
            )

            return chunk_ids

        except Exception as e:
            logger.error(f"Error storing document sections: {e}")
            raise

    async def semantic_search(
        self,
        query: str,
        n_results: int = 5,
        contract_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search over stored documents.

        Args:
            query: Search query text
            n_results: Number of results to return
            contract_id: Optional filter by specific contract

        Returns:
            List of search results with text, metadata, and relevance scores
        """
        try:
            # Generate query embedding
            query_result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )
            query_embedding = query_result['embedding']

            # Prepare where filter if contract_id specified
            where_filter = None
            if contract_id:
                where_filter = {"contract_id": contract_id}

            # Perform search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter
            )

            # Format results
            formatted_results = []

            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        "id": results['ids'][0][i],
                        "text": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "distance": results['distances'][0][i] if 'distances' in results else None,
                        "relevance_score": 1 - results['distances'][0][i] if 'distances' in results else None
                    })

            logger.info(
                f"Semantic search returned {len(formatted_results)} results "
                f"for query: '{query[:50]}...'"
            )

            return formatted_results

        except Exception as e:
            logger.error(f"Error performing semantic search: {e}")
            raise

    def delete_contract(self, contract_id: str) -> int:
        """
        Delete all chunks associated with a contract.

        Args:
            contract_id: Contract ID to delete

        Returns:
            Number of chunks deleted
        """
        try:
            # Get all chunks for this contract
            results = self.collection.get(
                where={"contract_id": contract_id}
            )

            if results['ids']:
                self.collection.delete(ids=results['ids'])
                deleted_count = len(results['ids'])
                logger.info(f"Deleted {deleted_count} chunks for contract {contract_id}")
                return deleted_count

            return 0

        except Exception as e:
            logger.error(f"Error deleting contract: {e}")
            raise

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store collection.

        Returns:
            Dictionary with collection statistics
        """
        try:
            count = self.collection.count()

            return {
                "collection_name": self.collection_name,
                "total_chunks": count,
                "persist_directory": self.persist_directory
            }

        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            raise

    def reset_collection(self) -> None:
        """
        Delete all data in the collection. Use with caution!
        """
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.warning(f"Collection '{self.collection_name}' has been reset")

        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
            raise
