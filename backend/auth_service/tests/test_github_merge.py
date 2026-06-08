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


def test_fast_forward_protected_branch_promotes_via_pull_request(monkeypatch):
    """A protected base branch (require-PR) refuses the direct ref update with a
    422 that is NOT a divergence ("Changes must be made through a pull request").
    We must fall back to opening + merging a PR pinned to the approved SHA, not
    mislabel it as 'diverged'."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    calls = []

    def fake_urlopen(req, timeout=10):
        method = getattr(req, "method", None) or "GET"
        url = req.full_url if hasattr(req, "full_url") else req
        data = getattr(req, "data", None)
        calls.append((method, url))
        # 1) direct ref update refused by branch protection
        if method == "PATCH" and "git/refs/heads/main" in url:
            raise urllib.error.HTTPError(
                url,
                422,
                "Unprocessable Entity",
                {},
                BytesIO(b'{"message":"Changes must be made through a pull request."}'),
            )
        # 2) create the throwaway promotion branch pinned at the approved sha
        if method == "POST" and url.endswith("/git/refs"):
            body = json.loads(data)
            assert body["sha"] == "approvedsha99"
            assert body["ref"].startswith("refs/heads/cms-promote-")
            return _FakeResp({"ref": body["ref"], "object": {"sha": "approvedsha99"}})
        # 3) open the PR
        if method == "POST" and url.endswith("/pulls"):
            body = json.loads(data)
            assert body["base"] == "main"
            assert body["head"].startswith("cms-promote-")
            return _FakeResp({"number": 7})
        # 4) merge the PR, pinned to the approved sha
        if method == "PUT" and "/pulls/7/merge" in url:
            body = json.loads(data)
            assert body["sha"] == "approvedsha99"
            return _FakeResp({"merged": True, "sha": "mergecommitsha"})
        # 5) delete the throwaway branch (204, no body)
        if method == "DELETE" and "/git/refs/heads/cms-promote-" in url:
            return _FakeResp({})
        raise AssertionError(f"unexpected {method} {url}")

    with patch.object(github_merge.urllib.request, "urlopen", side_effect=fake_urlopen):
        result = github_merge.fast_forward(
            repo="owner/repo",
            base_branch="main",
            head_branch="cms-preview",
            target_sha="approvedsha99",
        )

    # Production ref ends up at the PR's merge commit.
    assert result["object"]["sha"] == "mergecommitsha"
    methods = [m for m, _ in calls]
    assert methods.count("PATCH") >= 1  # tried the fast path first
    assert "POST" in methods and "PUT" in methods
    assert any(m == "DELETE" for m, _ in calls)  # throwaway branch cleaned up


def test_protected_fallback_recovers_when_temp_branch_already_exists(monkeypatch):
    """If a prior promotion of the same SHA left its throwaway branch behind
    (cleanup failed), re-promoting must not wedge: creating the ref 422s
    ('Reference already exists'), so we update it in place and continue."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    def fake_urlopen(req, timeout=10):
        method = getattr(req, "method", None) or "GET"
        url = req.full_url if hasattr(req, "full_url") else req
        if method == "PATCH" and "git/refs/heads/main" in url:
            raise urllib.error.HTTPError(
                url,
                422,
                "Unprocessable Entity",
                {},
                BytesIO(b'{"message":"Changes must be made through a pull request."}'),
            )
        if method == "POST" and url.endswith("/git/refs"):
            raise urllib.error.HTTPError(
                url,
                422,
                "Unprocessable Entity",
                {},
                BytesIO(b'{"message":"Reference already exists"}'),
            )
        if method == "PATCH" and "/git/refs/heads/cms-promote-" in url:
            return _FakeResp(
                {"ref": "refs/heads/cms-promote-x", "object": {"sha": "approvedsha99"}}
            )
        if method == "POST" and url.endswith("/pulls"):
            return _FakeResp({"number": 9})
        if method == "PUT" and "/pulls/9/merge" in url:
            return _FakeResp({"merged": True, "sha": "mergesha2"})
        if method == "DELETE":
            return _FakeResp({})
        raise AssertionError(f"unexpected {method} {url}")

    with patch.object(github_merge.urllib.request, "urlopen", side_effect=fake_urlopen):
        result = github_merge.fast_forward(
            repo="owner/repo",
            base_branch="main",
            head_branch="cms-preview",
            target_sha="approvedsha99",
        )

    assert result["object"]["sha"] == "mergesha2"


def test_protected_fallback_wraps_merge_failure_as_github_error(monkeypatch):
    """If the PR cannot be merged (e.g. a required status check on the protected
    branch), surface a GitHubError so the Slack approval handler reports it
    cleanly instead of leaking a raw urllib error to the caller."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    def fake_urlopen(req, timeout=10):
        method = getattr(req, "method", None) or "GET"
        url = req.full_url if hasattr(req, "full_url") else req
        if method == "PATCH" and "git/refs/heads/main" in url:
            raise urllib.error.HTTPError(
                url,
                422,
                "Unprocessable Entity",
                {},
                BytesIO(b'{"message":"Changes must be made through a pull request."}'),
            )
        if method == "POST" and url.endswith("/git/refs"):
            return _FakeResp(
                {"ref": "refs/heads/cms-promote-x", "object": {"sha": "approvedsha99"}}
            )
        if method == "POST" and url.endswith("/pulls"):
            return _FakeResp({"number": 11})
        if method == "PUT" and "/pulls/11/merge" in url:
            raise urllib.error.HTTPError(
                url,
                405,
                "Method Not Allowed",
                {},
                BytesIO(b'{"message":"Required status check is expected."}'),
            )
        if method == "DELETE":
            return _FakeResp({})
        raise AssertionError(f"unexpected {method} {url}")

    with patch.object(github_merge.urllib.request, "urlopen", side_effect=fake_urlopen):
        with pytest.raises(github_merge.GitHubError, match="promoting via pull request"):
            github_merge.fast_forward(
                repo="owner/repo",
                base_branch="main",
                head_branch="cms-preview",
                target_sha="approvedsha99",
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
