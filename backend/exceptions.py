"""
Custom exception hierarchy for YouTube Audit Engine.

This module defines domain-specific exceptions for better error handling,
debugging, and user-friendly error messages across the application.
"""

from typing import Optional, Dict, Any


class YouTubeAuditError(Exception):
    """
    Base exception for all YouTube Audit Engine errors.

    All custom exceptions inherit from this base class to enable
    catch-all exception handling when needed.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        """
        Initialize the exception.

        Args:
            message: Technical error message for logging
            error_code: Machine-readable error code (e.g., "INGESTION_001")
            details: Additional context information for debugging
            user_message: User-friendly error message for display
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.user_message = user_message or message

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "user_message": self.user_message
        }


# ============================================================================
# Configuration Errors
# ============================================================================

class ConfigurationError(YouTubeAuditError):
    """Raised when there are configuration-related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", "CONFIG_001"),
            user_message=kwargs.get("user_message", "Application configuration error. Please contact support."),
            **{k: v for k, v in kwargs.items() if k not in ["error_code", "user_message"]}
        )


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""

    def __init__(self, config_key: str, **kwargs):
        super().__init__(
            message=f"Missing required configuration: {config_key}",
            error_code="CONFIG_002",
            user_message=f"Application is not properly configured. Missing: {config_key}",
            details={"config_key": config_key},
            **kwargs
        )


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""

    def __init__(self, config_key: str, reason: str, **kwargs):
        super().__init__(
            message=f"Invalid configuration for {config_key}: {reason}",
            error_code="CONFIG_003",
            user_message=f"Invalid configuration: {reason}",
            details={"config_key": config_key, "reason": reason},
            **kwargs
        )


# ============================================================================
# Validation Errors
# ============================================================================

class ValidationError(YouTubeAuditError):
    """Raised when input validation fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", "VALIDATION_001"),
            user_message=kwargs.get("user_message", message),
            **{k: v for k, v in kwargs.items() if k not in ["error_code", "user_message"]}
        )


class FileValidationError(ValidationError):
    """Raised when file validation fails."""

    def __init__(self, reason: str, filename: Optional[str] = None, **kwargs):
        super().__init__(
            message=f"File validation failed: {reason}" + (f" (file: {filename})" if filename else ""),
            error_code="VALIDATION_002",
            user_message=f"Invalid file: {reason}",
            details={"filename": filename, "reason": reason},
            **kwargs
        )


class FileSizeError(FileValidationError):
    """Raised when file size exceeds limits."""

    def __init__(self, size: int, max_size: int, filename: Optional[str] = None, **kwargs):
        size_mb = size / (1024 * 1024)
        max_mb = max_size / (1024 * 1024)
        super().__init__(
            reason=f"File size {size_mb:.2f}MB exceeds maximum {max_mb:.2f}MB",
            filename=filename,
            error_code="VALIDATION_003",
            details={"size_bytes": size, "max_size_bytes": max_size, "size_mb": size_mb, "max_mb": max_mb},
            **kwargs
        )


class FileTypeError(FileValidationError):
    """Raised when file type is not supported."""

    def __init__(self, file_type: str, allowed_types: list, filename: Optional[str] = None, **kwargs):
        super().__init__(
            reason=f"File type '{file_type}' not supported. Allowed: {', '.join(allowed_types)}",
            filename=filename,
            error_code="VALIDATION_004",
            details={"file_type": file_type, "allowed_types": allowed_types},
            **kwargs
        )


class APIKeyValidationError(ValidationError):
    """Raised when API key validation fails."""

    def __init__(self, reason: str, **kwargs):
        super().__init__(
            message=f"API key validation failed: {reason}",
            error_code="VALIDATION_005",
            user_message="Invalid API key. Please check your Google API key.",
            details={"reason": reason},
            **kwargs
        )


# ============================================================================
# Ingestion Errors
# ============================================================================

