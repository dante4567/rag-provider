from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Form
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

# LLM Provider Configuration
LLM_PROVIDERS = {
    "anthropic": {
        "api_key": ANTHROPIC_API_KEY,
        "model": "claude-3-sonnet-20241022",
        "max_tokens": 4000,
        "client_class": anthropic.Anthropic
    },
    "openai": {
        "api_key": OPENAI_API_KEY,
        "model": "gpt-4o-mini",
        "max_tokens": 4000,
        "client_class": openai.OpenAI
    },
    "groq": {
        "api_key": GROQ_API_KEY,
        "model": "llama-3.1-8b-instant",
        "max_tokens": 8000,
        "client_class": groq.Groq
    }
}

# Initialize LLM clients
llm_clients = {}
for provider, config in LLM_PROVIDERS.items():
    if config["api_key"]:
        try:
            if provider == "groq":
                llm_clients[provider] = config["client_class"](api_key=config["api_key"])
            else:
                llm_clients[provider] = config["client_class"](api_key=config["api_key"])
            logger.info(f"Initialized {provider} LLM client")
        except Exception as e:
            logger.warning(f"Failed to initialize {provider} client: {e}")

# Initialize FastAPI app
app = FastAPI(
    title="Enhanced RAG Service",
    version="2.0.0",
    description="Cross-platform RAG service with OCR, WhatsApp processing, and Obsidian optimization"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
chroma_client = None
collection = None
text_splitter = None
file_watcher = None
executor = ThreadPoolExecutor(max_workers=4)

class LLMService:
    """Manages multiple LLM providers with fallback"""

    def __init__(self):
        self.provider_order = [DEFAULT_LLM, FALLBACK_LLM, EMERGENCY_LLM]

    async def call_llm(self, prompt: str, provider: str = None, max_tokens: int = None) -> str:
        """Call LLM with fallback support"""
        providers_to_try = [provider] if provider else self.provider_order

        for llm_provider in providers_to_try:
            if llm_provider not in llm_clients:
                continue

            try:
                config = LLM_PROVIDERS[llm_provider]
                client = llm_clients[llm_provider]
                tokens = max_tokens or config["max_tokens"]

                if llm_provider == "anthropic":
                    response = client.messages.create(
                        model=config["model"],
                        max_tokens=tokens,
                        temperature=LLM_TEMPERATURE,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return response.content[0].text

                elif llm_provider in ["openai", "groq"]:
                    response = client.chat.completions.create(
                        model=config["model"],
                        max_tokens=tokens,
                        temperature=LLM_TEMPERATURE,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return response.choices[0].message.content

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

    async def extract_text_from_file(self, file_path: str, process_ocr: bool = False) -> tuple[str, DocumentType]:
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

        # PDF processing
        if mime_type == "application/pdf" or file_extension == ".pdf":
            return await self._process_pdf(file_path, process_ocr)

        # Office documents
        elif file_extension in ['.docx', '.doc']:
            return await self._process_word_document(file_path), DocumentType.office
        elif file_extension in ['.pptx', '.ppt']:
            return await self._process_powerpoint(file_path), DocumentType.office
        elif file_extension in ['.xlsx', '.xls']:
            return await self._process_excel(file_path), DocumentType.office

        # Images
        elif mime_type.startswith("image/") or file_extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            if process_ocr or USE_OCR:
                text = OCRService.extract_text_from_image(str(file_path))
                return text, DocumentType.scanned
            else:
                return f"Image file: {file_path.name}", DocumentType.image

        # Text-based files
        elif (mime_type.startswith("text/") or
              file_extension in ['.txt', '.md', '.py', '.js', '.json', '.yaml', '.yml', '.xml', '.html', '.css']):
            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = await f.read()

            # Check if it's a WhatsApp export
            if self._is_whatsapp_export(content):
                return content, DocumentType.whatsapp
            elif file_extension in ['.py', '.js', '.java', '.cpp', '.c', '.cs', '.php']:
                return content, DocumentType.code
            else:
                return content, DocumentType.text

        # Email files
        elif file_extension in ['.eml', '.msg']:
            return await self._process_email(file_path), DocumentType.email

        # HTML/Web content
        elif mime_type.startswith("text/html") or file_extension in ['.html', '.htm']:
            return await self._process_html(file_path), DocumentType.webpage

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
        try:
            doc = DocxDocument(str(file_path))
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except Exception as e:
            logger.error(f"Word document processing failed: {e}")
            return f"Failed to process Word document: {file_path.name}"

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

    async def enrich_with_llm(self, content: str, filename: str, document_type: DocumentType) -> ObsidianMetadata:
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
    "title": "Descriptive title for the document",
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
                title=filename,
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

    async def process_document(self,
                             content: str,
                             filename: str = None,
                             document_type: DocumentType = DocumentType.text,
                             process_ocr: bool = False,
                             generate_obsidian: bool = True,
                             file_metadata: Dict[str, Any] = None) -> IngestResponse:
        """Process a document with full enrichment pipeline"""

        doc_id = str(uuid.uuid4())

        try:
            # Split into chunks
            chunks = self.document_processor.text_splitter.split_text(content)

            # LLM enrichment
            obsidian_metadata = await self.document_processor.enrich_with_llm(
                content, filename or f"document_{doc_id}", document_type
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
            content, document_type = await self.document_processor.extract_text_from_file(file_path, process_ocr)
            filename = Path(file_path).name

            return await self.process_document(
                content=content,
                filename=filename,
                document_type=document_type,
                process_ocr=process_ocr,
                generate_obsidian=generate_obsidian
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
async def ingest_document(document: Document):
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
    generate_obsidian: bool = Form(True)
):
    """Ingest file via upload"""
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
async def test_llm_provider(provider: LLMProvider, prompt: str = "Hello, how are you?"):
    """Test LLM provider"""
    try:
        llm_service = LLMService()
        response = await llm_service.call_llm(prompt, provider.value)
        return {
            "provider": provider,
            "prompt": prompt,
            "response": response,
            "success": True
        }
    except Exception as e:
        return {
            "provider": provider,
            "prompt": prompt,
            "error": str(e),
            "success": False
        }

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