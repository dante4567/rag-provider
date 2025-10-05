"""
Map of Content (MOC) Auto-Generator
Creates and updates Obsidian MOC files
"""

import frontmatter
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class MOCGenerator:
    """Generates and updates Maps of Content"""

    def __init__(self, vault_path: Path):
        self.vault_path = Path(vault_path)
        self.moc_dir = self.vault_path / "MOCs"
        self.moc_dir.mkdir(parents=True, exist_ok=True)

    def update_mocs_for_document(self, document_metadata: Dict):
        """Update all relevant MOCs when a new document is added"""

        # Extract MOC references
        category = document_metadata.get('category', 'uncategorized')
        tags = document_metadata.get('tags', [])
        relates_to = document_metadata.get('relates_to', [])

        # Update category MOC
        self.update_category_moc(category, document_metadata)

        # Update tag MOCs (for major tags)
        for tag in tags[:3]:  # Top 3 tags
            if tag.count('/') >= 2:  # Only for hierarchical tags
                self.update_tag_moc(tag, document_metadata)

        # Update temporal MOC
        self.update_temporal_moc(document_metadata)

    def update_category_moc(self, category: str, document_metadata: Dict):
        """Update or create category MOC"""

        # Normalize category for filename
        category_name = category.replace('/', ' - ').title()
        moc_file = self.moc_dir / f"{category_name} MOC.md"

        if moc_file.exists():
            # Update existing MOC
            with open(moc_file, 'r') as f:
                post = frontmatter.load(f)
        else:
            # Create new MOC
            post = frontmatter.Post('')
            post.metadata = {
                'type': 'moc',
                'category': category,
                'created': datetime.now().isoformat(),
                'auto_generated': True
            }

            # Create initial content
            post.content = self._create_moc_template(category_name)

        # Update metadata
        post['updated'] = datetime.now().isoformat()

        # Add document link to appropriate section
        post.content = self._add_document_to_moc(
            post.content,
            document_metadata
        )

        # Save
        with open(moc_file, 'w') as f:
            f.write(frontmatter.dumps(post))

        logger.info(f"Updated MOC: {moc_file.name}")

    def update_tag_moc(self, tag: str, document_metadata: Dict):
        """Update MOC for a specific tag"""

        # Create MOC name from tag
        tag_parts = tag.split('/')
        moc_name = ' - '.join([p.replace('-', ' ').title() for p in tag_parts])
        moc_file = self.moc_dir / f"{moc_name} MOC.md"

        if moc_file.exists():
            with open(moc_file, 'r') as f:
                post = frontmatter.load(f)
        else:
            post = frontmatter.Post('')
            post.metadata = {
                'type': 'moc',
                'tag': tag,
                'created': datetime.now().isoformat(),
                'auto_generated': True
            }
            post.content = self._create_tag_moc_template(tag, moc_name)

        post['updated'] = datetime.now().isoformat()

        # Add document
        post.content = self._add_document_to_moc(post.content, document_metadata)

        with open(moc_file, 'w') as f:
            f.write(frontmatter.dumps(post))

    def update_temporal_moc(self, document_metadata: Dict):
        """Update year-based MOC"""

        created = document_metadata.get('created', datetime.now().isoformat())
        year = datetime.fromisoformat(created).year

        moc_file = self.moc_dir / f"{year} Documents MOC.md"

        if moc_file.exists():
            with open(moc_file, 'r') as f:
                post = frontmatter.load(f)
        else:
            post = frontmatter.Post('')
            post.metadata = {
                'type': 'moc',
                'temporal': True,
                'year': year,
                'created': datetime.now().isoformat(),
                'auto_generated': True
            }
            post.content = self._create_temporal_moc_template(year)

        post['updated'] = datetime.now().isoformat()
        post.content = self._add_document_to_moc(post.content, document_metadata)

        with open(moc_file, 'w') as f:
            f.write(frontmatter.dumps(post))

    def _create_moc_template(self, category_name: str) -> str:
        """Create initial MOC template"""

        return f"""# {category_name} MOC

Central hub for all {category_name.lower()} documents.

## Overview

This Map of Content (MOC) organizes all documents related to {category_name.lower()}.

---

## 📊 Statistics

```dataview
TABLE
  length(rows) as "Count"
WHERE contains(file.folder, "{category_name}")
GROUP BY file.folder
SORT length(rows) DESC
```

---

## 📅 By Year

### 2025


### 2024


---

## 📁 By Subcategory


---

## 🔗 Related MOCs


---

*Auto-generated by RAG Pipeline. Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""

    def _create_tag_moc_template(self, tag: str, moc_name: str) -> str:
        """Create tag-specific MOC template"""

        return f"""# {moc_name} MOC

