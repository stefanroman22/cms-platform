# Slack Approval, Publish, Email (S1.5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Slack ✅ reaction on a resolved-issue message merges `cms-preview → master` of the client repo + emails the client; threaded text reply reverts the issue to `in_progress` with stored feedback.

**Architecture:** New `/slack/events` router with HMAC signature verification + Slack event dispatch. Two service modules implement the action paths (`github_merge`, `issue_resolved_email`) and a third (`slack_handler`) contains the reaction + message handlers. The existing `slack_notify.notify_issue_resolved` is extended to return the Slack message `ts` so the router can persist it on `project_issues.slack_resolved_ts` for later lookup. Idempotency via a new `slack_processed_events` table.

**Tech Stack:** FastAPI, Python 3.13, urllib.request (stdlib HTTP — matches existing service modules), pytest, Supabase, Slack Events API, GitHub REST API, Resend Email API.

**Spec:** `docs/superpowers/specs/2026-05-15-slack-issue-approval-publish-design.md`

**Branch:** `feat/slack-issue-approval-publish` (already created off latest master after S1 shipped).

---

## File Structure

**Create:**
- `backend/migrations/2026_05_15_slack_inbound_s1_5.sql` — DB migration (3 columns on issues, 1 on projects, idempotency table, data fix).
- `backend/auth_service/services/slack_signature.py` — HMAC verifier (pure function, no I/O).
- `backend/auth_service/services/slack_events_dedup.py` — idempotency table read/write helpers.
- `backend/auth_service/services/github_merge.py` — GitHub API fast-forward.
- `backend/auth_service/services/issue_resolved_email.py` — Resend POST + branded HTML.
- `backend/auth_service/services/slack_handler.py` — `handle_reaction_added`, `handle_message`, internal helpers.
- `backend/auth_service/routers/slack_events.py` — `POST /slack/events` endpoint.
- `backend/auth_service/tests/test_slack_signature.py` — HMAC unit tests.
- `backend/auth_service/tests/test_slack_events_dedup.py` — idempotency unit tests.
- `backend/auth_service/tests/test_github_merge.py` — github_merge unit tests.
- `backend/auth_service/tests/test_issue_resolved_email.py` — email service unit tests.
- `backend/auth_service/tests/test_slack_handler.py` — handler unit tests.
- `backend/auth_service/tests/test_slack_events_router.py` — `/slack/events` integration tests.

**Modify:**
- `backend/auth_service/services/slack_notify.py` — `notify_issue_resolved` returns Slack `ts`. Add helper `post_thread_reply()`.
- `backend/auth_service/routers/issues.py` — capture `ts` returned by `notify_issue_resolved`, persist to `project_issues.slack_resolved_ts`.
- `backend/auth_service/main.py` — `app.include_router(slack_events.router)`.
- `backend/auth_service/routers/deps.py` — widen `require_project_access` SELECT to include `production_branch`.
- `backend/auth_service/tests/conftest.py` — extend `fake_require_project_access` to include `production_branch`; add patch entries for `slack_events` router.
- `backend/auth_service/core/config.py` — declare `SLACK_SIGNING_SECRET`, `SLACK_APPROVER_USER_ID`, `SLACK_BOT_USER_ID`, `GITHUB_TOKEN` fields (optional, default empty).
- `docs/ENVIRONMENTS.md` — document 4 new env vars.
- `docs/ONBOARDING.md` — Slack app re-install + new env-var setup section.

---

## Task 1: DB migration

**Files:**
- Create: `backend/migrations/2026_05_15_slack_inbound_s1_5.sql`

- [ ] **Step 1: Write the migration**

Create `backend/migrations/2026_05_15_slack_inbound_s1_5.sql`:

```sql
-- 2026_05_15 — Slack inbound S1.5 schema
-- Adds columns + idempotency table needed for /slack/events approval +
-- revision flows. Also fixes stale repo_branch data from S1's default.
-- RLS: project_issues + projects use existing tenant policies; slack_processed_events
-- is server-internal (no client access) so RLS stays off but we restrict via no
-- public grants (Supabase service-role-only by default).

-- 1. project_issues: track Slack message ts + revision feedback
ALTER TABLE project_issues
  ADD COLUMN IF NOT EXISTS slack_resolved_ts TEXT NULL,
  ADD COLUMN IF NOT EXISTS revision_feedback TEXT NULL,
  ADD COLUMN IF NOT EXISTS revision_feedback_at TIMESTAMPTZ NULL;

COMMENT ON COLUMN project_issues.slack_resolved_ts IS
  'Slack message ts of the most recent "Issue Resolved" post. Lookup key for reaction + thread-reply events.';
COMMENT ON COLUMN project_issues.revision_feedback IS
  'Stefan''s last rejection text. Cleared when ✅ approves.';

-- 2. projects: production branch name for fast-forward
ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS production_branch TEXT NOT NULL DEFAULT 'master';

COMMENT ON COLUMN projects.production_branch IS
  'Production git branch. Backend fast-forwards this ref to repo_branch HEAD on ✅ approval.';

-- 3. Data fix: real client repos use cms-preview, not the speculative dev default
UPDATE projects
  SET repo_branch = 'cms-preview'
  WHERE repo_branch = 'dev'
    AND github_repo IS NOT NULL;

-- 4. Idempotency table for Slack event de-dup
CREATE TABLE IF NOT EXISTS slack_processed_events (
  event_id TEXT PRIMARY KEY,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_slack_processed_events_received_at
  ON slack_processed_events (received_at);
```

- [ ] **Step 2: Do NOT apply automatically**

The user applies migrations via Supabase MCP. Do not call `apply_migration` or `psql`. Stop after writing the file.

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/2026_05_15_slack_inbound_s1_5.sql
git commit -m "feat(db): S1.5 — slack_resolved_ts + revision_feedback + production_branch + dedup table"
```

---

## Task 2: HMAC signature verifier (pure unit)

**Files:**
- Create: `backend/auth_service/services/slack_signature.py`
- Create: `backend/auth_service/tests/test_slack_signature.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/auth_service/tests/test_slack_signature.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests/test_slack_signature.py -v
```

Expected: collection error or 6 failures — module doesn't exist yet.

- [ ] **Step 3: Implement the module**

Create `backend/auth_service/services/slack_signature.py`:

```python
"""Slack Events API HMAC-SHA-256 signature verification.

Slack signs each event request with the app's signing secret. We must
reject any request whose signature doesn't match. Also enforces a 5-min
replay window — old captured requests can't be replayed later.
"""
from __future__ import annotations

import hashlib
import hmac
import time

_REPLAY_WINDOW_S = 300


def verify(timestamp: str, body: bytes, signature: str, secret: str) -> bool:
    """Returns True iff signature is valid AND within the replay window."""
    if not timestamp or not signature or not secret:
        return False
    try:
        ts_int = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - ts_int) > _REPLAY_WINDOW_S:
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8', errors='replace')}".encode()
    expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest auth_service/tests/test_slack_signature.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/slack_signature.py backend/auth_service/tests/test_slack_signature.py
