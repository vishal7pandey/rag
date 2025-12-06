from uuid import uuid4

from backend.core.chunking_models import ChunkingConfig
from backend.core.chunking_service import ChunkingService
from backend.core.data_models import ExtractedDocument, ExtractedPage


def _create_mock_extracted_document(format: str, pages):
    pages_list = []
    for spec in pages:
        pages_list.append(
            ExtractedPage(
                page_number=spec.get("page_number", 0),
                raw_text=spec.get("raw_text", ""),
                normalized_text=spec.get("raw_text", ""),
                is_empty=not bool(spec.get("raw_text")),
                word_count=len(spec.get("raw_text", "").split()),
                char_count=len(spec.get("raw_text", "")),
                line_count=1,
                language=spec.get("language", "en"),
                section_title=spec.get("section_title"),
                confidence_score=1.0,
            )
        )

    return ExtractedDocument(
        document_id=uuid4(),
        filename=f"doc.{format}",
        format=format,
        language="en",
        total_pages=len(pages_list),
        pages=pages_list,
        extraction_metadata={},
        extraction_duration_ms=1.0,
    )


def test_chunking_pdf_document_sliding_window() -> None:
    """Chunk ExtractedDocument from PDF using sliding-window strategy."""

    extracted = _create_mock_extracted_document(
        format="pdf",
        pages=[
            {"page_number": 0, "raw_text": "Content page 1 " * 50},
            {"page_number": 1, "raw_text": "Content page 2 " * 50},
        ],
    )

    config = ChunkingConfig(
        strategy="sliding_window",
        chunk_size_chars=200,
        chunk_overlap_chars=20,
    )

    service = ChunkingService()
    result = service.chunk_document(
        extracted, config, trace_context={"trace_id": "test-123"}
    )

    assert result.total_chunks > 0
    assert all(chunk.document_id == extracted.document_id for chunk in result.chunks)
    assert all(chunk.metadata["page_number"] in [0, 1] for chunk in result.chunks)


def test_chunking_recursive_strategy_preserves_boundaries() -> None:
    """Recursive chunking aims to respect sentence boundaries."""

    extracted = _create_mock_extracted_document(
        format="txt",
        pages=[
            {
                "page_number": 0,
                "raw_text": "First sentence. Second sentence. Third sentence." * 20,
            }
        ],
    )

    config = ChunkingConfig(
        strategy="recursive",
        chunk_size_chars=256,
        separators=["\n\n", "\n", ".", " "],
    )

    service = ChunkingService()
    result = service.chunk_document(extracted, config)

    assert result.total_chunks > 0
    for chunk in result.chunks:
        # Heuristic check: chunks should generally end on non-letter boundaries.
        assert chunk.content[-1] not in "abcdefghijklmnopqrstuvwxyz"


def test_chunking_handles_empty_pages() -> None:
    """Empty pages are skipped gracefully by the chunking service."""

    extracted = _create_mock_extracted_document(
        format="pdf",
        pages=[
            {"page_number": 0, "raw_text": "Content" * 50},
            {"page_number": 1, "raw_text": ""},
            {"page_number": 2, "raw_text": "More content" * 50},
        ],
    )

    config = ChunkingConfig(strategy="sliding_window")
    service = ChunkingService()
    result = service.chunk_document(extracted, config)

    page_numbers = {c.metadata["page_number"] for c in result.chunks}
    assert 1 not in page_numbers


def test_chunking_markdown_preserves_sections() -> None:
    """Markdown section titles flow through to chunk metadata."""

    extracted = _create_mock_extracted_document(
        format="markdown",
        pages=[
            {
                "page_number": 0,
                "raw_text": "Introduction content" * 50,
                "section_title": "Introduction",
            }
        ],
    )

    config = ChunkingConfig(strategy="sliding_window")
    service = ChunkingService()
    result = service.chunk_document(extracted, config)

    assert result.total_chunks > 0
    for chunk in result.chunks:
        assert chunk.metadata["section_title"] == "Introduction"
