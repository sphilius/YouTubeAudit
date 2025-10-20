"""
Input validation layer for YouTube Audit Engine.

This module provides comprehensive validation for all inputs including
file uploads, API keys, and request parameters.
"""

import os
import re
from typing import Optional, List
from pathlib import Path
from werkzeug.datastructures import FileStorage
from backend.utils.logging_config import get_logger
from backend.exceptions import (
    ValidationError,
    FileValidationError,
    FileSizeError,
    FileTypeError,
    APIKeyValidationError
)
from backend.config import get_config

log = get_logger(__name__)


class FileValidator:
    """Validator for file uploads."""

    def __init__(self):
        self.config = get_config()

    def validate_file_upload(self, file: Optional[FileStorage]) -> None:
        """
        Validate an uploaded file.

        Args:
            file: The uploaded file from Flask request

        Raises:
            FileValidationError: If file validation fails
        """
        log.debug("Validating file upload")

        # Check if file exists
        if file is None:
            log.error("No file provided in upload")
            raise FileValidationError(reason="No file provided")

        if file.filename == '':
            log.error("Empty filename in upload")
            raise FileValidationError(reason="No file selected")

        filename = file.filename
        log.debug("Validating file", filename=filename)

        # Validate file extension
        self._validate_file_extension(filename)

        # Note: file size validation happens after saving in Flask
        # because FileStorage doesn't reliably provide size before reading
        log.info("File upload validation passed", filename=filename)

    def validate_saved_file(self, file_path: str) -> None:
        """
        Validate a saved file (size, readability, etc.).

        Args:
            file_path: Path to the saved file

        Raises:
            FileValidationError: If file validation fails
        """
        log.debug("Validating saved file", file_path=file_path)

        # Check file exists
        if not os.path.exists(file_path):
            log.error("File does not exist", file_path=file_path)
            raise FileValidationError(reason="File not found", filename=file_path)

        # Validate file size
        self._validate_file_size(file_path)

        # Validate file is readable
        self._validate_file_readable(file_path)

        log.info("Saved file validation passed", file_path=file_path)

    def _validate_file_extension(self, filename: str) -> None:
        """Validate file extension is allowed."""
        file_extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        allowed_extensions = self.config.allowed_extensions
        if file_extension not in allowed_extensions:
            log.error(
                "Invalid file extension",
                filename=filename,
                extension=file_extension,
                allowed=list(allowed_extensions)
            )
            raise FileTypeError(
                file_type=file_extension,
                allowed_types=list(allowed_extensions),
                filename=filename
            )

        log.debug("File extension valid", extension=file_extension)

    def _validate_file_size(self, file_path: str) -> None:
        """Validate file size is within limits."""
        file_size = os.path.getsize(file_path)
        max_size = self.config.max_upload_size_bytes

        if file_size > max_size:
            log.error(
                "File size exceeds limit",
                file_path=file_path,
                size_bytes=file_size,
                max_bytes=max_size
            )
            raise FileSizeError(
                size=file_size,
                max_size=max_size,
                filename=file_path
            )

        if file_size == 0:
            log.error("File is empty", file_path=file_path)
            raise FileValidationError(reason="File is empty", filename=file_path)

        log.debug("File size valid", size_bytes=file_size, max_bytes=max_size)

    def _validate_file_readable(self, file_path: str) -> None:
        """Validate file is readable."""
        if not os.access(file_path, os.R_OK):
            log.error("File is not readable", file_path=file_path)
            raise FileValidationError(
                reason="File is not readable",
                filename=file_path
            )

        log.debug("File is readable", file_path=file_path)


