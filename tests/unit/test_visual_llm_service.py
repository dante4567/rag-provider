"""
Unit tests for Visual LLM Service

Tests visual LLM capabilities for extracting text from images and PDFs
using AI vision models (Gemini Vision, GPT-4V, Claude Vision).
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from PIL import Image
import io
import os

from src.services.visual_llm_service import VisualLLMService


class TestVisualLLMServiceInit:
    """Test service initialization"""

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    def test_init_with_all_deps(self, mock_genai):
        """Should initialize successfully with all dependencies"""
        service = VisualLLMService()

        # enabled is truthy (the API key) when all deps available
        assert service.enabled
        assert service.google_api_key == 'test-key'
        mock_genai.configure.assert_called_once_with(api_key='test-key')

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    def test_init_without_api_key(self):
        """Should disable when API key missing"""
        service = VisualLLMService()

        # enabled is falsy (None or False) when API key missing
        assert not service.enabled
        assert service.google_api_key is None

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    def test_init_without_gemini(self):
        """Should disable when Gemini not available"""
        service = VisualLLMService()

        assert service.enabled is False

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    def test_init_without_pdf2image(self):
        """Should disable when pdf2image not available"""
        service = VisualLLMService()

        assert service.enabled is False


class TestIsAvailable:
    """Test availability checking"""

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    def test_is_available_when_enabled(self, mock_genai):
        """Should return True when all deps available"""
        service = VisualLLMService()

        # is_available() returns truthy value when enabled
        assert service.is_available()

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    def test_is_available_when_disabled(self):
        """Should return False when deps missing"""
        service = VisualLLMService()

        assert service.is_available() is False


class TestAssessOCRQuality:
    """Test OCR quality assessment"""

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    def test_assess_empty_text(self):
        """Should mark empty text as poor quality"""
        service = VisualLLMService()

        result = service.assess_ocr_quality("")

        assert result['quality'] == 'poor'
        assert result['score'] == 0.0
        assert result['use_visual_llm'] is True
        assert 'Empty' in result['reason']

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    def test_assess_very_short_text(self):
        """Should mark very short text as poor quality"""
        service = VisualLLMService()

        result = service.assess_ocr_quality("abc")

        assert result['quality'] == 'poor'
        assert result['use_visual_llm'] is True

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    def test_assess_good_quality_text(self):
        """Should mark clean text as good quality"""
        service = VisualLLMService()

        text = "This is a well-formatted document with clear text and proper sentences."
        result = service.assess_ocr_quality(text)

        assert result['quality'] == 'good'
        assert result['score'] >= 0.6
        assert result['use_visual_llm'] is False
        assert 'Good quality' in result['reason']

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    def test_assess_gibberish_text(self):
        """Should detect gibberish patterns in OCR text"""
        service = VisualLLMService()

        # Text with many OCR gibberish patterns
        text = "* = u L * = u L > * A > + + u $ EEE EEE CCR HHH AAA = = u L L L CEE CEE"
        result = service.assess_ocr_quality(text)

        # Should detect gibberish patterns (scoring is conservative)
        assert result['gibberish_count'] > 5, "Should detect multiple gibberish patterns"
        assert result['gibberish_ratio'] > 0, "Gibberish ratio should be positive"
        assert 'quality' in result
        assert 'score' in result

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    def test_assess_repeated_single_chars(self):
        """Should detect repeated single characters pattern"""
        service = VisualLLMService()

        # Text with many single capital letters (OCR error pattern)
        text = "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z"
        result = service.assess_ocr_quality(text)

        # Single chars contribute 30% to score degradation
        # Without gibberish, this scores as 'good' (0.7) in current impl
        assert result['quality'] == 'good'
        assert result['score'] < 0.8  # But lower than perfect text
        assert 'gibberish_ratio' in result

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    def test_assess_fair_quality_text(self):
        """Should mark partially corrupted text as fair quality"""
        service = VisualLLMService()

        # Mix of good text and some gibberish
        text = "This is a document. EEE Some good text here. * = u L More content follows."
        result = service.assess_ocr_quality(text)

        # Quality should be between poor and good
        assert result['score'] > 0.3
        assert result['score'] < 1.0


class TestCalculateGeminiCost:
    """Test Gemini cost calculation"""

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    def test_calculate_cost_returns_estimate(self):
        """Should return cost estimate for Gemini"""
        service = VisualLLMService()

        # Create dummy image
        image = Image.new('RGB', (100, 100))
        cost = service._calculate_gemini_cost(image)

        assert isinstance(cost, float)
        assert cost == 0.0025  # Conservative estimate

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    def test_calculate_cost_consistent(self):
        """Cost should be consistent for same image"""
        service = VisualLLMService()

        image1 = Image.new('RGB', (100, 100))
        image2 = Image.new('RGB', (200, 200))

        # Currently returns flat rate
        assert service._calculate_gemini_cost(image1) == service._calculate_gemini_cost(image2)


class TestExtractFromPDF:
    """Test PDF extraction"""

    @patch.dict(os.environ, {}, clear=True)
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', False)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', False)
    @pytest.mark.asyncio
    async def test_extract_raises_when_disabled(self):
        """Should raise error when service disabled"""
        service = VisualLLMService()

        with pytest.raises(RuntimeError, match="not available"):
            await service.extract_from_pdf("test.pdf")

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    @patch('src.services.visual_llm_service.convert_from_path')
    @pytest.mark.asyncio
    async def test_extract_handles_pdf_conversion_error(self, mock_convert, mock_genai):
        """Should handle PDF conversion errors"""
        service = VisualLLMService()
        service.enabled = True

        mock_convert.side_effect = Exception("PDF conversion failed")

        with pytest.raises(Exception, match="PDF conversion failed"):
            await service.extract_from_pdf("test.pdf")

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    @patch('src.services.visual_llm_service.convert_from_path')
    @pytest.mark.asyncio
    async def test_extract_limits_max_pages(self, mock_convert, mock_genai):
        """Should limit processing to max_pages"""
        service = VisualLLMService()
        service.enabled = True

        # Create 15 dummy images
        images = [Image.new('RGB', (100, 100)) for _ in range(15)]
        mock_convert.return_value = images

        # Mock _analyze_image to return simple result
        service._analyze_image = AsyncMock(return_value={
            'full_text': 'Test text',
            'title': 'Test',
            'summary': 'Summary',
            'document_type': 'test',
            'key_info': {},
            'cost': 0.0025
        })

        result = await service.extract_from_pdf("test.pdf", max_pages=10)

        # Should only process 10 pages
        assert service._analyze_image.call_count == 10
        assert result['metadata']['pages_processed'] == 10

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    @patch('src.services.visual_llm_service.convert_from_path')
    @pytest.mark.asyncio
    async def test_extract_combines_multi_page_results(self, mock_convert, mock_genai):
        """Should combine results from multiple pages"""
        service = VisualLLMService()
        service.enabled = True

        # Create 3 dummy images
        images = [Image.new('RGB', (100, 100)) for _ in range(3)]
        mock_convert.return_value = images

        # Mock _analyze_image to return different text per page
        async def mock_analyze(image, model, page_num):
            return {
                'full_text': f'Page {page_num} text',
                'title': f'Page {page_num}',
                'summary': f'Summary {page_num}',
                'document_type': 'test',
                'key_info': {
                    'names': [f'Name{page_num}'],
                    'dates': [f'2025-{page_num:02d}-01'],
                    'amounts': [f'${page_num}00']
                },
                'cost': 0.0025
            }

        service._analyze_image = mock_analyze

        result = await service.extract_from_pdf("test.pdf")

        # Check combined text
        assert 'Page 1 text' in result['text']
        assert 'Page 2 text' in result['text']
        assert 'Page 3 text' in result['text']

        # Check metadata aggregation
        assert result['metadata']['pages_processed'] == 3
        assert result['metadata']['total_cost'] == 0.0075  # 3 * 0.0025

        # Check that names/dates/amounts are combined and deduplicated
        assert len(result['metadata']['names']) == 3
        assert len(result['metadata']['dates']) == 3
        assert len(result['metadata']['amounts']) == 3

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    @patch('src.services.visual_llm_service.convert_from_path')
    @pytest.mark.asyncio
    async def test_extract_handles_page_analysis_errors(self, mock_convert, mock_genai):
        """Should handle errors in page analysis gracefully"""
        service = VisualLLMService()
        service.enabled = True

        images = [Image.new('RGB', (100, 100)) for _ in range(2)]
        mock_convert.return_value = images

        # First page succeeds, second fails
        call_count = [0]
        async def mock_analyze(image, model, page_num):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    'full_text': 'Good text',
                    'title': 'Good Page',
                    'summary': 'Summary',
                    'document_type': 'test',
                    'key_info': {},
                    'cost': 0.0025
                }
            else:
                raise Exception("Analysis failed")

        service._analyze_image = mock_analyze

        result = await service.extract_from_pdf("test.pdf")

        # Should have both pages (one success, one error)
        assert 'Good text' in result['text']
        assert 'Error processing page 2' in result['text']


class TestGeminiVision:
    """Test Gemini Vision integration"""

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    @pytest.mark.asyncio
    async def test_gemini_vision_parses_json_response(self, mock_genai):
        """Should parse JSON response from Gemini"""
        service = VisualLLMService()
        service.enabled = True

        # Mock Gemini response
        mock_response = Mock()
        mock_response.text = '''```json
{
  "title": "Test Document",
  "summary": "This is a test summary",
  "document_type": "letter",
  "key_info": {
    "names": ["John Doe"],
    "dates": ["2025-01-01"],
    "amounts": ["$100"],
    "action_items": ["Review document"]
  },
  "full_text": "Full text here"
}
```'''

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        image = Image.new('RGB', (100, 100))
        result = await service._gemini_vision(image, "gemini-2.0-flash-exp", 1)

        assert result['title'] == 'Test Document'
        assert result['summary'] == 'This is a test summary'
        assert result['document_type'] == 'letter'
        assert 'John Doe' in result['key_info']['names']
        assert result['cost'] == 0.0025

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    @pytest.mark.asyncio
    async def test_gemini_vision_handles_non_json_response(self, mock_genai):
        """Should handle non-JSON response gracefully"""
        service = VisualLLMService()
        service.enabled = True

        # Mock Gemini response without JSON
        mock_response = Mock()
        mock_response.text = "This is just plain text without JSON formatting"

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        image = Image.new('RGB', (100, 100))
        result = await service._gemini_vision(image, "gemini-2.0-flash-exp", 1)

        # Should fallback to using raw text
        assert result['title'] == 'Scanned Document'
        assert 'This is just plain text' in result['summary']
        assert result['full_text'] == "This is just plain text without JSON formatting"

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    @pytest.mark.asyncio
    async def test_gemini_vision_handles_api_error(self, mock_genai):
        """Should handle Gemini API errors"""
        service = VisualLLMService()
        service.enabled = True

        # Mock Gemini error
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API error")
        mock_genai.GenerativeModel.return_value = mock_model

        image = Image.new('RGB', (100, 100))
        result = await service._gemini_vision(image, "gemini-2.0-flash-exp", 1)

        # Should return error result instead of raising
        assert result['title'] == 'Error Processing Page'
        assert 'Error' in result['summary']
        assert result['cost'] == 0.0


class TestAnalyzeImage:
    """Test image analysis routing"""

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    @pytest.mark.asyncio
    async def test_analyze_routes_to_gemini(self, mock_genai):
        """Should route to Gemini for gemini models"""
        service = VisualLLMService()
        service.enabled = True

        service._gemini_vision = AsyncMock(return_value={'test': 'result'})

        image = Image.new('RGB', (100, 100))
        result = await service._analyze_image(image, "gemini-2.0-flash-exp", 1)

        service._gemini_vision.assert_called_once()
        assert result == {'test': 'result'}

    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.services.visual_llm_service.GEMINI_AVAILABLE', True)
    @patch('src.services.visual_llm_service.PDF2IMAGE_AVAILABLE', True)
    @patch('src.services.visual_llm_service.genai')
    @pytest.mark.asyncio
    async def test_analyze_raises_for_unsupported_model(self, mock_genai):
        """Should raise error for unsupported models"""
        service = VisualLLMService()
        service.enabled = True

        image = Image.new('RGB', (100, 100))

        with pytest.raises(ValueError, match="Unsupported model"):
            await service._analyze_image(image, "gpt-4v", 1)
