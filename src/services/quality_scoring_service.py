"""
Quality Scoring Service - Implements do_index quality gates

Based on personal_rag_pipeline_full.md blueprint:
- quality_score: OCR confidence, parse ratio, structural integrity
- novelty_score: New info vs corpus (TF-IDF/cosine)
- actionability_score: Hits watchlist (people/projects/topics/dates)
- signalness: Composite score (0.4*quality + 0.3*novelty + 0.3*actionability)
- do_index: Gate based on per-document-type thresholds
"""

from typing import Dict, Optional
from enum import Enum
from datetime import datetime


class DocumentType(str, Enum):
    """Document types with different quality thresholds"""
    EMAIL_THREAD = "email.thread"
    CHAT_DAILY = "chat.daily"
    PDF_REPORT = "pdf.report"
    WEB_ARTICLE = "web.article"
    NOTE = "note"
    TEXT = "text"
    LEGAL = "legal"
    GENERIC = "generic"


# Quality gates per document type (from blueprint)
QUALITY_GATES = {
    DocumentType.EMAIL_THREAD: {"min_quality": 0.70, "min_signal": 0.60},
    DocumentType.CHAT_DAILY: {"min_quality": 0.65, "min_signal": 0.60},
    DocumentType.PDF_REPORT: {"min_quality": 0.75, "min_signal": 0.65},
    DocumentType.WEB_ARTICLE: {"min_quality": 0.70, "min_signal": 0.60},
    DocumentType.NOTE: {"min_quality": 0.60, "min_signal": 0.50},
    DocumentType.TEXT: {"min_quality": 0.65, "min_signal": 0.55},
    DocumentType.LEGAL: {"min_quality": 0.80, "min_signal": 0.70},
    DocumentType.GENERIC: {"min_quality": 0.65, "min_signal": 0.55},
}