git commit -m "feat(slack): add HMAC signature verifier for Events API"
```

---

## Task 3: Idempotency helpers

**Files:**
- Create: `backend/auth_service/services/slack_events_dedup.py`
- Create: `backend/auth_service/tests/test_slack_events_dedup.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/auth_service/tests/test_slack_events_dedup.py`:

```python
"""Idempotency table for Slack event delivery."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from ..services import slack_events_dedup


def test_mark_processed_inserts_row():
    mock_sb = MagicMock()
    for m in ("table", "insert", "execute"):
        getattr(mock_sb, m).return_value = mock_sb
    with patch.object(slack_events_dedup, "get_supabase_admin", return_value=mock_sb):
        slack_events_dedup.mark_processed("evt-123")
    mock_sb.table.assert_called_with("slack_processed_events")
    args = mock_sb.insert.call_args.args[0]
    assert args["event_id"] == "evt-123"


def test_already_processed_true_when_row_exists():
    mock_sb = MagicMock()
    for m in ("table", "select", "eq", "maybe_single", "execute"):
        getattr(mock_sb, m).return_value = mock_sb
    mock_sb.execute.return_value = MagicMock(data={"event_id": "evt-123"})
    with patch.object(slack_events_dedup, "get_supabase_admin", return_value=mock_sb):
        assert slack_events_dedup.already_processed("evt-123") is True


def test_already_processed_false_when_row_absent():
    mock_sb = MagicMock()
    for m in ("table", "select", "eq", "maybe_single", "execute"):
        getattr(mock_sb, m).return_value = mock_sb
    mock_sb.execute.return_value = MagicMock(data=None)
    with patch.object(slack_events_dedup, "get_supabase_admin", return_value=mock_sb):
        assert slack_events_dedup.already_processed("evt-unknown") is False


def test_empty_event_id_returns_false_already_processed():
    """Defensive: missing event_id treated as not-processed (safer than blocking)."""
    assert slack_events_dedup.already_processed("") is False
    assert slack_events_dedup.already_processed(None) is False  # type: ignore[arg-type]


def test_mark_processed_swallows_db_error():
    """If the dedup insert fails, the caller still proceeds — worse to drop legitimate events."""
    mock_sb = MagicMock()
    mock_sb.table.return_value = mock_sb
    mock_sb.insert.return_value = mock_sb
    mock_sb.execute.side_effect = RuntimeError("db down")
    with patch.object(slack_events_dedup, "get_supabase_admin", return_value=mock_sb):
        slack_events_dedup.mark_processed("evt-x")  # must not raise
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest auth_service/tests/test_slack_events_dedup.py -v
```

Expected: collection error.

- [ ] **Step 3: Implement the module**

Create `backend/auth_service/services/slack_events_dedup.py`:

```python
"""Slack event idempotency.

Slack may redeliver the same event (network glitch, our timeout, etc).
We insert event_id with ON CONFLICT DO NOTHING semantics — but Supabase
client doesn't expose ON CONFLICT directly, so we do a SELECT-then-INSERT
pattern. Race conditions are acceptable: duplicate action is rare and
safe (merge is idempotent, email may double-send — acceptable for our
volume).
"""
from __future__ import annotations

import logging

from .supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)


def already_processed(event_id: str | None) -> bool:
    if not event_id:
        return False
    try:
        sb = get_supabase_admin()
        result = (
            sb.table("slack_processed_events")
            .select("event_id")
            .eq("event_id", event_id)
            .maybe_single()
            .execute()
        )
        return bool(result.data)
    except Exception:
        logger.exception("dedup lookup failed; treating as not-processed")
        return False


def mark_processed(event_id: str | None) -> None:
    if not event_id:
        return
    try:
        sb = get_supabase_admin()
        sb.table("slack_processed_events").insert({"event_id": event_id}).execute()
    except Exception:
        # DB error or unique-violation race. Either way, the caller already
        # decided to process this event; we don't want to abort that work.
        logger.exception("dedup insert failed (id=%s)", event_id)
```

- [ ] **Step 4: Run tests**

```bash
pytest auth_service/tests/test_slack_events_dedup.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/slack_events_dedup.py backend/auth_service/tests/test_slack_events_dedup.py
git commit -m "feat(slack): add event idempotency helpers"
```

---

## Task 4: GitHub fast-forward service

**Files:**
- Create: `backend/auth_service/services/github_merge.py`
- Create: `backend/auth_service/tests/test_github_merge.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/auth_service/tests/test_github_merge.py`:

```python
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

    # Verify the PATCH body contains sha + force:False
    patch_call = [c for c in calls if c[0] == "PATCH"][0]
    body = json.loads(patch_call[2])
    assert body == {"sha": "abc123def456", "force": False}


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
        # PATCH raises 422
        raise urllib.error.HTTPError(
            url, 422, "Unprocessable Entity", {}, BytesIO(b'{"message":"Update is not a fast forward"}')
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest auth_service/tests/test_github_merge.py -v
```

Expected: collection error.

- [ ] **Step 3: Implement the module**

Create `backend/auth_service/services/github_merge.py`:

```python
"""Fast-forward a base branch to a head branch via GitHub REST API.

Used by S1.5 Slack approval flow: when Stefan ✅ a resolved-issue
message, we promote cms-preview → master on the client repo, which
triggers a Vercel production deploy.

Uses urllib.request (stdlib) to match the existing services/ pattern;
no new dependencies.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_GH_API = "https://api.github.com"


class GitHubError(Exception):
    pass


def fast_forward(*, repo: str, base_branch: str, head_branch: str) -> dict:
    """PATCH `base_branch` ref to point at HEAD of `head_branch`.

    `repo` is "owner/name". Returns the GitHub API JSON response.
    Raises GitHubError on any non-2xx response.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubError("GITHUB_TOKEN not configured")

    head = _get(f"{_GH_API}/repos/{repo}/git/refs/heads/{head_branch}", token)
    new_sha = head["object"]["sha"]

    body = json.dumps({"sha": new_sha, "force": False}).encode()
    req = urllib.request.Request(
        f"{_GH_API}/repos/{repo}/git/refs/heads/{base_branch}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "cms-backend/1.0",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        if e.code == 422:
            raise GitHubError(
                f"Cannot fast-forward {base_branch} to {head_branch} — diverged. "
                f"Resolve manually. ({body_text})"
            ) from e
        raise GitHubError(f"GitHub {e.code}: {body_text}") from e


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "cms-backend/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise GitHubError(f"GitHub {e.code} on {url}: {e.read().decode(errors='replace')}") from e
```

- [ ] **Step 4: Run tests**

```bash
pytest auth_service/tests/test_github_merge.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/github_merge.py backend/auth_service/tests/test_github_merge.py
git commit -m "feat(github): add fast-forward merge helper for S1.5 approval"
```

---

## Task 5: Resend "issue resolved" email

**Files:**
- Create: `backend/auth_service/services/issue_resolved_email.py`
- Create: `backend/auth_service/tests/test_issue_resolved_email.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/auth_service/tests/test_issue_resolved_email.py`:

```python
"""Resend issue-resolved client email unit tests."""
from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from unittest.mock import patch

import pytest

from ..services import issue_resolved_email


def _issue() -> dict:
    return {
        "id": "i1",
        "title": "Hero image broken",
        "description": "Stretches on iPhone Safari.",
    }


def _project() -> dict:
    return {
        "id": "p1",
        "slug": "acme",
        "name": "Acme Site",
        "production_url": "https://acme.example.com",
        "client_name": "Acme Co",
    }


def test_render_html_includes_branding_and_content():
    html = issue_resolved_email.render_html(
        client_name="Stefan",
        issue_title="Hero broken",
        issue_description="Stretches on Safari.",
        production_url="https://acme.example.com",
    )
    assert "Roman Technologies" in html
    assert "Client Portal" in html
    assert "logo_dark.png" in html
    assert "Hero broken" in html
    assert "Stretches on Safari." in html
    assert "https://acme.example.com" in html
    assert "Stefan" in html


def test_render_html_escapes_user_input():
    html = issue_resolved_email.render_html(
        client_name="<script>alert(1)</script>",
        issue_title="Title <img src=x>",
        issue_description="Desc <b>bold</b>",
        production_url="https://x.example.com",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x>" not in html
    assert "&lt;img" in html
    assert "<b>bold</b>" not in html


def test_render_html_rejects_non_http_url():
    html = issue_resolved_email.render_html(
        client_name="x",
        issue_title="t",
        issue_description="d",
        production_url="javascript:alert(1)",
    )
    # Falls back to safe default
    assert "javascript:" not in html
    assert "roman-technologies.dev" in html


def test_send_raises_when_resend_unset(monkeypatch):
    from ..core import config

    monkeypatch.setattr(config.settings, "RESEND_API_KEY", "")
    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        issue_resolved_email.send(
            to_email="client@example.com", issue=_issue(), project=_project()
        )


def test_send_short_circuits_for_e2e_throwaway(monkeypatch):
    from ..core import config

    monkeypatch.setattr(config.settings, "RESEND_API_KEY", "re_test")
    # e2e_email_guard recognizes "throwaway" emails — verify short-circuit works.
    result = issue_resolved_email.send(
        to_email="throwaway-test@example.com",
        issue=_issue(),
        project={**_project(), "name": "throwaway"},
    )
    assert result.get("short_circuit") is True or "throwaway" in json.dumps(result).lower()


def test_send_posts_to_resend(monkeypatch):
    from ..core import config

    monkeypatch.setattr(config.settings, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(config.settings, "RESEND_FROM_NAME", "Roman Tech")
    monkeypatch.setattr(config.settings, "RESEND_FROM_EMAIL", "noreply@x.dev")

    captured = {}

    class _Resp:
        def __init__(self):
            self._buf = BytesIO(b'{"id":"email_123"}')

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return self._buf.read()

    def fake_urlopen(req, timeout=10):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        captured["body"] = json.loads(req.data)
        return _Resp()

    with patch.object(issue_resolved_email.urllib.request, "urlopen", side_effect=fake_urlopen):
        result = issue_resolved_email.send(
            to_email="client@example.com", issue=_issue(), project=_project()
        )

    assert result == {"id": "email_123"}
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["body"]["to"] == "client@example.com"
    assert "Acme Site" in captured["body"]["subject"]
    assert "Hero image broken" in captured["body"]["html"]
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest auth_service/tests/test_issue_resolved_email.py -v
```

Expected: collection error.

- [ ] **Step 3: Implement the module**

Create `backend/auth_service/services/issue_resolved_email.py`:

```python
"""Client-facing email when an issue is approved + promoted to prod.

