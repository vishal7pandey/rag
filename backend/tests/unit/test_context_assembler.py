from __future__ import annotations

from uuid import uuid4

import pytest

from backend.core.prompt_services import (
    CitationFormatter,
    ContextAssembler,
    TokenCounter,
)
from backend.core.query_models import RetrievedChunk


@pytest.mark.parametrize("available_tokens", [50, 200])
def test_context_assembler_respects_budget(available_tokens: int) -> None:
    counter = TokenCounter()
    assembler = ContextAssembler()
    formatter = CitationFormatter()

    chunks = [
        RetrievedChunk(
            chunk_id=uuid4(),
            content="Chunk 1 content " * 20,
            similarity_score=0.9,
            rank=1,
            metadata={"source_file": "doc1.pdf"},
        ),
        RetrievedChunk(
            chunk_id=uuid4(),
            content="Chunk 2 content " * 20,
            similarity_score=0.8,
            rank=2,
            metadata={"source_file": "doc2.pdf"},
        ),
    ]

    context, used_indices, metrics = assembler.assemble(
        chunks=chunks,
        available_tokens=available_tokens,
        token_counter=counter,
        citation_formatter=formatter,
    )

    context_tokens = counter.count(context)
    assert context_tokens <= available_tokens + 10
    assert metrics["chunks_included"] >= 0
    assert len(used_indices) == metrics["chunks_included"]


def test_context_assembler_truncates_when_over_budget() -> None:
    counter = TokenCounter()
    assembler = ContextAssembler()
    formatter = CitationFormatter()

    chunks = [
        RetrievedChunk(
            chunk_id=uuid4(),
            content="X " * 500,
            similarity_score=0.9,
            rank=1,
            metadata={"source_file": "doc1.pdf"},
        ),
    ]

    context, used_indices, metrics = assembler.assemble(
        chunks=chunks,
        available_tokens=50,
        token_counter=counter,
        citation_formatter=formatter,
    )

    assert context
    assert "[...]" in context or metrics["chunks_truncated"] >= 1
    assert metrics["chunks_included"] == 1
    assert metrics["chunks_truncated"] >= 0


def test_context_assembler_orders_by_rank() -> None:
    counter = TokenCounter()
    assembler = ContextAssembler()
    formatter = CitationFormatter()

    chunks = [
        RetrievedChunk(
            chunk_id=uuid4(),
            content="Low rank content",
            similarity_score=0.5,
            rank=2,
            metadata={"source_file": "doc2.pdf"},
        ),
        RetrievedChunk(
            chunk_id=uuid4(),
            content="High rank content",
            similarity_score=0.95,
            rank=1,
            metadata={"source_file": "doc1.pdf"},
        ),
    ]

    context, used_indices, _ = assembler.assemble(
        chunks=chunks,
        available_tokens=500,
        token_counter=counter,
        citation_formatter=formatter,
    )

    assert "High rank content" in context
    assert "Low rank content" in context
    high_idx = context.index("High rank content")
    low_idx = context.index("Low rank content")
    assert high_idx < low_idx
