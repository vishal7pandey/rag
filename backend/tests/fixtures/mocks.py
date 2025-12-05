"""Test doubles and mocks for backend API tests.

These are lightweight fakes used in Story 002 to illustrate where more
sophisticated service-layer mocks will live in later stories.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class FakeIngestionService:
    """Very small fake of an ingestion service.

    This does not implement real ingestion logic; it exists as a placeholder so
    tests and future stories have a clear location for service mocks.
    """

    calls: List[Dict] | None = None

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def enqueue(self, *, document_path: str, metadata: Dict | None = None) -> str:
        """Record an enqueue call and return a fake task id."""

        task_id = f"task-{len(self.calls) + 1}"
        self.calls.append(
            {
                "task_id": task_id,
                "document_path": document_path,
                "metadata": metadata or {},
            }
        )
        return task_id
