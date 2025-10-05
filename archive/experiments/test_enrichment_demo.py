#!/usr/bin/env python3
"""
Document Enrichment Demo

This demonstrates how the LLM enrichment creates:
- Intelligent summaries and abstracts
- Hierarchical tag taxonomies
- Rich metadata extraction
- Obsidian-style markdown with frontmatter
- Cross-document linking and relationship discovery
"""

import asyncio
import json
import tempfile
from pathlib import Path
import requests

async def test_document_enrichment_pipeline():
    """Test the complete enrichment pipeline with real examples"""

    print("🚀 Document Enrichment Pipeline Demo")
    print("=" * 60)

    # Test documents with different types and complexity
    test_documents = {
        "technical_report.txt": """
# Machine Learning Infrastructure Performance Analysis Q3 2024

## Executive Summary

This comprehensive analysis examines the performance characteristics of our ML infrastructure deployed across AWS, Azure, and Google Cloud platforms. Key findings indicate a 42% improvement in model inference latency and 28% reduction in compute costs through optimized resource allocation.

## Methodology

Our evaluation employed distributed testing across three major cloud providers, analyzing performance metrics for 15 different ML model architectures including:

- Transformer models (BERT, GPT variants)
- Computer vision models (ResNet, EfficientNet)
- Time series forecasting models (LSTM, Prophet)

### Infrastructure Components

**AWS Environment:**
- EC2 P4 instances with NVIDIA A100 GPUs
- EKS clusters for container orchestration
- S3 for model artifact storage
- CloudWatch for monitoring

**Azure Environment:**
- Azure Machine Learning compute instances
- AKS for Kubernetes workloads
- Blob Storage for data persistence
- Application Insights for telemetry

**Google Cloud Environment:**
- Vertex AI training and prediction
- GKE clusters with Autopilot
- Cloud Storage for ML pipelines
- Cloud Monitoring for observability

## Key Findings

### Performance Improvements

1. **Inference Latency**: Reduced from 150ms to 87ms average (42% improvement)
2. **Throughput**: Increased from 500 req/sec to 750 req/sec (50% improvement)
3. **Cost Efficiency**: 28% reduction in compute costs per prediction
4. **Model Accuracy**: Maintained 99.2% accuracy while improving speed

### Technology Stack Optimizations

- **TensorRT**: GPU optimization reduced inference time by 35%
- **ONNX Runtime**: Cross-platform inference improved portability
- **Kubernetes HPA**: Auto-scaling reduced resource waste by 40%
- **Ray Serve**: Distributed serving improved fault tolerance

## Team Contributions

**Lead Engineers:**
- Sarah Chen (MLOps Architecture)
- Michael Rodriguez (Infrastructure Optimization)
- Priya Patel (Performance Analysis)

**Contributing Teams:**
- Data Science Team (Model Optimization)
- Platform Engineering (Infrastructure)
- DevOps Team (CI/CD Pipelines)

## Recommendations

1. **Immediate Actions (Next 30 days)**:
   - Deploy TensorRT optimization to all production models
   - Implement cross-cloud load balancing
   - Upgrade monitoring and alerting systems

2. **Medium-term Initiatives (3-6 months)**:
   - Migrate legacy models to optimized inference engines
   - Implement MLOps best practices across all teams
   - Establish cost optimization governance

3. **Strategic Investments (6-12 months)**:
   - Evaluate edge computing for latency-critical applications
   - Research quantum computing applications for optimization problems
   - Build internal AI infrastructure platform

## Conclusion

The Q3 performance analysis validates our multi-cloud ML infrastructure strategy. Significant improvements in latency, throughput, and cost efficiency position us well for scaling our AI capabilities. Continued investment in infrastructure optimization and MLOps practices will ensure sustainable growth.

## References

- Internal Performance Benchmarking Report Q3-2024
- AWS ML Best Practices Guide v2.1
- Azure ML Architecture Patterns 2024
- Google Cloud AI Platform Documentation
""",

        "team_meeting_notes.txt": """
Weekly Team Sync - AI Research Lab
Date: September 28, 2024
Attendees: Alice Johnson, Bob Chen, Charlie Davis, Diana Martinez, Eve Thompson

## Project Updates

### Project Alpha: Conversational AI Enhancement
**Owner:** Alice Johnson
**Status:** On track for Q4 delivery

Progress this week:
- Completed integration testing with new transformer architecture
- Improved response quality by 23% in human evaluation
- Reduced training time from 48 hours to 18 hours using optimized data pipeline

Blockers:
- Waiting for GPU cluster approval for large-scale training
- Need ethics review for bias testing framework

Next week:
- Begin user acceptance testing with beta users
- Finalize deployment strategy for production rollout

### Project Beta: Document Intelligence Platform
**Owner:** Bob Chen
**Status:** Ahead of schedule

Achievements:
- Successfully processed 50,000 documents in benchmark testing
- OCR accuracy improved to 98.5% for scanned documents
- Implemented multi-language support (English, Spanish, French, German)

Technical highlights:
- Integrated Unstructured.io for advanced document parsing
- Added LiteLLM for unified LLM provider management
- Deployed sentence-transformers for document reranking

Upcoming milestones:
- Launch internal beta next week
- Begin customer pilot program in October

### Project Gamma: Predictive Analytics Dashboard
**Owner:** Charlie Davis
**Status:** Minor delays due to data quality issues

Current challenges:
- Data integration from legacy systems taking longer than expected
- Need to resolve schema inconsistencies between data sources
- Performance optimization required for real-time dashboard updates

Solutions in progress:
- Implemented data validation pipeline
- Working with IT team on database migration
- Exploring caching strategies for improved performance

## Team Discussions

### Hiring Updates
**Diana Martinez** provided update on open positions:
- Senior ML Engineer: 3 candidates in final round
- Data Scientist: Offer extended to preferred candidate
- DevOps Engineer: Interviews scheduled for next week

### Technology Decisions
**Eve Thompson** led discussion on standardizing ML infrastructure:

Decisions made:
- Adopt Kubernetes for all ML workload orchestration
- Standardize on Python 3.11 for new projects
- Implement MLflow for experiment tracking across all teams

Action items:
- Create migration plan for existing projects (Owner: Bob)
- Set up training sessions for Kubernetes (Owner: Alice)
- Evaluate MLflow integration requirements (Owner: Charlie)

### Budget Planning Q4 2024
Discussed resource allocation for Q4:
- Cloud infrastructure costs projected at $45K/month
- Additional GPU resources needed for Project Alpha
- Training budget approved for team certifications

## Action Items

1. **Alice**: Submit GPU cluster request by Friday
2. **Bob**: Schedule internal beta kickoff meeting
3. **Charlie**: Provide data migration timeline by Tuesday
4. **Diana**: Send offer details to data scientist candidate
5. **Eve**: Create Kubernetes training schedule

## Next Meeting
Date: October 5, 2024
Time: 2:00 PM PST
Location: Conference Room B / Zoom Hybrid

Special topics:
- Q4 planning and goal setting
- Technology roadmap review
- Team performance reviews
""",

        "research_paper_abstract.txt": """
Attention-Based Neural Architecture Search for Efficient Transformer Models

Authors: Dr. Lisa Wang¹, Prof. James Miller², Dr. Sarah Kim¹, Alex Johnson³
¹Stanford University, ²MIT, ³Google Research

Abstract

We present AUTOFORMER, a novel neural architecture search (NAS) framework specifically designed for discovering efficient transformer architectures. Our approach leverages attention mechanisms not only within the candidate architectures but also in the search process itself, enabling more effective exploration of the design space.

Traditional NAS methods for transformers often rely on predefined search spaces that may miss optimal configurations. AUTOFORMER addresses this limitation by introducing a learnable attention-based controller that dynamically adjusts the search strategy based on intermediate results. The controller evaluates architectural components including attention head configurations, layer depths, embedding dimensions, and feed-forward network sizes.

Our experimental evaluation on multiple benchmarks demonstrates significant improvements over existing approaches:
- 15% reduction in model parameters while maintaining accuracy
- 32% improvement in inference speed on mobile devices
- 18% lower energy consumption during training
- Superior performance on GLUE, SuperGLUE, and custom language tasks

Key innovations include:
1. Attention-driven architecture sampling that focuses on promising regions
2. Multi-objective optimization balancing accuracy, efficiency, and resource constraints
3. Progressive search refinement that adapts to hardware constraints
4. Transfer learning capabilities across different domains and scales

The discovered architectures consistently outperform manually designed transformers and other NAS-generated models across diverse tasks including natural language understanding, machine translation, and document classification. Notably, our compact models achieve 96.8% of BERT-Large performance with only 40% of the parameters.

Implementation details and code are available at: https://github.com/stanford-ai/autoformer
Reproducibility artifacts and trained models: https://huggingface.co/stanford-ai/autoformer

This work establishes new benchmarks for efficient transformer design and provides practitioners with automated tools for creating task-specific architectures that balance performance and computational requirements.

Keywords: Neural Architecture Search, Transformers, Attention Mechanisms, Model Efficiency, AutoML, Natural Language Processing
""",

        "customer_feedback_email.txt": """
Subject: Quarterly Customer Satisfaction Survey Results - Q3 2024

Dear Product Team,

I'm pleased to share the results from our Q3 2024 customer satisfaction survey. We received responses from 2,847 customers across all product tiers, representing a 34% response rate.

## Overall Satisfaction Metrics

**Net Promoter Score (NPS):** 72 (Industry benchmark: 58)
**Customer Satisfaction Score (CSAT):** 4.3/5.0 (Up from 4.1 in Q2)
**Customer Effort Score (CES):** 2.1/7.0 (Lower is better, improved from 2.4)

## Key Findings by Category

### Product Features (4.2/5.0 average)
**Highly Rated:**
- User interface design and usability (4.6/5.0)
- Integration capabilities with existing tools (4.4/5.0)
- Data export and reporting features (4.3/5.0)

**Areas for Improvement:**
- Mobile app performance (3.7/5.0)
- Advanced search functionality (3.8/5.0)
- Customization options (3.9/5.0)

### Customer Support (4.4/5.0 average)
**Strengths:**
- Response time to support tickets (4.6/5.0)
- Technical knowledge of support staff (4.5/5.0)
- Multi-channel support availability (4.3/5.0)

**Opportunities:**
- Self-service documentation quality (3.9/5.0)
- Video tutorial library completeness (4.0/5.0)

### Platform Performance (4.1/5.0 average)
**Positive Feedback:**
- System uptime and reliability (4.5/5.0)
- Data processing speed (4.2/5.0)
- Security and privacy measures (4.4/5.0)

**Concerns:**
- Load times during peak usage (3.6/5.0)
- Occasional sync issues with cloud storage (3.8/5.0)

## Verbatim Customer Comments

**Positive Feedback:**
"The recent UI improvements have made our daily workflows so much more efficient. The team is saving 2-3 hours per week on routine tasks." - Enterprise Customer

"Outstanding customer support experience. The technical team resolved our integration challenge within 24 hours." - Mid-market Customer

"Love the new dashboard features. Finally have the visibility we need for data-driven decisions." - SMB Customer

**Constructive Criticism:**
"Mobile app crashes frequently on Android devices. Hoping for stability improvements soon." - Enterprise Customer

"Would appreciate more granular permission controls for team management." - Mid-market Customer

"Search functionality needs work - hard to find specific documents quickly." - SMB Customer

## Customer Segmentation Analysis

### Enterprise Customers (500+ employees)
- Higher satisfaction with advanced features (4.5/5.0)
- Strong demand for enhanced security controls
- Willing to pay premium for white-label options

### Mid-market Customers (50-500 employees)
- Most satisfied with price-to-value ratio (4.4/5.0)
- Request more automation capabilities
- High interest in API access and integrations

### SMB Customers (<50 employees)
- Value ease of use above advanced features (4.6/5.0)
- Price sensitivity higher than other segments
- Prefer guided onboarding and templates

## Competitive Analysis Insights

Customers compared us favorably to competitors in:
- User experience and interface design
- Customer support responsiveness
- Integration ecosystem breadth

Areas where competitors lead:
- Mobile application quality
- Advanced analytics capabilities
- Pricing flexibility

## Recommended Actions

### Immediate (Next 30 days)
1. **Mobile App Stability**: Deploy hotfix for Android crash issues
2. **Performance Optimization**: Implement caching for peak load handling
3. **Documentation Update**: Refresh self-service help articles

### Short-term (Next Quarter)
1. **Search Enhancement**: Implement AI-powered semantic search
2. **Customization Expansion**: Add user interface personalization options
3. **Mobile App Redesign**: Complete native app rewrite for better performance

### Medium-term (Next 6 months)
1. **Advanced Analytics**: Build predictive dashboard capabilities
2. **White-label Option**: Develop enterprise branding customization
3. **API Enhancement**: Expand third-party integration marketplace

## Customer Advisory Board Feedback

Our Customer Advisory Board (12 enterprise customers) provided additional insights:
- Strong interest in AI-powered features for automation
- Request for industry-specific templates and workflows
- Desire for enhanced collaboration tools within platform

## Next Steps

1. Product roadmap review meeting scheduled for October 5th
2. Engineering priorities alignment session with development teams
3. Customer interview program expansion to gather deeper insights

The survey results demonstrate strong customer satisfaction with clear direction for continued improvement. Our focus on user experience and customer support continues to differentiate us in the market.

Please reach out with any questions or requests for deeper analysis of specific feedback areas.

Best regards,

Jennifer Park
Senior Customer Success Manager
customer-success@company.com
Direct: (555) 123-4567

Attachments:
- Detailed Survey Results Q3-2024.xlsx
- Customer Verbatim Comments.pdf
- Competitive Analysis Summary.pdf
"""
    }

    # Create test directory
    test_dir = Path(tempfile.mkdtemp(prefix="enrichment_demo_"))
    print(f"📁 Test directory: {test_dir}")

    # Test the enrichment for each document
    print("\n🧠 Testing LLM Document Enrichment...")

    for filename, content in test_documents.items():
        print(f"\n📄 Processing: {filename}")
        print("-" * 40)

        # Save test file
        test_file = test_dir / filename
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(content)

        # Upload to RAG service for enrichment
        try:
            with open(test_file, 'rb') as f:
                files = {'file': (filename, f, 'text/plain')}
                data = {
                    'document_type': 'text',
                    'process_ocr': 'false',
                    'generate_obsidian': 'true',  # Enable Obsidian generation
                    'enable_enrichment': 'true'   # Enable LLM enrichment
                }

                print(f"  📤 Uploading {filename}...")
                response = requests.post(
                    "http://localhost:8001/ingest/file",
                    files=files,
                    data=data,
                    timeout=60
                )

                if response.status_code == 200:
                    result = response.json()
                    print(f"  ✅ Successfully processed!")
                    print(f"  📊 Document ID: {result.get('document_id', 'N/A')}")
                    print(f"  📈 Processing time: {result.get('processing_time', 'N/A')}s")

                    # Show enrichment preview
                    if 'metadata' in result:
                        metadata = result['metadata']
                        print(f"  📝 Title: {metadata.get('title', 'N/A')}")
                        print(f"  📚 Summary: {metadata.get('summary', 'N/A')[:100]}...")
                        print(f"  🏷️  Tags: {', '.join(metadata.get('tags', [])[:5])}")
                        print(f"  👥 People: {', '.join(metadata.get('people', [])[:3])}")
                        print(f"  🏢 Organizations: {', '.join(metadata.get('organizations', [])[:3])}")
                        print(f"  🔧 Technologies: {', '.join(metadata.get('technologies', [])[:3])}")
                        print(f"  🎯 Complexity: {metadata.get('complexity', 'N/A')}")
                        print(f"  ⏱️  Reading time: {metadata.get('reading_time_minutes', 'N/A')} minutes")

                else:
                    print(f"  ❌ Upload failed: {response.status_code}")
                    print(f"  📋 Error: {response.text}")

        except Exception as e:
            print(f"  ❌ Error: {e}")

    # Test search functionality with enriched metadata
    print(f"\n🔍 Testing Search with Enriched Metadata...")
    print("-" * 40)

    test_queries = [
        "machine learning performance optimization",
        "team meetings and project updates",
        "customer satisfaction survey results",
        "neural architecture search transformers",
        "AWS cloud infrastructure costs"
    ]

    for query in test_queries:
        try:
            print(f"\n🔎 Query: '{query}'")
            response = requests.post(
                "http://localhost:8001/search",
                json={"text": query, "top_k": 3},
                timeout=30
            )

            if response.status_code == 200:
                results = response.json()
                print(f"  📊 Found {len(results.get('results', []))} results")

                for i, result in enumerate(results.get('results', [])[:2], 1):
                    score = result.get('relevance_score', 0)
                    title = result.get('metadata', {}).get('title', 'Untitled')
                    print(f"    {i}. {title} (score: {score:.3f})")

            else:
                print(f"  ❌ Search failed: {response.status_code}")

        except Exception as e:
            print(f"  ❌ Search error: {e}")

    # Test RAG chat with enriched context
    print(f"\n💬 Testing RAG Chat with Enriched Context...")
    print("-" * 40)

    chat_questions = [
        "What are the main findings from the ML infrastructure analysis?",
        "Who are the key team members mentioned in the meeting notes?",
        "What are customers saying about mobile app performance?",
        "What neural architecture search innovations are discussed?",
        "What are the budget implications mentioned in the documents?"
    ]

    for question in chat_questions:
        try:
            print(f"\n❓ Question: {question}")
            response = requests.post(
                "http://localhost:8001/chat",
                json={
                    "question": question,
                    "llm_model": "groq/llama-3.1-8b-instant",
                    "max_context_chunks": 3,
                    "include_sources": True
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                answer = result.get('answer', 'No answer provided')
                sources = result.get('sources', [])

                print(f"  💡 Answer: {answer[:200]}...")
                print(f"  📚 Sources: {len(sources)} documents referenced")

            else:
                print(f"  ❌ Chat failed: {response.status_code}")

        except Exception as e:
            print(f"  ❌ Chat error: {e}")

    print(f"\n🎉 Document Enrichment Demo Complete!")
    print(f"📁 Test files available in: {test_dir}")

    # Show Obsidian vault information
    print(f"\n📝 Obsidian Vault Generation:")
    print(f"  🗂️  Markdown files: /data/obsidian/")
    print(f"  🏷️  Rich frontmatter with hierarchical tags")
    print(f"  🔗 Cross-document links: [[Document Name]]")
    print(f"  📊 Metadata includes: summaries, entities, complexity, reading time")
    print(f"  🔄 Syncable across machines via Obsidian Sync or Git")

if __name__ == "__main__":
    asyncio.run(test_document_enrichment_pipeline())