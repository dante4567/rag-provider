"""
Unit tests for ActionabilityFilterService

Tests filtering of people and dates for actionability (vCard/calendar worthiness)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.services.actionability_filter_service import ActionabilityFilterService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_service():
    """Mock LLM service"""
    mock = Mock()
    mock.generate = AsyncMock(return_value='{"actionable_people": ["John Doe"]}')
    return mock


@pytest.fixture
def service(mock_llm_service):
    """Create ActionabilityFilterService with mocked dependencies"""
    return ActionabilityFilterService(llm_service=mock_llm_service)


# ============================================================================
# People Filtering Tests
# ============================================================================

class TestPeopleFiltering:
    """Test people filtering functionality"""

    @pytest.mark.asyncio
    async def test_filter_empty_people_list(self, service):
        """Should return empty list for empty input"""
        result = await service.filter_people(
            people=[],
            document_title="Test Doc",
            document_topics=[]
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_filter_actionable_topic_keeps_all(self, service):
        """Should keep all people if document has actionable topics"""
        people = ["Lawyer Smith", "Judge Jones"]
        result = await service.filter_people(
            people=people,
            document_title="Legal Document",
            document_topics=["legal/contracts"]
        )
        assert result == people

    @pytest.mark.asyncio
    async def test_filter_business_topic_keeps_all(self, service):
        """Should keep all people for business documents"""
        people = ["CEO Smith", "Manager Jones"]
        result = await service.filter_people(
            people=people,
            document_title="Business Meeting",
            document_topics=["business/meeting"]
        )
        assert result == people


# ============================================================================
# Dates Filtering Tests
# ============================================================================

class TestDatesFiltering:
    """Test dates filtering functionality"""

    @pytest.mark.asyncio
    async def test_filter_empty_dates_list(self, service):
        """Should return empty list for empty input"""
        result = await service.filter_dates(
            dates=[],
            document_title="Test Doc",
            document_topics=[]
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_filter_actionable_topic_keeps_all_dates(self, service):
        """Should keep all dates if document has actionable topics"""
        dates = ["2025-11-15", "2025-12-01"]
        result = await service.filter_dates(
            dates=dates,
            document_title="Court Hearing",
            document_topics=["legal/court"]
        )
        assert result == dates

    @pytest.mark.asyncio
    async def test_filter_old_dates_removed(self, service):
        """Should filter out dates older than 1 year"""
        old_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        dates = [old_date]
        result = await service.filter_dates(
            dates=dates,
            document_title="Old Document",
            document_topics=[]
        )
        assert result == []


# ============================================================================
# Prompt Building Tests
# ============================================================================

class TestPromptBuilding:
    """Test prompt construction"""

    def test_people_prompt_includes_context(self, service):
        """Should include document context in prompt"""
        prompt = service._build_people_filter_prompt(
            people=["John Doe"],
            document_title="Test Doc",
            document_topics=["test/topic"],
            document_content="Test content"
        )
        assert "Test Doc" in prompt
        assert "test/topic" in prompt
        assert "John Doe" in prompt

    def test_dates_prompt_includes_context(self, service):
        """Should include document context in dates prompt"""
        prompt = service._build_dates_filter_prompt(
            dates=["2025-11-15"],
            document_title="Test Doc",
            document_topics=["test/topic"],
            document_content="Test content"
        )
        assert "Test Doc" in prompt
        assert "test/topic" in prompt
        assert "2025-11-15" in prompt

    def test_prompt_truncates_long_content(self, service):
        """Should truncate content longer than 500 chars"""
        long_content = "a" * 1000
        prompt = service._build_people_filter_prompt(
            people=["John Doe"],
            document_title="Test",
            document_topics=[],
            document_content=long_content
        )
        # Should contain truncated content with "..."
        assert "..." in prompt
