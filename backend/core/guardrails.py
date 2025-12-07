from __future__ import annotations

import contextvars
import re
import time
from typing import Any, Dict, List, Optional, Pattern

from backend.core.exceptions import QueryTimeoutError, ValidationError
from backend.core.logging import get_logger
from backend.core.tracing import get_trace_context


class InputValidator:
    """Basic input validation for query requests (Story 015).

    This validator enforces simple guardrails on the public /api/query payload
    before the expensive RAG pipeline runs.
    """

    MAX_QUERY_LENGTH: int = 5000
    MIN_QUERY_LENGTH: int = 1
    TOP_K_MIN: int = 1
    TOP_K_MAX: int = 100

    # Minimal placeholder patterns for "forbidden" content. These are intentionally
    # conservative to avoid over-filtering; they mainly exist so the wiring is in
    # place for future expansion.
    FORBIDDEN_PATTERNS: List[Pattern[str]] = [
        re.compile(r"__FORBIDDEN__", re.IGNORECASE),
    ]

    def validate_query_text(
        self,
        query: str,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Validate the user query text.

        Raises ValidationError when the query is empty, too long, or matches a
        forbidden pattern.
        """

        if not query or not query.strip():
            raise ValidationError(
                message="Query cannot be empty",
                validation_field="query",
            )

        if len(query) > self.MAX_QUERY_LENGTH:
            raise ValidationError(
                message=(
                    f"Query exceeds maximum length of {self.MAX_QUERY_LENGTH} characters"
                ),
                validation_field="query",
            )

        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern.search(query):
                raise ValidationError(
                    message="Query contains forbidden content",
                    validation_field="query",
                )

    def validate_top_k(
        self,
        top_k: int,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Validate the top_k parameter.

        Raises ValidationError when top_k is outside the allowed range.
        """

        if top_k < self.TOP_K_MIN or top_k > self.TOP_K_MAX:
            raise ValidationError(
                message=(
                    f"top_k must be between {self.TOP_K_MIN} and {self.TOP_K_MAX}"
                ),
                validation_field="top_k",
                details={"top_k": top_k, "min": self.TOP_K_MIN, "max": self.TOP_K_MAX},
            )

    def validate_request(
        self,
        query: str,
        top_k: int,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Validate the combination of query text and top_k."""

        self.validate_query_text(query, trace_context=trace_context)
        self.validate_top_k(top_k, trace_context=trace_context)


class TimeoutManager:
    """Manage a global query timeout across RAG pipeline stages.

    This is a lightweight helper that tracks a start time and deadline. It is
    intentionally simple and does not yet integrate deeply with asyncio
    cancellation; instead, it provides explicit checks via assert_time_available
    that can be invoked before each major stage.
    """

    _deadline_var: contextvars.ContextVar[float] = contextvars.ContextVar(
        "timeout_deadline", default=0.0
    )

    def __init__(self, timeout_seconds: int = 30) -> None:
        # Clamp to a reasonable range to avoid misconfiguration.
        timeout_seconds = max(1, min(timeout_seconds, 120))
        self.timeout_seconds: int = timeout_seconds
        self.start_time: float = time.time()
        self.deadline: float = self.start_time + float(timeout_seconds)
        self._deadline_var.set(self.deadline)

        logger = get_logger("rag.core.timeout")
        logger.info(
            "timeout_manager_started",
            extra={
                "context": {
                    "timeout_seconds": self.timeout_seconds,
                    "deadline_ts": self.deadline,
                    "trace": get_trace_context(),
                }
            },
        )

    def get_elapsed_ms(self) -> float:
        """Return elapsed time since creation in milliseconds."""

        return (time.time() - self.start_time) * 1000.0

    def get_remaining_ms(self) -> float:
        """Return remaining time before deadline in milliseconds (may be negative)."""

        return (self.deadline - time.time()) * 1000.0

    def assert_time_available(
        self,
        min_required_seconds: float = 1.0,
        stage_name: str | None = None,
        stages_completed: int = 0,
    ) -> None:
        """Raise QueryTimeoutError if not enough time remains.

        The min_required_seconds buffer ensures that a stage does not start if
        there is almost no time left in the global budget.
        """

        remaining_seconds = self.deadline - time.time()
        if remaining_seconds < min_required_seconds:
            elapsed_ms = self.get_elapsed_ms()
            logger = get_logger("rag.core.timeout")
            logger.warning(
                "timeout_exceeded_before_stage",
                extra={
                    "context": {
                        "timeout_seconds": self.timeout_seconds,
                        "elapsed_ms": elapsed_ms,
                        "remaining_seconds": remaining_seconds,
                        "stage": stage_name,
                        "stages_completed": stages_completed,
                        "trace": get_trace_context(),
                    }
                },
            )
            raise QueryTimeoutError(
                message="Query execution exceeded the configured timeout.",
                timeout_seconds=self.timeout_seconds,
                elapsed_ms=elapsed_ms,
                stages_completed=stages_completed,
            )

    def check_remaining_time(self) -> float:
        """Return remaining time in seconds before the timeout deadline."""

        return self.deadline - time.time()

    def log_stage_timing(self, stage_name: str, stage_latency_ms: float) -> None:
        """Log timing information for an individual pipeline stage."""

        logger = get_logger("rag.core.timeout")
        logger.info(
            "stage_complete",
            extra={
                "context": {
                    "stage": stage_name,
                    "latency_ms": stage_latency_ms,
                    "elapsed_ms": self.get_elapsed_ms(),
                    "timeout_seconds": self.timeout_seconds,
                    "trace": get_trace_context(),
                }
            },
        )
