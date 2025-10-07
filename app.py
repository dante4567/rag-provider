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

# Initialize structured logging FIRST
from src.core.logging_config import init_app_logging, get_logger, set_request_id, get_request_id
from src.core.rate_limiting import get_default_limiter, get_api_key_limiter
init_app_logging()
logger = get_logger(__name__)
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
    from src.services.tag_taxonomy_service import TagTaxonomyService
    from src.services.smart_triage_service import SmartTriageService
    from src.services.obsidian_service import ObsidianService
    from src.services.vocabulary_service import VocabularyService
    from src.services.chunking_service import ChunkingService
    from src.services.quality_scoring_service import QualityScoringService

    NEW_SERVICES_AVAILABLE = True
except ImportError as e:
    NEW_SERVICES_AVAILABLE = False
    logging.warning(f"New service layer not available: {e}")

# Import schemas from centralized models file
from src.models.schemas import (
    DocumentType, LLMProvider, LLMModel, ComplexityLevel,
    Keywords, Entities, ObsidianMetadata, Document,
    EnrichmentSettings, IngestResponse, SearchResult, SearchResponse,
    DocumentInfo, Stats, Query, ChatRequest, ChatResponse,
    CostInfo, CostStats, TestLLMRequest
)

# Import route modules
from src.routes import health, ingest, search, stats, chat, admin, email_threading, evaluation, monitoring

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

# Enrichment Configuration
USE_ENRICHMENT_V2 = os.getenv("USE_ENRICHMENT_V2", "true").lower() == "true"
VOCABULARY_DIR = os.getenv("VOCABULARY_DIR", "vocabulary")

# Obsidian Configuration V3 (RAG-first format)
USE_OBSIDIAN_V3 = os.getenv("USE_OBSIDIAN_V3", "true").lower() == "true"

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

# Include routers
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(email_threading.router)
app.include_router(evaluation.router)
app.include_router(monitoring.router)

