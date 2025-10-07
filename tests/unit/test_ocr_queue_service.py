"""
Unit tests for OCRQueueService

Tests OCR quality queue for re-processing low confidence documents
"""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from src.services.ocr_queue_service import (
    OCRQueueService,
    OCRQueueEntry,
    OCRQueueStatus
)


class TestOCRQueueService:
    """Test the OCRQueueService class"""

    @pytest.fixture
    def temp_queue_file(self):
        """Create temporary queue file"""
        temp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        temp.close()
        yield temp.name
        # Cleanup
        Path(temp.name).unlink(missing_ok=True)

    @pytest.fixture
    def service(self, temp_queue_file):
        """Create OCRQueueService instance"""
        return OCRQueueService(
            confidence_threshold=0.7,
            max_attempts=3,
            queue_file=temp_queue_file
        )

    def test_init(self, temp_queue_file):
        """Test initialization"""
        service = OCRQueueService(
            confidence_threshold=0.8,
            max_attempts=5,
            queue_file=temp_queue_file
        )
        assert service.confidence_threshold == 0.8
        assert service.max_attempts == 5
        assert len(service.queue) == 0

    def test_should_reocr_below_threshold(self, service):
        """Test should_reocr returns True for low confidence"""
        assert service.should_reocr(0.5) is True
        assert service.should_reocr(0.6) is True

    def test_should_reocr_above_threshold(self, service):
        """Test should_reocr returns False for high confidence"""
        assert service.should_reocr(0.8) is False
        assert service.should_reocr(0.95) is False

    def test_should_reocr_document_type_adjustments(self, service):
        """Test threshold adjusts by document type"""
        # Invoice has stricter threshold (0.8)
        assert service.should_reocr(0.75, "invoice") is True
        assert service.should_reocr(0.85, "invoice") is False

        # Note has lenient threshold (0.6)
        assert service.should_reocr(0.65, "note") is False
        assert service.should_reocr(0.55, "note") is True

    def test_add_to_queue(self, service):
        """Test adding document to queue"""
        entry = service.add_to_queue("doc1", "/path/to/doc1.pdf", 0.55)

        assert entry.doc_id == "doc1"
        assert entry.original_confidence == 0.55
        assert entry.status == OCRQueueStatus.PENDING
        assert "doc1" in service.queue

    def test_add_multiple_to_queue(self, service):
        """Test adding multiple documents"""
        service.add_to_queue("doc1", "/path/1.pdf", 0.5)
        service.add_to_queue("doc2", "/path/2.pdf", 0.4)
        service.add_to_queue("doc3", "/path/3.pdf", 0.6)

        assert len(service.queue) == 3

    def test_get_pending_entries(self, service):
        """Test retrieving pending entries"""
        service.add_to_queue("doc1", "/path/1.pdf", 0.5)
        service.add_to_queue("doc2", "/path/2.pdf", 0.3)

        pending = service.get_pending_entries()

        assert len(pending) == 2
        # Should be sorted by confidence (lowest first)
        assert pending[0].original_confidence < pending[1].original_confidence

    def test_get_pending_entries_with_limit(self, service):
        """Test retrieving pending entries with limit"""
        for i in range(5):
            service.add_to_queue(f"doc{i}", f"/path/{i}.pdf", 0.5 - i * 0.05)

        pending = service.get_pending_entries(limit=3)

        assert len(pending) == 3

    def test_mark_processing(self, service):
        """Test marking entry as processing"""
        service.add_to_queue("doc1", "/path/1.pdf", 0.5)

        service.mark_processing("doc1")

        entry = service.queue["doc1"]
        assert entry.status == OCRQueueStatus.PROCESSING
        assert entry.attempts == 1
        assert entry.last_attempt is not None

    def test_mark_completed(self, service):
        """Test marking entry as completed"""
        service.add_to_queue("doc1", "/path/1.pdf", 0.5)
        service.mark_processing("doc1")
        service.mark_completed("doc1", 0.92)

        entry = service.queue["doc1"]
        assert entry.status == OCRQueueStatus.COMPLETED
        assert entry.improved_confidence == 0.92

    def test_mark_failed_with_retries_remaining(self, service):
        """Test marking entry as failed with retries remaining"""
        service.add_to_queue("doc1", "/path/1.pdf", 0.5)
        service.mark_processing("doc1")
        service.mark_failed("doc1", "OCR engine error")

        entry = service.queue["doc1"]
        # Should go back to pending for retry
        assert entry.status == OCRQueueStatus.PENDING
        assert entry.attempts == 1

    def test_mark_failed_max_attempts_reached(self, service):
        """Test marking entry as failed after max attempts"""
        service.add_to_queue("doc1", "/path/1.pdf", 0.5)

        # Simulate max attempts
        for i in range(service.max_attempts):
            service.mark_processing("doc1")
            service.mark_failed("doc1", "Persistent error")

        entry = service.queue["doc1"]
        assert entry.status == OCRQueueStatus.FAILED
        assert entry.attempts == service.max_attempts

    def test_get_statistics(self, service):
        """Test getting queue statistics"""
        service.add_to_queue("doc1", "/path/1.pdf", 0.5)
        service.add_to_queue("doc2", "/path/2.pdf", 0.4)
        service.mark_processing("doc1")
        service.mark_completed("doc1", 0.92)

        stats = service.get_statistics()

        assert stats["total_entries"] == 2
        assert stats["completed_count"] == 1
        assert stats["pending_count"] == 1
        assert stats["average_improvement"] > 0
        assert 0 <= stats["success_rate"] <= 1

    def test_remove_entry(self, service):
        """Test removing entry from queue"""
        service.add_to_queue("doc1", "/path/1.pdf", 0.5)
        assert "doc1" in service.queue

        service.remove_entry("doc1")
        assert "doc1" not in service.queue

    def test_clear_completed(self, service):
        """Test clearing completed entries"""
        service.add_to_queue("doc1", "/path/1.pdf", 0.5)
        service.add_to_queue("doc2", "/path/2.pdf", 0.4)

        service.mark_processing("doc1")
        service.mark_completed("doc1", 0.92)

        service.clear_completed()

        assert "doc1" not in service.queue
        assert "doc2" in service.queue

    def test_queue_persistence(self, temp_queue_file):
        """Test queue persists across restarts"""
        # Create service and add entries
        service1 = OCRQueueService(queue_file=temp_queue_file)
        service1.add_to_queue("doc1", "/path/1.pdf", 0.5)
        service1.add_to_queue("doc2", "/path/2.pdf", 0.4)

        # Create new service instance (simulates restart)
        service2 = OCRQueueService(queue_file=temp_queue_file)

        # Should load persisted queue
        assert len(service2.queue) == 2
        assert "doc1" in service2.queue
        assert "doc2" in service2.queue

    def test_entry_to_dict(self):
        """Test converting entry to dictionary"""
        entry = OCRQueueEntry(
            doc_id="doc1",
            file_path="/path/1.pdf",
            original_confidence=0.5
        )

        data = entry.to_dict()

        assert data["doc_id"] == "doc1"
        assert data["original_confidence"] == 0.5
        assert data["status"] == "pending"

    def test_entry_from_dict(self):
        """Test creating entry from dictionary"""
        data = {
            "doc_id": "doc1",
            "file_path": "/path/1.pdf",
            "original_confidence": 0.5,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }

        entry = OCRQueueEntry.from_dict(data)

        assert entry.doc_id == "doc1"
        assert entry.original_confidence == 0.5
        assert entry.status == OCRQueueStatus.PENDING
