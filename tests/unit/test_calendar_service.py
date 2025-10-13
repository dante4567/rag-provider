"""
Unit tests for CalendarService

Tests calendar event generation, iCal format, date parsing, and event type inference
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil
from src.services.calendar_service import CalendarService, get_calendar_service


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_calendar_dir():
    """Create temporary directory for calendar files"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def calendar_service(temp_calendar_dir):
    """Create CalendarService with temp directory"""
    return CalendarService(output_dir=temp_calendar_dir)


# =============================================================================
# UID Generation Tests
# =============================================================================

class TestUIDGeneration:
    """Test unique identifier generation"""

    def test_generate_uid(self, calendar_service):
        """Test UID generation is consistent"""
        uid1 = calendar_service.generate_uid("2025-10-13", "Test Event")
        uid2 = calendar_service.generate_uid("2025-10-13", "Test Event")

        assert uid1 == uid2  # Same inputs = same UID
        assert "@rag-provider.local" in uid1

    def test_generate_uid_unique(self, calendar_service):
        """Test different inputs generate different UIDs"""
        uid1 = calendar_service.generate_uid("2025-10-13", "Event 1")
        uid2 = calendar_service.generate_uid("2025-10-13", "Event 2")
        uid3 = calendar_service.generate_uid("2025-10-14", "Event 1")

        assert uid1 != uid2  # Different titles
        assert uid1 != uid3  # Different dates


# =============================================================================
# Text Escaping Tests
# =============================================================================

class TestTextEscaping:
    """Test iCalendar text escaping"""

    def test_escape_backslash(self, calendar_service):
        """Test backslash escaping"""
        result = calendar_service._escape_text("Path\\to\\file")
        assert result == "Path\\\\to\\\\file"

    def test_escape_comma(self, calendar_service):
        """Test comma escaping"""
        result = calendar_service._escape_text("Hello, World")
        assert result == "Hello\\, World"

    def test_escape_semicolon(self, calendar_service):
        """Test semicolon escaping"""
        result = calendar_service._escape_text("Name; Title")
        assert result == "Name\\; Title"

    def test_escape_newline(self, calendar_service):
        """Test newline escaping"""
        result = calendar_service._escape_text("Line 1\nLine 2")
        assert result == "Line 1\\nLine 2"

    def test_escape_combined(self, calendar_service):
        """Test multiple special characters"""
        result = calendar_service._escape_text("Path\\file, name; desc\nNext")
        assert "\\\\" in result
        assert "\\," in result
        assert "\\;" in result
        assert "\\n" in result


# =============================================================================
# Event Creation Tests
# =============================================================================

