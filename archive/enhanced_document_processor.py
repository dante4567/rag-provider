"""
Enhanced Document Processor using Unstructured.io

This module provides a modern document processing implementation using Unstructured.io
to replace the custom document parsing logic. It maintains compatibility with the
existing FastAPI interface while providing better document processing capabilities.

Benefits over the original implementation:
- Handles 20+ document formats out of the box
- Better OCR and image processing
- Superior table extraction and structure preservation
- Automatic metadata extraction
- More robust error handling
- Significantly less code to maintain
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from enum import Enum
import asyncio
import tempfile
import shutil

# Unstructured imports
from unstructured.partition.auto import partition
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.image import partition_image
from unstructured.partition.email import partition_email
from unstructured.partition.html import partition_html
from unstructured.chunking.title import chunk_by_title

# Keep the existing enums for compatibility
class DocumentType(str, Enum):
    text = "text"
    pdf = "pdf"
    image = "image"
    whatsapp = "whatsapp"
    email = "email"
    webpage = "webpage"
    scanned = "scanned"
    office = "office"
    code = "code"

logger = logging.getLogger(__name__)

class EnhancedDocumentProcessor:
    """
    Enhanced document processor using Unstructured.io

    This replaces the custom DocumentProcessor with a modern implementation
    that leverages mature libraries for better document processing.
    """

    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        # Configuration for Unstructured
        self.chunk_size = 1000
        self.chunk_overlap = 200

    async def extract_text_from_file(self, file_path: str, process_ocr: bool = False) -> Tuple[str, DocumentType, Dict[str, Any]]:
        """
        Extract text from various file formats using Unstructured.io

        This method replaces hundreds of lines of custom parsing code with
        a simple, robust implementation using mature libraries.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Processing file with Unstructured: {file_path}")

        try:
            # Check if it's a WhatsApp export first (simple text check)
            if file_path.suffix.lower() in ['.txt', '.md'] and await self._is_whatsapp_export(file_path):
                return await self._process_whatsapp_export(file_path)

            # Use Unstructured for all other document types
            elements = await self._partition_document(file_path, process_ocr)

            # Extract text and metadata
            text_content = self._extract_text_from_elements(elements)
            metadata = self._extract_metadata_from_elements(elements)
            doc_type = self._determine_document_type(file_path, elements)

            logger.info(f"Successfully processed {file_path} with Unstructured")
            return text_content, doc_type, metadata

        except Exception as e:
            logger.error(f"Enhanced document processing failed for {file_path}: {e}")
            # Fallback to basic text reading for text files
            if file_path.suffix.lower() in ['.txt', '.md']:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    return content, DocumentType.text, {}
                except:
                    pass
            raise ValueError(f"Failed to process document: {file_path.name} - {str(e)}")

    async def _partition_document(self, file_path: Path, process_ocr: bool) -> List:
        """
        Partition document using Unstructured.io based on file type
        """
        file_extension = file_path.suffix.lower()

        # Run in thread pool since Unstructured is not async
        loop = asyncio.get_event_loop()

        try:
            if file_extension == '.pdf':
                # Use specialized PDF partitioner for better results
                elements = await loop.run_in_executor(
                    None,
                    lambda: partition_pdf(
                        filename=str(file_path),
                        strategy="hi_res" if process_ocr else "fast",
                        infer_table_structure=True,
                        extract_images_in_pdf=process_ocr,
                        extract_image_block_types=["Image", "Table"] if process_ocr else []
                    )
                )
            elif file_extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
                # Use specialized image partitioner
                elements = await loop.run_in_executor(
                    None,
                    lambda: partition_image(
                        filename=str(file_path),
                        strategy="hi_res" if process_ocr else "fast",
                        infer_table_structure=True
                    )
                )
            elif file_extension in ['.eml', '.msg']:
                # Use specialized email partitioner
                elements = await loop.run_in_executor(
                    None,
                    lambda: partition_email(filename=str(file_path))
                )
            elif file_extension in ['.html', '.htm']:
                # Use specialized HTML partitioner
                elements = await loop.run_in_executor(
                    None,
                    lambda: partition_html(filename=str(file_path))
                )
            else:
                # Use auto partitioner for all other formats
                elements = await loop.run_in_executor(
                    None,
                    lambda: partition(
                        filename=str(file_path),
                        strategy="hi_res" if process_ocr else "fast",
                        infer_table_structure=True
                    )
                )

            return elements

        except Exception as e:
            logger.error(f"Unstructured partitioning failed for {file_path}: {e}")
            raise

    def _extract_text_from_elements(self, elements: List) -> str:
        """
        Extract clean text from Unstructured elements

        This replaces hundreds of lines of custom text extraction logic
        """
        text_parts = []

        for element in elements:
            # Unstructured elements have a text attribute
            if hasattr(element, 'text') and element.text:
                text_parts.append(element.text.strip())

        return "\n\n".join(text_parts)

    def _extract_metadata_from_elements(self, elements: List) -> Dict[str, Any]:
        """
        Extract metadata from Unstructured elements

        Unstructured provides rich metadata automatically
        """
        metadata = {
            "element_count": len(elements),
            "element_types": [],
            "tables_detected": 0,
            "images_detected": 0,
            "languages": set()
        }

        for element in elements:
            # Track element types
            element_type = type(element).__name__
            metadata["element_types"].append(element_type)

            # Count specific element types
            if "Table" in element_type:
                metadata["tables_detected"] += 1
            elif "Image" in element_type:
                metadata["images_detected"] += 1

            # Extract language information if available
            if hasattr(element, 'metadata') and element.metadata:
                if 'languages' in element.metadata:
                    metadata["languages"].update(element.metadata['languages'])

        # Convert set to list for JSON serialization
        metadata["languages"] = list(metadata["languages"])
        metadata["element_types"] = list(set(metadata["element_types"]))

        return metadata

    def _determine_document_type(self, file_path: Path, elements: List) -> DocumentType:
        """
        Determine document type based on file extension and content
        """
        file_extension = file_path.suffix.lower()

        # Map file extensions to document types
        type_mapping = {
            '.pdf': DocumentType.pdf,
            '.docx': DocumentType.office,
            '.doc': DocumentType.office,
            '.pptx': DocumentType.office,
            '.ppt': DocumentType.office,
            '.xlsx': DocumentType.office,
            '.xls': DocumentType.office,
            '.png': DocumentType.image,
            '.jpg': DocumentType.image,
            '.jpeg': DocumentType.image,
            '.tiff': DocumentType.image,
            '.bmp': DocumentType.image,
            '.eml': DocumentType.email,
            '.msg': DocumentType.email,
            '.html': DocumentType.webpage,
            '.htm': DocumentType.webpage,
            '.py': DocumentType.code,
            '.js': DocumentType.code,
            '.java': DocumentType.code,
            '.cpp': DocumentType.code,
            '.c': DocumentType.code,
            '.cs': DocumentType.code,
            '.php': DocumentType.code,
        }

        # Check if it contains scanned content (images with text)
        has_images = any("Image" in type(element).__name__ for element in elements)
        if has_images and file_extension == '.pdf':
            return DocumentType.scanned
        elif has_images and file_extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            return DocumentType.scanned

        return type_mapping.get(file_extension, DocumentType.text)

    async def _is_whatsapp_export(self, file_path: Path) -> bool:
        """
        Check if the file is a WhatsApp chat export
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)  # Read first 1000 chars

            # Simple heuristic for WhatsApp exports
            whatsapp_indicators = [
                r'\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}',  # Date pattern
                'Messages and calls are end-to-end encrypted',
                'This message was deleted',
                '<Media omitted>'
            ]

            import re
            for pattern in whatsapp_indicators:
                if re.search(pattern, content):
                    return True

            return False
        except:
            return False

    async def _process_whatsapp_export(self, file_path: Path) -> Tuple[str, DocumentType, Dict[str, Any]]:
        """
        Process WhatsApp export files (keeping original logic for now)
        """
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        return content, DocumentType.whatsapp, {"format": "whatsapp_export"}

    def chunk_text(self, text: str) -> List[str]:
        """
        Chunk text using Unstructured's chunking capabilities

        This replaces the custom SimpleTextSplitter
        """
        if not text:
            return []

        try:
            # Create a temporary element for chunking
            from unstructured.documents.elements import Text

            # Create a text element
            element = Text(text=text)

            # Use Unstructured's chunking
            chunks = chunk_by_title(
                elements=[element],
                max_characters=self.chunk_size,
                overlap=self.chunk_overlap
            )

            return [chunk.text for chunk in chunks if chunk.text.strip()]

        except Exception as e:
            logger.warning(f"Unstructured chunking failed, falling back to simple chunking: {e}")
            # Fallback to simple chunking
            return self._simple_chunk_text(text)

    def _simple_chunk_text(self, text: str) -> List[str]:
        """
        Simple fallback chunking method
        """
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + self.chunk_size

            # Try to break at sentence boundary
            if end < text_len:
                for i in range(min(100, self.chunk_size // 4)):
                    if end - i >= 0 and text[end - i] in '.!?':
                        end = end - i + 1
                        break
                else:
                    # Try word boundary
                    for i in range(min(50, self.chunk_size // 8)):
                        if end - i >= 0 and text[end - i] == ' ':
                            end = end - i
                            break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - self.chunk_overlap if end < text_len else end

        return chunks


# Factory function to create the enhanced processor
def create_enhanced_document_processor(llm_service=None):
    """
    Factory function to create an enhanced document processor
    """
    return EnhancedDocumentProcessor(llm_service)


# Compatibility wrapper for easy migration
class UnstructuredDocumentProcessor(EnhancedDocumentProcessor):
    """
    Alias for enhanced document processor to maintain naming consistency
    """
    pass