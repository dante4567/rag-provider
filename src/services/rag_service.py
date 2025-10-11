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
    from src.services.tag_taxonomy_service import TagTaxonomyService
    from src.services.smart_triage_service import SmartTriageService
    from src.services.quality_scoring_service import QualityScoringService
    from src.services.contact_service import ContactService
    from src.services.calendar_service import CalendarService
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

            # Initialize Obsidian export service (formerly V3 - RAG-first)
            obsidian_output_dir = os.getenv("OBSIDIAN_VAULT_PATH", "./obsidian_vault")
            self.obsidian_service = ObsidianService(
                output_dir=obsidian_output_dir,
                refs_dir=f"{obsidian_output_dir}/refs"
            )

            # Initialize contact/calendar export services
            # Use absolute paths for Docker, relative for local dev
            contacts_default = "/data/contacts" if IS_DOCKER else "./data/contacts"
            calendar_default = "/data/calendar" if IS_DOCKER else "./data/calendar"
            contacts_output_dir = Path(os.getenv("CONTACTS_PATH", contacts_default))
            calendar_output_dir = Path(os.getenv("CALENDAR_PATH", calendar_default))
            self.contact_service = ContactService(output_dir=contacts_output_dir)
            self.calendar_service = CalendarService(output_dir=calendar_output_dir)

            # Initialize entity name filter (filters generic roles)
            self.entity_filter = EntityNameFilterService()

            # Initialize quality scoring service (blueprint do_index gates)
            self.quality_scoring_service = QualityScoringService()

            self.using_new_services = True
            logger.info("✅ EnrichmentService initialized with controlled vocabulary")
            logger.info(f"   📚 Topics: {len(self.vocabulary_service.get_all_topics())}")
            logger.info(f"   🏗️  Projects: {len(self.vocabulary_service.get_active_projects())}")
            logger.info(f"   📍 Places: {len(self.vocabulary_service.get_all_places())}")
            logger.info("✅ Structure-aware chunking enabled (ignores RAG:IGNORE blocks)")
            logger.info(f"✅ ObsidianService initialized (RAG-first format) → {obsidian_output_dir}")
            logger.info(f"✅ ContactService initialized → {contacts_output_dir}")
            logger.info(f"✅ CalendarService initialized → {calendar_output_dir}")
        except Exception as e:
            logger.error(f"❌ Service layer initialization failed: {e}")
            raise RuntimeError(f"Service layer is required but initialization failed: {e}")

    def setup_chromadb(self):
        global chroma_client, collection
        try:
            chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
            chroma_client.heartbeat()

            # Use Voyage-3-lite embeddings (best value: 85% cheaper, better quality)
            import voyageai
            from chromadb.api.types import EmbeddingFunction

            class VoyageEmbeddingFunction(EmbeddingFunction):
                def __init__(self, api_key: str, model_name: str = "voyage-3-lite"):
                    self.client = voyageai.Client(api_key=api_key)
                    self.model_name = model_name

                def __call__(self, input: list[str]) -> list[list[float]]:
                    """Embed texts using Voyage AI"""
                    response = self.client.embed(
                        input,
                        model=self.model_name,
                        input_type="document"
                    )
                    return response.embeddings

            voyage_ef = VoyageEmbeddingFunction(
                api_key=os.getenv("VOYAGE_API_KEY"),
                model_name="voyage-3-lite"
            )

            try:
                collection = chroma_client.get_collection(
                    name=COLLECTION_NAME,
                    embedding_function=voyage_ef
                )
            except:
                collection = chroma_client.create_collection(
                    name=COLLECTION_NAME,
                    embedding_function=voyage_ef,
                    metadata={"hnsw:space": "cosine"}
                )
            logger.info("✅ Connected to ChromaDB with Voyage-3-lite (512 dims, $0.02/1M tokens)")
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
                except:
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
            print(f"\n[APP.PY DEBUG] enriched_metadata after enrichment service:")
            print(f"  - 'people' in metadata: {'people' in enriched_metadata}")
            print(f"  - people value: {enriched_metadata.get('people', 'NOT FOUND')}")
            print(f"  - 'dates' in metadata: {'dates' in enriched_metadata}")
            print(f"  - dates value: {enriched_metadata.get('dates', 'NOT FOUND')}")
            print(f"  - 'entities' in metadata: {'entities' in enriched_metadata}")
            print(f"  - entities value: {enriched_metadata.get('entities', 'NOT FOUND')}\n")

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

                        if filtered_people:
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
                        else:
                            logger.info(f"ℹ️  No specific people found (all {len(people)} were generic roles)")
                except Exception as e:
                    logger.warning(f"⚠️ vCard generation failed: {e}")

                # Generate iCal events for dates (if any)
                try:
                    dates = enriched_metadata.get('entities', {}).get('dates', [])
                    if dates:
                        logger.info(f"📅 Generating calendar events for {len(dates)} dates...")
                        events_created = self.calendar_service.create_events_from_metadata(
                            dates=dates,
                            document_title=title,
                            document_content=content,
                            document_topics=enriched_metadata.get('topics', [])
                        )
                        logger.info(f"✅ Created {len(events_created)} calendar event(s) → {self.calendar_service.output_dir}")
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

    async def process_file(self, file_path: str, process_ocr: bool = False, generate_obsidian: bool = True, use_critic: bool = False, use_iteration: bool = False) -> IngestResponse:
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
                file_metadata=metadata,
                use_critic=use_critic,
                use_iteration=use_iteration
            )
        except Exception as e:
            logger.error(f"File processing failed for {file_path}: {e}")
            raise

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

