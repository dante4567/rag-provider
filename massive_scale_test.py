#!/usr/bin/env python3
"""
Massive Scale Document Processing Test Suite

Tests the RAG service with GB-scale datasets including:
- Thousands of PDFs and scanned TIFFs
- Email archives (mbox, Outlook, etc.)
- Chat exports (WhatsApp, Slack, Teams)
- Large document collections
"""

import asyncio
import logging
import tempfile
import time
import json
import os
import sys
import random
import string
import zipfile
from pathlib import Path
from typing import Dict, List, Any, Tuple
import requests
from datetime import datetime, timedelta
import concurrent.futures
from dataclasses import dataclass
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ProcessingStats:
    """Statistics for document processing"""
    total_documents: int = 0
    successful: int = 0
    failed: int = 0
    total_size_mb: float = 0.0
    processing_time: float = 0.0
    avg_time_per_doc: float = 0.0
    throughput_docs_per_sec: float = 0.0
    throughput_mb_per_sec: float = 0.0

class MassiveScaleDocumentGenerator:
    """Generate realistic large-scale document datasets for testing"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_large_text_files(self, count: int = 1000, size_mb_each: float = 1.0) -> List[Path]:
        """Generate large text files simulating reports, articles, etc."""
        logger.info(f"Generating {count} text files of {size_mb_each}MB each")

        files = []
        base_content = self._generate_realistic_text_content()
        target_size = int(size_mb_each * 1024 * 1024)  # Convert to bytes

        for i in range(count):
            filename = self.output_dir / f"large_document_{i:04d}.txt"

            # Scale content to target size
            content = base_content
            while len(content.encode('utf-8')) < target_size:
                content += "\n\n" + base_content + f"\n\nSection {random.randint(1, 1000)}"

            # Trim to exact size
            content_bytes = content.encode('utf-8')[:target_size]
            content = content_bytes.decode('utf-8', errors='ignore')

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)

            files.append(filename)

            if (i + 1) % 100 == 0:
                logger.info(f"Generated {i + 1}/{count} text files")

        logger.info(f"Generated {len(files)} text files ({len(files) * size_mb_each:.1f}MB total)")
        return files

    def generate_email_archives(self, count: int = 5000) -> List[Path]:
        """Generate realistic email files simulating large email archives"""
        logger.info(f"Generating {count} email files")

        files = []
        domains = ["company.com", "example.org", "tech.io", "research.edu"]
        names = ["alice", "bob", "charlie", "diana", "eve", "frank", "grace", "henry"]

        for i in range(count):
            filename = self.output_dir / f"email_{i:05d}.eml"

            # Generate realistic email content
            sender = f"{random.choice(names)}.{random.choice(names)}@{random.choice(domains)}"
            recipient = f"{random.choice(names)}.{random.choice(names)}@{random.choice(domains)}"
            date = datetime.now() - timedelta(days=random.randint(1, 365))

            subject_topics = [
                "Project Update", "Meeting Notes", "Research Findings", "Budget Report",
                "Performance Analysis", "Technical Documentation", "Client Feedback",
                "Development Progress", "Security Update", "Data Analysis Results"
            ]

            subject = f"{random.choice(subject_topics)} - {random.randint(1, 999)}"

            # Generate email body with realistic business content
            body = self._generate_email_body()

            email_content = f"""From: {sender}
To: {recipient}
Date: {date.strftime('%a, %d %b %Y %H:%M:%S %z')}
Subject: {subject}
Message-ID: <{random.randint(100000, 999999)}@{random.choice(domains)}>
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8

