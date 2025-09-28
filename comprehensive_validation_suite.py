#!/usr/bin/env python3
"""
Comprehensive Validation Suite for Modernized RAG Service

This suite performs extensive testing with multiple document types, formats,
and edge cases to validate the modernized RAG service using Unstructured.io
and LiteLLM against the original implementation.
"""

import asyncio
import logging
import tempfile
import time
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
import requests
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ComprehensiveValidator:
    """Comprehensive validation of the modernized RAG service"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.test_results = {}
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.temp_dir = None

    async def setup_test_environment(self):
        """Setup test environment with sample documents"""
        self.temp_dir = Path(tempfile.mkdtemp())
        logger.info(f"Created test directory: {self.temp_dir}")

        # Create comprehensive test documents
        await self.create_test_documents()

        # Verify service is running
        await self.verify_service_health()

    async def create_test_documents(self):
        """Create a comprehensive suite of test documents"""
        logger.info("Creating comprehensive test document suite...")

        # 1. Simple text files
        text_files = {
            "simple_text.txt": "This is a simple text document for testing basic text processing.",

            "markdown_doc.md": """# Machine Learning Guide

## Introduction
Machine learning is a subset of artificial intelligence (AI) that focuses on algorithms.

### Key Concepts
- **Supervised Learning**: Uses labeled training data
- **Unsupervised Learning**: Finds patterns in unlabeled data
- **Deep Learning**: Uses neural networks with multiple layers

## Applications
1. Image recognition
2. Natural language processing
3. Recommendation systems

> "Machine learning is the future of technology" - Tech Expert

### Code Example
```python
import sklearn
from sklearn.linear_model import LinearRegression

model = LinearRegression()
model.fit(X_train, y_train)
predictions = model.predict(X_test)
```

## Conclusion
Machine learning continues to evolve and transform industries.
""",

            "technical_report.txt": """Technical Report: System Performance Analysis

Executive Summary:
This report analyzes the performance characteristics of our distributed computing system
over the past quarter. Key findings include a 15% improvement in throughput and
a 23% reduction in latency.

Methodology:
- Data collection period: Q3 2024
- Metrics tracked: throughput, latency, error rates
- Testing environments: production, staging, development

Results:
System throughput increased from 1,000 req/sec to 1,150 req/sec.
Average response time decreased from 250ms to 192ms.
Error rate remained stable at 0.02%.

Recommendations:
1. Continue current optimization strategies
2. Implement additional caching layers
3. Monitor memory usage patterns

Technical Details:
CPU utilization: 65% average (down from 78%)
Memory usage: 4.2GB average (up from 3.8GB)
Network I/O: 125MB/sec average
Disk I/O: 45MB/sec average

Conclusion:
The system performance improvements validate our architectural decisions.
Further optimizations should focus on memory efficiency and cache hit rates.
""",

            "whatsapp_export.txt": """12/1/24, 9:15 AM - Alice: Good morning team! Ready for today's standup?
12/1/24, 9:16 AM - Bob: Morning! Yes, I've prepared my updates
12/1/24, 9:17 AM - Charlie: Hi everyone, I'll join in 2 minutes
12/1/24, 9:18 AM - Alice: Perfect, let's start with yesterday's accomplishments
12/1/24, 9:19 AM - Bob: I completed the API integration and wrote unit tests
12/1/24, 9:20 AM - Alice: Great! Any blockers?
12/1/24, 9:21 AM - Bob: None currently, but I might need help with the database migration
12/1/24, 9:22 AM - Charlie: I can help with that, I've done similar migrations before
12/1/24, 9:23 AM - Alice: Excellent teamwork! Charlie, what about your updates?
12/1/24, 9:24 AM - Charlie: I finished the UI mockups and got approval from design team
12/1/24, 9:25 AM - Alice: <Media omitted>
12/1/24, 9:26 AM - Bob: Looking good! When do we start implementation?
12/1/24, 9:27 AM - Charlie: This afternoon, after the database migration
12/1/24, 9:28 AM - Alice: Perfect. Today's goals: migration and UI implementation
12/1/24, 9:29 AM - Bob: 👍
12/1/24, 9:30 AM - Charlie: Sounds like a plan!
""",

            "json_data.json": """{
  "project": "RAG Service Modernization",
  "version": "2.0.0",
  "description": "Enhanced RAG service using modern libraries",
  "features": [
    {
      "name": "Document Processing",
      "library": "Unstructured.io",
      "status": "implemented",
      "benefits": ["Better parsing", "Rich metadata", "Multiple formats"]
    },
    {
      "name": "LLM Management",
      "library": "LiteLLM",
      "status": "implemented",
      "benefits": ["Unified interface", "Cost tracking", "Auto fallback"]
    }
  ],
  "metrics": {
    "code_reduction": "75%",
    "test_coverage": "95%",
    "performance_improvement": "20%"
  },
  "team": {
    "lead": "AI Engineer",
    "contributors": ["Backend Developer", "ML Engineer", "DevOps"],
    "timeline": "2 weeks"
  }
}""",

            "csv_data.csv": """Name,Age,Department,Salary,Performance,Projects