class TestEventCreation:
    """Test calendar event creation"""

    def test_create_all_day_event(self, calendar_service, temp_calendar_dir):
        """Test all-day event creation"""
        path = calendar_service.create_event(
            date="2025-10-13",
            title="Test Event",
            all_day=True
        )

        assert path is not None
        assert path.exists()
        assert path.suffix == ".ics"

        content = path.read_text()
        assert "BEGIN:VCALENDAR" in content
        assert "BEGIN:VEVENT" in content
        assert "SUMMARY:Test Event" in content
        assert "DTSTART;VALUE=DATE:20251013" in content
        assert "CATEGORIES:RAG-Extracted" in content
        assert "END:VEVENT" in content
        assert "END:VCALENDAR" in content

    def test_create_timed_event(self, calendar_service, temp_calendar_dir):
        """Test timed event creation"""
        path = calendar_service.create_event(
            date="2025-10-13T14:30:00",
            title="Meeting",
            all_day=False
        )

        assert path is not None
        content = path.read_text()

        # Timed events use DATETIME format (no VALUE=DATE)
        assert "DTSTART:20251013T143000" in content
        assert "DTEND:20251013T153000" in content  # +1 hour

    def test_create_event_with_description(self, calendar_service):
        """Test event with description"""
        path = calendar_service.create_event(
            date="2025-10-13",
            title="Test",
            description="This is a test event"
        )

        content = path.read_text()
        assert "DESCRIPTION:This is a test event" in content

    def test_create_event_with_location(self, calendar_service):
        """Test event with location"""
        path = calendar_service.create_event(
            date="2025-10-13",
            title="Meeting",
            location="Conference Room A"
        )

        content = path.read_text()
        assert "LOCATION:Conference Room A" in content

    def test_create_event_with_source(self, calendar_service):
        """Test event with document source"""
        path = calendar_service.create_event(
            date="2025-10-13",
            title="Test",
            document_source="test_document.pdf"
        )

        content = path.read_text()
        assert "Source: test_document.pdf" in content

    def test_create_event_with_category(self, calendar_service):
        """Test event with category"""
        path = calendar_service.create_event(
            date="2025-10-13",
            title="Deadline",
            category="Legal"
        )

        content = path.read_text()
        assert "CATEGORIES:RAG-Extracted,Legal" in content

    def test_create_event_invalid_date(self, calendar_service):
        """Test event with invalid date returns None"""
        path = calendar_service.create_event(
            date="invalid-date",
            title="Test"
        )

        assert path is None

    def test_create_event_filename_sanitization(self, calendar_service, temp_calendar_dir):
        """Test filename is sanitized"""
        path = calendar_service.create_event(
            date="2025-10-13",
            title="Test/Event: With Special*Chars"
        )

        # Special characters should be removed
        assert "/" not in path.name
        assert ":" not in path.name
        assert "*" not in path.name


# =============================================================================
# Event Type Inference Tests
# =============================================================================

class TestEventTypeInference:
    """Test event type inference from context"""

    def test_infer_deadline(self, calendar_service):
        """Test deadline detection"""
        context = "The submission deadline is October 13th"
        event_type = calendar_service.infer_event_type(context, "2025-10-13")
        assert event_type == "Deadline"

    def test_infer_meeting(self, calendar_service):
        """Test meeting detection"""
        context = "We have a meeting scheduled for next week"
        event_type = calendar_service.infer_event_type(context, "2025-10-20")
        assert event_type == "Meeting"

    def test_infer_court_hearing(self, calendar_service):
        """Test court hearing detection"""
        context = "Court hearing on December 5th"
        event_type = calendar_service.infer_event_type(context, "2025-12-05")
        assert event_type == "Court Hearing"

    def test_infer_school_event(self, calendar_service):
        """Test school event detection"""
        context = "School enrollment begins on September 1st"
        event_type = calendar_service.infer_event_type(context, "2025-09-01")
        assert event_type == "School Event"

    def test_infer_generic_event(self, calendar_service):
        """Test generic event fallback"""
        context = "Something happens on that day"
        event_type = calendar_service.infer_event_type(context, "2025-10-13")
        assert event_type == "Event"

    def test_infer_case_insensitive(self, calendar_service):
        """Test case-insensitive keyword matching"""
        context = "DEADLINE for submission"
        event_type = calendar_service.infer_event_type(context, "2025-10-13")
        assert event_type == "Deadline"


# =============================================================================
# Context Extraction Tests
# =============================================================================

class TestContextExtraction:
    """Test extracting context around dates"""

    def test_extract_context_iso_format(self, calendar_service):
        """Test context extraction for ISO date"""
        content = "This is some text before 2025-10-13 and some text after the date."
        context = calendar_service._extract_context_around_date(content, "2025-10-13", window=20)

        assert "2025-10-13" in context
        assert len(context) > 0

    def test_extract_context_german_format(self, calendar_service):
        """Test context extraction for German date format"""
        content = "Meeting on 13.10.2025 at the office"
        context = calendar_service._extract_context_around_date(content, "2025-10-13", window=20)

        assert "13.10.2025" in context

    def test_extract_context_not_found(self, calendar_service):
        """Test context extraction when date not found"""
        content = "Some content without the date"
        context = calendar_service._extract_context_around_date(content, "2025-10-13")

        assert context == ""

    def test_extract_context_window_size(self, calendar_service):
        """Test context window respects size limit"""
        content = "A" * 200 + " 2025-10-13 " + "B" * 200
        context = calendar_service._extract_context_around_date(content, "2025-10-13", window=50)

        # Context should be roughly 100 chars (50 before + date + 50 after)
        assert len(context) < 150  # Some room for date and formatting


