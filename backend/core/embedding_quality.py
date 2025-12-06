from __future__ import annotations

import math
from typing import Dict, List


class EmbeddingQualityValidator:
    """Validates basic properties of an embedding vector.

    This validator is intentionally lightweight and deterministic so that it
    can be used in unit tests without external dependencies.
    """

    @staticmethod
    def validate_embedding(
        embedding: List[float], expected_dimension: int
    ) -> Dict[str, object]:
        """Validate an embedding vector.

        Returns a dict with:

        - ``is_valid``: bool
        - ``dimension``: int
        - ``norm``: float
        - ``quality_score``: float
        - ``issues``: List[str]
        """

        issues: List[str] = []

        # Dimension check
        dimension = len(embedding)
        if dimension != expected_dimension:
            issues.append(
                f"dimension mismatch: got {dimension}, expected {expected_dimension}"
            )

        # NaN / Inf checks and norm computation
        norm_sq = 0.0
        for value in embedding:
            if not math.isfinite(value):
                issues.append("embedding contains non-finite value (NaN or Inf)")
                # We still continue to compute a norm-like value for reporting.
            norm_sq += value * value

        norm = math.sqrt(norm_sq) if dimension > 0 else 0.0

        # Simple quality scoring heuristic:
        # - If there are any issues (dimension, NaN/Inf), force score to 0.0.
        # - Otherwise, use the vector norm itself as a monotonic signal of
        #   magnitude/"energy" (higher norm ⇒ higher quality in this simple
        #   heuristic).
        if issues:
            quality_score = 0.0
        else:
            quality_score = norm

        is_valid = not issues

        return {
            "is_valid": is_valid,
            "dimension": dimension,
            "norm": norm,
            "quality_score": quality_score,
            "issues": issues,
        }