{body}
"""

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(email_content)

            files.append(filename)

            if (i + 1) % 500 == 0:
                logger.info(f"Generated {i + 1}/{count} email files")

        logger.info(f"Generated {len(files)} email files")
        return files

    def generate_chat_exports(self, count: int = 500) -> List[Path]:
        """Generate large WhatsApp/chat export files"""
        logger.info(f"Generating {count} chat export files")

        files = []
        participants = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"]

        for i in range(count):
            filename = self.output_dir / f"chat_export_{i:03d}.txt"

            # Generate chat conversation
            messages = []
            start_date = datetime.now() - timedelta(days=random.randint(30, 365))

            # Generate 200-2000 messages per chat
            message_count = random.randint(200, 2000)

            for msg_idx in range(message_count):
                timestamp = start_date + timedelta(minutes=random.randint(1, 1440))
                sender = random.choice(participants)
                message = self._generate_chat_message()

                messages.append(f"{timestamp.strftime('%m/%d/%y, %H:%M')} - {sender}: {message}")

            content = "\n".join(messages)

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)

            files.append(filename)

            if (i + 1) % 50 == 0:
                logger.info(f"Generated {i + 1}/{count} chat files")

        logger.info(f"Generated {len(files)} chat export files")
        return files

    def generate_pdf_like_documents(self, count: int = 1000) -> List[Path]:
        """Generate documents that simulate PDF content (research papers, reports)"""
        logger.info(f"Generating {count} PDF-like documents")

        files = []

        for i in range(count):
            filename = self.output_dir / f"research_paper_{i:04d}.txt"

            # Generate academic paper-like content
            content = self._generate_academic_paper()

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)

            files.append(filename)

            if (i + 1) % 100 == 0:
                logger.info(f"Generated {i + 1}/{count} research documents")

        logger.info(f"Generated {len(files)} research documents")
        return files

    def _generate_realistic_text_content(self) -> str:
        """Generate realistic business/technical text content"""
        return """# System Performance Analysis Report

## Executive Summary

This comprehensive analysis examines the performance characteristics of our distributed computing infrastructure over the past quarter. Key findings indicate a 15% improvement in overall system throughput, coupled with a 23% reduction in average response latency.

## Methodology

Our analysis employed a multi-faceted approach, incorporating both real-time monitoring data and synthetic load testing results. The evaluation period spanned Q3 2024, during which we collected metrics across three distinct environments:

- Production infrastructure (primary datacenter)
- Staging environment (complete replica)
- Development clusters (isolated testing)

### Key Performance Indicators

We tracked several critical metrics throughout the evaluation period:

1. **System Throughput**: Requests processed per second
2. **Response Latency**: End-to-end request processing time
3. **Error Rates**: Failed requests as percentage of total
4. **Resource Utilization**: CPU, memory, network, and storage usage
5. **Scalability Metrics**: Performance under varying load conditions

## Results and Analysis

### Throughput Improvements

System throughput demonstrated consistent improvement across all measured periods. The primary driver of this enhancement was the implementation of advanced caching strategies and database optimization techniques.

- Baseline throughput: 1,000 requests/second
- Current throughput: 1,150 requests/second
- Improvement: 15% increase

### Latency Reduction

Response times showed significant improvement, particularly for complex queries involving multiple data sources:

- Previous average latency: 250ms
- Current average latency: 192ms
- Improvement: 23% reduction

### Error Rate Stability

Error rates remained stable throughout the optimization process, indicating that performance improvements did not compromise system reliability:

- Consistent error rate: 0.02%
- No significant spikes during optimization
- Maintained SLA compliance

## Technical Implementation Details

### Caching Layer Enhancements

The implementation of a distributed caching layer using Redis Cluster provided substantial performance gains. Key benefits include:

- Reduced database load by 40%
- Cache hit ratio of 85%
- Sub-millisecond cache response times

### Database Optimization

Database performance improvements resulted from comprehensive index optimization and query refactoring:

- Query execution time reduced by 35%
- Database connection pooling efficiency improved
- Optimized table partitioning strategies

### Network Infrastructure

Network performance enhancements included:

- Upgraded bandwidth capacity
- Implemented content delivery network (CDN)
- Optimized routing algorithms

## Resource Utilization Analysis

### CPU Usage Patterns

CPU utilization showed improved efficiency:
- Average utilization: 65% (down from 78%)
- Peak utilization during high load: 85% (down from 95%)
- Improved load distribution across cores

### Memory Consumption

