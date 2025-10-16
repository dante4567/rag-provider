"""
RAG Service - Main document processing orchestration

This service coordinates all document processing operations including:
- LLM enrichment and metadata extraction
- Structure-aware chunking
- Vector embedding and storage
- Obsidian export
- Quality scoring and triage
- Cost tracking
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
import hashlib
import logging
import os
from datetime import datetime, date as date_type
import asyncio
import time
import chromadb

from watchdog.events import FileSystemEventHandler

# Import all service dependencies
try:
    from src.core.config import get_settings
    from src.models.schemas import (
        IngestResponse, SearchResult, SearchResponse, DocumentType,
        CostInfo, CostStats, ObsidianMetadata, Keywords, Entities,
        ComplexityLevel
    )
    from fastapi import HTTPException

    from src.services import (
        DocumentService,
        LLMService,
        VectorService,
        OCRService
    )
    from src.services.enrichment_service import EnrichmentService
    from src.services.vocabulary_service import VocabularyService
    from src.services.chunking_service import ChunkingService
    from src.services.obsidian_service import ObsidianService
    from src.services.daily_note_service import DailyNoteService
    from src.services.tag_taxonomy_service import TagTaxonomyService
    from src.services.smart_triage_service import SmartTriageService
    from src.services.quality_scoring_service import QualityScoringService
    from src.services.contact_service import ContactService
    from src.services.calendar_service import CalendarService

    # Pipeline architecture
    from src.pipeline import create_ingestion_pipeline, StageContext, RawDocument, StageResult
    from src.services.entity_name_filter_service import EntityNameFilterService
except ImportError as e:
    raise ImportError(f"Failed to import required services: {e}")

logger = logging.getLogger(__name__)

# Platform detection
IS_DOCKER = os.getenv("DOCKER_CONTAINER", "false").lower() == "true"

# ChromaDB configuration
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "documents")

# Global ChromaDB instances (module-level)
chroma_client = None
collection = None

# Cost tracking configuration
DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "10.0"))
ENABLE_COST_TRACKING = os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"

# Model pricing (per 1M tokens) - Updated 2024
MODEL_PRICING = {
    # Groq - Lightning fast inference
    "groq/llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    
    # Anthropic - High quality reasoning
    "anthropic/claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "anthropic/claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
    
    # OpenAI - Reliable general purpose
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4o": {"input": 5.0, "output": 15.0},
    
    # Google - Long context specialist
    "google/gemini-1.5-pro": {"input": 1.25, "output": 5.0}
}

# Cost tracking storage (in-memory)
cost_tracking = {
    "operations": [],
    "daily_totals": {},
    "total_cost": 0.0
}


class VoyageEmbeddingFunction:
    """
    Custom embedding function for Voyage AI embeddings

    Supports:
    - voyage-3-lite (512 dims, MTEB ~68, $0.02/1M tokens)
    - Batch processing (up to 128 inputs)
    - Input type specification (document vs query)
    """

    def __init__(self, api_key: str, model_name: str = "voyage-3-lite"):
        """
        Initialize Voyage embedding function

        Args:
            api_key: Voyage AI API key
            model_name: Model name (default: voyage-3-lite)
        """
        try:
            import voyageai
            self.client = voyageai.Client(api_key=api_key)
            self.model_name = model_name
            logger.info(f"✅ Initialized Voyage AI embeddings: {model_name}")
        except ImportError:
            logger.error("voyageai package not installed. Run: pip install voyageai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Voyage AI: {e}")
            raise

    def name(self) -> str:
        """
        Return the name of the embedding function (required by ChromaDB)

        Returns:
            str: Embedding function name
        """
        return f"voyage-{self.model_name}"

    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        Generate embeddings for input texts (documents)

        Args:
            input: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not input:
            return []

        try:
            response = self.client.embed(
                input,
                model=self.model_name,
                input_type="document"  # Use "document" for indexing
            )
            # Return plain Python lists (ChromaDB handles conversion internally)
            return response.embeddings
        except Exception as e:
            logger.error(f"Voyage embedding failed: {e}")
            raise

    def embed_query(self, query = None, input = None):
        """
        Generate embedding for a search query

        Args:
            query: Query text or list of texts to embed
            input: Alternative name for query (ChromaDB compatibility)

        Returns:
            Embedding vector(s) for the query (numpy array for ChromaDB)
        """
        import numpy as np

        # Accept either query or input parameter
        text = query if query is not None else input
        if not text:
            return []

        # Handle both string and list inputs
        if isinstance(text, list):
            if len(text) == 0:
                return []
            text = text[0]  # Use first element

        if not text:
            return []

        try:
            response = self.client.embed(
                [text],
                model=self.model_name,
                input_type="query"  # Use "query" for search
            )
            # Convert to numpy array (ChromaDB expects .tolist() method)
            embeddings_array = np.array(response.embeddings, dtype=np.float32)
            return embeddings_array
        except Exception as e:
            logger.error(f"Voyage query embedding failed: {e}")
            raise


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
class RAGService:
    def __init__(self):
        # Setup ChromaDB first
        self.setup_chromadb()

        # Initialize new service layer
        try:
            logger.info("✅ Using new service layer architecture")
            settings = get_settings()
            self.llm_service = LLMService(settings)
            self.vector_service = VectorService(collection, settings)
            self.document_service = DocumentService(settings)
            self.ocr_service = OCRService(languages=['eng', 'deu', 'fra', 'spa'])

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

            # Initialize daily note service for automatic journal generation
            obsidian_output_dir = os.getenv("OBSIDIAN_VAULT_PATH", "./obsidian_vault")
            self.daily_note_service = DailyNoteService(
                refs_dir=f"{obsidian_output_dir}/refs",
                llm_service=self.llm_service
            )

            # Initialize Obsidian export service (formerly V3 - RAG-first)
            self.obsidian_service = ObsidianService(
                output_dir=obsidian_output_dir,
                refs_dir=f"{obsidian_output_dir}/refs",
                daily_note_service=self.daily_note_service
            )

            # Initialize contact/calendar export services (opt-in via ENABLE_VCF_ICS=true)
            # Disabled by default for personal use (entities are in Obsidian wiki-links)
            enable_vcf_ics = os.getenv("ENABLE_VCF_ICS", "false").lower() == "true"
            if enable_vcf_ics:
                # Use absolute paths for Docker, relative for local dev
                contacts_default = "/data/contacts" if IS_DOCKER else "./data/contacts"
                calendar_default = "/data/calendar" if IS_DOCKER else "./data/calendar"
                contacts_output_dir = Path(os.getenv("CONTACTS_PATH", contacts_default))
                calendar_output_dir = Path(os.getenv("CALENDAR_PATH", calendar_default))
                self.contact_service = ContactService(output_dir=contacts_output_dir)
                self.calendar_service = CalendarService(output_dir=calendar_output_dir)
            else:
                self.contact_service = None
                self.calendar_service = None

            # Initialize entity name filter (filters generic roles)
            self.entity_filter = EntityNameFilterService()

            # Initialize quality scoring service (blueprint do_index gates)
            self.quality_scoring_service = QualityScoringService()

            # Initialize ingestion pipeline (modular architecture)
            # NEW: Triage stage runs BEFORE enrichment to save costs on duplicates/junk
            self.pipeline = create_ingestion_pipeline(
                enrichment_service=self.enrichment_service,
                quality_service=self.quality_scoring_service,
                chunking_service=self.chunking_service,
                vector_service=self.vector_service,
                obsidian_service=self.obsidian_service,
                triage_service=self.triage_service,  # NEW: Enable smart triage
                enable_triage=True,  # NEW: Duplicate detection + junk filtering
                enable_quality_gate=True,  # CHANGED: Enable quality gating (was False)
                enable_export=True  # Re-enabled after fixing API mismatch
            )

            self.using_new_services = True
            logger.info("✅ EnrichmentService initialized with controlled vocabulary")
            logger.info(f"   📚 Topics: {len(self.vocabulary_service.get_all_topics())}")
            logger.info(f"   🏗️  Projects: {len(self.vocabulary_service.get_active_projects())}")
            logger.info(f"   📍 Places: {len(self.vocabulary_service.get_all_places())}")
            logger.info("✅ Structure-aware chunking enabled (ignores RAG:IGNORE blocks)")
            logger.info(f"✅ ObsidianService initialized (RAG-first format) → {obsidian_output_dir}")
            logger.info("✅ Pipeline architecture initialized (6 stages: triage → enrichment → quality → chunking → storage → export)")
            logger.info("   🔍 Triage enabled: duplicate detection + junk filtering")
            logger.info("   🚪 Quality gate enabled: filters low-quality documents")
            if enable_vcf_ics:
                logger.info(f"✅ ContactService enabled → {contacts_output_dir}")
                logger.info(f"✅ CalendarService enabled → {calendar_output_dir}")
            else:
                logger.info("ℹ️  VCF/ICS export disabled (enable with ENABLE_VCF_ICS=true)")
        except Exception as e:
            logger.error(f"❌ Service layer initialization failed: {e}")
            raise RuntimeError(f"Service layer is required but initialization failed: {e}")

    def setup_chromadb(self):
        global chroma_client, collection
        try:
            chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
            chroma_client.heartbeat()

            # Try Voyage embeddings first, fall back to sentence-transformers
            voyage_api_key = os.getenv("VOYAGE_API_KEY")
            embedding_function = None

            if voyage_api_key:
                try:
                    # Use Voyage-3-lite (512 dims, MTEB ~68, $0.02/1M tokens)
                    embedding_function = VoyageEmbeddingFunction(
                        api_key=voyage_api_key,
                        model_name="voyage-3-lite"
                    )
                    embedding_info = "Voyage-3-lite (512 dims, MTEB ~68, $0.02/1M tokens)"
                    logger.info(f"✅ Using Voyage AI embeddings: {embedding_info}")
                except Exception as e:
                    logger.warning(f"Failed to initialize Voyage embeddings: {e}")
                    logger.info("Falling back to sentence-transformers")
                    embedding_function = None

            if embedding_function is None:
                # Fallback: sentence-transformers (local, free, 384 dims)
                from chromadb.utils import embedding_functions
                embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
                embedding_info = "sentence-transformers all-MiniLM-L6-v2 (384 dims, MTEB 56.3, local/free)"
                logger.info(f"✅ Using fallback embeddings: {embedding_info}")

            # Get or create collection with selected embedding function
            try:
                collection = chroma_client.get_collection(
                    name=COLLECTION_NAME,
                    embedding_function=embedding_function
                )
            except (ValueError, Exception):
                collection = chroma_client.create_collection(
                    name=COLLECTION_NAME,
                    embedding_function=embedding_function,
                    metadata={"hnsw:space": "cosine"}
                )

            logger.info(f"✅ Connected to ChromaDB with {embedding_info}")
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
                             file_metadata: Dict[str, Any] = None,
                             use_critic: bool = False,
                             use_iteration: bool = False) -> IngestResponse:
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
                # Handle both string IDs and list IDs
                first_id = existing_docs['ids'][0]
                if isinstance(first_id, list):
                    first_id = first_id[0] if first_id else ""
                existing_doc_id = first_id.split('_chunk_')[0] if isinstance(first_id, str) else str(first_id)
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

            # Extract date from file metadata if available
            from datetime import date as date_type
            created_date = None
            if file_metadata and 'created_date' in file_metadata:
                try:
                    created_date = date_type.fromisoformat(file_metadata['created_date'])
                except (ValueError, TypeError):
                    pass

            # Use iteration loop if requested (slower but higher quality)
            critique_result = None
            if use_iteration:
                logger.info("   🔄 Using self-improvement loop (critic + editor)")
                enriched_metadata, critique_data = await self.enrichment_service.enrich_with_iteration(
                    text=content,
                    filename=filename or f"document_{doc_id}",
                    max_iterations=2,
                    min_avg_score=4.0,
                    use_critic=True
                )

                # Store critique result from iteration
                if critique_data:
                    from src.models.schemas import QualityScores, CritiqueResult
                    critique_result = CritiqueResult(
                        scores=QualityScores(**critique_data["scores"]),
                        overall_quality=critique_data["overall_quality"],
                        suggestions=critique_data["suggestions"],
                        critic_model=critique_data["critic_model"],
                        critic_cost=critique_data["critic_cost"],
                        critic_date=critique_data["critic_date"]
                    )
                    logger.info(f"   ✅ Iteration complete: {critique_data['overall_quality']:.2f}/5.0")
            else:
                # Standard enrichment with controlled vocabulary
                logger.info("   📊 Enriching with controlled vocabulary")
                enriched_metadata = await self.enrichment_service.enrich_document(
                    content=content,
                    filename=filename or f"document_{doc_id}",
                    document_type=document_type,
                    created_at=created_date,
                    existing_metadata=file_metadata
                )

            # Debug: Check if people/dates are in enriched_metadata
            logger.debug(f"\nenriched_metadata after enrichment service:\n"
                        f"  - 'people' in metadata: {'people' in enriched_metadata}\n"
                        f"  - people value: {enriched_metadata.get('people', 'NOT FOUND')}\n"
                        f"  - 'dates' in metadata: {'dates' in enriched_metadata}\n"
                        f"  - dates value: {enriched_metadata.get('dates', 'NOT FOUND')}\n"
                        f"  - 'entities' in metadata: {'entities' in enriched_metadata}\n"
                        f"  - entities value: {enriched_metadata.get('entities', 'NOT FOUND')}")

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
            # OPTIONAL: LLM-as-Critic Quality Assessment
            # (Skip if using iteration - already includes critic)
            # ============================================================
            if use_critic and not use_iteration:
                try:
                    logger.info(f"🔍 Running LLM-as-critic quality assessment...")
                    critique_data = await self.enrichment_service.critique_enrichment(
                        content=content,
                        enriched_metadata=enriched_metadata,
                        filename=filename or f"document_{doc_id}"
                    )

                    # Store critique in response
                    from src.models.schemas import QualityScores, CritiqueResult
                    critique_result = CritiqueResult(
                        scores=QualityScores(**critique_data["scores"]),
                        overall_quality=critique_data["overall_quality"],
                        suggestions=critique_data["suggestions"],
                        critic_model=critique_data["critic_model"],
                        critic_cost=critique_data["critic_cost"],
                        critic_date=critique_data["critic_date"]
                    )

                    logger.info(f"✅ Critic assessment complete: {critique_data['overall_quality']:.2f}/5.0")
                    logger.info(f"   📊 Schema: {critique_data['scores']['schema_compliance']:.1f} | Entities: {critique_data['scores']['entity_quality']:.1f} | Topics: {critique_data['scores']['topic_relevance']:.1f}")
                    logger.info(f"   📊 Summary: {critique_data['scores']['summary_quality']:.1f} | Tasks: {critique_data['scores']['task_identification']:.1f} | Privacy: {critique_data['scores']['privacy_assessment']:.1f}")
                    logger.info(f"   💰 Critic cost: ${critique_data['critic_cost']:.6f}")
                    if critique_data['suggestions']:
                        logger.info(f"   💡 Suggestions ({len(critique_data['suggestions'])}): {critique_data['suggestions'][0][:80]}...")
                except Exception as e:
                    logger.warning(f"   ⚠️ Critic assessment failed: {e}")
                    import traceback
                    traceback.print_exc()

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
                    except (AttributeError, KeyError, FileNotFoundError, Exception):
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
                # Use specialized chunking for chat logs (turn-based)
                logger.debug(f"   🔍 Chunking decision: document_type={document_type} (type: {type(document_type)}), DocumentType.llm_chat={DocumentType.llm_chat}, equal={document_type == DocumentType.llm_chat}")
                if document_type == DocumentType.llm_chat:
                    logger.info("   💬 Using strategic turn-based chunking for chat log...")
                    chunk_dicts = self.chunking_service.chunk_chat_log(content, enriched_metadata)
                    # Extract just the content strings for backward compatibility
                    chunks = [c['content'] for c in chunk_dicts]
                    # Store full chunk metadata for later use
                    chunk_metadata_list = chunk_dicts
                    logger.info(f"   ✅ Created {len(chunks)} turn-based chunks (was {enriched_metadata.get('turn_count', 0)} turns)")
                else:
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
            technologies_list = enriched_lists.get("technologies", [])  # FIX: Extract technologies!

            # Extract summary string (handle both dict and string formats)
            summary_value = enriched_metadata.get("summary", "")
            if isinstance(summary_value, dict):
                summary_str = summary_value.get("tl_dr", "") or summary_value.get("text", "") or str(summary_value)
            else:
                summary_str = str(summary_value) if summary_value else ""

            obsidian_metadata = ObsidianMetadata(
                title=title,
                keywords=Keywords(primary=tags_list[:3], secondary=tags_list[3:] if len(tags_list) > 3 else []),
                tags=[f"#{tag}" if not tag.startswith("#") else tag for tag in tags_list],
                summary=summary_str,
                abstract=summary_str,
                key_points=key_points_list,
                entities=Entities(
                    people=people_list,
                    organizations=orgs_list,
                    locations=locs_list,
                    technologies=technologies_list  # FIX: Add technologies!
                ),
                reading_time=f"{enriched_metadata.get('estimated_reading_time_min', 1)} min",
                complexity=ComplexityLevel[enriched_metadata.get("complexity", "intermediate")],
                links=[],
                document_type=document_type,
                source=filename or "",
                created_at=datetime.now(),

                # Add date entities (top-level for Obsidian queries)
                dates=dates_list,
                dates_detailed=enriched_lists.get("dates_detailed", []),

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

            # Import adapter for format conversion
            from src.adapters.chroma_adapter import ChromaDBAdapter

            # Sanitize enriched metadata for ChromaDB (remove None values and non-scalars)
            sanitized_enriched = ChromaDBAdapter.sanitize_for_chromadb(enriched_metadata)

            # Flatten entity lists for ChromaDB using adapter
            entity_metadata = ChromaDBAdapter.flatten_entities_for_storage(
                people=people_list,
                organizations=orgs_list,
                locations=locs_list,
                technologies=technologies_list
            )

            # Use enriched metadata for ChromaDB (already flat key-value)
            base_metadata = {
                **sanitized_enriched,  # All the LLM-enriched fields (sanitized)
                **entity_metadata,     # Flattened entity lists (via adapter)
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

                    # Use document's actual created_at date, not ingestion time
                    # This is critical for daily notes to show documents on correct dates
                    doc_created_at = datetime.now()
                    if created_date:
                        # Convert date to datetime (midnight)
                        doc_created_at = datetime.combine(created_date, datetime.min.time())

                    file_path = self.obsidian_service.export_document(
                        title=title,
                        content=content,
                        metadata=enriched_metadata,
                        document_type=document_type,
                        created_at=doc_created_at,
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

                # Generate vCards for people (if any)
                try:
                    people = enriched_metadata.get('people', [])
                    if people:
                        # Filter out generic roles (keep only specific named people)
                        filtered_people = self.entity_filter.filter_people(people)

                        # Show what was filtered
                        filtered_out = [p for p in people if p not in filtered_people]
                        if filtered_out:
                            # Handle both string and dict formats
                            filtered_names = [p if isinstance(p, str) else p.get('name', '') for p in filtered_out]
                            logger.info(f"🔍 Filtered out generic roles: {', '.join(filtered_names)}")

                        if filtered_people and self.contact_service:
                            # Handle both string and dict formats
                            people_names = [p if isinstance(p, str) else p.get('name', '') for p in filtered_people]
                            logger.info(f"👥 Creating vCards for {len(filtered_people)} specific people: {', '.join(people_names)}")
                            vcards_created = self.contact_service.create_vcards_from_metadata(
                                people=filtered_people,
                                organizations=enriched_metadata.get('entities', {}).get('orgs', []),
                                document_title=title,
                                document_id=doc_id
                            )
                            logger.info(f"✅ Created {len(vcards_created)} vCard(s) → {self.contact_service.output_dir}")
                        elif filtered_people:
                            logger.debug(f"ℹ️  VCF export disabled, skipping {len(filtered_people)} people")
                        else:
                            logger.info(f"ℹ️  No specific people found (all {len(people)} were generic roles)")
                except Exception as e:
                    logger.warning(f"⚠️ vCard generation failed: {e}")

                # Generate iCal events for dates (if any, and if service enabled)
                try:
                    dates = enriched_metadata.get('entities', {}).get('dates', [])
                    if dates and self.calendar_service:
                        logger.info(f"📅 Generating calendar events for {len(dates)} dates...")
                        events_created = self.calendar_service.create_events_from_metadata(
                            dates=dates,
                            document_title=title,
                            document_content=content,
                            document_topics=enriched_metadata.get('topics', [])
                        )
                        logger.info(f"✅ Created {len(events_created)} calendar event(s) → {self.calendar_service.output_dir}")
                    elif dates:
                        logger.debug(f"ℹ️  ICS export disabled, skipping {len(dates)} dates")
                except Exception as e:
                    logger.warning(f"⚠️ Calendar event generation failed: {e}")

            logger.info(f"✅ Processed document {doc_id}: {len(chunks)} chunks, Obsidian: {bool(obsidian_path)}")

            # Convert obsidian_metadata to dict and add enrichment_version
            response_metadata = obsidian_metadata.model_dump() if hasattr(obsidian_metadata, 'model_dump') else obsidian_metadata.dict()
            response_metadata["enrichment_version"] = enriched_metadata.get("enrichment_version", "2.0")

            return IngestResponse(
                success=True,
                doc_id=doc_id,
                chunks=len(chunks),
                metadata=response_metadata,
                obsidian_path=obsidian_path,
                critique=critique_result
            )

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

    async def process_document_pipeline(self,
                                        content: str,
                                        filename: str = None,
                                        document_type: DocumentType = DocumentType.text) -> IngestResponse:
        """
        Process document using modular pipeline architecture.

        This is the new pipeline-based implementation that replaces the monolithic
        process_document() method. Uses the stage-based pipeline:
          RawDocument → Enrichment → QualityGate → Chunking → Storage → Export

        Args:
            content: Document content
            filename: Optional filename
            document_type: Type of document

        Returns:
            IngestResponse with ingestion results
        """
        # Validate content
        if not content or not content.strip():
            raise ValueError("Document content cannot be empty")

        if len(content.strip()) < 10:
            raise ValueError("Document content must be at least 10 characters long")

        # Clean content
        content = self._clean_content(content)

        doc_id = str(uuid.uuid4())

        # Check for duplicate content
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        try:
            existing_docs = collection.get(
                where={"content_hash": content_hash},
                limit=1
            )
            if existing_docs and existing_docs['ids']:
                first_id = existing_docs['ids'][0]
                if isinstance(first_id, list):
                    first_id = first_id[0] if first_id else ""
                existing_doc_id = first_id.split('_chunk_')[0] if isinstance(first_id, str) else str(first_id)
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
            logger.info(f"▶️  Starting pipeline ingestion: {filename or doc_id}")

            # Create raw document
            raw_doc = RawDocument(
                content=content,
                filename=filename,
                document_type=document_type
            )

            # Create pipeline context
            context = StageContext(
                doc_id=doc_id,
                filename=filename
            )

            # Run pipeline
            result, output = await self.pipeline.run(raw_doc, context)

            # Handle pipeline results
            if result == StageResult.STOP:
                logger.warning(f"⛔ Document gated: {context.gate_reason}")
                # Return minimal response for gated documents
                return IngestResponse(
                    success=False,
                    doc_id=doc_id,
                    chunks=0,
                    metadata={
                        "title": filename or "Unknown",
                        "gated": True,
                        "gate_reason": context.gate_reason,
                        "triage_category": getattr(context, 'triage_category', None),
                        "triage_confidence": getattr(context, 'triage_confidence', None),
                        "keywords": {"tags": [], "topics": []},
                        "entities": {"people": [], "organizations": [], "locations": [], "technologies": []}
                    },
                    obsidian_path=None,
                    message=f"Document blocked by {context.gate_reason} filter"
                )
            elif result == StageResult.ERROR:
                raise HTTPException(status_code=500, detail="Pipeline processing failed")

            # Success - extract response data from output
            # With export disabled, output is StoredDocument (has chunk_count)
            # With export enabled, output is ExportedDocument (need to get from metadata)
            logger.info(f"Output type: {type(output).__name__}, has chunk_count: {hasattr(output, 'chunk_count')}")
            if hasattr(output, 'chunk_count'):
                chunk_count = output.chunk_count
                enriched_metadata = output.enriched_metadata
                logger.info(f"Using StoredDocument: chunk_count={chunk_count}")
            else:
                chunk_count = output.metadata.get('chunks', 0)
                enriched_metadata = output.metadata
                logger.info(f"Using ExportedDocument: chunk_count={chunk_count}")

            logger.info(f"✅ Pipeline complete: {doc_id} ({chunk_count} chunks)")

            # Convert enriched_metadata to ObsidianMetadata for IngestResponse
            # Extract and format fields from flat enriched_metadata dict
            tags_list = enriched_metadata.get("tags", [])
            if isinstance(tags_list, str):
                tags_list = [t.strip() for t in tags_list.split(',') if t.strip()]

            people_list = enriched_metadata.get("people", [])
            if isinstance(people_list, str):
                people_list = [p.strip() for p in people_list.split(',') if p.strip()]

            orgs_list = enriched_metadata.get("organizations", [])
            if isinstance(orgs_list, str):
                orgs_list = [o.strip() for o in orgs_list.split(',') if o.strip()]

            locs_list = enriched_metadata.get("locations", [])
            if isinstance(locs_list, str):
                locs_list = [l.strip() for l in locs_list.split(',') if l.strip()]

            tech_list = enriched_metadata.get("technologies", [])
            if isinstance(tech_list, str):
                tech_list = [t.strip() for t in tech_list.split(',') if t.strip()]

            dates_list = enriched_metadata.get("dates", [])
            if isinstance(dates_list, str):
                dates_list = [d.strip() for d in dates_list.split(',') if d.strip()]

            # Extract summary
            summary_value = enriched_metadata.get("summary", "")
            if isinstance(summary_value, dict):
                summary_str = summary_value.get("tl_dr", "") or summary_value.get("text", "") or str(summary_value)
            else:
                summary_str = str(summary_value) if summary_value else ""

            # Convert document_type string to enum
            doc_type_str = enriched_metadata.get("document_type", "text")
            if isinstance(doc_type_str, str) and doc_type_str.startswith("DocumentType."):
                doc_type_str = doc_type_str.replace("DocumentType.", "")
            try:
                doc_type_enum = DocumentType[doc_type_str]
            except (KeyError, TypeError):
                doc_type_enum = DocumentType.text

            # Create ObsidianMetadata
            response_metadata = ObsidianMetadata(
                title=enriched_metadata.get("title", filename or "Untitled"),
                keywords=Keywords(
                    primary=tags_list[:3] if tags_list else [],
                    secondary=tags_list[3:] if len(tags_list) > 3 else []
                ),
                tags=[f"#{tag}" if not tag.startswith("#") else tag for tag in tags_list],
                summary=summary_str,
                abstract=summary_str,
                key_points=enriched_metadata.get("key_points", []),
                entities=Entities(
                    people=people_list,
                    organizations=orgs_list,
                    locations=locs_list,
                    technologies=tech_list
                ),
                reading_time=f"{enriched_metadata.get('estimated_reading_time_min', 1)} min",
                complexity=ComplexityLevel[enriched_metadata.get("complexity", "intermediate")],
                links=[],
                document_type=doc_type_enum,
                source=filename or "",
                created_at=datetime.now(),
                dates=dates_list,
                dates_detailed=enriched_metadata.get("dates_detailed", [])
            )

            # Get obsidian_path from output if available (ExportedDocument has it, StoredDocument doesn't)
            obsidian_path = getattr(output, 'obsidian_path', None)

            return IngestResponse(
                success=True,
                doc_id=doc_id,
                chunks=chunk_count,
                metadata=response_metadata,
                obsidian_path=obsidian_path
            )

        except Exception as e:
            logger.error(f"Pipeline processing failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

    async def process_file(self, file_path: str, process_ocr: bool = False, generate_obsidian: bool = True, use_critic: bool = False, use_iteration: bool = False, process_attachments: bool = True) -> IngestResponse:
        """
        Process a file from path

        Args:
            file_path: Path to file
            process_ocr: Enable OCR for images
            generate_obsidian: Generate Obsidian markdown
            use_critic: Use LLM-as-critic quality scoring
            use_iteration: Use self-improvement loop
            process_attachments: Process email attachments as separate documents (default: True)
        """
        try:
            # Extract text using document service
            logger.info(f"🔄 Processing file: {file_path}")
            content, document_type, metadata = await self.document_service.extract_text_from_file(
                file_path,
                process_ocr=process_ocr
            )

            filename = Path(file_path).name

            # For emails with attachments: extract attachment summaries FIRST
            attachment_summaries = []
            if process_attachments and metadata.get('has_attachments', False):
                attachment_paths = metadata.get('attachment_paths', [])
                if attachment_paths:
                    logger.info(f"📎 Extracting summaries from {len(attachment_paths)} attachments for email context...")
                    attachment_summaries = await self._extract_attachment_summaries(
                        attachment_paths=attachment_paths,
                        process_ocr=process_ocr
                    )

                    # Add attachment context to email content
                    if attachment_summaries:
                        attachment_context = "\n\n--- ATTACHMENT SUMMARIES (for context) ---\n"
                        for att in attachment_summaries:
                            attachment_context += f"\n📎 {att['filename']}:\n{att['summary']}\n"
                        content += attachment_context
                        logger.info(f"✅ Added {len(attachment_summaries)} attachment summaries to email enrichment context")

            # Process main document (now with attachment context if applicable)
            # Use pipeline if enabled and no critic/iteration requested (pipeline doesn't support those yet)
            use_pipeline = os.getenv("USE_PIPELINE", "true").lower() == "true"
            if use_pipeline and not use_critic and not use_iteration:
                logger.info("Using pipeline-based ingestion")
                result = await self.process_document_pipeline(
                    content=content,
                    filename=filename,
                    document_type=document_type
                )
            else:
                if use_critic or use_iteration:
                    logger.info("Using legacy ingestion (critic/iteration requested)")
                result = await self.process_document(
                    content=content,
                    filename=filename,
                    document_type=document_type,
                    process_ocr=process_ocr,
                    generate_obsidian=generate_obsidian,
                    file_metadata=metadata,
                    use_critic=use_critic,
                    use_iteration=use_iteration
                )

            # Process email attachments as full documents (now that parent is enriched)
            if process_attachments and metadata.get('has_attachments', False):
                attachment_paths = metadata.get('attachment_paths', [])
                if attachment_paths:
                    logger.info(f"📎 Processing {len(attachment_paths)} email attachments as separate documents...")
                    await self._process_email_attachments(
                        attachment_paths=attachment_paths,
                        parent_doc_id=result.doc_id,
                        parent_metadata=metadata,
                        process_ocr=process_ocr,
                        generate_obsidian=generate_obsidian
                    )

            return result
        except Exception as e:
            logger.error(f"File processing failed for {file_path}: {e}")
            raise

    async def _process_email_attachments(
        self,
        attachment_paths: List[str],
        parent_doc_id: str,
        parent_metadata: Dict[str, Any],
        process_ocr: bool = False,
        generate_obsidian: bool = True
    ):
        """
        Process email attachments as separate documents

        Args:
            attachment_paths: List of paths to attachment files
            parent_doc_id: Document ID of parent email
            parent_metadata: Metadata from parent email (for threading context)
            process_ocr: Enable OCR for image attachments
            generate_obsidian: Generate Obsidian markdown for attachments
        """
        success_count = 0
        skip_count = 0
        attachment_doc_ids = []  # Collect attachment doc IDs for WikiLinks

        for att_path in attachment_paths:
            att_path_obj = Path(att_path)

            # Skip non-document attachments (logos, icons, etc.)
            if att_path_obj.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico']:
                # Only process if they're large enough to be content (not logos)
                if att_path_obj.exists() and att_path_obj.stat().st_size < 50000:  # < 50KB = likely logo/icon
                    logger.debug(f"   ⏭️  Skipping small image: {att_path_obj.name} ({att_path_obj.stat().st_size} bytes)")
                    skip_count += 1
                    continue

            try:
                # Extract content from attachment
                content, doc_type, att_metadata = await self.document_service.extract_text_from_file(
                    att_path,
                    process_ocr=process_ocr
                )

                # Skip if no meaningful content extracted
                if not content or len(content.strip()) < 20:
                    logger.debug(f"   ⏭️  Skipping attachment with minimal content: {att_path_obj.name}")
                    skip_count += 1
                    continue

                # Enrich attachment metadata with parent context
                att_metadata['parent_doc_id'] = parent_doc_id
                att_metadata['thread_id'] = parent_metadata.get('thread_id', '')
                att_metadata['subject'] = f"Attachment: {parent_metadata.get('subject', 'Email')}"
                att_metadata['is_attachment'] = True
                att_metadata['parent_sender'] = parent_metadata.get('sender', 'Unknown')

                # Process as regular document
                result = await self.process_document(
                    content=content,
                    filename=f"[Attachment] {att_path_obj.name}",
                    document_type=doc_type,
                    process_ocr=False,  # Already processed if needed
                    generate_obsidian=generate_obsidian,
                    file_metadata=att_metadata,
                    use_critic=False,  # Skip critic for attachments (cost optimization)
                    use_iteration=False
                )

                # Collect attachment doc ID and filename for WikiLinks
                if result.success and result.doc_id:
                    attachment_doc_ids.append({
                        'doc_id': result.doc_id,
                        'filename': att_path_obj.name,
                        'obsidian_path': result.obsidian_path
                    })

                success_count += 1
                logger.info(f"   ✅ Processed attachment: {att_path_obj.name}")

            except Exception as e:
                logger.warning(f"   ⚠️  Failed to process attachment {att_path_obj.name}: {e}")
                continue

        # Update parent email with WikiLinks to attachments
        if attachment_doc_ids and generate_obsidian:
            await self._update_parent_with_attachment_links(parent_doc_id, attachment_doc_ids)

        logger.info(f"📎 Attachment processing complete: {success_count} processed, {skip_count} skipped")

    async def _extract_attachment_summaries(
        self,
        attachment_paths: List[str],
        process_ocr: bool = False
    ) -> List[Dict[str, str]]:
        """
        Extract quick summaries from attachments for email enrichment context

        Args:
            attachment_paths: List of paths to attachment files
            process_ocr: Enable OCR for image attachments

        Returns:
            List of dicts with filename and summary
        """
        summaries = []

        for att_path in attachment_paths:
            att_path_obj = Path(att_path)

            # Check file size first to avoid OOM on large attachments
            if att_path_obj.exists():
                file_size = att_path_obj.stat().st_size

                # Skip very large attachments (>1MB) for summary extraction
                # They will still be processed as separate documents later
                if file_size > 1_000_000:  # 1MB
                    logger.info(f"   ⏭️  Skipping large attachment for summary: {att_path_obj.name} ({file_size / 1_000_000:.1f}MB)")
                    continue

            # Skip non-document attachments (logos, icons, etc.)
            if att_path_obj.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico']:
                if att_path_obj.exists() and att_path_obj.stat().st_size < 50000:  # < 50KB
                    continue

            try:
                # Extract content from attachment
                content, doc_type, att_metadata = await self.document_service.extract_text_from_file(
                    att_path,
                    process_ocr=process_ocr
                )

                # Skip if no meaningful content
                if not content or len(content.strip()) < 20:
                    continue

                # Generate quick summary (first 500 chars)
                summary = content[:500].strip()
                if len(content) > 500:
                    summary += "..."

                summaries.append({
                    'filename': att_path_obj.name,
                    'summary': summary,
                    'doc_type': str(doc_type)
                })

            except Exception as e:
                logger.warning(f"   ⚠️  Failed to extract summary from {att_path_obj.name}: {e}")
                continue

        return summaries

    async def _update_parent_with_attachment_links(
        self,
        parent_doc_id: str,
        attachment_info: List[Dict[str, str]]
    ):
        """
        Update parent email's Obsidian file with WikiLinks to attachments

        Args:
            parent_doc_id: Document ID of parent email
            attachment_info: List of dicts with doc_id, filename, obsidian_path
        """
        try:
            # Find parent Obsidian file
            obsidian_path = Path(self.settings.obsidian_path)
            parent_files = list(obsidian_path.glob(f"*{parent_doc_id[:8]}*.md"))

            if not parent_files:
                logger.warning(f"Could not find parent Obsidian file for {parent_doc_id}")
                return

            parent_file = parent_files[0]

            # Read current content
            with open(parent_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Replace file path listings with WikiLinks
            if "--- Attachments ---" in content:
                # Find the attachments section and replace with WikiLinks
                lines = content.split('\n')
                new_lines = []
                in_attachments = False

                for line in lines:
                    if "--- Attachments ---" in line:
                        in_attachments = True
                        new_lines.append(line)
                        # Add WikiLinks
                        for att in attachment_info:
                            # Extract just the filename from the Obsidian path
                            if att.get('obsidian_path'):
                                obsidian_filename = Path(att['obsidian_path']).stem
                                new_lines.append(f"- 📎 [[{obsidian_filename}|{att['filename']}]]")
                        continue
                    elif in_attachments and line.startswith('📎'):
                        # Skip old file path listings
                        continue
                    elif in_attachments and not line.strip():
                        # End of attachments section
                        in_attachments = False

                    new_lines.append(line)

                # Write updated content
                with open(parent_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(new_lines))

                logger.info(f"✅ Updated parent email with {len(attachment_info)} attachment WikiLinks")

        except Exception as e:
            logger.error(f"Failed to update parent with attachment links: {e}")

    async def process_file_from_watch(self, file_path: str):
        """Process file from watch folder and move to processed"""
        try:
            import shutil
            result = await self.process_file(file_path, process_ocr=True, generate_obsidian=True)

            # Get PATHS from app (or could be passed to constructor)
            from app import PATHS

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

