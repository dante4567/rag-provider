# Optimized Multi-platform Dockerfile for Enhanced RAG Service
FROM --platform=$BUILDPLATFORM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DOCKER_CONTAINER=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
ENV QT_QPA_PLATFORM=offscreen
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies for all platforms (combined in one layer)
RUN apt-get update && apt-get install -y \
    gcc g++ curl wget \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-spa \
    poppler-utils libmagic1 \
    libjpeg-dev libpng-dev libtiff-dev \
    libxml2-dev libxslt-dev \
    libssl-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Upgrade pip/setuptools first (separate layer for caching)
RUN pip install --no-cache-dir --upgrade pip==24.2 setuptools==75.6.0 wheel==0.45.1

# Copy requirements
COPY requirements.txt .

# Install lightweight dependencies first (fast layer)
RUN pip install --no-cache-dir \
    fastapi==0.118.0 \
    uvicorn[standard]==0.37.0 \
    pydantic==2.11.10 \
    pydantic-settings==2.11.0 \
    python-multipart==0.0.20 \
    aiofiles==24.1.0 \
    httpx==0.28.1 \
    pyyaml==6.0.3 \
    requests==2.32.5 \
    click==8.3.0 \
    tqdm==4.67.1 \
    watchdog==6.0.0 \
    psutil==7.1.0 \
    pytest==8.4.2 \
    pytest-asyncio==1.2.0

# Install document processing (medium layer)
RUN pip install --no-cache-dir \
    PyPDF2==3.0.1 \
    python-magic==0.4.27 \
    python-docx==1.2.0 \
    openpyxl==3.1.5 \
    python-pptx==1.0.2 \
    xlrd==2.0.2 \
    pytesseract==0.3.13 \
    Pillow==11.3.0 \
    pdf2image==1.17.0 \
    python-dateutil==2.9.0.post0 \
    beautifulsoup4==4.13.5 \
    lxml==6.0.2 \
    extract-msg==0.55.0 \
    email-reply-parser==0.5.12 \
    python-Levenshtein==0.27.1 \
    rank-bm25==0.2.2 \
    rich==14.1.0 \
    python-slugify==8.0.4

# Install LLM providers (lightweight)
RUN pip install --no-cache-dir \
    anthropic==0.69.0 \
    openai==2.1.0 \
    groq==0.32.0 \
    google-generativeai==0.8.5

# Install heavy dependencies last (separate layers for easier debugging)
RUN pip install --no-cache-dir chromadb==1.1.1

RUN pip install --no-cache-dir litellm==1.77.7

# Install unstructured (VERY heavy - includes detectron2, torch, etc.)
RUN pip install --no-cache-dir unstructured[pdf]==0.18.15 pdfminer.six==20250506

# Install sentence-transformers (heavy - includes torch)
RUN pip install --no-cache-dir sentence-transformers==5.1.1

# Copy application code
COPY . .

# Create data directories with proper structure
RUN mkdir -p \
    /data/input \
    /data/output \
    /data/processed \
    /data/processed_originals \
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
