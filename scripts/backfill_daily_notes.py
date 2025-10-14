#!/usr/bin/env python3
"""
Backfill Daily Notes for Existing Documents

Reads all documents from Obsidian vault and creates daily notes for them.
Useful after enabling daily notes feature on existing corpus.

Usage:
    python scripts/backfill_daily_notes.py
    python scripts/backfill_daily_notes.py --obsidian-path /data/obsidian
    python scripts/backfill_daily_notes.py --dry-run  # Preview only
"""

import sys
import os
import argparse
import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.daily_note_service import DailyNoteService


def extract_metadata_from_markdown(file_path: Path) -> dict:
    """Extract frontmatter from markdown file"""
    try:
        content = file_path.read_text(encoding='utf-8')

        if not content.startswith('---'):
            return {}

        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}

        frontmatter_str = parts[1].strip()
        metadata = yaml.safe_load(frontmatter_str)

        return metadata or {}

    except Exception as e:
        print(f"  ⚠️  Failed to read {file_path.name}: {e}")
        return {}


def backfill_daily_notes(
    obsidian_path: str = "./obsidian_vault",
    dry_run: bool = False,
    verbose: bool = False
):
    """
    Backfill daily notes for all existing documents

    Args:
        obsidian_path: Path to Obsidian vault
        dry_run: If True, only preview without creating notes
        verbose: Show detailed progress
    """
    obsidian_dir = Path(obsidian_path)

    if not obsidian_dir.exists():
        print(f"❌ Obsidian directory not found: {obsidian_path}")
        return

    # Initialize daily note service
    daily_service = DailyNoteService(
        refs_dir=str(obsidian_dir / "refs"),
        llm_service=None  # No LLM needed for backfill
    )

    # Find all markdown documents (skip refs/ directory)
    md_files = []
    for md_file in obsidian_dir.glob("*.md"):
        if md_file.parent.name != "refs":
            md_files.append(md_file)

    print(f"📚 Found {len(md_files)} documents in {obsidian_path}")

    if dry_run:
        print("🔍 DRY RUN MODE - No files will be modified\n")

    # Group documents by date
    docs_by_date = defaultdict(list)
    skipped = 0

    for md_file in md_files:
        metadata = extract_metadata_from_markdown(md_file)

        if not metadata:
            skipped += 1
            if verbose:
                print(f"  ⏭️  Skipped (no metadata): {md_file.name}")
            continue

        # Extract document info
        doc_id = metadata.get('id', '')
        title = metadata.get('title', md_file.stem)
        doc_type = metadata.get('doc_type', 'text')
        created_at_str = metadata.get('created_at', '')

        if not created_at_str:
            skipped += 1
            if verbose:
                print(f"  ⏭️  Skipped (no created_at): {md_file.name}")
            continue

        try:
            # Parse created_at date
            if 'T' in created_at_str:
                doc_date = datetime.fromisoformat(created_at_str)
            else:
                doc_date = datetime.strptime(created_at_str, '%Y-%m-%d')

            # Remove .md extension for wiki-links
            doc_filename = md_file.stem

            docs_by_date[doc_date.date()].append({
                'id': doc_id,
                'title': title,
                'type': doc_type,
                'filename': doc_filename,
                'date': doc_date
            })

        except (ValueError, TypeError) as e:
            skipped += 1
            if verbose:
                print(f"  ⚠️  Skipped (invalid date '{created_at_str}'): {md_file.name}")

    print(f"\n📅 Documents span {len(docs_by_date)} unique dates")
    print(f"⏭️  Skipped {skipped} documents (no metadata or invalid dates)\n")

    if dry_run:
        print("Preview of daily notes that would be created:\n")
        for date, docs in sorted(docs_by_date.items())[:10]:  # Show first 10
            print(f"  {date} ({len(docs)} documents)")
            for doc in docs[:3]:  # Show first 3 per date
                print(f"    - {doc['title']} ({doc['type']})")
            if len(docs) > 3:
                print(f"    ... and {len(docs) - 3} more")
        if len(docs_by_date) > 10:
            print(f"\n  ... and {len(docs_by_date) - 10} more dates")
        print(f"\n✅ Would create/update {len(docs_by_date)} daily notes")
        return

    # Create daily notes
    created = 0
    updated = 0

    print("🔧 Creating daily notes...\n")

    for date, docs in sorted(docs_by_date.items()):
        daily_path = daily_service.get_daily_note_path(datetime.combine(date, datetime.min.time()))

        # Check if already exists
        existed = daily_path.exists()

        for doc in docs:
            try:
                daily_service.add_document_to_daily_note(
                    doc_date=doc['date'],
                    doc_title=doc['title'],
                    doc_type=doc['type'],
                    doc_id=doc['id'],
                    doc_filename=doc['filename']
                )
            except Exception as e:
                print(f"  ⚠️  Failed to add {doc['title']} to daily note: {e}")

        if existed:
            updated += 1
        else:
            created += 1

        if verbose or (created + updated) % 50 == 0:
            print(f"  ✅ {date}: {len(docs)} documents")

    print(f"\n✅ Backfill complete!")
    print(f"   📝 Created {created} new daily notes")
    print(f"   🔄 Updated {updated} existing daily notes")
    print(f"   📊 Total documents processed: {sum(len(docs) for docs in docs_by_date.values())}")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill daily notes for existing Obsidian documents"
    )
    parser.add_argument(
        '--obsidian-path',
        default='./obsidian_vault',
        help='Path to Obsidian vault (default: ./obsidian_vault)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without creating notes'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed progress'
    )

    args = parser.parse_args()

    backfill_daily_notes(
        obsidian_path=args.obsidian_path,
        dry_run=args.dry_run,
        verbose=args.verbose
    )


if __name__ == '__main__':
    main()
