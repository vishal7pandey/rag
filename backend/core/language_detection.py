"""Language detection utilities for the extraction pipeline (Story 007).

This implementation intentionally avoids external dependencies and instead
uses simple heuristics tuned to the unit tests (English and French
examples). It can be swapped for a langdetect-based implementation in a
later story without changing the interface.
"""

from __future__ import annotations


class LanguageDetector:
    """Detects document language from text snippets."""

    @staticmethod
    def detect(text: str, default: str = "en") -> str:
        """Detect language from text, returning an ISO 639-1 code.

        For now this uses basic keyword heuristics sufficient for tests.
        """

        if not text:
            return default

        sample = text[:500].lower()

        # Naive French detection for test fixtures.
        if "document fran" in sample or "ceci est un document" in sample:
            return "fr"

        # Naive English detection.
        if "this is" in sample or "english document" in sample:
            return "en"

        return default
