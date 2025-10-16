"""
Pipeline Data Models

These models define the data that flows through pipeline stages.
Each stage has clear input/output contracts using these Pydantic models.

FLOW:
    RawDocument → EnrichedDocument → ChunkedDocument → StoredDocument → ExportedDocument
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from src.models.schemas import DocumentType


class RawDocument(BaseModel):
    """Input to the pipeline - raw document data"""
    content: str
    filename: Optional[str] = None
    document_type: DocumentType = DocumentType.text
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EnrichedDocument(BaseModel):
    """Output from enrichment stage - document with extracted metadata"""
    content: str
    filename: Optional[str] = None
    document_type: DocumentType = DocumentType.text

    # Enriched metadata (flat dict for ChromaDB compatibility)
    enriched_metadata: Dict[str, Any]

    # Extracted entity lists
    people: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)

    # Other extracted lists
    tags: List[str] = Field(default_factory=list)
    key_points: List[str] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)

    # Quality scores
    quality_score: float = 0.0
    novelty_score: float = 0.0
    actionability_score: float = 0.0
    signalness: float = 0.0

    # Indexing decision
    do_index: bool = True
    gate_reason: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class Chunk(BaseModel):
    """A single chunk of text with metadata"""
    content: str
    chunk_index: int
    chunk_type: str = "paragraph"
    section_title: Optional[str] = None
    parent_sections: List[str] = Field(default_factory=list)
    estimated_tokens: int = 0

    @model_validator(mode='after')
    def calculate_tokens_if_zero(self):
        """Auto-calculate estimated_tokens from content if not provided"""
        if self.estimated_tokens == 0:
            # Rough estimate: 1 token ≈ 4 characters
            self.estimated_tokens = max(1, len(self.content) // 4)
        return self


class ChunkedDocument(BaseModel):
    """Output from chunking stage - document split into chunks"""
    doc_id: str
    chunks: List[Chunk]
    enriched_metadata: Dict[str, Any]

    # Carry forward from enrichment
    people: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)

    filename: Optional[str] = None
    document_type: DocumentType = DocumentType.text


class StoredDocument(BaseModel):
    """Output from storage stage - document stored in vector DB"""
    doc_id: str
    chunk_ids: List[str]
    chunk_count: int

    # Metadata for response
    enriched_metadata: Dict[str, Any]


class ExportedDocument(BaseModel):
    """Output from export stage - document exported to Obsidian"""
    doc_id: str
    obsidian_path: Optional[str] = None
    entity_refs_created: int = 0
    attachment_refs_created: int = 0

    # Final response metadata
    metadata: Dict[str, Any]

    class Config:
        arbitrary_types_allowed = True