Inline HTML matches the project_request_email.py header pattern
(zinc-900 bar + roman-technologies logo + "Client Portal" eyebrow).
Resend POST via urllib.request, no new dependencies.
"""
from __future__ import annotations

import html
import json
import urllib.error
import urllib.request

from ..core.config import settings


def _safe_url(value: str, fallback: str = "https://roman-technologies.dev") -> str:
    v = (value or "").strip()
    if v.startswith("http://") or v.startswith("https://"):
        return v
    return fallback


def render_html(
    *,
    client_name: str,
    issue_title: str,
    issue_description: str,
    production_url: str,
) -> str:
    name = html.escape(client_name) if client_name else "there"
    title = html.escape(issue_title)
    desc = html.escape(issue_description).replace("\n", "<br>")
    url = _safe_url(production_url)
    url_safe = html.escape(url)

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#27272a">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f4;padding:40px 20px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border:1px solid #e4e4e7;border-radius:12px;overflow:hidden">
        <tr><td style="background:#18181b;padding:24px 32px">
          <table cellpadding="0" cellspacing="0"><tr>
            <td width="44" height="44" valign="middle" style="background:#18181b;border-radius:10px">
              <img src="https://roman-technologies.dev/logo_dark.png" width="44" height="44" alt="" style="display:block;border:0;border-radius:10px">
            </td>
            <td style="vertical-align:middle;padding-left:14px">
              <p style="margin:0;color:#fff;font-size:18px;font-weight:600;letter-spacing:-0.01em">Roman Technologies</p>
              <p style="margin:2px 0 0;color:#a1a1aa;font-size:12px">Client Portal</p>
            </td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:32px 32px 8px">
          <h1 style="margin:0 0 12px;font-size:22px;font-weight:600;color:#18181b">Your issue is fixed.</h1>
          <p style="margin:0;font-size:15px;line-height:1.55;color:#52525b">
            Hi {name}, the fix for the issue you reported is now live on your site.
          </p>
        </td></tr>
        <tr><td style="padding:8px 32px">
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;background:#fafafa;border:1px solid #e4e4e7;border-radius:8px">
            <tr><td style="padding:18px 22px">
              <p style="margin:0 0 12px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#71717a">Issue resolved</p>
              <p style="margin:0 0 8px;font-size:15px;font-weight:600;color:#18181b">{title}</p>
              <p style="margin:0;font-size:14px;line-height:1.6;color:#52525b">{desc}</p>
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:24px 32px 8px" align="center">
          <a href="{url_safe}" style="display:inline-block;background:#18181b;color:#fff;text-decoration:none;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px">View your live site &rarr;</a>
        </td></tr>
        <tr><td style="padding:32px 32px 28px;border-top:1px solid #f4f4f5">
          <p style="margin:0;font-size:12px;color:#a1a1aa;line-height:1.5">
            Sent from <a href="https://roman-technologies.dev" style="color:#71717a;text-decoration:none">roman-technologies.dev</a> &middot;
            &copy; 2026 Roman Technologies &middot; Client Portal
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def send(*, to_email: str, issue: dict, project: dict) -> dict:
    """POST to Resend. Returns parsed JSON on 200, raises RuntimeError otherwise."""
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    project_name = project.get("name") or project.get("slug") or "your site"

    if should_short_circuit(to_email, "", project_name, project.get("production_url", "")):
        return short_circuit_response(f"issue_resolved:{to_email}")

    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured on this backend")

    body = {
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": to_email,
        "subject": f"Your issue is fixed — {project_name}",
        "html": render_html(
            client_name=project.get("client_name", "") or "",
            issue_title=issue.get("title", "Issue resolved"),
            issue_description=issue.get("description", ""),
            production_url=project.get("production_url", ""),
        ),
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "roman-technologies-cms-backend/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend {e.code}: {e.read().decode()}") from e
```

- [ ] **Step 4: Run tests**

```bash
pytest auth_service/tests/test_issue_resolved_email.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/issue_resolved_email.py backend/auth_service/tests/test_issue_resolved_email.py
git commit -m "feat(email): add issue-resolved client email with branded template"
```

---

## Task 6: Extend `slack_notify` to return `ts` + add `post_thread_reply`

**Files:**
- Modify: `backend/auth_service/services/slack_notify.py`
- Modify: `backend/auth_service/tests/test_slack_notify.py`

- [ ] **Step 1: Append failing tests**

Add to `backend/auth_service/tests/test_slack_notify.py`:

```python
def test_resolved_returns_slack_ts(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    class _OkResp:
        def json(self):
            return {"ok": True, "ts": "1715789123.001234"}

    with patch.object(slack_notify.httpx, "post", return_value=_OkResp()):
        ts = slack_notify.notify_issue_resolved(
            issue=_sample_issue(),
            project=_sample_project(),
            resolver_email="stefan@example.com",
        )

    assert ts == "1715789123.001234"


def test_resolved_returns_none_when_disabled(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ISSUES_CHANNEL_ID", raising=False)
    ts = slack_notify.notify_issue_resolved(
        issue=_sample_issue(),
        project=_sample_project(),
        resolver_email="stefan@example.com",
    )
    assert ts is None


def test_resolved_returns_none_on_api_error(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    class _ErrResp:
        def json(self):
            return {"ok": False, "error": "not_in_channel"}

    with patch.object(slack_notify.httpx, "post", return_value=_ErrResp()):
        ts = slack_notify.notify_issue_resolved(
            issue=_sample_issue(),
            project=_sample_project(),
            resolver_email="stefan@example.com",
        )

    assert ts is None


def test_post_thread_reply_posts_with_thread_ts(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    captured = {}

    class _OkResp:
        def json(self):
            return {"ok": True, "ts": "1715789200.000001"}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return _OkResp()

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        slack_notify.post_thread_reply(thread_ts="1715789123.001234", text="🚀 Promoted to production.")

    body = captured["json"]
    assert body["channel"] == "C123"
    assert body["thread_ts"] == "1715789123.001234"
    assert body["text"] == "🚀 Promoted to production."


def test_post_thread_reply_disabled_no_op(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ISSUES_CHANNEL_ID", raising=False)
    with patch.object(slack_notify.httpx, "post") as mock_post:
        slack_notify.post_thread_reply(thread_ts="x", text="y")
        mock_post.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm failures**

```bash
pytest auth_service/tests/test_slack_notify.py -v -k "returns_slack_ts or post_thread_reply or returns_none"
```

Expected: 5 failures (functions don't yet return `ts` or don't yet have `post_thread_reply`).

- [ ] **Step 3: Modify `slack_notify.py`**

In `backend/auth_service/services/slack_notify.py`:

1. Change `_post` to return the response `ts` on success, `None` otherwise:

```python
def _post(blocks: list[dict], text_fallback: str, thread_ts: str | None = None) -> str | None:
    """POST one message to Slack. Returns the message ts on success, None on
    disabled mode or any failure. Swallow all errors."""
    if not _enabled():
        logger.info("slack_notify disabled — skipping")
        return None
    try:
        body: dict[str, Any] = {
            "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
            "text": text_fallback,
            "blocks": blocks,
        }
        if thread_ts:
            body["thread_ts"] = thread_ts
        resp = httpx.post(
            SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=body,
            timeout=_TIMEOUT_S,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("slack_notify api error: %s", data.get("error"))
            return None
        return data.get("ts")
    except Exception:
        logger.exception("slack_notify post failed")
        return None
```

2. Change `notify_issue_resolved` to return what `_post` returns:

```python
def notify_issue_resolved(
    issue: dict[str, Any], project: dict[str, Any], resolver_email: str | None
) -> str | None:
    """Returns the Slack message ts on success, None otherwise."""
    if not _enabled():
        logger.info("slack_notify disabled — skipping resolved")
        return None
    try:
        blocks = _build_resolved_blocks(issue, project, resolver_email)
        fallback = f"Resolved [{project.get('slug', '?')}]: {issue.get('title', '?')}"
        return _post(blocks, fallback)
    except Exception:  # noqa: BLE001 — public API must never re-raise
        logger.exception("slack_notify (resolved) failed during build/post")
        return None
```

3. Apply same return-value treatment to `notify_issue_created` (returns `str | None`):

```python
def notify_issue_created(
    issue: dict[str, Any], project: dict[str, Any], user_email: str | None
) -> str | None:
    if not _enabled():
        logger.info("slack_notify disabled — skipping created")
        return None
    try:
        blocks = _build_created_blocks(issue, project, user_email)
        fallback = f"New issue [{project.get('slug', '?')}]: {issue.get('title', '?')}"
        return _post(blocks, fallback)
    except Exception:  # noqa: BLE001 — public API must never re-raise
        logger.exception("slack_notify (created) failed during build/post")
        return None
```

4. Add `post_thread_reply` as a new public function:

```python
def post_thread_reply(*, thread_ts: str, text: str) -> str | None:
    """Reply in the thread of a previously-posted message.

    text is rendered as Slack mrkdwn. No blocks (simple reply).
    Returns the reply's ts on success, None otherwise.
    """
    if not _enabled():
        logger.info("slack_notify disabled — skipping thread reply")
        return None
    try:
        resp = httpx.post(
            SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
                "thread_ts": thread_ts,
                "text": text,
            },
            timeout=_TIMEOUT_S,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("post_thread_reply api error: %s", data.get("error"))
            return None
        return data.get("ts")
    except Exception:
        logger.exception("post_thread_reply failed")
        return None
```

- [ ] **Step 4: Run the slack_notify tests**

```bash
pytest auth_service/tests/test_slack_notify.py -v
```

Expected: all previous tests pass (none asserted return value) + 5 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/slack_notify.py backend/auth_service/tests/test_slack_notify.py
git commit -m "feat(slack): return ts from notify_* + add post_thread_reply"
```

---

## Task 7: Persist `slack_resolved_ts` on issue resolve

**Files:**
- Modify: `backend/auth_service/routers/issues.py`
- Modify: `backend/auth_service/tests/test_issues_router.py`

- [ ] **Step 1: Append failing test**

Add to `backend/auth_service/tests/test_issues_router.py`:

```python
def test_status_done_persists_slack_ts(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    auth_as(admin_user)

    pending_row = {"id": "issue-1", "project_id": "project-acme", "status": "pending"}
    updated_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "Hero broken",
        "description": "stretches",
        "priority": "High",
        "status": "done",
        "created_by": "client-uuid",
        "created_at": "2026-05-15T10:00:00Z",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=pending_row),                              # pre-update SELECT
        MagicMock(data=[updated_row]),                            # UPDATE status
        MagicMock(data={"email": "client@acme.com"}),             # email lookup
        MagicMock(data=[updated_row]),                            # UPDATE slack_resolved_ts
    ]

    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: "1715789123.001234",
    )

    resp = client.patch(
        "/projects/acme/issues/issue-1/status", json={"status": "done"}
    )
    assert resp.status_code == 200

    # Verify the second UPDATE call set slack_resolved_ts
    update_calls = [c for c in mock_supabase.update.call_args_list]
    ts_update = next(
        c for c in update_calls if "slack_resolved_ts" in (c.args[0] if c.args else {})
    )
    assert ts_update.args[0]["slack_resolved_ts"] == "1715789123.001234"


def test_status_done_no_ts_when_slack_disabled(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    """If slack_notify returns None, do NOT update slack_resolved_ts."""
    auth_as(admin_user)
    pending_row = {"id": "issue-1", "project_id": "project-acme", "status": "pending"}
    updated_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "x",
        "description": "y",
        "priority": "Low",
        "status": "done",
        "created_by": None,
        "created_at": "2026-05-15T10:00:00Z",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=pending_row),
        MagicMock(data=[updated_row]),
    ]

    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: None,
    )

    resp = client.patch(
        "/projects/acme/issues/issue-1/status", json={"status": "done"}
    )
    assert resp.status_code == 200

    update_calls = [c.args[0] for c in mock_supabase.update.call_args_list if c.args]
    assert not any("slack_resolved_ts" in u for u in update_calls)
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest auth_service/tests/test_issues_router.py::test_status_done_persists_slack_ts -v
```

Expected: FAIL — `slack_resolved_ts` never written.

- [ ] **Step 3: Modify `update_issue_status`**

In `backend/auth_service/routers/issues.py`, find the `update_issue_status` block where `slack_notify.notify_issue_resolved` is called. Replace the call site with:

```python
    if old_status != "done" and body.status == "done":
        try:
            ts = slack_notify.notify_issue_resolved(
                issue={"id": r["id"], "title": r["title"]},
                project=project,
                resolver_email=user.email,
            )
            if ts:
                sb.table("project_issues").update(
                    {"slack_resolved_ts": ts}
                ).eq("id", r["id"]).execute()
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("slack_notify (resolved) raised")

    return issue_out
```

The `if ts:` guard skips the UPDATE when Slack is disabled or failed.

- [ ] **Step 4: Run the new tests**

```bash
pytest auth_service/tests/test_issues_router.py -v
```

Expected: 7 passed (5 from S1 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/issues.py backend/auth_service/tests/test_issues_router.py
git commit -m "feat(issues): persist slack_resolved_ts after notify on resolve"
```

---

## Task 8: Declare new env vars on Settings + widen `require_project_access`

**Files:**
- Modify: `backend/auth_service/core/config.py`
- Modify: `backend/auth_service/routers/deps.py`
- Modify: `backend/auth_service/tests/conftest.py`

- [ ] **Step 1: Add Settings fields**

In `backend/auth_service/core/config.py`, append to the `Settings` class (after existing fields, before `model_config`):

```python
    # Slack — S1 outbound + S1.5 inbound
    SLACK_BOT_TOKEN: str = ""
    SLACK_ISSUES_CHANNEL_ID: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_APPROVER_USER_ID: str = ""
    SLACK_BOT_USER_ID: str = ""
    CMS_DASHBOARD_URL: str = "https://roman-technologies.dev"

    # GitHub PAT for production-promote fast-forward (S1.5)
    GITHUB_TOKEN: str = ""
```

Note: `slack_notify.py` reads via `os.getenv` and `main.py` calls `load_dotenv()` — those keep working. Declaring on Settings just makes them available via `settings.X` for new code (the slack_events router uses `settings.SLACK_SIGNING_SECRET` for HMAC).

- [ ] **Step 2: Widen `require_project_access` SELECT**

In `backend/auth_service/routers/deps.py`, change line 26 from:

```python
        .select("id, name, slug, user_id, is_active, github_repo, preview_url")
```

to:

```python
        .select("id, name, slug, user_id, is_active, github_repo, preview_url, production_url, production_branch, repo_branch")
```

Adds the production-side fields the slack_handler needs.

- [ ] **Step 3: Update `auth_as` fake to match**

In `backend/auth_service/tests/conftest.py`, find `fake_require_project_access` and extend the returned dict:

```python
        def fake_require_project_access(slug, u):
            return {
                "id": f"project-{slug}",
                "slug": slug,
                "name": slug.title(),
                "github_repo": f"https://github.com/test/{slug}",
                "repo_branch": "cms-preview",
                "production_branch": "master",
                "preview_url": f"https://{slug}-dev.vercel.app",
                "production_url": f"https://{slug}.vercel.app",
            }
```

Note `repo_branch` was `"dev"` in S1 conftest — flip to `"cms-preview"` to match real-world data after Task 1's UPDATE.

The S1 test `test_create_issue_fires_slack_created` asserts `call["project"]["repo_branch"] == "dev"` — that test must change to `"cms-preview"` (mechanical follow-up).

- [ ] **Step 4: Fix S1 test assertion**

In `backend/auth_service/tests/test_issues_router.py`, find:

```python
    assert call["project"]["repo_branch"] == "dev"
```

Change to:

```python
    assert call["project"]["repo_branch"] == "cms-preview"
```

- [ ] **Step 5: Run full suite**

```bash
pytest auth_service/tests -v 2>&1 | tail -10
```

Expected: still 112+ passed (S1 tests adapted, no new tests yet in this task).

- [ ] **Step 6: Add a regression test on the widened SELECT**

Append to `backend/auth_service/tests/test_deps.py` (file exists from S1):

```python
def test_require_project_access_selects_s1_5_fields(mock_supabase, admin_user):
    """Regression: deps.require_project_access must SELECT production_branch and
    production_url so the slack_handler approval flow has the fields it needs."""
    from auth_service.routers import deps

    mock_supabase.execute.return_value.data = {
        "id": "p1",
        "name": "Acme",
        "slug": "acme",
        "user_id": admin_user.id,
        "is_active": True,
        "github_repo": "https://github.com/x/acme",
        "preview_url": "https://acme-dev.vercel.app",
        "production_url": "https://acme.vercel.app",
        "production_branch": "master",
        "repo_branch": "cms-preview",
    }

    project = deps.require_project_access("acme", admin_user)

    select_arg = mock_supabase.select.call_args.args[0]
    assert "production_branch" in select_arg
    assert "production_url" in select_arg
    assert "repo_branch" in select_arg

    assert project["production_branch"] == "master"
    assert project["repo_branch"] == "cms-preview"
```

- [ ] **Step 7: Run + commit**

```bash
pytest auth_service/tests -v 2>&1 | tail -5
```

Expected: 113+ passed (1 new test).

```bash
git add backend/auth_service/core/config.py backend/auth_service/routers/deps.py backend/auth_service/tests/conftest.py backend/auth_service/tests/test_issues_router.py backend/auth_service/tests/test_deps.py
git commit -m "feat(config): declare Slack + GitHub envs + widen project SELECT for S1.5"
```

---

## Task 9: Slack handler — reaction (approve) flow

**Files:**
- Create: `backend/auth_service/services/slack_handler.py`
- Create: `backend/auth_service/tests/test_slack_handler.py`

- [ ] **Step 1: Write the failing tests (reaction flow only)**

Create `backend/auth_service/tests/test_slack_handler.py`:

```python
"""Slack inbound event handler unit tests — reaction approval flow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ..services import slack_handler


