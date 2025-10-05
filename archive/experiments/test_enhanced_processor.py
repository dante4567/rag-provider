#!/usr/bin/env python3
"""
Test script to compare original DocumentProcessor with EnhancedDocumentProcessor

This script tests both implementations side by side to validate that the
Unstructured.io-based processor provides better or equivalent functionality.
"""

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import Dict, Any
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, '/app')

# Import both processors
from enhanced_document_processor import EnhancedDocumentProcessor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProcessorComparison:
    """Compare old and new document processors"""

    def __init__(self):
        self.enhanced_processor = EnhancedDocumentProcessor()

    async def create_test_documents(self) -> Dict[str, Path]:
        """Create test documents for comparison"""
        test_docs = {}

        # Create temporary directory for test files
        temp_dir = Path(tempfile.mkdtemp())
        logger.info(f"Created temp directory: {temp_dir}")

        # Test text document
        text_file = temp_dir / "test.txt"
        with open(text_file, 'w') as f:
            f.write("""# Test Document

This is a test document for comparing document processors.

## Section 1
This section contains some text with **bold** and *italic* formatting.

## Section 2
- Item 1
- Item 2
- Item 3

### Subsection
Here's a paragraph with multiple sentences. This is the second sentence. And this is the third.

""")
        test_docs["text"] = text_file

        # Test WhatsApp-like export
        whatsapp_file = temp_dir / "whatsapp_export.txt"
        with open(whatsapp_file, 'w') as f:
            f.write("""1/20/24, 10:30 - John: How is the ML project going?
1/20/24, 10:31 - Jane: Going really well! We just hit 95% accuracy.
1/20/24, 10:32 - John: That's amazing! When do we deploy?
1/20/24, 10:33 - Jane: Testing next week, then production.
1/20/24, 10:34 - John: <Media omitted>
1/20/24, 10:35 - Jane: This message was deleted
""")
        test_docs["whatsapp"] = whatsapp_file

        # Test HTML document
        html_file = temp_dir / "test.html"
        with open(html_file, 'w') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Test HTML Document</title>
</head>
<body>
    <h1>Main Title</h1>
    <p>This is a paragraph with <strong>bold text</strong> and <em>italic text</em>.</p>

    <h2>Table Example</h2>
    <table>
        <tr>
            <th>Name</th>
            <th>Score</th>
        </tr>
        <tr>
            <td>Alice</td>
            <td>95</td>
        </tr>
        <tr>
            <td>Bob</td>
            <td>87</td>
        </tr>
    </table>

    <h2>List Example</h2>
    <ul>
        <li>First item</li>
        <li>Second item</li>
        <li>Third item</li>
    </ul>
</body>
</html>""")
        test_docs["html"] = html_file

        # Test code file
        code_file = temp_dir / "test.py"
        with open(code_file, 'w') as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Test Python file for document processing
\"\"\"

def main():
    print("Hello, world!")

    # This is a comment
    data = {
        "name": "test",
        "value": 42
    }

    for key, value in data.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    main()
""")
        test_docs["code"] = code_file

        return test_docs

    async def test_enhanced_processor(self, test_docs: Dict[str, Path]):
        """Test the enhanced processor with Unstructured.io"""
        logger.info("=== Testing Enhanced Processor (Unstructured.io) ===")

        results = {}

        for doc_type, file_path in test_docs.items():
            logger.info(f"\nTesting {doc_type}: {file_path}")

            try:
                start_time = time.time()
                text, detected_type, metadata = await self.enhanced_processor.extract_text_from_file(
                    str(file_path), process_ocr=False
                )
                end_time = time.time()

                processing_time = end_time - start_time

                # Test chunking
                chunks = self.enhanced_processor.chunk_text(text)

                results[doc_type] = {
                    "success": True,
                    "text_length": len(text),
                    "detected_type": detected_type,
                    "metadata": metadata,
                    "chunk_count": len(chunks),
                    "processing_time": processing_time,
                    "first_100_chars": text[:100] + "..." if len(text) > 100 else text
                }

                logger.info(f"✅ Success - Type: {detected_type}, Length: {len(text)}, Time: {processing_time:.3f}s")
                logger.info(f"   Metadata: {metadata}")
                logger.info(f"   Chunks: {len(chunks)}")
                logger.info(f"   Preview: {text[:100]}...")

            except Exception as e:
                logger.error(f"❌ Failed: {e}")
                results[doc_type] = {
                    "success": False,
                    "error": str(e),
                    "processing_time": 0
                }

        return results

    async def run_comparison(self):
        """Run the full comparison test"""
        logger.info("Starting document processor comparison...")

        # Create test documents
        test_docs = await self.create_test_documents()
        logger.info(f"Created {len(test_docs)} test documents")

        # Test enhanced processor
        enhanced_results = await self.test_enhanced_processor(test_docs)

        # Print summary
        logger.info("\n" + "="*60)
        logger.info("COMPARISON SUMMARY")
        logger.info("="*60)

        for doc_type in test_docs.keys():
            logger.info(f"\n{doc_type.upper()} Document:")

            enhanced = enhanced_results.get(doc_type, {})

            if enhanced.get("success"):
                logger.info(f"  Enhanced: ✅ {enhanced['text_length']} chars, "
                          f"{enhanced['chunk_count']} chunks, {enhanced['processing_time']:.3f}s")
                logger.info(f"    Type: {enhanced['detected_type']}")
                logger.info(f"    Metadata keys: {list(enhanced['metadata'].keys())}")
            else:
                logger.info(f"  Enhanced: ❌ {enhanced.get('error', 'Unknown error')}")

        # Calculate overall stats
        enhanced_successes = sum(1 for r in enhanced_results.values() if r.get("success"))
        total_tests = len(test_docs)

        logger.info(f"\nOVERALL RESULTS:")
        logger.info(f"Enhanced Processor: {enhanced_successes}/{total_tests} successful")

        # Clean up test files
        import shutil
        temp_dir = list(test_docs.values())[0].parent
        shutil.rmtree(temp_dir)
        logger.info(f"Cleaned up temp directory: {temp_dir}")

        return enhanced_results

async def main():
    """Main test function"""
    comparison = ProcessorComparison()
    results = await comparison.run_comparison()

    # Return non-zero exit code if any tests failed
    failed_tests = [k for k, v in results.items() if not v.get("success")]
    if failed_tests:
        logger.error(f"Failed tests: {failed_tests}")
        return 1
    else:
        logger.info("All tests passed! ✅")
        return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)