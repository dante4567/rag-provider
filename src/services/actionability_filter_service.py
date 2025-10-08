"""
Actionability Filter Service - LLM-powered filtering for vCards and calendar events

Determines if extracted people/dates are actionable and worth creating
vCards or calendar events for.

Examples of NON-actionable:
- Historical dates in blog posts
- Authors of books mentioned
- Generic date references ("next Monday")
- People mentioned as examples

Examples of actionable:
- Legal contacts (lawyers, judges)
- Actual appointments and deadlines
- School contacts and enrollment dates
- Business contacts from contracts
"""

from typing import List, Dict, Optional
import logging
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ActionabilityFilterService:
    """Filter extracted people/dates to determine if they're actionable"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    async def filter_people(
        self,
        people: List[str],
        document_title: str,
        document_topics: List[str],
        document_content: str = None
    ) -> List[str]:
        """
        Filter people list to only include actionable contacts

        Args:
            people: List of people extracted from document
            document_title: Document title
            document_topics: Document topics
            document_content: Optional document content for context

        Returns:
            List of people that should become vCards
        """
        if not people:
            return []

        # Quick heuristic filters first (avoid LLM call if obvious)
        actionable_topics = [
            'legal/', 'business/', 'education/', 'medical/', 'government/',
            'communication/', 'meeting/'
        ]

        # If document is clearly actionable (legal, business, etc), keep all people
        if any(topic.startswith(prefix) for topic in document_topics for prefix in actionable_topics):
            logger.info(f"Document has actionable topics - keeping all {len(people)} people")
            return people

        # Otherwise, use LLM to filter
        logger.info(f"Using LLM to filter {len(people)} people for actionability")

        prompt = self._build_people_filter_prompt(
            people=people,
            document_title=document_title,
            document_topics=document_topics,
            document_content=document_content
        )

        response = await self.llm_service.generate(
            prompt=prompt,
            model="groq/llama-3.1-70b-versatile",  # Fast, cheap model
            temperature=0.0,  # Deterministic
            max_tokens=500
        )

        # Parse response - expect JSON list
        try:
            import json
            result = json.loads(response.strip())
            actionable_people = result.get('actionable_people', [])
            logger.info(f"Filtered {len(people)} people → {len(actionable_people)} actionable")
            return actionable_people
        except Exception as e:
            logger.warning(f"Failed to parse LLM filter response: {e}, keeping all people")
            return people  # Fail open

    async def filter_dates(
        self,
        dates: List[str],
        document_title: str,
        document_topics: List[str],
        document_content: str = None
    ) -> List[str]:
        """
        Filter dates list to only include actionable events

        Args:
            dates: List of dates extracted from document
            document_title: Document title
            document_topics: Document topics
            document_content: Optional document content for context

        Returns:
            List of dates that should become calendar events
        """
        if not dates:
            return []

        # Quick heuristic filters
        actionable_topics = [
            'legal/', 'education/', 'business/', 'medical/', 'meeting/', 'event/'
        ]

        # If document is clearly actionable, keep all dates
        if any(topic.startswith(prefix) for topic in document_topics for prefix in actionable_topics):
            logger.info(f"Document has actionable topics - keeping all {len(dates)} dates")
            return dates

        # Filter out past dates (more than 1 year old)
        from datetime import datetime, timedelta
        one_year_ago = datetime.now() - timedelta(days=365)
        recent_dates = []
        for date_str in dates:
            try:
                date_obj = datetime.fromisoformat(date_str)
                if date_obj > one_year_ago:
                    recent_dates.append(date_str)
            except ValueError:
                # Keep if can't parse (LLM will handle)
                recent_dates.append(date_str)

        if not recent_dates:
            logger.info(f"Filtered out all {len(dates)} dates (too old)")
            return []

        # Use LLM to filter recent dates
        logger.info(f"Using LLM to filter {len(recent_dates)} dates for actionability")

        prompt = self._build_dates_filter_prompt(
            dates=recent_dates,
            document_title=document_title,
            document_topics=document_topics,
            document_content=document_content
        )

        response = await self.llm_service.generate(
            prompt=prompt,
            model="groq/llama-3.1-70b-versatile",
            temperature=0.0,
            max_tokens=500
        )

        # Parse response
        try:
            import json
            result = json.loads(response.strip())
            actionable_dates = result.get('actionable_dates', [])
            logger.info(f"Filtered {len(recent_dates)} dates → {len(actionable_dates)} actionable")
            return actionable_dates
        except Exception as e:
            logger.warning(f"Failed to parse LLM filter response: {e}, keeping all dates")
            return recent_dates  # Fail open

    def _build_people_filter_prompt(
        self,
        people: List[str],
        document_title: str,
        document_topics: List[str],
        document_content: str = None
    ) -> str:
        """Build prompt for LLM to filter people"""

        # Truncate content if too long
        content_snippet = ""
        if document_content:
            content_snippet = document_content[:500] + "..." if len(document_content) > 500 else document_content

        return f"""You are filtering extracted people to determine if they should become contacts (vCards).

Document Title: {document_title}
Topics: {', '.join(document_topics)}
Content Preview: {content_snippet}

Extracted People:
{chr(10).join(f"- {person}" for person in people)}

ACTIONABLE people (should become contacts):
- Lawyers, judges, legal representatives (in legal documents)
- Business contacts, clients, partners
- School officials, teachers (in education documents)
- Doctors, medical staff (in medical documents)
- Government officials (in official documents)
- People you need to contact or interact with

NON-ACTIONABLE people (should NOT become contacts):
- Historical figures
- Authors of books mentioned
- Generic examples ("John Doe")
- Fictional characters
- People mentioned in passing without context
- Generic role names without specific person

Return ONLY a JSON object with the list of actionable people:
{{"actionable_people": ["Person 1", "Person 2"]}}

Be conservative - when in doubt, include the person (better to have extra contacts than miss important ones).
"""

    def _build_dates_filter_prompt(
        self,
        dates: List[str],
        document_title: str,
        document_topics: List[str],
        document_content: str = None
    ) -> str:
        """Build prompt for LLM to filter dates"""

        # Truncate content if too long
        content_snippet = ""
        if document_content:
            content_snippet = document_content[:500] + "..." if len(document_content) > 500 else document_content

        return f"""You are filtering extracted dates to determine if they should become calendar events.

Document Title: {document_title}
Topics: {', '.join(document_topics)}
Content Preview: {content_snippet}

Extracted Dates:
{chr(10).join(f"- {date}" for date in dates)}

ACTIONABLE dates (should become calendar events):
- Deadlines (school registration, legal deadlines, project deadlines)
- Appointments (meetings, medical appointments, court hearings)
- Events (conferences, school events, important dates)
- Future dates that require action

NON-ACTIONABLE dates (should NOT become calendar events):
- Historical dates (e.g., "founded in 1995")
- Dates mentioned as context/background
- Dates in blog posts about the past
- Document creation dates (unless they're actually deadlines)
- Random dates mentioned without action context

Return ONLY a JSON object with the list of actionable dates:
{{"actionable_dates": ["2025-11-15", "2025-12-01"]}}

Be conservative - when in doubt, include the date (better to have extra events than miss important deadlines).
"""


def get_actionability_filter_service(llm_service: LLMService) -> ActionabilityFilterService:
    """Get ActionabilityFilterService instance"""
    return ActionabilityFilterService(llm_service=llm_service)
