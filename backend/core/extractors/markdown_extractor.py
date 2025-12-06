"""Markdown extractor for Story 007.

Parses markdown content into an ExtractedDocument while preserving basic
structure (headings and sections). This is a light-weight implementation
that does not depend on a full markdown library; it is sufficient for the
Story 007 unit tests and can be swapped for a richer parser later.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from backend.core.data_models import ExtractedDocument, ExtractedPage
from backend.core.exceptions import ExtractionError
from backend.core.language_detection import LanguageDetector
from backend.core.logging import get_logger
from backend.core.normalization import TextNormalizer


class MarkdownExtractor:
    """Extracts text from markdown files with simple structure tracking."""

    @staticmethod
    def extract(
        content: bytes,
        document_id: UUID,
        filename: str,
    ) -> ExtractedDocument:
        """Extract markdown into an ExtractedDocument.

        This implementation:
        - Decodes bytes as UTF-8 (with fallback ignoring errors).
        - Parses optional YAML frontmatter (lines between leading and
          trailing '---').
        - Tracks headings (#, ##, etc.) and uses them as section titles.
        - Produces a single-page ExtractedDocument with normalized text.
        """

        import time

        logger = get_logger("rag.core.markdown_extractor")
        start_time = time.time()

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("utf-8", errors="ignore")
            except Exception as exc2:  # pragma: no cover - very defensive
                logger.error(
                    "markdown_decode_failed",
                    extra={
                        "context": {
                            "filename": filename,
                            "error_type": "decode_error",
                            "encoding": "utf-8",
                        }
                    },
                )
                raise ExtractionError(
                    message="Failed to decode markdown content",
                    filename=filename,
                    error_type="decode_error",
                    details={"encoding": "utf-8"},
                    status_code=500,
                ) from exc2

        lines = text.split("\n")
        metadata = {}
        body_lines: List[str] = []

        # Very simple YAML frontmatter detection.
        if lines and lines[0].strip() == "---":
            end_index = None
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    end_index = i
                    break
            if end_index is not None:
                frontmatter_lines = lines[1:end_index]
                for line in frontmatter_lines:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip()
                body_lines = lines[end_index + 1 :]
            else:
                body_lines = lines
        else:
            body_lines = lines

        # Track heading hierarchy and preserve code blocks.
        section_title = None
        cleaned_lines: List[str] = []
        section_hierarchy: List[dict] = []
        in_code_block = False

        for line in body_lines:
            stripped = line.rstrip("\n")

            # Toggle fenced code blocks (```)
            if stripped.strip().startswith("```"):
                in_code_block = not in_code_block
                cleaned_lines.append(stripped)
                continue

            if in_code_block:
                # Preserve code lines verbatim inside fenced blocks.
                cleaned_lines.append(stripped)
                continue

            # Headings: #, ##, ### ...
            if stripped.lstrip().startswith("#"):
                leading_hashes = len(stripped) - len(stripped.lstrip("#"))
                level = max(1, min(leading_hashes, 6))
                heading = stripped.lstrip("#").strip()
                section_title = heading or section_title
                cleaned_lines.append(heading)

                section_hierarchy.append({"level": level, "title": heading})
                continue

            # Lists/bullets: -, *, +, or numbered lists like "1. "
            stripped_ws = stripped.lstrip()
            if stripped_ws.startswith(("- ", "* ", "+ ")):
                bullet_text = stripped_ws[2:].strip()
            elif any(stripped_ws.startswith(f"{i}. ") for i in range(1, 10)):
                # Very simple numbered list handling for 1-9.
                bullet_text = stripped_ws.split(" ", 1)[1].strip()
            else:
                bullet_text = stripped

            # Remove basic markdown emphasis/link syntax but keep words.
            no_emphasis = bullet_text.replace("**", "").replace("*", "")
            # Very naive link removal: [text](url) -> text
            while "[" in no_emphasis and "](" in no_emphasis:
                start = no_emphasis.find("[")
                mid = no_emphasis.find("](", start)
                end = no_emphasis.find(")", mid)
                if start == -1 or mid == -1 or end == -1:
                    break
                label = no_emphasis[start + 1 : mid]
                no_emphasis = no_emphasis[:start] + label + no_emphasis[end + 1 :]

            cleaned_lines.append(no_emphasis)

        raw_text = "\n".join(cleaned_lines)
        normalized_text = TextNormalizer.normalize(raw_text)

        is_empty = TextNormalizer.is_empty_page(normalized_text)
        word_count = len(normalized_text.split()) if normalized_text else 0
        char_count = len(normalized_text)
        line_count = len(cleaned_lines)

        page = ExtractedPage(
            page_number=0,
            raw_text=raw_text,
            normalized_text=normalized_text,
            is_empty=is_empty,
            word_count=word_count,
            char_count=char_count,
            line_count=line_count,
            language=None,
            section_title=section_title,
            confidence_score=1.0,
        )

        language = LanguageDetector.detect(normalized_text or raw_text)
        page.language = language

        # Document-level quality metrics for a single-page markdown document.
        total_words = word_count
        total_chars = char_count
        empty_pages = 1 if is_empty else 0
        non_empty_pages = 1 - empty_pages

        duration_ms = (time.time() - start_time) * 1000.0

        logger.info(
            "markdown_extraction_completed",
            extra={
                "context": {
                    "filename": filename,
                    "document_id": str(document_id),
                    "format": "markdown",
                    "total_pages": 1,
                    "language": language,
                    "duration_ms": duration_ms,
                }
            },
        )

        return ExtractedDocument(
            document_id=document_id,
            filename=filename,
            format="markdown",
            language=language,
            total_pages=1,
            pages=[page],
            extraction_metadata={
                **metadata,
                "section_hierarchy": section_hierarchy,
                "total_words": total_words,
                "total_chars": total_chars,
                "empty_pages": empty_pages,
                "non_empty_pages": non_empty_pages,
            },
            extraction_duration_ms=duration_ms,
        )
