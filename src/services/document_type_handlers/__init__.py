"""
Document Type Handlers

Type-specific preprocessing, metadata extraction, and chunking strategies.
Each document type (email, scanned PDF, invoice, etc.) gets its own handler.
"""
from .base_handler import DocumentTypeHandler
from .email_handler import EmailHandler
from .chat_log_handler import ChatLogHandler
from .scanned_doc_handler import ScannedDocHandler
from .invoice_handler import InvoiceHandler
from .manual_handler import ManualHandler

__all__ = [
    'DocumentTypeHandler',
    'EmailHandler',
    'ChatLogHandler',
    'ScannedDocHandler',
    'InvoiceHandler',
    'ManualHandler',
]
