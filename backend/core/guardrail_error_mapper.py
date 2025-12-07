from __future__ import annotations

from typing import Tuple

from backend.core.exceptions import QueryTimeoutError, ValidationError


class GuardrailErrorMapper:
    """Map guardrail-related errors to HTTP-friendly tuples.

    This helper mirrors the Story 015 specification by providing explicit
    mappings for ValidationError and QueryTimeoutError. In practice, the
    global exception handler already turns these into the correct JSON error
    envelope, but this mapper is useful for tests and future wiring.
    """

    def map_validation_error(self, error: ValidationError) -> Tuple[int, str, str]:
        """Map ValidationError to (status_code, error_type, message)."""

        status_code = error.status_code
        error_type = error.error_code or "validation"
        message = error.message
        return status_code, error_type, message

    def map_timeout_error(self, error: QueryTimeoutError) -> Tuple[int, str, str]:
        """Map QueryTimeoutError to (status_code, error_type, message)."""

        status_code = error.status_code
        error_type = error.error_code or "timeout"
        # Provide a user-friendly message referencing the configured timeout.
        timeout_seconds = getattr(error, "timeout_seconds", None)
        if timeout_seconds is not None:
            message = f"Query execution exceeded {timeout_seconds} seconds."
        else:
            message = error.message
        return status_code, error_type, message
