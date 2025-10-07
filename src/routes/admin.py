"""
Administrative endpoints for maintenance and cleanup
"""
from fastapi import APIRouter, HTTPException
import logging

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
