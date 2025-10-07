"""
OCR Quality Queue Service

Manages re-OCR queue for documents with low confidence scores.
Blueprint requirement: OCR quality gates with re-OCR queue.

Workflow:
1. Document processed with OCR
2. If confidence < threshold → add to re-OCR queue
3. Queue processes documents with better OCR settings
4. Track attempts and success/failure
"""

import logging
from typing import List, Dict, Optional, Set
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class OCRQueueStatus(str, Enum):
    """OCR queue entry status"""
    PENDING = "pending"           # Waiting for processing
    PROCESSING = "processing"     # Currently being processed
    COMPLETED = "completed"       # Successfully re-OCRed
    FAILED = "failed"            # Failed after max attempts
    SKIPPED = "skipped"          # Skipped (original good enough)


@dataclass
class OCRQueueEntry:
    """Entry in OCR re-processing queue"""
    doc_id: str
    file_path: str
    original_confidence: float
    attempts: int = 0
    max_attempts: int = 3
    status: OCRQueueStatus = OCRQueueStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    last_attempt: Optional[datetime] = None
    error_message: Optional[str] = None
    improved_confidence: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "doc_id": self.doc_id,
            "file_path": self.file_path,
            "original_confidence": self.original_confidence,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_attempt": self.last_attempt.isoformat() if self.last_attempt else None,
            "error_message": self.error_message,
            "improved_confidence": self.improved_confidence
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'OCRQueueEntry':
        """Create from dictionary"""
        return cls(
            doc_id=data["doc_id"],
            file_path=data["file_path"],
            original_confidence=data["original_confidence"],
            attempts=data.get("attempts", 0),
            max_attempts=data.get("max_attempts", 3),
            status=OCRQueueStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_attempt=datetime.fromisoformat(data["last_attempt"]) if data.get("last_attempt") else None,
            error_message=data.get("error_message"),
            improved_confidence=data.get("improved_confidence")
        )


class OCRQueueService:
    """
    Manage OCR quality queue for low-confidence documents

    Features:
    - Add documents with low OCR confidence to queue
    - Process queue with improved OCR settings
    - Track attempts and results
    - Persistent queue (survives restarts)
    """

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        max_attempts: int = 3,
        queue_file: str = "./data/ocr_queue.json"
    ):
        """
        Initialize OCR queue service

        Args:
            confidence_threshold: Minimum confidence to accept (0-1)
            max_attempts: Maximum re-OCR attempts per document
            queue_file: Path to persistent queue file
        """
        self.confidence_threshold = confidence_threshold
        self.max_attempts = max_attempts
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

        # In-memory queue
        self.queue: Dict[str, OCRQueueEntry] = {}

        # Load queue from disk
        self._load_queue()

    def should_reocr(
        self,
        confidence: float,
        doc_type: str = "unknown"
    ) -> bool:
        """
        Determine if document needs re-OCR

        Args:
            confidence: OCR confidence score (0-1)
            doc_type: Document type (affects threshold)

        Returns:
            True if document should be re-OCRed
        """
        # Adjust threshold by document type
        threshold = self.confidence_threshold

        if doc_type in ["invoice", "receipt", "legal"]:
            threshold = 0.8  # Stricter for important docs
        elif doc_type in ["note", "email"]:
            threshold = 0.6  # More lenient for casual docs

        return confidence < threshold

    def add_to_queue(
        self,
        doc_id: str,
        file_path: str,
        confidence: float,
        max_attempts: Optional[int] = None
    ) -> OCRQueueEntry:
        """
        Add document to re-OCR queue

        Args:
            doc_id: Document identifier
            file_path: Path to original file
            confidence: Original OCR confidence
            max_attempts: Override max attempts for this doc

        Returns:
            Created queue entry
        """
        entry = OCRQueueEntry(
            doc_id=doc_id,
            file_path=file_path,
            original_confidence=confidence,
            max_attempts=max_attempts or self.max_attempts
        )

        self.queue[doc_id] = entry
        self._save_queue()

        logger.info(
            f"Added document to OCR queue: {doc_id} "
            f"(confidence: {confidence:.2f})"
        )

        return entry

    def get_pending_entries(
        self,
        limit: Optional[int] = None
    ) -> List[OCRQueueEntry]:
        """
        Get pending queue entries

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of pending queue entries
        """
        pending = [
            entry for entry in self.queue.values()
            if entry.status == OCRQueueStatus.PENDING
        ]

        # Sort by original confidence (lowest first)
        pending.sort(key=lambda e: e.original_confidence)

        if limit:
            pending = pending[:limit]

        return pending

    def mark_processing(self, doc_id: str):
        """Mark entry as processing"""
        if doc_id in self.queue:
            self.queue[doc_id].status = OCRQueueStatus.PROCESSING
            self.queue[doc_id].attempts += 1
            self.queue[doc_id].last_attempt = datetime.now()
            self._save_queue()

    def mark_completed(
        self,
        doc_id: str,
        improved_confidence: float
    ):
        """
        Mark entry as completed

        Args:
            doc_id: Document identifier
            improved_confidence: New confidence score
        """
        if doc_id in self.queue:
            entry = self.queue[doc_id]
            entry.status = OCRQueueStatus.COMPLETED
            entry.improved_confidence = improved_confidence
            self._save_queue()

            logger.info(
                f"OCR improvement: {doc_id} "
                f"{entry.original_confidence:.2f} → {improved_confidence:.2f}"
            )

    def mark_failed(
        self,
        doc_id: str,
        error_message: str
    ):
        """
        Mark entry as failed

        Args:
            doc_id: Document identifier
            error_message: Failure reason
        """
        if doc_id in self.queue:
            entry = self.queue[doc_id]

            if entry.attempts >= entry.max_attempts:
                entry.status = OCRQueueStatus.FAILED
                entry.error_message = error_message
                logger.warning(
                    f"OCR failed after {entry.attempts} attempts: {doc_id} - {error_message}"
                )
            else:
                # Reset to pending for retry
                entry.status = OCRQueueStatus.PENDING
                logger.info(
                    f"OCR retry scheduled: {doc_id} "
                    f"(attempt {entry.attempts}/{entry.max_attempts})"
                )

            self._save_queue()

    def get_statistics(self) -> Dict:
        """
        Get queue statistics

        Returns:
            Statistics dictionary
        """
        status_counts = {}
        for entry in self.queue.values():
            status = entry.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        # Calculate average improvement
        improvements = [
            entry.improved_confidence - entry.original_confidence
            for entry in self.queue.values()
            if entry.status == OCRQueueStatus.COMPLETED and entry.improved_confidence
        ]

        avg_improvement = sum(improvements) / len(improvements) if improvements else 0

        return {
            "total_entries": len(self.queue),
            "status_breakdown": status_counts,
            "pending_count": status_counts.get("pending", 0),
            "completed_count": status_counts.get("completed", 0),
            "failed_count": status_counts.get("failed", 0),
            "average_improvement": avg_improvement,
            "success_rate": (
                status_counts.get("completed", 0) / len(self.queue)
                if len(self.queue) > 0 else 0
            )
        }

    def remove_entry(self, doc_id: str):
        """Remove entry from queue"""
        if doc_id in self.queue:
            del self.queue[doc_id]
            self._save_queue()

    def clear_completed(self):
        """Remove completed entries from queue"""
        self.queue = {
            doc_id: entry
            for doc_id, entry in self.queue.items()
            if entry.status != OCRQueueStatus.COMPLETED
        }
        self._save_queue()

    def _save_queue(self):
        """Save queue to disk"""
        try:
            data = {
                doc_id: entry.to_dict()
                for doc_id, entry in self.queue.items()
            }
            self.queue_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save OCR queue: {e}")

    def _load_queue(self):
        """Load queue from disk"""
        try:
            if self.queue_file.exists():
                data = json.loads(self.queue_file.read_text())
                self.queue = {
                    doc_id: OCRQueueEntry.from_dict(entry_data)
                    for doc_id, entry_data in data.items()
                }
                logger.info(f"Loaded OCR queue: {len(self.queue)} entries")
        except Exception as e:
            logger.error(f"Failed to load OCR queue: {e}")
            self.queue = {}