class IngestionError(YouTubeAuditError):
    """Raised when data ingestion fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", "INGESTION_001"),
            user_message=kwargs.get("user_message", "Failed to process your YouTube data. Please check the file format."),
            **{k: v for k, v in kwargs.items() if k not in ["error_code", "user_message"]}
        )


class TakeoutParseError(IngestionError):
    """Raised when parsing YouTube Takeout file fails."""

    def __init__(self, reason: str, filename: Optional[str] = None, **kwargs):
        super().__init__(
            message=f"Failed to parse Takeout file: {reason}" + (f" ({filename})" if filename else ""),
            error_code="INGESTION_002",
            user_message=f"Could not read YouTube Takeout file: {reason}",
            details={"reason": reason, "filename": filename},
            **kwargs
        )


class MissingWatchHistoryError(IngestionError):
    """Raised when watch-history.json is not found in Takeout."""

    def __init__(self, **kwargs):
        super().__init__(
            message="watch-history.json not found in Takeout archive",
            error_code="INGESTION_003",
            user_message="Your Takeout file doesn't contain watch history. Please export 'YouTube and YouTube Music' data.",
            **kwargs
        )


class InvalidJSONError(IngestionError):
    """Raised when JSON parsing fails."""

    def __init__(self, filename: str, parse_error: str, **kwargs):
        super().__init__(
            message=f"Invalid JSON in {filename}: {parse_error}",
            error_code="INGESTION_004",
            user_message=f"The file contains invalid data: {parse_error}",
            details={"filename": filename, "parse_error": parse_error},
            **kwargs
        )


class EmptyDatasetError(IngestionError):
    """Raised when no valid data is found after ingestion."""

    def __init__(self, **kwargs):
        super().__init__(
            message="No valid video data found in the provided file",
            error_code="INGESTION_005",
            user_message="No watch history found in your file. Please ensure you've exported the correct data.",
            **kwargs
        )


# ============================================================================
# Enrichment Errors
# ============================================================================

class EnrichmentError(YouTubeAuditError):
    """Raised when video metadata enrichment fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", "ENRICHMENT_001"),
            user_message=kwargs.get("user_message", "Failed to fetch video metadata from YouTube."),
            **{k: v for k, v in kwargs.items() if k not in ["error_code", "user_message"]}
        )


