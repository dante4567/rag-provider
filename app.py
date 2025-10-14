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
    from src.services.contact_service import ContactService
    from src.services.calendar_service import CalendarService
    from src.services.entity_name_filter_service import EntityNameFilterService

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
from src.routes import health, ingest, search, stats, chat, admin, email_threading, evaluation, monitoring, daily_notes

# Simple text splitter to replace langchain dependency

# Import extracted classes from services module
from src.services.rag_service import (
    SimpleTextSplitter,
    CostTracker,
    FileWatchHandler,
    RAGService,
    MODEL_PRICING,
    cost_tracking
)


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
            'obsidian_path': '/data/obsidian',
            'archive_path': '/data/processed_originals',
            'temp_path': '/tmp'
        }
    elif PLATFORM == 'windows':
        base_path = os.path.expanduser('~/Documents/rag_data')
        return {
            'input_path': f'{base_path}/input',
            'output_path': f'{base_path}/output',
            'processed_path': f'{base_path}/processed',
            'obsidian_path': f'{base_path}/obsidian',
            'archive_path': f'{base_path}/processed_originals',
            'temp_path': os.environ.get('TEMP', '/tmp')
        }
    else:  # Linux/macOS
        base_path = os.path.expanduser('~/rag_data')
        return {
            'input_path': f'{base_path}/input',
            'output_path': f'{base_path}/output',
            'processed_path': f'{base_path}/processed',
            'obsidian_path': f'{base_path}/obsidian',
            'archive_path': f'{base_path}/processed_originals',
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
app.include_router(daily_notes.router)

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
text_splitter = None
file_watcher = None
executor = ThreadPoolExecutor(max_workers=4)

# Initialize services
rag_service = RAGService()

# Expose chroma_client and collection from RAGService for health checks
from src.services.rag_service import chroma_client, collection

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
    import socket

    # Get port from environment with fallback
    APP_PORT = int(os.getenv("APP_PORT", "8001"))
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")

    # Check if port is available
    def is_port_available(port):
        """Check if a port is available for binding"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return True
        except OSError:
            return False

    if not is_port_available(APP_PORT):
        logger.warning(f"Port {APP_PORT} is already in use, trying alternative ports...")
        # Try ports in range
        for alt_port in range(APP_PORT + 1, APP_PORT + 10):
            if is_port_available(alt_port):
                logger.info(f"Using alternative port {alt_port}")
                APP_PORT = alt_port
                break
        else:
            logger.error(f"No available ports found in range {APP_PORT}-{APP_PORT+9}")
            raise RuntimeError(f"Port {APP_PORT} and alternatives are all in use")

    logger.info(f"Starting RAG service on {APP_HOST}:{APP_PORT}")
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)