def _stefan() -> str:
    return "U_STEFAN"


def _bot() -> str:
    return "U_BOT"


def _channel() -> str:
    return "C_ISSUES"


def _issue_done() -> dict:
    return {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "Hero broken",
        "description": "stretches",
        "status": "done",
        "created_by": "client-uid",
        "slack_resolved_ts": "1715789123.001234",
    }


def _project() -> dict:
    return {
        "id": "project-acme",
        "slug": "acme",
        "name": "Acme",
        "github_repo": "stefan/acme",
        "repo_branch": "cms-preview",
        "production_branch": "master",
        "production_url": "https://acme.example.com",
    }


def _event_reaction(emoji: str = "white_check_mark", user: str | None = None) -> dict:
    return {
        "type": "reaction_added",
        "reaction": emoji,
        "user": user or _stefan(),
        "item": {"type": "message", "ts": "1715789123.001234", "channel": _channel()},
    }


@pytest.fixture
def slack_env(monkeypatch):
    monkeypatch.setattr(slack_handler.settings, "SLACK_ISSUES_CHANNEL_ID", _channel())
    monkeypatch.setattr(slack_handler.settings, "SLACK_APPROVER_USER_ID", _stefan())
    monkeypatch.setattr(slack_handler.settings, "SLACK_BOT_USER_ID", _bot())


