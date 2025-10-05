"""
Unit tests for OCRService
"""
import pytest
import tempfile
from pathlib import Path
from PIL import Image
from unittest.mock import Mock, patch
from src.services.ocr_service import OCRService


@pytest.fixture
def ocr_service():
    """Create OCRService instance"""
    return OCRService(languages=['eng', 'deu'])


@pytest.mark.asyncio
async def test_extract_text_from_image(ocr_service):
    """Test OCR text extraction from image"""
    # Create a temporary image
    img = Image.new('RGB', (200, 100), color='white')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name)
        temp_path = f.name

    try:
        with patch('pytesseract.image_to_string') as mock_ocr:
            mock_ocr.return_value = "Test OCR extracted text"

            result = await ocr_service.extract_text_from_image(temp_path)

            assert result == "Test OCR extracted text"
            mock_ocr.assert_called_once()
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_extract_text_with_multiple_languages(ocr_service):
    """Test OCR with multiple language support"""
    img = Image.new('RGB', (200, 100), color='white')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name)
        temp_path = f.name

    try:
        with patch('pytesseract.image_to_string') as mock_ocr:
            mock_ocr.return_value = "Multilingual text"

            await ocr_service.extract_text_from_image(temp_path)

            call_args = mock_ocr.call_args[1]
            assert 'lang' in call_args
            assert 'eng' in call_args['lang']
            assert 'deu' in call_args['lang']
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_extract_text_from_pdf_pages(ocr_service):
    """Test OCR extraction from PDF (converted to images)"""
    with patch('pdf2image.convert_from_path') as mock_convert:
        # Mock PDF pages as images
        mock_images = [
            Image.new('RGB', (200, 100), color='white'),
            Image.new('RGB', (200, 100), color='white')
        ]
        mock_convert.return_value = mock_images

        with patch('pytesseract.image_to_string') as mock_ocr:
            mock_ocr.side_effect = ["Page 1 text", "Page 2 text"]

            result = await ocr_service.extract_text_from_pdf("test.pdf")

            assert "Page 1 text" in result
            assert "Page 2 text" in result
            assert mock_ocr.call_count == 2


@pytest.mark.asyncio
async def test_image_preprocessing(ocr_service):
    """Test that images are preprocessed for better OCR"""
    img = Image.new('RGB', (200, 100), color='white')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name)
        temp_path = f.name

    try:
        with patch('pytesseract.image_to_string') as mock_ocr:
            mock_ocr.return_value = "Preprocessed text"

            # OCR service should preprocess image (convert to grayscale, etc.)
            result = await ocr_service.extract_text_from_image(
                temp_path,
                preprocess=True
            )

            assert result == "Preprocessed text"
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_empty_image_handling(ocr_service):
    """Test handling of images with no text"""
    img = Image.new('RGB', (200, 100), color='white')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name)
        temp_path = f.name

    try:
        with patch('pytesseract.image_to_string') as mock_ocr:
            mock_ocr.return_value = ""

            result = await ocr_service.extract_text_from_image(temp_path)

            assert result == ""
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_invalid_image_file(ocr_service):
    """Test handling of invalid/corrupted image"""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(b"not a valid image")
        temp_path = f.name

    try:
        with pytest.raises(Exception):
            await ocr_service.extract_text_from_image(temp_path)
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_supported_languages(ocr_service):
    """Test that supported languages are correctly configured"""
    assert 'eng' in ocr_service.languages
    assert 'deu' in ocr_service.languages


@pytest.mark.asyncio
async def test_confidence_score(ocr_service):
    """Test OCR confidence score extraction"""
    img = Image.new('RGB', (200, 100), color='white')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name)
        temp_path = f.name

    try:
        with patch('pytesseract.image_to_data') as mock_ocr_data:
            mock_ocr_data.return_value = {
                'text': ['Test', 'text'],
                'conf': [95, 90]
            }

            result = await ocr_service.extract_text_with_confidence(temp_path)

            assert 'text' in result
            assert 'confidence' in result
            assert result['confidence'] > 0
    finally:
        Path(temp_path).unlink()
