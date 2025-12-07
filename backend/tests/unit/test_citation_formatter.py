from __future__ import annotations

from uuid import uuid4

from backend.core.prompt_services import CitationFormatter
from backend.core.query_models import RetrievedChunk


def test_format_chunk_with_citation_includes_source_marker() -> None:
    formatter = CitationFormatter()
    chunk = RetrievedChunk(
        chunk_id=uuid4(),
        content="Policy states: remote work allowed 3 days/week",
        similarity_score=0.92,
        rank=1,
        metadata={
            "source_file": "HRPolicy2025.pdf",
            "page": 3,
            "section": "Remote Work",
        },
    )

    formatted = formatter.format_chunk(chunk, citation_index=1)

    assert "[Source 1]" in formatted
    assert "HRPolicy2025.pdf" in formatted
    assert "Page 3" in formatted
    assert "Remote Work" in formatted


def test_build_citation_map_uses_chunk_metadata() -> None:
    formatter = CitationFormatter()
    chunk = RetrievedChunk(
        chunk_id=uuid4(),
        content="Example",
        similarity_score=0.9,
        rank=1,
        metadata={"source_file": "doc.pdf", "page": 2},
    )

    citation_map = formatter.build_citation_map([chunk], [1])

    assert 1 in citation_map
    entry = citation_map[1]
    assert entry["chunk_id"] == str(chunk.chunk_id)
    assert entry["source_file"] == "doc.pdf"
    assert entry["page"] == 2
