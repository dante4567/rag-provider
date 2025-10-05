#!/usr/bin/env python3
"""
Data models for the RAG service
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    """Document type enumeration"""
    PDF = "pdf"
    TEXT = "text"
    DOCX = "docx"
    DOC = "doc"
    PPTX = "pptx"
    XLSX = "xlsx"
    XLS = "xls"
    EMAIL = "email"
    HTML = "html"
    IMAGE = "image"
    WHATSAPP = "whatsapp"
    CSV = "csv"
    JSON = "json"


class ProcessingStatus(str, Enum):
    """Processing status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchRequest(BaseModel):
    """Search request model"""
    text: str = Field(..., description="Search query text")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Similarity threshold")
    collection_name: str = Field(default="documents", description="Collection to search")


class SearchResult(BaseModel):
    """Search result model"""
    id: str = Field(..., description="Document ID")
    text: str = Field(..., description="Matched text content")
    score: float = Field(..., description="Similarity score")
    metadata: Dict[str, Any] = Field(default={}, description="Document metadata")


class SearchResponse(BaseModel):
    """Search response model"""
    results: List[SearchResult]
    query: str
    total_results: int
    processing_time: float


class ChatRequest(BaseModel):
    """Chat request model"""
    question: str = Field(..., description="Question to ask")
    llm_model: str = Field(default="groq/llama-3.1-8b-instant", description="LLM model to use")
    max_context_docs: int = Field(default=5, ge=1, le=20, description="Max documents for context")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Response creativity")


class ChatResponse(BaseModel):
    """Chat response model"""
    answer: str
    sources: List[SearchResult]
    model_used: str
    processing_time: float
    cost: float


class DocumentInfo(BaseModel):
    """Document information model"""
    id: str
    filename: str
    file_type: DocumentType
    size_bytes: int
    processing_status: ProcessingStatus
    upload_time: datetime
    processing_time: Optional[float] = None
    error_message: Optional[str] = None
    chunk_count: int = 0
    metadata: Dict[str, Any] = {}


class UploadResponse(BaseModel):
    """Upload response model"""
    document_id: str
    filename: str
    status: ProcessingStatus
    message: str
    processing_time: Optional[float] = None
    chunk_count: Optional[int] = None


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    timestamp: datetime
    version: str
    components: Dict[str, str]


class LLMTestRequest(BaseModel):
    """LLM test request model"""
    provider: str = Field(..., description="LLM provider to test")
    prompt: str = Field(default="Hello, how are you?", description="Test prompt")
    model: Optional[str] = Field(None, description="Specific model to test")


class LLMTestResponse(BaseModel):
    """LLM test response model"""
    provider: str
    model: str
    response: str
    cost: float
    processing_time: float
    success: bool
    error: Optional[str] = None


class DocumentStats(BaseModel):
    """Document statistics model"""
    total_documents: int
    total_chunks: int
    documents_by_type: Dict[str, int]
    processing_stats: Dict[str, int]
    storage_size_mb: float


class SystemStatus(BaseModel):
    """System status model"""
    status: str
    uptime: str
    document_stats: DocumentStats
    llm_providers: Dict[str, bool]
    features: Dict[str, bool]


class EnrichmentRequest(BaseModel):
    """Document enrichment request model"""
    document_id: str = Field(..., description="Document ID to enrich")
    enable_summary: bool = Field(default=True, description="Generate summary")
    enable_tags: bool = Field(default=True, description="Generate tags")
    enable_entities: bool = Field(default=True, description="Extract entities")
    llm_model: str = Field(default="groq/llama-3.1-8b-instant", description="LLM model for enrichment")


class EnrichmentResponse(BaseModel):
    """Document enrichment response model"""
    document_id: str
    summary: Optional[str] = None
    tags: List[str] = []
    entities: Dict[str, List[str]] = {}
    processing_time: float
    cost: float
    model_used: str