class APIKeyValidator:
    """Validator for Google API keys."""

    # Google API key pattern (starts with AIza and is 39 characters)
    GOOGLE_API_KEY_PATTERN = re.compile(r'^AIza[0-9A-Za-z_-]{35}$')

    @classmethod
    def validate_google_api_key(cls, api_key: Optional[str]) -> str:
        """
        Validate Google API key format.

        Args:
            api_key: The API key to validate

        Returns:
            The validated API key (stripped)

        Raises:
            APIKeyValidationError: If API key is invalid
        """
        log.debug("Validating Google API key")

        if not api_key:
            log.error("No API key provided")
            raise APIKeyValidationError(reason="API key is required")

        # Strip whitespace
        api_key = api_key.strip()

        # Validate format
        if not cls.GOOGLE_API_KEY_PATTERN.match(api_key):
            log.error("Invalid API key format", key_prefix=api_key[:4] if len(api_key) >= 4 else api_key)
            raise APIKeyValidationError(
                reason="Invalid API key format. Google API keys should start with 'AIza' and be 39 characters long."
            )

        log.info("Google API key validation passed")
        return api_key


class BearerTokenValidator:
    """Validator for bearer tokens."""

    @classmethod
    def validate_bearer_token(cls, token: Optional[str], expected_token: str) -> None:
        """
        Validate bearer token matches expected value.

        Args:
            token: The provided bearer token
            expected_token: The expected token value

        Raises:
            ValidationError: If token is invalid
        """
        log.debug("Validating bearer token")

        if not token:
            log.error("No bearer token provided")
            raise ValidationError(
                message="No bearer token provided",
                error_code="AUTH_001",
                user_message="Authentication required"
            )

        if token != expected_token:
            log.error("Invalid bearer token")
            raise ValidationError(
                message="Invalid bearer token",
                error_code="AUTH_002",
                user_message="Invalid authentication credentials"
            )

        log.debug("Bearer token validated successfully")


class RequestValidator:
    """Validator for API request parameters."""

    @classmethod
    def validate_num_clusters(cls, num_clusters: Optional[int], min_val: int, max_val: int) -> int:
        """
        Validate number of clusters parameter.

        Args:
            num_clusters: Requested number of clusters
            min_val: Minimum allowed value
            max_val: Maximum allowed value

        Returns:
            Validated number of clusters

        Raises:
            ValidationError: If value is out of range
        """
        if num_clusters is None:
            # Use default from middle of range
            return (min_val + max_val) // 2

        if not isinstance(num_clusters, int):
            raise ValidationError(
                message=f"num_clusters must be an integer, got {type(num_clusters).__name__}",
                user_message="Invalid cluster count"
            )

        if num_clusters < min_val or num_clusters > max_val:
            raise ValidationError(
                message=f"num_clusters must be between {min_val} and {max_val}, got {num_clusters}",
                user_message=f"Cluster count must be between {min_val} and {max_val}"
            )

        return num_clusters

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal attacks.

        Args:
            filename: The filename to sanitize

        Returns:
            Sanitized filename

        Example:
            >>> sanitize_filename("../../etc/passwd")
            'passwd'
        """
        # Remove path components
        filename = os.path.basename(filename)

        # Remove any remaining potentially dangerous characters
        filename = re.sub(r'[^\w\s.-]', '', filename)

        return filename


# Convenience functions for direct use
def validate_file_upload(file: Optional[FileStorage]) -> None:
    """Validate file upload. Convenience wrapper."""
    validator = FileValidator()
    validator.validate_file_upload(file)


def validate_saved_file(file_path: str) -> None:
    """Validate saved file. Convenience wrapper."""
    validator = FileValidator()
    validator.validate_saved_file(file_path)


def validate_google_api_key(api_key: Optional[str]) -> str:
    """Validate Google API key. Convenience wrapper."""
    return APIKeyValidator.validate_google_api_key(api_key)


def validate_bearer_token(token: Optional[str], expected: str) -> None:
    """Validate bearer token. Convenience wrapper."""
    BearerTokenValidator.validate_bearer_token(token, expected)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename. Convenience wrapper."""
    return RequestValidator.sanitize_filename(filename)
