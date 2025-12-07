from __future__ import annotations

import asyncio
from uuid import uuid4

from backend.config.debug_settings import DebugSettings
from backend.core.artifact_logger import ArtifactLogger
from backend.core.artifact_storage import InMemoryArtifactStorage
from backend.core.generation_models import QueryGenerationMetadata
from backend.core.query_models import RetrievedChunk


def _run(coro):
    asyncio.run(coro)


async def _drain_storage_tasks() -> None:
    # Give any background asyncio.create_task calls a chance to run.
    await asyncio.sleep(0)


def test_artifact_logger_disabled_no_logging() -> None:
    """When debug is disabled, no artifacts are stored."""

    settings = DebugSettings(enabled=False)
    storage = InMemoryArtifactStorage()
    logger = ArtifactLogger(settings, storage)

    logger.log_query_artifact(query_text="test", top_k=5)

    async def _assert_no_artifacts() -> None:
        artifacts = await storage.get_by_trace_id("any")
        assert artifacts == []

    _run(_assert_no_artifacts())


def test_artifact_logger_logs_query() -> None:
    settings = DebugSettings(enabled=True)
    storage = InMemoryArtifactStorage()
    logger = ArtifactLogger(settings, storage)

    logger.log_query_artifact(query_text="What is policy?", top_k=5, filters={"k": "v"})

    async def _assert() -> None:
        artifacts = await storage.get_by_trace_id("unknown")
        assert len(artifacts) == 1
        a = artifacts[0]["data"]
        assert a["type"] == "query"
        assert a["query_text"] == "What is policy?"
        assert a["top_k"] == 5

    _run(_assert())


def test_artifact_logger_logs_retrieved_chunks() -> None:
    settings = DebugSettings(enabled=True, include_chunk_content=True)
    storage = InMemoryArtifactStorage()
    logger = ArtifactLogger(settings, storage)

    chunk = RetrievedChunk(
        chunk_id=uuid4(),
        content="Policy text here",
        similarity_score=0.95,
        rank=1,
        metadata={"source_file": "policy.pdf", "page": 1},
    )

    logger.log_retrieved_chunks_artifact(chunks=[chunk], retrieval_latency_ms=150.0)

    async def _assert() -> None:
        artifacts = await storage.get_by_trace_id("unknown")
        assert len(artifacts) == 1
        a = artifacts[0]["data"]
        assert a["type"] == "retrieved_chunks"
        assert a["chunks_count"] == 1
        assert a["chunks_data"][0]["content"] == "Policy text here"

    _run(_assert())


def test_artifact_logger_logs_prompt() -> None:
    settings = DebugSettings(enabled=True, include_prompt_details=True)
    storage = InMemoryArtifactStorage()
    logger = ArtifactLogger(settings, storage)

    logger.log_prompt_artifact(
        system_message="You are a helpful assistant",
        user_message="What is the policy?",
        token_breakdown={
            "system_tokens": 10,
            "context_tokens": 500,
            "response_tokens": 1000,
        },
        citation_map={"1": "source.pdf"},
    )

    async def _assert() -> None:
        artifacts = await storage.get_by_trace_id("unknown")
        assert len(artifacts) == 1
        a = artifacts[0]["data"]
        assert a["type"] == "prompt"
        assert a["system_prompt_tokens"] == 10
        assert a["context_tokens"] == 500
        assert a["response_tokens"] == 1000
        assert a["system_message"] == "You are a helpful assistant"

    _run(_assert())


def test_artifact_logger_logs_answer() -> None:
    settings = DebugSettings(enabled=True, include_llm_raw_output=True)
    storage = InMemoryArtifactStorage()
    logger = ArtifactLogger(settings, storage)

    logger.log_answer_artifact(
        answer_text="The policy states...",
        raw_llm_output='{"text": "The policy states..."}',
        generation_latency_ms=1500.0,
        model="gpt-5-nano",
        token_usage={"answer_tokens": 150, "prompt_tokens": 500, "total_tokens": 650},
    )

    async def _assert() -> None:
        artifacts = await storage.get_by_trace_id("unknown")
        assert len(artifacts) == 1
        a = artifacts[0]["data"]
        assert a["type"] == "answer"
        assert a["model"] == "gpt-5-nano"
        assert a["generation_latency_ms"] == 1500.0
        assert a["answer_tokens"] == 150
        assert a["raw_llm_output"] == '{"text": "The policy states..."}'

    _run(_assert())


def test_artifact_logger_logs_response() -> None:
    settings = DebugSettings(enabled=True)
    storage = InMemoryArtifactStorage()
    logger = ArtifactLogger(settings, storage)

    metadata = QueryGenerationMetadata(
        total_latency_ms=2000.0,
        embedding_latency_ms=250.0,
        retrieval_latency_ms=400.0,
        prompt_assembly_latency_ms=150.0,
        generation_latency_ms=1200.0,
        answer_processing_latency_ms=0.0,
        total_tokens_used=100,
        model="gpt-5-nano",
        chunks_retrieved=5,
    )

    logger.log_response_artifact(
        answer="The policy states...",
        citations=[],
        used_chunks=[],
        metadata=metadata,
    )

    async def _assert() -> None:
        artifacts = await storage.get_by_trace_id("unknown")
        assert len(artifacts) == 1
        a = artifacts[0]["data"]
        assert a["type"] == "response"
        assert a["model"] == "gpt-5-nano"
        assert a["total_latency_ms"] == 2000.0
        assert a["metadata"]["embedding_latency_ms"] == 250.0

    _run(_assert())