# Logging middleware - tracks all requests with timing
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests with timing and request ID"""
    # Generate request ID
    request_id = set_request_id()

    # Start timer
    start_time = time.time()

    # Log incoming request
    logger.info(f"→ {request.method} {request.url.path}")

    try:
        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        logger.info(
            f"← {request.method} {request.url.path} -> {response.status_code} ({duration_ms:.2f}ms)"
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    except Exception as e:
        # Log errors
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"← {request.method} {request.url.path} -> ERROR ({duration_ms:.2f}ms): {str(e)}",
            exc_info=True
        )
        raise

# Rate limiting middleware - protect against DoS attacks
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limit requests based on IP and API key"""
    from fastapi.responses import JSONResponse

    # Skip rate limiting for public endpoints
    if request.url.path in PUBLIC_ENDPOINTS:
        return await call_next(request)

    # Determine identifier (API key if present, otherwise IP)
    api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")

    if api_key and api_key == API_KEY:
        # Authenticated with valid API key - use generous limits
        identifier = f"key:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
        limiter = get_api_key_limiter()
    else:
        # Unauthenticated or invalid key - use strict limits
        identifier = f"ip:{request.client.host}"
        limiter = get_default_limiter()

    # Check rate limit
    allowed, limit_type, retry_after = limiter.check_rate_limit(identifier)

    if not allowed:
        logger.warning(f"Rate limit exceeded: {identifier} ({limit_type}, retry in {retry_after:.1f}s)")
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "limit_type": limit_type,
                "retry_after": retry_after,
                "message": f"Too many requests. Please wait {retry_after:.1f} seconds."
            },
            headers={"Retry-After": str(int(retry_after) + 1)}
        )

    return await call_next(request)

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

            # Initialize supporting services
            self.tag_taxonomy = TagTaxonomyService(collection=collection)
            self.triage_service = SmartTriageService(collection=collection)

            # Initialize vocabulary and enrichment service (formerly V2)
            self.vocabulary_service = VocabularyService("vocabulary")
            self.enrichment_service = EnrichmentService(
                llm_service=self.llm_service,
                vocab_service=self.vocabulary_service
            )

            # Initialize structure-aware chunking
            self.chunking_service = ChunkingService(
                target_size=512,    # ~512 tokens per chunk
                min_size=100,       # Minimum chunk size
                max_size=800,       # Maximum chunk size
                overlap=50          # Token overlap between chunks
            )

            # Initialize Obsidian export service (formerly V3 - RAG-first)
            obsidian_output_dir = os.getenv("OBSIDIAN_VAULT_PATH", "./obsidian_vault")
            self.obsidian_service = ObsidianService(
                output_dir=obsidian_output_dir,
                refs_dir=f"{obsidian_output_dir}/refs"
            )

            # Initialize quality scoring service (blueprint do_index gates)
            self.quality_scoring_service = QualityScoringService()

            self.using_new_services = True
            logger.info("✅ EnrichmentService initialized with controlled vocabulary")
            logger.info(f"   📚 Topics: {len(self.vocabulary_service.get_all_topics())}")
            logger.info(f"   🏗️  Projects: {len(self.vocabulary_service.get_active_projects())}")
            logger.info(f"   📍 Places: {len(self.vocabulary_service.get_all_places())}")
            logger.info("✅ Structure-aware chunking enabled (ignores RAG:IGNORE blocks)")
            logger.info(f"✅ ObsidianService initialized (RAG-first format) → {obsidian_output_dir}")
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

        # Remove excessive whitespace WITHIN lines, but preserve newlines
        # This is critical for structure-aware chunking
        lines = content.split('\n')
        cleaned_lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in lines]
        content = '\n'.join(cleaned_lines)

        # Remove excessive blank lines (more than 2 consecutive)
        content = re.sub(r'\n{3,}', '\n\n', content)
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

            # Use V2 enrichment if available, otherwise fall back to standard
            logger.info("   📊 Enriching with controlled vocabulary")
            # Extract date from file metadata if available
            from datetime import date as date_type
            created_date = None
            if file_metadata and 'created_date' in file_metadata:
                try:
                    created_date = date_type.fromisoformat(file_metadata['created_date'])
                except:
                    pass

            enriched_metadata = await self.enrichment_service.enrich_document(
                content=content,
                filename=filename or f"document_{doc_id}",
                document_type=document_type,
                created_at=created_date,
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

            # ============================================================
            # QUALITY GATES - Blueprint do_index scoring
            # ============================================================
            try:
                # Get existing document count for novelty scoring
                existing_docs_count = collection.count()

                # Extract watchlists from vocabulary service (if available)
                watchlist_people = None
                watchlist_projects = None
                watchlist_topics = None
                if hasattr(self, 'vocabulary_service'):
                    try:
                        # Get active projects as watchlist
                        watchlist_projects = [p['name'] for p in self.vocabulary_service.get_active_projects()]
                    except:
                        pass

                # Calculate quality scores
                quality_scores = self.quality_scoring_service.score_document(
                    content=content,
                    document_type=document_type,
                    metadata=enriched_metadata,
                    existing_docs_count=existing_docs_count,
                    watchlist_people=watchlist_people,
                    watchlist_projects=watchlist_projects,
                    watchlist_topics=watchlist_topics
                )

                # Add quality scores to metadata
                enriched_metadata.update({
                    "quality_score": quality_scores["quality_score"],
                    "novelty_score": quality_scores["novelty_score"],
                    "actionability_score": quality_scores["actionability_score"],
                    "signalness": quality_scores["signalness"],
                    "do_index": quality_scores["do_index"]
                })

                logger.info(f"   🎯 Quality Scores: Q={quality_scores['quality_score']:.2f} N={quality_scores['novelty_score']:.2f} A={quality_scores['actionability_score']:.2f} → Signal={quality_scores['signalness']:.2f}")

                # Check quality gate
                if not quality_scores["do_index"]:
                    logger.warning(f"   ⛔ Document GATED (not indexed): {quality_scores.get('gate_reason', 'Failed quality threshold')}")

                    # Create minimal ObsidianMetadata for gated documents
                    gated_metadata = ObsidianMetadata(
                        title=enriched_metadata.get("title", filename or f"document_{doc_id}"),
                        keywords=Keywords(primary=[], secondary=[]),
                        entities=Entities(people=[], organizations=[], locations=[]),
                        document_type=document_type,
                        source=filename or "",
                        created_at=datetime.now()
                    )
                    gated_response_metadata = gated_metadata.model_dump() if hasattr(gated_metadata, 'model_dump') else gated_metadata.dict()
                    gated_response_metadata.update({
                        "gated": True,
                        "gate_reason": quality_scores.get("gate_reason"),
                        "quality_score": quality_scores["quality_score"],
                        "signalness": quality_scores["signalness"],
                        "enrichment_version": enriched_metadata.get("enrichment_version", "2.0")
                    })

                    return IngestResponse(
                        success=True,
                        doc_id=doc_id,
                        chunks=0,
                        metadata=gated_response_metadata,
                        obsidian_path=None
                    )
                else:
                    logger.info(f"   ✅ Quality gate passed - proceeding with indexing")

            except Exception as e:
                logger.warning(f"   ⚠️  Quality scoring failed, proceeding with indexing: {e}")
                # Add default scores if quality scoring fails
                enriched_metadata.update({
                    "quality_score": 0.8,
                    "novelty_score": 0.7,
                    "actionability_score": 0.5,
                    "signalness": 0.7,
                    "do_index": True
                })

            # Split into chunks using structure-aware chunking if available
            if self.chunking_service:
                logger.info("   📐 Using structure-aware chunking...")
                chunk_dicts = self.chunking_service.chunk_text(content, preserve_structure=True)
                # Extract just the content strings for backward compatibility
                chunks = [c['content'] for c in chunk_dicts]
                # Store full chunk metadata for later use
                chunk_metadata_list = chunk_dicts
                logger.info(f"   ✅ Created {len(chunks)} structure-aware chunks")
            else:
                logger.info("   Using standard text splitting...")
                chunks = self.document_service.chunk_text(content)
                # Create basic metadata for backward compatibility
                chunk_metadata_list = [
                    {
                        'content': chunk,
                        'metadata': {'chunk_type': 'paragraph'},
                        'sequence': i,
                        'estimated_tokens': len(chunk) // 4
                    }
                    for i, chunk in enumerate(chunks)
                ]

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

            # Sanitize enriched metadata for ChromaDB (remove None values)
            sanitized_enriched = {
                k: v for k, v in enriched_metadata.items()
                if v is not None and isinstance(v, (str, int, float, bool))
            }

            # Use enriched metadata for ChromaDB (already flat key-value)
            base_metadata = {
                **sanitized_enriched,  # All the LLM-enriched fields (sanitized)
                "doc_id": doc_id,
                "filename": str(filename or f"document_{doc_id}"),
                "chunks": int(len(chunks)),
            }

            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"

                # Get structure metadata for this chunk
                chunk_struct_meta = chunk_metadata_list[i]['metadata']

                # Safely extract parent_sections (might be strings or dicts)
                parent_secs = chunk_struct_meta.get('parent_sections', [])
                if parent_secs and isinstance(parent_secs[0], dict):
                    # Extract titles from dict format
                    parent_secs_str = ','.join(p.get('title', str(p)) for p in parent_secs)
                else:
                    # Already strings
                    parent_secs_str = ','.join(str(p) for p in parent_secs)

                chunk_metadata = {
                    **base_metadata,
                    "chunk_index": i,
                    "chunk_id": chunk_id,
                    # Add structure-aware metadata
                    "chunk_type": chunk_struct_meta.get('chunk_type', 'paragraph'),
                    "section_title": chunk_struct_meta.get('section_title') or '',
                    "parent_sections": parent_secs_str,
                    "estimated_tokens": chunk_metadata_list[i].get('estimated_tokens', 0)
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
            if generate_obsidian:
                try:
                    logger.info(f"📝 Exporting to Obsidian vault (RAG-first format)...")
                    file_path = self.obsidian_service.export_document(
                        title=title,
                        content=content,
                        metadata=enriched_metadata,
                        document_type=document_type,
                        created_at=datetime.now(),
                        source=filename or "rag_pipeline"
                    )
                    obsidian_path = str(file_path)
                    logger.info(f"✅ Obsidian export: {file_path.name}")
                    logger.info(f"   📁 Entity stubs created in refs/")
                except Exception as e:
                    logger.warning(f"⚠️ Obsidian export failed: {e}")
                    import traceback
                    traceback.print_exc()
                    # Don't fail the whole operation if Obsidian export fails

            logger.info(f"✅ Processed document {doc_id}: {len(chunks)} chunks, Obsidian: {bool(obsidian_path)}")

            # Convert obsidian_metadata to dict and add enrichment_version
            response_metadata = obsidian_metadata.model_dump() if hasattr(obsidian_metadata, 'model_dump') else obsidian_metadata.dict()
            response_metadata["enrichment_version"] = enriched_metadata.get("enrichment_version", "2.0")

            return IngestResponse(
                success=True,
                doc_id=doc_id,
                chunks=len(chunks),
                metadata=response_metadata,
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

# Root web interface endpoint
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