"""
Centralized configuration management for YouTube Audit Engine.

This module provides type-safe configuration with validation using Pydantic.
All configuration values are loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional, Literal
from pydantic import Field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """
    Main application configuration.

    All settings can be overridden via environment variables.
    Example: API_BEARER_TOKEN environment variable sets api_bearer_token.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # ========================================================================
    # Application Settings
    # ========================================================================

    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment"
    )

    debug: bool = Field(
        default=False,
        description="Enable debug mode (should be False in production)"
    )

    # ========================================================================
    # Security Settings
    # ========================================================================

    api_bearer_token: str = Field(
        default="",
        description="Bearer token for API authentication"
    )

    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Flask secret key for session management"
    )

    allowed_origins: str = Field(
        default="*",
        description="CORS allowed origins (comma-separated)"
    )

    @field_validator("api_bearer_token")
    @classmethod
    def validate_bearer_token(cls, v: str, info: ValidationInfo) -> str:
        """Ensure bearer token is set in non-development environments."""
        environment = info.data.get("environment", "development")
        if environment != "development" and not v:
            raise ValueError("api_bearer_token must be set in production/staging")
        if v and len(v) < 16:
            raise ValueError("api_bearer_token must be at least 16 characters")
        return v

    # ========================================================================
    # File Upload Settings
    # ========================================================================

    upload_folder: Path = Field(
        default=Path("uploads"),
        description="Directory for temporary file uploads"
    )

    max_upload_size_mb: int = Field(
        default=100,
        description="Maximum upload file size in megabytes",
        ge=1,
        le=1000
    )

    allowed_extensions: set = Field(
        default={"zip", "json"},
        description="Allowed file extensions for upload"
    )

    cleanup_temp_files: bool = Field(
        default=True,
        description="Automatically delete temporary files after processing"
    )

    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @field_validator("upload_folder")
    @classmethod
    def ensure_upload_folder_exists(cls, v: Path) -> Path:
        """Create upload folder if it doesn't exist."""
        v = v.resolve()
        v.mkdir(parents=True, exist_ok=True)
        return v

    # ========================================================================
    # YouTube API Settings
    # ========================================================================

    google_api_key: Optional[str] = Field(
        default=None,
        description="Google API key for YouTube Data API (can be provided by user)"
    )

    youtube_api_timeout: int = Field(
        default=30,
        description="Timeout for YouTube API requests in seconds",
        ge=5,
        le=300
    )

    youtube_api_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for YouTube API calls",
        ge=0,
        le=10
    )

    youtube_api_batch_size: int = Field(
        default=50,
        description="Number of videos to fetch per API request",
        ge=1,
        le=50
    )

    youtube_api_quota_limit: int = Field(
        default=10000,
        description="Daily YouTube API quota limit (units)",
        ge=0
    )

    # ========================================================================
    # Embedding Settings
    # ========================================================================

    embedding_model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model for embeddings"
    )

    embedding_dimension: int = Field(
        default=384,
        description="Expected embedding vector dimension",
        ge=64,
        le=2048
    )

    embedding_batch_size: int = Field(
        default=32,
        description="Batch size for embedding generation",
        ge=1,
        le=256
    )

    faiss_index_type: str = Field(
        default="Flat",
        description="FAISS index type (Flat, IVF, HNSW)"
    )

    # ========================================================================
    # Clustering Settings
    # ========================================================================

    min_clusters: int = Field(
        default=3,
        description="Minimum number of clusters",
        ge=2,
        le=100
    )

    max_clusters: int = Field(
        default=15,
        description="Maximum number of clusters",
        ge=2,
        le=100
    )

    min_videos_for_clustering: int = Field(
        default=10,
        description="Minimum videos required for clustering",
        ge=5
    )

    clustering_algorithm: str = Field(
        default="kmeans",
        description="Clustering algorithm to use"
    )

    clustering_random_state: int = Field(
        default=42,
        description="Random state for reproducible clustering"
    )

    @field_validator("max_clusters")
    @classmethod
    def validate_cluster_range(cls, v: int, info: ValidationInfo) -> int:
        """Ensure max_clusters >= min_clusters."""
        min_clusters = info.data.get("min_clusters", 3)
        if v < min_clusters:
            raise ValueError(f"max_clusters ({v}) must be >= min_clusters ({min_clusters})")
        return v

    # ========================================================================
    # Logging Settings
    # ========================================================================

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log output format"
    )

    log_file: Optional[Path] = Field(
        default=None,
        description="Log file path (None for stdout only)"
    )

    log_rotation_size_mb: int = Field(
        default=10,
        description="Log file rotation size in megabytes",
        ge=1,
        le=1000
    )

    log_retention_days: int = Field(
        default=7,
        description="Number of days to retain old log files",
        ge=1,
        le=365
    )

    enable_request_logging: bool = Field(
        default=True,
        description="Log all HTTP requests"
    )

    sanitize_logs: bool = Field(
        default=True,
        description="Remove sensitive data from logs (API keys, tokens)"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v

    # ========================================================================
    # Server Settings
    # ========================================================================

    host: str = Field(
        default="0.0.0.0",
        description="Server host address"
    )

    port: int = Field(
        default=8000,
        description="Server port",
        ge=1,
        le=65535
    )

    workers: int = Field(
        default=4,
        description="Number of Gunicorn worker processes",
        ge=1,
        le=32
    )

    worker_class: str = Field(
        default="sync",
        description="Gunicorn worker class (sync, gevent, eventlet)"
    )

    timeout: int = Field(
        default=300,
        description="Worker timeout in seconds",
        ge=30,
        le=1800
    )

    keepalive: int = Field(
        default=5,
        description="Keep-alive timeout in seconds",
        ge=0,
        le=300
    )

    # ========================================================================
    # Performance Settings
    # ========================================================================

    enable_caching: bool = Field(
        default=True,
        description="Enable response caching"
    )

    cache_ttl_seconds: int = Field(
        default=3600,
        description="Cache time-to-live in seconds",
        ge=0
    )

    max_concurrent_requests: int = Field(
        default=10,
        description="Maximum concurrent API requests",
        ge=1,
        le=100
    )

    request_timeout: int = Field(
        default=900,
        description="Maximum request processing time in seconds (15 minutes)",
        ge=30,
        le=3600
    )

    # ========================================================================
    # Feature Flags
    # ========================================================================

    enable_rate_limiting: bool = Field(
        default=True,
        description="Enable API rate limiting"
    )

    rate_limit_per_minute: int = Field(
        default=60,
        description="Maximum requests per minute per IP",
        ge=1,
        le=1000
    )

    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection"
    )

    enable_health_checks: bool = Field(
        default=True,
        description="Enable health check endpoints"
    )

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def get_allowed_origins_list(self) -> list:
        """Parse allowed origins into a list."""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]


