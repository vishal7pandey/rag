"""Global exception handler for the FastAPI app.

Story 005 adds a central error handler that converts exceptions into a
standardized JSON envelope and ensures the correlation ID (trace ID) is
included in all error responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from backend.api import errors as api_errors
from backend.core.exceptions import RAGException
from backend.core.logging import get_logger
from backend.core.tracing import get_trace_context


logger = get_logger("rag.api.error_handler")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all uncaught exceptions and return a standardized JSON envelope."""

    trace_context = get_trace_context()
    trace_id = trace_context.get("trace_id") or "unknown"

    # Determine status code and error metadata based on exception type.
    if isinstance(exc, RAGException):
        status_code = exc.status_code
        error_type = exc.error_code
        message = exc.message
        details = exc.details
    elif isinstance(exc, api_errors.APIError):
        status_code = exc.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = exc.__class__.__name__
        message = exc.detail
        details: Dict[str, Any] = {}
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = exc.__class__.__name__
        message = "Internal server error"
        details = {}

    # Log error with full context and stack trace.
    logger.error(
        "exception_caught",
        extra={
            "context": {
                "error_type": error_type,
                "message": message,
                "status_code": status_code,
                "trace_id": trace_id,
                "path": request.url.path,
                "method": request.method,
            }
        },
        exc_info=True,
    )

    error_envelope = {
        "error": {
            "type": error_type,
            "message": message,
            "status_code": status_code,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "details": details,
        }
    }

    headers: Dict[str, str] = {"X-Trace-ID": trace_id}
    # For rate-limited responses, include Retry-After if available.
    retry_after = (
        details.get("retry_after_seconds") if isinstance(details, dict) else None
    )
    if status_code == status.HTTP_429_TOO_MANY_REQUESTS and retry_after is not None:
        headers["Retry-After"] = str(retry_after)

    return JSONResponse(
        status_code=status_code,
        content=error_envelope,
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the global exception handler with the FastAPI app."""

    # Register for our domain-specific base types first so they are matched
    # before the generic Exception handler.
    app.add_exception_handler(RAGException, global_exception_handler)
    app.add_exception_handler(api_errors.APIError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
