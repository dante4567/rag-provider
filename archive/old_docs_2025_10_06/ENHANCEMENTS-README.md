# RAG Provider Enhancements

This document describes the enhancements added to integrate with the NixOS RAG architecture and Obsidian knowledge management system.

## 🎯 Overview

These enhancements add:
- **Hierarchical taxonomy** with controlled vocabulary
- **Enhanced metadata** with file hashing and dimensional structure
- **MOC auto-generation** for automatic organization
- **.obsidian folder pre-configuration** for consistent cross-client experience
- **Confidence scoring** for quality tracking

## 📂 New Files

### 1. `config/taxonomy.yaml`
Defines hierarchical tag structure and mapping rules.

**Structure:**
- Main categories: `tech`, `business`, `work`, `personal`, `reference`
- Nested subcategories: `tech/ml/operations`, `business/finance/taxes/personal`
- Mapping rules for technologies, patterns, file types
- Tag generation rules and Obsidian compatibility settings

**Example:**
```yaml
taxonomy:
  tech:
    ml:
      operations: "Machine Learning Operations (MLOps)"
      infrastructure: "ML Infrastructure & Platforms"

mapping_rules:
  technologies:
    "TensorRT": "tech/ml/deployment"
    "Kubernetes": "tech/devops/infrastructure"

  patterns:
    - pattern: "tax return|steuererklärung"
      tags: ["business/finance/taxes/personal"]
```

### 2. `src/enhanced_metadata.py`
Core metadata generation with hierarchical tags, file hashing, and confidence scoring.

**Classes:**
- `TaxonomyManager`: Loads taxonomy, generates hierarchical tags from entities
- `EnhancedMetadataGenerator`: File hashing, dimensional metadata, confidence scores

**Key Features:**
- SHA256 file hashing for deduplication
- Hierarchical tag generation from entities and classification
- Dimensional metadata with wikilinks: `[[Person]]`, `[[Organization]]`
- Multi-dimensional confidence scoring (OCR, extraction, classification, entity quality)

### 3. `src/moc_generator.py`
Auto-generates Maps of Content for document organization.

**Features:**
- Category-based MOCs
- Tag-based MOCs (for hierarchical tags with 2+ levels)
- Temporal MOCs (by year/quarter)
- Master index with statistics
- Dashboard with Dataview queries

**Auto-generated files:**
- `MOCs/Technology MOC.md`
- `MOCs/Tech - ML - Operations MOC.md`
- `MOCs/2025 Documents MOC.md`
- `_Index.md` (master index)
- `_Dashboard.md` (statistics dashboard)

### 4. `src/obsidian_configurator.py`
Pre-configures .obsidian folder for consistent experience across all clients.

**Creates:**
- `app.json` - Editor settings
- `appearance.json` - Theme and visual settings
- `core-plugins.json` - Enabled core plugins
- `community-plugins.json` - Dataview, Templater, Tag Wrangler
- Plugin configurations (Dataview, Templater settings)
- `graph.json` - Color-coded tag visualization
- `hotkeys.json` - Keyboard shortcuts
- CSS snippets - Custom styling for hierarchical tags
- `workspace.json` - Default layout

## 🔧 Integration

### Step 1: Install Dependencies

Add to `requirements.txt`:
```txt
pyyaml>=6.0
python-frontmatter>=1.0.0
```

Install:
```bash
pip install pyyaml python-frontmatter
```

### Step 2: Create Taxonomy File

Copy the example taxonomy or create your own:
```bash
cp config/taxonomy.yaml.example config/taxonomy.yaml
# Edit to match your document types and tags
nano config/taxonomy.yaml
```

### Step 3: Integrate into Main Pipeline

Update `src/app.py` to use the enhanced modules:

