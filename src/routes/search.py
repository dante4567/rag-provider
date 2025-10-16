"""
Search and document management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pathlib import Path
import re
import logging

from src.models.schemas import Query, SearchResponse, DocumentInfo, SearchResult
from src.core.dependencies import get_rag_service, get_paths, get_app_collection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    query: Query,
    rag_service = Depends(get_rag_service)
):
    """
    Hybrid search endpoint - combines BM25 + dense embeddings + MMR + reranking

    Uses the full hybrid retrieval pipeline:
    1. BM25 keyword search (exact term matching)
    2. Dense vector search (semantic similarity)
    3. Score fusion with weighted combination
    4. MMR for diversity
    5. Cross-encoder reranking for final ordering

    This is the recommended search endpoint for best results.
    """
    import time
    start_time = time.time()

    try:
        from src.services.reranking_service import get_reranking_service

        # Get hybrid search results (BM25 + dense + MMR)
        # Fetch more results for reranking (4x to improve recall)
        hybrid_results = await rag_service.vector_service.hybrid_search(
            query=query.text,
            top_k=query.top_k * 4,  # Get 4x for reranking (improved from 2x)
            filter=query.filter,
            apply_mmr=True  # Always use MMR for diversity
        )

        # Apply cross-encoder reranking for final ordering
        reranker = get_reranking_service()
        reranked_results = reranker.rerank(
            query=query.text,
            results=hybrid_results,
            top_k=query.top_k
        )

        search_time_ms = (time.time() - start_time) * 1000

        # Convert to SearchResult format
        search_results = []
        for result in reranked_results:
            # Normalize rerank_score to [0, 1] range if present
            # Rerank scores from cross-encoders can be any value (-10 to +10 typical)
            if 'rerank_score' in result:
                import math
                raw_score = result['rerank_score']
                relevance_score = 1 / (1 + math.exp(-raw_score))
            elif 'hybrid_score' in result:
                # Hybrid scores should already be [0, 1] but clamp anyway
                relevance_score = result['hybrid_score']
            else:
                relevance_score = result.get('relevance_score', 0.0)

            # Ensure score is in [0, 1] range
            relevance_score = max(0.0, min(1.0, relevance_score))

            search_results.append(SearchResult(
                content=result['content'],
                metadata=result['metadata'],
                relevance_score=relevance_score,
                chunk_id=result.get('chunk_id', result['metadata'].get('chunk_id', 'unknown'))
            ))

        logger.info(f"🔀 Hybrid search completed: {len(search_results)} results in {search_time_ms:.2f}ms")

        return SearchResponse(
            query=query.text,
            results=search_results,
            total_results=len(search_results),
            search_time_ms=search_time_ms
        )

    except Exception as e:
        logger.error(f"Hybrid search failed for query '{query.text}': {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/documents", response_model=List[DocumentInfo])
async def list_documents(
    collection = Depends(get_app_collection),
    PATHS: dict = Depends(get_paths)
):
    """List all documents"""
    try:
        results = collection.get()

        docs = {}
        for metadata in results['metadatas']:
            doc_id = metadata.get('doc_id')
            if doc_id and doc_id not in docs:
                # Find Obsidian file
                obsidian_path = None
                title = metadata.get('title', metadata.get('filename', ''))
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = re.sub(r'\s+', '_', safe_title)
                potential_path = Path(PATHS['obsidian_path']) / f"{safe_title}_{doc_id[:8]}.md"
                if potential_path.exists():
                    obsidian_path = str(potential_path)

                docs[doc_id] = DocumentInfo(
                    id=doc_id,
                    filename=metadata.get('filename', ''),
                    chunks=metadata.get('chunks', 0),
                    created_at=metadata.get('created_at', ''),
                    metadata=metadata,
                    obsidian_path=obsidian_path
                )

        return list(docs.values())

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{doc_id}", response_model=DocumentInfo)
async def get_document(
    doc_id: str,
    collection = Depends(get_app_collection),
    PATHS: dict = Depends(get_paths)
):
    """Get a specific document by ID"""
    try:
        # Get document chunks
        results = collection.get(where={"doc_id": doc_id})

        if not results['ids'] or not results['metadatas']:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

        # Use first chunk's metadata (all chunks have same doc metadata)
        metadata = results['metadatas'][0]

        # Find Obsidian file
        obsidian_path = None
        title = metadata.get('title', metadata.get('filename', ''))
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = re.sub(r'\s+', '_', safe_title)
        potential_path = Path(PATHS['obsidian_path']) / f"{safe_title}_{doc_id[:8]}.md"
        if potential_path.exists():
            obsidian_path = str(potential_path)

        return DocumentInfo(
            id=doc_id,
            filename=metadata.get('filename', ''),
            chunks=len(results['ids']),
            created_at=metadata.get('created_at', ''),
            metadata=metadata,
            obsidian_path=obsidian_path
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads/{thread_id}")
async def get_thread_messages(
    thread_id: str,
    collection = Depends(get_app_collection)
):
    """
    Get all messages in an email thread

    Returns messages grouped by thread_id, sorted chronologically
    """
    try:
        # Search for all documents with this thread_id
        results = collection.get(
            where={"thread_id": thread_id},
            include=['metadatas']
        )

        if not results['metadatas']:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

        # Group by doc_id and get unique documents
        docs_by_id = {}
        for metadata in results['metadatas']:
            doc_id = metadata.get('doc_id')
            if doc_id and doc_id not in docs_by_id:
                docs_by_id[doc_id] = metadata

        # Sort by created_at date
        thread_docs = sorted(docs_by_id.values(), key=lambda x: x.get('created_at', ''))

        return {
            "thread_id": thread_id,
            "message_count": len(thread_docs),
            "messages": [
                {
                    "doc_id": doc.get('doc_id'),
                    "title": doc.get('title'),
                    "subject": doc.get('subject'),
                    "sender": doc.get('sender'),
                    "created_at": doc.get('created_at'),
                    "summary": doc.get('summary', '')[:200]
                }
                for doc in thread_docs
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/{entity_name}/timeline")
async def get_entity_timeline(
    entity_name: str,
    entity_type: str = "person",
    collection = Depends(get_app_collection)
):
    """
    Get timeline of all documents mentioning an entity

    Args:
        entity_name: Name of entity (e.g., "Vimalas Borsch", "Köln")
        entity_type: Type of entity (person, place, organization)

    Returns chronologically sorted documents mentioning the entity
    """
    try:
        # Get all documents (we'll filter client-side since ChromaDB doesn't support LIKE queries)
        results = collection.get(include=['metadatas'])

        # Filter documents containing the entity
        matching_docs = []
        for metadata in results['metadatas']:
            doc_id = metadata.get('doc_id')

            # Check if entity appears in appropriate field
            if entity_type == "person":
                people_str = metadata.get('people', '')
                if isinstance(people_str, list):
                    people_names = people_str
                else:
                    people_names = people_str.split(',') if people_str else []

                if any(entity_name.lower() in name.lower() for name in people_names):
                    matching_docs.append((doc_id, metadata))

            elif entity_type == "place":
                places_str = metadata.get('places', '')
                if isinstance(places_str, list):
                    places = places_str
                else:
                    places = places_str.split(',') if places_str else []

                if any(entity_name.lower() in place.lower() for place in places):
                    matching_docs.append((doc_id, metadata))

            elif entity_type == "organization":
                orgs_str = metadata.get('organizations', '')
                if isinstance(orgs_str, list):
                    orgs = orgs_str
                else:
                    orgs = orgs_str.split(',') if orgs_str else []

                if any(entity_name.lower() in org.lower() for org in orgs):
                    matching_docs.append((doc_id, metadata))

        # Remove duplicates by doc_id
        unique_docs = {doc_id: meta for doc_id, meta in matching_docs}

        # Sort chronologically
        timeline = sorted(
            unique_docs.values(),
            key=lambda x: x.get('created_at', ''),
            reverse=True  # Most recent first
        )

        return {
            "entity": entity_name,
            "entity_type": entity_type,
            "document_count": len(timeline),
            "timeline": [
                {
                    "doc_id": doc.get('doc_id'),
                    "title": doc.get('title'),
                    "created_at": doc.get('created_at'),
                    "summary": doc.get('summary', '')[:200],
                    "doc_type": doc.get('doc_type'),
                    "thread_id": doc.get('thread_id', '')
                }
                for doc in timeline
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get entity timeline for {entity_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    collection = Depends(get_app_collection),
    PATHS: dict = Depends(get_paths)
):
    """Delete document and associated files"""
    try:
        # Get document info first
        results = collection.get(where={"doc_id": doc_id})
        if not results['ids']:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete from ChromaDB
        collection.delete(where={"doc_id": doc_id})

        # Delete Obsidian files
        obsidian_files = list(Path(PATHS['obsidian_path']).glob(f"*_{doc_id[:8]}.md"))
        for md_file in obsidian_files:
            md_file.unlink()
            logger.info(f"Deleted Obsidian file: {md_file}")

        return {"success": True, "message": f"Document {doc_id} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
