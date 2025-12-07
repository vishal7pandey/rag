from __future__ import annotations

from uuid import uuid4

from backend.core.prompt_models import PromptConstructionRequest
from backend.core.prompt_services import PromptAssembler
from backend.core.query_models import RetrievedChunk


def test_prompt_assembler_constructs_prompt_with_context_and_query() -> None:
    chunk = RetrievedChunk(
        chunk_id=uuid4(),
        content="Employees may work remotely up to 3 days per week.",
        similarity_score=0.95,
        rank=1,
        metadata={"source_file": "HRPolicy2025.pdf", "page": 3},
    )

    request = PromptConstructionRequest(
        request_id=uuid4(),
        query_text="What is the remote work policy?",
        retrieved_chunks=[chunk],
    )

    assembler = PromptAssembler()
    response = assembler.construct_prompt(request)

    assert response.system_message
    assert (
        "You are a helpful, accurate, and concise assistant" in response.system_message
    )

    # User message should contain both context and query sections.
    assert "---RETRIEVED CONTEXT---" in response.user_message
    assert "---USER QUERY---" in response.user_message
    assert "What is the remote work policy?" in response.user_message
    assert "[Source 1]" in response.user_message

    # Citation map and token metrics should be populated.
    assert response.citation_map
    assert 1 in response.citation_map
    assert response.token_metrics.get("context_tokens", 0) >= 0
    assert response.chunks_included == 1
    assert response.assembly_latency_ms >= 0.0
