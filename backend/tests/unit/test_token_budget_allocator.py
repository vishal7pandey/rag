from __future__ import annotations

import pytest

from backend.core.prompt_services import TokenBudgetAllocator


def test_allocate_budget_simple() -> None:
    allocator = TokenBudgetAllocator()
    budget = allocator.allocate(
        system_tokens=500,
        query_tokens=100,
        response_budget=1500,
        model="gpt-5-nano",
    )

    assert budget["system_prompt"] == 500
    assert budget["query"] == 100
    assert budget["response_reserved"] == 1500
    assert budget["available_for_context"] > 0
    assert (
        budget["available_for_context"]
        + budget["system_prompt"]
        + budget["query"]
        + budget["response_reserved"]
        <= budget["context_window"]
    )


def test_allocate_with_history_and_examples_reduces_context_budget() -> None:
    allocator = TokenBudgetAllocator()

    base_budget = allocator.allocate(
        system_tokens=500,
        query_tokens=100,
        response_budget=1500,
        model="gpt-5-nano",
    )

    budget = allocator.allocate(
        system_tokens=500,
        query_tokens=100,
        history_tokens=1000,
        examples_tokens=500,
        response_budget=1500,
        model="gpt-5-nano",
    )

    assert budget["available_for_context"] < base_budget["available_for_context"]
    assert (
        budget["available_for_context"]
        == base_budget["available_for_context"] - 1000 - 500
    )


def test_allocate_budget_exceeds_context_window_raises() -> None:
    allocator = TokenBudgetAllocator()

    with pytest.raises(ValueError):
        allocator.allocate(
            system_tokens=100_000,
            query_tokens=50_000,
            response_budget=50_000,
            model="gpt-5-nano",
        )
