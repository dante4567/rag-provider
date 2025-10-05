"""
Enhanced Metadata Generator for RAG Provider
Generates rich, hierarchical, Obsidian-compatible metadata
"""

import hashlib
import yaml
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TaxonomyManager:
    """Manages hierarchical tag taxonomy"""

    def __init__(self, taxonomy_file: str = "/config/taxonomy.yaml"):
        self.taxonomy_file = Path(taxonomy_file)
        self.taxonomy = self._load_taxonomy()
        self.mapping_rules = self.taxonomy.get('mapping_rules', {})
        self.tag_rules = self.taxonomy.get('tag_rules', {})

    def _load_taxonomy(self) -> Dict:
        """Load taxonomy from YAML file"""
        try:
            if self.taxonomy_file.exists():
                with open(self.taxonomy_file, 'r') as f:
                    return yaml.safe_load(f)
            else:
                logger.warning(f"Taxonomy file not found: {self.taxonomy_file}")
                return {}
        except Exception as e:
            logger.error(f"Error loading taxonomy: {e}")
            return {}

    def generate_hierarchical_tags(
        self,
        entities: Dict[str, List],
        classification: Dict,
        source_file: str,
        content: str
    ) -> List[str]:
        """Generate hierarchical tags from entities and classification"""

        tags = []

        # 1. Map classification to taxonomy
        category_tags = self._map_classification_to_tags(classification)
        tags.extend(category_tags)

        # 2. Map technologies to tags
        tech_tags = self._map_technologies_to_tags(entities.get('technologies', []))
        tags.extend(tech_tags)

        # 3. Pattern-based tagging
        pattern_tags = self._map_patterns_to_tags(content)
        tags.extend(pattern_tags)

        # 4. File type tagging
        file_type_tags = self._map_file_type_to_tags(source_file)
        tags.extend(file_type_tags)

        # 5. Add temporal tags
        if self.tag_rules.get('always_add_temporal', True):
            temporal_tags = self._generate_temporal_tags()
            tags.extend(temporal_tags)

        # 6. Add location tags if detected
        if self.tag_rules.get('add_location_tags', True) and entities.get('locations'):
            location_tags = self._map_locations_to_tags(entities['locations'])
            tags.extend(location_tags)

        # 7. Remove duplicates and limit
        tags = list(dict.fromkeys(tags))  # Preserve order, remove dupes
        max_tags = self.tag_rules.get('max_tags_per_document', 10)
        tags = tags[:max_tags]

        return tags

    def _map_classification_to_tags(self, classification: Dict) -> List[str]:
        """Map classification categories to hierarchical tags"""
        tags = []

        categories = classification.get('categories', [])
        topics = classification.get('topics', [])

        # Try to build hierarchical path
        if categories and topics:
            category = self._normalize_tag(categories[0])
            topic = self._normalize_tag(topics[0])

            # Look up in taxonomy
            if category in self.taxonomy.get('taxonomy', {}):
                cat_section = self.taxonomy['taxonomy'][category]

                # Find matching topic in category
                for topic_key in cat_section.keys():
                    if topic_key in topic or topic in topic_key:
                        tags.append(f"{category}/{topic_key}")
                        break
                else:
                    # No exact match, use generic
                    tags.append(f"{category}/{topic}")

        return tags

    def _map_technologies_to_tags(self, technologies: List[str]) -> List[str]:
        """Map technology names to taxonomy tags"""
        tags = []

        tech_mapping = self.mapping_rules.get('technologies', {})

        for tech in technologies:
            if tech in tech_mapping:
                tags.append(tech_mapping[tech])
            else:
                # Default: tech/other
                tags.append(f"tech/other/{self._normalize_tag(tech)}")

        return tags

    def _map_patterns_to_tags(self, content: str) -> List[str]:
        """Pattern-based tagging from content"""
        tags = []

        patterns = self.mapping_rules.get('patterns', [])

        for pattern_rule in patterns:
            pattern = pattern_rule.get('pattern', '')
            pattern_tags = pattern_rule.get('tags', [])

            if re.search(pattern, content, re.IGNORECASE):
                tags.extend(pattern_tags)

        return tags

    def _map_file_type_to_tags(self, filename: str) -> List[str]:
        """Map file extension to type tags"""
        tags = []

        file_types = self.mapping_rules.get('file_types', {})
        ext = Path(filename).suffix.lower()

        if ext in file_types:
            tags.append(file_types[ext])

        return tags

    def _generate_temporal_tags(self) -> List[str]:
        """Generate time-based tags"""
        now = datetime.now()

        tags = [
            f"time/{now.year}",
            f"time/{now.year}/Q{(now.month-1)//3+1}",
        ]

        return tags

    def _map_locations_to_tags(self, locations: List[str]) -> List[str]:
        """Map location entities to geography tags"""
        tags = []

        for location in locations:
            location_norm = self._normalize_tag(location)

            # Check if in taxonomy
            loc_taxonomy = self.taxonomy.get('taxonomy', {}).get('location', {})

            for region, region_data in loc_taxonomy.items():
                if isinstance(region_data, dict):
                    for key, values in region_data.items():
                        if location_norm in [self._normalize_tag(v) for v in values]:
                            tags.append(f"location/{region}/{location_norm}")
                            break

        return tags

    def _normalize_tag(self, text: str) -> str:
        """Normalize text for tag format"""
        # Convert to lowercase
        text = text.lower()

        # Replace spaces and special chars with hyphens
        text = re.sub(r'[^a-z0-9]+', '-', text)

        # Remove leading/trailing hyphens
        text = text.strip('-')

        return text


