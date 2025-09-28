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

class LLMService:
    """Manages multiple LLM providers with fallback and cost tracking"""

    def __init__(self):
        self.provider_order = [DEFAULT_LLM, FALLBACK_LLM, EMERGENCY_LLM]
        self.cost_tracker = CostTracker()

    def get_model_info(self, model_id: str) -> tuple[str, dict]:
        """Extract provider and model config from model ID"""
        provider = model_id.split('/')[0]
        if provider in LLM_PROVIDERS and model_id in LLM_PROVIDERS[provider]["models"]:
            return provider, LLM_PROVIDERS[provider]["models"][model_id]
        return None, None

    async def call_llm_with_model(self, prompt: str, model_id: str, max_tokens: int = None) -> tuple[str, float]:
        """Call LLM with specific model and return response with cost"""
        if not self.cost_tracker.check_budget():
            raise Exception("Daily budget limit reached")

        provider, model_config = self.get_model_info(model_id)
        if not provider or provider not in llm_clients:
            raise Exception(f"Model {model_id} not available")

        try:
            client = llm_clients[provider]
            tokens = max_tokens or model_config["max_tokens"]
            model_name = model_config["model_name"]

            # Estimate input tokens
            input_tokens = self.cost_tracker.estimate_tokens(prompt)

            if provider == "anthropic":
                response = client.messages.create(
                    model=model_name,
                    max_tokens=tokens,
                    temperature=LLM_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.content[0].text
                output_tokens = self.cost_tracker.estimate_tokens(result)

            elif provider in ["openai", "groq"]:
                response = client.chat.completions.create(
                    model=model_name,
                    max_tokens=tokens,
                    temperature=LLM_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.choices[0].message.content
                output_tokens = self.cost_tracker.estimate_tokens(result)

            elif provider == "google":
                response = client.generate_content(prompt)
                result = response.text
                output_tokens = self.cost_tracker.estimate_tokens(result)

            # Calculate and record cost
            cost = self.cost_tracker.calculate_cost(model_id, input_tokens, output_tokens)
            self.cost_tracker.record_operation(provider, model_id, input_tokens, output_tokens, cost)

            return result, cost

        except Exception as e:
            logger.warning(f"LLM {provider}/{model_id} failed: {e}")
            raise

    async def call_llm(self, prompt: str, provider: str = None, max_tokens: int = None) -> str:
        """Call LLM with fallback support (legacy method)"""
        providers_to_try = [provider] if provider else self.provider_order

        for llm_provider in providers_to_try:
            if llm_provider not in llm_clients:
                continue

            # Use default model for the provider
            provider_config = LLM_PROVIDERS.get(llm_provider, {})
            models = provider_config.get("models", {})
            if not models:
                continue

            default_model = list(models.keys())[0]  # Use first model as default

            try:
                result, cost = await self.call_llm_with_model(prompt, default_model, max_tokens)
                return result
            except Exception as e:
                logger.warning(f"LLM {llm_provider} failed: {e}")
                continue

        raise Exception("All LLM providers failed")

class OCRService:
    """Handles OCR processing for scanned documents"""

    @staticmethod
    def extract_text_from_image(image_path: str, languages: List[str] = None) -> str:
        """Extract text from image using Tesseract"""
        if not OCR_AVAILABLE:
            raise Exception("OCR dependencies not available")

        try:
            lang_codes = "+".join(languages or OCR_LANGUAGES)
            text = pytesseract.image_to_string(
                Image.open(image_path),
                lang=lang_codes,
                config='--psm 6'
            )
            return text.strip()
        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
            return ""

    @staticmethod
    def extract_text_from_pdf_images(pdf_path: str) -> str:
        """Convert PDF pages to images and extract text"""
        if not OCR_AVAILABLE:
            raise Exception("OCR dependencies not available")

        try:
            pages = convert_from_path(pdf_path, dpi=300)
            extracted_text = ""

            for i, page in enumerate(pages):
                temp_image_path = f"/tmp/page_{i}.png"
                page.save(temp_image_path, 'PNG')

                page_text = OCRService.extract_text_from_image(temp_image_path)
                extracted_text += f"\n\n--- Page {i+1} ---\n{page_text}"

                os.unlink(temp_image_path)

            return extracted_text.strip()
        except Exception as e:
            logger.error(f"PDF OCR failed for {pdf_path}: {e}")
            return ""

class WhatsAppParser:
    """Parses WhatsApp chat exports"""

    @staticmethod
    def parse_whatsapp_export(content: str) -> tuple[List[Dict], str, Dict]:
        """Parse WhatsApp chat export into structured messages"""

        # Various WhatsApp timestamp patterns
        patterns = [
            r'(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?) - ([^:]+): (.*)',  # US format
            r'(\d{1,2}\.\d{1,2}\.\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?) - ([^:]+): (.*)',  # EU format
            r'(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}(?::\d{2})?) - ([^:]+): (.*)',  # ISO format
            r'\[(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?)\] ([^:]+): (.*)'  # Bracket format
        ]

        messages = []
        participants = set()

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                timestamp_str, sender, message = match.groups()

                try:
                    timestamp = date_parser.parse(timestamp_str)
                except:
                    timestamp = datetime.now()

                participants.add(sender.strip())
                messages.append({
                    "timestamp": timestamp,
                    "sender": sender.strip(),
                    "message": message.strip(),
                    "type": "whatsapp_message"
                })

        # Sort by timestamp
        messages.sort(key=lambda x: x["timestamp"])

        # Generate conversation summary
        summary = WhatsAppParser._generate_conversation_summary(messages, participants)

        metadata = {
            "total_messages": len(messages),
            "participants": list(participants),
            "date_range": {
                "start": messages[0]["timestamp"].isoformat() if messages else None,
                "end": messages[-1]["timestamp"].isoformat() if messages else None
            },
            "conversation_type": "whatsapp_chat"
        }

        return messages, summary, metadata

    @staticmethod
    def _generate_conversation_summary(messages: List[Dict], participants: set) -> str:
        """Generate a basic summary of the conversation"""
        if not messages:
            return "Empty conversation"

        total_messages = len(messages)
        date_span = (messages[-1]["timestamp"] - messages[0]["timestamp"]).days

        # Count messages per participant
        message_counts = {}
        for msg in messages:
            sender = msg["sender"]
            message_counts[sender] = message_counts.get(sender, 0) + 1

        summary = f"WhatsApp conversation with {len(participants)} participants "
        summary += f"({', '.join(list(participants)[:3])}{'...' if len(participants) > 3 else ''}). "
        summary += f"Total of {total_messages} messages over {date_span} days."

        return summary

class DocumentProcessor:
    """Handles various document types"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.text_splitter = SimpleTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )

    async def extract_text_from_file(self, file_path: str, process_ocr: bool = False) -> tuple[str, DocumentType, Dict[str, Any]]:
        """Extract text from various file formats"""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(f"File too large: {file_size_mb:.1f}MB (max: {MAX_FILE_SIZE_MB}MB)")

        # Detect file type
        mime_type = magic.from_file(str(file_path), mime=True)
        file_extension = file_path.suffix.lower()
        logger.info(f"Detected file: {file_path}, MIME type: {mime_type}, Extension: {file_extension}")
        logger.info(f"Is .docx or .doc: {file_extension in ['.docx', '.doc']}")
        metadata = {}

        # PDF processing
        if mime_type == "application/pdf" or file_extension == ".pdf":
            text, doc_type = await self._process_pdf(file_path, process_ocr)
            return text, doc_type, metadata

        # Office documents
        elif file_extension in ['.docx', '.doc']:
            text, metadata = await self._process_word_document(file_path)
            return text, DocumentType.office, metadata
        elif file_extension in ['.pptx', '.ppt']:
            text = await self._process_powerpoint(file_path)
            return text, DocumentType.office, metadata
        elif file_extension in ['.xlsx', '.xls']:
            text = await self._process_excel(file_path)
            return text, DocumentType.office, metadata

        # Images
        elif mime_type.startswith("image/") or file_extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            if process_ocr or USE_OCR:
                text = OCRService.extract_text_from_image(str(file_path))
                return text, DocumentType.scanned, metadata
            else:
                return f"Image file: {file_path.name}", DocumentType.image, metadata

        # Text-based files
        elif (mime_type.startswith("text/") or
              file_extension in ['.txt', '.md', '.py', '.js', '.json', '.yaml', '.yml', '.xml', '.html', '.css']):
            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = await f.read()

            # Check if it's a WhatsApp export
            if self._is_whatsapp_export(content):
                return content, DocumentType.whatsapp, metadata
            elif file_extension in ['.py', '.js', '.java', '.cpp', '.c', '.cs', '.php']:
                return content, DocumentType.code, metadata
            else:
                return content, DocumentType.text, metadata

        # Email files
        elif file_extension in ['.eml', '.msg']:
            text = await self._process_email(file_path)
            return text, DocumentType.email, metadata

        # HTML/Web content
        elif mime_type.startswith("text/html") or file_extension in ['.html', '.htm']:
            text = await self._process_html(file_path)
            return text, DocumentType.webpage, metadata

        else:
            raise ValueError(f"Unsupported file type: {mime_type} ({file_extension})")

    async def _process_pdf(self, file_path: Path, process_ocr: bool) -> tuple[str, DocumentType]:
        """Process PDF files with optional OCR"""
        try:
            # Try text extraction first
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text += page_text + "\n"

            # If no text extracted or OCR requested, use OCR
            if (not text.strip() or process_ocr) and USE_OCR and OCR_AVAILABLE:
                logger.info(f"Using OCR for PDF: {file_path}")
                ocr_text = OCRService.extract_text_from_pdf_images(str(file_path))
                text = ocr_text if ocr_text.strip() else text
                return text, DocumentType.scanned

            return text, DocumentType.pdf

        except Exception as e:
            logger.error(f"PDF processing failed for {file_path}: {e}")
            if USE_OCR and OCR_AVAILABLE:
                return OCRService.extract_text_from_pdf_images(str(file_path)), DocumentType.scanned
            else:
                raise

    async def _process_word_document(self, file_path: Path) -> str:
        """Process Word documents"""
        logger.info(f"Attempting to process Word document: {file_path}")
        try:
            doc = DocxDocument(str(file_path))
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            title = doc.core_properties.title if doc.core_properties.title else file_path.stem
            logger.info(f"Successfully extracted text from {file_path}")
            return text, {"title": title}
        except Exception as e:
            logger.error(f"Word document processing failed for {file_path}: {e}")
            return f"Failed to process Word document: {file_path.name}", {}

    async def _process_powerpoint(self, file_path: Path) -> str:
        """Process PowerPoint presentations"""
        try:
            prs = Presentation(str(file_path))
            text = ""
            for slide_num, slide in enumerate(prs.slides, 1):
                text += f"\n--- Slide {slide_num} ---\n"
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
            return text
        except Exception as e:
            logger.error(f"PowerPoint processing failed: {e}")
            return f"Failed to process PowerPoint: {file_path.name}"

    async def _process_excel(self, file_path: Path) -> str:
        """Process Excel spreadsheets"""
        try:
            if file_path.suffix.lower() == '.xlsx':
                workbook = openpyxl.load_workbook(str(file_path))
                text = ""
                for sheet_name in workbook.sheetnames:
                    sheet = workbook[sheet_name]
                    text += f"\n--- Sheet: {sheet_name} ---\n"
                    for row in sheet.iter_rows(values_only=True):
                        row_text = "\t".join([str(cell) if cell is not None else "" for cell in row])
                        if row_text.strip():
                            text += row_text + "\n"
            else:  # .xls
                workbook = xlrd.open_workbook(str(file_path))
                text = ""
                for sheet in workbook.sheets():
                    text += f"\n--- Sheet: {sheet.name} ---\n"
                    for row_idx in range(sheet.nrows):
                        row = sheet.row_values(row_idx)
                        row_text = "\t".join([str(cell) for cell in row if cell])
                        if row_text.strip():
                            text += row_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Excel processing failed: {e}")
            return f"Failed to process Excel file: {file_path.name}"

    async def _process_email(self, file_path: Path) -> str:
        """Process email files"""
        try:
            with open(file_path, 'rb') as f:
                msg = email.message_from_bytes(f.read())

            text = f"From: {msg.get('From', 'Unknown')}\n"
            text += f"To: {msg.get('To', 'Unknown')}\n"
            text += f"Subject: {msg.get('Subject', 'No Subject')}\n"
            text += f"Date: {msg.get('Date', 'Unknown')}\n\n"

            # Extract body
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        text += part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                text += msg.get_payload(decode=True).decode('utf-8', errors='ignore')

            return text
        except Exception as e:
            logger.error(f"Email processing failed: {e}")
            return f"Failed to process email: {file_path.name}"

    async def _process_html(self, file_path: Path) -> str:
        """Process HTML files"""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = await f.read()

            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text()
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text
        except Exception as e:
            logger.error(f"HTML processing failed: {e}")
            return f"Failed to process HTML: {file_path.name}"

    def _is_whatsapp_export(self, content: str) -> bool:
        """Check if content is a WhatsApp export"""
        whatsapp_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2} - .+: .*',
            r'\d{1,2}\.\d{1,2}\.\d{2,4}, \d{1,2}:\d{2} - .+: .*',
            r'\[\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}\] .+: .*'
        ]

        for pattern in whatsapp_patterns:
            if re.search(pattern, content[:1000]):  # Check first 1000 chars
                return True
        return False

    async def enrich_with_llm(self, content: str, filename: str, document_type: DocumentType, title: str = None) -> ObsidianMetadata:
        """Enhanced LLM enrichment for metadata extraction"""

        # Determine content sample for LLM analysis
        content_sample = content[:3000] if len(content) > 3000 else content

        # Handle different document types
        if document_type == DocumentType.whatsapp:
            messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(content)
            return await self._enrich_whatsapp_chat(messages, summary, metadata, filename)

        # Standard document enrichment
        prompt = f"""Analyze this document and provide detailed metadata in JSON format.

Document: {filename}
Type: {document_type}
Content Sample: {content_sample}

Provide a JSON response with this exact structure:
{{
    "title": "{title or 'Descriptive title for the document'}",
    "summary": "2-3 sentence executive summary",
    "abstract": "Detailed paragraph abstract",
    "keywords": {{
        "primary": ["main topic 1", "main topic 2"],
        "secondary": ["related topic 1", "related topic 2"],
        "related": ["broader topic 1", "broader topic 2"]
    }},
    "tags": ["#tag1", "#tag2", "#tag3"],
    "key_points": ["Important insight 1", "Important insight 2"],
    "entities": {{
        "people": ["Person 1", "Person 2"],
        "organizations": ["Org 1", "Org 2"],
        "locations": ["Location 1", "Location 2"],
        "technologies": ["Tech 1", "Tech 2"]
    }},
    "complexity": "beginner|intermediate|advanced",
    "reading_time": "X minutes",
    "document_type": "{document_type}",
    "links": ["[[Related Topic 1]]", "[[Related Topic 2]]"]
}}

Respond only with valid JSON."""

        try:
            response = await self.llm_service.call_llm(prompt)
            metadata_dict = json.loads(response)

            # Create ObsidianMetadata object with safe parsing
            links = metadata_dict.get("links", [])
            # Ensure links are strings, not nested lists
            if isinstance(links, list):
                safe_links = []
                for link in links:
                    if isinstance(link, list):
                        safe_links.extend([str(item) for item in link])
                    else:
                        safe_links.append(str(link))
                links = safe_links

            obsidian_metadata = ObsidianMetadata(
                title=metadata_dict.get("title", filename),
                summary=metadata_dict.get("summary", ""),
                abstract=metadata_dict.get("abstract", ""),
                keywords=Keywords(**metadata_dict.get("keywords", {})),
                tags=metadata_dict.get("tags", []),
                key_points=metadata_dict.get("key_points", []),
                entities=Entities(**metadata_dict.get("entities", {})),
                complexity=ComplexityLevel(metadata_dict.get("complexity", "intermediate")),
                reading_time=metadata_dict.get("reading_time", "Unknown"),
                document_type=document_type,
                links=links,
                source=filename,
                created_at=datetime.now()
            )

            return obsidian_metadata

        except Exception as e:
            logger.error(f"LLM enrichment failed: {e}")
            # Return basic metadata as fallback
            return ObsidianMetadata(
                title=title or filename,
                summary=f"Document: {filename}",
                keywords=Keywords(primary=["document"], secondary=[], related=[]),
                entities=Entities(),
                document_type=document_type,
                source=filename
            )

    async def _enrich_whatsapp_chat(self, messages: List[Dict], summary: str, metadata: Dict, filename: str) -> ObsidianMetadata:
        """Enrich WhatsApp chat with LLM analysis"""

        # Sample recent messages for analysis
        recent_messages = messages[-50:] if len(messages) > 50 else messages
        message_text = "\n".join([f"{msg['sender']}: {msg['message']}" for msg in recent_messages])

        prompt = f"""Analyze this WhatsApp conversation and extract metadata in JSON format.

Conversation: {filename}
Participants: {', '.join(metadata['participants'])}
Total Messages: {metadata['total_messages']}
Date Range: {metadata['date_range']['start']} to {metadata['date_range']['end']}

Recent Messages Sample:
{message_text}

Provide JSON with:
{{
    "title": "Descriptive title for the conversation",
    "summary": "Brief summary of the conversation topic/purpose",
    "keywords": {{
        "primary": ["main topics discussed"],
        "secondary": ["secondary topics"],
        "related": ["related themes"]
    }},
    "tags": ["#whatsapp", "#conversation", "#topic-tags"],
    "key_points": ["Important points discussed"],
    "entities": {{
        "people": {metadata['participants']},
        "organizations": [],
        "locations": [],
        "technologies": []
    }},
    "complexity": "beginner",
    "reading_time": "5 minutes"
}}

Respond only with valid JSON."""

        try:
            response = await self.llm_service.call_llm(prompt)
            metadata_dict = json.loads(response)

            return ObsidianMetadata(
                title=metadata_dict.get("title", f"WhatsApp Chat - {filename}"),
                summary=metadata_dict.get("summary", summary),
                keywords=Keywords(**metadata_dict.get("keywords", {})),
                tags=metadata_dict.get("tags", ["#whatsapp"]),
                key_points=metadata_dict.get("key_points", []),
                entities=Entities(**metadata_dict.get("entities", {})),
                complexity=ComplexityLevel.beginner,
                reading_time="5 minutes",
                document_type=DocumentType.whatsapp,
                source=filename
            )

        except Exception as e:
            logger.error(f"WhatsApp enrichment failed: {e}")
            return ObsidianMetadata(
                title=f"WhatsApp Chat - {filename}",
                summary=summary,
                keywords=Keywords(primary=["whatsapp", "conversation"]),
                tags=["#whatsapp"],
                entities=Entities(people=metadata['participants']),
                document_type=DocumentType.whatsapp,
                source=filename
            )

    async def create_obsidian_markdown(self, content: str, metadata: ObsidianMetadata, doc_id: str) -> str:
        """Create Obsidian-optimized markdown file"""

        os.makedirs(PATHS['obsidian_path'], exist_ok=True)

        # Create safe filename
        safe_title = "".join(c for c in metadata.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = re.sub(r'\s+', '_', safe_title)
        markdown_filename = f"{safe_title}_{doc_id[:8]}.md"
        markdown_path = Path(PATHS['obsidian_path']) / markdown_filename

        # Create frontmatter
        frontmatter = {
            'title': metadata.title,
            'id': doc_id,
            'created': metadata.created_at.isoformat(),
            'tags': metadata.tags,
            'type': metadata.document_type,
            'source': metadata.source,
            'summary': metadata.summary,
            'abstract': metadata.abstract,
            'keywords': {
                'primary': metadata.keywords.primary,
                'secondary': metadata.keywords.secondary,
                'related': metadata.keywords.related
            },
            'entities': {
                'people': metadata.entities.people,
                'organizations': metadata.entities.organizations,
                'locations': metadata.entities.locations,
                'technologies': metadata.entities.technologies
            },
            'complexity': metadata.complexity,
            'reading_time': metadata.reading_time,
            'links': metadata.links
        }

        # Create markdown content
        markdown_content = "---\n"
        markdown_content += yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
        markdown_content += "---\n\n"

        # Add title
        markdown_content += f"# {metadata.title}\n\n"

        # Add summary section
        if metadata.summary:
            markdown_content += "## Summary\n\n"
            markdown_content += f"{metadata.summary}\n\n"

        # Add key insights
        if metadata.key_points:
            markdown_content += "## Key Insights\n\n"
            for point in metadata.key_points:
                markdown_content += f"- {point}\n"
            markdown_content += "\n"

        # Add entities section
        if any([metadata.entities.people, metadata.entities.organizations,
                metadata.entities.locations, metadata.entities.technologies]):
            markdown_content += "## Entities\n\n"

            if metadata.entities.people:
                markdown_content += "**People:** " + ", ".join([f"[[{person}]]" for person in metadata.entities.people]) + "\n\n"
            if metadata.entities.organizations:
                markdown_content += "**Organizations:** " + ", ".join([f"[[{org}]]" for org in metadata.entities.organizations]) + "\n\n"
            if metadata.entities.locations:
                markdown_content += "**Locations:** " + ", ".join([f"[[{loc}]]" for loc in metadata.entities.locations]) + "\n\n"
            if metadata.entities.technologies:
                markdown_content += "**Technologies:** " + ", ".join([f"[[{tech}]]" for tech in metadata.entities.technologies]) + "\n\n"

        # Add content section
        markdown_content += "## Content\n\n"

        # Format content based on document type
        if metadata.document_type == DocumentType.whatsapp:
            markdown_content += await self._format_whatsapp_content(content)
        else:
            markdown_content += content

        # Add related notes section
        if metadata.links:
            markdown_content += "\n\n## Related Notes\n\n"
            for link in metadata.links:
                markdown_content += f"- {link}\n"

        # Add tags section
        if metadata.tags:
            markdown_content += "\n\n## Tags\n\n"
            markdown_content += " ".join(metadata.tags)

        # Write file
        async with aiofiles.open(markdown_path, 'w', encoding='utf-8') as f:
            await f.write(markdown_content)

        logger.info(f"Created Obsidian markdown: {markdown_path}")
        return str(markdown_path)

    async def _format_whatsapp_content(self, content: str) -> str:
        """Format WhatsApp content for better readability"""
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(content)

        formatted = f"**Conversation Summary:** {summary}\n\n"
        formatted += f"**Participants:** {', '.join(metadata['participants'])}\n\n"
        formatted += f"**Message Count:** {metadata['total_messages']}\n\n"
        formatted += f"**Date Range:** {metadata['date_range']['start']} to {metadata['date_range']['end']}\n\n"
        formatted += "## Messages\n\n"

        # Group messages by date
        current_date = None
        for msg in messages[-100:]:  # Show last 100 messages
            msg_date = msg['timestamp'].date()
            if current_date != msg_date:
                formatted += f"\n### {msg_date}\n\n"
                current_date = msg_date

            time_str = msg['timestamp'].strftime("%H:%M")
            formatted += f"**{msg['sender']}** ({time_str}): {msg['message']}\n\n"

        return formatted

# File watcher for auto-processing
class FileWatchHandler(FileSystemEventHandler):
    def __init__(self, rag_service):
        self.rag_service = rag_service

    def on_created(self, event):
        if not event.is_directory:
            logger.info(f"New file detected: {event.src_path}")
            asyncio.create_task(self.rag_service.process_file_from_watch(event.src_path))

# Main RAG Service
class RAGService:
    def __init__(self):
        self.llm_service = LLMService()
        self.document_processor = DocumentProcessor(self.llm_service)
        self.setup_chromadb()

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
            # Split into chunks
            chunks = self.document_processor.text_splitter.split_text(content)

            # LLM enrichment
            title = file_metadata.get("title") if file_metadata else None
            obsidian_metadata = await self.document_processor.enrich_with_llm(
                content, filename or f"document_{doc_id}", document_type, title=title
            )

            # Store chunks in ChromaDB
            chunk_ids = []
            chunk_metadatas = []
            chunk_contents = []

            base_metadata = {
                "doc_id": doc_id,
                "filename": filename or f"document_{doc_id}",
                "chunks": len(chunks),
                "created_at": datetime.now().isoformat(),
                "document_type": str(document_type),
                "title": obsidian_metadata.title,
                "tags": ",".join(obsidian_metadata.tags) if obsidian_metadata.tags else "",
                "keywords_primary": ",".join(obsidian_metadata.keywords.primary) if obsidian_metadata.keywords.primary else "",
                "keywords_secondary": ",".join(obsidian_metadata.keywords.secondary) if obsidian_metadata.keywords.secondary else "",
                "entities_people": ",".join(obsidian_metadata.entities.people) if obsidian_metadata.entities.people else "",
                "entities_organizations": ",".join(obsidian_metadata.entities.organizations) if obsidian_metadata.entities.organizations else "",
                "complexity": str(obsidian_metadata.complexity),
                "content_hash": content_hash,
                **(file_metadata or {})
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

            # Create Obsidian markdown
            obsidian_path = None
            if generate_obsidian:
                obsidian_path = await self.document_processor.create_obsidian_markdown(
                    content, obsidian_metadata, doc_id
                )

            logger.info(f"Processed document {doc_id}: {len(chunks)} chunks, Obsidian: {bool(obsidian_path)}")

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
            content, document_type, metadata = await self.document_processor.extract_text_from_file(file_path, process_ocr)
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

        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filter_dict
        )

        search_time_ms = (time.time() - start_time) * 1000

        search_results = []
        if results['documents'] and results['documents'][0]:
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
                search_results.append(SearchResult(
                    content=doc,
                    metadata=metadata,
                    relevance_score=1.0 - distance,
                    chunk_id=metadata.get('chunk_id', f'chunk_{i}')
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
        # Step 1: Search for relevant context
        rag_service = RAGService()
        search_query = Query(
            text=request.question,
            top_k=request.max_context_chunks
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

        # Step 2: Prepare context from search results
        context_chunks = []
        for result in search_response.results:
            context_chunks.append(f"Source: {result.metadata.get('filename', 'Unknown')}\nContent: {result.content}")

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
        llm_service = LLMService()
        cost = 0.0
        model_used = None

        # Determine which model to use
        if request.llm_model:
            model_to_use = request.llm_model.value
            try:
                answer, cost = await llm_service.call_llm_with_model(rag_prompt, model_to_use)
                provider_used = model_to_use.split('/')[0]
                model_used = model_to_use
            except Exception as e:
                logger.error(f"LLM call failed for {model_to_use}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to generate answer with {model_to_use}: {str(e)}")
        else:
            # Use legacy fallback method
            provider_to_use = request.llm_provider.value if request.llm_provider else None
            try:
                answer = await llm_service.call_llm(rag_prompt, provider_to_use)
                provider_used = provider_to_use or DEFAULT_LLM
                model_used = f"{provider_used}/default"
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")

        # Step 5: Prepare response
        sources = search_response.results if request.include_sources else []

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