def test_reaction_wrong_emoji_noop(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    with patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(_event_reaction(emoji="thumbsup"))
        ack.assert_not_called()


def test_reaction_wrong_channel_noop(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    event = _event_reaction()
    event["item"]["channel"] = "C_OTHER"
    with patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(event)
        ack.assert_not_called()


def test_reaction_unknown_message_noop(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: None)
    with patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(_event_reaction())
        ack.assert_not_called()


def test_reaction_wrong_user_warns_no_merge(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    with patch.object(slack_handler, "github_merge") as merge, \
         patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(_event_reaction(user="U_OTHER"))
        merge.fast_forward.assert_not_called()
        ack.assert_called_once()
        assert "Only Stefan" in ack.call_args.args[1]


def test_reaction_issue_not_done_warns(slack_env, monkeypatch):
    issue = _issue_done()
    issue["status"] = "pending"
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: issue)
    monkeypatch.setattr(slack_handler, "_get_project_full", lambda pid: _project())
    with patch.object(slack_handler, "github_merge") as merge, \
         patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(_event_reaction())
        merge.fast_forward.assert_not_called()
        ack.assert_called_once()
        assert "pending" in ack.call_args.args[1]


def test_reaction_happy_path(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    monkeypatch.setattr(slack_handler, "_get_project_full", lambda pid: _project())
    monkeypatch.setattr(slack_handler, "_email_for_user", lambda uid: "client@acme.com")
    monkeypatch.setattr(slack_handler, "_clear_revision_feedback", lambda iid: None)

    with patch.object(slack_handler.github_merge, "fast_forward",
                       return_value={"object": {"sha": "abc123def4567"}}) as merge, \
         patch.object(slack_handler.issue_resolved_email, "send",
                       return_value={"id": "email_1"}) as email, \
         patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(_event_reaction())

    merge.assert_called_once()
    kwargs = merge.call_args.kwargs
    assert kwargs["repo"] == "stefan/acme"
    assert kwargs["base_branch"] == "master"
    assert kwargs["head_branch"] == "cms-preview"

    email.assert_called_once()
    assert email.call_args.kwargs["to_email"] == "client@acme.com"

    ack.assert_called_once()
    text = ack.call_args.args[1]
    assert "🚀" in text
    assert "abc123d" in text  # short SHA prefix


def test_reaction_merge_diverged_posts_failure_no_email(slack_env, monkeypatch):
    from ..services.github_merge import GitHubError

    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    monkeypatch.setattr(slack_handler, "_get_project_full", lambda pid: _project())

    with patch.object(slack_handler.github_merge, "fast_forward",
                       side_effect=GitHubError("diverged")) as merge, \
         patch.object(slack_handler.issue_resolved_email, "send") as email, \
         patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(_event_reaction())

    merge.assert_called_once()
    email.assert_not_called()
    ack.assert_called_once()
    assert "❌" in ack.call_args.args[1]
    assert "diverged" in ack.call_args.args[1]


def test_reaction_email_failure_partial_success(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    monkeypatch.setattr(slack_handler, "_get_project_full", lambda pid: _project())
    monkeypatch.setattr(slack_handler, "_email_for_user", lambda uid: "client@acme.com")

    with patch.object(slack_handler.github_merge, "fast_forward",
                       return_value={"object": {"sha": "abc"}}), \
         patch.object(slack_handler.issue_resolved_email, "send",
                       side_effect=RuntimeError("resend down")), \
         patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(_event_reaction())

    ack.assert_called_once()
    text = ack.call_args.args[1]
    assert "⚠️" in text
    assert "email" in text.lower()
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest auth_service/tests/test_slack_handler.py -v
```

Expected: collection error.

- [ ] **Step 3: Implement the handler module (reaction half only)**

Create `backend/auth_service/services/slack_handler.py`:

```python
"""Slack Events API handlers — reaction (approve) + message (revision) flows."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from ..core.config import settings
from . import github_merge, issue_resolved_email, slack_notify
from .supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)


def handle_reaction_added(event: dict) -> None:
    """Stefan ✅ on a tracked resolved-issue message → publish + email."""
    if event.get("reaction") != "white_check_mark":
        return

    item = event.get("item", {})
    if item.get("type") != "message":
        return

    msg_ts = item.get("ts")
    channel = item.get("channel")
    if not msg_ts or channel != settings.SLACK_ISSUES_CHANNEL_ID:
        return

    issue = _find_issue_by_slack_ts(msg_ts)
    if not issue:
        logger.info("reaction on untracked message ts=%s — ignoring", msg_ts)
        return

    if event.get("user") != settings.SLACK_APPROVER_USER_ID:
        _post_thread_reply(msg_ts, "⚠️ Only Stefan can approve. Reaction ignored.")
        return

    if issue["status"] != "done":
        _post_thread_reply(msg_ts, f"⚠️ Issue is `{issue['status']}` — cannot approve.")
        return

    project = _get_project_full(issue["project_id"])

    try:
        merge_result = github_merge.fast_forward(
            repo=project["github_repo"],
            base_branch=project["production_branch"],
            head_branch=project["repo_branch"],
        )
    except github_merge.GitHubError as e:
        _post_thread_reply(msg_ts, f"❌ Production merge failed: {e}")
        return

    try:
        issue_resolved_email.send(
            to_email=_email_for_user(issue["created_by"]),
            issue=issue,
            project=project,
        )
    except Exception:
        logger.exception("client email failed but production merge succeeded")
        _post_thread_reply(
            msg_ts,
            f"⚠️ Merged to `{project['production_branch']}` but email failed. "
            f"Notify client manually. Deployment: {project.get('production_url') or '(unknown)'}",
        )
        return

    _clear_revision_feedback(issue["id"])

    sha = merge_result.get("object", {}).get("sha", "?")[:7]
    _post_thread_reply(
        msg_ts,
        f"🚀 *Promoted to production.*\n"
        f"• Merged `{project['repo_branch']}` → `{project['production_branch']}` (SHA `{sha}`)\n"
        f"• Email sent to client\n"
        f"• Production: {project.get('production_url') or '(deploy in progress)'}",
    )


# ── private helpers ──────────────────────────────────────────────────────────


def _find_issue_by_slack_ts(ts: str) -> dict | None:
    sb = get_supabase_admin()
    result = (
        sb.table("project_issues")
        .select("id, project_id, title, description, status, created_by, slack_resolved_ts")
        .eq("slack_resolved_ts", ts)
        .maybe_single()
        .execute()
    )
    return result.data


def _get_project_full(project_id: str) -> dict:
    sb = get_supabase_admin()
    result = (
        sb.table("projects")
        .select("id, name, slug, github_repo, repo_branch, production_branch, production_url, user_id")
        .eq("id", project_id)
        .single()
        .execute()
    )
    return result.data or {}


def _email_for_user(user_id: str | None) -> str:
    if not user_id:
        return ""
    sb = get_supabase_admin()
    result = (
        sb.table("users")
        .select("email")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return (result.data or {}).get("email", "") if result else ""


def _clear_revision_feedback(issue_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("project_issues").update(
        {"revision_feedback": None, "revision_feedback_at": None}
    ).eq("id", issue_id).execute()


def _post_thread_reply(thread_ts: str, text: str) -> None:
    slack_notify.post_thread_reply(thread_ts=thread_ts, text=text)
```

- [ ] **Step 4: Run reaction tests**

```bash
pytest auth_service/tests/test_slack_handler.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/slack_handler.py backend/auth_service/tests/test_slack_handler.py
git commit -m "feat(slack): add reaction-added handler for approval flow"
```

---

## Task 10: Slack handler — message (revision) flow

**Files:**
- Modify: `backend/auth_service/services/slack_handler.py`
- Modify: `backend/auth_service/tests/test_slack_handler.py`

- [ ] **Step 1: Append failing tests**

Add to `backend/auth_service/tests/test_slack_handler.py`:

```python
def _event_message(*, user: str | None = None, text: str = "fix the spacing on hero", thread_ts: str = "1715789123.001234", subtype: str | None = None, bot_id: str | None = None) -> dict:
    event: dict = {
        "type": "message",
        "user": user or _stefan(),
        "text": text,
        "thread_ts": thread_ts,
        "channel": _channel(),
    }
    if subtype:
        event["subtype"] = subtype
    if bot_id:
        event["bot_id"] = bot_id
    return event


def test_message_bot_subtype_noop(slack_env):
    with patch.object(slack_handler, "_find_issue_by_slack_ts") as lookup:
        slack_handler.handle_message(_event_message(subtype="bot_message"))
        lookup.assert_not_called()


def test_message_bot_id_noop(slack_env):
    with patch.object(slack_handler, "_find_issue_by_slack_ts") as lookup:
        slack_handler.handle_message(_event_message(bot_id="B123"))
        lookup.assert_not_called()


def test_message_from_bot_user_noop(slack_env):
    with patch.object(slack_handler, "_find_issue_by_slack_ts") as lookup:
        slack_handler.handle_message(_event_message(user=_bot()))
        lookup.assert_not_called()


def test_message_top_level_no_thread_noop(slack_env):
    event = _event_message()
    del event["thread_ts"]
    with patch.object(slack_handler, "_find_issue_by_slack_ts") as lookup:
        slack_handler.handle_message(event)
        lookup.assert_not_called()


def test_message_unknown_thread_noop(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: None)
    with patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_message(_event_message())
        ack.assert_not_called()


def test_message_wrong_user_noop(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    with patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_message(_event_message(user="U_RANDO"))
        ack.assert_not_called()


def test_message_status_not_done_warns(slack_env, monkeypatch):
    issue = _issue_done()
    issue["status"] = "in_progress"
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: issue)
    with patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_message(_event_message())
        ack.assert_called_once()
        assert "in_progress" in ack.call_args.args[1]


def test_message_too_short_noop(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    with patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_message(_event_message(text="ok"))
        ack.assert_not_called()


def test_message_happy_path_reverts_status(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())

    updates: list[dict] = []
    fake_sb = MagicMock()
    for m in ("table", "update", "eq", "execute"):
        getattr(fake_sb, m).return_value = fake_sb

    def capture_update(payload):
        updates.append(payload)
        return fake_sb

    fake_sb.update = capture_update

    with patch.object(slack_handler, "get_supabase_admin", return_value=fake_sb), \
         patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_message(_event_message(text="please fix the spacing on hero, looks tight"))

    assert len(updates) == 1
    update = updates[0]
    assert update["status"] == "in_progress"
    assert "please fix the spacing" in update["revision_feedback"]
    assert update["revision_feedback_at"]

    ack.assert_called_once()
    text = ack.call_args.args[1]
    assert "📝" in text
    assert "please fix the spacing" in text
    assert "in_progress" in text


def test_message_long_feedback_truncated_in_ack(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    long_text = "needs revision " * 30  # ~450 chars

    fake_sb = MagicMock()
    for m in ("table", "update", "eq", "execute"):
        getattr(fake_sb, m).return_value = fake_sb

    with patch.object(slack_handler, "get_supabase_admin", return_value=fake_sb), \
         patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_message(_event_message(text=long_text))

    text = ack.call_args.args[1]
    assert "…" in text  # truncation marker
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest auth_service/tests/test_slack_handler.py -v -k "message"
```

Expected: 10 failures (no `handle_message` yet).

- [ ] **Step 3: Implement `handle_message`**

Append to `backend/auth_service/services/slack_handler.py` (before the private-helpers section):

```python
def handle_message(event: dict) -> None:
    """Stefan replies in the resolved-issue thread → revert + store feedback."""
    if event.get("subtype") == "bot_message":
        return
    if event.get("bot_id") or event.get("user") == settings.SLACK_BOT_USER_ID:
        return

    channel = event.get("channel")
    thread_ts = event.get("thread_ts")
    text = (event.get("text") or "").strip()

    if channel != settings.SLACK_ISSUES_CHANNEL_ID or not thread_ts:
        return

    issue = _find_issue_by_slack_ts(thread_ts)
    if not issue:
        return

    if event.get("user") != settings.SLACK_APPROVER_USER_ID:
        return

    if issue["status"] != "done":
        _post_thread_reply(
            thread_ts,
            f"⚠️ Issue is `{issue['status']}` — cannot mark as needs revision.",
        )
        return

    if len(text) < 5:
        return

    sb = get_supabase_admin()
    sb.table("project_issues").update(
        {
            "status": "in_progress",
            "revision_feedback": text,
            "revision_feedback_at": datetime.now(UTC).isoformat(),
        }
    ).eq("id", issue["id"]).execute()

    excerpt = text[:120] + ("…" if len(text) > 120 else "")
    _post_thread_reply(
        thread_ts,
        f"📝 *Marked as needs revision.*\n> {excerpt}\n\n"
        f"Issue moved back to `in_progress`. Fix on `cms-preview` and "
        f"mark done again to re-trigger approval.",
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest auth_service/tests/test_slack_handler.py -v
```

Expected: 18 passed (8 reaction + 10 message).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/slack_handler.py backend/auth_service/tests/test_slack_handler.py
git commit -m "feat(slack): add message-thread-reply handler for revision flow"
```

---

## Task 11: `/slack/events` router endpoint

**Files:**
- Create: `backend/auth_service/routers/slack_events.py`
- Create: `backend/auth_service/tests/test_slack_events_router.py`
- Modify: `backend/auth_service/main.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/auth_service/tests/test_slack_events_router.py`:

```python
"""Integration tests for POST /slack/events."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import patch


def _sign(body: bytes, ts: str, secret: str) -> str:
    base = f"v0:{ts}:{body.decode()}".encode()
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


def test_url_verification_returns_challenge(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")

    payload = {"type": "url_verification", "challenge": "abc123"}
    body = json.dumps(payload).encode()

    # url_verification doesn't require HMAC per Slack docs (bootstrap event)
    resp = client.post("/slack/events", content=body, headers={"content-type": "application/json"})
    assert resp.status_code == 200
    assert resp.text == "abc123"


def test_bad_signature_returns_401(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")

    payload = {"type": "event_callback", "event": {"type": "reaction_added"}, "event_id": "Ev1"}
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": "v0=deadbeef",
        },
    )
    assert resp.status_code == 401


def test_reaction_event_dispatched(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.already_processed",
        lambda eid: False,
    )
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.mark_processed",
        lambda eid: None,
    )

    payload = {
        "type": "event_callback",
        "event_id": "Ev_REACT_1",
        "event": {"type": "reaction_added", "reaction": "white_check_mark"},
    }
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = _sign(body, ts, "secret")

    called: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_handler.handle_reaction_added",
        lambda event: called.append(event),
    )

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        },
    )
    assert resp.status_code == 200
    assert len(called) == 1
    assert called[0]["type"] == "reaction_added"


