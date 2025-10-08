"""
Calendar Service - Generate iCal events from extracted dates

Automatically creates calendar events (.ics files) for dates mentioned in documents.
"""

from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
import re
import hashlib

logger = logging.getLogger(__name__)


class CalendarService:
    """Generate iCal calendar events for dates extracted from documents"""

    def __init__(self, output_dir: Path = None):
        """
        Initialize calendar service

        Args:
            output_dir: Directory for .ics files (default: data/calendar)
        """
        self.output_dir = output_dir or Path("/data/calendar")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_uid(self, date: str, title: str) -> str:
        """
        Generate unique UID for calendar event

        Args:
            date: Date string (ISO format)
            title: Event title

        Returns:
            Unique identifier
        """
        content = f"{date}{title}"
        hash_part = hashlib.md5(content.encode()).hexdigest()[:16]
        return f"{hash_part}@rag-provider.local"

    def create_event(
        self,
        date: str,
        title: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        all_day: bool = True,
        document_source: Optional[str] = None,
        category: Optional[str] = None
    ) -> Path:
        """
        Create iCal event file

        Args:
            date: Date in ISO format (YYYY-MM-DD)
            title: Event title
            description: Event description
            location: Event location
            all_day: Whether this is an all-day event
            document_source: Source document
            category: Event category (deadline, meeting, etc.)

        Returns:
            Path to created .ics file
        """
        # Parse date
        try:
            event_date = datetime.fromisoformat(date)
        except ValueError:
            logger.warning(f"Invalid date format: {date}")
            return None

        # Generate UID
        uid = self.generate_uid(date, title)

        # Create filename
        safe_title = re.sub(r'[^a-zA-Z0-9\-]', '', title.replace(' ', '-'))[:50]
        filename = f"{date}_{safe_title}.ics"
        file_path = self.output_dir / filename

        # Build iCalendar format
        ical_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//RAG Provider//Calendar Service//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT"
        ]

        # Add UID
        ical_lines.append(f"UID:{uid}")

        # Add dates
        if all_day:
            # All-day events use DATE format (no time)
            dtstart = event_date.strftime('%Y%m%d')
            dtend = (event_date + timedelta(days=1)).strftime('%Y%m%d')
            ical_lines.append(f"DTSTART;VALUE=DATE:{dtstart}")
            ical_lines.append(f"DTEND;VALUE=DATE:{dtend}")
        else:
            # Timed events use DATETIME format
            dtstart = event_date.strftime('%Y%m%dT%H%M%S')
            dtend = (event_date + timedelta(hours=1)).strftime('%Y%m%dT%H%M%S')
            ical_lines.append(f"DTSTART:{dtstart}")
            ical_lines.append(f"DTEND:{dtend}")

        # Add title (SUMMARY)
        ical_lines.append(f"SUMMARY:{self._escape_text(title)}")

        # Add description
        desc_parts = []
        if description:
            desc_parts.append(description)

        if document_source:
            desc_parts.append(f"Source: {document_source}")

        if desc_parts:
            combined_desc = "\\n".join(desc_parts)
            ical_lines.append(f"DESCRIPTION:{self._escape_text(combined_desc)}")

        # Add location
        if location:
            ical_lines.append(f"LOCATION:{self._escape_text(location)}")

        # Add category
        categories = ["RAG-Extracted"]
        if category:
            categories.append(category)
        ical_lines.append(f"CATEGORIES:{','.join(categories)}")

        # Add creation timestamp
        now = datetime.now().strftime('%Y%m%dT%H%M%SZ')
        ical_lines.append(f"DTSTAMP:{now}")
        ical_lines.append(f"CREATED:{now}")
        ical_lines.append(f"LAST-MODIFIED:{now}")

        # Add status
        ical_lines.append("STATUS:CONFIRMED")

        # Close event and calendar
        ical_lines.append("END:VEVENT")
        ical_lines.append("END:VCALENDAR")

        # Write .ics file
        ical_content = "\r\n".join(ical_lines) + "\r\n"
        file_path.write_text(ical_content, encoding='utf-8')

        logger.info(f"Created calendar event for {date}: {file_path}")
        return file_path

    def _escape_text(self, text: str) -> str:
        """
        Escape text for iCalendar format

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        # Escape special characters
        text = text.replace('\\', '\\\\')  # Backslash
        text = text.replace(',', '\\,')    # Comma
        text = text.replace(';', '\\;')    # Semicolon
        text = text.replace('\n', '\\n')   # Newline

        return text

    def infer_event_type(self, context: str, date: str) -> Optional[str]:
        """
        Infer event type from context

        Args:
            context: Text surrounding the date
            date: Date string

        Returns:
            Event type (deadline, meeting, etc.)
        """
        context_lower = context.lower()

        # Deadline keywords
        deadline_keywords = ['deadline', 'frist', 'späteste', 'bis', 'until', 'due']
        if any(kw in context_lower for kw in deadline_keywords):
            return 'Deadline'

        # Meeting keywords
        meeting_keywords = ['meeting', 'termin', 'besprechung', 'conference', 'call']
        if any(kw in context_lower for kw in meeting_keywords):
            return 'Meeting'

        # Court/hearing keywords
        court_keywords = ['hearing', 'verhandlung', 'gericht', 'court']
        if any(kw in context_lower for kw in court_keywords):
            return 'Court Hearing'

        # School/education keywords
        school_keywords = ['anmeldung', 'einschulung', 'school', 'enrollment']
        if any(kw in context_lower for kw in school_keywords):
            return 'School Event'

        return 'Event'

    def create_events_from_metadata(
        self,
        dates: List[str],
        document_title: str = None,
        document_content: str = None,
        document_topics: List[str] = None
    ) -> List[Path]:
        """
        Create calendar events from document metadata

        Args:
            dates: List of dates (ISO format)
            document_title: Source document title
            document_content: Document content (for context)
            document_topics: Document topics

        Returns:
            List of created .ics file paths
        """
        events = []

        for date in dates:
            # Infer event type from context
            event_type = 'Event'
            description = None

            if document_content:
                # Find context around this date
                context = self._extract_context_around_date(document_content, date)
                event_type = self.infer_event_type(context, date)
                description = context[:200] if context else None

            # Create title
            if document_title:
                title = f"{event_type}: {document_title}"
            else:
                title = event_type

            # Determine category from topics
            category = None
            if document_topics:
                if any('legal' in t for t in document_topics):
                    category = 'Legal'
                elif any('school' in t or 'education' in t for t in document_topics):
                    category = 'Education'

            # Create event
            event_path = self.create_event(
                date=date,
                title=title,
                description=description,
                document_source=document_title,
                category=category
            )

            if event_path:
                events.append(event_path)

        logger.info(f"Created {len(events)} calendar events from metadata")
        return events

    def _extract_context_around_date(self, content: str, date: str, window: int = 100) -> str:
        """
        Extract text context around a date mention

        Args:
            content: Full document content
            date: Date to find (ISO format)
            window: Characters before/after to include

        Returns:
            Context string
        """
        # Try different date formats
        patterns = [
            date,  # ISO: 2025-10-08
            date.replace('-', '.'),  # German: 2025.10.08
            date[8:] + '.' + date[5:7] + '.' + date[:4]  # DD.MM.YYYY
        ]

        for pattern in patterns:
            index = content.find(pattern)
            if index != -1:
                start = max(0, index - window)
                end = min(len(content), index + len(pattern) + window)
                context = content[start:end].replace('\n', ' ').strip()
                return context

        return ""

    def create_deadline_reminder(
        self,
        date: str,
        title: str,
        days_before: int = 7,
        **kwargs
    ) -> Path:
        """
        Create event with alarm/reminder

        Args:
            date: Deadline date (ISO format)
            title: Event title
            days_before: Days before deadline to trigger reminder
            **kwargs: Additional event parameters

        Returns:
            Path to .ics file with reminder
        """
        # Parse date
        try:
            deadline = datetime.fromisoformat(date)
        except ValueError:
            logger.warning(f"Invalid date format: {date}")
            return None

        # Create event with alarm
        uid = self.generate_uid(date, title)
        safe_title = re.sub(r'[^a-zA-Z0-9\-]', '', title.replace(' ', '-'))[:50]
        filename = f"{date}_deadline_{safe_title}.ics"
        file_path = self.output_dir / filename

        # Build iCalendar with VALARM
        dtstart = deadline.strftime('%Y%m%d')
        dtend = (deadline + timedelta(days=1)).strftime('%Y%m%d')
        now = datetime.now().strftime('%Y%m%dT%H%M%SZ')

        description = kwargs.get('description', '')
        if kwargs.get('document_source'):
            description += f"\\nSource: {kwargs['document_source']}"

        ical_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//RAG Provider//Calendar Service//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTART;VALUE=DATE:{dtstart}
DTEND;VALUE=DATE:{dtend}
SUMMARY:⚠️ DEADLINE: {self._escape_text(title)}
DESCRIPTION:{self._escape_text(description)}
CATEGORIES:RAG-Extracted,Deadline
PRIORITY:1
STATUS:CONFIRMED
DTSTAMP:{now}
CREATED:{now}
LAST-MODIFIED:{now}
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Reminder: {self._escape_text(title)}
TRIGGER:-P{days_before}D
END:VALARM
END:VEVENT
END:VCALENDAR
"""

        file_path.write_text(ical_content, encoding='utf-8')
        logger.info(f"Created deadline reminder for {date}: {file_path}")
        return file_path

    def export_all_events(self, output_file: Path = None) -> Path:
        """
        Export all events to a single .ics calendar file

        This creates a single file that can be imported into calendar apps.

        Args:
            output_file: Output file path (default: calendar/all_events.ics)

        Returns:
            Path to combined calendar file
        """
        output_file = output_file or self.output_dir / "all_events.ics"

        # Collect all event files
        event_files = list(self.output_dir.glob("*.ics"))

        # Parse and combine events
        all_events = []
        for event_file in event_files:
            if event_file != output_file:  # Don't include the combined file itself
                content = event_file.read_text(encoding='utf-8')

                # Extract VEVENT section
                if 'BEGIN:VEVENT' in content and 'END:VEVENT' in content:
                    start = content.index('BEGIN:VEVENT')
                    end = content.index('END:VEVENT') + len('END:VEVENT')
                    event_section = content[start:end]
                    all_events.append(event_section)

        # Build combined calendar
        combined_calendar = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//RAG Provider//Calendar Service//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:RAG Extracted Events",
            "X-WR-TIMEZONE:Europe/Berlin"
        ]

        combined_calendar.extend(all_events)
        combined_calendar.append("END:VCALENDAR")

        # Write combined file
        output_file.write_text("\r\n".join(combined_calendar) + "\r\n", encoding='utf-8')

        logger.info(f"Exported {len(all_events)} events to {output_file}")
        return output_file


def get_calendar_service(output_dir: Path = None) -> CalendarService:
    """Get CalendarService instance"""
    return CalendarService(output_dir=output_dir)
