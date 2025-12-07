from __future__ import annotations

from backend.core.exceptions import (
    BadRequestError,
    RAGException,
    RateLimitError,
    ServiceUnavailableError,
)
from backend.core.generation_services import GenerationErrorMapper


def test_map_rate_limit_error_returns_503() -> None:
    mapper = GenerationErrorMapper()
    err = RateLimitError("Too many requests", retry_after_seconds=10)

    status, error_type, message = mapper.map_error(err)

    assert status == 503
    assert error_type == "rate_limit"
    assert "temporarily" in message.lower()


def test_map_service_unavailable_error_returns_503() -> None:
    mapper = GenerationErrorMapper()
    err = ServiceUnavailableError("Upstream down")

    status, error_type, message = mapper.map_error(err)

    assert status == 503
    assert error_type == "service_unavailable"
    assert "unavailable" in message.lower()


def test_map_bad_request_or_value_error_returns_400() -> None:
    mapper = GenerationErrorMapper()

    status1, error_type1, _ = mapper.map_error(BadRequestError("bad"))
    status2, error_type2, _ = mapper.map_error(ValueError("invalid"))

    assert status1 == 400
    assert error_type1 == "invalid_request"
    assert status2 == 400
    assert error_type2 == "invalid_request"


def test_map_generic_rag_exception_preserves_status_and_code() -> None:
    mapper = GenerationErrorMapper()
    err = RAGException("oops", status_code=418, error_code="TeapotError")

    status, error_type, message = mapper.map_error(err)

    assert status == 418
    assert error_type == "TeapotError"
    assert "error" in message.lower()


def test_map_unknown_exception_defaults_to_503_provider_error() -> None:
    mapper = GenerationErrorMapper()

    status, error_type, message = mapper.map_error(RuntimeError("boom"))

    assert status == 503
    assert error_type == "provider_error"
    assert "temporarily" in message.lower() or "unavailable" in message.lower()
