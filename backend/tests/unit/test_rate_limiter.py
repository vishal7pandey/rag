from backend.core.rate_limiter import RateLimiter


def test_rate_limiter_allows_within_limit() -> None:
    limiter = RateLimiter()

    is_allowed, retry_after = limiter.is_allowed("user-1", limit=3, window_seconds=60)

    assert is_allowed
    assert retry_after is None


def test_rate_limiter_blocks_over_limit() -> None:
    limiter = RateLimiter()

    # Fill quota
    for _ in range(3):
        allowed, _ = limiter.is_allowed("user-2", limit=3, window_seconds=60)
        assert allowed

    # Next request should be blocked
    is_allowed, retry_after = limiter.is_allowed("user-2", limit=3, window_seconds=60)

    assert not is_allowed
    assert retry_after is not None
    assert retry_after > 0
