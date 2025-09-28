#!/usr/bin/env python3
"""
Simple OCR processor that bypasses complex dependencies
"""

import os
import logging
from typing import Optional
from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)

class SimpleOCRProcessor:
    """Simple OCR processor using only Tesseract and PIL"""

    def __init__(self):
        """Initialize the OCR processor"""
        self.supported_formats = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif'}

    def can_process(self, file_path: str) -> bool:
        """Check if file can be processed"""
        return any(file_path.lower().endswith(ext) for ext in self.supported_formats)

    def extract_text_from_image(self, file_path: str) -> str:
        """Extract text from image using Tesseract OCR"""
        try:
            logger.info(f"Processing image with OCR: {file_path}")

            # Open image with PIL
            with Image.open(file_path) as image:
                # Convert to RGB if necessary
                if image.mode not in ('RGB', 'L'):
                    image = image.convert('RGB')

                # Extract text using Tesseract
                text = pytesseract.image_to_string(image, lang='eng')

                # Clean up the text
                text = text.strip()

                if not text:
                    logger.warning(f"No text extracted from {file_path}")
                    return ""

                logger.info(f"Successfully extracted {len(text)} characters from {file_path}")
                return text

        except Exception as e:
            logger.error(f"OCR failed for {file_path}: {str(e)}")
            return ""

    def process_file(self, file_path: str) -> str:
        """Process a file and extract text"""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return ""

        if not self.can_process(file_path):
            logger.error(f"Unsupported file format: {file_path}")
            return ""

        return self.extract_text_from_image(file_path)

def test_ocr():
    """Test OCR functionality"""
    processor = SimpleOCRProcessor()

    # Test with existing test image
    test_file = "/app/test_ocr_image.png"
    if os.path.exists(test_file):
        result = processor.process_file(test_file)
        print(f"OCR Test Result: {len(result)} characters extracted")
        if result:
            print(f"Sample text: {result[:200]}")
        else:
            print("No text extracted")
    else:
        print(f"Test file not found: {test_file}")

if __name__ == "__main__":
    test_ocr()