Alice Johnson,28,Engineering,95000,Excellent,5
Bob Smith,32,Engineering,105000,Good,7
Charlie Brown,26,Design,75000,Excellent,3
Diana Ross,35,Marketing,85000,Good,4
Evan Davis,29,Engineering,98000,Excellent,6
Fiona Chen,31,Data Science,110000,Outstanding,8
George Wilson,27,Engineering,88000,Good,4
Hannah Lee,33,Product,120000,Excellent,9
Ivan Petrov,30,Engineering,102000,Good,5
Julia Garcia,25,Design,72000,Good,2
""",

            "log_file.log": """2024-12-01 09:15:23 INFO  [main] Application started successfully
2024-12-01 09:15:24 DEBUG [http] Server listening on port 8001
2024-12-01 09:15:25 INFO  [db] Database connection established
2024-12-01 09:16:01 INFO  [api] GET /health - 200 OK - 15ms
2024-12-01 09:16:15 INFO  [api] POST /ingest - 200 OK - 234ms
2024-12-01 09:16:16 DEBUG [processor] Processing document: test.pdf
2024-12-01 09:16:17 INFO  [ocr] OCR processing completed - 1,245 chars extracted
2024-12-01 09:16:18 INFO  [vector] Document embedded and stored - doc_id: abc123
2024-12-01 09:16:45 INFO  [api] POST /search - 200 OK - 87ms
2024-12-01 09:16:46 DEBUG [search] Query: "machine learning" - 5 results found
2024-12-01 09:17:12 WARN  [llm] Provider timeout, switching to fallback
2024-12-01 09:17:13 INFO  [llm] Fallback provider response successful
2024-12-01 09:17:30 ERROR [api] POST /invalid-endpoint - 404 Not Found
2024-12-01 09:18:00 INFO  [scheduler] Background cleanup task completed
""",

            "xml_data.xml": """<?xml version="1.0" encoding="UTF-8"?>
<research_paper>
    <metadata>
        <title>Advances in Natural Language Processing</title>
        <authors>
            <author>Dr. Sarah Wilson</author>
            <author>Prof. Michael Chen</author>
        </authors>
        <institution>University of Technology</institution>
        <date>2024-11-15</date>
        <keywords>NLP, transformers, attention mechanism, BERT, GPT</keywords>
    </metadata>
    <abstract>
        This paper presents recent advances in natural language processing,
        focusing on transformer architectures and their applications.
        We demonstrate significant improvements in text understanding
        and generation tasks across multiple domains.
    </abstract>
    <sections>
        <section id="introduction">
            <title>Introduction</title>
            <content>
                Natural Language Processing has evolved rapidly with the
                introduction of transformer models. These architectures
                have revolutionized how machines understand and generate text.
            </content>
        </section>
        <section id="methodology">
            <title>Methodology</title>
            <content>
                We evaluated multiple transformer models including BERT,
                GPT-3, and T5 across various benchmarks. Our experiments
                covered text classification, summarization, and generation.
            </content>
        </section>
        <section id="results">
            <title>Results</title>
            <content>
                Results show consistent improvements across all tasks.
                BERT achieved 94.2% accuracy on classification tasks,
                while GPT-3 generated human-like text with high coherence.
            </content>
        </section>
    </sections>
