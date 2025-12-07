from __future__ import annotations

import asyncio

from backend.core.artifact_storage import InMemoryArtifactStorage


def test_in_memory_artifact_storage_store_and_get_by_trace_id() -> None:
    """Artifacts for a trace_id are stored and retrievable in order."""

    storage = InMemoryArtifactStorage()

    async def _run() -> None:
        await storage.store("trace-1", "query", {"q": "one"})
        await storage.store("trace-1", "answer", {"a": "two"})

        artifacts = await storage.get_by_trace_id("trace-1")
        assert len(artifacts) == 2
        assert artifacts[0]["type"] == "query"
        assert artifacts[0]["data"]["q"] == "one"
        assert artifacts[1]["type"] == "answer"
        assert artifacts[1]["data"]["a"] == "two"

    asyncio.run(_run())
