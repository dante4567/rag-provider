"""
Unit tests for DocumentService
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from src.services.document_service import DocumentService
from src.core.config import Settings


@pytest.fixture
def settings():
    """Create test settings"""
    return Settings(
        chunk_size=1000,
        chunk_overlap=200,
        use_ocr=True,
        ocr_provider="tesseract",
        ocr_languages="eng,deu"
    )


@pytest.fixture
def document_service(settings):
    """Create DocumentService instance"""
    return DocumentService(settings)


@pytest.mark.asyncio
async def test_extract_text_from_txt_file(document_service):
    """Test text extraction from plain text file"""
    # Create temporary text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a test document.\nIt has multiple lines.")
        temp_path = f.name

    try:
        content, doc_type, metadata = await document_service.extract_text_from_file(
            temp_path,
            process_ocr=False
        )

        assert "test document" in content
        assert doc_type.value == "text"
        assert metadata["file_type"] == ".txt"
        assert metadata["file_size"] > 0
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_extract_text_from_pdf_file(document_service):
    """Test text extraction from PDF file (mocked)"""
    with patch('src.services.document_service.extract_text_from_pdf') as mock_extract:
        mock_extract.return_value = "PDF content here"

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            temp_path = f.name

        try:
            content, doc_type, metadata = await document_service.extract_text_from_file(
                temp_path,
                process_ocr=False
            )

            assert content == "PDF content here"
            assert doc_type.value == "pdf"
            mock_extract.assert_called_once()
        finally:
            Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_chunk_text(document_service):
    """Test text chunking functionality"""
    long_text = "word " * 500  # Create text longer than chunk_size

    chunks = document_service.chunk_text(long_text)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= document_service.settings.chunk_size + 200  # Allow for overlap


@pytest.mark.asyncio
async def test_extract_text_file_not_found(document_service):
    """Test handling of non-existent file"""
    with pytest.raises(FileNotFoundError):
        await document_service.extract_text_from_file(
            "/non/existent/file.txt",
            process_ocr=False
        )


@pytest.mark.asyncio
async def test_extract_text_with_ocr_disabled(document_service):
    """Test that OCR is skipped when disabled"""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        temp_path = f.name

    try:
        with patch('src.services.document_service.extract_text_from_pdf') as mock_extract:
            mock_extract.return_value = "PDF text without OCR"

            content, _, _ = await document_service.extract_text_from_file(
                temp_path,
                process_ocr=False
            )

            assert content == "PDF text without OCR"
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_metadata_extraction(document_service):
    """Test that metadata is properly extracted"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Test content")
        temp_path = f.name

    try:
        _, _, metadata = await document_service.extract_text_from_file(temp_path)

        assert "file_name" in metadata
        assert "file_type" in metadata
        assert "file_size" in metadata
        assert "extraction_method" in metadata
        assert metadata["file_type"] == ".txt"
    finally:
        Path(temp_path).unlink()
