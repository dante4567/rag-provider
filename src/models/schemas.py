"""
Pydantic models and schemas for RAG Provider API

All request/response models, data structures, and enumerations
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


# ===== Enumerations =====

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
    """Available LLM models across providers"""

    # Groq models (fast & cost-effective)
    groq_llama3_8b = "groq/llama-3.1-8b-instant"  # Lightning fast, very cheap
    groq_llama3_70b = "groq/llama3-70b-8192"      # Good quality, fast

    # Anthropic models (high quality)
    anthropic_claude_3_haiku = "anthropic/claude-3-haiku-20240307"   # Cheap & good
    anthropic_claude_3_5_sonnet = "anthropic/claude-3-5-sonnet-20241022"  # Balanced, latest
    anthropic_claude_3_opus = "anthropic/claude-3-opus-20240229"    # Ultimate quality

    # OpenAI models (reliable)
    openai_gpt_4o_mini = "openai/gpt-4o-mini"     # Very cheap
    openai_gpt_4o = "openai/gpt-4o"               # Powerful

    # Google models (long context)
    google_gemini_15_pro = "google/gemini-1.5-pro"  # Long context processing


class ComplexityLevel(str, Enum):
    """Document complexity classification"""
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class SemanticDocumentType(str, Enum):
    """Semantic document type classification (what kind of document is this?)"""
    # Legal
    legal_court_decision = "legal/court-decision"
    legal_contract = "legal/contract"
    legal_law = "legal/law"
    legal_regulation = "legal/regulation"

    # Forms
    form_questionnaire = "form/questionnaire"
    form_application = "form/application"
    form_checklist = "form/checklist"
    form_registration = "form/registration"

    # Education
    education_transcript = "education/transcript"
    education_course_material = "education/course-material"
    education_textbook = "education/textbook"

    # Reference
    reference_brochure = "reference/brochure"
    reference_guide = "reference/guide"
    reference_faq = "reference/faq"
    reference_directory = "reference/directory"
    reference_report = "reference/report"

    # Communication
    communication_email = "communication/email"
    communication_letter = "communication/letter"
    communication_meeting_notes = "communication/meeting-notes"

    # Financial
    financial_invoice = "financial/invoice"
    financial_receipt = "financial/receipt"
    financial_statement = "financial/statement"

    # Personal
    personal_note = "personal/note"
    personal_handwritten = "personal/handwritten"

    # Government
    government_regulation = "government/regulation"
    government_policy = "government/policy"
    government_statistics = "government/statistics"

    # Unknown
    unknown = "unknown/uncategorized"


# ===== Data Models =====

class Keywords(BaseModel):
    """Extracted keywords from document"""
    primary: List[str] = Field(default_factory=list, description="Primary keywords")
    secondary: List[str] = Field(default_factory=list, description="Secondary keywords")
    related: List[str] = Field(default_factory=list, description="Related terms")


class Entities(BaseModel):
    """Named entities extracted from document"""
    people: List[str] = Field(default_factory=list, description="Person names")
    organizations: List[str] = Field(default_factory=list, description="Organization names")
    locations: List[str] = Field(default_factory=list, description="Geographic locations")
    technologies: List[str] = Field(default_factory=list, description="Technologies and tools")


class ObsidianMetadata(BaseModel):
    """Rich metadata for Obsidian vault export"""
    title: str = Field(..., description="Document title")
    keywords: Keywords
    tags: List[str] = Field(default_factory=list, description="Obsidian tags")
    summary: str = Field(default="", description="Document summary")
    abstract: str = Field(default="", description="Abstract or synopsis")
    key_points: List[str] = Field(default_factory=list, description="Key takeaways")
    entities: Entities
    reading_time: str = Field(default="", description="Estimated reading time")
    complexity: ComplexityLevel = Field(default=ComplexityLevel.intermediate)
    links: List[str] = Field(default_factory=list, description="Wikilinks to related notes")
    document_type: DocumentType = Field(default=DocumentType.text)
    source: str = Field(default="", description="Original file path")
    created_at: datetime = Field(default_factory=datetime.now)
    enrichment_version: Optional[str] = Field(default="2.0", description="Enrichment system version")


# ===== Request Models =====

class Document(BaseModel):
    """Document ingestion request"""
    content: str = Field(..., description="Document text content")
    filename: Optional[str] = Field(default=None, description="Original filename")
    document_type: Optional[DocumentType] = Field(default=DocumentType.text)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    process_ocr: bool = Field(default=False, description="Process with OCR if needed")
    generate_obsidian: bool = Field(default=True, description="Generate Obsidian markdown")
    use_critic: bool = Field(default=False, description="Run LLM-as-critic quality assessment")


class EnrichmentSettings(BaseModel):
    """Configuration for LLM enrichment"""
    generate_summary: bool = Field(default=True, description="Generate document summary")
    extract_entities: bool = Field(default=True, description="Extract named entities")
    create_hierarchy: bool = Field(default=True, description="Create hierarchical tags")
    controlled_vocabulary: bool = Field(default=True, description="Use controlled vocabulary")
    max_keywords: int = Field(default=10, ge=1, le=50, description="Maximum keywords to extract")
    llm_provider: Optional[LLMProvider] = Field(default=None, description="Preferred LLM provider")


class Query(BaseModel):
    """Search query request"""
    text: str = Field(..., min_length=1, description="Search query text")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of results to return")
    filter: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters")


class ChatRequest(BaseModel):
    """Chat with RAG request"""
    question: str = Field(..., min_length=1, description="Question to answer")
    max_context_chunks: int = Field(default=5, ge=1, le=20, description="Max chunks to use as context")
    llm_model: Optional[LLMModel] = Field(default=None, description="Specific LLM model to use")
    llm_provider: Optional[LLMProvider] = Field(default=None, description="Specific LLM provider to use")
    include_sources: bool = Field(default=True, description="Include source chunks in response")


class TestLLMRequest(BaseModel):
    """Test LLM provider request"""
    provider: Optional[LLMProvider] = Field(default=None, description="Provider to test")
    model: Optional[LLMModel] = Field(default=None, description="Model to test")
    prompt: str = Field(default="Hello, this is a test.", description="Test prompt")


# ===== Response Models =====

class IngestResponse(BaseModel):
    """Document ingestion response"""
    success: bool = Field(..., description="Ingestion successful")
    doc_id: str = Field(..., description="Unique document ID")
    chunks: int = Field(..., description="Number of chunks created")
    metadata: ObsidianMetadata = Field(..., description="Generated metadata")
    obsidian_path: Optional[str] = Field(default=None, description="Path to Obsidian markdown file")
    critique: Optional["CritiqueResult"] = Field(default=None, description="Quality critique from LLM-as-critic")


class SearchResult(BaseModel):
    """Single search result"""
    content: str = Field(..., description="Chunk content")
    metadata: Dict[str, Any] = Field(..., description="Chunk metadata")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    chunk_id: str = Field(..., description="Chunk identifier")


class SearchResponse(BaseModel):
    """Search results response"""
    query: str = Field(..., description="Original query")
    results: List[SearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., description="Total number of results")
    search_time_ms: float = Field(..., description="Search time in milliseconds")


class DocumentInfo(BaseModel):
    """Document information"""
    id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    chunks: int = Field(..., description="Number of chunks")
    created_at: str = Field(..., description="Creation timestamp")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")
    obsidian_path: Optional[str] = Field(default=None, description="Obsidian markdown path")


class Stats(BaseModel):
    """System statistics"""
    total_documents: int = Field(..., description="Total documents ingested")
    total_chunks: int = Field(..., description="Total chunks stored")
    storage_used_mb: float = Field(..., description="Storage used in MB")
    last_ingestion: Optional[str] = Field(default=None, description="Last ingestion timestamp")
    llm_provider_status: Dict[str, bool] = Field(..., description="LLM provider availability")
    ocr_available: bool = Field(..., description="OCR functionality available")


class ChatResponse(BaseModel):
    """Chat response with RAG context"""
    question: str = Field(..., description="Original question")
    answer: str = Field(..., description="Generated answer")
    sources: List[SearchResult] = Field(..., description="Source chunks used")
    llm_provider_used: str = Field(..., description="LLM provider that generated response")
    llm_model_used: str = Field(..., description="LLM model that generated response")
    total_chunks_found: int = Field(..., description="Total relevant chunks found")
    response_time_ms: float = Field(..., description="Response time in milliseconds")
    cost_usd: Optional[float] = Field(default=None, description="Estimated cost in USD")


class CostInfo(BaseModel):
    """Individual operation cost information"""
    provider: str = Field(..., description="LLM provider")
    model: str = Field(..., description="Model used")
    input_tokens: int = Field(..., description="Input tokens")
    output_tokens: int = Field(..., description="Output tokens")
    cost_usd: float = Field(..., description="Cost in USD")
    timestamp: datetime = Field(..., description="Operation timestamp")


class CostStats(BaseModel):
    """Cost tracking statistics"""
    total_cost_today: float = Field(..., description="Total cost today (USD)")
    total_cost_all_time: float = Field(..., description="Total cost all time (USD)")
    daily_budget: float = Field(..., description="Daily budget limit (USD)")
    budget_remaining: float = Field(..., description="Remaining budget today (USD)")
    operations_today: int = Field(..., description="Number of operations today")
    most_expensive_operation: Optional[CostInfo] = Field(default=None, description="Most expensive operation")
    cost_by_provider: Dict[str, float] = Field(..., description="Cost breakdown by provider")


# ===== Quality Assessment Models (LLM-as-Critic) =====

class QualityScores(BaseModel):
    """Quality scores from LLM critic (0-5 scale)"""
    schema_compliance: float = Field(..., ge=0.0, le=5.0, description="Required fields present, correct data types")
    entity_quality: float = Field(..., ge=0.0, le=5.0, description="Completeness and accuracy of extracted entities")
    topic_relevance: float = Field(..., ge=0.0, le=5.0, description="Appropriate controlled vocabulary usage")
    summary_quality: float = Field(..., ge=0.0, le=5.0, description="Conciseness, accuracy, key points captured")
    task_identification: float = Field(..., ge=0.0, le=5.0, description="Action items and deadlines extracted")
    privacy_assessment: float = Field(..., ge=0.0, le=5.0, description="PII detection and handling")
    chunking_suitability: float = Field(..., ge=0.0, le=5.0, description="Document structure analysis")


class CritiqueResult(BaseModel):
    """Result from LLM-as-critic quality assessment"""
    scores: QualityScores = Field(..., description="Individual rubric scores")
    overall_quality: float = Field(..., ge=0.0, le=5.0, description="Weighted average quality score")
    suggestions: List[str] = Field(default_factory=list, description="Specific improvement suggestions")
    critic_model: str = Field(..., description="LLM model used for critique")
    critic_cost: float = Field(..., description="Cost of critique in USD")
    critic_date: str = Field(..., description="ISO timestamp of critique")