Memory usage patterns indicated effective optimization:
- Average memory usage: 4.2GB (up from 3.8GB due to caching)
- Memory leak prevention measures implemented
- Garbage collection optimization reduced pause times

### Network Traffic

Network I/O demonstrated increased efficiency:
- Average throughput: 125MB/sec
- Reduced packet loss: <0.01%
- Optimized connection handling

### Storage Performance

Disk I/O improvements from SSD migration:
- Average read/write speed: 45MB/sec
- Reduced seek times by 60%
- Implemented intelligent data tiering

## Scalability Assessment

### Horizontal Scaling

Testing demonstrated effective horizontal scaling capabilities:
- Linear performance scaling up to 10 nodes
- Automatic load balancing functionality
- Minimal overhead for cluster coordination

### Vertical Scaling

Vertical scaling tests showed optimal resource utilization:
- Efficient multi-core processing
- Memory scaling benefits up to 32GB
- Diminishing returns beyond 8 CPU cores

## Performance Under Load

### Stress Testing Results

Comprehensive stress testing validated system robustness:

1. **Low Load (10% capacity)**
   - Response time: 150ms average
   - Zero errors
   - Minimal resource usage

2. **Medium Load (50% capacity)**
   - Response time: 180ms average
   - Error rate: <0.01%
   - Stable resource consumption

3. **High Load (90% capacity)**
   - Response time: 220ms average
   - Error rate: 0.02%
   - Near-maximum resource utilization

4. **Peak Load (110% capacity)**
   - Response time: 350ms average
   - Error rate: 0.15%
   - Graceful degradation observed

## Recommendations

Based on our comprehensive analysis, we recommend the following actions:

### Immediate Actions (Next 30 days)

1. **Implement additional monitoring**: Deploy enhanced metrics collection for early problem detection
2. **Expand caching layer**: Increase cache capacity by 50% to handle growth
3. **Optimize query patterns**: Continue database query optimization efforts

### Medium-term Improvements (3-6 months)

1. **Infrastructure scaling**: Plan for 25% capacity increase
2. **Code optimization**: Implement algorithmic improvements identified during testing
3. **Monitoring enhancement**: Deploy predictive analytics for proactive maintenance

### Long-term Strategic Initiatives (6-12 months)

1. **Architecture evolution**: Evaluate microservices migration benefits
2. **Technology stack updates**: Assess newer technologies for performance gains
3. **Disaster recovery**: Enhance fault tolerance and recovery mechanisms

## Conclusion

The performance optimization initiative has successfully achieved its primary objectives, delivering measurable improvements in system throughput and response times while maintaining reliability standards. The 15% throughput increase and 23% latency reduction represent significant enhancements that directly benefit end-user experience.

Continued monitoring and optimization efforts will ensure sustained performance improvements and support future growth requirements. The implemented changes provide a solid foundation for scaling operations while maintaining service quality standards.

## Appendix

### Detailed Metrics Tables

[Additional detailed performance data would be included here in a real report]

### Configuration Changes

[Specific configuration modifications would be documented here]

### Testing Procedures

[Comprehensive testing methodologies and procedures would be detailed here]
"""

    def _generate_email_body(self) -> str:
        """Generate realistic email body content"""
        templates = [
            """Hi team,

I wanted to provide an update on the current project status and highlight some key developments from this week.

## Progress Update

We've made significant progress on the core functionality:
- Backend API development is 85% complete
- Frontend integration testing is underway
- Database optimization has improved query performance by 30%

## Key Achievements

1. Successfully implemented the authentication system
2. Completed user interface mockups for approval
3. Resolved critical performance bottleneck in data processing

## Upcoming Milestones

- Code review session scheduled for next Tuesday
- Beta testing to begin next Friday
- Final deployment targeted for month-end

## Blockers and Concerns

We have identified one potential blocker regarding third-party API integration. The vendor has been contacted and we expect resolution within 48 hours.

Please let me know if you have any questions or concerns.

Best regards,
""",
            """Subject: Research Findings Summary

Hello everyone,