class YouTubeAPIError(EnrichmentError):
    """Raised when YouTube API calls fail."""

    def __init__(self, reason: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(
            message=f"YouTube API error: {reason}" + (f" (status {status_code})" if status_code else ""),
            error_code="ENRICHMENT_002",
            user_message=f"YouTube API error: {reason}",
            details={"reason": reason, "status_code": status_code},
            **kwargs
        )


class QuotaExceededError(EnrichmentError):
    """Raised when YouTube API quota is exceeded."""

    def __init__(self, **kwargs):
        super().__init__(
            message="YouTube API quota exceeded",
            error_code="ENRICHMENT_003",
            user_message="YouTube API quota limit reached. Please try again tomorrow or use a different API key.",
            **kwargs
        )


class RateLimitError(EnrichmentError):
    """Raised when rate limit is hit."""

    def __init__(self, retry_after: Optional[int] = None, **kwargs):
        super().__init__(
            message=f"Rate limit exceeded" + (f", retry after {retry_after}s" if retry_after else ""),
            error_code="ENRICHMENT_004",
            user_message="Too many requests. Please wait a moment and try again.",
            details={"retry_after": retry_after},
            **kwargs
        )


# ============================================================================
# Embedding Errors
# ============================================================================

class EmbeddingError(YouTubeAuditError):
    """Raised when embedding generation fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", "EMBEDDING_001"),
            user_message=kwargs.get("user_message", "Failed to generate video embeddings."),
            **{k: v for k, v in kwargs.items() if k not in ["error_code", "user_message"]}
        )


class ModelLoadError(EmbeddingError):
    """Raised when embedding model fails to load."""

    def __init__(self, model_name: str, reason: str, **kwargs):
        super().__init__(
            message=f"Failed to load model {model_name}: {reason}",
            error_code="EMBEDDING_002",
            user_message="System error: Could not load AI model.",
            details={"model_name": model_name, "reason": reason},
            **kwargs
        )


class VectorStoreError(EmbeddingError):
    """Raised when vector store operations fail."""

    def __init__(self, operation: str, reason: str, **kwargs):
        super().__init__(
            message=f"Vector store {operation} failed: {reason}",
            error_code="EMBEDDING_003",
            user_message=f"Failed to {operation} embeddings.",
            details={"operation": operation, "reason": reason},
            **kwargs
        )


class DimensionMismatchError(EmbeddingError):
    """Raised when embedding dimensions don't match."""

    def __init__(self, expected: int, actual: int, **kwargs):
        super().__init__(
            message=f"Embedding dimension mismatch: expected {expected}, got {actual}",
            error_code="EMBEDDING_004",
            user_message="System error: Embedding dimension mismatch.",
            details={"expected_dimension": expected, "actual_dimension": actual},
            **kwargs
        )


# ============================================================================
# Clustering Errors
# ============================================================================

class ClusteringError(YouTubeAuditError):
    """Raised when clustering fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", "CLUSTERING_001"),
            user_message=kwargs.get("user_message", "Failed to cluster videos into topics."),
            **{k: v for k, v in kwargs.items() if k not in ["error_code", "user_message"]}
        )


class InsufficientDataError(ClusteringError):
    """Raised when there's not enough data for clustering."""

    def __init__(self, data_points: int, minimum_required: int, **kwargs):
        super().__init__(
            message=f"Insufficient data for clustering: {data_points} videos (minimum {minimum_required} required)",
            error_code="CLUSTERING_002",
            user_message=f"Not enough videos to analyze. Found {data_points}, need at least {minimum_required}.",
            details={"data_points": data_points, "minimum_required": minimum_required},
            **kwargs
        )


class ClusteringAlgorithmError(ClusteringError):
    """Raised when clustering algorithm fails."""

    def __init__(self, algorithm: str, reason: str, **kwargs):
        super().__init__(
            message=f"{algorithm} clustering failed: {reason}",
            error_code="CLUSTERING_003",
            user_message="Clustering algorithm failed. Please try again.",
            details={"algorithm": algorithm, "reason": reason},
            **kwargs
        )


# ============================================================================
# External Service Errors
# ============================================================================

class ExternalServiceError(YouTubeAuditError):
    """Raised when external service calls fail."""

    def __init__(self, service: str, reason: str, **kwargs):
        super().__init__(
            message=f"{service} service error: {reason}",
            error_code=kwargs.get("error_code", "EXTERNAL_001"),
            user_message=kwargs.get("user_message", f"External service error: {reason}"),
            details={"service": service, "reason": reason},
            **{k: v for k, v in kwargs.items() if k not in ["error_code", "user_message"]}
        )


class TimeoutError(ExternalServiceError):
    """Raised when external service call times out."""

    def __init__(self, service: str, timeout_seconds: int, **kwargs):
        super().__init__(
            service=service,
            reason=f"Request timed out after {timeout_seconds}s",
            error_code="EXTERNAL_002",
            user_message=f"Request to {service} timed out. Please try again.",
            details={"timeout_seconds": timeout_seconds},
            **kwargs
        )


class NetworkError(ExternalServiceError):
    """Raised when network connectivity issues occur."""

    def __init__(self, service: str, reason: str, **kwargs):
        super().__init__(
            service=service,
            reason=reason,
            error_code="EXTERNAL_003",
            user_message="Network error. Please check your internet connection.",
            **kwargs
        )


# ============================================================================
# Authentication and Authorization Errors
# ============================================================================

class AuthenticationError(YouTubeAuditError):
    """Raised when authentication fails."""

    def __init__(self, reason: str, **kwargs):
        super().__init__(
            message=f"Authentication failed: {reason}",
            error_code="AUTH_001",
            user_message="Authentication failed. Please check your credentials.",
            details={"reason": reason},
            **kwargs
        )


class InvalidTokenError(AuthenticationError):
    """Raised when bearer token is invalid."""

    def __init__(self, **kwargs):
        super().__init__(
            reason="Invalid or missing bearer token",
            error_code="AUTH_002",
            user_message="Invalid authentication token.",
            **kwargs
        )
