"""Unit tests for services/solver_dispatch.py."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from auth_service.services import solver_dispatch
from auth_service.services.solver_dispatch import SolverDispatchError, dispatch_solver_tick


def _fake_response(status: int = 204, body: bytes = b""):
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: None
    return resp


def test_dispatch_posts_to_correct_url_with_payload(monkeypatch):
    monkeypatch.setenv("SOLVER_DISPATCH_TOKEN", "secret-token")
    monkeypatch.setenv("SOLVER_DISPATCH_REPO", "stefanroman22/cms-platform")

    captured: dict = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode())
        captured["timeout"] = timeout
        return _fake_response(204)

    with patch.object(solver_dispatch.urllib.request, "urlopen", fake_urlopen):
        dispatch_solver_tick(issue_id="issue-42")

    assert captured["url"] == "https://api.github.com/repos/stefanroman22/cms-platform/dispatches"
    assert captured["method"] == "POST"
    # Header lookup is case-insensitive in HTTP but urllib stores titlecase keys.
    headers_lower = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers_lower["authorization"] == "Bearer secret-token"
    assert headers_lower["accept"] == "application/vnd.github+json"
    assert headers_lower["content-type"] == "application/json"
    assert captured["body"] == {
        "event_type": "solver-tick",
        "client_payload": {"issue_id": "issue-42", "trigger": "issue_created"},
    }
    assert captured["timeout"] == 5


def test_dispatch_without_issue_id_omits_client_payload(monkeypatch):
    monkeypatch.setenv("SOLVER_DISPATCH_TOKEN", "t")
    captured: dict = {}

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode())
        return _fake_response(204)

    with patch.object(solver_dispatch.urllib.request, "urlopen", fake_urlopen):
        dispatch_solver_tick()

    assert captured["body"] == {"event_type": "solver-tick"}


def test_dispatch_missing_token_raises(monkeypatch):
    monkeypatch.delenv("SOLVER_DISPATCH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(SolverDispatchError, match="Neither SOLVER_DISPATCH_TOKEN nor GITHUB_TOKEN"):
        dispatch_solver_tick(issue_id="x")


def test_dispatch_falls_back_to_github_token(monkeypatch):
    """When SOLVER_DISPATCH_TOKEN is unset, dispatch reuses GITHUB_TOKEN."""
    monkeypatch.delenv("SOLVER_DISPATCH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "fallback-token")

    captured: dict = {}

    def fake_urlopen(req, timeout):
        captured["auth"] = dict(req.header_items())["Authorization"]
        return _fake_response(204)

    with patch.object(solver_dispatch.urllib.request, "urlopen", fake_urlopen):
        dispatch_solver_tick(issue_id="x")

    assert captured["auth"] == "Bearer fallback-token"


def test_dispatch_prefers_solver_token_over_github_token(monkeypatch):
    """If both are set, SOLVER_DISPATCH_TOKEN wins."""
    monkeypatch.setenv("SOLVER_DISPATCH_TOKEN", "primary")
    monkeypatch.setenv("GITHUB_TOKEN", "fallback")

    captured: dict = {}

    def fake_urlopen(req, timeout):
        captured["auth"] = dict(req.header_items())["Authorization"]
        return _fake_response(204)

    with patch.object(solver_dispatch.urllib.request, "urlopen", fake_urlopen):
        dispatch_solver_tick(issue_id="x")

    assert captured["auth"] == "Bearer primary"


def test_dispatch_http_error_raises(monkeypatch):
    monkeypatch.setenv("SOLVER_DISPATCH_TOKEN", "t")

    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url,
            401,
            "Unauthorized",
            {},
            MagicMock(read=lambda: b'{"message":"Bad credentials"}'),
        )

    with patch.object(solver_dispatch.urllib.request, "urlopen", fake_urlopen):
        with pytest.raises(SolverDispatchError, match="GitHub 401"):
            dispatch_solver_tick(issue_id="x")


def test_dispatch_server_error_raises(monkeypatch):
    monkeypatch.setenv("SOLVER_DISPATCH_TOKEN", "t")

    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url, 502, "Bad Gateway", {}, MagicMock(read=lambda: b"down")
        )

    with patch.object(solver_dispatch.urllib.request, "urlopen", fake_urlopen):
        with pytest.raises(SolverDispatchError, match="GitHub 502"):
            dispatch_solver_tick(issue_id="x")


def test_dispatch_url_error_raises(monkeypatch):
    monkeypatch.setenv("SOLVER_DISPATCH_TOKEN", "t")

    def fake_urlopen(req, timeout):
        raise urllib.error.URLError("connection refused")

    with patch.object(solver_dispatch.urllib.request, "urlopen", fake_urlopen):
        with pytest.raises(SolverDispatchError, match="Network error"):
            dispatch_solver_tick(issue_id="x")


def test_dispatch_uses_overridable_repo(monkeypatch):
    monkeypatch.setenv("SOLVER_DISPATCH_TOKEN", "t")
    monkeypatch.setenv("SOLVER_DISPATCH_REPO", "someone/other-repo")
    captured: dict = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        return _fake_response(204)

    with patch.object(solver_dispatch.urllib.request, "urlopen", fake_urlopen):
        dispatch_solver_tick(issue_id="x")

    assert captured["url"] == "https://api.github.com/repos/someone/other-repo/dispatches"