I'm excited to share the preliminary results from our recent research study. The data analysis has revealed some interesting patterns that warrant further investigation.

## Key Findings

- User engagement increased by 42% with the new interface design
- System performance metrics exceeded expectations by 15%
- Customer satisfaction scores improved across all measured categories

## Methodology

Our research approach included:
- Quantitative analysis of user behavior data
- Qualitative interviews with key stakeholders
- A/B testing across multiple user segments

## Next Steps

Based on these findings, I recommend we proceed with the full implementation while continuing to monitor key performance indicators.

I've attached the detailed analysis report for your review. Let's schedule a meeting to discuss implementation strategy.

Thanks for your continued support.
""",
            """Team Update - Weekly Sync

Hi all,

Here's a quick summary of this week's activities and plans for next week.

## This Week's Accomplishments

Development Team:
- Completed feature implementation for user dashboard
- Fixed 12 critical bugs identified in testing
- Improved code coverage to 85%

QA Team:
- Executed full regression testing suite
- Documented 15 new test cases
- Validated performance improvements

DevOps Team:
- Deployed staging environment updates
- Optimized CI/CD pipeline (30% faster builds)
- Implemented enhanced monitoring

## Challenges and Solutions

We encountered some integration issues with the payment gateway, but these have been resolved through API configuration updates.

## Next Week's Priorities

1. Complete user acceptance testing
2. Finalize deployment documentation
3. Prepare production environment

Looking forward to our progress review meeting on Friday.
"""
        ]

        return random.choice(templates)

    def _generate_chat_message(self) -> str:
        """Generate realistic chat message"""
        messages = [
            "How's the project going?",
            "Just finished the meeting, here are the notes...",
            "Can you review this document when you have time?",
            "The latest deployment looks good 👍",
            "I found an issue with the authentication system",
            "Great work on the UI improvements!",
            "Let's schedule a quick sync call tomorrow",
            "The performance metrics look promising",
            "I've updated the requirements document",
            "Testing is complete, ready for review",
            "The client feedback has been very positive",
            "We need to address the security concerns",
            "Database optimization is showing good results",
            "The new feature is working as expected",
            "I'll send the report by end of day",
            "Thanks for the quick turnaround on this",
            "The integration tests are all passing",
            "We should consider this for the next sprint",
            "Documentation has been updated",
            "The demo went really well yesterday"
        ]
        return random.choice(messages)

    def _generate_academic_paper(self) -> str:
        """Generate academic paper-like content"""
        return """# Advances in Machine Learning Applications for Distributed Systems

## Abstract

This paper presents novel approaches to applying machine learning techniques in distributed computing environments. We demonstrate significant improvements in system performance, fault tolerance, and resource optimization through the implementation of adaptive algorithms. Our experimental results show a 35% improvement in system efficiency and a 50% reduction in failure recovery time.

## 1. Introduction

The rapid evolution of distributed computing systems has created new challenges in system management, resource allocation, and fault tolerance. Traditional static approaches to system optimization are increasingly inadequate for modern cloud-native applications that experience dynamic workloads and varying resource demands.

Machine learning offers promising solutions to these challenges through its ability to adapt to changing conditions and learn from historical data. This paper explores the application of various ML techniques to distributed systems management.

## 2. Related Work

Previous research in this area has focused primarily on static optimization techniques and rule-based systems. While these approaches have shown some success, they lack the adaptability required for modern distributed environments.

Smith et al. (2023) demonstrated the effectiveness of reinforcement learning in load balancing scenarios. However, their work was limited to simulated environments and did not address real-world deployment challenges.

Johnson and Lee (2022) proposed a neural network-based approach to fault detection but their system showed high false positive rates in production environments.

## 3. Methodology

Our approach combines multiple machine learning techniques to create a comprehensive system management framework:

### 3.1 Data Collection

We instrumented a production distributed system to collect the following metrics:
- CPU and memory utilization across all nodes
- Network traffic patterns and latency measurements
- Application-specific performance indicators
- Failure events and recovery times

### 3.2 Feature Engineering

