"""Core exception hierarchy for the RAG system.

This module defines a small set of HTTP-oriented exception types that can be
used across layers (API, ingestion, retrieval, etc.). Story 005 introduces
`RAGException` as a common base so that the global error handler can produce a
consistent JSON error envelope.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class RAGException(Exception):
    """Base exception for the RAG system.

    Parameters
    ----------
    message:
        Human-readable error message.
    status_code:
        HTTP status code associated with this error.
    error_code:
        Stable machine-readable error code; defaults to the class name.
    details:
        Optional additional structured information about the error.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(message)


class BadRequestError(RAGException):
    """HTTP 400 – Bad Request."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=400, details=details)


class UnauthorizedError(RAGException):
    """HTTP 401 – Unauthorized."""

    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, status_code=401)


class NotFoundError(RAGException):
    """HTTP 404 – Not Found."""

    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, status_code=404)


class ConflictError(RAGException):
    """HTTP 409 – Conflict."""

    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, status_code=409)


class InternalServerError(RAGException):
    """HTTP 500 – Internal Server Error."""

    def __init__(self, message: str = "Internal server error") -> None:
        super().__init__(message, status_code=500)


class ServiceUnavailableError(RAGException):
    """HTTP 503 – Service Unavailable."""

    def __init__(self, message: str = "Service unavailable") -> None:
        super().__init__(message, status_code=503)


class QueryTimeoutError(ServiceUnavailableError):
    """HTTP 408 – Query exceeded global timeout.

    Used by Story 015 to signal that the end-to-end query execution exceeded
    the configured timeout. This is a specialized subtype of
    ServiceUnavailableError so it participates in the same error-handling
    flow while carrying additional timeout metadata.
    """

    def __init__(
        self,
        message: str,
        *,
        timeout_seconds: int,
        elapsed_ms: float,
        stages_completed: int = 0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.elapsed_ms = elapsed_ms
        self.stages_completed = stages_completed
        extra_details: Dict[str, Any] = {
            "timeout_seconds": timeout_seconds,
            "elapsed_ms": elapsed_ms,
            "stages_completed": stages_completed,
        }
        if details:
            extra_details.update(details)

        # Bypass ServiceUnavailableError.__init__ so we can use 408 instead of 503.
        RAGException.__init__(
            self,
            message,
            status_code=408,
            error_code="timeout",
            details=extra_details,
        )


class ValidationError(BadRequestError):
    """HTTP 422 – Input validation failed.

    Story 015 uses this for query-level validation errors (e.g. empty query,
    query too long, invalid top_k). It carries the name of the field that
    failed validation in addition to a human-readable message.
    """

    def __init__(
        self,
        message: str,
        *,
        validation_field: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details: Dict[str, Any] = {"field": validation_field}
        if details:
            extra_details.update(details)
        RAGException.__init__(
            self,
            message,
            status_code=422,
            error_code="validation",
            details=extra_details,
        )


class ResourceExistsError(ConflictError):
    """Resource already exists."""


class ExtractionError(RAGException):
    """Extraction failed for a particular file.

    This error is used by the text extraction pipeline (Story 007) and is
    aligned with the global RAGException hierarchy so that the API error
    handler can produce a consistent JSON envelope.
    """

    def __init__(
        self,
        message: str,
        filename: str,
        error_type: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ) -> None:
        merged_details: Dict[str, Any] = {
            "filename": filename,
            "error_type": error_type,
        }
        if details:
            merged_details.update(details)
        super().__init__(message, status_code=status_code, details=merged_details)


class FileValidationError(BadRequestError):
    """File validation failed for one or more uploaded files."""

    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        details = {"validation_errors": validation_errors or []}
        super().__init__(message, details=details)


class RateLimitError(RAGException):
    """Rate limit exceeded for a user or API key."""

    def __init__(
        self,
        message: str,
        retry_after_seconds: int = 3600,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra_details: Dict[str, Any] = {"retry_after_seconds": retry_after_seconds}
        if details:
            extra_details.update(details)
        super().__init__(
            message,
            status_code=429,
            error_code="RateLimitError",
            details=extra_details,
        )
