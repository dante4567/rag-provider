"""
Service layer for RAG Provider

Business logic separated from API endpoints
"""
from src.services.document_service import DocumentService
from src.services.text_splitter import SimpleTextSplitter
from src.services.ocr_service import OCRService
from src.services.whatsapp_parser import WhatsAppParser
from src.services.llm_chat_parser import LLMChatParser
from src.services.email_threading_service import EmailThreadingService
from src.services.llm_service import LLMService, CostTracker
from src.services.vector_service import VectorService
from src.services.search_cache_service import SearchResultCache, get_search_cache, clear_search_cache
from src.services.daily_note_service import DailyNoteService
from src.services.entity_enrichment_service import EntityEnrichmentService

__all__ = [
    "DocumentService",
    "SimpleTextSplitter",
    "OCRService",
    "WhatsAppParser",
    "LLMChatParser",
    "EmailThreadingService",
    "LLMService",
    "CostTracker",
    "VectorService",
    "SearchResultCache",
    "get_search_cache",
    "clear_search_cache",
    "DailyNoteService",
    "EntityEnrichmentService",
]

# Self-improvement loop services
from src.services.editor_service import EditorService
from src.services.patch_service import PatchService
from src.services.schema_validator import SchemaValidator
