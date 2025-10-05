from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Form, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
import chromadb
from pathlib import Path
import hashlib
import json
import logging
import os
import uuid
import asyncio
import aiofiles
import time
import yaml
import re
import platform
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
import mimetypes

# Document processing imports
# Using simple text splitter to avoid langchain dependency conflicts
import PyPDF2
import magic
from docx import Document as DocxDocument
from pptx import Presentation
import openpyxl
import xlrd
from bs4 import BeautifulSoup
import email
from email.mime.text import MIMEText
from dateutil import parser as date_parser

# OCR imports
try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.warning("OCR dependencies not available")

# LLM provider imports
import anthropic
import openai
import groq
try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google Generative AI not available")

# File monitoring
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Rich console output
from rich.console import Console
from rich.table import Table
from tqdm import tqdm

# New service layer imports
try:
    from src.core.dependencies import get_settings
    from src.services import (
        DocumentService as NewDocumentService,
        LLMService as NewLLMService,
        VectorService as NewVectorService,
        OCRService as NewOCRService
    )
    from src.services.enrichment_service import EnrichmentService
    from src.services.advanced_enrichment_service import AdvancedEnrichmentService
    from src.services.tag_taxonomy_service import TagTaxonomyService
    from src.services.smart_triage_service import SmartTriageService
    from src.services.obsidian_service import ObsidianService
    NEW_SERVICES_AVAILABLE = True
except ImportError as e:
    NEW_SERVICES_AVAILABLE = False
    logging.warning(f"New service layer not available: {e}")

# Simple text splitter to replace langchain dependency
class SimpleTextSplitter:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        """Split text into chunks with overlap"""
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + self.chunk_size

            # If this isn't the last chunk, try to break at a sentence or word boundary
            if end < text_len:
                # Look for sentence endings
                for i in range(min(100, self.chunk_size // 4)):
                    if end - i >= 0 and text[end - i] in '.!?':
                        end = end - i + 1
                        break
                else:
                    # Look for word boundaries
                    for i in range(min(50, self.chunk_size // 8)):
                        if end - i >= 0 and text[end - i] == ' ':
                            end = end - i
                            break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = end - self.chunk_overlap
            if start <= 0:
                start = end

        return chunks

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

# Environment variables with defaults
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "documents")

# Platform detection
PLATFORM = platform.system().lower()
IS_DOCKER = os.getenv("DOCKER_CONTAINER", "false").lower() == "true"

# Platform-specific paths
def get_platform_config():
    if IS_DOCKER:
        return {
            'input_path': '/data/input',
            'output_path': '/data/output',
            'processed_path': '/data/processed',
            'obsidian_path': '/tmp/obsidian',
            'temp_path': '/tmp'
        }
    elif PLATFORM == 'windows':
        base_path = os.path.expanduser('~/Documents/rag_data')
        return {
            'input_path': f'{base_path}/input',
            'output_path': f'{base_path}/output',
            'processed_path': f'{base_path}/processed',
            'obsidian_path': f'{base_path}/obsidian',
            'temp_path': os.environ.get('TEMP', '/tmp')
        }
    else:  # Linux/macOS
        base_path = os.path.expanduser('~/rag_data')
        return {
            'input_path': f'{base_path}/input',
            'output_path': f'{base_path}/output',
            'processed_path': f'{base_path}/processed',
            'obsidian_path': f'{base_path}/obsidian',
            'temp_path': '/tmp'
        }

PATHS = get_platform_config()

# Processing configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
ENABLE_FILE_WATCH = os.getenv("ENABLE_FILE_WATCH", "true").lower() == "true"

# LLM Configuration
DEFAULT_LLM = os.getenv("DEFAULT_LLM", "groq")
FALLBACK_LLM = os.getenv("FALLBACK_LLM", "anthropic")
EMERGENCY_LLM = os.getenv("EMERGENCY_LLM", "openai")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))

# OCR Configuration
USE_OCR = os.getenv("USE_OCR", "true").lower() == "true"
OCR_PROVIDER = os.getenv("OCR_PROVIDER", "tesseract")
OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "eng").split(",")

# Obsidian Configuration
CREATE_OBSIDIAN_LINKS = os.getenv("CREATE_OBSIDIAN_LINKS", "true").lower() == "true"
HIERARCHY_DEPTH = int(os.getenv("HIERARCHY_DEPTH", "3"))

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Cost tracking
DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "10.0"))
ENABLE_COST_TRACKING = os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"

# Security Configuration
API_KEY = os.getenv("RAG_API_KEY")
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() == "true"
PUBLIC_ENDPOINTS = {"/health", "/docs", "/redoc", "/openapi.json"}

# Authentication setup
security = HTTPBearer(auto_error=False)

# Enums
class DocumentType(str, Enum):
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
    anthropic = "anthropic"
    openai = "openai"
    groq = "groq"
    google = "google"

class LLMModel(str, Enum):
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
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"

# Pydantic Models
class Keywords(BaseModel):
    primary: List[str] = Field(default_factory=list)
    secondary: List[str] = Field(default_factory=list)
    related: List[str] = Field(default_factory=list)

class Entities(BaseModel):
    people: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)

class ObsidianMetadata(BaseModel):
    title: str
    keywords: Keywords
    tags: List[str] = Field(default_factory=list)
    summary: str = ""
    abstract: str = ""
    key_points: List[str] = Field(default_factory=list)
    entities: Entities
    reading_time: str = ""
    complexity: ComplexityLevel = ComplexityLevel.intermediate
    links: List[str] = Field(default_factory=list)
    document_type: DocumentType = DocumentType.text
    source: str = ""
    created_at: datetime = Field(default_factory=datetime.now)

    # Enrichment quality metrics
    domain: str = "general"
    significance_score: float = 0.0
    quality_tier: str = "medium"
    entity_richness: float = 0.0
    content_depth: float = 0.0
    extraction_confidence: float = 0.0

    # Entity counts
    people_count: int = 0
    organizations_count: int = 0
    concepts_count: int = 0

    # Triage information
    triage_category: str = "unknown"
    triage_confidence: float = 0.0
    is_duplicate: bool = False
    is_actionable: bool = False

