"""
Centralized logging configuration for YouTube Audit Engine.

This module provides structured logging with sanitization, context binding,
and flexible output formats.
"""

import logging
import sys
import re
from pathlib import Path
from typing import Any, Dict, Optional
import structlog
from structlog.types import EventDict, Processor


# ============================================================================
# Log Sanitization
# ============================================================================

# Patterns for sensitive data
SENSITIVE_PATTERNS = [
    (r'(api[_-]?key["\s:=]+)([A-Za-z0-9_\-]{20,})', r'\1***REDACTED***'),
    (r'(bearer["\s:=]+)([A-Za-z0-9_\-\.]{16,})', r'\1***REDACTED***'),
    (r'(token["\s:=]+)([A-Za-z0-9_\-\.]{16,})', r'\1***REDACTED***'),
    (r'(password["\s:=]+)([^\s"]+)', r'\1***REDACTED***'),
    (r'(secret["\s:=]+)([^\s"]+)', r'\1***REDACTED***'),
]


def sanitize_value(value: Any) -> Any:
    """
    Sanitize sensitive data from a value.

    Args:
        value: The value to sanitize (string, dict, list, etc.)

    Returns:
        Sanitized value with sensitive data redacted
    """
    if isinstance(value, str):
        for pattern, replacement in SENSITIVE_PATTERNS:
            value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
        return value

    elif isinstance(value, dict):
        return {k: sanitize_value(v) for k, v in value.items()}

    elif isinstance(value, (list, tuple)):
        return type(value)(sanitize_value(item) for item in value)

    return value


def sanitize_event_dict(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Structlog processor to sanitize sensitive data from log events.

    Args:
        logger: Logger instance
        method_name: The name of the method being called
        event_dict: The event dictionary to process

    Returns:
        Sanitized event dictionary
    """
    # Sanitize the main event message
    if "event" in event_dict:
        event_dict["event"] = sanitize_value(event_dict["event"])

    # Sanitize all other fields
    for key, value in list(event_dict.items()):
        if key != "event":
            event_dict[key] = sanitize_value(value)

    return event_dict


# ============================================================================
# Custom Processors
# ============================================================================

def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add application context to log events.

    Args:
        logger: Logger instance
        method_name: The name of the method being called
        event_dict: The event dictionary to process

    Returns:
        Event dictionary with app context added
    """
    event_dict["app"] = "youtube-audit"
    event_dict["component"] = logger.name if hasattr(logger, "name") else "unknown"
    return event_dict


def add_caller_info(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add caller information to log events for debugging.

    Args:
        logger: Logger instance
        method_name: The name of the method being called
        event_dict: The event dictionary to process

    Returns:
        Event dictionary with caller info added
    """
    # This is handled by structlog.processors.CallsiteParameterAdder in detailed mode
    return event_dict


# ============================================================================
# Logging Configuration
# ============================================================================

def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[Path] = None,
    enable_sanitization: bool = True,
    development_mode: bool = False
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "text")
        log_file: Optional path to log file (logs to stdout if None)
        enable_sanitization: Whether to sanitize sensitive data
        development_mode: Enable development-friendly logging (colored, human-readable)
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    # Build processor chain
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_app_context,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    # Add caller info in development mode
    if development_mode:
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            )
        )

    # Add sanitization if enabled
    if enable_sanitization:
        processors.append(sanitize_event_dict)

    # Add stack info for exceptions
    processors.append(structlog.processors.StackInfoRenderer())
    processors.append(structlog.processors.format_exc_info)

    # Choose renderer based on format
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        if development_mode:
            # Colored console output for development
            processors.append(
                structlog.dev.ConsoleRenderer(
                    colors=True,
                    exception_formatter=structlog.dev.plain_traceback,
                )
            )
        else:
            # Plain text for production
            processors.append(structlog.processors.KeyValueRenderer(key_order=["event", "level"]))

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure file handler if log_file is specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(logging.Formatter("%(message)s"))

        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__ from the calling module)

    Returns:
        Configured structlog BoundLogger instance

    Example:
        >>> from backend.utils.logging_config import get_logger
        >>> log = get_logger(__name__)
        >>> log.info("Processing started", video_count=42)
    """
    return structlog.get_logger(name)


# ============================================================================
# Context Management
# ============================================================================

def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables that will be included in all subsequent log events.

    This is useful for adding request IDs, user IDs, or other contextual information.

    Args:
        **kwargs: Key-value pairs to bind to the context

    Example:
        >>> bind_context(request_id="abc-123", user_id="user_456")
        >>> log.info("User action")  # Will include request_id and user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """
    Remove specific keys from the bound context.

    Args:
        *keys: Keys to remove from the context

    Example:
        >>> unbind_context("request_id", "user_id")
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """
    Clear all bound context variables.

    Example:
        >>> clear_context()
    """
    structlog.contextvars.clear_contextvars()


# ============================================================================
# Convenience Functions
# ============================================================================

def log_function_call(log: structlog.BoundLogger, func_name: str, **params: Any) -> None:
    """
    Log a function call with parameters.

    Args:
        log: Logger instance
        func_name: Name of the function being called
        **params: Function parameters to log
    """
    log.debug(
        "Function called",
        function=func_name,
        parameters=params
    )


def log_function_result(log: structlog.BoundLogger, func_name: str, result: Any, duration_ms: Optional[float] = None) -> None:
    """
    Log a function result.

    Args:
        log: Logger instance
        func_name: Name of the function
        result: Result to log (will be sanitized)
        duration_ms: Optional execution duration in milliseconds
    """
    log_data = {
        "function": func_name,
        "result_type": type(result).__name__,
    }

    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 2)

    log.debug("Function completed", **log_data)


def log_error(log: structlog.BoundLogger, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an error with full context.

    Args:
        log: Logger instance
        error: The exception to log
        context: Optional additional context
    """
    log_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    if context:
        log_data.update(context)

    log.error("Error occurred", exc_info=True, **log_data)