# =============================================================================
# Deadline Reminder Tests
# =============================================================================

class TestDeadlineReminders:
    """Test deadline reminder creation"""

    def test_create_deadline_reminder(self, calendar_service):
        """Test deadline with alarm"""
        path = calendar_service.create_deadline_reminder(
            date="2025-10-13",
            title="Submit Report",
            days_before=7
        )

        assert path is not None
        content = path.read_text()

        assert "BEGIN:VALARM" in content
        assert "END:VALARM" in content
        assert "TRIGGER:-P7D" in content  # 7 days before
        assert "⚠️ DEADLINE:" in content
        assert "PRIORITY:1" in content

    def test_create_deadline_reminder_with_source(self, calendar_service):
        """Test deadline with document source"""
        path = calendar_service.create_deadline_reminder(
            date="2025-10-13",
            title="Submit Report",
            document_source="requirements.pdf"
        )

        content = path.read_text()
        assert "Source: requirements.pdf" in content

    def test_create_deadline_reminder_invalid_date(self, calendar_service):
        """Test invalid date returns None"""
        path = calendar_service.create_deadline_reminder(
            date="invalid",
            title="Test"
        )

        assert path is None


# =============================================================================
# Batch Event Creation Tests
# =============================================================================

class TestBatchEventCreation:
    """Test creating events from metadata"""

    def test_create_events_from_metadata_basic(self, calendar_service):
        """Test basic batch event creation"""
        dates = ["2025-10-13", "2025-10-14", "2025-10-15"]
        paths = calendar_service.create_events_from_metadata(
            dates=dates,
            document_title="Test Document"
        )

        assert len(paths) == 3
        for path in paths:
            assert path.exists()

    def test_create_events_with_content_analysis(self, calendar_service):
        """Test event creation with context analysis"""
        dates = ["2025-10-13"]
        content = "Important deadline on 2025-10-13 for project submission"

        paths = calendar_service.create_events_from_metadata(
            dates=dates,
            document_title="Project Guidelines",
            document_content=content
        )

        assert len(paths) == 1
        event_content = paths[0].read_text()
        assert "Deadline" in event_content  # Inferred from "deadline" keyword

    def test_create_events_with_topics_legal(self, calendar_service):
        """Test category inference from legal topics"""
        paths = calendar_service.create_events_from_metadata(
            dates=["2025-10-13"],
            document_title="Court Notice",
            document_topics=["legal/court", "legal/civil"]
        )

        content = paths[0].read_text()
        assert "Legal" in content

    def test_create_events_with_topics_education(self, calendar_service):
        """Test category inference from education topics"""
        paths = calendar_service.create_events_from_metadata(
            dates=["2025-10-13"],
            document_title="School Notice",
            document_topics=["school/enrollment"]
        )

        content = paths[0].read_text()
        assert "Education" in content

    def test_create_events_empty_dates(self, calendar_service):
        """Test batch creation with no dates"""
        paths = calendar_service.create_events_from_metadata(
            dates=[],
            document_title="Test"
        )

        assert len(paths) == 0


# =============================================================================
# Export Tests
# =============================================================================

