"""Unit tests for the bearer-path token bucket.

Decoupled from slowapi so the bucket is testable without standing up
a FastAPI app. Clock is injectable via the `now` parameter to avoid
sleep-based tests.
"""

from auth_service.core import bearer_limiter


def test_first_ten_attempts_pass():
    bucket = bearer_limiter.Bucket(capacity=10, window_seconds=60)
    for i in range(10):
        assert bucket.check("203.0.113.5", now=1000.0 + i) is True


def test_eleventh_attempt_blocks():
    bucket = bearer_limiter.Bucket(capacity=10, window_seconds=60)
    for i in range(10):
        bucket.check("203.0.113.5", now=1000.0 + i)
    assert bucket.check("203.0.113.5", now=1010.0) is False


def test_window_resets_after_60s():
    bucket = bearer_limiter.Bucket(capacity=10, window_seconds=60)
    for i in range(10):
        bucket.check("203.0.113.5", now=1000.0 + i)
    # 61s later → first slot has expired, attempt allowed.
    assert bucket.check("203.0.113.5", now=1061.5) is True


def test_per_ip_isolation():
    bucket = bearer_limiter.Bucket(capacity=10, window_seconds=60)
    for i in range(10):
        bucket.check("203.0.113.5", now=1000.0 + i)
    # Different IP — fresh quota.
    assert bucket.check("203.0.113.99", now=1010.0) is True
