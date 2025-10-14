"""
Daily Note Service - Automatic Daily/Weekly/Monthly Journal Generation

Creates periodic notes that link to documents by date:
- Daily notes: Link to all documents from that day
- Weekly notes: Link to daily notes + LLM summary of themes
- Monthly notes: Link to weekly notes + high-level summary

Philosophy:
- Automatic creation on document ingest
- Lightweight "what happened" tracking
- LLM-generated summaries of "what was on my mind"
- Dataview-queryable structure
"""

import logging
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class DailyNoteService:
    """
    Generate daily/weekly/monthly notes with automatic backlinks

    Structure:
    - refs/days/YYYY-MM-DD.md
    - refs/weeks/YYYY-W##.md
    - refs/months/YYYY-MM.md
    """

    def __init__(
        self,
        refs_dir: str = "./obsidian_vault/refs",
        llm_service = None
    ):
        self.refs_dir = Path(refs_dir)
        self.llm_service = llm_service

        # Create directory structure
        self.days_dir = self.refs_dir / "days"
        self.weeks_dir = self.refs_dir / "weeks"
        self.months_dir = self.refs_dir / "months"

        for directory in [self.days_dir, self.weeks_dir, self.months_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def get_week_number(self, date: datetime) -> tuple[int, int]:
        """Get ISO week number and year for a date"""
        iso = date.isocalendar()
        return iso[0], iso[1]  # (year, week_number)

    def get_daily_note_path(self, date: datetime) -> Path:
        """Get path for daily note"""
        date_str = date.strftime('%Y-%m-%d')
        return self.days_dir / f"{date_str}.md"

    def get_weekly_note_path(self, date: datetime) -> Path:
        """Get path for weekly note"""
        year, week = self.get_week_number(date)
        return self.weeks_dir / f"{year}-W{week:02d}.md"

    def get_monthly_note_path(self, date: datetime) -> Path:
        """Get path for monthly note"""
        month_str = date.strftime('%Y-%m')
        return self.months_dir / f"{month_str}.md"

    def add_document_to_daily_note(
        self,
        doc_date: datetime,
        doc_title: str,
        doc_type: str,
        doc_id: str,
        doc_filename: str
    ):
        """
        Add document reference to daily note

        Creates/updates the daily note with a link to this document
        """
        daily_path = self.get_daily_note_path(doc_date)
        date_str = doc_date.strftime('%Y-%m-%d')

        # Load or create daily note
        if daily_path.exists():
            content = daily_path.read_text(encoding='utf-8')
            # Split frontmatter and body
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter_str = parts[1]
                    body = parts[2].strip()
                else:
                    frontmatter_str = ""
                    body = content
            else:
                frontmatter_str = ""
                body = content
        else:
            # Create new daily note
            frontmatter_str = ""
            body = ""

        # Parse existing frontmatter
        if frontmatter_str.strip():
            frontmatter = yaml.safe_load(frontmatter_str)
        else:
            frontmatter = {
                'date': date_str,
                'type': 'daily-note',
                'week': f"[[{self._get_week_link(doc_date)}]]",
                'month': f"[[{self._get_month_link(doc_date)}]]",
                'documents': []
            }

        # Add document to frontmatter list
        doc_entry = {
            'id': doc_id,
            'title': doc_title,
            'type': doc_type,
            'filename': doc_filename
        }

        if 'documents' not in frontmatter:
            frontmatter['documents'] = []

        # Check if already exists
        if not any(d.get('id') == doc_id for d in frontmatter['documents']):
            frontmatter['documents'].append(doc_entry)

        # Generate body if empty
        if not body:
            body = self._generate_daily_note_body(doc_date, frontmatter)
        else:
            # Update body with new document
            body = self._update_daily_note_body(body, doc_type, doc_title, doc_filename)

        # Write updated note
        self._write_note(daily_path, frontmatter, body)
        logger.info(f"Updated daily note: {daily_path}")

    def _get_week_link(self, date: datetime) -> str:
        """Get wiki-link text for weekly note"""
        year, week = self.get_week_number(date)
        return f"weeks/{year}-W{week:02d}"

    def _get_month_link(self, date: datetime) -> str:
        """Get wiki-link text for monthly note"""
        return f"months/{date.strftime('%Y-%m')}"

    def _generate_daily_note_body(self, date: datetime, frontmatter: Dict) -> str:
        """Generate initial body for daily note"""
        date_str = date.strftime('%A, %B %d, %Y')

        body = f"# {date_str}\n\n"
        body += f"← [[{self._get_week_link(date)}|Week {self.get_week_number(date)[1]}]] | "
        body += f"[[{self._get_month_link(date)}|{date.strftime('%B %Y')}]] →\n\n"

        # Group documents by type
        docs_by_type = defaultdict(list)
        for doc in frontmatter.get('documents', []):
            docs_by_type[doc['type']].append(doc)

        # LLM Chats
        if 'llm_chat' in docs_by_type:
            body += "## 🤖 LLM Conversations\n\n"
            for doc in docs_by_type['llm_chat']:
                body += f"- [[{doc['filename']}|{doc['title']}]]\n"
            body += "\n"

        # Emails
        if 'email' in docs_by_type:
            body += "## 📧 Emails\n\n"
            for doc in docs_by_type['email']:
                body += f"- [[{doc['filename']}|{doc['title']}]]\n"
            body += "\n"

        # Other documents
        other_types = [t for t in docs_by_type.keys() if t not in ['llm_chat', 'email']]
        if other_types:
            body += "## 📄 Other Documents\n\n"
            for doc_type in sorted(other_types):
                for doc in docs_by_type[doc_type]:
                    body += f"- [[{doc['filename']}|{doc['title']}]] ({doc_type})\n"
            body += "\n"

        return body

    def _update_daily_note_body(
        self,
        body: str,
        doc_type: str,
        doc_title: str,
        doc_filename: str
    ) -> str:
        """Add new document to existing daily note body"""
        # Build link to check for duplicates
        link = f"- [[{doc_filename}|{doc_title}]]"
        if doc_type not in ['llm_chat', 'email']:
            link += f" ({doc_type})"

        # Check if link already exists (deduplicate)
        if link in body:
            return body

        # Map document types to sections
        if doc_type == 'llm_chat':
            section = "## 🤖 LLM Conversations"
        elif doc_type == 'email':
            section = "## 📧 Emails"
        else:
            section = "## 📄 Other Documents"

        # Find section
        if section in body:
            # Add to existing section
            lines = body.split('\n')
            insert_idx = None
            for i, line in enumerate(lines):
                if line.startswith(section):
                    # Find end of this section (next ## or end)
                    for j in range(i + 1, len(lines)):
                        if lines[j].startswith('##') or j == len(lines) - 1:
                            insert_idx = j if lines[j].startswith('##') else j + 1
                            break
                    break

            if insert_idx:
                lines.insert(insert_idx, link)
                body = '\n'.join(lines)
        else:
            # Add new section
            body += f"\n{section}\n\n{link}\n"

        return body

    async def generate_weekly_note(self, date: datetime, force_regenerate: bool = False):
        """
        Generate weekly note with links to daily notes + LLM summary

        Args:
            date: Any date in the target week
            force_regenerate: Regenerate even if exists
        """
        weekly_path = self.get_weekly_note_path(date)

        if weekly_path.exists() and not force_regenerate:
            logger.info(f"Weekly note already exists: {weekly_path}")
            return

        year, week = self.get_week_number(date)

        # Find all daily notes in this week
        week_start = date - timedelta(days=date.weekday())
        daily_notes = []

        for i in range(7):
            day = week_start + timedelta(days=i)
            daily_path = self.get_daily_note_path(day)
            if daily_path.exists():
                daily_notes.append({
                    'date': day.strftime('%Y-%m-%d'),
                    'day_name': day.strftime('%A'),
                    'filename': f"days/{day.strftime('%Y-%m-%d')}"
                })

        # Load documents from daily notes for summary
        llm_chats = []
        for daily_info in daily_notes:
            daily_path = self.days_dir / f"{daily_info['date']}.md"
            content = daily_path.read_text(encoding='utf-8')

            # Extract frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    for doc in frontmatter.get('documents', []):
                        if doc.get('type') == 'llm_chat':
                            # Load actual document to get summary
                            doc_with_summary = self._load_document_summary(doc)
                            llm_chats.append(doc_with_summary)

        # Generate LLM summary if we have chats and LLM service
        summary = ""
        if llm_chats and self.llm_service:
            summary = await self._generate_weekly_summary(llm_chats, week_start)

        # Build frontmatter
        frontmatter = {
            'week': f"{year}-W{week:02d}",
            'year': year,
            'week_number': week,
            'type': 'weekly-note',
            'month': f"[[{self._get_month_link(date)}]]",
            'daily_notes': daily_notes,
            'llm_chat_count': len(llm_chats)
        }

        # Build body
        body = f"# Week {week}, {year}\n\n"
        body += f"← [[{self._get_month_link(date)}|{date.strftime('%B %Y')}]] →\n\n"

        # Daily notes
        body += "## Daily Notes\n\n"
        for daily in daily_notes:
            body += f"- [[{daily['filename']}|{daily['day_name']}, {daily['date']}]]\n"
        body += "\n"

        # Summary
        if summary:
            body += "## What Was On My Mind\n\n"
            body += f"{summary}\n\n"

        # Stats
        body += "## Week Summary\n\n"
        body += f"- **LLM Conversations**: {len(llm_chats)}\n"
        body += f"- **Days with activity**: {len(daily_notes)}\n"

        self._write_note(weekly_path, frontmatter, body)
        logger.info(f"Generated weekly note: {weekly_path}")

    async def generate_monthly_note(self, date: datetime, force_regenerate: bool = False):
        """
        Generate monthly note with links to weekly notes + high-level summary

        Args:
            date: Any date in the target month
            force_regenerate: Regenerate even if exists
        """
        monthly_path = self.get_monthly_note_path(date)

        if monthly_path.exists() and not force_regenerate:
            logger.info(f"Monthly note already exists: {monthly_path}")
            return

        month_str = date.strftime('%Y-%m')
        year = date.year
        month = date.month

        # Find all weekly notes in this month
        weekly_notes = []
        first_day = date.replace(day=1)
        last_day = (first_day.replace(month=month % 12 + 1, day=1) - timedelta(days=1)) if month < 12 else first_day.replace(month=12, day=31)

        current = first_day
        seen_weeks = set()

        while current <= last_day:
            year_num, week_num = self.get_week_number(current)
            week_key = f"{year_num}-W{week_num:02d}"

            if week_key not in seen_weeks:
                weekly_path = self.weeks_dir / f"{week_key}.md"
                if weekly_path.exists():
                    weekly_notes.append({
                        'week': week_key,
                        'filename': f"weeks/{week_key}"
                    })
                seen_weeks.add(week_key)

            current += timedelta(days=7)

        # Build frontmatter
        frontmatter = {
            'month': month_str,
            'year': year,
            'month_number': month,
            'type': 'monthly-note',
            'weekly_notes': weekly_notes
        }

        # Build body
        body = f"# {date.strftime('%B %Y')}\n\n"

        # Weekly notes
        body += "## Weekly Notes\n\n"
        for weekly in weekly_notes:
            body += f"- [[{weekly['filename']}|{weekly['week']}]]\n"
        body += "\n"

        # Stats
        body += "## Month Summary\n\n"
        body += f"- **Weeks tracked**: {len(weekly_notes)}\n"

        self._write_note(monthly_path, frontmatter, body)
        logger.info(f"Generated monthly note: {monthly_path}")

    def _load_document_summary(self, doc: Dict) -> Dict:
        """
        Load full document and extract summary from frontmatter

        Args:
            doc: Document dict with filename

        Returns:
            Document dict with 'summary' field added
        """
        try:
            # Construct path to document (in parent directory of refs/)
            doc_filename = doc.get('filename', '')
            if not doc_filename:
                return doc

            # Try to find the document
            doc_path = self.refs_dir.parent / f"{doc_filename}.md"

            if not doc_path.exists():
                logger.warning(f"Document not found: {doc_path}")
                return doc

            # Read and parse frontmatter
            content = doc_path.read_text(encoding='utf-8')
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1])
                        doc['summary'] = frontmatter.get('summary', '')
                    except Exception as e:
                        logger.warning(f"Failed to parse frontmatter for {doc_filename}: {e}")

        except Exception as e:
            logger.warning(f"Failed to load document summary for {doc.get('filename')}: {e}")

        return doc

    async def _generate_weekly_summary(
        self,
        llm_chats: List[Dict],
        week_start: datetime
    ) -> str:
        """
        Generate LLM summary of "what was on my mind" this week

        Uses LLM chat summaries to infer themes and preoccupations
        """
        if not llm_chats or not self.llm_service:
            return ""

        # Build prompt with summaries if available, fallback to titles
        chat_info = []
        for chat in llm_chats:
            title = chat.get('title', 'Untitled')
            summary = chat.get('summary', '')

            if summary:
                chat_info.append(f"**{title}**: {summary}")
            else:
                chat_info.append(f"- {title}")

        prompt = f"""Based on these LLM conversations from the week of {week_start.strftime('%B %d, %Y')}, write a brief 2-3 sentence summary of what themes and topics were on this person's mind.

Conversations:
{chr(10).join(chat_info)}

Write in first person ("I was thinking about..."). Be specific and insightful. Focus on patterns and themes across conversations, not individual ones."""

        try:
            # Use Groq for summaries - fast, cheap, and actually works
            response, _, _ = await self.llm_service.call_llm(
                prompt=prompt,
                model_id="groq/llama-3.1-8b-instant",
                temperature=0.7
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to generate weekly summary: {e}")
            return ""

    def _write_note(self, path: Path, frontmatter: Dict, body: str):
        """Write note with frontmatter and body"""
        content = "---\n"
        content += yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
        content += "---\n\n"
        content += body

        path.write_text(content, encoding='utf-8')
