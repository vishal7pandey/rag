"""File upload validation and format detection for ingestion.

Implements size, count, and MIME-type checks for uploaded files as
specified in Story 006.
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class FileValidationResult:
    """Result of validating a single uploaded file."""

    is_valid: bool
    filename: str
    file_size_bytes: int
    mime_type: str
    extension: str
    error: Optional[str] = None

    @property
    def file_size_mb(self) -> float:
        """File size in megabytes."""

        return self.file_size_bytes / (1024 * 1024)


class FileValidator:
    """Validates uploaded files against format and size constraints."""

    SUPPORTED_MIME_TYPES = {
        "application/pdf": [".pdf"],
        "text/plain": [".txt"],
        "text/markdown": [".md"],
        "text/x-markdown": [".md"],  # common alternative for markdown
    }

    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB per file
    MAX_FILES_PER_REQUEST = 10
    MAX_TOTAL_SIZE_BYTES = 500 * 1024 * 1024  # 500MB per request

    @staticmethod
    def _detect_mime_type(filename: str, content: bytes) -> str:
        """Detect MIME type from filename and content."""

        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            return mime_type

        if content.startswith(b"%PDF"):
            return "application/pdf"

        # Default generic binary type; will be rejected unless explicitly allowed.
        return "application/octet-stream"

    @staticmethod
    def _get_extension(filename: str) -> str:
        """Extract file extension (including dot, lowercased)."""

        if "." not in filename:
            return ""
        return "." + filename.rsplit(".", 1)[-1].lower()

    def validate_single_file(
        self, filename: str, content: bytes
    ) -> FileValidationResult:
        """Validate a single file according to Story 006 rules."""

        extension = self._get_extension(filename)
        file_size = len(content)
        mime_type = self._detect_mime_type(filename, content)

        if file_size > self.MAX_FILE_SIZE_BYTES:
            return FileValidationResult(
                is_valid=False,
                filename=filename,
                file_size_bytes=file_size,
                mime_type=mime_type,
                extension=extension,
                error=(
                    f"File size {file_size / (1024 * 1024):.1f} MB exceeds 50 MB limit"
                ),
            )

        if mime_type not in self.SUPPORTED_MIME_TYPES:
            return FileValidationResult(
                is_valid=False,
                filename=filename,
                file_size_bytes=file_size,
                mime_type=mime_type,
                extension=extension,
                error=f"Unsupported file type {extension or mime_type}",
            )

        supported_extensions = self.SUPPORTED_MIME_TYPES[mime_type]
        if extension not in supported_extensions:
            return FileValidationResult(
                is_valid=False,
                filename=filename,
                file_size_bytes=file_size,
                mime_type=mime_type,
                extension=extension,
                error=f"File extension {extension} does not match MIME type {mime_type}",
            )

        return FileValidationResult(
            is_valid=True,
            filename=filename,
            file_size_bytes=file_size,
            mime_type=mime_type,
            extension=extension,
        )

    def validate_batch(
        self, files: List[Tuple[str, bytes]]
    ) -> Tuple[List[FileValidationResult], Optional[str]]:
        """Validate all files in a batch.

        Returns (results, batch_error_message). If `batch_error_message` is not
        None, at least one file failed validation or the batch violates global
        size/count limits.
        """

        if not files:
            return [], "No files provided"

        if len(files) > self.MAX_FILES_PER_REQUEST:
            return (
                [],
                f"Maximum {self.MAX_FILES_PER_REQUEST} files per request, got {len(files)}",
            )

        results: List[FileValidationResult] = []
        total_size = 0

        for filename, content in files:
            result = self.validate_single_file(filename, content)
            results.append(result)
            if result.is_valid:
                total_size += result.file_size_bytes

        failed = [r for r in results if not r.is_valid]
        if failed:
            return results, "File validation failed"

        if total_size > self.MAX_TOTAL_SIZE_BYTES:
            return (
                results,
                f"Total payload {total_size / (1024 * 1024):.1f} MB exceeds 500 MB limit",
            )

        return results, None
