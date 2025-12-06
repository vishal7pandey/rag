"""Core data models for the text extraction pipeline (Story 007).

These models represent the normalized text view of ingested documents and
are used by extractors, normalizers, and downstream chunking/embedding
components.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExtractedPage(BaseModel):
    """Single page/section of an extracted document."""

    page_number: int
    raw_text: str
    normalized_text: str
    is_empty: bool
    word_count: int
    char_count: int
    line_count: int
    language: Optional[str] = None
    section_title: Optional[str] = None
    confidence_score: float = 1.0

    @property
    def is_valid(self) -> bool:
        """Page is valid if not empty and has a minimum amount of content."""

        return not self.is_empty and self.char_count > 50


class ExtractedDocument(BaseModel):
    """Complete extracted document with all pages.

    The ``document_id`` should match the ``document_id`` produced by the
    ingestion/upload layer (see ``IngestionResponse.document_id``), so that
    downstream components can correlate back to the original upload and
    file metadata.
    """

    document_id: UUID
    filename: str
    format: str
    language: str
    total_pages: int
    pages: List[ExtractedPage]

    extraction_metadata: Dict = Field(
        default_factory=dict,
        description="Format-specific metadata (e.g. page sizes, frontmatter).",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_duration_ms: float