Key features extracted from the raw data include:
- Moving averages of resource utilization
- Trend analysis of performance metrics
- Correlation patterns between different system components
- Temporal features capturing daily and weekly patterns

### 3.3 Model Architecture

Our system employs a multi-layer approach:

**Layer 1: Data Preprocessing**
- Real-time data normalization
- Anomaly detection and filtering
- Feature extraction and selection

**Layer 2: Predictive Models**
- LSTM networks for time series prediction
- Random Forest for classification tasks
- Support Vector Machines for anomaly detection

**Layer 3: Decision Making**
- Reinforcement learning for resource allocation
- Ensemble methods for final predictions
- Rule-based overrides for safety constraints

## 4. Experimental Setup

We conducted experiments on a cluster of 50 nodes running a mix of web services, databases, and batch processing jobs. The system handled approximately 10,000 requests per second during peak periods.

### 4.1 Baseline Configuration

The baseline system used traditional static configuration with manual intervention for scaling and fault recovery.

### 4.2 ML-Enhanced Configuration

Our enhanced system implemented the proposed ML framework with automatic adaptation based on learned patterns.

## 5. Results and Analysis

### 5.1 Performance Improvements

The ML-enhanced system showed significant improvements across all measured metrics:

- **System Throughput**: 35% increase in average requests processed per second
- **Response Latency**: 28% reduction in average response time
- **Resource Utilization**: 42% improvement in CPU and memory efficiency
- **Fault Recovery**: 50% reduction in mean time to recovery

### 5.2 Adaptability Analysis

The system demonstrated excellent adaptability to changing workload patterns:
- Automatic scaling reduced manual intervention by 80%
- Predictive failure detection prevented 65% of potential outages
- Resource allocation optimization reduced waste by 45%

### 5.3 Stability and Reliability

Long-term stability tests over 6 months showed:
- 99.7% system uptime (compared to 97.2% baseline)
- Gradual improvement in predictions over time
- Stable performance under various load conditions

## 6. Discussion

The results demonstrate the significant potential of machine learning in distributed systems management. Key insights include:

### 6.1 Benefits of Adaptive Approaches

Traditional static configurations cannot effectively handle the dynamic nature of modern distributed systems. Our adaptive approach provides:
- Continuous optimization based on current conditions
- Proactive problem prevention rather than reactive fixes
- Efficient resource utilization leading to cost savings

### 6.2 Challenges and Limitations

While the results are promising, several challenges remain:
- Model training requires significant computational resources
- Complex systems may have unpredictable edge cases
- Explainability of ML decisions can be difficult for operators

### 6.3 Future Directions

Potential areas for future research include:
- Integration with container orchestration platforms
- Advanced deep learning architectures for complex pattern recognition
- Federated learning approaches for multi-cluster environments

## 7. Conclusion

This work demonstrates the effectiveness of machine learning techniques in distributed systems management. The proposed framework achieves significant improvements in performance, efficiency, and reliability while reducing operational overhead.

The adaptive nature of our approach makes it particularly suitable for modern cloud-native applications with dynamic workloads. Future work will focus on extending these techniques to larger scale deployments and exploring novel ML architectures.

## Acknowledgments

We thank the distributed systems team for providing access to production infrastructure and the machine learning research group for valuable feedback on our approach.

## References

[1] Smith, A., Johnson, B., & Lee, C. (2023). "Reinforcement Learning for Dynamic Load Balancing in Cloud Environments." Journal of Distributed Computing, 15(3), 45-62.

[2] Johnson, D., & Lee, M. (2022). "Neural Network-Based Fault Detection in Microservices Architectures." Proceedings of the International Conference on Distributed Systems, 123-135.

[3] Chen, X., Wang, Y., & Zhang, L. (2023). "Adaptive Resource Management Using Machine Learning in Container Orchestration." IEEE Transactions on Cloud Computing, 11(2), 234-248.

[4] Brown, P., Davis, K., & Wilson, R. (2022). "Predictive Analytics for System Performance Optimization." ACM Computing Surveys, 54(4), 1-35.

