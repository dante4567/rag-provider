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
from src.core.dependencies import get_rag_service, get_paths

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_document(
    document: Document,
    rag_service = Depends(get_rag_service)
):
    """Ingest document via API"""
    try:
        # Auth handled by app-level middleware
        return await rag_service.process_document(
            content=document.content,
            filename=document.filename,
            document_type=document.document_type,
            process_ocr=document.process_ocr,
            generate_obsidian=document.generate_obsidian,
            file_metadata=document.metadata,
            use_critic=document.use_critic
        )
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    process_ocr: str = Form("false"),
    generate_obsidian: str = Form("true"),
    use_critic: str = Form("false"),
    use_iteration: str = Form("false"),
    rag_service = Depends(get_rag_service),
    PATHS: dict = Depends(get_paths)
):
    """
    Ingest file via upload

    Args:
        file: File to upload
        process_ocr: Whether to run OCR (for images/scanned PDFs)
        generate_obsidian: Whether to generate Obsidian markdown
        use_critic: Whether to score enrichment quality (adds $0.005/doc)
        use_iteration: Whether to use self-improvement loop (critic + editor, slower but better quality)
    """
    # Convert string form params to boolean
    process_ocr_bool = process_ocr.lower() in ("true", "1", "yes")
    generate_obsidian_bool = generate_obsidian.lower() in ("true", "1", "yes")
    use_critic_bool = use_critic.lower() in ("true", "1", "yes")
    use_iteration_bool = use_iteration.lower() in ("true", "1", "yes")

    logger.info(f"Received file for ingestion: {file.filename}, Content-Type: {file.content_type}, use_critic={use_critic_bool}, use_iteration={use_iteration_bool}")
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
            process_ocr=process_ocr_bool,
            generate_obsidian=generate_obsidian_bool,
            use_critic=use_critic_bool,
            use_iteration=use_iteration_bool
        )

        # Archive original file if successful (Priority 1: Lossless data archiving)
        if result.success:
            import shutil
            from datetime import datetime
            archive_dir = Path(PATHS.get('archive_path', '/data/processed_originals'))
            archive_dir.mkdir(parents=True, exist_ok=True)

            # Archive with timestamp to prevent overwrites
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_filename = f"{timestamp}_{file.filename}"
            archive_path = archive_dir / archive_filename
            shutil.copy2(str(temp_path), str(archive_path))
            logger.info(f"💾 Archived original to: {archive_path}")

        # Copy to Obsidian attachments if successful
        if generate_obsidian_bool and result.success:
            import shutil
            attachments_dir = Path(PATHS.get('obsidian_path', '/data/obsidian')) / 'attachments'
            attachments_dir.mkdir(parents=True, exist_ok=True)

            # Copy with original filename (no UUID prefix)
            dest_path = attachments_dir / file.filename
            shutil.copy2(str(temp_path), str(dest_path))
            logger.info(f"📎 Copied original to: {dest_path}")

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
    process_ocr: str = Form("false"),
    generate_obsidian: str = Form("true"),
    use_critic: str = Form("false"),
    rag_service = Depends(get_rag_service),
    PATHS: dict = Depends(get_paths)
):
    """Batch file ingestion"""
    # Convert string form params to boolean
    process_ocr_bool = process_ocr.lower() in ("true", "1", "yes")
    generate_obsidian_bool = generate_obsidian.lower() in ("true", "1", "yes")
    use_critic_bool = use_critic.lower() in ("true", "1", "yes")

    logger.info(f"Batch ingestion: {len(files)} files, use_critic={use_critic_bool}")

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
            task = rag_service.process_file(str(temp_path), process_ocr_bool, generate_obsidian_bool, use_critic_bool)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions and archive successful files
        processed_results = []
        import shutil
        from datetime import datetime
        archive_dir = Path(PATHS.get('archive_path', '/data/processed_originals'))
        archive_dir.mkdir(parents=True, exist_ok=True)

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
                # Archive original file if successful (Priority 1: Lossless data archiving)
                if result.success:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive_filename = f"{timestamp}_{files[i].filename}"
                    archive_path = archive_dir / archive_filename
                    shutil.copy2(str(temp_paths[i]), str(archive_path))
                    logger.info(f"💾 Archived original [{i+1}/{len(files)}]: {archive_path}")

                processed_results.append(result)

        return processed_results

    finally:
        # Clean up temp files
        for temp_path in temp_paths:
            if temp_path.exists():
                temp_path.unlink()
