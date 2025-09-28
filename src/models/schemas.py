"""
Pydantic models and schemas for the RAG Provider API
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class DocumentType(str, Enum):
    """Supported document types"""
    text = "text"
    pdf = "pdf"
    image = "image"
    whatsapp = "whatsapp"
    email = "email"
    webpage = "webpage"
    scanned = "scanned"
    office = "office"
    code = "code"


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    anthropic = "anthropic"
    openai = "openai"
    groq = "groq"
    google = "google"


class LLMModel(str, Enum):
    """Available LLM models"""
    # Groq models (fast & cost-effective)
    groq_llama3_8b = "groq/llama-3.1-8b-instant"
    groq_llama3_70b = "groq/llama3-70b-8192"

    # Anthropic models (high quality)
    claude_haiku = "anthropic/claude-3-haiku-20240307"
    claude_sonnet = "anthropic/claude-3-5-sonnet-20241022"
    claude_opus = "anthropic/claude-3-opus-20240229"

    # OpenAI models (general purpose)
    gpt4o_mini = "openai/gpt-4o-mini"
    gpt4o = "openai/gpt-4o"

    # Google models (long context)
    gemini_pro = "google/gemini-1.5-pro"


class ObsidianMetadata(BaseModel):
    """Metadata for Obsidian integration"""
    vault_path: Optional[str] = None
    links_created: int = 0
    backlinks_created: int = 0
    tags: List[str] = Field(default_factory=list)
    hierarchy_level: int = 0


class Document(BaseModel):
    """Document input model"""
    content: str
    filename: Optional[str] = None
    document_type: Optional[DocumentType] = DocumentType.text
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    process_ocr: bool = False
    generate_obsidian: bool = True


class IngestResponse(BaseModel):
    """Response from document ingestion"""
    success: bool
    doc_id: str
    chunks: int
    metadata: ObsidianMetadata
    processing_time: float
    message: str


class DocumentInfo(BaseModel):
    """Document information"""
    id: str
    filename: str
    chunks: int
    created_at: str
    metadata: Dict[str, Any]
    obsidian_path: Optional[str] = None


class Stats(BaseModel):
    """System statistics"""
    total_documents: int
    total_chunks: int
    storage_used_mb: float
    last_ingestion: Optional[str]
    llm_provider_status: Dict[str, bool]
    ocr_available: bool


class Query(BaseModel):
    """Search query model"""
    text: str
    top_k: int = 5
    filter: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """Individual search result"""
    id: str
    content: str
    metadata: Dict[str, Any]
    similarity: float
    document_id: str
    chunk_index: int


class SearchResponse(BaseModel):
    """Search results response"""
    results: List[SearchResult]
    query: str
    total_results: int
    processing_time: float


class ChatRequest(BaseModel):
    """Chat request with RAG"""
    question: str
    conversation_id: Optional[str] = None
    max_context_chunks: int = 5
    llm_provider: Optional[LLMProvider] = None
    include_sources: bool = True


class ChatResponse(BaseModel):
    """Chat response with RAG"""
    answer: str
    sources: List[SearchResult]
    conversation_id: str
    processing_time: float
    cost_usd: float
    model_used: str


class TestLLMRequest(BaseModel):
    """Test LLM provider request"""
    provider: Optional[LLMProvider] = None
    model: Optional[LLMModel] = None
    prompt: str = "Hello, this is a test."


class CostInfo(BaseModel):
    """Cost tracking information"""
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str
    timestamp: datetime


class EnrichmentSettings(BaseModel):
    """Document enrichment settings"""
    generate_summary: bool = True
    extract_entities: bool = True
    create_hierarchy: bool = True
    controlled_vocabulary: bool = True
    max_keywords: int = 10
    llm_provider: Optional[LLMProvider] = None