def test_message_event_dispatched(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.already_processed",
        lambda eid: False,
    )
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.mark_processed",
        lambda eid: None,
    )

    payload = {
        "type": "event_callback",
        "event_id": "Ev_MSG_1",
        "event": {"type": "message", "text": "hi"},
    }
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = _sign(body, ts, "secret")

    called: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_handler.handle_message",
        lambda event: called.append(event),
    )

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        },
    )
    assert resp.status_code == 200
    assert len(called) == 1


def test_duplicate_event_id_short_circuits(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.already_processed",
        lambda eid: True,
    )

    payload = {
        "type": "event_callback",
        "event_id": "Ev_DUP",
        "event": {"type": "reaction_added"},
    }
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = _sign(body, ts, "secret")

    called: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_handler.handle_reaction_added",
        lambda event: called.append(event),
    )

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        },
    )
    assert resp.status_code == 200
    assert called == []  # not dispatched


def test_unknown_event_type_returns_200(client, monkeypatch):
    from auth_service.core import config

    monkeypatch.setattr(config.settings, "SLACK_SIGNING_SECRET", "secret")
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.already_processed",
        lambda eid: False,
    )
    monkeypatch.setattr(
        "auth_service.routers.slack_events.slack_events_dedup.mark_processed",
        lambda eid: None,
    )

    payload = {
        "type": "event_callback",
        "event_id": "Ev_UNK",
        "event": {"type": "team_join"},
    }
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = _sign(body, ts, "secret")

    resp = client.post(
        "/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": sig,
        },
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest auth_service/tests/test_slack_events_router.py -v
```

Expected: collection error or 404 (route doesn't exist).

- [ ] **Step 3: Implement the router**

Create `backend/auth_service/routers/slack_events.py`:

```python
"""Slack Events API endpoint.

Receives reaction_added + message events from Slack and dispatches to
slack_handler. All requests pass HMAC verification (except the one-time
url_verification challenge sent during Slack app setup).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response, status

from ..core.config import settings
from ..services import slack_events_dedup, slack_handler, slack_signature

router = APIRouter(tags=["slack"])
logger = logging.getLogger(__name__)


@router.post("/slack/events")
async def slack_events(request: Request) -> Response:
    body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    # URL verification challenge — one-shot during Slack app setup.
    # Slack docs say no signature is required on this single event.
    if payload.get("type") == "url_verification":
        return Response(content=payload.get("challenge", ""), media_type="text/plain")

    ts = request.headers.get("x-slack-request-timestamp", "")
    sig = request.headers.get("x-slack-signature", "")
    if not slack_signature.verify(ts, body, sig, settings.SLACK_SIGNING_SECRET):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    event_id = payload.get("event_id")
    if event_id and slack_events_dedup.already_processed(event_id):
        return Response(status_code=status.HTTP_200_OK)
    if event_id:
        slack_events_dedup.mark_processed(event_id)

    event = payload.get("event") or {}
    event_type = event.get("type")

    try:
        if event_type == "reaction_added":
            slack_handler.handle_reaction_added(event)
        elif event_type == "message":
            slack_handler.handle_message(event)
        # unknown types: silently ignored
    except Exception:
        # Handlers are expected to swallow internally; this is paranoid.
        logger.exception("slack event handler raised; returning 200 anyway")

    return Response(status_code=status.HTTP_200_OK)
```

- [ ] **Step 4: Register router in `main.py`**

In `backend/auth_service/main.py`, find:

```python
from .routers import auth, content, projects, publish, workspace  # noqa: E402
from .routers.forms import router as forms_router  # noqa: E402
from .routers.issues import router as issues_router  # noqa: E402
```

Add a new import line:

```python
from .routers.slack_events import router as slack_events_router  # noqa: E402
```

Find the `app.include_router(...)` block (around line 127-132) and append:

```python
app.include_router(slack_events_router)
```

- [ ] **Step 5: Run tests**

```bash
pytest auth_service/tests/test_slack_events_router.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Run full suite**

```bash
pytest auth_service/tests -v 2>&1 | tail -10
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/auth_service/routers/slack_events.py backend/auth_service/main.py backend/auth_service/tests/test_slack_events_router.py
git commit -m "feat(slack): add /slack/events endpoint with HMAC + dedup"
```

---

## Task 12: Documentation updates

**Files:**
- Modify: `docs/ENVIRONMENTS.md`
- Modify: `docs/ONBOARDING.md`

- [ ] **Step 1: Add env vars to `docs/ENVIRONMENTS.md`**

Find the backend env-var table. Append rows (matching existing column format):

```markdown
| `SLACK_SIGNING_SECRET`     | optional   | HMAC secret from Slack app → Basic Information. Required for `/slack/events` to accept any event; if unset, all signed events 401. |
| `SLACK_APPROVER_USER_ID`   | optional   | Stefan's Slack member ID (`U...`). Pins who can approve via ✅ or submit revisions via thread reply. |
| `SLACK_BOT_USER_ID`        | optional   | CMS Issues Bot's user ID. Used by message handler to ignore bot's own replies (loop guard). |
| `GITHUB_TOKEN`             | optional   | PAT with `repo` scope. Required for ✅ approval to fast-forward `master` to `cms-preview`. Reuses CMS Connector agent's token. |
```

- [ ] **Step 2: Add S1.5 setup section to `docs/ONBOARDING.md`**

After the existing "Slack Issue Notifications" section, add:

```markdown
## Slack Approval & Revision (S1.5)

S1 posts notifications; S1.5 listens for Stefan's response in `#issues-websites`. A ✅ reaction on a resolved-issue Slack message merges `cms-preview → master` of the client repo (triggering a Vercel production deploy) and emails the client. A threaded text reply (≥5 chars) reverts the issue to `in_progress` and stores Stefan's feedback for later S3 use.

### One-time additions to the Slack app

1. https://api.slack.com/apps → CMS Issues Bot → **OAuth & Permissions** → Bot Token Scopes → add `reactions:read` and `channels:history`.
2. Click **Reinstall to Workspace** → approve. Copy the new `xoxb-...` token (the old one is revoked). Update `SLACK_BOT_TOKEN` in `backend/.env` and Vercel envs.
3. **Basic Information** → App Credentials → copy the **Signing Secret** → set as `SLACK_SIGNING_SECRET`.
4. **Event Subscriptions** → Enable → Request URL: `https://cms-backend-roman.vercel.app/slack/events` (deploy the backend with the new router first, otherwise Slack's verification ping fails). Subscribe to bot events: `reaction_added`, `message.channels`. Save.

### One-time GitHub PAT

Reuse the CMS Connector agent's PAT (`repo` scope) or create a new one at https://github.com/settings/tokens. Set as `GITHUB_TOKEN` env var (backend + Vercel).

### Slack user IDs

In Slack desktop, click your profile → **Copy member ID** for `SLACK_APPROVER_USER_ID`. For `SLACK_BOT_USER_ID`, in the Slack app dashboard go to OAuth & Permissions and copy the Bot User ID shown near the bot user setting.
```

- [ ] **Step 3: Commit**

```bash
git add docs/ENVIRONMENTS.md docs/ONBOARDING.md
git commit -m "docs: document S1.5 Slack approval + GitHub PAT setup"
```

---

## Task 13: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests -v 2>&1 | tail -15
```

Expected: all tests pass (S1's 112 + S1.5 additions).

- [ ] **Step 2: Ruff check**

```bash
ruff check auth_service/ 2>&1 | tail -5
```

Expected: clean for files we touched.

- [ ] **Step 3: Verify migration NOT applied yet**

Migration file exists at `backend/migrations/2026_05_15_slack_inbound_s1_5.sql` but has not been run. The user will apply it via Supabase MCP.

- [ ] **Step 4: Manual smoke (post-deploy only — flag for user)**

After merge + Vercel envs set + Slack app reconfigured:

1. Submit issue via dashboard, mark done. Verify "Issue Resolved" Slack message appears AND `project_issues.slack_resolved_ts` is populated.
2. React ✅ on that message. Verify: `master` of client repo fast-forwards to `cms-preview` (check via `gh api repos/<owner>/<repo>/branches`), Resend email lands in client inbox, "🚀 Promoted to production" appears in thread.
3. Submit another issue, mark done. In the resolved-message thread, reply: `please fix the spacing on the hero, it's too tight`. Verify: issue back to `in_progress`, `revision_feedback` populated, "📝 Marked as needs revision" appears in thread.

- [ ] **Step 5: Open PR**

```bash
git push -u origin feat/slack-issue-approval-publish
gh pr create --base dev --title "feat(s1.5): Slack approval + production publish + client email" --body "$(cat <<'EOF'
## Summary
- ✅ reaction on resolved-issue Slack message → GitHub fast-forward `cms-preview → master` + Resend email to client + Slack thread ack
- Text reply in same thread → revert issue to `in_progress` + store `revision_feedback` + Slack thread ack
- New `/slack/events` endpoint with HMAC verification + idempotency

## Migration
`backend/migrations/2026_05_15_slack_inbound_s1_5.sql` — apply via Supabase MCP before merge:
- New columns: `project_issues.slack_resolved_ts`, `revision_feedback`, `revision_feedback_at`
- New column: `projects.production_branch` (default `master`)
- Data fix: `repo_branch` updated from `dev` → `cms-preview` for real repos
- New table: `slack_processed_events` (idempotency)

## Vercel envs to set before merge
- `SLACK_SIGNING_SECRET` (from Slack app Basic Information)
- `SLACK_APPROVER_USER_ID` (Stefan's Slack member ID)
- `SLACK_BOT_USER_ID` (CMS Issues Bot user ID)
- `GITHUB_TOKEN` (PAT with `repo` scope)
- Update `SLACK_BOT_TOKEN` after Slack app re-install (new scopes invalidate old token)

## Test plan
- [ ] `pytest auth_service/tests` green
- [ ] Migration applied
- [ ] Slack app reconfigured (scopes + event subs + reinstall)
- [ ] Vercel envs set on preview + production
- [ ] Smoke: ✅ react → master updated, email arrives, Slack ack
- [ ] Smoke: text reply → issue reverts, ack appears

Spec: `docs/superpowers/specs/2026-05-15-slack-issue-approval-publish-design.md`
EOF
)"
```

Note: PR base is `dev` (project convention), not `master`.

---

## Self-Review

### Spec coverage
- Architecture (router + handler split) → Tasks 9, 10, 11
- Data model (3 issue cols, 1 project col, idempotency table, repo_branch fix) → Task 1
- Slack scopes + signing secret + event subscriptions → Task 12 docs
- HMAC verification → Task 2
- Idempotency → Task 3
- Reaction handler (approve) → Task 9
- Message handler (revision) → Task 10
- GitHub fast-forward → Task 4
- Resend email with branded HTML → Task 5
- `slack_resolved_ts` persistence → Tasks 6 (return ts) + 7 (persist)
- Env vars → Task 8 + Task 12
- `production_branch` widening of `require_project_access` → Task 8
- Error handling matrix → Task 9 (reaction failure cases tested)
- Test coverage (unit + integration) → distributed across tasks; manual E2E in Task 13

### Placeholder scan
- No "TBD" / "TODO" remaining.
- Each step has either complete code or a precise CLI command + expected output.
- Slack user-IDs in tests are constants (`U_STEFAN`, `U_BOT`, `C_ISSUES`) so the engineer doesn't need to substitute.

### Type consistency
- `notify_issue_resolved` and `notify_issue_created` both return `str | None` (Task 6).
- `post_thread_reply` returns `str | None` (Task 6).
- `github_merge.fast_forward(*, repo, base_branch, head_branch)` keyword-only signature consistent across Tasks 4, 9.
- `issue_resolved_email.send(*, to_email, issue, project)` keyword-only signature consistent across Tasks 5, 9.
- `slack_handler._post_thread_reply(thread_ts, text)` positional signature consistent across Task 9, 10, and tests.
- `slack_events_dedup.already_processed(event_id)` / `mark_processed(event_id)` consistent in Tasks 3, 11.

No drift detected.
