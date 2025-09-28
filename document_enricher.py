#!/usr/bin/env python3
"""
Advanced Document Enrichment Service

This service uses LLMs to enrich documents with:
- Intelligent summaries and abstracts
- Hierarchical tag taxonomies with controlled vocabularies
- Rich metadata extraction
- Obsidian-style markdown generation with frontmatter
- Cross-document linking and relationship discovery
"""

import asyncio
import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import yaml

from enhanced_llm_service import EnhancedLLMService

logger = logging.getLogger(__name__)

@dataclass
class DocumentMetadata:
    """Comprehensive document metadata structure"""
    title: str
    id: str
    created: str
    modified: str
    file_type: str
    source: str
    summary: str
    abstract: str
    reading_time_minutes: int
    complexity: str  # "basic", "intermediate", "advanced"
    language: str
    word_count: int

    # Hierarchical tags
    tags: List[str]
    categories: List[str]
    topics: List[str]
    subjects: List[str]

    # Entities
    people: List[str]
    organizations: List[str]
    locations: List[str]
    technologies: List[str]
    concepts: List[str]

    # Relationships
    related_documents: List[str]
    references: List[str]
    wiki_links: List[str]

    # Quality metrics
    readability_score: float
    information_density: float
    uniqueness_score: float

class DocumentEnricher:
    """
    Advanced document enrichment using LLMs for intelligent analysis
    and metadata generation with controlled vocabularies
    """

    def __init__(self, llm_service: Optional[EnhancedLLMService] = None):
        self.llm_service = llm_service or EnhancedLLMService()

        # Controlled vocabularies for consistent tagging
        self.controlled_vocabularies = {
            "technologies": [
                "Python", "JavaScript", "Java", "C++", "React", "Node.js", "Docker",
                "Kubernetes", "AWS", "Azure", "Google Cloud", "Machine Learning",
                "Artificial Intelligence", "Deep Learning", "Neural Networks", "NLP",
                "Computer Vision", "Data Science", "Analytics", "Big Data", "Blockchain",
                "Cybersecurity", "DevOps", "CI/CD", "Microservices", "API", "Database",
                "SQL", "NoSQL", "Redis", "MongoDB", "PostgreSQL", "MySQL"
            ],
            "business_areas": [
                "Strategy", "Operations", "Finance", "Marketing", "Sales", "HR",
                "Legal", "Compliance", "Risk Management", "Project Management",
                "Product Management", "Customer Success", "Support", "Training",
                "Research", "Development", "Innovation", "Quality Assurance"
            ],
            "document_types": [
                "Research Paper", "Technical Report", "Meeting Notes", "Email",
                "Chat Log", "Documentation", "Tutorial", "Guide", "Manual",
                "Specification", "Requirements", "Design", "Architecture",
                "Analysis", "Proposal", "Contract", "Policy", "Procedure"
            ],
            "complexity_levels": ["basic", "intermediate", "advanced", "expert"],
            "industry_sectors": [
                "Technology", "Healthcare", "Finance", "Education", "Manufacturing",
                "Retail", "Transportation", "Energy", "Telecommunications",
                "Media", "Real Estate", "Government", "Non-profit"
            ]
        }

    async def enrich_document(
        self,
        content: str,
        filename: str,
        file_type: str,
        existing_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[DocumentMetadata, str]:
        """
        Comprehensively enrich a document with LLM-generated metadata
        and return both metadata and Obsidian-formatted markdown
        """
        logger.info(f"Enriching document: {filename}")

        # Basic metrics
        word_count = len(content.split())
        reading_time = max(1, word_count // 200)  # Average 200 WPM

        # Generate document ID
        doc_id = self._generate_document_id(filename, content)

        # Step 1: Extract basic information and summary
        basic_info = await self._extract_basic_information(content, filename)

        # Step 2: Generate hierarchical tags and categories
        taxonomy = await self._generate_taxonomy(content, basic_info)

        # Step 3: Extract entities and relationships
        entities = await self._extract_entities(content)

        # Step 4: Analyze document quality and complexity
        quality_metrics = await self._analyze_quality(content, word_count)

        # Step 5: Find related concepts and generate links
        relationships = await self._find_relationships(content, basic_info)

        # Create comprehensive metadata
        metadata = DocumentMetadata(
            title=basic_info.get("title", filename),
            id=doc_id,
            created=datetime.now().isoformat(),
            modified=datetime.now().isoformat(),
            file_type=file_type,
            source=filename,
            summary=basic_info.get("summary", ""),
            abstract=basic_info.get("abstract", ""),
            reading_time_minutes=reading_time,
            complexity=quality_metrics.get("complexity", "intermediate"),
            language=basic_info.get("language", "en"),
            word_count=word_count,

            # Hierarchical classification
            tags=taxonomy.get("tags", []),
            categories=taxonomy.get("categories", []),
            topics=taxonomy.get("topics", []),
            subjects=taxonomy.get("subjects", []),

            # Entities
            people=entities.get("people", []),
            organizations=entities.get("organizations", []),
            locations=entities.get("locations", []),
            technologies=entities.get("technologies", []),
            concepts=entities.get("concepts", []),

            # Relationships
            related_documents=relationships.get("related_documents", []),
            references=relationships.get("references", []),
            wiki_links=relationships.get("wiki_links", []),

            # Quality metrics
            readability_score=quality_metrics.get("readability", 0.5),
            information_density=quality_metrics.get("information_density", 0.5),
            uniqueness_score=quality_metrics.get("uniqueness", 0.5)
        )

        # Generate Obsidian markdown
        obsidian_markdown = self._generate_obsidian_markdown(content, metadata)

        logger.info(f"Document enrichment complete for {filename}")
        return metadata, obsidian_markdown

    async def _extract_basic_information(self, content: str, filename: str) -> Dict[str, Any]:
        """Extract title, summary, abstract, and basic document information"""

        # Limit content for LLM processing
        content_sample = content[:4000] if len(content) > 4000 else content

        prompt = f"""
Analyze this document and extract key information.

Document filename: {filename}
Content:
{content_sample}

Provide a JSON response with:
{{
  "title": "Clear, descriptive title for this document",
  "summary": "2-3 sentence summary of the main content",
  "abstract": "Single paragraph abstract highlighting key points and conclusions",
  "language": "en|es|fr|de|etc",
  "primary_topic": "Main subject area",
  "document_purpose": "What this document is intended to accomplish"
}}

JSON Response:"""

        try:
            response = await self.llm_service.call_llm(
                prompt,
                model="groq/llama-3.1-8b-instant",
                max_tokens=500
            )

            # Parse JSON response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                logger.warning("Could not parse basic information JSON")
                return {"title": filename, "summary": "", "abstract": ""}

        except Exception as e:
            logger.error(f"Basic information extraction failed: {e}")
            return {"title": filename, "summary": "", "abstract": ""}

    async def _generate_taxonomy(self, content: str, basic_info: Dict[str, Any]) -> Dict[str, List[str]]:
        """Generate hierarchical tags and categories using controlled vocabularies"""

        content_sample = content[:3000]
        primary_topic = basic_info.get("primary_topic", "")

        prompt = f"""
Create a hierarchical tag taxonomy for this document.

Primary Topic: {primary_topic}
Content Sample:
{content_sample}

Available Technologies: {', '.join(self.controlled_vocabularies['technologies'][:20])}
Available Business Areas: {', '.join(self.controlled_vocabularies['business_areas'][:15])}
Available Document Types: {', '.join(self.controlled_vocabularies['document_types'][:15])}

Generate a JSON response with hierarchical classification:
{{
  "categories": ["broad category 1", "broad category 2"],
  "topics": ["specific topic 1", "specific topic 2", "specific topic 3"],
  "subjects": ["detailed subject 1", "detailed subject 2"],
  "tags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}}

Use only terms from the available vocabularies when possible. Create hierarchical relationships where broader categories contain more specific topics and subjects.

JSON Response:"""

        try:
            response = await self.llm_service.call_llm(
                prompt,
                model="groq/llama-3.1-8b-instant",
                max_tokens=400
            )

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                taxonomy = json.loads(json_match.group())

                # Validate against controlled vocabularies
                return self._validate_taxonomy(taxonomy)
            else:
                return {"categories": [], "topics": [], "subjects": [], "tags": []}

        except Exception as e:
            logger.error(f"Taxonomy generation failed: {e}")
            return {"categories": [], "topics": [], "subjects": [], "tags": []}

    async def _extract_entities(self, content: str) -> Dict[str, List[str]]:
        """Extract people, organizations, locations, technologies, and concepts"""

        content_sample = content[:3000]

        prompt = f"""
Extract entities from this document content:

{content_sample}

Identify and categorize entities into:

JSON Response:
{{
  "people": ["Person Name 1", "Person Name 2"],
  "organizations": ["Company 1", "Organization 2"],
  "locations": ["City 1", "Country 2"],
  "technologies": ["Technology 1", "Tool 2"],
  "concepts": ["Concept 1", "Method 2"]
}}

Only include entities that are explicitly mentioned in the content. Use proper names and standard terminology.

JSON Response:"""

        try:
            response = await self.llm_service.call_llm(
                prompt,
                model="anthropic/claude-3-haiku-20240307",
                max_tokens=400
            )

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                entities = json.loads(json_match.group())

                # Clean and validate entities
                return self._clean_entities(entities)
            else:
                return {"people": [], "organizations": [], "locations": [], "technologies": [], "concepts": []}

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return {"people": [], "organizations": [], "locations": [], "technologies": [], "concepts": []}

    async def _analyze_quality(self, content: str, word_count: int) -> Dict[str, Any]:
        """Analyze document quality, complexity, and information density"""

        content_sample = content[:2000]

        prompt = f"""
Analyze this document for quality metrics:

Content ({word_count} words):
{content_sample}

Evaluate and respond with JSON:
{{
  "complexity": "basic|intermediate|advanced|expert",
  "readability": 0.0-1.0,
  "information_density": 0.0-1.0,
  "uniqueness": 0.0-1.0,
  "technical_depth": "low|medium|high",
  "writing_quality": "poor|fair|good|excellent"
}}

Consider:
- Complexity: vocabulary difficulty, concept sophistication
- Readability: clarity, structure, accessibility
- Information density: knowledge per word, depth of insights
- Uniqueness: novelty, original insights vs common knowledge

JSON Response:"""

        try:
            response = await self.llm_service.call_llm(
                prompt,
                model="anthropic/claude-3-haiku-20240307",
                max_tokens=300
            )

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                quality_data = json.loads(json_match.group())

                # Convert string scores to floats
                for key in ["readability", "information_density", "uniqueness"]:
                    if key in quality_data and isinstance(quality_data[key], str):
                        try:
                            quality_data[key] = float(quality_data[key])
                        except:
                            quality_data[key] = 0.5

                return quality_data
            else:
                return {"complexity": "intermediate", "readability": 0.5, "information_density": 0.5, "uniqueness": 0.5}

        except Exception as e:
            logger.error(f"Quality analysis failed: {e}")
            return {"complexity": "intermediate", "readability": 0.5, "information_density": 0.5, "uniqueness": 0.5}

    async def _find_relationships(self, content: str, basic_info: Dict[str, Any]) -> Dict[str, List[str]]:
        """Find related concepts and generate potential wiki links"""

        title = basic_info.get("title", "")
        primary_topic = basic_info.get("primary_topic", "")

        prompt = f"""
Given this document about "{title}" (topic: {primary_topic}), suggest related concepts and potential document links.

Generate JSON:
{{
  "related_documents": ["Related Topic 1", "Related Topic 2"],
  "references": ["External Resource 1", "Standard 2"],
  "wiki_links": ["[[Concept 1]]", "[[Technology 2]]", "[[Method 3]]"]
}}

Focus on:
- Related documents that might exist in a knowledge base
- External references worth noting
- Wiki-style links for key concepts mentioned

JSON Response:"""

        try:
            response = await self.llm_service.call_llm(
                prompt,
                model="groq/llama-3.1-8b-instant",
                max_tokens=300
            )

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"related_documents": [], "references": [], "wiki_links": []}

        except Exception as e:
            logger.error(f"Relationship finding failed: {e}")
            return {"related_documents": [], "references": [], "wiki_links": []}

    def _validate_taxonomy(self, taxonomy: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Validate taxonomy against controlled vocabularies"""
        validated = {"categories": [], "topics": [], "subjects": [], "tags": []}

        # Validate each category
        for category in taxonomy.get("categories", []):
            if any(cat.lower() in category.lower() for cat in self.controlled_vocabularies["business_areas"]):
                validated["categories"].append(category)

        # Keep other fields as-is for now (could add more validation)
        for key in ["topics", "subjects", "tags"]:
            validated[key] = taxonomy.get(key, [])[:10]  # Limit to 10 items

        return validated

    def _clean_entities(self, entities: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Clean and validate extracted entities"""
        cleaned = {}

        for entity_type, entity_list in entities.items():
            if isinstance(entity_list, list):
                # Remove duplicates, empty strings, and limit to 10
                clean_list = list(set([e.strip() for e in entity_list if e and e.strip()]))[:10]
                cleaned[entity_type] = clean_list
            else:
                cleaned[entity_type] = []

        return cleaned

    def _generate_document_id(self, filename: str, content: str) -> str:
        """Generate a unique document ID"""
        import hashlib

        # Create hash from filename and first 1000 chars of content
        content_sample = content[:1000]
        hash_input = f"{filename}:{content_sample}".encode('utf-8')
        return hashlib.md5(hash_input).hexdigest()[:12]

    def _generate_obsidian_markdown(self, content: str, metadata: DocumentMetadata) -> str:
        """Generate Obsidian-style markdown with rich frontmatter"""

        # Create YAML frontmatter
        frontmatter_data = {
            "title": metadata.title,
            "id": metadata.id,
            "created": metadata.created,
            "modified": metadata.modified,
            "tags": metadata.tags,
            "type": metadata.file_type,
            "source": metadata.source,
            "summary": metadata.summary,
            "abstract": metadata.abstract,
            "classification": {
                "categories": metadata.categories,
                "topics": metadata.topics,
                "subjects": metadata.subjects,
                "complexity": metadata.complexity,
                "reading_time": f"{metadata.reading_time_minutes} minutes"
            },
            "entities": {
                "people": metadata.people,
                "organizations": metadata.organizations,
                "locations": metadata.locations,
                "technologies": metadata.technologies,
                "concepts": metadata.concepts
            },
            "relationships": {
                "related_documents": metadata.related_documents,
                "references": metadata.references
            },
            "metrics": {
                "word_count": metadata.word_count,
                "readability_score": metadata.readability_score,
                "information_density": metadata.information_density,
                "uniqueness_score": metadata.uniqueness_score
            }
        }

        # Generate YAML frontmatter
        frontmatter = yaml.dump(frontmatter_data, default_flow_style=False, allow_unicode=True)

        # Generate markdown content
        markdown = f"""---
{frontmatter}---

# {metadata.title}

## Summary
{metadata.summary}

## Abstract
{metadata.abstract}

## Key Information

**Reading Time:** {metadata.reading_time_minutes} minutes
**Complexity:** {metadata.complexity}
**Word Count:** {metadata.word_count}

### Entities
**People:** {', '.join([f'[[{person}]]' for person in metadata.people[:5]])}
**Organizations:** {', '.join([f'[[{org}]]' for org in metadata.organizations[:5]])}
**Technologies:** {', '.join([f'[[{tech}]]' for tech in metadata.technologies[:5]])}

### Classification
**Categories:** {', '.join(metadata.categories)}
**Topics:** {', '.join(metadata.topics)}
**Subjects:** {', '.join(metadata.subjects)}

## Content

{content}

## Related Notes
{chr(10).join([f'- [[{doc}]]' for doc in metadata.related_documents])}

## References
{chr(10).join([f'- {ref}' for ref in metadata.references])}

## Tags
{' '.join(metadata.tags)}

---
*Document ID: {metadata.id}*
*Source: {metadata.source}*
*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

        return markdown

    async def batch_enrich_documents(
        self,
        documents: List[Tuple[str, str, str]],  # (content, filename, file_type)
        output_dir: Path
    ) -> List[Dict[str, Any]]:
        """Batch process multiple documents for enrichment"""

        logger.info(f"Starting batch enrichment of {len(documents)} documents")
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []

        for i, (content, filename, file_type) in enumerate(documents):
            try:
                logger.info(f"Enriching document {i+1}/{len(documents)}: {filename}")

                # Enrich document
                metadata, obsidian_markdown = await self.enrich_document(
                    content, filename, file_type
                )

                # Save Obsidian markdown
                safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
                markdown_file = output_dir / f"{safe_filename}.md"

                with open(markdown_file, 'w', encoding='utf-8') as f:
                    f.write(obsidian_markdown)

                # Save metadata JSON
                metadata_file = output_dir / f"{safe_filename}_metadata.json"
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(asdict(metadata), f, indent=2, ensure_ascii=False)

                results.append({
                    "filename": filename,
                    "success": True,
                    "metadata": asdict(metadata),
                    "output_files": {
                        "markdown": str(markdown_file),
                        "metadata": str(metadata_file)
                    }
                })

                logger.info(f"Successfully enriched {filename}")

            except Exception as e:
                logger.error(f"Failed to enrich {filename}: {e}")
                results.append({
                    "filename": filename,
                    "success": False,
                    "error": str(e)
                })

        logger.info(f"Batch enrichment complete: {sum(1 for r in results if r['success'])}/{len(documents)} successful")
        return results

# Example usage
async def main():
    """Example usage of the document enricher"""
    enricher = DocumentEnricher()

    # Example document content
    content = """
    Machine Learning in Production Systems

    This document explores the challenges and best practices for deploying machine learning models in production environments. We discuss scalability, monitoring, and maintenance considerations.

    The key challenges include model drift, data quality issues, and infrastructure scaling. Our research shows that proper monitoring can reduce model degradation by 60%.

    Key technologies discussed include Docker, Kubernetes, MLflow, and various cloud platforms like AWS and Azure.
    """

    metadata, markdown = await enricher.enrich_document(
        content,
        "ml_production_guide.txt",
        "text"
    )

    print("Generated Metadata:")
    print(json.dumps(asdict(metadata), indent=2))
    print("\nObsidian Markdown Preview:")
    print(markdown[:1000] + "...")

if __name__ == "__main__":
    asyncio.run(main())