"""Distributed trace context management for request-scoped metadata.

Story 005 introduces a lightweight tracing context based on `contextvars` so
that we can attach a correlation ID (trace ID) and related information to all
logs produced during a request lifecycle.
"""

from __future__ import annotations

import contextvars
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# Context variables for implicit propagation across the call stack
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)
span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("span_id", default="")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


@dataclass
class TraceContext:
    """Manages trace/span context for a single request.

    The context can be bound to `contextvars` so that downstream code can
    enrich logs without having to thread IDs through every function call.
    """

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)

    def duration_ms(self) -> float:
        """Return elapsed time in milliseconds since this context was created."""

        return (time.time() - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context for logging."""

        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "duration_ms": round(self.duration_ms(), 2),
        }

    def set_context_vars(self) -> None:
        """Populate global context variables for downstream logging."""

        trace_id_var.set(self.trace_id)
        span_id_var.set(self.span_id)
        if self.user_id is not None:
            user_id_var.set(self.user_id)
        if self.request_id is not None:
            request_id_var.set(self.request_id)


def get_trace_context() -> Dict[str, str]:
    """Return the current trace context snapshot from context variables."""

    return {
        "trace_id": trace_id_var.get(),
        "span_id": span_id_var.get(),
        "user_id": user_id_var.get(),
        "request_id": request_id_var.get(),
    }