```python
from src.enhanced_metadata import TaxonomyManager, EnhancedMetadataGenerator
from src.moc_generator import MOCGenerator
from src.obsidian_configurator import setup_obsidian_vault
from pathlib import Path
import frontmatter

# Initialize on startup
taxonomy = TaxonomyManager("/config/taxonomy.yaml")
metadata_gen = EnhancedMetadataGenerator(taxonomy)
moc_gen = MOCGenerator(Path("/data/obsidian"))

# One-time: Configure .obsidian folder
setup_obsidian_vault(Path("/data/obsidian"))

# In your document processing function:
def process_document(file_path: Path, content: str, entities: dict, classification: dict, metrics: dict):

    # 1. Check for duplicates (NEW)
    file_hash_data = metadata_gen.generate_file_hash(file_path)
    existing_doc = metadata_gen.check_duplicate(file_hash_data['file_hash'], chroma_collection)

    if existing_doc:
        logger.info(f"Document already processed: {existing_doc}")
        return existing_doc

    # 2. Generate enhanced frontmatter (ENHANCED)
    document_data = {
        'id': generate_id(),
        'title': extract_title(content),
        'created': datetime.now().isoformat(),
        'summary': generate_summary(content),
        'chunk_count': len(chunks)
    }

    frontmatter_data = metadata_gen.generate_enhanced_frontmatter(
        document_data,
        entities,
        classification,
        metrics,
        file_path,
        content
    )

    # 3. Create markdown file
    output_path = Path("/data/obsidian") / f"{frontmatter_data['title']}.md"
    post = frontmatter.Post(content)
    post.metadata = frontmatter_data

    with open(output_path, 'w') as f:
        f.write(frontmatter.dumps(post))

    # 4. Update MOCs (NEW)
    moc_gen.update_mocs_for_document(frontmatter_data)

    # 5. Store in ChromaDB (existing)
    chroma_collection.add(
        documents=[content],
        metadatas=[frontmatter_data],
        ids=[frontmatter_data['id']]
    )

    return frontmatter_data['id']

# Periodically regenerate master index and dashboard
def regenerate_indices():
    all_documents = get_all_documents_from_chromadb()
    moc_gen.generate_master_index(all_documents)
    moc_gen.create_dashboard(all_documents)
```

### Step 4: Update Environment Variables

Add to `docker-compose.yml`:
```yaml
services:
  rag-service:
    environment:
      - TAXONOMY_FILE=/config/taxonomy.yaml
      - OBSIDIAN_VAULT_PATH=/data/obsidian
      - ENABLE_ENHANCED_METADATA=true
      - ENABLE_MOC_GENERATION=true
      - ENABLE_OBSIDIAN_CONFIG=true
```

### Step 5: Test Enhancement

```bash
# Start services
docker-compose up -d

# Drop a test document
cp test.pdf /data/input/

# Check output
ls -la /data/obsidian/
cat /data/obsidian/Test\ Document.md

# Verify MOCs created
ls -la /data/obsidian/MOCs/

# Check .obsidian configuration
ls -la /data/obsidian/.obsidian/
```

## 📊 Enhanced Frontmatter Output

**Before (current):**
```yaml
---
title: "ML Infrastructure Analysis"
tags: ["#machine-learning", "#cloud-infrastructure"]
source: "technical_report.txt"
entities:
  people: ["Sarah Chen"]
  technologies: ["TensorRT", "Kubernetes"]
---
```

**After (enhanced):**
```yaml
---
title: "ML Infrastructure Analysis"
id: "ml_infra_abc123"
created: "2025-10-05T12:30:45"

# Source with hash
source:
  original_file: "technical_report.txt"
  file_hash: "sha256:a3f5c8b2..."
  file_size: 125843

# Category from hierarchical tags
category: tech/ml

# Hierarchical tags
tags:
  - tech/ml/operations
  - tech/cloud/aws
  - time/2025/Q4

# Dimensional metadata
dimensions:
  people: ["[[Sarah Chen]]"]
  organizations: ["[[AWS]]"]
  technologies: ["[[TensorRT]]", "[[Kubernetes]]"]
  time:
    fiscal_year: 2025
    quarter: Q4

# Confidence scores
confidence:
  extraction_quality: 0.98
  classification_quality: 0.95
  overall: 0.96

# MOC links
relates_to:
  - "[[Tech - ML - Operations MOC]]"
  - "[[2025 Documents MOC]]"

# Embeddings
embeddings:
  model: "all-MiniLM-L6-v2"
  vector_id: "chromadb:ml_infra_abc123"
  chunk_count: 8
---
```

