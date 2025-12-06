"""File format detection and routing for text extraction (Story 007)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from backend.core.exceptions import ExtractionError
from backend.core.logging import get_logger


class FileFormat(str, Enum):
    PDF = "pdf"
    TEXT = "txt"
    MARKDOWN = "markdown"


class FormatDetector:
    """Detects file format from content and filename."""

    SUPPORTED_FORMATS = {
        FileFormat.PDF: [".pdf"],
        FileFormat.TEXT: [".txt"],
        FileFormat.MARKDOWN: [".md"],
    }

    @staticmethod
    def _detect_from_signature(content: bytes) -> Optional[FileFormat]:
        """Detect format from file signature (magic bytes)."""

        if content.startswith(b"%PDF"):
            return FileFormat.PDF
        # Extendable: add more signatures as needed.
        return None

    @staticmethod
    def _detect_from_extension(filename: str) -> Optional[FileFormat]:
        """Detect format from file extension."""

        if "." not in filename:
            return None

        ext = "." + filename.rsplit(".", 1)[-1].lower()
        for fmt, extensions in FormatDetector.SUPPORTED_FORMATS.items():
            if ext in extensions:
                return fmt

        return None

    @staticmethod
    def detect_format(filename: str, content: bytes) -> FileFormat:
        """Detect file format, preferring signature then extension."""

        fmt = FormatDetector._detect_from_signature(content)
        if fmt:
            return fmt

        fmt = FormatDetector._detect_from_extension(filename)
        if fmt:
            return fmt

        logger = get_logger("rag.core.format_detector")
        logger.error(
            "format_detection_failed",
            extra={
                "context": {
                    "filename": filename,
                    "error_type": "unsupported_format",
                    "reason": "extension_not_supported",
                }
            },
        )

        raise ExtractionError(
            message=f"Unsupported file format: {filename}",
            filename=filename,
            error_type="unsupported_format",
            details={"reason": "extension_not_supported"},
            status_code=400,
        )
