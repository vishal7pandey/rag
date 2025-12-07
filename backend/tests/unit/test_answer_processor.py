from __future__ import annotations

from typing import Dict, List
from uuid import uuid4

import pytest

from backend.core.generation_models import CitationEntry, UsedChunk
from backend.core.generation_services import AnswerProcessor
from backend.core.query_models import RetrievedChunk


@pytest.mark.asyncio
async def test_process_answer_with_valid_citation() -> None:
    processor = AnswerProcessor()

    chunk_id = uuid4()
    document_id = uuid4()

    citation_map: Dict[int, Dict[str, object]] = {
        1: {
            "chunk_id": str(chunk_id),
            "document_id": str(document_id),
            "source_file": "HRPolicy.pdf",
            "page": 3,
            "similarity_score": 0.92,
        }
    }

    chunks: List[RetrievedChunk] = [
        RetrievedChunk(
            chunk_id=chunk_id,
            content="Employees may work remotely up to 3 days per week.",
            similarity_score=0.92,
            rank=1,
        )
    ]

    llm_response = "Based on policy [Source 1], remote work is allowed."

    answer, citations, used_chunks, warnings = await processor.process(
        llm_response=llm_response,
        citation_map=citation_map,
        retrieved_chunks=chunks,
    )

    assert answer == llm_response.strip()
    assert isinstance(citations[0], CitationEntry)
    assert len(citations) == 1
    assert citations[0].source_index == 1
    assert len(used_chunks) == 1
    assert isinstance(used_chunks[0], UsedChunk)
    assert warnings == []


@pytest.mark.asyncio
async def test_process_handles_invalid_citations_gracefully() -> None:
    processor = AnswerProcessor()

    llm_response = "Based on [Source 99], remote work is allowed."
    citation_map: Dict[int, Dict[str, object]] = {}
    chunks: List[RetrievedChunk] = []

    answer, citations, used_chunks, warnings = await processor.process(
        llm_response=llm_response,
        citation_map=citation_map,
        retrieved_chunks=chunks,
    )

    assert answer == llm_response.strip()
    assert citations == []
    assert used_chunks == []
    assert len(warnings) >= 1
