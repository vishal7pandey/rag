"""Fixed-size sliding window text chunking (Story 008).

This module provides a low-level sliding-window chunker that operates on raw
strings. It returns simple dictionaries containing the chunk content and
character offsets; higher-level services are responsible for turning these into
rich Chunk objects with metadata.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional


class SlidingWindowChunker:
    """Chunks text using a fixed-size sliding window.

    The chunker operates in character space. It is intentionally simple and
    does not attempt to be token-aware; Story 008 uses character lengths here
    and approximates token counts at a higher level.
    """

    @staticmethod
    def chunk(
        text: str,
        chunk_size: int,
        overlap: int,
        length_fn: Optional[Callable[[str], int]] = None,
    ) -> List[Dict[str, int | str]]:
        """Split text into overlapping chunks.

        Args:
            text: Input text to chunk.
            chunk_size: Target size of each chunk in characters. Must be > 0.
            overlap: Desired overlap between consecutive chunks in characters.
            length_fn: Optional function to measure text length. Defaults to
                built-in ``len`` and must be compatible with character-based
                indexing.

        Returns:
            List of dictionaries: {"content": str, "start": int, "end": int}.
        """

        if not text or chunk_size <= 0:
            return []

        if overlap < 0:
            raise ValueError("overlap must be >= 0")

        if overlap >= chunk_size:
            raise ValueError("overlap must be < chunk_size")

        if length_fn is None:
            length_fn = len

        chunks: List[Dict[str, int | str]] = []
        text_len = length_fn(text)
        start = 0

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk_text = text[start:end]

            if chunk_text.strip():
                chunks.append({"content": chunk_text, "start": start, "end": end})

            # Advance by (chunk_size - overlap). We already ensure this is > 0.
            start += chunk_size - overlap

        return chunks
