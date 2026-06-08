"""GitHub API fast-forward unit tests."""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from unittest.mock import patch

import pytest

from ..services import github_merge


class _FakeResp:
    def __init__(self, payload: dict):
        self._buf = BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self) -> bytes:
        return self._buf.read()


def test_fast_forward_happy_path(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    calls = []

    def fake_urlopen(req, timeout=10):
        url = req.full_url if hasattr(req, "full_url") else req
        method = getattr(req, "method", None) or "GET"
        calls.append((method, url, getattr(req, "data", None)))
        if "git/refs/heads/cms-preview" in url:
            return _FakeResp({"object": {"sha": "abc123def456"}})
        if "git/refs/heads/master" in url:
            return _FakeResp({"ref": "refs/heads/master", "object": {"sha": "abc123def456"}})
        raise AssertionError(f"unexpected url: {url}")

    with patch.object(github_merge.urllib.request, "urlopen", side_effect=fake_urlopen):
        result = github_merge.fast_forward(
            repo="owner/repo", base_branch="master", head_branch="cms-preview"
        )

    assert result["object"]["sha"] == "abc123def456"

    patch_call = [c for c in calls if c[0] == "PATCH"][0]
    body = json.loads(patch_call[2])
    assert body == {"sha": "abc123def456", "force": False}


def test_fast_forward_target_sha_skips_head_get(monkeypatch):
    """When target_sha is provided, no GET on head_branch should fire — PATCH uses the SHA directly."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    calls = []

    def fake_urlopen(req, timeout=10):
        url = req.full_url if hasattr(req, "full_url") else req
        method = getattr(req, "method", None) or "GET"
        calls.append((method, url, getattr(req, "data", None)))
        if method == "PATCH":
            return _FakeResp({"ref": "refs/heads/master", "object": {"sha": "deadbeef0001"}})
        raise AssertionError(f"unexpected url/method: {method} {url}")

    with patch.object(github_merge.urllib.request, "urlopen", side_effect=fake_urlopen):
        result = github_merge.fast_forward(
            repo="owner/repo",
            base_branch="master",
            head_branch="cms-preview",
            target_sha="deadbeef0001",
        )

    assert result["object"]["sha"] == "deadbeef0001"
    # Exactly one HTTP call — the PATCH. No GET on head branch.
    assert len(calls) == 1
    assert calls[0][0] == "PATCH"
    body = json.loads(calls[0][2])
    assert body == {"sha": "deadbeef0001", "force": False}


def test_fast_forward_no_token_raises(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(github_merge.GitHubError, match="GITHUB_TOKEN"):
        github_merge.fast_forward(repo="x/y", base_branch="master", head_branch="cms-preview")


def test_fast_forward_diverged_422(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    def fake_urlopen(req, timeout=10):
        url = req.full_url if hasattr(req, "full_url") else req
        if getattr(req, "method", "GET") == "GET":
            return _FakeResp({"object": {"sha": "abc123"}})
        raise urllib.error.HTTPError(
            url,
            422,
            "Unprocessable Entity",
            {},
            BytesIO(b'{"message":"Update is not a fast forward"}'),
        )

    with patch.object(github_merge.urllib.request, "urlopen", side_effect=fake_urlopen):
        with pytest.raises(github_merge.GitHubError, match="diverged"):
            github_merge.fast_forward(
                repo="owner/repo", base_branch="master", head_branch="cms-preview"
            )


def test_fast_forward_404_raises(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    def fake_urlopen(req, timeout=10):
        raise urllib.error.HTTPError(
            "url", 404, "Not Found", {}, BytesIO(b'{"message":"Not Found"}')
        )

    with patch.object(github_merge.urllib.request, "urlopen", side_effect=fake_urlopen):
        with pytest.raises(github_merge.GitHubError, match="404"):
            github_merge.fast_forward(
                repo="owner/repo", base_branch="master", head_branch="cms-preview"
            )