All documents tagged with `#{tag}`

## Overview

This MOC collects all documents related to {tag.replace('/', ' → ')}.

---

## Documents

```dataview
TABLE
  summary,
  confidence.overall as "Quality",
  file.ctime as "Created"
WHERE contains(tags, "#{tag}")
SORT file.ctime DESC
```

---

## Recent Additions


---

*Auto-generated by RAG Pipeline. Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""

    def _create_temporal_moc_template(self, year: int) -> str:
        """Create year-based MOC template"""

        return f"""# {year} Documents MOC

All documents from {year}

## Overview

Collection of all processed documents from the year {year}.

---

## 📊 Statistics

```dataview
TABLE
  length(rows) as "Documents"
GROUP BY category
WHERE contains(dimensions.time.fiscal_year, "{year}")
SORT length(rows) DESC
```

---

## By Quarter

### Q1 ({year})


### Q2 ({year})


### Q3 ({year})


### Q4 ({year})


---

## By Category


---

*Auto-generated by RAG Pipeline. Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""

    def _add_document_to_moc(self, content: str, document_metadata: Dict) -> str:
        """Add document link to MOC content"""

        title = document_metadata.get('title', 'Untitled')
        created = document_metadata.get('created', datetime.now().isoformat())
        year = datetime.fromisoformat(created).year
        quarter = f"Q{(datetime.fromisoformat(created).month-1)//3+1}"

        # Create link with metadata
        doc_link = f"- [[{title}]]"

        if document_metadata.get('summary'):
            summary = document_metadata['summary'][:100]
            doc_link += f" - {summary}..."

        # Try to add to year section
        year_section = f"### {year}"
        if year_section in content:
            # Add after year header
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.strip() == year_section:
                    # Insert after header
                    lines.insert(i + 2, doc_link)
                    break
            content = '\n'.join(lines)
        else:
            # Try quarter section
            quarter_section = f"### {quarter} ({year})"
            if quarter_section in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if line.strip() == quarter_section:
                        lines.insert(i + 2, doc_link)
                        break
                content = '\n'.join(lines)
            else:
                # Add to "Recent Additions" section
                if "## Recent Additions" in content:
                    content = content.replace(
                        "## Recent Additions\n\n",
                        f"## Recent Additions\n\n{doc_link}\n"
                    )

        return content

    def generate_master_index(self, all_documents: List[Dict]):
        """Generate master index of all MOCs and documents"""

        index_file = self.vault_path / "_Index.md"

        # Group documents
        by_category = defaultdict(list)
        by_year = defaultdict(list)

        for doc in all_documents:
            category = doc.get('category', 'uncategorized')
            by_category[category].append(doc)

            created = doc.get('created', datetime.now().isoformat())
            year = datetime.fromisoformat(created).year
            by_year[year].append(doc)

        # Create index content
        content = f"""---
title: Vault Index
type: index
updated: {datetime.now().isoformat()}
auto_generated: true
---

# 📚 Vault Index

Welcome to your knowledge vault! This index organizes all {len(all_documents)} documents.

---

## 🗂️ Maps of Content

### By Category

