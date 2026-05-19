"""Tests for backend_api.py — HTTP client to the cms-platform admin endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import backend_api
import pytest


@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    monkeypatch.setenv("CMS_BACKEND_URL", "https://api.example.com")
    monkeypatch.setenv("CMS_API_TOKEN", "test-token")


def test_notify_agent_event_posts_to_correct_url(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = lambda: None
        resp.json = lambda: {"posted_ts": "ts-1"}
        return resp

    monkeypatch.setattr(backend_api.requests, "post", fake_post)

    backend_api.notify_agent_event("issue-77", kind="rejected", reason="already fixed")
    assert captured["url"] == "https://api.example.com/admin/issues/issue-77/agent-event"
    assert captured["json"] == {"kind": "rejected", "reason": "already fixed"}


def test_notify_agent_event_swallows_errors(monkeypatch):
    """Best-effort — log on failure, do not raise."""

    def boom(*a, **kw):
        raise ConnectionError("network down")

    monkeypatch.setattr(backend_api.requests, "post", boom)
    # Must not raise.
    backend_api.notify_agent_event("issue-77", kind="rejected", reason="x")


def test_trigger_issue_resolved_retries_on_5xx(monkeypatch):
    attempts = {"count": 0}

    def fake_patch(url, headers=None, json=None, timeout=None):
        attempts["count"] += 1
        resp = MagicMock()
        if attempts["count"] < 3:
            resp.status_code = 503

            def raise_503():
                from requests.exceptions import HTTPError

                err = HTTPError("503")
                err.response = resp
                raise err

            resp.raise_for_status = raise_503
        else:
            resp.status_code = 200
            resp.raise_for_status = lambda: None
            resp.json = lambda: {"ok": True}
        return resp

    monkeypatch.setattr(backend_api.requests, "patch", fake_patch)
    monkeypatch.setattr(backend_api.time, "sleep", lambda s: None)  # skip real delay

    result = backend_api.trigger_issue_resolved("issue-77")
    assert attempts["count"] == 3  # 2 failures + 1 success
    assert result == {"ok": True}


def test_trigger_issue_resolved_raises_after_max_retries(monkeypatch):
    def always_503(url, headers=None, json=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 503

        def raise_503():
            from requests.exceptions import HTTPError

            err = HTTPError("503")
            err.response = resp
            raise err

        resp.raise_for_status = raise_503
        return resp

    monkeypatch.setattr(backend_api.requests, "patch", always_503)
    monkeypatch.setattr(backend_api.time, "sleep", lambda s: None)

    from requests.exceptions import HTTPError

    with pytest.raises(HTTPError):
        backend_api.trigger_issue_resolved("issue-77")


def test_trigger_issue_resolved_does_not_retry_on_4xx(monkeypatch):
    attempts = {"count": 0}

    def fake_patch(url, headers=None, json=None, timeout=None):
        attempts["count"] += 1
        resp = MagicMock()
        resp.status_code = 401

        def raise_401():
            from requests.exceptions import HTTPError

            err = HTTPError("401")
            err.response = resp
            raise err

        resp.raise_for_status = raise_401
        return resp

    monkeypatch.setattr(backend_api.requests, "patch", fake_patch)

    from requests.exceptions import HTTPError

    with pytest.raises(HTTPError):
        backend_api.trigger_issue_resolved("issue-77")
    assert attempts["count"] == 1  # NOT retried


def test_post_thread_event_direct_posts_to_slack(monkeypatch):
    import slack as slack_client

    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    captured = {}

    class FakeResp:
        @staticmethod
        def json():
            return {"ok": True, "ts": "ts-direct"}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(slack_client.requests, "post", fake_post)

    slack_client.post_thread_event_direct(
        thread_ts="ts-original",
        kind="backend_error",
        reason="trigger_issue_resolved failed after 3 retries",
    )
    assert captured["url"] == "https://slack.com/api/chat.postMessage"
    assert captured["json"]["thread_ts"] == "ts-original"
    assert captured["json"]["channel"] == "C123"
    assert "🛑" in captured["json"]["text"]


def test_post_thread_event_direct_disabled_silently(monkeypatch):
    import slack as slack_client

    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ISSUES_CHANNEL_ID", raising=False)

    # Should not raise — disabled mode just logs.
    slack_client.post_thread_event_direct(thread_ts="x", kind="backend_error", reason="y")