class EnhancedMetadataGenerator:
    """Generates enhanced metadata for documents"""

    def __init__(self, taxonomy_manager: TaxonomyManager):
        self.taxonomy = taxonomy_manager

    def generate_file_hash(self, file_path: Path) -> Dict[str, Any]:
        """Generate SHA256 hash of file"""
        try:
            sha256 = hashlib.sha256()

            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)

            return {
                'original_file': file_path.name,
                'file_hash': f"sha256:{sha256.hexdigest()}",
                'file_size': file_path.stat().st_size,
                'file_type': file_path.suffix.lower()
            }
        except Exception as e:
            logger.error(f"Error hashing file {file_path}: {e}")
            return {
                'original_file': file_path.name,
                'file_hash': 'error',
                'file_size': 0
            }

    def check_duplicate(self, file_hash: str, collection) -> Optional[str]:
        """Check if document already processed based on hash"""
        try:
            # Query ChromaDB for documents with this hash
            results = collection.get(
                where={"source.file_hash": file_hash},
                limit=1
            )

            if results and results['ids']:
                return results['ids'][0]

            return None
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return None

    def create_dimensional_metadata(
        self,
        entities: Dict[str, List],
        document_metadata: Dict
    ) -> Dict[str, Any]:
        """Create structured dimensional metadata"""

        dimensions = {
            'people': [f"[[{person}]]" for person in entities.get('people', [])],

            'organizations': [f"[[{org}]]" for org in entities.get('organizations', [])],

            'locations': [f"[[{loc}]]" for loc in entities.get('locations', [])],

            'technologies': entities.get('technologies', []),

            'concepts': entities.get('concepts', []),

            'time': {}
        }

        # Add temporal data
        if 'created' in document_metadata:
            created_date = datetime.fromisoformat(document_metadata['created'])
            dimensions['time'] = {
                'created': document_metadata['created'],
                'fiscal_year': created_date.year,
                'quarter': f"Q{(created_date.month-1)//3+1}",
                'month': created_date.strftime('%B')
            }

        return dimensions

    def calculate_confidence_scores(
        self,
        extraction_metrics: Dict,
        classification: Dict,
        entities: Dict
    ) -> Dict[str, float]:
        """Calculate confidence scores for document processing"""

        # OCR quality (if applicable)
        ocr_quality = extraction_metrics.get('ocr_confidence', 1.0)

        # Extraction quality (based on readability and info density)
        extraction_quality = (
            extraction_metrics.get('readability_score', 0.5) * 0.5 +
            extraction_metrics.get('information_density', 0.5) * 0.5
        )

        # Classification quality (based on classification complexity)
        classification_quality = self._assess_classification_quality(classification)

        # Entity extraction quality
        entity_quality = self._assess_entity_quality(entities)

        # Overall confidence (weighted average)
        overall = (
            ocr_quality * 0.2 +
            extraction_quality * 0.3 +
            classification_quality * 0.3 +
            entity_quality * 0.2
        )

        return {
            'ocr_quality': round(ocr_quality, 3),
            'extraction_quality': round(extraction_quality, 3),
            'classification_quality': round(classification_quality, 3),
            'entity_quality': round(entity_quality, 3),
            'overall': round(overall, 3)
        }

    def _assess_classification_quality(self, classification: Dict) -> float:
        """Assess quality of classification"""
        score = 0.0

        # Has categories
        if classification.get('categories'):
            score += 0.3

        # Has topics
        if classification.get('topics'):
            score += 0.3

        # Has subjects
        if classification.get('subjects'):
            score += 0.2

        # Has complexity rating
        if classification.get('complexity'):
            score += 0.2

        return min(score, 1.0)

    def _assess_entity_quality(self, entities: Dict) -> float:
        """Assess quality of entity extraction"""
        score = 0.0

        # People extracted
        if entities.get('people'):
            score += 0.25

        # Organizations extracted
        if entities.get('organizations'):
            score += 0.25

        # Technologies/concepts extracted
        if entities.get('technologies') or entities.get('concepts'):
            score += 0.25

        # Locations extracted
        if entities.get('locations'):
            score += 0.25

        return min(score, 1.0)

    def create_relationships(
        self,
        document_metadata: Dict,
        existing_documents: List[Dict],
        classification: Dict
    ) -> Dict[str, Any]:
        """Create document relationships and MOC links"""

        relationships = {
            'related_documents': [],
            'references': document_metadata.get('references', []),
            'mocs': []
        }

        # Find related documents (simple similarity for now)
        title = document_metadata.get('title', '')
        summary = document_metadata.get('summary', '')

        for doc in existing_documents:
            if self._is_related(title, summary, doc):
                relationships['related_documents'].append(doc.get('title'))

        # Generate MOC links based on classification
        mocs = self._generate_moc_links(classification)
        relationships['mocs'] = mocs

        return relationships

    def _is_related(self, title: str, summary: str, other_doc: Dict) -> bool:
        """Simple relatedness check"""
        # Check for shared keywords
        title_words = set(title.lower().split())
        other_title_words = set(other_doc.get('title', '').lower().split())

        # At least 2 common words (excluding common words)
        common_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at']
        title_words = {w for w in title_words if w not in common_words}
        other_title_words = {w for w in other_title_words if w not in common_words}

        shared = title_words & other_title_words

        return len(shared) >= 2

    def _generate_moc_links(self, classification: Dict) -> List[str]:
        """Generate Maps of Content links"""
        mocs = []

        # Main category MOC
        categories = classification.get('categories', [])
        if categories:
            mocs.append(f"[[{categories[0]} MOC]]")

        # Topic-specific MOCs
        topics = classification.get('topics', [])
        for topic in topics[:2]:  # Top 2 topics
            mocs.append(f"[[{topic} MOC]]")

        return mocs

    def generate_enhanced_frontmatter(
        self,
        document_data: Dict,
        entities: Dict,
        classification: Dict,
        metrics: Dict,
        source_file: Path,
        content: str
    ) -> Dict[str, Any]:
        """Generate complete enhanced frontmatter"""

        # File source with hash
        source_metadata = self.generate_file_hash(source_file)

        # Hierarchical tags
        tags = self.taxonomy.generate_hierarchical_tags(
            entities, classification, str(source_file), content
        )

        # Dimensional metadata
        dimensions = self.create_dimensional_metadata(entities, document_data)

        # Confidence scores
        confidence = self.calculate_confidence_scores(
            metrics, classification, entities
        )

        # Relationships (would need existing docs from ChromaDB)
        relationships = {
            'related_documents': [],  # To be filled by caller
            'references': document_data.get('references', [])
        }

        # MOC links
        moc_links = self._generate_moc_links(classification)

        # Complete frontmatter
        frontmatter = {
            # Core metadata
            'title': document_data.get('title', source_file.stem),
            'id': document_data.get('id', hashlib.md5(str(source_file).encode()).hexdigest()),
            'created': document_data.get('created', datetime.now().isoformat()),
            'modified': document_data.get('modified', datetime.now().isoformat()),

            # Source with hash
            'source': source_metadata,

            # Document type
            'type': classification.get('type', 'document'),

            # Category
            'category': '/'.join(tags[0].split('/')[:2]) if tags else 'uncategorized',

            # Hierarchical tags
            'tags': tags,

            # Classification
            'classification': classification,

            # Keywords
            'keywords': {
                'primary': document_data.get('keywords', {}).get('primary', []),
                'secondary': document_data.get('keywords', {}).get('secondary', [])
            },

            # Summary
            'summary': document_data.get('summary', ''),

            # Dimensional metadata
            'dimensions': dimensions,

            # Confidence scores
            'confidence': confidence,

            # Relationships
            'relationships': relationships,

            # MOC links
            'relates_to': moc_links,

            # Metrics
            'metrics': metrics,

            # Embeddings metadata
            'embeddings': {
                'model': document_data.get('embedding_model', 'all-MiniLM-L6-v2'),
                'vector_id': f"chromadb:{document_data.get('id', '')}",
                'chunk_count': document_data.get('chunk_count', 0)
            }
        }

        return frontmatter


