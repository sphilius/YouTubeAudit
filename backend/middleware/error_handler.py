"""
Global error handling middleware for consistent error responses.

This module provides centralized error handling to convert exceptions
into consistent JSON responses with appropriate HTTP status codes.
"""

from flask import jsonify, request
from werkzeug.exceptions import HTTPException
from backend.utils.logging_config import get_logger
from backend.exceptions import (
    YouTubeAuditError,
    ValidationError,
    FileValidationError,
    AuthenticationError,
    ConfigurationError,
    IngestionError,
    EnrichmentError,
    EmbeddingError,
    ClusteringError,
    ExternalServiceError
)
from backend.middleware.correlation import get_correlation_id

log = get_logger(__name__)


class ErrorHandlerMiddleware:
    """
    Flask error handler middleware.

    Converts exceptions into consistent JSON error responses.
    """

    def __init__(self, app):
        """
        Initialize error handler middleware.

        Args:
            app: Flask application instance
        """
        self.app = app
        self._register_error_handlers()
        log.info("Error handler middleware initialized")

    def _register_error_handlers(self):
        """Register error handlers for different exception types."""

        @self.app.errorhandler(YouTubeAuditError)
        def handle_audit_error(error: YouTubeAuditError):
            """Handle custom application errors."""
            return self._create_error_response(
                error=error,
                status_code=self._get_status_code_for_error(error),
                include_details=True
            )

        @self.app.errorhandler(HTTPException)
        def handle_http_error(error: HTTPException):
            """Handle HTTP exceptions from Flask/Werkzeug."""
            log.warning(
                "HTTP exception",
                status_code=error.code,
                error=error.description
            )
            return jsonify({
                "error": error.name,
                "message": error.description,
                "status_code": error.code,
                "correlation_id": get_correlation_id()
            }), error.code

        @self.app.errorhandler(Exception)
        def handle_generic_error(error: Exception):
            """Handle unexpected errors."""
            log.error(
                "Unhandled exception",
                error_type=type(error).__name__,
                error=str(error),
                exc_info=True
            )
            return jsonify({
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
                "details": str(error),
                "correlation_id": get_correlation_id()
            }), 500

    def _get_status_code_for_error(self, error: YouTubeAuditError) -> int:
        """
        Determine HTTP status code based on error type.

        Args:
            error: The error to map

        Returns:
            Appropriate HTTP status code
        """
        error_type_map = {
            ValidationError: 400,
            FileValidationError: 400,
            AuthenticationError: 401,
            ConfigurationError: 500,
            IngestionError: 400,
            EnrichmentError: 503,
            EmbeddingError: 500,
            ClusteringError: 500,
            ExternalServiceError: 503,
        }

        # Check error type hierarchy
        for error_class, status_code in error_type_map.items():
            if isinstance(error, error_class):
                return status_code

        # Default to 500 for unknown custom errors
        return 500

    def _create_error_response(
        self,
        error: YouTubeAuditError,
        status_code: int,
        include_details: bool = True
    ):
        """
        Create a standardized error response.

        Args:
            error: The error to format
            status_code: HTTP status code
            include_details: Whether to include detailed error information

        Returns:
            Flask JSON response
        """
        log.error(
            "Application error",
            error_type=type(error).__name__,
            error_code=error.error_code,
            message=error.message,
            status_code=status_code
        )

        response_data = error.to_dict()
        response_data["status_code"] = status_code
        response_data["correlation_id"] = get_correlation_id()

        # Remove internal details if not needed
        if not include_details:
            response_data.pop("details", None)

        return jsonify(response_data), status_code
