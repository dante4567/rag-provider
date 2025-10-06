"""
Document ingestion endpoints
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import List
from pathlib import Path
import uuid
import aiofiles
import asyncio
import logging

from src.models.schemas import Document, IngestResponse, ObsidianMetadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_document(document: Document):
    """Ingest document via API"""
    try:
        from app import rag_service, verify_token
        # Auth handled by app-level middleware
        return await rag_service.process_document(
            content=document.content,
            filename=document.filename,
            document_type=document.document_type,
            process_ocr=document.process_ocr,
            generate_obsidian=document.generate_obsidian,
            file_metadata=document.metadata
        )
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    process_ocr: bool = Form(False),
    generate_obsidian: bool = Form(True)
):
    """Ingest file via upload"""
    from app import rag_service, PATHS

    logger.info(f"Received file for ingestion: {file.filename}, Content-Type: {file.content_type}")
    temp_path = None
    try:
        # Save uploaded file temporarily
        temp_path = Path(PATHS['temp_path']) / f"upload_{uuid.uuid4()}_{file.filename}"

        async with aiofiles.open(temp_path, 'wb') as f:
            content = await file.read()
            await f.write(content)

        # Process file
        result = await rag_service.process_file(
            str(temp_path),
            process_ocr=process_ocr,
            generate_obsidian=generate_obsidian
        )

        # Clean up temp file
        temp_path.unlink()

        return result

    except Exception as e:
        if temp_path and temp_path.exists():
            temp_path.unlink()
        logger.error(f"File ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=List[IngestResponse])
async def ingest_batch_files(
    files: List[UploadFile] = File(...),
    process_ocr: bool = Form(False),
    generate_obsidian: bool = Form(True)
):
    """Batch file ingestion"""
    from app import rag_service, PATHS

    results = []
    temp_paths = []

    try:
        # Save all files first
        for file in files:
            temp_path = Path(PATHS['temp_path']) / f"batch_{uuid.uuid4()}_{file.filename}"
            temp_paths.append(temp_path)

            async with aiofiles.open(temp_path, 'wb') as f:
                content = await file.read()
                await f.write(content)

        # Process files concurrently
        tasks = []
        for temp_path in temp_paths:
            task = rag_service.process_file(str(temp_path), process_ocr, generate_obsidian)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch processing failed for file {i}: {result}")
                processed_results.append(IngestResponse(
                    success=False,
                    doc_id="",
                    chunks=0,
                    metadata=ObsidianMetadata(
                        title=f"Failed: {files[i].filename}",
                        keywords={"primary": [], "secondary": [], "related": []},
                        entities={"people": [], "organizations": [], "locations": [], "technologies": []}
                    )
                ))
            else:
                processed_results.append(result)

        return processed_results

    finally:
        # Clean up temp files
        for temp_path in temp_paths:
            if temp_path.exists():
                temp_path.unlink()
