"""
Search and document management endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import List
from pathlib import Path
import re
import logging

from src.models.schemas import Query, SearchResponse, DocumentInfo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search_documents(query: Query):
    """Search documents"""
    try:
        from app import rag_service
        return await rag_service.search_documents(
            query=query.text,
            top_k=query.top_k,
            filter_dict=query.filter
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents", response_model=List[DocumentInfo])
async def list_documents():
    """List all documents"""
    try:
        from app import collection, PATHS

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


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete document and associated files"""
    try:
        from app import collection, PATHS

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