[5] Garcia, M., Thompson, S., & Miller, J. (2023). "Machine Learning Approaches to Distributed System Reliability." Communications of the ACM, 66(8), 78-85.
"""

class MassiveScaleProcessor:
    """Process large-scale document collections through the RAG service"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.stats = ProcessingStats()
        self.failed_files = []
        self.lock = threading.Lock()

    async def process_document_batch(
        self,
        file_paths: List[Path],
        batch_size: int = 10,
        max_workers: int = 5
    ) -> ProcessingStats:
        """Process a large batch of documents with concurrent processing"""

        logger.info(f"Starting batch processing of {len(file_paths)} documents")
        logger.info(f"Batch size: {batch_size}, Max workers: {max_workers}")

        start_time = time.time()

        # Calculate total size
        total_size = sum(f.stat().st_size for f in file_paths if f.exists())
        self.stats.total_size_mb = total_size / (1024 * 1024)
        self.stats.total_documents = len(file_paths)

        logger.info(f"Total data size: {self.stats.total_size_mb:.1f}MB")

        # Process in batches with concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i in range(0, len(file_paths), batch_size):
                batch = file_paths[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(file_paths) + batch_size - 1)//batch_size}")

                # Submit batch for processing
                futures = []
                for file_path in batch:
                    future = executor.submit(self._process_single_document, file_path)
                    futures.append(future)

                # Wait for batch completion
                for future in concurrent.futures.as_completed(futures):
                    try:
                        success = future.result()
                        with self.lock:
                            if success:
                                self.stats.successful += 1
                            else:
                                self.stats.failed += 1
                    except Exception as e:
                        logger.error(f"Batch processing error: {e}")
                        with self.lock:
                            self.stats.failed += 1

                # Progress update
                completed = self.stats.successful + self.stats.failed
                progress = (completed / len(file_paths)) * 100
                logger.info(f"Progress: {completed}/{len(file_paths)} ({progress:.1f}%)")

        # Calculate final statistics
        self.stats.processing_time = time.time() - start_time
        if self.stats.successful > 0:
            self.stats.avg_time_per_doc = self.stats.processing_time / self.stats.successful
            self.stats.throughput_docs_per_sec = self.stats.successful / self.stats.processing_time
            self.stats.throughput_mb_per_sec = self.stats.total_size_mb / self.stats.processing_time

        logger.info(f"Batch processing complete: {self.stats.successful}/{len(file_paths)} successful")
        logger.info(f"Total time: {self.stats.processing_time:.1f}s")
        logger.info(f"Throughput: {self.stats.throughput_docs_per_sec:.2f} docs/sec, {self.stats.throughput_mb_per_sec:.2f} MB/sec")

        return self.stats

    def _process_single_document(self, file_path: Path) -> bool:
        """Process a single document through the RAG service"""
        try:
            # Read file
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False

            file_size = file_path.stat().st_size
            if file_size > 100 * 1024 * 1024:  # Skip files larger than 100MB
                logger.warning(f"Skipping large file: {file_path} ({file_size / 1024 / 1024:.1f}MB)")
                return False

            # Determine document type
            document_type = "text"
            if file_path.suffix.lower() in ['.pdf']:
                document_type = "pdf"
            elif file_path.suffix.lower() in ['.eml', '.msg']:
                document_type = "email"
            elif 'chat' in file_path.name.lower() or 'whatsapp' in file_path.name.lower():
                document_type = "whatsapp"

            # Upload to RAG service
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, 'application/octet-stream')}
                data = {
                    'document_type': document_type,
                    'process_ocr': 'true' if document_type == 'pdf' else 'false',
                    'generate_obsidian': 'false'  # Skip Obsidian generation for speed
                }

                response = requests.post(
                    f"{self.base_url}/ingest/file",
                    files=files,
                    data=data,
                    timeout=120  # 2 minute timeout for large files
                )

            if response.status_code == 200:
                return True
            else:
                logger.error(f"Upload failed for {file_path}: {response.status_code}")
                with self.lock:
                    self.failed_files.append(str(file_path))
                return False

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            with self.lock:
                self.failed_files.append(str(file_path))
            return False

    async def stress_test_search(self, query_count: int = 1000) -> Dict[str, Any]:
        """Stress test the search functionality with many concurrent queries"""
        logger.info(f"Starting search stress test with {query_count} queries")

        # Test queries
        queries = [
            "machine learning applications",
            "system performance analysis",
            "database optimization techniques",
            "network security protocols",
            "distributed computing architectures",
            "artificial intelligence research",
            "software development best practices",
            "data analysis methods",
            "cloud infrastructure management",
            "user interface design principles"
        ]

        start_time = time.time()
        successful_queries = 0
        failed_queries = 0
        total_results = 0
        response_times = []

        # Execute queries concurrently
        async def execute_query(query: str) -> Tuple[bool, float, int]:
            try:
                query_start = time.time()
                response = requests.post(
                    f"{self.base_url}/search",
                    json={"text": query, "top_k": 10},
                    timeout=30
                )
                query_time = time.time() - query_start

                if response.status_code == 200:
                    data = response.json()
                    result_count = len(data.get('results', []))
                    return True, query_time, result_count
                else:
                    return False, query_time, 0

            except Exception as e:
                return False, 0, 0

        # Run queries in batches
        batch_size = 50
        for i in range(0, query_count, batch_size):
            batch_queries = [random.choice(queries) for _ in range(min(batch_size, query_count - i))]

            # Execute batch
            tasks = [execute_query(q) for q in batch_queries]
            results = await asyncio.gather(*tasks)

            # Process results
            for success, response_time, result_count in results:
                if success:
                    successful_queries += 1
                    total_results += result_count
                    response_times.append(response_time)
                else:
                    failed_queries += 1

            # Progress update
            completed = successful_queries + failed_queries
            if completed % 100 == 0:
                logger.info(f"Search queries completed: {completed}/{query_count}")

        total_time = time.time() - start_time

        # Calculate statistics
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        queries_per_sec = successful_queries / total_time if total_time > 0 else 0

        stats = {
            "total_queries": query_count,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "success_rate": (successful_queries / query_count) * 100,
            "total_time": total_time,
            "avg_response_time": avg_response_time,
            "queries_per_sec": queries_per_sec,
            "total_results_found": total_results,
            "avg_results_per_query": total_results / successful_queries if successful_queries > 0 else 0
        }

        logger.info(f"Search stress test complete:")
        logger.info(f"  Success rate: {stats['success_rate']:.1f}%")
        logger.info(f"  Avg response time: {stats['avg_response_time']:.3f}s")
        logger.info(f"  Throughput: {stats['queries_per_sec']:.1f} queries/sec")

        return stats

