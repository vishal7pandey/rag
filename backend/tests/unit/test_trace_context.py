import time

from backend.core.tracing import TraceContext


def test_trace_context_generates_id_if_not_provided() -> None:
    ctx = TraceContext()
    assert ctx.trace_id is not None
    assert len(ctx.trace_id) > 0


def test_trace_context_uses_provided_id() -> None:
    provided_id = "550e8400-e29b-41d4-a716-446655440000"
    ctx = TraceContext(trace_id=provided_id)
    assert ctx.trace_id == provided_id


def test_trace_context_duration_ms_increases() -> None:
    ctx = TraceContext()
    time.sleep(0.01)
    duration = ctx.duration_ms()
    assert duration >= 10


def test_trace_context_preserves_user_id() -> None:
    ctx = TraceContext(user_id="user-123")
    assert ctx.user_id == "user-123"
