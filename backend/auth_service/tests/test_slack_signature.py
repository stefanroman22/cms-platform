"""HMAC verification for Slack Events API requests."""

from __future__ import annotations

import hashlib
import hmac
import time

from ..services import slack_signature


def _sign(body: bytes, timestamp: str, secret: str) -> str:
    base = f"v0:{timestamp}:{body.decode()}".encode()
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


def test_valid_signature_returns_true():
    secret = "abc123"
    body = b'{"event":"x"}'
    ts = str(int(time.time()))
    sig = _sign(body, ts, secret)
    assert slack_signature.verify(ts, body, sig, secret) is True


def test_wrong_signature_returns_false():
    secret = "abc123"
    body = b'{"event":"x"}'
    ts = str(int(time.time()))
    assert slack_signature.verify(ts, body, "v0=deadbeef", secret) is False


def test_expired_timestamp_returns_false():
    secret = "abc123"
    body = b'{"event":"x"}'
    old_ts = str(int(time.time()) - 400)  # 400s old > 300s window
    sig = _sign(body, old_ts, secret)
    assert slack_signature.verify(old_ts, body, sig, secret) is False


def test_missing_timestamp_returns_false():
    assert slack_signature.verify("", b"x", "v0=x", "secret") is False


def test_missing_signature_returns_false():
    assert slack_signature.verify(str(int(time.time())), b"x", "", "secret") is False


def test_non_numeric_timestamp_returns_false():
    assert slack_signature.verify("not-a-number", b"x", "v0=x", "secret") is False
