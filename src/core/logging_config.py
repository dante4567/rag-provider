"""
Structured Logging Configuration

Provides centralized logging setup with:
- JSON formatting for production
- Console formatting for development
- Log rotation
- Request ID tracking
- Performance timing
"""

import logging
import sys
import json
from datetime import datetime
from pathlib import Path
import os
from typing import Optional
import uuid
from contextvars import ContextVar

# Context variable for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging

    Outputs logs in JSON format for easy parsing by log aggregators
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable formatter for console output

    Color-coded log levels for better readability in development
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            colored_levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            record.levelname = colored_levelname

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')

        # Build message
        message = f"{timestamp} | {record.levelname:20s} | {record.name:25s} | {record.getMessage()}"

        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            message += f" [req_id: {request_id[:8]}]"

        # Add exception if present
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return message


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    use_json: bool = False
) -> None:
    """
    Setup structured logging for the application

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        use_json: Whether to use JSON formatting (for production)
    """

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if use_json:
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(ConsoleFormatter())

    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use rotating file handler to prevent huge log files
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(StructuredFormatter())  # Always JSON for files

        root_logger.addHandler(file_handler)

    # Set specific loggers to WARNING to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.INFO)

    root_logger.info(f"Logging initialized at {level} level")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    Set request ID for current context

    Args:
        request_id: Request ID (generates one if not provided)

    Returns:
        The request ID that was set
    """
    if request_id is None:
        request_id = str(uuid.uuid4())

    request_id_var.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """Get current request ID from context"""
    return request_id_var.get()


def log_with_extra(logger: logging.Logger, level: str, message: str, **extra):
    """
    Log message with extra structured data

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **extra: Additional structured data
    """
    log_func = getattr(logger, level.lower())

    # Create a log record with extra data
    class ExtraAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            kwargs['extra'] = {'extra_data': self.extra}
            return msg, kwargs

    adapter = ExtraAdapter(logger, extra)
    log_func(message)


# Convenience functions for common logging patterns

def log_api_call(logger: logging.Logger, method: str, path: str, status_code: int, duration_ms: float):
    """Log an API call with timing"""
    log_with_extra(
        logger, 'info',
        f"{method} {path} -> {status_code} ({duration_ms:.2f}ms)",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms
    )


def log_llm_call(logger: logging.Logger, provider: str, model: str, tokens: int, cost: float, duration_ms: float):
    """Log an LLM API call with metrics"""
    log_with_extra(
        logger, 'info',
        f"LLM call: {provider}/{model} - {tokens} tokens, ${cost:.6f} ({duration_ms:.2f}ms)",
        provider=provider,
        model=model,
        tokens=tokens,
        cost=cost,
        duration_ms=duration_ms
    )


def log_document_processed(logger: logging.Logger, doc_id: str, file_type: str, chunks: int, duration_ms: float):
    """Log document processing with metrics"""
    log_with_extra(
        logger, 'info',
        f"Processed document {doc_id}: {file_type}, {chunks} chunks ({duration_ms:.2f}ms)",
        document_id=doc_id,
        file_type=file_type,
        chunk_count=chunks,
        duration_ms=duration_ms
    )


def log_error_with_context(logger: logging.Logger, error: Exception, context: dict):
    """Log an error with additional context"""
    log_with_extra(
        logger, 'error',
        f"Error: {str(error)}",
        error_type=type(error).__name__,
        **context
    )


# Initialize logging based on environment
def init_app_logging():
    """Initialize logging for the application based on environment variables"""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", "logs/app.log")
    use_json = os.getenv("LOG_FORMAT", "console").lower() == "json"

    # Don't write to file in development unless explicitly enabled
    if os.getenv("ENVIRONMENT", "development") == "development":
        log_file = None if not os.getenv("LOG_FILE") else log_file

    setup_logging(
        level=log_level,
        log_file=log_file,
        use_json=use_json
    )