"""

        # Add category MOCs
        for category in sorted(by_category.keys()):
            category_name = category.replace('/', ' - ').title()
            count = len(by_category[category])
            content += f"- [[{category_name} MOC]] ({count} documents)\n"

        content += "\n### By Year\n\n"

        # Add temporal MOCs
        for year in sorted(by_year.keys(), reverse=True):
            count = len(by_year[year])
            content += f"- [[{year} Documents MOC]] ({count} documents)\n"

        content += """

---

## 📊 Quick Stats

```dataview
TABLE
  length(rows) as "Documents",
  sum(rows.metrics.word_count) as "Total Words"
GROUP BY category
SORT length(rows) DESC
```

---

## 🔍 Search Tips

- **Cmd+O** (or **Ctrl+O**): Quick open files
- **Cmd+Shift+F**: Search across all files
- **Click tags**: See all tagged notes
- **Graph View** (**Cmd+G**): Visualize connections

---

## 📈 Recent Activity

```dataview
TABLE
  category,
  summary,
  confidence.overall as "Quality"
SORT file.ctime DESC
LIMIT 15
```

---

*Auto-generated. Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""

        with open(index_file, 'w') as f:
            f.write(content)

        logger.info(f"Generated master index: {index_file}")

    def create_dashboard(self, all_documents: List[Dict]):
        """Create statistics dashboard"""

        dashboard_file = self.vault_path / "_Dashboard.md"

        # Calculate stats
        total_docs = len(all_documents)
        total_words = sum(doc.get('metrics', {}).get('word_count', 0) for doc in all_documents)
        avg_confidence = sum(doc.get('confidence', {}).get('overall', 0) for doc in all_documents) / total_docs if total_docs > 0 else 0

        content = f"""---
title: Dashboard
type: dashboard
updated: {datetime.now().isoformat()}
auto_generated: true
---

# 📊 Vault Dashboard

## Overview

- **Total Documents:** {total_docs:,}
- **Total Words:** {total_words:,}
- **Average Confidence:** {avg_confidence:.1%}
- **Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 📈 Documents by Category

```dataview
TABLE
  length(rows) as "Count",
  sum(rows.metrics.word_count) as "Words"
GROUP BY category
SORT length(rows) DESC
```

---

## 📅 Recent Additions (Last 20)

```dataview
TABLE
  category,
  confidence.overall as "Quality",
  metrics.word_count as "Words"
SORT file.ctime DESC
LIMIT 20
```

---

## ⚠️ Low Confidence Documents

```dataview
TABLE
  source.original_file as "Source",
  confidence.overall as "Quality",
  category
WHERE confidence.overall < 0.85
SORT confidence.overall ASC
LIMIT 10
```

---

## 🔗 Most Connected Documents

```dataview
TABLE
  length(file.inlinks) as "Backlinks",
  length(file.outlinks) as "Links",
  category
SORT length(file.inlinks) DESC
LIMIT 15
```

---

## 📊 By Tag

```dataview
TABLE
  length(rows) as "Documents"
GROUP BY file.tags
SORT length(rows) DESC
LIMIT 20
```

---

*Auto-generated. Refresh this page to update statistics.*
"""

        with open(dashboard_file, 'w') as f:
            f.write(content)

        logger.info(f"Generated dashboard: {dashboard_file}")


# Example usage
if __name__ == "__main__":
    vault_path = Path("/data/obsidian")
    moc_gen = MOCGenerator(vault_path)

    # Example document
    sample_doc = {
        'title': 'ML Infrastructure Analysis Q3 2024',
        'category': 'tech/ml',
        'tags': ['tech/ml/operations', 'tech/cloud/aws', 'time/2024/Q3'],
        'created': '2024-09-28T12:30:45',
        'summary': 'Comprehensive analysis of ML infrastructure performance...',
        'confidence': {'overall': 0.95}
    }

    # Update MOCs
    moc_gen.update_mocs_for_document(sample_doc)

    print("MOCs updated successfully!")
