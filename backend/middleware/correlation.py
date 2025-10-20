"""
Request correlation ID middleware for distributed tracing.

This module provides middleware to generate and propagate correlation IDs
across the entire request lifecycle for better debugging and monitoring.
"""

import uuid
from flask import request, g
from typing import Callable
from backend.utils.logging_config import bind_context, clear_context, get_logger

log = get_logger(__name__)


def generate_correlation_id() -> str:
    """
    Generate a unique correlation ID for a request.

    Returns:
        A UUID-based correlation ID
    """
    return str(uuid.uuid4())


class CorrelationMiddleware:
    """
    Flask middleware to add correlation IDs to requests.

    This middleware:
    1. Extracts correlation ID from headers (if provided)
    2. Generates a new ID if none exists
    3. Binds the ID to the logging context
    4. Adds the ID to response headers
    """

    CORRELATION_ID_HEADER = 'X-Correlation-ID'

    def __init__(self, app):
        """
        Initialize correlation middleware.

        Args:
            app: Flask application instance
        """
        self.app = app
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        app.teardown_request(self.teardown_request)

        log.info("Correlation middleware initialized")

    def before_request(self) -> None:
        """
        Process request before it's handled.

        Extracts or generates correlation ID and binds it to logging context.
        """
        # Check if correlation ID is in headers
        correlation_id = request.headers.get(self.CORRELATION_ID_HEADER)

        # Generate new ID if not provided
        if not correlation_id:
            correlation_id = generate_correlation_id()
            log.debug("Generated new correlation ID", correlation_id=correlation_id)
        else:
            log.debug("Using correlation ID from headers", correlation_id=correlation_id)

        # Store in Flask's g object for access throughout request
        g.correlation_id = correlation_id

        # Bind to logging context so all logs include it
        bind_context(correlation_id=correlation_id)

        # Also bind request metadata
        bind_context(
            method=request.method,
            path=request.path,
            remote_addr=request.remote_addr
        )

        log.info(
            "Request started",
            correlation_id=correlation_id,
            method=request.method,
            path=request.path,
            user_agent=request.headers.get('User-Agent', 'unknown')
        )

    def after_request(self, response):
        """
        Process response after request is handled.

        Adds correlation ID to response headers.

        Args:
            response: Flask response object

        Returns:
            Modified response with correlation ID header
        """
        correlation_id = getattr(g, 'correlation_id', None)
        if correlation_id:
            response.headers[self.CORRELATION_ID_HEADER] = correlation_id

        log.info(
            "Request completed",
            correlation_id=correlation_id,
            status_code=response.status_code
        )

        return response

    def teardown_request(self, exception=None) -> None:
        """
        Clean up after request processing.

        Args:
            exception: Exception that occurred during request (if any)
        """
        correlation_id = getattr(g, 'correlation_id', None)

        if exception:
            log.error(
                "Request failed with exception",
                correlation_id=correlation_id,
                error=str(exception),
                exc_info=True
            )

        # Clear logging context
        clear_context()


def get_correlation_id() -> str:
    """
    Get the correlation ID for the current request.

    Returns:
        The correlation ID, or 'unknown' if not in request context

    Example:
        >>> from backend.middleware.correlation import get_correlation_id
        >>> correlation_id = get_correlation_id()
    """
    return getattr(g, 'correlation_id', 'unknown')