class Document(BaseModel):
    content: str
    filename: Optional[str] = None
    document_type: Optional[DocumentType] = DocumentType.text
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    process_ocr: bool = False
    generate_obsidian: bool = True

class EnrichmentSettings(BaseModel):
    generate_summary: bool = True
    extract_entities: bool = True
    create_hierarchy: bool = True
    controlled_vocabulary: bool = True
    max_keywords: int = 10
    llm_provider: Optional[LLMProvider] = None

class IngestResponse(BaseModel):
    success: bool
    doc_id: str
    chunks: int
    metadata: ObsidianMetadata
    obsidian_path: Optional[str] = None

class SearchResult(BaseModel):
    content: str
    metadata: Dict[str, Any]
    relevance_score: float
    chunk_id: str

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int
    search_time_ms: float

class DocumentInfo(BaseModel):
    id: str
    filename: str
    chunks: int
    created_at: str
    metadata: Dict[str, Any]
    obsidian_path: Optional[str] = None

class Stats(BaseModel):
    total_documents: int
    total_chunks: int
    storage_used_mb: float
    last_ingestion: Optional[str]
    llm_provider_status: Dict[str, bool]
    ocr_available: bool

class Query(BaseModel):
    text: str
    top_k: int = 5
    filter: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    question: str
    max_context_chunks: int = 5
    llm_model: Optional[LLMModel] = None
    llm_provider: Optional[LLMProvider] = None
    include_sources: bool = True

class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: List[SearchResult]
    llm_provider_used: str
    llm_model_used: str
    total_chunks_found: int
    response_time_ms: float
    cost_usd: Optional[float] = None

class CostInfo(BaseModel):
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: datetime

class CostStats(BaseModel):
    total_cost_today: float
    total_cost_all_time: float
    daily_budget: float
    budget_remaining: float
    operations_today: int
    most_expensive_operation: Optional[CostInfo] = None
    cost_by_provider: Dict[str, float]

class TestLLMRequest(BaseModel):
    provider: Optional[LLMProvider] = None
    model: Optional[LLMModel] = None
    prompt: str = "Hello, this is a test."

# Model pricing (per 1M tokens) - Updated 2024
MODEL_PRICING = {
    # Groq - Lightning fast inference
    "groq/llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},      # Ultra-cheap

    # Anthropic - High quality reasoning
    "anthropic/claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},        # Cheapest Claude
    "anthropic/claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},      # Latest & best balanced
    "anthropic/claude-3-opus-20240229": {"input": 15.0, "output": 75.0},         # Ultimate quality

    # OpenAI - Reliable general purpose
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},             # Very cheap & capable
    "openai/gpt-4o": {"input": 5.0, "output": 15.0},                   # Powerful flagship

    # Google - Long context specialist
    "google/gemini-1.5-pro": {"input": 1.25, "output": 5.0}            # 2M context window
}

# LLM Provider Configuration
LLM_PROVIDERS = {
    "anthropic": {
        "api_key": ANTHROPIC_API_KEY,
        "models": {
            "anthropic/claude-3-haiku-20240307": {"max_tokens": 4000, "model_name": "claude-3-haiku-20240307"},
            "anthropic/claude-3-5-sonnet-20241022": {"max_tokens": 4000, "model_name": "claude-3-5-sonnet-20241022"},
            "anthropic/claude-3-opus-20240229": {"max_tokens": 4000, "model_name": "claude-3-opus-20240229"}
        },
        "client_class": anthropic.Anthropic
    },
    "openai": {
        "api_key": OPENAI_API_KEY,
        "models": {
            "openai/gpt-4o-mini": {"max_tokens": 4000, "model_name": "gpt-4o-mini"},
            "openai/gpt-4o": {"max_tokens": 4000, "model_name": "gpt-4o"}
        },
        "client_class": openai.OpenAI
    },
    "groq": {
        "api_key": GROQ_API_KEY,
        "models": {
            "groq/llama-3.1-8b-instant": {"max_tokens": 8000, "model_name": "llama-3.1-8b-instant"}
        },
        "client_class": groq.Groq
    },
    "google": {
        "api_key": GOOGLE_API_KEY,
        "models": {
            "google/gemini-1.5-pro": {"max_tokens": 8000, "model_name": "gemini-1.5-pro-latest"}
        },
        "client_class": None  # Will be set during import
    }
}

# Initialize LLM clients
llm_clients = {}
for provider, config in LLM_PROVIDERS.items():
    if config["api_key"]:
        try:
            if provider == "google" and GOOGLE_AVAILABLE:
                genai.configure(api_key=config["api_key"])
                llm_clients[provider] = genai.GenerativeModel('gemini-1.5-pro-latest')
            elif provider in ["groq", "anthropic", "openai"]:
                llm_clients[provider] = config["client_class"](api_key=config["api_key"])
            logger.info(f"Initialized {provider} LLM client")
        except Exception as e:
            logger.warning(f"Failed to initialize {provider} client: {e}")

# Cost tracking storage (in-memory for simplicity, could be moved to database)
cost_tracking = {
    "operations": [],
    "daily_totals": {},
    "total_cost": 0.0
}

