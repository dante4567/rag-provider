"""
Vector database service for ChromaDB operations

Handles document storage, retrieval, and search operations
"""
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import chromadb

from src.core.config import Settings
from src.services.hybrid_search_service import get_hybrid_search_service

logger = logging.getLogger(__name__)


class VectorService:
    """
    Service for vector database operations using ChromaDB

    Manages document chunks, embeddings, and similarity search
    """

    def __init__(self, collection: chromadb.Collection, settings: Settings):
        """
        Initialize vector service

        Args:
            collection: ChromaDB collection instance
            settings: Application settings
        """
        self.collection = collection
        self.settings = settings
        self.hybrid_search_service = get_hybrid_search_service()

    async def add_document(
        self,
        doc_id: str,
        chunks: List[str],
        metadata: Dict[str, Any],
        embeddings: Optional[List[List[float]]] = None
    ) -> int:
        """
        Add document chunks to vector store

        Args:
            doc_id: Unique document identifier
            chunks: List of text chunks
            metadata: Document metadata
            embeddings: Pre-computed embeddings (optional, ChromaDB can generate)

        Returns:
            Number of chunks added

        Raises:
            Exception: If addition fails
        """
        if not chunks:
            raise ValueError("No chunks to add")

        try:
            chunk_ids = []
            chunk_metadatas = []
            chunk_texts = []

            # Prepare chunks for insertion
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                chunk_ids.append(chunk_id)

                # Add chunk-specific metadata
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                    "doc_id": doc_id,
                    "created_at": datetime.now().isoformat()
                })
                chunk_metadatas.append(chunk_metadata)
                chunk_texts.append(chunk)

            # Add to ChromaDB
            if embeddings:
                self.collection.add(
                    ids=chunk_ids,
                    documents=chunk_texts,
                    metadatas=chunk_metadatas,
                    embeddings=embeddings
                )
            else:
                # Let ChromaDB generate embeddings
                self.collection.add(
                    ids=chunk_ids,
                    documents=chunk_texts,
                    metadatas=chunk_metadatas
                )

            # Add to BM25 index for hybrid search
            self.hybrid_search_service.add_documents(doc_id, chunk_texts, metadata)

            logger.info(f"Added {len(chunks)} chunks for document {doc_id} (ChromaDB + BM25)")
            return len(chunks)

        except Exception as e:
            logger.error(f"Failed to add document {doc_id}: {e}")
            raise

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents

        Args:
            query: Search query text
            top_k: Number of results to return
            filter: Metadata filters (optional)

        Returns:
            List of search results with content, metadata, and scores
        """
        try:
            # Perform similarity search
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=filter,
                include=["documents", "metadatas", "distances"]
            )

            # Format results
            formatted_results = []

            if results and results["ids"] and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    formatted_results.append({
                        "chunk_id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "relevance_score": 1.0 - results["distances"][0][i],  # Convert distance to similarity
                    })

            logger.info(f"Search for '{query[:50]}...' returned {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            raise

    async def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        apply_mmr: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining BM25 + dense embeddings

        Uses:
        1. Dense vector search (semantic similarity)
        2. BM25 search (keyword matching)
        3. Score fusion (weighted combination)
        4. MMR for diversity (optional)

        Args:
            query: Search query text
            top_k: Number of results to return
            filter: Metadata filters (optional)
            apply_mmr: Whether to apply MMR for diversity

        Returns:
            List of hybrid search results
        """
        try:
            # First, get dense search results (fetch more for better fusion)
            dense_results = await self.search(query, top_k=top_k * 3, filter=filter)

            # Use hybrid search service to fuse with BM25
            hybrid_results = self.hybrid_search_service.hybrid_search(
                query=query,
                dense_results=dense_results,
                top_k=top_k,
                apply_mmr=apply_mmr
            )

            logger.info(f"🔀 Hybrid search for '{query[:50]}...' returned {len(hybrid_results)} results")
            return hybrid_results

        except Exception as e:
            logger.error(f"Hybrid search failed for query '{query}': {e}")
            raise

    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete all chunks for a document

        Args:
            doc_id: Document ID to delete

        Returns:
            True if successful

        Raises:
            Exception: If deletion fails
        """
        try:
            # Find all chunk IDs for this document
            results = self.collection.get(
                where={"doc_id": doc_id},
                include=["metadatas"]
            )

            if not results or not results["ids"]:
                logger.warning(f"No chunks found for document {doc_id}")
                return False

            # Delete all chunks
            self.collection.delete(ids=results["ids"])

            logger.info(f"Deleted {len(results['ids'])} chunks for document {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            raise

    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get all chunks for a specific document

        Args:
            doc_id: Document ID

        Returns:
            Document data with chunks, or None if not found
        """
        try:
            results = self.collection.get(
                where={"doc_id": doc_id},
                include=["documents", "metadatas"]
            )

            if not results or not results["ids"]:
                return None

            # Combine chunks
            chunks = []
            metadata = results["metadatas"][0] if results["metadatas"] else {}

            for i in range(len(results["ids"])):
                chunks.append({
                    "chunk_id": results["ids"][i],
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i] if results["metadatas"] else {}
                })

            return {
                "doc_id": doc_id,
                "chunks": chunks,
                "chunk_count": len(chunks),
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            raise

    async def list_documents(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all documents in collection

        Args:
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of document summaries
        """
        try:
            # Get all items
            results = self.collection.get(
                include=["metadatas"]
            )

            if not results or not results["ids"]:
                return []

            # Group by doc_id
            docs_by_id: Dict[str, Dict] = {}

            for i, chunk_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                doc_id = metadata.get("doc_id", chunk_id.split("_chunk_")[0])

                if doc_id not in docs_by_id:
                    docs_by_id[doc_id] = {
                        "id": doc_id,
                        "chunks": 0,
                        "metadata": metadata,
                        "created_at": metadata.get("created_at", "")
                    }

                docs_by_id[doc_id]["chunks"] += 1

            # Convert to list and apply pagination
            documents = list(docs_by_id.values())

            # Sort by created_at (newest first)
            documents.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            if limit:
                documents = documents[offset:offset + limit]

            return documents

        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics

        Returns:
            Dictionary with collection stats
        """
        try:
            # Get all items for counting
            results = self.collection.get()

            total_chunks = len(results["ids"]) if results and results["ids"] else 0

            # Count unique documents
            doc_ids = set()
            if results and results["metadatas"]:
                for metadata in results["metadatas"]:
                    doc_id = metadata.get("doc_id")
                    if doc_id:
                        doc_ids.add(doc_id)

            # Get collection metadata
            collection_metadata = self.collection.metadata or {}

            return {
                "total_documents": len(doc_ids),
                "total_chunks": total_chunks,
                "collection_name": self.collection.name,
                "collection_metadata": collection_metadata
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            raise

    async def cleanup_corrupted(self) -> Dict[str, Any]:
        """
        Remove corrupted or invalid documents

        Returns:
            Dictionary with cleanup results
        """
        try:
            results = self.collection.get(include=["metadatas", "documents"])

            corrupted_ids = []

            if results and results["ids"]:
                for i, chunk_id in enumerate(results["ids"]):
                    # Check for corruption indicators
                    is_corrupted = False

                    # Check for null/empty content
                    if not results["documents"][i] or not results["documents"][i].strip():
                        is_corrupted = True

                    # Check for missing metadata
                    if not results["metadatas"][i]:
                        is_corrupted = True

                    if is_corrupted:
                        corrupted_ids.append(chunk_id)

            # Delete corrupted chunks
            if corrupted_ids:
                self.collection.delete(ids=corrupted_ids)
                logger.info(f"Removed {len(corrupted_ids)} corrupted chunks")

            return {
                "removed_count": len(corrupted_ids),
                "corrupted_ids": corrupted_ids
            }

        except Exception as e:
            logger.error(f"Failed to cleanup corrupted documents: {e}")
            raise

    async def find_duplicates(self) -> List[Dict[str, Any]]:
        """
        Find potential duplicate documents

        Returns:
            List of potential duplicates
        """
        try:
            results = self.collection.get(include=["documents", "metadatas"])

            if not results or not results["documents"]:
                return []

            # Simple duplicate detection based on content hash
            seen_hashes = {}
            duplicates = []

            for i, doc in enumerate(results["documents"]):
                # Use simple hash
                content_hash = hash(doc[:1000])  # Hash first 1000 chars

                if content_hash in seen_hashes:
                    duplicates.append({
                        "chunk_id": results["ids"][i],
                        "duplicate_of": seen_hashes[content_hash],
                        "metadata": results["metadatas"][i] if results["metadatas"] else {}
                    })
                else:
                    seen_hashes[content_hash] = results["ids"][i]

            return duplicates

        except Exception as e:
            logger.error(f"Failed to find duplicates: {e}")
            raise
