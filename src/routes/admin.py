"""
Administrative endpoints for maintenance and cleanup
"""
from fastapi import APIRouter, HTTPException
import logging
from src.services.entity_enrichment_service import EntityEnrichmentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/cleanup-corrupted")
async def cleanup_corrupted_documents():
    """Remove documents with corrupted or binary content"""
    try:
        from app import collection, rag_service

        all_docs = collection.get()

        if not all_docs or not all_docs['documents']:
            return {"removed_corrupted": 0, "message": "No documents found"}

        corrupted_ids = []
        for i, doc_content in enumerate(all_docs['documents']):
            if doc_content:
                # Check for binary content indicators
                if (len(doc_content) > 100 and
                    (doc_content.count('\x00') > 0 or
                     doc_content.count('\ufffd') > 0 or  # replacement character
                     len([c for c in doc_content if ord(c) < 32 and c not in '\t\n\r']) > len(doc_content) * 0.1)):
                    corrupted_ids.append(all_docs['ids'][i])

        if corrupted_ids:
            rag_service.collection.delete(ids=corrupted_ids)
            logger.info(f"Removed {len(corrupted_ids)} corrupted documents")

        return {
            "removed_corrupted": len(corrupted_ids),
            "message": f"Successfully removed {len(corrupted_ids)} corrupted documents"
        }

    except Exception as e:
        logger.error(f"Corruption cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.post("/cleanup-duplicates")
async def cleanup_duplicates():
    """Remove duplicate documents based on content hash"""
    try:
        from app import collection

        # Get all documents grouped by content_hash
        all_docs = collection.get()

        if not all_docs or not all_docs['metadatas']:
            return {"removed_duplicates": 0, "message": "No documents found"}

        # Group by content_hash
        hash_groups = {}
        for i, metadata in enumerate(all_docs['metadatas']):
            content_hash = metadata.get('content_hash')
            if content_hash:
                if content_hash not in hash_groups:
                    hash_groups[content_hash] = []
                hash_groups[content_hash].append({
                    'id': all_docs['ids'][i],
                    'metadata': metadata,
                    'index': i
                })

        # Find duplicates (groups with more than 1 document)
        duplicates_removed = 0
        for content_hash, docs in hash_groups.items():
            if len(docs) > 1:
                # Keep the first one, remove the rest
                docs_to_remove = docs[1:]  # Remove all except the first
                ids_to_remove = [doc['id'] for doc in docs_to_remove]

                try:
                    collection.delete(ids=ids_to_remove)
                    duplicates_removed += len(ids_to_remove)
                    logger.info(f"Removed {len(ids_to_remove)} duplicates for hash {content_hash}")
                except Exception as e:
                    logger.error(f"Failed to remove duplicates for hash {content_hash}: {e}")

        return {
            "removed_duplicates": duplicates_removed,
            "message": f"Successfully removed {duplicates_removed} duplicate documents"
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.post("/reset-collection")
async def reset_collection(confirm: str = None):
    """Reset the entire collection (DANGEROUS - requires confirmation)"""
    if confirm != "yes-delete-everything":
        raise HTTPException(
            status_code=400,
            detail="Must provide confirm='yes-delete-everything' to reset collection"
        )

    try:
        from app import collection

        # Get all IDs
        all_docs = collection.get()
        if all_docs and all_docs['ids']:
            collection.delete(ids=all_docs['ids'])
            logger.warning(f"Collection reset - removed {len(all_docs['ids'])} documents")
            return {
                "success": True,
                "removed_count": len(all_docs['ids']),
                "message": "Collection successfully reset"
            }
        else:
            return {
                "success": True,
                "removed_count": 0,
                "message": "Collection was already empty"
            }

    except Exception as e:
        logger.error(f"Collection reset failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


@router.get("/documents")
async def list_documents_admin(limit: int = 100, offset: int = 0):
    """List all documents with metadata (admin route)"""
    return await _list_documents_impl(limit, offset)


async def _list_documents_impl(limit: int = 100, offset: int = 0):
    """Shared implementation for document listing"""
    try:
        from app import collection

        all_docs = collection.get()

        if not all_docs or not all_docs['ids']:
            return {
                "documents": [],
                "total": 0
            }

        # Get unique documents by doc_id
        doc_map = {}
        for i, metadata in enumerate(all_docs.get('metadatas', [])):
            doc_id = metadata.get('doc_id')
            if doc_id and doc_id not in doc_map:
                doc_map[doc_id] = {
                    "doc_id": doc_id,
                    "filename": metadata.get('filename', 'Unknown'),
                    "created_at": metadata.get('created_at'),
                    "title": metadata.get('title'),
                    "chunk_count": 0
                }
            if doc_id in doc_map:
                doc_map[doc_id]["chunk_count"] += 1

        documents = list(doc_map.values())

        # Apply pagination
        paginated = documents[offset:offset + limit]

        return {
            "documents": paginated,
            "total": len(documents),
            "offset": offset,
            "limit": limit
        }

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enrich-entities")
async def enrich_entities():
    """
    Enrich entity reference files with aggregated information from all documents.

    This endpoint:
    - Reads all documents from ChromaDB
    - Aggregates entity information (roles, organizations, contacts, dates)
    - Updates entity reference files in refs/ directory

    Enriches:
    - People: roles, organizations, emails, first/last seen
    - Organizations: locations, key people, first/last seen
    - Places: related orgs and people
    - Technologies: used by (orgs/people)
    """
    try:
        from app import rag_service

        # Initialize enrichment service
        enrichment_service = EntityEnrichmentService()

        # Run enrichment
        enrichment_service.enrich_all_entities(rag_service.vector_service)

        return {
            "success": True,
            "message": "Entity enrichment completed successfully"
        }

    except Exception as e:
        logger.error(f"Entity enrichment failed: {e}")
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")
