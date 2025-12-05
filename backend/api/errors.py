"""Shared API error classes and helpers.

These errors provide a consistent pattern for translating domain errors into
HTTP responses. Story 002 introduces this module as the central place for
API-level error definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status


@dataclass
class APIError(Exception):
    """Base class for API-layer errors.

    This is intentionally simple for now; future stories can extend it with
    error codes, user-facing messages, and logging metadata.
    """

    detail: str = "An unknown error occurred."
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class BadRequestError(APIError):
    """400-level validation or request-shape problems."""

    status_code: int = status.HTTP_400_BAD_REQUEST


@dataclass
class ServiceUnavailableError(APIError):
    """503-level dependency failures (e.g., vector DB, embedding service)."""

    status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE
    detail: str = "Service unavailable"


def to_http_exception(
    error: APIError, default_status: Optional[int] = None
) -> HTTPException:
    """Convert an APIError into FastAPI's HTTPException.

    Parameters
    ----------
    error: APIError
        The domain-level API error to convert.
    default_status: Optional[int]
        Fallback status code if error.status_code is not set.
    """

    status_code = (
        error.status_code or default_status or status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    return HTTPException(status_code=status_code, detail=error.detail)
