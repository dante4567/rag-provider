"""
Document Type Handlers

Type-specific preprocessing, metadata extraction, and chunking strategies.
Each document type (email, chat log, etc.) gets its own handler.
"""
from .base_handler import DocumentTypeHandler
from .email_handler import EmailHandler
from .chat_log_handler import ChatLogHandler

__all__ = [
    'DocumentTypeHandler',
    'EmailHandler',
    'ChatLogHandler',
]