## 🎨 Obsidian Features Enabled

### Graph View
- Color-coded tags by category
- Tech = Blue, Business = Green, Work = Orange, Personal = Pink

### Dataview Queries
MOCs include live queries like:
```dataview
TABLE
  summary,
  confidence.overall as "Quality",
  file.ctime as "Created"
WHERE contains(tags, "#tech/ml")
SORT file.ctime DESC
```

### Keyboard Shortcuts
- `Cmd+G`: Graph view
- `Cmd+Shift+F`: Global search
- `Cmd+O`: Quick switcher
- `Cmd+Shift+P`: Command palette

### CSS Customization
Hierarchical tag styling:
- Parent tags: Bold with full color
- Child tags: Lighter background

## 🔄 Data Flow

```
1. Document arrives in /data/input/
   ↓
2. Extract text + entities (existing)
   ↓
3. Generate file hash → Check for duplicates (NEW)
   ↓
4. Generate hierarchical tags from taxonomy (NEW)
   ↓
5. Create enhanced metadata with confidence scores (NEW)
   ↓
6. Export markdown to /data/obsidian/ (enhanced)
   ↓
7. Update relevant MOCs (NEW)
   ↓
8. Store in ChromaDB (existing)
   ↓
9. Syncthing syncs to all clients
```

## 📝 Configuration Options

### Taxonomy Rules

Edit `config/taxonomy.yaml`:

```yaml
tag_rules:
  max_tags_per_document: 10           # Limit total tags
  min_confidence_for_auto_tag: 0.70   # Only auto-tag if confident
  always_add_temporal: true           # Add time/YYYY/QN tags
  add_location_tags: true             # Add location tags if detected
  hierarchical_format: true           # Use tech/ml vs tech-ml
  separator: "/"                       # Hierarchy separator
```

### Confidence Scoring Weights

Edit `src/enhanced_metadata.py`:

```python
# In calculate_confidence_scores():
overall = (
    ocr_quality * 0.2 +           # OCR accuracy weight
    extraction_quality * 0.3 +     # Extraction quality weight
    classification_quality * 0.3 + # Classification accuracy weight
    entity_quality * 0.2           # Entity extraction weight
)
```

### MOC Generation Rules

Edit `src/moc_generator.py`:

```python
# In update_mocs_for_document():
for tag in tags[:3]:  # Top 3 tags → Change to [:5] for top 5
    if tag.count('/') >= 2:  # Only 2+ level tags → Change to >= 1 for all
        self.update_tag_moc(tag, document_metadata)
```

## 🧪 Testing

### Test Taxonomy Loading
```python
from src.enhanced_metadata import TaxonomyManager

taxonomy = TaxonomyManager("/config/taxonomy.yaml")
print(taxonomy.taxonomy.keys())  # Should show: tech, business, work, personal, reference
```

### Test Tag Generation
```python
entities = {
    'technologies': ['Kubernetes', 'AWS'],
    'locations': ['Munich']
}
classification = {
    'categories': ['Technology'],
    'topics': ['Machine Learning Operations']
}

tags = taxonomy.generate_hierarchical_tags(
    entities, classification, "test.pdf", "ML infrastructure content"
)
print(tags)
# Expected: ['tech/ml/operations', 'tech/devops/infrastructure', 'tech/cloud/aws', 'location/germany/munich', 'time/2025', 'time/2025/Q4']
```

### Test File Hashing
```python
from pathlib import Path
from src.enhanced_metadata import EnhancedMetadataGenerator

metadata_gen = EnhancedMetadataGenerator(taxonomy)
hash_data = metadata_gen.generate_file_hash(Path("test.pdf"))
print(hash_data)
# Expected: {'original_file': 'test.pdf', 'file_hash': 'sha256:...', 'file_size': 123456}
```

