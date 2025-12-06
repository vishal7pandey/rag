"""Simple test script for OpenAI embedding and generation.

Runs a small end-to-end check of embeddings, generation, and streaming and
prints latency metrics. Intended for manual verification.
"""

from __future__ import annotations

import os
import sys
import time

from backend.providers.openai_client import (
    OpenAIEmbeddingClient,
    OpenAIGenerationClient,
)


def test_embedding_and_generation() -> None:
    """Test embedding and generation with latency logging."""

    print("=" * 60)
    print("OpenAI Provider Test")
    print("=" * 60)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not set")
        sys.exit(1)

    print(f"✅ API key configured: {api_key[:10]}...")
    print()

    # Test 1: Embedding
    print("Test 1: Embedding Generation")
    print("-" * 60)

    embedding_client = OpenAIEmbeddingClient(api_key=api_key)
    test_text = "This is a test document for RAG system embedding."

    start = time.time()
    embedding_result = embedding_client.embed(test_text)
    embedding_time = time.time() - start

    print(f"✅ Model: {embedding_result['model']}")
    print(f"✅ Dimensions: {len(embedding_result['embedding'])}")
    print(f"✅ Tokens used: {embedding_result['usage']['total_tokens']}")
    print(f"✅ Latency: {embedding_time * 1000:.2f}ms")
    print(f"✅ First 5 dims: {embedding_result['embedding'][:5]}")
    print()

    # Test 2: Generation
    print("Test 2: Chat Generation")
    print("-" * 60)

    generation_client = OpenAIGenerationClient(api_key=api_key)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": "What is retrieval-augmented generation in one sentence?",
        },
    ]

    start = time.time()
    generation_result = generation_client.generate(messages, max_tokens=100)
    generation_time = time.time() - start

    print(f"✅ Model: {generation_result['model']}")
    print(f"✅ Response: {generation_result['content']}")
    print(f"✅ Tokens used: {generation_result['usage']['total_tokens']}")
    print(f"✅ Latency: {generation_time * 1000:.2f}ms")
    print(f"✅ Finish reason: {generation_result['finish_reason']}")
    print()

    # Test 3: Streaming
    print("Test 3: Streaming Generation")
    print("-" * 60)

    print("Response: ", end="", flush=True)
    start = time.time()

    for chunk in generation_client.generate_stream(messages, max_tokens=50):
        print(chunk, end="", flush=True)

    stream_time = time.time() - start
    print()
    print(f"✅ Streaming latency: {stream_time * 1000:.2f}ms")
    print()

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(
        f"✅ Embedding: text-embedding-3-small working ({embedding_time * 1000:.0f}ms)"
    )
    print(f"✅ Generation: gpt-5-nano working ({generation_time * 1000:.0f}ms)")
    print(f"✅ Streaming: enabled ({stream_time * 1000:.0f}ms)")
    print()
    print("✅ All tests passed!")


if __name__ == "__main__":
    test_embedding_and_generation()