# Authentication dependency
async def verify_token(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for protected endpoints"""
    if not REQUIRE_AUTH:
        return True

    # Check if endpoint is public
    if request.url.path in PUBLIC_ENDPOINTS:
        return True

    # Check for API key in header or query parameter
    token = None
    if credentials:
        token = credentials.credentials
    else:
        token = request.headers.get("X-API-Key") or request.query_params.get("api_key")

    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is required but no API key is configured"
        )

    if not token or token != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True

# Initialize FastAPI app
app = FastAPI(
    title="Enhanced RAG Service",
    version="2.0.1",
    description="Secure cross-platform RAG service with OCR, WhatsApp processing, and Obsidian optimization"
)

# Secure CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Global variables
chroma_client = None
collection = None
text_splitter = None
file_watcher = None
executor = ThreadPoolExecutor(max_workers=4)

class CostTracker:
    """Tracks LLM API costs and enforces budget limits"""

    def __init__(self):
        self.operations = cost_tracking["operations"]
        self.daily_totals = cost_tracking["daily_totals"]
        self.total_cost = cost_tracking["total_cost"]

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars = 1 token for most models)"""
        return len(text) // 4

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model pricing"""
        if model not in MODEL_PRICING:
            return 0.0

        pricing = MODEL_PRICING[model]
        input_cost = (input_tokens / 1000000) * pricing["input"]
        output_cost = (output_tokens / 1000000) * pricing["output"]
        return input_cost + output_cost

    def check_budget(self) -> bool:
        """Check if daily budget limit is reached"""
        if not ENABLE_COST_TRACKING:
            return True

        today = datetime.now().strftime("%Y-%m-%d")
        today_cost = self.daily_totals.get(today, 0.0)
        return today_cost < DAILY_BUDGET_USD

    def record_operation(self, provider: str, model: str, input_tokens: int, output_tokens: int, cost: float):
        """Record an API operation and its cost"""
        if not ENABLE_COST_TRACKING:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        operation = CostInfo(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            timestamp=datetime.now()
        )

        self.operations.append(operation)
        self.daily_totals[today] = self.daily_totals.get(today, 0.0) + cost
        self.total_cost += cost

        logger.info(f"Recorded ${cost:.4f} cost for {provider}/{model}")

    def get_stats(self) -> CostStats:
        """Get current cost statistics"""
        today = datetime.now().strftime("%Y-%m-%d")
        today_cost = self.daily_totals.get(today, 0.0)

        cost_by_provider = {}
        operations_today = 0
        most_expensive = None
        max_cost = 0.0

        for op in self.operations:
            if op.timestamp.strftime("%Y-%m-%d") == today:
                operations_today += 1
                cost_by_provider[op.provider] = cost_by_provider.get(op.provider, 0.0) + op.cost_usd
                if op.cost_usd > max_cost:
                    max_cost = op.cost_usd
                    most_expensive = op

        return CostStats(
            total_cost_today=today_cost,
            total_cost_all_time=self.total_cost,
            daily_budget=DAILY_BUDGET_USD,
            budget_remaining=max(0, DAILY_BUDGET_USD - today_cost),
            operations_today=operations_today,
            most_expensive_operation=most_expensive,
            cost_by_provider=cost_by_provider
        )


# ============================================================================
# FILE WATCH HANDLER
# ============================================================================

class FileWatchHandler(FileSystemEventHandler):
    def __init__(self, rag_service):
        self.rag_service = rag_service

    def on_created(self, event):
        if not event.is_directory:
            logger.info(f"New file detected: {event.src_path}")
            asyncio.create_task(self.rag_service.process_file_from_watch(event.src_path))

# ============================================================================
# MAIN RAG SERVICE
# ============================================================================
# Note: Old LLMService, OCRService, and DocumentProcessor classes removed.
# All functionality now handled by new service layer in src/services/
# ============================================================================

class RAGService:
    def __init__(self):
        # Setup ChromaDB first
        self.setup_chromadb()

        # Initialize new service layer
        if NEW_SERVICES_AVAILABLE:
            logger.info("✅ Using new service layer architecture")
            settings = get_settings()
            self.llm_service = NewLLMService(settings)
            self.vector_service = NewVectorService(collection, settings)
            self.document_service = NewDocumentService(settings)
            self.ocr_service = NewOCRService(languages=['eng', 'deu', 'fra', 'spa'])

            # Initialize tag taxonomy, triage, and advanced enrichment
            self.tag_taxonomy = TagTaxonomyService(collection=collection)
            self.triage_service = SmartTriageService(collection=collection)
            self.enrichment_service = AdvancedEnrichmentService(
                llm_service=self.llm_service,
                tag_taxonomy=self.tag_taxonomy,
                triage_service=self.triage_service
            )

            # Initialize Obsidian export service
            obsidian_output_dir = os.getenv("OBSIDIAN_VAULT_PATH", "./obsidian_vault")
            self.obsidian_service = ObsidianService(
                llm_service=self.llm_service,
                output_dir=obsidian_output_dir
            )

            self.using_new_services = True
            logger.info("✅ Advanced multi-stage enrichment initialized (Groq + Claude + Triage)")
            logger.info(f"✅ Obsidian export enabled → {obsidian_output_dir}")
            logger.info("   - Stage 1: Fast classification (Groq)")
            logger.info("   - Stage 2: Entity extraction (Claude)")
            logger.info("   - Stage 3: OCR quality assessment")
            logger.info("   - Stage 4: Significance scoring")
            logger.info("   - Stage 5: Evolving tag taxonomy")
            logger.info("   - Stage 6: Smart triage & duplicate detection")
        else:
            logger.error("❌ New service layer not available - cannot start!")
            raise RuntimeError("New service layer is required but not available")

    def setup_chromadb(self):
        global chroma_client, collection
        try:
            chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
            chroma_client.heartbeat()

            try:
                collection = chroma_client.get_collection(name=COLLECTION_NAME)
            except:
                collection = chroma_client.create_collection(
                    name=COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"}
                )
            logger.info("Connected to ChromaDB successfully")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            raise

    def _clean_content(self, content: str) -> str:
        """Clean and validate content encoding"""
        import re

        # Remove null bytes and other problematic control characters
        content = content.replace('\x00', '')

        # Remove other control characters except whitespace
        content = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)

        # Ensure valid UTF-8 encoding
        try:
            content = content.encode('utf-8', errors='ignore').decode('utf-8')
        except Exception:
            # Fallback: try latin-1 then convert to utf-8
            try:
                content = content.encode('latin-1').decode('utf-8', errors='ignore')
            except Exception:
                content = str(content)

        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()

        return content

    async def process_document(self,
                             content: str,
                             filename: str = None,
                             document_type: DocumentType = DocumentType.text,
                             process_ocr: bool = False,
                             generate_obsidian: bool = True,
                             file_metadata: Dict[str, Any] = None) -> IngestResponse:
        """Process a document with full enrichment pipeline"""

        # Validate content
        if not content or not content.strip():
            raise ValueError("Document content cannot be empty")

        # Check minimum content length
        if len(content.strip()) < 10:
            raise ValueError("Document content must be at least 10 characters long")

        # Validate and clean content encoding
        content = self._clean_content(content)

        doc_id = str(uuid.uuid4())

        # Check for duplicate content
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        # Search for existing documents with same content hash
        try:
            existing_docs = collection.get(
                where={"content_hash": content_hash},
                limit=1
            )
            if existing_docs and existing_docs['ids']:
                existing_doc_id = existing_docs['ids'][0].split('_chunk_')[0]
                logger.info(f"Duplicate content detected for {filename}. Existing doc: {existing_doc_id}")
                return IngestResponse(
                    success=True,
                    doc_id=existing_doc_id,
                    chunks=len(existing_docs['ids']),
                    metadata={"duplicate": True, "original_filename": filename},
                    obsidian_path=None
                )
        except Exception as e:
            logger.debug(f"Duplicate check failed, proceeding with ingestion: {e}")

        try:
            # ============================================================
            # STEP 1: LLM ENRICHMENT - Extract high-quality metadata
            # ============================================================
            logger.info(f"🤖 Enriching document with LLM: {filename}")
            enriched_metadata = await self.enrichment_service.enrich_document(
                content=content,
                filename=filename or f"document_{doc_id}",
                document_type=document_type,
                existing_metadata=file_metadata
            )

            # Use LLM-improved title
            title = enriched_metadata.get("title", filename or f"document_{doc_id}")
            logger.info(f"✅ Multi-stage enrichment complete: {title}")
            logger.info(f"   📊 Significance: {enriched_metadata.get('significance_score', 0):.2f} ({enriched_metadata.get('quality_tier', 'unknown')})")
            logger.info(f"   🏷️  Tags ({enriched_metadata.get('tag_count', 0)}): {enriched_metadata.get('tags', 'none')[:100]}")
            logger.info(f"   🎯 Domain: {enriched_metadata.get('domain', 'general')}")
            logger.info(f"   👥 Entities: {enriched_metadata.get('people_count', 0)} people, {enriched_metadata.get('organizations_count', 0)} orgs, {enriched_metadata.get('concepts_count', 0)} concepts")
            logger.info(f"   💰 Enrichment cost: ${enriched_metadata.get('enrichment_cost_usd', 0):.6f}")
            if enriched_metadata.get('recommended_for_review', False):
                logger.info(f"   ⚠️  Recommended for manual review (confidence/significance flags)")

            # Split into chunks using new document service
            chunks = self.document_service.chunk_text(content)

            # Create ObsidianMetadata for response (using enriched data)
            # Extract lists from flat metadata
            enriched_lists = self.enrichment_service.extract_enriched_lists(enriched_metadata)

            tags_list = enriched_lists.get("tags", [])
            key_points_list = enriched_lists.get("key_points", [])
            people_list = [p.get("name") if isinstance(p, dict) else p for p in enriched_lists.get("people", [])]
            orgs_list = enriched_lists.get("organizations", [])
            locs_list = enriched_lists.get("locations", [])
            dates_list = enriched_lists.get("dates", [])

            obsidian_metadata = ObsidianMetadata(
                title=title,
                keywords=Keywords(primary=tags_list[:3], secondary=tags_list[3:] if len(tags_list) > 3 else []),
                tags=[f"#{tag}" if not tag.startswith("#") else tag for tag in tags_list],
                summary=enriched_metadata.get("summary", ""),
                abstract=enriched_metadata.get("summary", ""),
                key_points=key_points_list,
                entities=Entities(
                    people=people_list,
                    organizations=orgs_list,
                    locations=locs_list,
                    dates=dates_list
                ),
                reading_time=f"{enriched_metadata.get('estimated_reading_time_min', 1)} min",
                complexity=ComplexityLevel[enriched_metadata.get("complexity", "intermediate")],
                links=[],
                document_type=document_type,
                source=filename or "",
                created_at=datetime.now(),

                # Add enrichment quality metrics
                domain=enriched_metadata.get("domain", "general"),
                significance_score=float(enriched_metadata.get("significance_score", 0.0)),
                quality_tier=enriched_metadata.get("quality_tier", "medium"),
                entity_richness=float(enriched_metadata.get("entity_richness", 0.0)),
                content_depth=float(enriched_metadata.get("content_depth", 0.0)),
                extraction_confidence=float(enriched_metadata.get("extraction_confidence", 0.0)),

                # Add entity counts
                people_count=enriched_metadata.get("people_count", 0),
                organizations_count=enriched_metadata.get("organizations_count", 0),
                concepts_count=enriched_metadata.get("concepts_count", 0),

                # Add triage information
                triage_category=enriched_metadata.get("triage_category", "unknown"),
                triage_confidence=float(enriched_metadata.get("triage_confidence", 0.0)),
                is_duplicate=enriched_metadata.get("is_duplicate", False),
                is_actionable=enriched_metadata.get("is_actionable", False)
            )

            # ============================================================
            # STEP 2: STORE IN CHROMADB - Use enriched metadata
            # ============================================================
            chunk_ids = []
            chunk_metadatas = []
            chunk_contents = []

            # Use enriched metadata for ChromaDB (already flat key-value)
            base_metadata = {
                **enriched_metadata,  # All the LLM-enriched fields
                "doc_id": doc_id,
                "filename": str(filename or f"document_{doc_id}"),
                "chunks": int(len(chunks)),
            }

            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                chunk_metadata = {
                    **base_metadata,
                    "chunk_index": i,
                    "chunk_id": chunk_id
                }

                chunk_ids.append(chunk_id)
                chunk_metadatas.append(chunk_metadata)
                chunk_contents.append(chunk)

            # Add to ChromaDB
            collection.add(
                ids=chunk_ids,
                documents=chunk_contents,
                metadatas=chunk_metadatas
            )

            # ============================================================
            # STEP 3: OBSIDIAN EXPORT (if enabled)
            # ============================================================
            obsidian_path = None
            if generate_obsidian and self.obsidian_service:
                try:
                    logger.info(f"📝 Exporting to Obsidian vault...")
                    file_path, export_data = await self.obsidian_service.export_to_obsidian(
                        doc_id=doc_id,
                        content=content,
                        enriched_metadata=enriched_metadata,
                        document_type=document_type,
                        source=filename or ""
                    )
                    obsidian_path = str(file_path)
                    logger.info(f"✅ Obsidian export: {file_path.name}")
                except Exception as e:
                    logger.warning(f"⚠️ Obsidian export failed: {e}")
                    # Don't fail the whole operation if Obsidian export fails

            logger.info(f"✅ Processed document {doc_id}: {len(chunks)} chunks, Obsidian: {bool(obsidian_path)}")

            return IngestResponse(
                success=True,
                doc_id=doc_id,
                chunks=len(chunks),
                metadata=obsidian_metadata,
                obsidian_path=obsidian_path
            )

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

    async def process_file(self, file_path: str, process_ocr: bool = False, generate_obsidian: bool = True) -> IngestResponse:
        """Process a file from path"""
        try:
            # Extract text using document service
            logger.info(f"🔄 Processing file: {file_path}")
            content, document_type, metadata = await self.document_service.extract_text_from_file(
                file_path,
                process_ocr=process_ocr
            )

            filename = Path(file_path).name

            return await self.process_document(
                content=content,
                filename=filename,
                document_type=document_type,
                process_ocr=process_ocr,
                generate_obsidian=generate_obsidian,
                file_metadata=metadata
            )
        except Exception as e:
            logger.error(f"File processing failed for {file_path}: {e}")
            raise

    async def process_file_from_watch(self, file_path: str):
        """Process file from watch folder and move to processed"""
        try:
            result = await self.process_file(file_path, process_ocr=True, generate_obsidian=True)

            # Move to processed folder
            processed_path = Path(PATHS['processed_path']) / Path(file_path).name
            os.makedirs(PATHS['processed_path'], exist_ok=True)
            shutil.move(file_path, processed_path)

            logger.info(f"Processed and moved file: {file_path} -> {processed_path}")

        except Exception as e:
            logger.error(f"Watch file processing failed for {file_path}: {e}")

    async def search_documents(self, query: str, top_k: int = 5, filter_dict: Dict[str, Any] = None) -> SearchResponse:
        """Search for relevant documents"""
        # Validate search query
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        if len(query.strip()) < 2:
            raise ValueError("Search query must be at least 2 characters long")

        start_time = time.time()

        # Search using vector service
        logger.info(f"🔍 Searching: {query}")
        results_list = await self.vector_service.search(
            query=query,
            top_k=top_k,
            filter=filter_dict
        )

        search_time_ms = (time.time() - start_time) * 1000

        # Convert service format to SearchResult format
        search_results = []
        for result in results_list:
            search_results.append(SearchResult(
                content=result['content'],
                metadata=result['metadata'],
                relevance_score=result['relevance_score'],
                chunk_id=result.get('chunk_id', result['metadata'].get('chunk_id', 'unknown'))
            ))

        return SearchResponse(
            query=query,
            results=search_results,
            total_results=len(search_results),
            search_time_ms=search_time_ms
        )

# Initialize services
rag_service = RAGService()

# Setup file watcher
if ENABLE_FILE_WATCH:
    file_handler = FileWatchHandler(rag_service)
    file_observer = Observer()
    os.makedirs(PATHS['input_path'], exist_ok=True)
    file_observer.schedule(file_handler, PATHS['input_path'], recursive=False)
    file_observer.start()
    logger.info(f"File watcher started for: {PATHS['input_path']}")

# Create data directories
for path in PATHS.values():
    os.makedirs(path, exist_ok=True)

# API Endpoints
@app.get("/health")
async def health_check():
    """Enhanced health check"""
    try:
        chroma_client.heartbeat()

        llm_status = {}
        for provider in LLM_PROVIDERS.keys():
            llm_status[provider] = provider in llm_clients

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "platform": PLATFORM,
            "docker": IS_DOCKER,
            "chromadb": "connected",
            "file_watcher": "enabled" if ENABLE_FILE_WATCH else "disabled",
            "ocr_available": OCR_AVAILABLE,
            "llm_providers": llm_status,
            "paths": PATHS
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")

@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(document: Document, _: bool = Depends(verify_token)):
    """Ingest document via API"""
    try:
        return await rag_service.process_document(
            content=document.content,
            filename=document.filename,
            document_type=document.document_type,
            process_ocr=document.process_ocr,
            generate_obsidian=document.generate_obsidian,
            file_metadata=document.metadata
        )
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    process_ocr: bool = Form(False),
    generate_obsidian: bool = Form(True),
    _: bool = Depends(verify_token)
):
    """Ingest file via upload"""
    logger.info(f"Received file for ingestion: {file.filename}, Content-Type: {file.content_type}")
    try:
        # Save uploaded file temporarily
        temp_path = Path(PATHS['temp_path']) / f"upload_{uuid.uuid4()}_{file.filename}"

        async with aiofiles.open(temp_path, 'wb') as f:
            content = await file.read()
            await f.write(content)

        # Process file
        result = await rag_service.process_file(
            str(temp_path),
            process_ocr=process_ocr,
            generate_obsidian=generate_obsidian
        )

        # Clean up temp file
        temp_path.unlink()

        return result

    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        logger.error(f"File ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest/batch", response_model=List[IngestResponse])
async def ingest_batch_files(
    files: List[UploadFile] = File(...),
    process_ocr: bool = Form(False),
    generate_obsidian: bool = Form(True)
):
    """Batch file ingestion"""
    results = []
    temp_paths = []

    try:
        # Save all files first
        for file in files:
            temp_path = Path(PATHS['temp_path']) / f"batch_{uuid.uuid4()}_{file.filename}"
            temp_paths.append(temp_path)

            async with aiofiles.open(temp_path, 'wb') as f:
                content = await file.read()
                await f.write(content)

        # Process files concurrently
        tasks = []
        for temp_path in temp_paths:
            task = rag_service.process_file(str(temp_path), process_ocr, generate_obsidian)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch processing failed for file {i}: {result}")
                processed_results.append(IngestResponse(
                    success=False,
                    doc_id="",
                    chunks=0,
                    metadata=ObsidianMetadata(title=f"Failed: {files[i].filename}")
                ))
            else:
                processed_results.append(result)

        return processed_results

    finally:
        # Clean up temp files
        for temp_path in temp_paths:
            if temp_path.exists():
                temp_path.unlink()

@app.post("/search", response_model=SearchResponse)
async def search_documents(query: Query):
    """Search documents"""
    try:
        return await rag_service.search_documents(
            query=query.text,
            top_k=query.top_k,
            filter_dict=query.filter
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents", response_model=List[DocumentInfo])
async def list_documents():
    """List all documents"""
    try:
        results = collection.get()

        docs = {}
        for metadata in results['metadatas']:
            doc_id = metadata.get('doc_id')
            if doc_id and doc_id not in docs:
                # Find Obsidian file
                obsidian_path = None
                title = metadata.get('title', metadata.get('filename', ''))
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = re.sub(r'\s+', '_', safe_title)
                potential_path = Path(PATHS['obsidian_path']) / f"{safe_title}_{doc_id[:8]}.md"
                if potential_path.exists():
                    obsidian_path = str(potential_path)

                docs[doc_id] = DocumentInfo(
                    id=doc_id,
                    filename=metadata.get('filename', ''),
                    chunks=metadata.get('chunks', 0),
                    created_at=metadata.get('created_at', ''),
                    metadata=metadata,
                    obsidian_path=obsidian_path
                )

        return list(docs.values())

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete document and associated files"""
    try:
        # Get document info first
        results = collection.get(where={"doc_id": doc_id})
        if not results['ids']:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete from ChromaDB
        collection.delete(where={"doc_id": doc_id})

        # Delete Obsidian files
        obsidian_files = list(Path(PATHS['obsidian_path']).glob(f"*_{doc_id[:8]}.md"))
        for md_file in obsidian_files:
            md_file.unlink()
            logger.info(f"Deleted Obsidian file: {md_file}")

        return {"success": True, "message": f"Document {doc_id} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats", response_model=Stats)
async def get_stats():
    """Get enhanced system statistics"""
    try:
        results = collection.get()

        doc_ids = set()
        last_ingestion = None

        for metadata in results['metadatas']:
            doc_id = metadata.get('doc_id')
            if doc_id:
                doc_ids.add(doc_id)

            created_at = metadata.get('created_at')
            if created_at:
                if not last_ingestion or created_at > last_ingestion:
                    last_ingestion = created_at

        # Calculate storage
        total_chars = sum(len(doc) for doc in results['documents'])
        storage_mb = total_chars / (1024 * 1024)

        # LLM provider status
        llm_status = {}
        for provider in LLM_PROVIDERS.keys():
            llm_status[provider] = provider in llm_clients

        return Stats(
            total_documents=len(doc_ids),
            total_chunks=len(results['ids']),
            storage_used_mb=round(storage_mb, 2),
            last_ingestion=last_ingestion,
            llm_provider_status=llm_status,
            ocr_available=OCR_AVAILABLE
        )

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-llm")
async def test_llm_provider(request: TestLLMRequest, _: bool = Depends(verify_token)):
    """Test LLM provider or specific model"""
    try:
        # Check if any LLM providers are available
        if not llm_clients:
            raise HTTPException(
                status_code=503,
                detail="No LLM providers are configured with valid API keys. Please set your API keys in the .env file."
            )

        llm_service = LLMService()

        if request.model:
            # Test specific model
            response, cost = await llm_service.call_llm_with_model(request.prompt, request.model.value)
            return {
                "model": request.model.value,
                "prompt": request.prompt,
                "response": response,
                "cost_usd": cost,
                "success": True
            }
        elif request.provider:
            # Test provider with default model
            response = await llm_service.call_llm(request.prompt, request.provider.value)
            return {
                "provider": request.provider.value,
                "prompt": request.prompt,
                "response": response,
                "success": True
            }
        else:
            # Test default fallback chain
            response = await llm_service.call_llm(request.prompt)
            return {
                "provider": "fallback_chain",
                "prompt": request.prompt,
                "response": response,
                "success": True
            }
    except Exception as e:
        return {
            "provider": request.provider.value if request.provider else "unknown",
            "model": request.model.value if request.model else None,
            "prompt": request.prompt,
            "error": str(e),
            "success": False
        }

@app.get("/cost-stats", response_model=CostStats)
async def get_cost_stats():
    """Get cost tracking statistics"""
    try:
        cost_tracker = CostTracker()
        return cost_tracker.get_stats()
    except Exception as e:
        logger.error(f"Failed to get cost stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
async def list_available_models():
    """List all available LLM models with their pricing"""
    available_models = []

    for provider, config in LLM_PROVIDERS.items():
        if config["api_key"] and provider in llm_clients:
            for model_id, model_config in config.get("models", {}).items():
                pricing = MODEL_PRICING.get(model_id, {"input": 0, "output": 0})
                available_models.append({
                    "model_id": model_id,
                    "provider": provider,
                    "model_name": model_config["model_name"],
                    "max_tokens": model_config["max_tokens"],
                    "pricing_per_1m_tokens": pricing,
                    "available": True
                })

    return {
        "available_models": available_models,
        "total_models": len(available_models),
        "providers": list(llm_clients.keys())
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_with_rag(request: ChatRequest):
    """Chat endpoint with RAG functionality - combines search with LLM-powered answer generation"""
    start_time = time.time()

    try:
        # Import reranking service
        from src.services.reranking_service import get_reranking_service

        # Step 1: Search for relevant context (retrieve more for reranking)
        rag_service = RAGService()
        # Retrieve 3x more results for reranking
        initial_results_count = request.max_context_chunks * 3
        search_query = Query(
            text=request.question,
            top_k=initial_results_count
        )

        search_response = await search_documents(search_query)

        if not search_response.results:
            # No relevant context found
            return ChatResponse(
                question=request.question,
                answer="I don't have any relevant information in my knowledge base to answer your question. Please try rephrasing your question or ensure relevant documents have been ingested.",
                sources=[],
                llm_provider_used="none",
                total_chunks_found=0,
                response_time_ms=round((time.time() - start_time) * 1000, 2)
            )

        # Step 1.5: Rerank results for better relevance
        reranker = get_reranking_service()

        # Convert SearchResult objects to dicts for reranking
        results_for_reranking = []
        for result in search_response.results:
            results_for_reranking.append({
                'content': result.content,
                'metadata': result.metadata,
                'relevance_score': result.relevance_score,
                'chunk_id': result.chunk_id
            })

        # Rerank and take top K
        reranked_results = reranker.rerank(
            query=request.question,
            results=results_for_reranking,
            top_k=request.max_context_chunks
        )

        logger.info(f"🎯 Reranking: {len(results_for_reranking)} → {len(reranked_results)} results")

        # Step 2: Prepare context from reranked results
        context_chunks = []
        for result in reranked_results:
            context_chunks.append(f"Source: {result['metadata'].get('filename', 'Unknown')}\nContent: {result['content']}")

        context = "\n\n---\n\n".join(context_chunks)

        # Step 3: Create RAG prompt
        rag_prompt = f"""You are an AI assistant that answers questions based on the provided context. Use only the information from the context to answer the question. If the context doesn't contain enough information to answer the question, say so clearly.

Context:
{context}

Question: {request.question}

Instructions:
- Answer based solely on the provided context
- Be accurate and specific
- If the context is insufficient, clearly state that
- Cite relevant parts of the context when possible
- Keep your answer concise but complete

Answer:"""

        # Step 4: Generate answer using LLM
        cost = 0.0
        model_used = None

        # Generate answer using LLM service
        logger.info(f"💬 Generating chat response")
        try:
            # Determine which model to use
            model_to_use = request.llm_model.value if request.llm_model else None

            # LLMService.call_llm returns (response, cost, model_used)
            answer, cost, model_used = await rag_service.llm_service.call_llm(
                prompt=rag_prompt,
                model_id=model_to_use
            )
            provider_used = model_used.split('/')[0] if '/' in model_used else "unknown"

        except Exception as e:
            logger.error(f"LLM service failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")

        # Step 5: Prepare response - convert reranked results back to SearchResult objects
        if request.include_sources:
            sources = []
            for reranked in reranked_results:
                sources.append(SearchResult(
                    content=reranked['content'],
                    metadata=reranked['metadata'],
                    relevance_score=reranked.get('rerank_score', reranked.get('relevance_score', 0.0)),
                    chunk_id=reranked['chunk_id']
                ))
        else:
            sources = []

        response_time = round((time.time() - start_time) * 1000, 2)

        return ChatResponse(
            question=request.question,
            answer=answer,
            sources=sources,
            llm_provider_used=provider_used,
            llm_model_used=model_used,
            total_chunks_found=search_response.total_results,
            response_time_ms=response_time,
            cost_usd=cost if cost > 0 else None
        )

    except Exception as e:
        logger.error(f"Chat endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@app.post("/admin/cleanup-corrupted")
async def cleanup_corrupted_documents():
    """Remove documents with corrupted or binary content"""
    try:
        all_docs = collection.get()

        if not all_docs or not all_docs['documents']:
            return {"removed_corrupted": 0, "message": "No documents found"}

        corrupted_ids = []
        for i, doc_content in enumerate(all_docs['documents']):
            if doc_content:
                # Check for binary content indicators
                if (len(doc_content) > 100 and
                    (doc_content.count('\x00') > 0 or
                     doc_content.count('\ufffd') > 0 or  # replacement character
                     len([c for c in doc_content if ord(c) < 32 and c not in '\t\n\r']) > len(doc_content) * 0.1)):
                    corrupted_ids.append(all_docs['ids'][i])

        if corrupted_ids:
            rag_service.collection.delete(ids=corrupted_ids)
            logger.info(f"Removed {len(corrupted_ids)} corrupted documents")

        return {
            "removed_corrupted": len(corrupted_ids),
            "message": f"Successfully removed {len(corrupted_ids)} corrupted documents"
        }

    except Exception as e:
        logger.error(f"Corruption cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.post("/admin/cleanup-duplicates")
async def cleanup_duplicates():
    """Remove duplicate documents based on content hash"""
    try:
        # Get all documents grouped by content_hash
        all_docs = collection.get()

        if not all_docs or not all_docs['metadatas']:
            return {"removed_duplicates": 0, "message": "No documents found"}

        # Group by content_hash
        hash_groups = {}
        for i, metadata in enumerate(all_docs['metadatas']):
            content_hash = metadata.get('content_hash')
            if content_hash:
                if content_hash not in hash_groups:
                    hash_groups[content_hash] = []
                hash_groups[content_hash].append({
                    'id': all_docs['ids'][i],
                    'metadata': metadata,
                    'index': i
                })

        # Find duplicates (groups with more than 1 document)
        duplicates_removed = 0
        for content_hash, docs in hash_groups.items():
            if len(docs) > 1:
                # Keep the first one, remove the rest
                docs_to_remove = docs[1:]  # Remove all except the first
                ids_to_remove = [doc['id'] for doc in docs_to_remove]

                try:
                    collection.delete(ids=ids_to_remove)
                    duplicates_removed += len(ids_to_remove)
                    logger.info(f"Removed {len(ids_to_remove)} duplicates for hash {content_hash}")
                except Exception as e:
                    logger.error(f"Failed to remove duplicates for hash {content_hash}: {e}")

        return {
            "removed_duplicates": duplicates_removed,
            "message": f"Successfully removed {duplicates_removed} duplicate documents"
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def web_interface():
    """Simple web interface for file upload"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>RAG Service - File Upload</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .upload-area { border: 2px dashed #ccc; padding: 40px; text-align: center; margin: 20px 0; }
            .upload-area:hover { background-color: #f9f9f9; }
            .form-group { margin: 10px 0; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .results { margin-top: 20px; padding: 10px; background: #f8f9fa; border-radius: 5px; }
            .checkbox-group { display: flex; gap: 20px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>RAG Service - Enhanced Document Processing</h1>

        <div class="upload-area" onclick="document.getElementById('fileInput').click()">
            <p>Click here or drag files to upload</p>
            <input type="file" id="fileInput" multiple style="display: none;">
        </div>

        <div class="checkbox-group">
            <label><input type="checkbox" id="processOCR"> Enable OCR Processing</label>
            <label><input type="checkbox" id="generateObsidian" checked> Generate Obsidian Markdown</label>
        </div>

        <button onclick="uploadFiles()">Upload and Process</button>

        <div id="results" class="results" style="display: none;"></div>

        <script>
            async function uploadFiles() {
                const files = document.getElementById('fileInput').files;
                if (files.length === 0) {
                    alert('Please select files first');
                    return;
                }

                const formData = new FormData();
                for (let file of files) {
                    formData.append('files', file);
                }
                formData.append('process_ocr', document.getElementById('processOCR').checked);
                formData.append('generate_obsidian', document.getElementById('generateObsidian').checked);

                document.getElementById('results').innerHTML = 'Processing...';
                document.getElementById('results').style.display = 'block';

                try {
                    const endpoint = files.length === 1 ? '/ingest/file' : '/ingest/batch';
                    const response = await fetch(endpoint, {
                        method: 'POST',
                        body: formData
                    });

                    const result = await response.json();

                    if (response.ok) {
                        let html = '<h3>Processing Complete!</h3>';
                        const results = Array.isArray(result) ? result : [result];

                        for (let res of results) {
                            html += `<div style="margin: 10px 0; padding: 10px; border: 1px solid #ddd;">`;
                            html += `<strong>Document:</strong> ${res.metadata.title}<br>`;
                            html += `<strong>Chunks:</strong> ${res.chunks}<br>`;
                            html += `<strong>Type:</strong> ${res.metadata.document_type}<br>`;
                            if (res.obsidian_path) {
                                html += `<strong>Obsidian File:</strong> ${res.obsidian_path}<br>`;
                            }
                            html += `<strong>Summary:</strong> ${res.metadata.summary}<br>`;
                            html += `</div>`;
                        }

                        document.getElementById('results').innerHTML = html;
                    } else {
                        document.getElementById('results').innerHTML = `<p style="color: red;">Error: ${result.detail}</p>`;
                    }
                } catch (error) {
                    document.getElementById('results').innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
                }
            }

            // Drag and drop support
            const uploadArea = document.querySelector('.upload-area');

            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.style.backgroundColor = '#f0f0f0';
            });

            uploadArea.addEventListener('dragleave', () => {
                uploadArea.style.backgroundColor = '';
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.style.backgroundColor = '';
                document.getElementById('fileInput').files = e.dataTransfer.files;
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Enhanced RAG Integration
try:
    import sys
    sys.path.append('/home/danielt/mygit/rag-provider')
    from production_enhanced_retrieval import ProductionEnhancedRAG

    # Initialize enhanced RAG service
    enhanced_rag = None

    @app.post("/search/enhanced")
    async def enhanced_search_endpoint(request: dict):
        """Enhanced search with hybrid retrieval and reranking"""
        global enhanced_rag

        if enhanced_rag is None:
            enhanced_rag = ProductionEnhancedRAG()
            await enhanced_rag.initialize()

        query = request.get('text', '')
        top_k = request.get('top_k', 5)
        use_hybrid = request.get('use_hybrid', True)
        use_reranker = request.get('use_reranker', True)

        if not query or not query.strip():
            return {"error": "Search query cannot be empty"}

        try:
            result = await enhanced_rag.enhanced_search(
                query=query,
                top_k=top_k,
                use_hybrid=use_hybrid,
                use_reranker=use_reranker
            )
            return result
        except Exception as e:
            logger.error(f"Enhanced search failed: {e}")
            return {"error": str(e)}

    @app.post("/chat/enhanced")
    async def enhanced_chat_endpoint(request: dict):
        """Enhanced RAG chat with improved retrieval"""
        global enhanced_rag

        if enhanced_rag is None:
            enhanced_rag = ProductionEnhancedRAG()
            await enhanced_rag.initialize()

        question = request.get('question', '')
        max_context_chunks = request.get('max_context_chunks', 5)
        use_hybrid = request.get('use_hybrid', True)
        use_reranker = request.get('use_reranker', True)

        if not question or not question.strip():
            return {"error": "Question cannot be empty"}

        try:
            result = await enhanced_rag.enhanced_chat(
                question=question,
                max_context_chunks=max_context_chunks,
                use_hybrid=use_hybrid,
                use_reranker=use_reranker
            )
            return result
        except Exception as e:
            logger.error(f"Enhanced chat failed: {e}")
            return {"error": str(e)}

    @app.post("/triage/document")
    async def document_quality_triage(file: UploadFile = File(...)):
        """Analyze document quality and suggest improvements"""
        global enhanced_rag

        if enhanced_rag is None:
            enhanced_rag = ProductionEnhancedRAG()
            await enhanced_rag.initialize()

        try:
            content = await file.read()
            text_content = content.decode('utf-8', errors='ignore')

            result = await enhanced_rag.triage_document_quality(text_content)
            return result
        except Exception as e:
            logger.error(f"Document triage failed: {e}")
            return {"error": str(e)}

    @app.get("/search/config")
    async def get_enhanced_search_config():
        """Get enhanced search configuration"""
        global enhanced_rag

        if enhanced_rag is None:
            enhanced_rag = ProductionEnhancedRAG()
            await enhanced_rag.initialize()

        return {
            'hybrid_retrieval': {
                'dense_weight': enhanced_rag.dense_weight,
                'sparse_weight': enhanced_rag.sparse_weight,
                'initialized': enhanced_rag.initialized
            },
            'reranker': {
                'model': 'production-hybrid-scorer',
                'available': True
            },
            'triage': {
                'quality_levels': ['excellent', 'good', 'fair', 'poor', 'unusable'],
                'ocr_enabled': True,
                'cloud_ocr_fallbacks': ['google_vision', 'azure_cv', 'aws_textract']
            }
        }

    @app.post("/admin/initialize-enhanced")
    async def initialize_enhanced_search():
        """Initialize enhanced search with current documents"""
        global enhanced_rag

        try:
            enhanced_rag = ProductionEnhancedRAG()
            await enhanced_rag.initialize()

            return {
                "success": True,
                "message": "Enhanced RAG initialized successfully",
                "features": ["hybrid_retrieval", "reranking", "quality_triage", "cloud_ocr"]
            }
        except Exception as e:
            logger.error(f"Enhanced RAG initialization failed: {e}")
            return {"error": str(e)}

except ImportError as e:
    logger.warning(f"Enhanced RAG features not available: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if ENABLE_FILE_WATCH and file_observer:
        file_observer.stop()
        file_observer.join()

    executor.shutdown(wait=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)