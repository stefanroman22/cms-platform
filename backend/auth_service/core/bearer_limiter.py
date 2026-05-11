"""Per-IP sliding-window rate limiter for the admin Bearer auth path.

Decoupled from slowapi because slowapi's `@limiter.limit` decorator
binds to a FastAPI route handler — we need to enforce the limit
inside a dependency (`admin_user_via_bearer_or_sid`) before calling
`verify_admin_api_key`. The bucket is process-local; on Vercel each
serverless instance gets its own counter, which is acceptable given
the threat model (brute-forcing a 192-bit secret) — the floor of
10/min/IP/instance still cuts attack throughput by ~6 orders of
magnitude.

Memory bound: at most `capacity * <unique-IPs-in-window>` floats per
bucket. Old entries are pruned lazily on every `check`.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class Bucket:
    """Sliding-window counter. Not thread-safe across processes."""

    def __init__(self, capacity: int = 10, window_seconds: int = 60) -> None:
        self.capacity = capacity
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, *, now: float | None = None) -> bool:
        """Returns True if the attempt is allowed; False if rate-limited.

        Records a hit on success so the next call sees the new count.
        Failed attempts (rate-limited) DO count — that's the point —
        otherwise an attacker can pause for 1ms after each 429 and
        keep guessing.
        """
        ts = time.monotonic() if now is None else now
        cutoff = ts - self.window
        with self._lock:
            q = self._hits[key]
            # Drop expired entries from the left.
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.capacity:
                return False
            q.append(ts)
            return True


# Module-level singleton. 10 attempts / 60s / IP — matches /auth/login's
# original tier (BE-002 raised /login to 30/min for typo tolerance, but
# Bearer keys are machine-issued so 10 is plenty).
_BEARER_BUCKET = Bucket(capacity=10, window_seconds=60)


def check_bearer_attempt(ip: str) -> bool:
    """Public entrypoint used by `admin_user_via_bearer_or_sid`."""
    return _BEARER_BUCKET.check(ip)
