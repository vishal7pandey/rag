from __future__ import annotations

from backend.core.prompt_services import TokenCounter


def test_count_tokens_simple() -> None:
    counter = TokenCounter(model="gpt-5-nano")
    text = "Hello world"
    tokens = counter.count(text)

    assert tokens >= 1
    assert tokens <= 10


def test_count_tokens_batch_matches_individual() -> None:
    counter = TokenCounter()
    texts = ["Hello", "world", "test"]

    single_counts = [counter.count(t) for t in texts]
    batch_counts = counter.count_batch(texts)

    assert single_counts == batch_counts


def test_count_tokens_with_special_characters() -> None:
    counter = TokenCounter()
    text = "[Source 1] File: policy.pdf, Page 3"

    tokens = counter.count(text)

    assert tokens > 0
