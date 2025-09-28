#!/usr/bin/env python3
"""
Simple test for Unstructured.io basic functionality

This script tests basic Unstructured functionality without heavy dependencies
to validate the core document processing capabilities.
"""

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import Dict, Any
import sys
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_basic_unstructured():
    """Test basic Unstructured functionality"""
    logger.info("Testing basic Unstructured.io functionality...")

    try:
        # Import Unstructured
        from unstructured.partition.auto import partition
        from unstructured.partition.text import partition_text
        logger.info("✅ Unstructured.io imported successfully")

        # Create test content
        test_text = """
# Test Document

This is a test document for validating Unstructured.io functionality.

## Section 1
This section contains important information about the project.

## Section 2
- Item 1: First important point
- Item 2: Second important point
- Item 3: Third important point

### Subsection
Here's a detailed paragraph with multiple sentences. This demonstrates how Unstructured handles text processing. The library should be able to extract meaningful elements from this content.
"""

        # Test text partitioning
        logger.info("Testing text partitioning...")
        elements = partition_text(text=test_text)
        logger.info(f"✅ Text partitioning successful: {len(elements)} elements extracted")

        # Display elements
        for i, element in enumerate(elements):
            element_type = type(element).__name__
            text_preview = element.text[:50] + "..." if len(element.text) > 50 else element.text
            logger.info(f"  Element {i+1}: {element_type} - '{text_preview}'")

        # Test file partitioning with a temporary file
        logger.info("Testing file partitioning...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_text)
            temp_file = f.name

        try:
            file_elements = partition(filename=temp_file)
            logger.info(f"✅ File partitioning successful: {len(file_elements)} elements extracted")
        finally:
            os.unlink(temp_file)

        # Test metadata extraction
        logger.info("Testing metadata extraction...")
        if elements:
            sample_element = elements[0]
            if hasattr(sample_element, 'metadata'):
                logger.info(f"✅ Metadata available: {sample_element.metadata}")
            else:
                logger.info("ℹ️ No metadata found (this is normal for basic text)")

        logger.info("🎉 All basic Unstructured.io tests passed!")
        return True

    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

async def test_enhanced_processor_basic():
    """Test basic functionality of our enhanced processor without heavy dependencies"""
    logger.info("Testing EnhancedDocumentProcessor basic functionality...")

    try:
        # Create a minimal test version without heavy imports
        class MinimalEnhancedProcessor:
            def __init__(self):
                self.chunk_size = 1000
                self.chunk_overlap = 200

            async def extract_text_basic(self, content: str):
                """Basic text extraction for testing"""
                # Import only what we need
                from unstructured.partition.text import partition_text

                elements = partition_text(text=content)
                text_content = "\n\n".join([element.text for element in elements if element.text.strip()])

                metadata = {
                    "element_count": len(elements),
                    "element_types": [type(element).__name__ for element in elements],
                    "text_length": len(text_content)
                }

                return text_content, metadata

        # Test the processor
        processor = MinimalEnhancedProcessor()

        test_content = """
# Enhanced RAG System

This document describes the enhanced RAG system implementation.

## Key Features
- Multi-LLM support with fallback chains
- Advanced document processing
- Cost tracking and budget management
- Obsidian integration

## Architecture
The system uses FastAPI for the REST API and ChromaDB for vector storage.
        """

        text, metadata = await processor.extract_text_basic(test_content)

        logger.info(f"✅ Enhanced processor test successful")
        logger.info(f"   Text length: {len(text)}")
        logger.info(f"   Elements: {metadata['element_count']}")
        logger.info(f"   Types: {set(metadata['element_types'])}")

        # Test chunking simulation
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + processor.chunk_size, len(text))
            chunks.append(text[start:end])
            start = end - processor.chunk_overlap if end < len(text) else end

        logger.info(f"✅ Chunking test successful: {len(chunks)} chunks created")

        return True

    except Exception as e:
        logger.error(f"❌ Enhanced processor test failed: {e}")
        return False

async def main():
    """Main test function"""
    logger.info("Starting Unstructured.io compatibility tests...")

    results = []

    # Test basic Unstructured functionality
    result1 = await test_basic_unstructured()
    results.append(result1)

    # Test enhanced processor basics
    result2 = await test_enhanced_processor_basic()
    results.append(result2)

    # Summary
    passed = sum(results)
    total = len(results)

    logger.info(f"\n{'='*50}")
    logger.info(f"TEST SUMMARY: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 All tests passed! Unstructured.io is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)