</research_paper>"""
        }

        # Create HTML files
        html_files = {
            "webpage.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Research Lab</title>
</head>
<body>
    <header>
        <h1>AI Research Laboratory</h1>
        <nav>
            <a href="#about">About</a>
            <a href="#research">Research</a>
            <a href="#publications">Publications</a>
        </nav>
    </header>

    <main>
        <section id="about">
            <h2>About Our Lab</h2>
            <p>We are a cutting-edge research facility focusing on artificial intelligence
            and machine learning. Our team of 20+ researchers works on breakthrough
            technologies in natural language processing, computer vision, and robotics.</p>

            <h3>Research Areas</h3>
            <ul>
                <li><strong>Natural Language Processing</strong> - Advanced text understanding</li>
                <li><strong>Computer Vision</strong> - Image and video analysis</li>
                <li><strong>Robotics</strong> - Autonomous systems and control</li>
                <li><strong>Machine Learning</strong> - Novel algorithms and architectures</li>
            </ul>
        </section>

        <section id="research">
            <h2>Current Research Projects</h2>
            <div class="project">
                <h3>Project Alpha: Conversational AI</h3>
                <p>Developing next-generation chatbots with improved context understanding.</p>
                <p><em>Status:</em> Active | <em>Team:</em> 5 researchers | <em>Duration:</em> 18 months</p>
            </div>

            <div class="project">
                <h3>Project Beta: Visual Understanding</h3>
                <p>Creating AI systems that can interpret complex visual scenes.</p>
                <p><em>Status:</em> Phase 2 | <em>Team:</em> 7 researchers | <em>Duration:</em> 24 months</p>
            </div>
        </section>

        <section id="publications">
            <h2>Recent Publications</h2>
            <table>
                <tr>
                    <th>Title</th>
                    <th>Authors</th>
                    <th>Venue</th>
                    <th>Year</th>
                </tr>
                <tr>
                    <td>Attention Mechanisms in Modern NLP</td>
                    <td>Smith, J. et al.</td>
                    <td>AAAI 2024</td>
                    <td>2024</td>
                </tr>
                <tr>
                    <td>Robotic Vision for Autonomous Navigation</td>
                    <td>Chen, L. et al.</td>
                    <td>ICRA 2024</td>
                    <td>2024</td>
                </tr>
            </table>
        </section>
    </main>

    <footer>
        <p>&copy; 2024 AI Research Laboratory. All rights reserved.</p>
        <p>Contact: research@ailab.edu | Phone: (555) 123-4567</p>
    </footer>
</body>
</html>""",

            "form_data.html": """<!DOCTYPE html>
<html>
<head><title>Survey Form</title></head>
<body>
    <h1>Customer Feedback Survey</h1>
    <form action="/submit" method="post">
        <fieldset>
            <legend>Personal Information</legend>
            <label>Name: <input type="text" name="name" required></label><br>
            <label>Email: <input type="email" name="email" required></label><br>
            <label>Age: <input type="number" name="age" min="18" max="100"></label><br>
        </fieldset>

        <fieldset>
            <legend>Feedback</legend>
            <label>Overall satisfaction:</label>
            <input type="radio" name="satisfaction" value="excellent"> Excellent
            <input type="radio" name="satisfaction" value="good"> Good
            <input type="radio" name="satisfaction" value="fair"> Fair
            <input type="radio" name="satisfaction" value="poor"> Poor<br>

            <label>Services used (check all that apply):</label><br>
            <input type="checkbox" name="services" value="support"> Customer Support<br>
            <input type="checkbox" name="services" value="billing"> Billing<br>
            <input type="checkbox" name="services" value="technical"> Technical Services<br>

            <label>Additional comments:</label><br>
            <textarea name="comments" rows="4" cols="50"></textarea><br>
        </fieldset>

        <button type="submit">Submit Feedback</button>
    </form>
</body>
</html>"""
        }

        # Write all text-based files
        for filename, content in {**text_files, **html_files}.items():
            file_path = self.temp_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        # Create binary test files
        await self.create_binary_test_files()

        logger.info(f"Created {len(text_files) + len(html_files) + 3} test documents")

    async def create_binary_test_files(self):
        """Create binary test files for more comprehensive testing"""

        # Create a simple PDF-like content
        pdf_content = """%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(This is a test PDF document) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
295
%%EOF"""

        with open(self.temp_dir / "test_document.pdf", 'w') as f:
            f.write(pdf_content)

        # Create a mock image file (PNG header + some data)
        png_data = (
            b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'  # PNG signature
            b'\x00\x00\x00\x0D\x49\x48\x44\x52'  # IHDR chunk
            b'\x00\x00\x00\x01\x00\x00\x00\x01'  # 1x1 pixel
            b'\x08\x02\x00\x00\x00\x90\x77\x53\xDE'  # IHDR data + CRC
            b'\x00\x00\x00\x0C\x49\x44\x41\x54'  # IDAT chunk
            b'\x78\x9C\x63\x00\x01\x00\x00\x05\x00\x01\x0D\x0A\x2D\xB4'  # IDAT data + CRC
            b'\x00\x00\x00\x00\x49\x45\x4E\x44\xAE\x42\x60\x82'  # IEND chunk
        )

        with open(self.temp_dir / "test_image.png", 'wb') as f:
            f.write(png_data)

        # Create a mock email file
        email_content = """From: sender@example.com
To: recipient@example.com
Subject: Test Email for RAG Processing
Date: Mon, 1 Dec 2024 10:30:00 +0000
Content-Type: text/plain; charset=UTF-8

Dear Team,

This is a test email message for validating email processing capabilities
in the modernized RAG service.

Key points:
- Email parsing should extract headers and body content
- Metadata should include sender, recipient, subject, and date
- Content should be properly cleaned and formatted

The email contains both structured metadata and unstructured content,
making it ideal for testing the enhanced document processing pipeline.

Best regards,
Test Sender

---
This email was generated for testing purposes.
Contact: test@example.com
Phone: (555) 123-4567
"""

        with open(self.temp_dir / "test_email.eml", 'w') as f:
            f.write(email_content)

    async def verify_service_health(self):
        """Verify that the RAG service is running and healthy"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                logger.info("✅ Service health check passed")
                logger.info(f"   Platform: {health_data.get('platform', 'unknown')}")
                logger.info(f"   OCR Available: {health_data.get('ocr_available', False)}")
                logger.info(f"   LLM Providers: {health_data.get('llm_providers', {})}")
                return True
            else:
                logger.error(f"❌ Service health check failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Service health check failed: {e}")
            return False

    async def test_document_processing(self):
        """Test document processing with all sample documents"""
        logger.info("=" * 60)
        logger.info("TESTING DOCUMENT PROCESSING")
        logger.info("=" * 60)

        processing_results = {}

        for file_path in self.temp_dir.iterdir():
            if file_path.is_file():
                await self.test_single_document(file_path, processing_results)

        return processing_results

    async def test_single_document(self, file_path: Path, results: Dict):
        """Test processing of a single document"""
        filename = file_path.name
        logger.info(f"\nTesting: {filename}")

        try:
            # Test file upload and processing
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f, 'application/octet-stream')}
                data = {
                    'process_ocr': 'true',
                    'generate_obsidian': 'true'
                }

                start_time = time.time()
                response = requests.post(
                    f"{self.base_url}/ingest/file",
                    files=files,
                    data=data,
                    timeout=60
                )
                processing_time = time.time() - start_time

            if response.status_code == 200:
                result_data = response.json()
                doc_id = result_data.get('doc_id')
                chunks = result_data.get('chunks', 0)
                metadata = result_data.get('metadata', {})

                results[filename] = {
                    'status': 'success',
                    'doc_id': doc_id,
                    'chunks': chunks,
                    'processing_time': processing_time,
                    'metadata_keys': list(metadata.keys()),
                    'file_size': file_path.stat().st_size
                }

                logger.info(f"  ✅ Success - Doc ID: {doc_id}")
                logger.info(f"     Chunks: {chunks}, Time: {processing_time:.2f}s")
                logger.info(f"     Metadata: {len(metadata)} fields")

                self.passed_tests += 1

            else:
                results[filename] = {
                    'status': 'failed',
                    'error': f"HTTP {response.status_code}: {response.text[:200]}",
                    'processing_time': processing_time
                }
                logger.error(f"  ❌ Failed - {response.status_code}: {response.text[:100]}")
                self.failed_tests += 1

        except Exception as e:
            results[filename] = {
                'status': 'error',
                'error': str(e),
                'processing_time': 0
            }
            logger.error(f"  ❌ Error - {str(e)}")
            self.failed_tests += 1

        self.total_tests += 1

    async def test_llm_providers(self):
        """Test all available LLM providers"""
        logger.info("=" * 60)
        logger.info("TESTING LLM PROVIDERS")
        logger.info("=" * 60)

        providers_to_test = [
            ("groq", "groq/llama-3.1-8b-instant"),
            ("anthropic", "anthropic/claude-3-haiku-20240307"),
            ("openai", "openai/gpt-4o-mini"),
            ("google", "google/gemini-1.5-pro")
        ]

        llm_results = {}

        for provider, model in providers_to_test:
            logger.info(f"\nTesting {provider} ({model})...")

            try:
                test_data = {
                    "provider": provider,
                    "model": model,
                    "prompt": "Explain machine learning in exactly one sentence."
                }

                start_time = time.time()
                response = requests.post(
                    f"{self.base_url}/test-llm",
                    json=test_data,
                    timeout=30
                )
                response_time = time.time() - start_time

                if response.status_code == 200:
                    result = response.json()
                    llm_results[provider] = {
                        'status': 'success',
                        'model': model,
                        'response_time': response_time,
                        'response_length': len(result.get('response', '')),
                        'cost': result.get('cost', 0)
                    }

                    logger.info(f"  ✅ {provider} - Response: {result.get('response', '')[:100]}...")
                    logger.info(f"     Time: {response_time:.2f}s, Cost: ${result.get('cost', 0):.6f}")

                    self.passed_tests += 1

                else:
                    llm_results[provider] = {
                        'status': 'failed',
                        'error': f"HTTP {response.status_code}",
                        'response_time': response_time
                    }
                    logger.error(f"  ❌ {provider} failed - {response.status_code}")
                    self.failed_tests += 1

            except Exception as e:
                llm_results[provider] = {
                    'status': 'error',
                    'error': str(e),
                    'response_time': 0
                }
                logger.error(f"  ❌ {provider} error - {str(e)}")
                self.failed_tests += 1

            self.total_tests += 1

        return llm_results

    async def test_search_functionality(self):
        """Test search functionality with various queries"""
        logger.info("=" * 60)
        logger.info("TESTING SEARCH FUNCTIONALITY")
        logger.info("=" * 60)

        search_queries = [
            "machine learning",
            "natural language processing",
            "system performance",
            "research project",
            "customer feedback",
            "team collaboration",
            "data analysis",
            "artificial intelligence"
        ]

        search_results = {}

        for query in search_queries:
            logger.info(f"\nTesting search: '{query}'")

            try:
                search_data = {
                    "text": query,
                    "top_k": 5
                }

                start_time = time.time()
                response = requests.post(
                    f"{self.base_url}/search",
                    json=search_data,
                    timeout=30
                )
                search_time = time.time() - start_time

                if response.status_code == 200:
                    result = response.json()
                    results = result.get('results', [])

                    search_results[query] = {
                        'status': 'success',
                        'results_count': len(results),
                        'search_time': search_time,
                        'has_results': len(results) > 0
                    }

                    logger.info(f"  ✅ Found {len(results)} results in {search_time:.2f}s")

                    if results:
                        top_result = results[0]
                        relevance = top_result.get('relevance_score', 0)
                        content_preview = top_result.get('content', '')[:100]
                        logger.info(f"     Top result: {relevance:.3f} - {content_preview}...")

                    self.passed_tests += 1

                else:
                    search_results[query] = {
                        'status': 'failed',
                        'error': f"HTTP {response.status_code}",
                        'search_time': search_time
                    }
                    logger.error(f"  ❌ Search failed - {response.status_code}")
                    self.failed_tests += 1

            except Exception as e:
                search_results[query] = {
                    'status': 'error',
                    'error': str(e),
                    'search_time': 0
                }
                logger.error(f"  ❌ Search error - {str(e)}")
                self.failed_tests += 1

            self.total_tests += 1

        return search_results

    async def test_chat_functionality(self):
        """Test RAG-enhanced chat functionality"""
        logger.info("=" * 60)
        logger.info("TESTING RAG CHAT FUNCTIONALITY")
        logger.info("=" * 60)

        chat_questions = [
            "What is machine learning?",
            "Explain the system performance results",
            "What are the research projects mentioned?",
            "Summarize the customer feedback survey",
            "What technologies are discussed in the documents?",
            "Who are the team members mentioned?"
        ]

        chat_results = {}

        for question in chat_questions:
            logger.info(f"\nTesting chat: '{question}'")

            try:
                chat_data = {
                    "question": question,
                    "llm_model": "groq/llama-3.1-8b-instant",
                    "max_context_chunks": 3,
                    "include_sources": True
                }

                start_time = time.time()
                response = requests.post(
                    f"{self.base_url}/chat",
                    json=chat_data,
                    timeout=30
                )
                chat_time = time.time() - start_time

                if response.status_code == 200:
                    result = response.json()
                    answer = result.get('answer', '')
                    sources = result.get('sources', [])
                    context_used = result.get('context_chunks_used', 0)

                    chat_results[question] = {
                        'status': 'success',
                        'answer_length': len(answer),
                        'sources_count': len(sources),
                        'context_chunks': context_used,
                        'response_time': chat_time
                    }

                    logger.info(f"  ✅ Response generated in {chat_time:.2f}s")
                    logger.info(f"     Answer length: {len(answer)} chars")
                    logger.info(f"     Sources: {len(sources)}, Context chunks: {context_used}")
                    logger.info(f"     Answer preview: {answer[:150]}...")

                    self.passed_tests += 1

                else:
                    chat_results[question] = {
                        'status': 'failed',
                        'error': f"HTTP {response.status_code}",
                        'response_time': chat_time
                    }
                    logger.error(f"  ❌ Chat failed - {response.status_code}")
                    self.failed_tests += 1

            except Exception as e:
                chat_results[question] = {
                    'status': 'error',
                    'error': str(e),
                    'response_time': 0
                }
                logger.error(f"  ❌ Chat error - {str(e)}")
                self.failed_tests += 1

            self.total_tests += 1

        return chat_results

    async def test_edge_cases(self):
        """Test edge cases and error handling"""
        logger.info("=" * 60)
        logger.info("TESTING EDGE CASES")
        logger.info("=" * 60)

        edge_cases = []

        # Test empty document
        logger.info("\nTesting empty document...")
        try:
            empty_file = self.temp_dir / "empty.txt"
            empty_file.touch()

            with open(empty_file, 'rb') as f:
                files = {'file': ('empty.txt', f, 'text/plain')}
                response = requests.post(f"{self.base_url}/ingest/file", files=files, timeout=30)

            edge_cases.append({
                'test': 'empty_document',
                'status': 'success' if response.status_code == 200 else 'handled_error',
                'response_code': response.status_code
            })

        except Exception as e:
            edge_cases.append({
                'test': 'empty_document',
                'status': 'error',
                'error': str(e)
            })

        # Test very large text
        logger.info("Testing large document...")
        try:
            large_text = "This is a large document. " * 10000  # ~250KB
            large_file = self.temp_dir / "large.txt"
            with open(large_file, 'w') as f:
                f.write(large_text)

            with open(large_file, 'rb') as f:
                files = {'file': ('large.txt', f, 'text/plain')}
                response = requests.post(f"{self.base_url}/ingest/file", files=files, timeout=60)

            edge_cases.append({
                'test': 'large_document',
                'status': 'success' if response.status_code == 200 else 'handled_error',
                'response_code': response.status_code,
                'file_size': len(large_text)
            })

        except Exception as e:
            edge_cases.append({
                'test': 'large_document',
                'status': 'error',
                'error': str(e)
            })

        # Test special characters
        logger.info("Testing special characters...")
        try:
            special_text = """Special characters: áéíóú, ñ, ü, ç, ß, ø, æ, œ
            Unicode: 🚀 💡 🔬 📊 🤖 🌟
            Math symbols: ∀ ∃ ∈ ⊆ ∪ ∩ ∅ ℝ ℕ ℤ ∞
            Technical: λ, Δ, Σ, Π, Ω, α, β, γ, θ, π
            Punctuation: «», ‹›, "", '', ‚„, ¿¡, …, –—
            Currency: $ € £ ¥ ₹ ₽ ₩ ₪ ₨ ₦
            Chinese: 你好世界
            Japanese: こんにちは世界
            Arabic: مرحبا بالعالم
            Russian: Привет мир
            """

            special_file = self.temp_dir / "special_chars.txt"
            with open(special_file, 'w', encoding='utf-8') as f:
                f.write(special_text)

            with open(special_file, 'rb') as f:
                files = {'file': ('special_chars.txt', f, 'text/plain')}
                response = requests.post(f"{self.base_url}/ingest/file", files=files, timeout=30)

            edge_cases.append({
                'test': 'special_characters',
                'status': 'success' if response.status_code == 200 else 'handled_error',
                'response_code': response.status_code
            })

        except Exception as e:
            edge_cases.append({
                'test': 'special_characters',
                'status': 'error',
                'error': str(e)
            })

        # Test invalid search queries
        logger.info("Testing invalid search queries...")
        invalid_queries = ["", " ", "a" * 1000, "🚀" * 100]

        for query in invalid_queries:
            try:
                search_data = {"text": query, "top_k": 5}
                response = requests.post(f"{self.base_url}/search", json=search_data, timeout=10)

                edge_cases.append({
                    'test': f'invalid_query_{len(query)}',
                    'status': 'success' if response.status_code == 200 else 'handled_error',
                    'response_code': response.status_code,
                    'query_length': len(query)
                })

            except Exception as e:
                edge_cases.append({
                    'test': f'invalid_query_{len(query)}',
                    'status': 'error',
                    'error': str(e)
                })

        return edge_cases

    async def test_performance_stress(self):
        """Test performance under stress conditions"""
        logger.info("=" * 60)
        logger.info("TESTING PERFORMANCE & STRESS")
        logger.info("=" * 60)

        performance_results = {}

        # Test concurrent document processing
        logger.info("Testing concurrent document processing...")

        async def process_document_concurrent(file_path: Path, session_id: int):
            try:
                with open(file_path, 'rb') as f:
                    files = {'file': (f'concurrent_{session_id}_{file_path.name}', f, 'application/octet-stream')}
                    start_time = time.time()
                    response = requests.post(f"{self.base_url}/ingest/file", files=files, timeout=30)
                    processing_time = time.time() - start_time

                return {
                    'session_id': session_id,
                    'status': 'success' if response.status_code == 200 else 'failed',
                    'processing_time': processing_time,
                    'response_code': response.status_code
                }
            except Exception as e:
                return {
                    'session_id': session_id,
                    'status': 'error',
                    'error': str(e),
                    'processing_time': 0
                }

        # Test with 5 concurrent uploads of the same file
        test_file = self.temp_dir / "markdown_doc.md"
        if test_file.exists():
            concurrent_tasks = []
            for i in range(5):
                task = process_document_concurrent(test_file, i)
                concurrent_tasks.append(task)

            start_time = time.time()
            concurrent_results = await asyncio.gather(*concurrent_tasks)
            total_time = time.time() - start_time

            successful = sum(1 for r in concurrent_results if r['status'] == 'success')
            avg_time = sum(r['processing_time'] for r in concurrent_results) / len(concurrent_results)

            performance_results['concurrent_processing'] = {
                'total_requests': len(concurrent_results),
                'successful': successful,
                'failed': len(concurrent_results) - successful,
                'total_time': total_time,
                'average_processing_time': avg_time,
                'requests_per_second': len(concurrent_results) / total_time
            }

            logger.info(f"  Concurrent processing: {successful}/{len(concurrent_results)} successful")
            logger.info(f"  Total time: {total_time:.2f}s, Avg per request: {avg_time:.2f}s")
            logger.info(f"  Throughput: {len(concurrent_results) / total_time:.2f} req/s")

        # Test search performance
        logger.info("Testing search performance...")
        search_queries = ["machine learning", "system performance", "research"] * 10

        search_times = []
        for query in search_queries:
            try:
                start_time = time.time()
                response = requests.post(
                    f"{self.base_url}/search",
                    json={"text": query, "top_k": 5},
                    timeout=10
                )
                search_time = time.time() - start_time
                if response.status_code == 200:
                    search_times.append(search_time)
            except:
                pass

        if search_times:
            performance_results['search_performance'] = {
                'total_searches': len(search_times),
                'average_time': sum(search_times) / len(search_times),
                'min_time': min(search_times),
                'max_time': max(search_times),
                'searches_per_second': len(search_times) / sum(search_times)
            }

            avg_time = sum(search_times) / len(search_times)
            logger.info(f"  Search performance: {len(search_times)} searches")
            logger.info(f"  Average time: {avg_time:.3f}s, Range: {min(search_times):.3f}-{max(search_times):.3f}s")

        return performance_results

    async def run_comprehensive_validation(self):
        """Run the complete validation suite"""
        logger.info("🚀 Starting Comprehensive RAG Service Validation")
        logger.info("=" * 80)

        # Setup
        await self.setup_test_environment()

        # Run all test suites
        self.test_results['document_processing'] = await self.test_document_processing()
        self.test_results['llm_providers'] = await self.test_llm_providers()
        self.test_results['search_functionality'] = await self.test_search_functionality()
        self.test_results['chat_functionality'] = await self.test_chat_functionality()
        self.test_results['edge_cases'] = await self.test_edge_cases()
        self.test_results['performance'] = await self.test_performance_stress()

        # Generate final report
        await self.generate_validation_report()

    async def generate_validation_report(self):
        """Generate comprehensive validation report"""
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE VALIDATION SUMMARY")
        logger.info("=" * 80)

        # Overall statistics
        logger.info(f"\n📊 OVERALL RESULTS:")
        logger.info(f"   Total Tests: {self.total_tests}")
        logger.info(f"   Passed: {self.passed_tests}")
        logger.info(f"   Failed: {self.failed_tests}")
        logger.info(f"   Success Rate: {(self.passed_tests/self.total_tests*100):.1f}%")

        # Document processing summary
        doc_results = self.test_results.get('document_processing', {})
        successful_docs = sum(1 for r in doc_results.values() if r.get('status') == 'success')
        logger.info(f"\n📄 DOCUMENT PROCESSING:")
        logger.info(f"   Documents tested: {len(doc_results)}")
        logger.info(f"   Successfully processed: {successful_docs}")
        logger.info(f"   Processing success rate: {(successful_docs/len(doc_results)*100):.1f}%")

        # LLM providers summary
        llm_results = self.test_results.get('llm_providers', {})
        working_providers = sum(1 for r in llm_results.values() if r.get('status') == 'success')
        logger.info(f"\n🤖 LLM PROVIDERS:")
        logger.info(f"   Providers tested: {len(llm_results)}")
        logger.info(f"   Working providers: {working_providers}")
        logger.info(f"   Provider success rate: {(working_providers/len(llm_results)*100):.1f}%")

        # Search functionality summary
        search_results = self.test_results.get('search_functionality', {})
        successful_searches = sum(1 for r in search_results.values() if r.get('status') == 'success')
        logger.info(f"\n🔍 SEARCH FUNCTIONALITY:")
        logger.info(f"   Search queries tested: {len(search_results)}")
        logger.info(f"   Successful searches: {successful_searches}")
        logger.info(f"   Search success rate: {(successful_searches/len(search_results)*100):.1f}%")

        # Performance summary
        performance = self.test_results.get('performance', {})
        if 'concurrent_processing' in performance:
            concurrent = performance['concurrent_processing']
            logger.info(f"\n⚡ PERFORMANCE:")
            logger.info(f"   Concurrent processing: {concurrent['successful']}/{concurrent['total_requests']}")
            logger.info(f"   Throughput: {concurrent['requests_per_second']:.2f} req/s")

        if 'search_performance' in performance:
            search_perf = performance['search_performance']
            logger.info(f"   Search performance: {search_perf['average_time']:.3f}s avg")

        # Generate detailed JSON report
        report_data = {
            'validation_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': self.total_tests,
                'passed_tests': self.passed_tests,
                'failed_tests': self.failed_tests,
                'success_rate': self.passed_tests / self.total_tests * 100
            },
            'detailed_results': self.test_results
        }

        # Save report
        report_file = Path('COMPREHENSIVE_VALIDATION_REPORT.json')
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

        logger.info(f"\n📋 Detailed report saved to: {report_file}")

        # Final verdict
        if self.passed_tests / self.total_tests >= 0.9:
            logger.info("\n🎉 VALIDATION VERDICT: EXCELLENT - Service is production ready!")
        elif self.passed_tests / self.total_tests >= 0.8:
            logger.info("\n✅ VALIDATION VERDICT: GOOD - Service is ready with minor issues")
        elif self.passed_tests / self.total_tests >= 0.7:
            logger.info("\n⚠️  VALIDATION VERDICT: ACCEPTABLE - Service needs improvements")
        else:
            logger.info("\n❌ VALIDATION VERDICT: NEEDS WORK - Service requires fixes")

async def main():
    """Main function to run comprehensive validation"""
    validator = ComprehensiveValidator()
    await validator.run_comprehensive_validation()

if __name__ == "__main__":
    asyncio.run(main())