### Test MOC Generation
```python
from src.moc_generator import MOCGenerator

moc_gen = MOCGenerator(Path("/data/obsidian"))
sample_doc = {
    'title': 'Test Document',
    'category': 'tech/ml',
    'tags': ['tech/ml/operations'],
    'created': '2025-10-05T12:30:45',
    'summary': 'Test summary'
}
moc_gen.update_mocs_for_document(sample_doc)
# Check: /data/obsidian/MOCs/Tech - ML MOC.md should exist
```

## 🎯 Migration from Existing Output

If you have existing documents, migrate them:

```python
import frontmatter
from pathlib import Path

def migrate_document(old_path: Path):
    """Migrate existing document to enhanced format"""

    with open(old_path, 'r') as f:
        post = frontmatter.load(f)

    old_metadata = post.metadata

    # Generate new enhanced metadata
    enhanced = metadata_gen.generate_enhanced_frontmatter(
        old_metadata,
        old_metadata.get('entities', {}),
        old_metadata.get('classification', {}),
        old_metadata.get('metrics', {}),
        old_path,
        post.content
    )

    # Update frontmatter
    post.metadata = enhanced

    # Save
    with open(old_path, 'w') as f:
        f.write(frontmatter.dumps(post))

    # Update MOCs
    moc_gen.update_mocs_for_document(enhanced)

# Migrate all existing documents
vault_path = Path("/data/obsidian")
for md_file in vault_path.glob("*.md"):
    if md_file.name not in ['_Index.md', '_Dashboard.md']:
        migrate_document(md_file)

# Regenerate indices
all_documents = [...]  # Load from ChromaDB
moc_gen.generate_master_index(all_documents)
moc_gen.create_dashboard(all_documents)
```

## 🚀 Performance Considerations

### Deduplication
- File hashing adds ~10ms per document
- ChromaDB query adds ~50ms
- Total overhead: ~60ms per document (negligible)

### Tag Generation
- Taxonomy lookup: O(1) for most mappings
- Pattern matching: O(n) where n = number of patterns (~20)
- Total: ~5ms per document

### MOC Updates
- Category MOC: ~10ms
- Tag MOCs: ~10ms each (max 3)
- Temporal MOC: ~10ms
- Total: ~40ms per document

**Overall enhancement overhead: ~100-150ms per document**

This is acceptable for background processing. For high-volume scenarios (>100 docs/hour), consider:
- Batch MOC updates (update every 10 documents)
- Async MOC generation
- Cache taxonomy lookups

## 📚 Further Customization

### Add New Main Category

Edit `config/taxonomy.yaml`:
```yaml
taxonomy:
  research:  # New category
    papers:
      ai: "AI Research Papers"
      neuroscience: "Neuroscience Research"
    datasets:
      public: "Public Datasets"
      proprietary: "Proprietary Datasets"
```

### Add Custom Pattern Matching

```yaml
mapping_rules:
  patterns:
    - pattern: "quarterly report|Q[1-4] report"
      tags: ["business/finance/reporting"]

    - pattern: "standup|daily meeting"
      tags: ["work/meetings/daily"]
```

### Customize CSS Styling

Edit `src/obsidian_configurator.py`:
```python
# Add custom CSS for your tags
document_css = """
.tag[href="#research"] {
    background-color: #9b59b6;  /* Purple for research */
    color: white;
}

.tag[href^="#research/"] {
    background-color: rgba(155, 89, 182, 0.3);
}
"""
```

## ✅ Validation

After integration, verify:

- [ ] Taxonomy loads without errors
- [ ] Tags are hierarchical (tech/ml/operations)
- [ ] File hashes appear in frontmatter
- [ ] Duplicates are detected
- [ ] MOCs are auto-created in MOCs/
- [ ] _Index.md exists with statistics
- [ ] _Dashboard.md exists with queries
- [ ] .obsidian folder is configured
- [ ] Confidence scores are calculated
- [ ] Dimensional metadata uses wikilinks

## 🔗 See Also

- `INTEGRATION-WITH-NIX-CONFIG.md` - Enhancement comparison
- `RAG-PROVIDER-INTEGRATION.md` - Client integration guide
- `config/taxonomy.yaml` - Full taxonomy reference
- `/Users/danielteckentrup/Documents/my-git/nixos/docs/RAG-PROVIDER-INTEGRATION.md` - Nix config integration
