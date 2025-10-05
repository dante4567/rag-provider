"""
OCR (Optical Character Recognition) service for extracting text from images and scanned PDFs
"""
import os
import logging
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Check OCR dependencies
try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR dependencies (pytesseract, PIL, pdf2image) not available")


class OCRService:
    """
    Handles OCR processing for scanned documents and images

    Uses Tesseract OCR for text extraction from images and PDF pages
    """

    def __init__(self, languages: Optional[List[str]] = None):
        """
        Initialize OCR service

        Args:
            languages: List of language codes for OCR (e.g., ['eng', 'deu', 'fra'])
        """
        self.languages = languages or ['eng']

        if not OCR_AVAILABLE:
            logger.warning("OCR dependencies not available. OCR functionality disabled.")

    def is_available(self) -> bool:
        """Check if OCR is available"""
        return OCR_AVAILABLE

    def extract_text_from_image(
        self,
        image_path: str | Path,
        languages: Optional[List[str]] = None
    ) -> str:
        """
        Extract text from an image file using Tesseract OCR

        Args:
            image_path: Path to image file
            languages: Language codes for OCR (overrides default)

        Returns:
            Extracted text

        Raises:
            Exception: If OCR dependencies not available or extraction fails
        """
        if not OCR_AVAILABLE:
            raise Exception("OCR dependencies not available. Install: pip install pytesseract pillow pdf2image")

        try:
            lang_codes = "+".join(languages or self.languages)

            # Open image and extract text
            text = pytesseract.image_to_string(
                Image.open(str(image_path)),
                lang=lang_codes,
                config='--psm 6'  # Assume uniform block of text
            )

            return text.strip()

        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
            raise

    def extract_text_from_pdf_images(
        self,
        pdf_path: str | Path,
        languages: Optional[List[str]] = None,
        dpi: int = 300
    ) -> str:
        """
        Convert PDF pages to images and extract text using OCR

        Args:
            pdf_path: Path to PDF file
            languages: Language codes for OCR
            dpi: Resolution for PDF to image conversion (higher = better quality, slower)

        Returns:
            Extracted text from all pages

        Raises:
            Exception: If OCR dependencies not available or conversion fails
        """
        if not OCR_AVAILABLE:
            raise Exception("OCR dependencies not available")

        try:
            # Convert PDF pages to images
            pages = convert_from_path(str(pdf_path), dpi=dpi)
            extracted_text = ""

            logger.info(f"Processing {len(pages)} pages from {pdf_path}")

            for i, page in enumerate(pages):
                # Save page as temporary image
                temp_image_path = f"/tmp/page_{os.getpid()}_{i}.png"

                try:
                    page.save(temp_image_path, 'PNG')

                    # Extract text from page image
                    page_text = self.extract_text_from_image(temp_image_path, languages)
                    extracted_text += f"\n\n--- Page {i+1} ---\n{page_text}"

                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_image_path):
                        os.unlink(temp_image_path)

            return extracted_text.strip()

        except Exception as e:
            logger.error(f"PDF OCR failed for {pdf_path}: {e}")
            raise

    def extract_with_confidence(
        self,
        image_path: str | Path,
        min_confidence: float = 0.6
    ) -> tuple[str, float]:
        """
        Extract text with confidence scoring

        Args:
            image_path: Path to image file
            min_confidence: Minimum confidence threshold (0.0-1.0)

        Returns:
            Tuple of (extracted_text, average_confidence)
        """
        if not OCR_AVAILABLE:
            raise Exception("OCR dependencies not available")

        try:
            # Get detailed OCR data with confidence
            data = pytesseract.image_to_data(
                Image.open(str(image_path)),
                lang="+".join(self.languages),
                output_type=pytesseract.Output.DICT
            )

            # Filter by confidence and reconstruct text
            filtered_text = []
            confidences = []

            for i, conf in enumerate(data['conf']):
                if conf != -1:  # -1 means no text detected
                    conf_score = int(conf) / 100.0
                    if conf_score >= min_confidence:
                        text = data['text'][i]
                        if text.strip():
                            filtered_text.append(text)
                            confidences.append(conf_score)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            result_text = ' '.join(filtered_text)

            return result_text.strip(), avg_confidence

        except Exception as e:
            logger.error(f"Confidence OCR failed for {image_path}: {e}")
            raise