# ============================================================================
# Global Configuration Instance
# ============================================================================

# Singleton instance of configuration
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """
    Get the global configuration instance.

    Returns:
        AppConfig: The singleton configuration object

    Example:
        >>> from backend.config import get_config
        >>> config = get_config()
        >>> print(config.max_upload_size_mb)
    """
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reload_config() -> AppConfig:
    """
    Reload configuration from environment variables.

    Useful for testing or when environment variables change.

    Returns:
        AppConfig: The reloaded configuration object
    """
    global _config
    _config = AppConfig()
    return _config


# ============================================================================
# Configuration Validation
# ============================================================================

def validate_config() -> tuple[bool, list[str]]:
    """
    Validate the current configuration.

    Returns:
        Tuple of (is_valid, list_of_errors)

    Example:
        >>> is_valid, errors = validate_config()
        >>> if not is_valid:
        ...     print("Configuration errors:", errors)
    """
    errors = []

    try:
        config = get_config()

        # Validate production requirements
        if config.is_production():
            if config.debug:
                errors.append("debug must be False in production")

            if config.secret_key == "dev-secret-key-change-in-production":
                errors.append("secret_key must be changed in production")

            if not config.api_bearer_token:
                errors.append("api_bearer_token must be set in production")

        # Validate upload folder is writable
        if not os.access(config.upload_folder, os.W_OK):
            errors.append(f"upload_folder {config.upload_folder} is not writable")

        # Validate log file directory
        if config.log_file:
            log_dir = config.log_file.parent
            if not log_dir.exists():
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"Cannot create log directory {log_dir}: {e}")

    except Exception as e:
        errors.append(f"Configuration validation failed: {e}")

    return (len(errors) == 0, errors)


def print_config(show_secrets: bool = False) -> None:
    """
    Print current configuration (for debugging).

    Args:
        show_secrets: Whether to show sensitive values (default: False)
    """
    config = get_config()
    print("=" * 80)
    print("YouTube Audit Engine Configuration")
    print("=" * 80)

    for field_name, field_info in config.model_fields.items():
        value = getattr(config, field_name)

        # Hide sensitive values
        if not show_secrets and field_name in ["api_bearer_token", "secret_key", "google_api_key"]:
            if value:
                value = "***HIDDEN***"

        print(f"{field_name:30} = {value}")

    print("=" * 80)

    # Validate and show any errors
    is_valid, errors = validate_config()
    if not is_valid:
        print("\nCONFIGURATION WARNINGS:")
        for error in errors:
            print(f"  ⚠️  {error}")
        print("=" * 80)
