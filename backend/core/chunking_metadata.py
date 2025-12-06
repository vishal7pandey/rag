"""Chunk metadata utilities and quality scoring (Story 008)."""

from __future__ import annotations

from typing import Dict, Optional
from uuid import UUID, uuid4

from backend.core.chunking_models import Chunk


class ChunkMetadataTracker:
    """Factory for creating chunks with consistent metadata and metrics."""

    @staticmethod
    def create_chunk(
        *,
        content: str,
        document_id: UUID,
        page_number: int,
        position_in_page: Dict[str, int],
        section_title: Optional[str],
        original_content: Optional[str] = None,
        document_type: Optional[str] = None,
        source_filename: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Chunk:
        """Create a fully-formed ``Chunk`` instance.

        The caller is responsible for supplying basic provenance information;
        this helper computes word/char/token counts and a simple quality score.
        """

        text = content or ""
        original = original_content or text

        words = text.split()
        word_count = len(words)
        char_count = len(text)
        token_count = int(round(word_count * 1.3))

        quality_score = ChunkMetadataTracker._compute_quality_score(token_count)

        metadata: Dict[str, object] = {
            "page_number": page_number,
            "position_in_page": position_in_page,
        }

        if section_title is not None:
            metadata["section_title"] = section_title
        if document_type is not None:
            metadata["document_type"] = document_type
        if source_filename is not None:
            metadata["source_filename"] = source_filename
        if language is not None:
            metadata["language"] = language

        return Chunk(
            chunk_id=uuid4(),
            document_id=document_id,
            content=text,
            original_content=original,
            metadata=metadata,
            token_count=token_count,
            word_count=word_count,
            char_count=char_count,
            quality_score=quality_score,
        )

    @staticmethod
    def _compute_quality_score(token_count: int) -> float:
        """Compute a simple quality score based on approximate token length.

        The score is highest for medium-sized chunks and decreases for very
        small or very large chunks. This is intentionally simple but good
        enough for Story 008.
        """

        if token_count <= 0:
            return 0.0

        # Ideal range ~300-800 tokens.
        ideal_min = 300
        ideal_max = 800

        if token_count <= ideal_min:
            return max(0.1, token_count / ideal_min)
        if token_count <= ideal_max:
            return 1.0

        # Above ideal_max, decay linearly until 0 at 2 * ideal_max.
        decay_range = float(ideal_max)
        excess = float(token_count - ideal_max)
        score = max(0.0, 1.0 - excess / decay_range)
        return score
