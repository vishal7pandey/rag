from __future__ import annotations

from backend.core.exceptions import QueryTimeoutError, ValidationError
from backend.core.guardrail_error_mapper import GuardrailErrorMapper


def test_map_validation_error() -> None:
    """Maps ValidationError to 422 with type 'validation'."""

    mapper = GuardrailErrorMapper()
    error = ValidationError("Query too long", validation_field="query")

    status_code, error_type, message = mapper.map_validation_error(error)

    assert status_code == 422
    assert error_type == "validation"
    assert "query" in message.lower() or "long" in message.lower()


def test_map_timeout_error() -> None:
    """Maps QueryTimeoutError to 408 with type 'timeout'."""

    mapper = GuardrailErrorMapper()
    error = QueryTimeoutError(
        message="Timeout exceeded",
        timeout_seconds=30,
        elapsed_ms=30100.0,
        stages_completed=2,
    )

    status_code, error_type, message = mapper.map_timeout_error(error)

    assert status_code == 408
    assert error_type == "timeout"
    # Message should reference the timeout window or the generic timeout notion.
    assert "30" in message or "timeout" in message.lower()