class TestExportAllEvents:
    """Test exporting all events to single file"""

    def test_export_all_events(self, calendar_service, temp_calendar_dir):
        """Test combining multiple events into single file"""
        # Create some events
        calendar_service.create_event("2025-10-13", "Event 1")
        calendar_service.create_event("2025-10-14", "Event 2")
        calendar_service.create_event("2025-10-15", "Event 3")

        # Export all
        export_path = calendar_service.export_all_events()

        assert export_path.exists()
        content = export_path.read_text()

        # Should have one VCALENDAR with multiple VEVENTs
        assert content.count("BEGIN:VCALENDAR") == 1
        assert content.count("END:VCALENDAR") == 1
        assert content.count("BEGIN:VEVENT") == 3
        assert content.count("END:VEVENT") == 3

    def test_export_all_events_custom_path(self, calendar_service, temp_calendar_dir):
        """Test export to custom path"""
        calendar_service.create_event("2025-10-13", "Test")

        custom_path = temp_calendar_dir / "custom_export.ics"
        export_path = calendar_service.export_all_events(output_file=custom_path)

        assert export_path == custom_path
        assert custom_path.exists()

    def test_export_all_events_empty(self, calendar_service):
        """Test export with no events"""
        export_path = calendar_service.export_all_events()

        assert export_path.exists()
        content = export_path.read_text()

        # Should have valid calendar structure
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content

    def test_export_all_events_metadata(self, calendar_service):
        """Test exported calendar has metadata"""
        calendar_service.create_event("2025-10-13", "Test")
        export_path = calendar_service.export_all_events()

        content = export_path.read_text()
        assert "X-WR-CALNAME:RAG Extracted Events" in content
        assert "X-WR-TIMEZONE:Europe/Berlin" in content


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunction:
    """Test get_calendar_service factory"""

    def test_get_calendar_service_default(self):
        """Test factory with default output dir"""
        service = get_calendar_service()
        assert isinstance(service, CalendarService)
        assert service.output_dir == Path("/data/calendar")

    def test_get_calendar_service_custom_dir(self, temp_calendar_dir):
        """Test factory with custom output dir"""
        service = get_calendar_service(output_dir=temp_calendar_dir)
        assert service.output_dir == temp_calendar_dir


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_event_with_empty_title(self, calendar_service):
        """Test event with empty title"""
        path = calendar_service.create_event(
            date="2025-10-13",
            title=""
        )

        assert path is not None
        content = path.read_text()
        assert "SUMMARY:" in content  # Empty summary is valid iCal

    def test_event_with_very_long_title(self, calendar_service):
        """Test filename truncation for long titles"""
        long_title = "A" * 200
        path = calendar_service.create_event(
            date="2025-10-13",
            title=long_title
        )

        # Filename should be truncated to 50 chars
        assert len(path.stem) < 100  # Date + truncated title

    def test_event_with_unicode_characters(self, calendar_service):
        """Test event with unicode characters"""
        path = calendar_service.create_event(
            date="2025-10-13",
            title="Événement spécial 🎉",
            description="Café meeting ☕"
        )

        assert path is not None
        content = path.read_text(encoding='utf-8')
        assert "Événement spécial" in content

    def test_multiple_events_same_date_title(self, calendar_service, temp_calendar_dir):
        """Test creating duplicate events overwrites file"""
        path1 = calendar_service.create_event("2025-10-13", "Test Event")
        path2 = calendar_service.create_event("2025-10-13", "Test Event")

        # Should be same file (overwritten)
        assert path1 == path2

        # Should only have one file with this pattern
        matching_files = list(temp_calendar_dir.glob("2025-10-13_*.ics"))
        assert len(matching_files) == 1

    def test_event_date_formats(self, calendar_service):
        """Test various date formats"""
        # ISO with time
        path1 = calendar_service.create_event("2025-10-13T14:30:00", "Test 1")
        assert path1 is not None

        # ISO date only
        path2 = calendar_service.create_event("2025-10-13", "Test 2")
        assert path2 is not None

    def test_output_dir_creation(self, temp_calendar_dir):
        """Test output directory is created if it doesn't exist"""
        non_existent = temp_calendar_dir / "subdir" / "calendar"
        service = CalendarService(output_dir=non_existent)

        assert non_existent.exists()
        assert non_existent.is_dir()
