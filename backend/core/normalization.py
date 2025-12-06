"""Text normalization utilities for the extraction pipeline (Story 007)."""

from __future__ import annotations

import re


class TextNormalizer:
    """Normalizes extracted text and detects empty/near-empty pages."""

    _CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

    @staticmethod
    def normalize(text: str) -> str:
        """Apply normalization rules to extracted text.

        - Remove control characters (except tab/newline/carriage return).
        - Normalize CRLF/CR to LF.
        - Collapse multiple spaces/tabs within lines.
        - Strip leading/trailing whitespace per line.
        - Remove excessive empty lines while preserving basic structure.
        """

        if not text:
            return ""

        # Remove control characters.
        text = TextNormalizer._CONTROL_CHARS_RE.sub("", text)

        # Normalize line endings to LF.
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        normalized_lines = []
        for line in text.split("\n"):
            # Collapse multiple spaces/tabs to a single space within the line.
            line = re.sub(r"[ \t]+", " ", line).strip()
            if line:
                normalized_lines.append(line)

        return "\n".join(normalized_lines)

    @staticmethod
    def is_empty_page(text: str) -> bool:
        """Return True if the page should be considered empty.

        Uses a simple heuristic based primarily on word count and
        whitespace-only content.
        """

        if not text or not text.strip():
            return True

        words = text.split()
        if len(words) < 3:
            return True

        return False
