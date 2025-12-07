from __future__ import annotations

import time

import pytest

from backend.core.exceptions import QueryTimeoutError
from backend.core.guardrails import TimeoutManager


def test_timeout_manager_initialization_has_deadline() -> None:
    manager = TimeoutManager(timeout_seconds=30)

    assert manager.timeout_seconds == 30
    # Immediately after creation there should be some positive remaining time.
    assert manager.get_remaining_ms() > 0


def test_timeout_manager_tracks_elapsed_time() -> None:
    manager = TimeoutManager(timeout_seconds=5)

    elapsed_1 = manager.get_elapsed_ms()
    time.sleep(0.01)
    elapsed_2 = manager.get_elapsed_ms()

    assert elapsed_2 > elapsed_1


def test_timeout_manager_raises_when_exceeded() -> None:
    manager = TimeoutManager(timeout_seconds=1)

    time.sleep(1.1)

    with pytest.raises(QueryTimeoutError) as exc_info:
        manager.assert_time_available(min_required_seconds=0.1)

    assert exc_info.value.status_code == 408
    assert exc_info.value.error_code == "timeout"


def test_timeout_manager_remaining_time_calculation() -> None:
    manager = TimeoutManager(timeout_seconds=1)

    remaining = manager.get_remaining_ms()
    assert remaining <= 1000.0


def test_timeout_manager_assertion_with_buffer() -> None:
    manager = TimeoutManager(timeout_seconds=2)

    # Initially should have enough time.
    manager.assert_time_available(min_required_seconds=1.0)

    # Wait until close to the deadline.
    time.sleep(1.6)

    with pytest.raises(QueryTimeoutError):
        manager.assert_time_available(min_required_seconds=1.0)
