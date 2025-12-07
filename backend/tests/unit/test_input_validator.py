from __future__ import annotations

import pytest

from backend.core.exceptions import ValidationError
from backend.core.guardrails import InputValidator


def test_validate_query_empty_raises_validation_error() -> None:
    validator = InputValidator()

    with pytest.raises(ValidationError) as exc_info:
        validator.validate_request(query="", top_k=10)

    assert "empty" in str(exc_info.value).lower()
    assert exc_info.value.details.get("field") == "query"


def test_validate_query_too_long_raises_validation_error() -> None:
    validator = InputValidator()
    long_query = "x" * (validator.MAX_QUERY_LENGTH + 1)

    with pytest.raises(ValidationError) as exc_info:
        validator.validate_request(query=long_query, top_k=10)

    text = str(exc_info.value).lower()
    assert "exceed" in text or "long" in text
    assert exc_info.value.details.get("field") == "query"


def test_validate_top_k_out_of_range_raises_validation_error() -> None:
    validator = InputValidator()

    with pytest.raises(ValidationError):
        validator.validate_request(query="test", top_k=0)

    with pytest.raises(ValidationError):
        validator.validate_request(query="test", top_k=validator.TOP_K_MAX + 1)


def test_validate_valid_inputs_ok() -> None:
    validator = InputValidator()

    # Should not raise
    validator.validate_request(query="what is policy?", top_k=10)


def test_validate_boundary_lengths_ok() -> None:
    validator = InputValidator()

    # Min valid length
    validator.validate_request(query="a", top_k=10)

    # Max valid length
    validator.validate_request(query="x" * validator.MAX_QUERY_LENGTH, top_k=10)

    # Boundary top_k values
    validator.validate_request(query="test", top_k=validator.TOP_K_MIN)
    validator.validate_request(query="test", top_k=validator.TOP_K_MAX)
