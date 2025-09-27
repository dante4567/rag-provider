# Multi-platform Dockerfile for Enhanced RAG Service
FROM --platform=$BUILDPLATFORM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DOCKER_CONTAINER=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies for all platforms
RUN apt-get update && apt-get install -y \
    # Build tools
    gcc \
    g++ \
    curl \
    wget \
    # For OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-deu \
    tesseract-ocr-fra \
    tesseract-ocr-spa \
    # For PDF processing
    poppler-utils \
    # For image processing
    libmagic1 \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    # For Office documents
    libxml2-dev \
    libxslt-dev \
    # For email processing
    libssl-dev \
    libffi-dev \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories with proper structure
RUN mkdir -p \
    /data/input \
    /data/output \
    /data/processed \
    /data/obsidian \
    /tmp/rag_processing

# Create non-root user and set permissions
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app /data /tmp/rag_processing
USER appuser

# Expose port
EXPOSE 8001

# Health check with Python instead of curl for better compatibility
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/health', timeout=5)" || exit 1

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]