class QualityScoringService:
    """
    Calculate quality scores and determine do_index gates

    Implements blueprint-compliant scoring:
    1. quality_score - Content integrity (OCR, parsing, structure)
    2. novelty_score - New vs existing corpus
    3. actionability_score - Relevance to watchlist
    4. signalness - Composite score
    5. do_index - Gate decision
    """

    def __init__(self):
        self.gates = QUALITY_GATES

    def calculate_quality_score(
        self,
        content: str,
        ocr_confidence: Optional[float] = None,
        parse_quality: Optional[float] = None,
        has_structure: bool = True
    ) -> float:
        """
        Calculate quality score (0-1)

        Factors:
        - OCR confidence (if applicable)
        - Parse quality (clean extraction)
        - Structure integrity (headings, formatting)
        - Content length (min threshold)
        """
        scores = []

        # OCR confidence (if provided)
        if ocr_confidence is not None:
            scores.append(ocr_confidence)

        # Parse quality (if provided)
        if parse_quality is not None:
            scores.append(parse_quality)

        # Content length (penalize very short)
        char_count = len(content.strip())
        if char_count < 100:
            length_score = char_count / 100.0
        elif char_count < 300:
            length_score = 0.7
        else:
            length_score = 1.0
        scores.append(length_score)

        # Structure (has headings/formatting)
        structure_score = 1.0 if has_structure else 0.7
        scores.append(structure_score)

        # Average all factors
        return sum(scores) / len(scores) if scores else 0.8

    def calculate_novelty_score(
        self,
        content: str,
        existing_docs_count: int = 0,
        content_hash: Optional[str] = None
    ) -> float:
        """
        Calculate novelty score (0-1)

        Simple heuristic for now:
        - New corpus = higher novelty
        - More docs = lower baseline novelty
        - Could be enhanced with TF-IDF/cosine similarity
        """
        # Baseline: new corpus = high novelty
        if existing_docs_count < 10:
            return 0.9
        elif existing_docs_count < 50:
            return 0.7
        elif existing_docs_count < 200:
            return 0.6
        else:
            return 0.5

    def calculate_actionability_score(
        self,
        metadata: Dict,
        watchlist_people: Optional[list] = None,
        watchlist_projects: Optional[list] = None,
        watchlist_topics: Optional[list] = None
    ) -> float:
        """
        Calculate actionability score (0-1)

        Factors:
        - Hits watchlist people/projects/topics
        - Recent dates (within time window)
        - Actionable keywords (deadline, decision, urgent)
        """
        score = 0.5  # Baseline

        # Check watchlist hits
        people = metadata.get("people_roles", "").lower() if metadata.get("people_roles") else ""
        projects = metadata.get("projects", "").lower() if metadata.get("projects") else ""
        topics = metadata.get("topics", "").lower() if metadata.get("topics") else ""

        if watchlist_people and any(p.lower() in people for p in watchlist_people):
            score += 0.2

        if watchlist_projects and any(p.lower() in projects for p in watchlist_projects):
            score += 0.2

        if watchlist_topics and any(t.lower() in topics for t in watchlist_topics):
            score += 0.1

        # Check for actionable dates (recent or upcoming)
        dates_str = metadata.get("dates", "")
        if dates_str:
            # If has dates, slightly more actionable
            score += 0.1

        return min(1.0, score)

    def calculate_signalness(
        self,
        quality: float,
        novelty: float,
        actionability: float
    ) -> float:
        """
        Calculate composite signalness score

        Blueprint formula:
        signalness = 0.4*quality + 0.3*novelty + 0.3*actionability
        """
        return 0.4 * quality + 0.3 * novelty + 0.3 * actionability

    def should_index(
        self,
        document_type: str,
        quality_score: float,
        signalness: float
    ) -> bool:
        """
        Determine if document should be indexed

        Uses per-document-type thresholds from blueprint
        """
        # Normalize document_type
        doc_type = self._normalize_doc_type(document_type)

        # Get gates for this type
        gates = self.gates.get(doc_type, self.gates[DocumentType.GENERIC])

        # Check thresholds
        passes_quality = quality_score >= gates["min_quality"]
        passes_signal = signalness >= gates["min_signal"]

        return passes_quality and passes_signal

    def _normalize_doc_type(self, doc_type: str) -> DocumentType:
        """Normalize document type string to enum"""
        doc_type_lower = doc_type.lower()

        if "email" in doc_type_lower or "thread" in doc_type_lower:
            return DocumentType.EMAIL_THREAD
        elif "chat" in doc_type_lower:
            return DocumentType.CHAT_DAILY
        elif "pdf" in doc_type_lower or "report" in doc_type_lower:
            return DocumentType.PDF_REPORT
        elif "web" in doc_type_lower or "article" in doc_type_lower:
            return DocumentType.WEB_ARTICLE
        elif "note" in doc_type_lower:
            return DocumentType.NOTE
        elif "legal" in doc_type_lower or "court" in doc_type_lower:
            return DocumentType.LEGAL
        elif "text" in doc_type_lower:
            return DocumentType.TEXT
        else:
            return DocumentType.GENERIC

    def score_document(
        self,
        content: str,
        document_type: str,
        metadata: Dict,
        ocr_confidence: Optional[float] = None,
        existing_docs_count: int = 0,
        watchlist_people: Optional[list] = None,
        watchlist_projects: Optional[list] = None,
        watchlist_topics: Optional[list] = None
    ) -> Dict:
        """
        Complete scoring pipeline for a document

        Returns:
            {
                "quality_score": float,
                "novelty_score": float,
                "actionability_score": float,
                "signalness": float,
                "do_index": bool,
                "gate_reason": str (if not indexed)
            }
        """
        # Calculate scores
        has_structure = "#" in content or "##" in content  # Simple heuristic

        quality = self.calculate_quality_score(
            content,
            ocr_confidence=ocr_confidence,
            has_structure=has_structure
        )

        novelty = self.calculate_novelty_score(
            content,
            existing_docs_count=existing_docs_count
        )

        actionability = self.calculate_actionability_score(
            metadata,
            watchlist_people=watchlist_people,
            watchlist_projects=watchlist_projects,
            watchlist_topics=watchlist_topics
        )

        signalness = self.calculate_signalness(quality, novelty, actionability)

        # Determine if should index
        do_index = self.should_index(document_type, quality, signalness)

        # Reason if not indexed
        gate_reason = None
        if not do_index:
            doc_type = self._normalize_doc_type(document_type)
            gates = self.gates.get(doc_type, self.gates[DocumentType.GENERIC])

            if quality < gates["min_quality"]:
                gate_reason = f"Quality {quality:.2f} < {gates['min_quality']}"
            elif signalness < gates["min_signal"]:
                gate_reason = f"Signal {signalness:.2f} < {gates['min_signal']}"

        return {
            "quality_score": round(quality, 3),
            "novelty_score": round(novelty, 3),
            "actionability_score": round(actionability, 3),
            "signalness": round(signalness, 3),
            "do_index": do_index,
            "gate_reason": gate_reason
        }