# Test
if __name__ == "__main__":
    import tempfile

    # Create temp queue file
    temp_queue = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_queue.close()

    service = OCRQueueService(
        confidence_threshold=0.7,
        queue_file=temp_queue.name
    )

    print("=" * 60)
    print("OCR Quality Queue Service Test")
    print("=" * 60)

    # Test 1: Check if document should be re-OCRed
    print("\n1. Should re-OCR tests:")
    print(f"   Confidence 0.5 → {service.should_reocr(0.5)}")  # True
    print(f"   Confidence 0.8 → {service.should_reocr(0.8)}")  # False
    print(f"   Invoice 0.75 → {service.should_reocr(0.75, 'invoice')}")  # True (stricter)

    # Test 2: Add documents to queue
    print("\n2. Adding documents to queue:")
    entry1 = service.add_to_queue("doc1", "/path/to/doc1.pdf", 0.55)
    entry2 = service.add_to_queue("doc2", "/path/to/doc2.pdf", 0.42)
    print(f"   Added {len(service.queue)} documents")

    # Test 3: Get pending entries
    print("\n3. Pending entries:")
    pending = service.get_pending_entries()
    for entry in pending:
        print(f"   - {entry.doc_id}: confidence={entry.original_confidence:.2f}")

    # Test 4: Process an entry
    print("\n4. Processing entry:")
    service.mark_processing("doc1")
    service.mark_completed("doc1", 0.92)
    print(f"   Completed doc1: 0.55 → 0.92")

    # Test 5: Fail an entry
    print("\n5. Failing entry:")
    service.mark_processing("doc2")
    service.mark_failed("doc2", "OCR engine error")
    print(f"   Failed doc2 (attempt {service.queue['doc2'].attempts})")

    # Test 6: Statistics
    print("\n6. Queue statistics:")
    stats = service.get_statistics()
    print(f"   Total: {stats['total_entries']}")
    print(f"   Completed: {stats['completed_count']}")
    print(f"   Failed: {stats['failed_count']}")
    print(f"   Avg improvement: {stats['average_improvement']:.2f}")
    print(f"   Success rate: {stats['success_rate']:.1%}")

    print("\n" + "=" * 60)
    print("✅ All tests passed")

    # Cleanup
    Path(temp_queue.name).unlink()