# Example usage
if __name__ == "__main__":
    # Initialize
    taxonomy = TaxonomyManager("/config/taxonomy.yaml")
    metadata_gen = EnhancedMetadataGenerator(taxonomy)

    # Example document data
    sample_entities = {
        'people': ['Sarah Chen', 'Michael Rodriguez'],
        'organizations': ['AWS', 'Azure', 'Google Cloud'],
        'technologies': ['Kubernetes', 'TensorRT', 'Docker'],
        'concepts': ['MLOps', 'Cost Optimization'],
        'locations': ['Munich']
    }

    sample_classification = {
        'categories': ['Technology'],
        'topics': ['Machine Learning Operations'],
        'subjects': ['Infrastructure Scaling'],
        'complexity': 'advanced',
        'type': 'technical_report'
    }

    sample_metrics = {
        'word_count': 1247,
        'readability_score': 0.7,
        'information_density': 0.8,
        'ocr_confidence': 0.98
    }

    sample_doc = {
        'id': 'ml_infra_2024',
        'title': 'ML Infrastructure Analysis Q3 2024',
        'created': '2024-09-28T12:30:45',
        'summary': 'Comprehensive analysis...',
        'chunk_count': 8
    }

    sample_file = Path("/data/input/ml_infrastructure.pdf")
    sample_content = "Machine learning infrastructure performance analysis..."

    # Generate enhanced frontmatter
    frontmatter = metadata_gen.generate_enhanced_frontmatter(
        sample_doc,
        sample_entities,
        sample_classification,
        sample_metrics,
        sample_file,
        sample_content
    )

    print(yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True))
