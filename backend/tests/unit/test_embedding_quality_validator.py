from __future__ import annotations

from typing import List

from backend.core.embedding_quality import EmbeddingQualityValidator


def test_validator_validates_correct_dimension() -> None:
    """Correct dimension passes validation."""

    embedding: List[float] = [0.1] * 1536

    result = EmbeddingQualityValidator.validate_embedding(embedding, 1536)

    assert result["is_valid"] is True
    assert result["dimension"] == 1536
    assert result["issues"] == []


def test_validator_rejects_wrong_dimension() -> None:
    """Wrong dimension fails validation."""

    embedding: List[float] = [0.1] * 512  # Wrong size

    result = EmbeddingQualityValidator.validate_embedding(embedding, 1536)

    assert result["is_valid"] is False
    assert any("dimension" in issue for issue in result["issues"])


def test_validator_rejects_nan_values() -> None:
    """NaN values detected."""

    embedding: List[float] = [0.1] * 1535 + [float("nan")]

    result = EmbeddingQualityValidator.validate_embedding(embedding, 1536)

    assert result["is_valid"] is False
    assert any("NaN" in issue or "non-finite" in issue for issue in result["issues"])


def test_validator_calculates_norm() -> None:
    """L2 norm calculated correctly."""

    # Unit vector should have norm ~1.0
    embedding: List[float] = [1.0 / (1536**0.5)] * 1536

    result = EmbeddingQualityValidator.validate_embedding(embedding, 1536)

    assert abs(result["norm"] - 1.0) < 0.1


def test_validator_quality_score() -> None:
    """Quality score reflects norm and properties."""

    good_embedding: List[float] = [0.1] * 1536  # Larger norm
    bad_embedding: List[float] = [0.001] * 1536  # Very small values

    good_result = EmbeddingQualityValidator.validate_embedding(good_embedding, 1536)
    bad_result = EmbeddingQualityValidator.validate_embedding(bad_embedding, 1536)

    assert good_result["quality_score"] > bad_result["quality_score"]
