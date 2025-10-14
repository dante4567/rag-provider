"""
Pydantic models for LLM enrichment responses

These models are used with Instructor to get type-safe,
validated responses from LLMs.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field, field_validator
from datetime import date


class PersonRelationship(BaseModel):
    """A relationship between two people"""
    type: str = Field(description="Relationship type (father, mother, son, daughter, colleague, etc.)")
    person: str = Field(description="Name of the related person")


class Person(BaseModel):
    """A person entity extracted from the document"""
    name: str = Field(description="Full name with titles/roles")
    role: Optional[str] = Field(default=None, description="Their role or function")
    email: Optional[str] = Field(default=None, description="Email address if mentioned")
    phone: Optional[str] = Field(default=None, description="Phone number if mentioned")
    address: Optional[str] = Field(default=None, description="Physical address if mentioned")
    organization: Optional[str] = Field(default=None, description="Organization they belong to")
    birth_date: Optional[str] = Field(default=None, description="Date of birth in YYYY-MM-DD format")
    relationships: List[PersonRelationship] = Field(
        default_factory=list,
        description="Relationships to other people mentioned in the document"
    )


class DateEntity(BaseModel):
    """A date mentioned in the document"""
    date: str = Field(description="Date in YYYY-MM-DD format")
    context: Optional[str] = Field(default=None, description="Context or description of what this date refers to")


class Entities(BaseModel):
    """All entities extracted from the document"""
    people: List[Person] = Field(
        default_factory=list,
        description="People mentioned in the document (max 20)",
        max_length=20
    )
    organizations: List[str] = Field(
        default_factory=list,
        description="Organizations/companies mentioned (max 20)",
        max_length=20  # Increased from 10 to handle complex documents
    )
    places: List[str] = Field(
        default_factory=list,
        description="Places/locations mentioned (max 10)",
        max_length=10
    )
    dates: List[DateEntity] = Field(
        default_factory=list,
        description="Important dates mentioned",
        max_length=20
    )
    numbers: List[str] = Field(
        default_factory=list,
        description="Important numbers/amounts mentioned"
    )


class QualityIndicators(BaseModel):
    """Quality indicators for the document"""
    ocr_quality: Optional[float] = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="OCR confidence score (0-1)"
    )
    content_completeness: Optional[float] = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Completeness score (0-1)"
    )
    language_confidence: Optional[float] = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Language detection confidence (0-1)"
    )


class EnrichmentResponse(BaseModel):
    """
    Complete enrichment response from LLM

    This model enforces the controlled vocabulary constraints
    and provides automatic validation via Pydantic.
    """

    summary: str = Field(
        description="2-3 sentence summary of the document content",
        min_length=10,
        max_length=600
    )

    topics: List[str] = Field(
        default_factory=list,
        description="Topics from controlled vocabulary (8-15 tags covering broad and specific categories)",
        min_length=0,
        max_length=15  # Increased from 5 to allow more granular tagging
    )

    suggested_topics: List[str] = Field(
        default_factory=list,
        description="NEW topics not in vocabulary (for review)",
        max_length=10
    )

    entities: Entities = Field(
        default_factory=Entities,
        description="All entities extracted from the document"
    )

    places: List[str] = Field(
        default_factory=list,
        description="Places from controlled vocabulary",
        max_length=5
    )

    quality_indicators: QualityIndicators = Field(
        default_factory=QualityIndicators,
        description="Quality assessment of the document/extraction"
    )

    @field_validator('topics')
    @classmethod
    def deduplicate_topics(cls, v: List[str]) -> List[str]:
        """Remove duplicate topics while preserving order"""
        seen = set()
        result = []
        for topic in v:
            if topic not in seen:
                seen.add(topic)
                result.append(topic)
        return result

    @field_validator('suggested_topics')
    @classmethod
    def clean_suggested_topics(cls, v: List[str]) -> List[str]:
        """Remove empty strings and duplicates"""
        return list(set(filter(None, v)))

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "summary": "This document discusses the LiteLLM integration for managing LLM providers with a unified interface.",
                "topics": ["technology/api", "business/operations"],
                "suggested_topics": ["llm-integration", "api-unification"],
                "entities": {
                    "people": [],
                    "organizations": ["LiteLLM"],
                    "places": [],
                    "dates": [],
                    "numbers": ["100"]
                },
                "places": [],
                "quality_indicators": {
                    "ocr_quality": 1.0,
                    "content_completeness": 1.0,
                    "language_confidence": 1.0
                }
            }
        }
