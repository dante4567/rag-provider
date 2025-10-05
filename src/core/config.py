"""
Centralized configuration management with validation
"""
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
import os
import platform


class Settings(BaseSettings):
    """
    Application settings with environment variable support and validation

    All settings can be overridden via environment variables or .env file
    """

    # ===== Application =====
    app_name: str = "RAG Provider"
    version: str = "2.1.0"
    debug: bool = False
    environment: str = Field(default="production", description="Environment: development, staging, production")

    # ===== Security =====
    rag_api_key: Optional[str] = Field(default=None, description="API key for authentication")
    require_auth: bool = Field(default=False, description="Require authentication for API access")
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="Comma-separated CORS origins"
    )

    # ===== ChromaDB =====
    chroma_host: str = Field(default="localhost", description="ChromaDB host")
    chroma_port: int = Field(default=8000, description="ChromaDB port")
    collection_name: str = Field(default="documents", description="ChromaDB collection name")

    # ===== Document Processing =====
    chunk_size: int = Field(default=1000, ge=100, le=10000, description="Text chunk size in characters")
    chunk_overlap: int = Field(default=200, ge=0, le=1000, description="Chunk overlap in characters")
    max_file_size_mb: int = Field(default=50, ge=1, le=500, description="Maximum file size in MB")
    supported_formats: str = Field(
        default="pdf,txt,docx,xlsx,pptx,eml,msg,md",
        description="Comma-separated supported file formats"
    )

    # ===== LLM Configuration =====
    default_llm: str = Field(default="groq", description="Default LLM provider")
    fallback_llm: str = Field(default="anthropic", description="Fallback LLM provider")
    emergency_llm: str = Field(default="openai", description="Emergency LLM provider")
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature")
    llm_max_retries: int = Field(default=3, ge=1, le=10, description="Maximum LLM retry attempts")
    llm_timeout_seconds: int = Field(default=30, ge=5, le=300, description="LLM request timeout")

    # ===== API Keys =====
    groq_api_key: Optional[str] = Field(default=None, description="Groq API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    google_api_key: Optional[str] = Field(default=None, description="Google Generative AI API key")
    cohere_api_key: Optional[str] = Field(default=None, description="Cohere API key")
    mistral_api_key: Optional[str] = Field(default=None, description="Mistral API key")

    # ===== OCR Configuration =====
    use_ocr: bool = Field(default=True, description="Enable OCR for images and scanned PDFs")
    ocr_provider: str = Field(default="tesseract", description="OCR provider: tesseract, google, azure, aws")
    ocr_languages: str = Field(default="eng,deu,fra,spa", description="Comma-separated OCR language codes")

    # Cloud OCR (optional)
    google_vision_api_key: Optional[str] = None
    azure_cv_endpoint: Optional[str] = None
    azure_cv_api_key: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"

    # ===== File Paths =====
    input_path: str = Field(default="/data/input", description="Input directory for documents")
    output_path: str = Field(default="/data/output", description="Output directory for processed files")
    processed_path: str = Field(default="/data/processed", description="Archive directory for processed files")
    obsidian_path: str = Field(default="/data/obsidian", description="Obsidian vault output path")
    temp_path: str = Field(default="/tmp/rag_processing", description="Temporary processing directory")

    # ===== Feature Flags =====
    enable_file_watch: bool = Field(default=True, description="Enable automatic file watching")
    create_obsidian_links: bool = Field(default=True, description="Generate Obsidian wikilinks")
    enable_cost_tracking: bool = Field(default=True, description="Track LLM API costs")
    enable_enhanced_search: bool = Field(default=True, description="Enable enhanced search with reranking")
    enable_hybrid_retrieval: bool = Field(default=True, description="Enable hybrid retrieval (vector + keyword)")
    enable_quality_triage: bool = Field(default=True, description="Enable document quality assessment")

    # ===== Obsidian Features =====
    hierarchy_depth: int = Field(default=3, ge=1, le=10, description="Wikilink hierarchy depth")
    obsidian_vault_name: str = Field(default="RAG Knowledge Base", description="Obsidian vault name")

    # ===== Performance =====
    worker_threads: int = Field(default=4, ge=1, le=32, description="Thread pool worker count")
    batch_size: int = Field(default=10, ge=1, le=100, description="Batch processing size")

    # ===== Cost Tracking =====
    daily_budget_usd: float = Field(default=10.0, ge=0.0, description="Daily LLM budget in USD")
    cost_alert_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Alert when % of budget reached")

    # ===== Platform Detection =====
    docker_container: bool = Field(default=False, description="Running in Docker container")
    platform_system: str = Field(default_factory=lambda: platform.system().lower())

    @field_validator("allowed_origins")
    @classmethod
    def parse_origins(cls, v):
        """Parse comma-separated origins into list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("supported_formats")
    @classmethod
    def parse_formats(cls, v):
        """Parse comma-separated formats into list"""
        if isinstance(v, str):
            return [fmt.strip().lower() for fmt in v.split(",")]
        return v

    @field_validator("ocr_languages")
    @classmethod
    def parse_languages(cls, v):
        """Parse comma-separated language codes"""
        if isinstance(v, str):
            return [lang.strip() for lang in v.split(",")]
        return v

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v, info):
        """Ensure overlap is less than chunk size"""
        if "chunk_size" in info.data and v >= info.data["chunk_size"]:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v

    def get_llm_api_key(self, provider: str) -> Optional[str]:
        """Get API key for specific LLM provider"""
        key_mapping = {
            "groq": self.groq_api_key,
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "google": self.google_api_key,
            "cohere": self.cohere_api_key,
            "mistral": self.mistral_api_key,
        }
        return key_mapping.get(provider.lower())

    def has_any_llm_key(self) -> bool:
        """Check if any LLM API key is configured"""
        return any([
            self.groq_api_key,
            self.anthropic_api_key,
            self.openai_api_key,
            self.google_api_key,
        ])

    def get_available_llm_providers(self) -> List[str]:
        """Get list of LLM providers with configured API keys"""
        providers = []
        if self.groq_api_key:
            providers.append("groq")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.openai_api_key:
            providers.append("openai")
        if self.google_api_key:
            providers.append("google")
        if self.cohere_api_key:
            providers.append("cohere")
        if self.mistral_api_key:
            providers.append("mistral")
        return providers

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Allow extra fields for forward compatibility
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance

    Uses LRU cache to avoid re-reading environment variables on every request
    """
    return Settings()


def reload_settings():
    """Force reload settings (clears cache)"""
    get_settings.cache_clear()
    return get_settings()