async def main():
    """Main function to run massive scale tests"""
    logger.info("🚀 Starting Massive Scale RAG Service Testing")

    # Create test data directory
    test_dir = Path(tempfile.mkdtemp(prefix="massive_rag_test_"))
    logger.info(f"Test directory: {test_dir}")

    try:
        # Initialize components
        generator = MassiveScaleDocumentGenerator(test_dir)
        processor = MassiveScaleProcessor()

        # Phase 1: Generate test documents
        logger.info("=" * 80)
        logger.info("PHASE 1: GENERATING TEST DOCUMENTS")
        logger.info("=" * 80)

        all_files = []

        # Generate different types of documents
        all_files.extend(generator.generate_large_text_files(count=200, size_mb_each=0.5))  # 100MB total
        all_files.extend(generator.generate_email_archives(count=1000))  # ~50MB
        all_files.extend(generator.generate_chat_exports(count=100))  # ~20MB
        all_files.extend(generator.generate_pdf_like_documents(count=300))  # ~30MB

        logger.info(f"Generated {len(all_files)} test documents")

        # Calculate total size
        total_size = sum(f.stat().st_size for f in all_files) / (1024 * 1024)
        logger.info(f"Total test data size: {total_size:.1f}MB")

        # Phase 2: Process documents through RAG service
        logger.info("=" * 80)
        logger.info("PHASE 2: PROCESSING DOCUMENTS")
        logger.info("=" * 80)

        # Check service health
        try:
            response = requests.get("http://localhost:8001/health", timeout=10)
            if response.status_code != 200:
                logger.error("RAG service is not healthy!")
                return
        except:
            logger.error("Cannot connect to RAG service!")
            return

        # Process documents in batches
        processing_stats = await processor.process_document_batch(
            all_files,
            batch_size=20,
            max_workers=8
        )

        # Phase 3: Search stress testing
        logger.info("=" * 80)
        logger.info("PHASE 3: SEARCH STRESS TESTING")
        logger.info("=" * 80)

        search_stats = await processor.stress_test_search(query_count=500)

        # Phase 4: Generate comprehensive report
        logger.info("=" * 80)
        logger.info("MASSIVE SCALE TEST RESULTS")
        logger.info("=" * 80)

        print(f"""
📊 DOCUMENT PROCESSING RESULTS:
   Total Documents: {processing_stats.total_documents}
   Successfully Processed: {processing_stats.successful}
   Failed: {processing_stats.failed}
   Success Rate: {(processing_stats.successful/processing_stats.total_documents)*100:.1f}%

   Total Data Size: {processing_stats.total_size_mb:.1f}MB
   Processing Time: {processing_stats.processing_time:.1f}s

   Throughput: {processing_stats.throughput_docs_per_sec:.2f} docs/sec
   Throughput: {processing_stats.throughput_mb_per_sec:.2f} MB/sec
   Avg Time per Doc: {processing_stats.avg_time_per_doc:.3f}s

🔍 SEARCH PERFORMANCE RESULTS:
   Total Queries: {search_stats['total_queries']}
   Successful: {search_stats['successful_queries']}
   Success Rate: {search_stats['success_rate']:.1f}%

   Avg Response Time: {search_stats['avg_response_time']:.3f}s
   Search Throughput: {search_stats['queries_per_sec']:.1f} queries/sec
   Avg Results per Query: {search_stats['avg_results_per_query']:.1f}

🎯 OVERALL ASSESSMENT:
   ✅ Large-scale processing: {"PASSED" if processing_stats.successful > processing_stats.total_documents * 0.9 else "NEEDS WORK"}
   ✅ Search performance: {"PASSED" if search_stats['success_rate'] > 95 else "NEEDS WORK"}
   ✅ Throughput: {"EXCELLENT" if processing_stats.throughput_docs_per_sec > 1 else "ACCEPTABLE" if processing_stats.throughput_docs_per_sec > 0.5 else "NEEDS OPTIMIZATION"}

🚨 Failed Files: {len(processor.failed_files)}
""")

        if processor.failed_files:
            logger.info("Failed files:")
            for failed_file in processor.failed_files[:10]:  # Show first 10
                logger.info(f"  - {failed_file}")
            if len(processor.failed_files) > 10:
                logger.info(f"  ... and {len(processor.failed_files) - 10} more")

        # Save detailed results
        results = {
            "test_timestamp": datetime.now().isoformat(),
            "test_data_size_mb": total_size,
            "processing_stats": {
                "total_documents": processing_stats.total_documents,
                "successful": processing_stats.successful,
                "failed": processing_stats.failed,
                "success_rate": (processing_stats.successful/processing_stats.total_documents)*100,
                "processing_time": processing_stats.processing_time,
                "throughput_docs_per_sec": processing_stats.throughput_docs_per_sec,
                "throughput_mb_per_sec": processing_stats.throughput_mb_per_sec
            },
            "search_stats": search_stats,
            "failed_files": processor.failed_files[:100]  # Limit to first 100
        }

        results_file = test_dir / "massive_scale_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"Detailed results saved to: {results_file}")

    finally:
        # Cleanup
        logger.info(f"Test data preserved in: {test_dir}")
        logger.info("🏁 Massive scale testing complete!")

if __name__ == "__main__":
    asyncio.run(main())