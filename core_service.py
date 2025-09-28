#!/usr/bin/env python3
"""
Core RAG service functionality
"""

import logging
import chromadb
import hashlib
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from models import DocumentInfo, ProcessingStatus, SearchResult, DocumentType

logger = logging.getLogger(__name__)


class ChromaDBService:
    """ChromaDB service for vector operations"""

    def __init__(self, host: str = "chromadb", port: int = 8000):
        self.host = host
        self.port = port
        self.client = None
        self.collection = None

    async def connect(self):
        """Connect to ChromaDB"""
        try:
            self.client = chromadb.HttpClient(host=self.host, port=self.port)

            # Test connection
            heartbeat = self.client.heartbeat()
            logger.info("Connected to ChromaDB successfully")

            # Get or create collection
            try:
                self.collection = self.client.get_collection("documents")
                logger.info("Using existing 'documents' collection")
            except:
                self.collection = self.client.create_collection("documents")
                logger.info("Created new 'documents' collection")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            return False

    def add_documents(self, texts: List[str], metadatas: List[Dict], ids: List[str]) -> bool:
        """Add documents to the collection"""
        try:
            self.collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return False

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Search for similar documents"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )

            search_results = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    result = SearchResult(
                        id=results['ids'][0][i],
                        text=doc,
                        score=1 - results['distances'][0][i],  # Convert distance to similarity
                        metadata=results['metadatas'][0][i] if results['metadatas'][0] else {}
                    )
                    search_results.append(result)

            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_collection_count(self) -> int:
        """Get total number of documents in collection"""
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Failed to get collection count: {e}")
            return 0


class DocumentManager:
    """Document management service"""

    def __init__(self, storage_path: str = "/data"):
        self.storage_path = Path(storage_path)
        self.metadata_file = self.storage_path / "documents_metadata.json"
        self._documents = {}
        self._load_metadata()

    def _load_metadata(self):
        """Load document metadata from file"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                    self._documents = {
                        doc_id: DocumentInfo(**doc_data)
                        for doc_id, doc_data in data.items()
                    }
                logger.info(f"Loaded metadata for {len(self._documents)} documents")
            else:
                logger.info("No existing metadata file found")
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            self._documents = {}

    def _save_metadata(self):
        """Save document metadata to file"""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_file, 'w') as f:
                data = {
                    doc_id: doc_info.dict()
                    for doc_id, doc_info in self._documents.items()
                }
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def add_document(self, filename: str, file_type: DocumentType, size_bytes: int) -> str:
        """Add a new document"""
        doc_id = str(uuid.uuid4())
        doc_info = DocumentInfo(
            id=doc_id,
            filename=filename,
            file_type=file_type,
            size_bytes=size_bytes,
            processing_status=ProcessingStatus.PENDING,
            upload_time=datetime.now()
        )

        self._documents[doc_id] = doc_info
        self._save_metadata()

        logger.info(f"Added document {doc_id}: {filename}")
        return doc_id

    def update_document_status(self, doc_id: str, status: ProcessingStatus,
                             processing_time: Optional[float] = None,
                             chunk_count: Optional[int] = None,
                             error_message: Optional[str] = None):
        """Update document processing status"""
        if doc_id in self._documents:
            doc = self._documents[doc_id]
            doc.processing_status = status
            if processing_time is not None:
                doc.processing_time = processing_time
            if chunk_count is not None:
                doc.chunk_count = chunk_count
            if error_message is not None:
                doc.error_message = error_message

            self._save_metadata()
            logger.info(f"Updated document {doc_id} status to {status}")

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        """Get document information"""
        return self._documents.get(doc_id)

    def list_documents(self) -> List[DocumentInfo]:
        """List all documents"""
        return list(self._documents.values())

    def get_stats(self) -> Dict[str, Any]:
        """Get document statistics"""
        docs = list(self._documents.values())

        type_counts = {}
        status_counts = {}
        total_size = 0

        for doc in docs:
            # Count by type
            type_str = doc.file_type.value
            type_counts[type_str] = type_counts.get(type_str, 0) + 1

            # Count by status
            status_str = doc.processing_status.value
            status_counts[status_str] = status_counts.get(status_str, 0) + 1

            # Sum sizes
            total_size += doc.size_bytes

        return {
            "total_documents": len(docs),
            "total_chunks": sum(doc.chunk_count for doc in docs),
            "documents_by_type": type_counts,
            "processing_stats": status_counts,
            "storage_size_mb": total_size / (1024 * 1024)
        }


class TextSplitter:
    """Simple text splitter for chunking documents"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        """Split text into chunks"""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to break at sentence or paragraph boundary
            if end < len(text):
                for delimiter in ['\n\n', '\n', '. ', '! ', '? ']:
                    last_delim = text.rfind(delimiter, start, end)
                    if last_delim > start:
                        end = last_delim + len(delimiter)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - self.chunk_overlap

        return chunks


def generate_content_hash(content: str) -> str:
    """Generate hash for content deduplication"""
    return hashlib.sha256(content.encode()).hexdigest()


def detect_file_type(filename: str, content: bytes = None) -> DocumentType:
    """Detect file type from filename and content"""
    filename_lower = filename.lower()

    if filename_lower.endswith('.pdf'):
        return DocumentType.PDF
    elif filename_lower.endswith(('.doc', '.docx')):
        return DocumentType.DOCX
    elif filename_lower.endswith(('.ppt', '.pptx')):
        return DocumentType.PPTX
    elif filename_lower.endswith(('.xls', '.xlsx')):
        return DocumentType.XLSX
    elif filename_lower.endswith('.txt'):
        return DocumentType.TEXT
    elif filename_lower.endswith('.html'):
        return DocumentType.HTML
    elif filename_lower.endswith('.csv'):
        return DocumentType.CSV
    elif filename_lower.endswith('.json'):
        return DocumentType.JSON
    elif filename_lower.endswith('.eml'):
        return DocumentType.EMAIL
    elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
        return DocumentType.IMAGE
    elif 'whatsapp' in filename_lower:
        return DocumentType.WHATSAPP
    else:
        return DocumentType.TEXT  # Default fallback