"""Simple in-memory rate limiter for file uploads.

Implements a per-user sliding-window rate limit as described in Story 006.
This is suitable for development and testing; production deployments can
swap this out for a Redis-backed implementation.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import DefaultDict, List, Optional, Tuple


class RateLimiter:
    """Simple in-memory rate limiter.

    Tracks request timestamps per user and enforces a maximum number of
    actions within a given window.
    """

    def __init__(self) -> None:
        self.user_requests: DefaultDict[str, List[datetime]] = defaultdict(list)

    def is_allowed(
        self,
        user_id: str,
        limit: int = 100,
        window_seconds: int = 3600,
    ) -> Tuple[bool, Optional[int]]:
        """Return (is_allowed, retry_after_seconds).

        If the user is within their limit, returns (True, None) and records
        the current request timestamp. If the limit is exceeded, returns
        (False, retry_after_seconds) where retry_after_seconds indicates how
        long the caller should wait before retrying.
        """

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)

        # Drop timestamps outside the window.
        self.user_requests[user_id] = [
            ts for ts in self.user_requests[user_id] if ts > window_start
        ]

        if len(self.user_requests[user_id]) < limit:
            self.user_requests[user_id].append(now)
            return True, None

        # At limit: compute how long until the oldest entry falls out of window.
        oldest_request = self.user_requests[user_id][0]
        retry_after = int((oldest_request - window_start).total_seconds()) + 1
        return False, retry_after
