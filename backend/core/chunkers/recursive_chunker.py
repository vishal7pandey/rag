"""Recursive text chunking on semantic boundaries (Story 008).

This module provides a low-level recursive chunker that operates on raw
strings. It returns simple dictionaries containing the chunk content and
relative character offsets. Higher-level services are responsible for
converting these into rich Chunk objects with metadata.
"""

from __future__ import annotations

from typing import Dict, List, Optional


class RecursiveChunker:
    """Chunks text recursively on semantic boundaries.

    The chunker works in character space and is intentionally simple. It tries
    a series of separators in order and falls back to smaller separators or
    character-level splitting when necessary.
    """

    @staticmethod
    def chunk(
        text: str,
        chunk_size: int,
        separators: Optional[List[str]] = None,
        keep_separator: bool = False,
    ) -> List[Dict[str, int | str]]:
        """Split text recursively into chunks.

        Args:
            text: Input text to chunk.
            chunk_size: Target chunk size in characters.
            separators: List of separators to try in order. If ``None``, a
                default list of ["\n\n", "\n", ".", " "] is used.
            keep_separator: Whether to keep the separator attached to the
                preceding chunk.

        Returns:
            List of dictionaries: {"content": str, "start": int, "end": int}.
        """

        if not text:
            return []

        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")

        if separators is None:
            separators = ["\n\n", "\n", ".", " "]

        return RecursiveChunker._split_text(
            text=text,
            separators=separators,
            chunk_size=chunk_size,
            keep_separator=keep_separator,
            offset=0,
        )

    @staticmethod
    def _split_text(
        text: str,
        separators: List[str],
        chunk_size: int,
        keep_separator: bool,
        offset: int,
    ) -> List[Dict[str, int | str]]:
        """Recursively split ``text`` into chunks.

        Offsets are tracked relative to the initial input text by carrying an
        ``offset`` parameter; they are intended for approximate position
        tracking and are sufficient for the Story 008 tests.
        """

        text = text or ""
        length = len(text)

        # If we have no separators left, fall back to character-level splitting.
        if not separators:
            if not text.strip():
                return []

            chunks: List[Dict[str, int | str]] = []
            start = 0
            while start < length:
                end = min(start + chunk_size, length)
                segment = text[start:end]
                if segment.strip():
                    chunks.append(
                        {
                            "content": segment,
                            "start": offset + start,
                            "end": offset + end,
                        }
                    )
                start = end
            return chunks

        # If text already fits in a single chunk and we still have separators,
        # we *still* allow splitting on separators to preserve boundaries.
        if length <= chunk_size and separators:
            current_sep = separators[0]
            if current_sep in text:
                # Let the normal splitting logic below handle this.
                pass
            else:
                # Try remaining separators; if none work, we'll fall back above.
                return RecursiveChunker._split_text(
                    text=text,
                    separators=separators[1:],
                    chunk_size=chunk_size,
                    keep_separator=keep_separator,
                    offset=offset,
                )

        current_sep = separators[0]
        remaining_seps = separators[1:]

        # If this separator does not occur, try the next one.
        if current_sep and current_sep not in text:
            return RecursiveChunker._split_text(
                text=text,
                separators=remaining_seps,
                chunk_size=chunk_size,
                keep_separator=keep_separator,
                offset=offset,
            )

        parts = text.split(current_sep)
        # If the separator produced only one part, fall back to the next.
        if len(parts) == 1:
            return RecursiveChunker._split_text(
                text=text,
                separators=remaining_seps,
                chunk_size=chunk_size,
                keep_separator=keep_separator,
                offset=offset,
            )

        chunks: List[Dict[str, int | str]] = []
        running_offset = offset

        for i, part in enumerate(parts):
            if not part and i == len(parts) - 1:
                break

            segment = part
            # For sentence boundaries ('.'), we always keep the separator with
            # the preceding chunk so that chunks tend to end on punctuation
            # rather than mid-word. For other separators we respect the
            # keep_separator flag.
            attach_separator = keep_separator or current_sep == "."
            if attach_separator and i < len(parts) - 1:
                segment = part + current_sep

            seg_len = len(segment)
            if seg_len == 0:
                running_offset += len(part) + (
                    len(current_sep) if i < len(parts) - 1 else 0
                )
                continue

            if seg_len > chunk_size and remaining_seps:
                # Recurse with the remaining separators for oversized segments.
                subchunks = RecursiveChunker._split_text(
                    text=segment,
                    separators=remaining_seps,
                    chunk_size=chunk_size,
                    keep_separator=keep_separator,
                    offset=running_offset,
                )
                chunks.extend(subchunks)
            else:
                if segment.strip():
                    chunks.append(
                        {
                            "content": segment,
                            "start": running_offset,
                            "end": running_offset + seg_len,
                        }
                    )

            running_offset += seg_len

        return chunks
