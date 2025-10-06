"""
Unit tests for OCRService

Tests OCR functionality including:
- Availability checking
- Image text extraction
- PDF OCR processing
- Confidence scoring
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import tempfile


# =============================================================================
# OCRService Tests
# =============================================================================

class TestOCRService:
    """Test the OCRService class"""

    @pytest.fixture
    def mock_ocr_available(self):
        """Mock OCR dependencies as available"""
        with patch('src.services.ocr_service.OCR_AVAILABLE', True):
            yield

    @pytest.fixture
    def mock_ocr_unavailable(self):
        """Mock OCR dependencies as unavailable"""
        with patch('src.services.ocr_service.OCR_AVAILABLE', False):
            yield

    @pytest.fixture
    def service(self):
        """Create OCRService instance"""
        from src.services.ocr_service import OCRService
        return OCRService(languages=['eng', 'deu'])

    def test_init_default_language(self):
        """Test initialization with default language"""
        from src.services.ocr_service import OCRService
        service = OCRService()

        assert service.languages == ['eng']

    def test_init_custom_languages(self):
        """Test initialization with custom languages"""
        from src.services.ocr_service import OCRService
        service = OCRService(languages=['eng', 'deu', 'fra'])

        assert 'eng' in service.languages
        assert 'deu' in service.languages
        assert 'fra' in service.languages

    def test_is_available_when_deps_installed(self, mock_ocr_available, service):
        """Test is_available returns True when dependencies installed"""
        assert service.is_available() is True

    def test_is_available_when_deps_missing(self, mock_ocr_unavailable):
        """Test is_available returns False when dependencies missing"""
        from src.services.ocr_service import OCRService
        service = OCRService()

        assert service.is_available() is False

    @patch('src.services.ocr_service.pytesseract.image_to_string')
    @patch('src.services.ocr_service.Image.open')
    def test_extract_text_from_image_basic(
        self,
        mock_image_open,
        mock_tesseract,
        mock_ocr_available,
        service
    ):
        """Test basic image text extraction"""
        # Mock image
        mock_image = Mock()
        mock_image_open.return_value = mock_image

        # Mock tesseract output
        mock_tesseract.return_value = "Extracted text from image"

        result = service.extract_text_from_image("/fake/image.png")

        assert result == "Extracted text from image"
        mock_tesseract.assert_called_once()

    @patch('src.services.ocr_service.pytesseract.image_to_string')
    @patch('src.services.ocr_service.Image.open')
    def test_extract_text_from_image_with_languages(
        self,
        mock_image_open,
        mock_tesseract,
        mock_ocr_available,
        service
    ):
        """Test image extraction with custom languages"""
        mock_image = Mock()
        mock_image_open.return_value = mock_image
        mock_tesseract.return_value = "Text"

        service.extract_text_from_image(
            "/fake/image.png",
            languages=['fra', 'spa']
        )

        # Check language codes passed
        call_args = mock_tesseract.call_args
        assert 'fra+spa' in str(call_args)

    @patch('src.services.ocr_service.pytesseract.image_to_string')
    @patch('src.services.ocr_service.Image.open')
    def test_extract_text_from_image_strips_whitespace(
        self,
        mock_image_open,
        mock_tesseract,
        mock_ocr_available,
        service
    ):
        """Test that extracted text is stripped"""
        mock_image = Mock()
        mock_image_open.return_value = mock_image
        mock_tesseract.return_value = "  Text with spaces  \n\n"

        result = service.extract_text_from_image("/fake/image.png")

        assert result == "Text with spaces"

    def test_extract_text_from_image_no_deps(self, mock_ocr_unavailable):
        """Test extraction raises exception when deps missing"""
        from src.services.ocr_service import OCRService
        service = OCRService()

        with pytest.raises(Exception) as exc_info:
            service.extract_text_from_image("/fake/image.png")

        assert "OCR dependencies not available" in str(exc_info.value)

    @patch('src.services.ocr_service.convert_from_path')
    @patch('src.services.ocr_service.pytesseract.image_to_string')
    @patch('src.services.ocr_service.Image.open')
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_extract_text_from_pdf_images_basic(
        self,
        mock_unlink,
        mock_exists,
        mock_image_open,
        mock_tesseract,
        mock_convert,
        mock_ocr_available,
        service
    ):
        """Test PDF OCR extraction"""
        # Mock PDF pages
        mock_page1 = Mock()
        mock_page2 = Mock()
        mock_convert.return_value = [mock_page1, mock_page2]

        # Mock image operations
        mock_image = Mock()
        mock_image_open.return_value = mock_image
        mock_exists.return_value = True

        # Mock tesseract extraction
        mock_tesseract.side_effect = ["Page 1 text", "Page 2 text"]

        result = service.extract_text_from_pdf_images("/fake/document.pdf")

        # Should contain text from both pages
        assert "Page 1" in result
        assert "Page 2" in result

        # Should have called convert_from_path
        mock_convert.assert_called_once()

    @patch('src.services.ocr_service.convert_from_path')
    @patch('src.services.ocr_service.pytesseract.image_to_string')
    @patch('src.services.ocr_service.Image.open')
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_extract_text_from_pdf_cleans_temp_files(
        self,
        mock_unlink,
        mock_exists,
        mock_image_open,
        mock_tesseract,
        mock_convert,
        mock_ocr_available,
        service
    ):
        """Test that temporary files are cleaned up"""
        mock_page = Mock()
        mock_convert.return_value = [mock_page]

        mock_image = Mock()
        mock_image_open.return_value = mock_image
        mock_exists.return_value = True
        mock_tesseract.return_value = "Text"

        service.extract_text_from_pdf_images("/fake/doc.pdf")

        # Should clean up temp files
        assert mock_unlink.called

    @patch('src.services.ocr_service.pytesseract.image_to_data')
    @patch('src.services.ocr_service.Image.open')
    def test_extract_with_confidence_basic(
        self,
        mock_image_open,
        mock_image_to_data,
        mock_ocr_available,
        service
    ):
        """Test extraction with confidence scoring"""
        mock_image = Mock()
        mock_image_open.return_value = mock_image

        # Mock tesseract data output
        mock_image_to_data.return_value = {
            'text': ['Hello', 'World', 'Test'],
            'conf': [85, 90, 75]  # Confidence scores
        }

        text, confidence = service.extract_with_confidence(
            "/fake/image.png",
            min_confidence=0.7
        )

        # All words above 70% confidence
        assert "Hello" in text
        assert "World" in text
        assert "Test" in text

        # Average confidence should be around 0.83
        assert 0.75 <= confidence <= 0.9

    @patch('src.services.ocr_service.pytesseract.image_to_data')
    @patch('src.services.ocr_service.Image.open')
    def test_extract_with_confidence_filtering(
        self,
        mock_image_open,
        mock_image_to_data,
        mock_ocr_available,
        service
    ):
        """Test that low-confidence text is filtered out"""
        mock_image = Mock()
        mock_image_open.return_value = mock_image

        # Mock data with mixed confidence
        mock_image_to_data.return_value = {
            'text': ['Good', 'Bad', 'Excellent'],
            'conf': [90, 30, 95]  # 'Bad' has low confidence
        }

        text, confidence = service.extract_with_confidence(
            "/fake/image.png",
            min_confidence=0.6
        )

        # Low confidence word should be filtered
        assert "Good" in text
        assert "Excellent" in text
        assert "Bad" not in text

    @patch('src.services.ocr_service.pytesseract.image_to_data')
    @patch('src.services.ocr_service.Image.open')
    def test_extract_with_confidence_handles_no_text(
        self,
        mock_image_open,
        mock_image_to_data,
        mock_ocr_available,
        service
    ):
        """Test handling when no text detected"""
        mock_image = Mock()
        mock_image_open.return_value = mock_image

        # Mock no text detected
        mock_image_to_data.return_value = {
            'text': [],
            'conf': []
        }

        text, confidence = service.extract_with_confidence("/fake/image.png")

        assert text == ""
        assert confidence == 0.0

    @patch('src.services.ocr_service.pytesseract.image_to_data')
    @patch('src.services.ocr_service.Image.open')
    def test_extract_with_confidence_ignores_invalid_conf(
        self,
        mock_image_open,
        mock_image_to_data,
        mock_ocr_available,
        service
    ):
        """Test that -1 confidence values are ignored"""
        mock_image = Mock()
        mock_image_open.return_value = mock_image

        # -1 means no text detected in that region
        mock_image_to_data.return_value = {
            'text': ['Word1', '', 'Word2'],
            'conf': [85, -1, 90]
        }

        text, confidence = service.extract_with_confidence(
            "/fake/image.png",
            min_confidence=0.6
        )

        # Should only include valid detections
        assert "Word1" in text
        assert "Word2" in text


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestOCRServiceIntegration:
    """Integration tests for OCR workflow"""

    def test_service_gracefully_handles_missing_deps(self):
        """Test that service works even when OCR deps missing"""
        with patch('src.services.ocr_service.OCR_AVAILABLE', False):
            from src.services.ocr_service import OCRService
            service = OCRService()

            # Should not crash
            assert service.is_available() is False

            # Methods should raise clear errors
            with pytest.raises(Exception) as exc:
                service.extract_text_from_image("/fake.png")

            assert "dependencies" in str(exc.value).lower()

    @patch('src.services.ocr_service.OCR_AVAILABLE', True)
    @patch('src.services.ocr_service.convert_from_path')
    def test_pdf_extraction_with_dpi_setting(self, mock_convert):
        """Test that DPI setting is passed to PDF conversion"""
        from src.services.ocr_service import OCRService
        service = OCRService()

        mock_convert.return_value = []

        try:
            service.extract_text_from_pdf_images("/fake.pdf", dpi=600)
        except:
            pass  # We're just testing the DPI parameter

        # Check DPI was passed
        call_args = mock_convert.call_args
        assert call_args[1]['dpi'] == 600
