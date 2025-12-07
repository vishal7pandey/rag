from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

from backend.core.generation_services import CitationValidator
from backend.core.query_models import RetrievedChunk


def _make_chunk_and_map() -> tuple[Dict[int, Dict[str, Any]], List[RetrievedChunk]]:
    chunk_id = uuid4()
    document_id = uuid4()

    citation_map: Dict[int, Dict[str, Any]] = {
        1: {
            "chunk_id": str(chunk_id),
            "document_id": str(document_id),
            "source_file": "policy.pdf",
            "page": 3,
            "similarity_score": 0.92,
        }
    }

    chunks = [
        RetrievedChunk(
            chunk_id=chunk_id,
            content="Employees may work remotely...",
            similarity_score=0.92,
            rank=1,
            metadata={"source_file": "policy.pdf", "page": 3},
        )
    ]

    return citation_map, chunks


def test_validate_valid_citation() -> None:
    validator = CitationValidator()
    citation_map, chunks = _make_chunk_and_map()
    extracted = {1: [(0, 9)]}

    citations, warnings = validator.validate(
        extracted_citations=extracted,
        citation_map=citation_map,
        retrieved_chunks=chunks,
    )

    assert len(citations) == 1
    entry = citations[0]
    assert entry.source_index == 1
    assert entry.source_file == "policy.pdf"
    assert entry.page == 3
    assert entry.similarity_score == 0.92
    assert len(entry.preview) > 0
    assert warnings == []


def test_validate_missing_citation_adds_warning() -> None:
    validator = CitationValidator()
    citation_map, chunks = _make_chunk_and_map()
    # Extracted includes a citation index that is not in the map.
    extracted = {1: [(0, 9)], 2: [(50, 59)]}

    citations, warnings = validator.validate(
        extracted_citations=extracted,
        citation_map=citation_map,
        retrieved_chunks=chunks,
    )

    # Only the valid citation is included.
    assert len(citations) == 1
    assert any("Source 2" in w for w in warnings)


def test_validate_handles_empty_inputs() -> None:
    validator = CitationValidator()

    citations, warnings = validator.validate(
        extracted_citations={},
        citation_map={},
        retrieved_chunks=[],
    )

    assert citations == []
    assert warnings == []
