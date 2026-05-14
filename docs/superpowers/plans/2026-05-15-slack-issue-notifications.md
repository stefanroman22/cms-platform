# Slack Issue Notifications (S1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend posts a Slack message to `#issues-websites` when a client submits an issue and when an admin marks one resolved.

**Architecture:** New `services/slack_notify.py` module with two pure functions (`notify_issue_created`, `notify_issue_resolved`). Called inline from `routers/issues.py` after Supabase write. Failures swallowed. Slack credentials via env (`SLACK_BOT_TOKEN`, `SLACK_ISSUES_CHANNEL_ID`). One DB column added: `projects.repo_branch`.

**Tech Stack:** FastAPI, Python 3.13, httpx (sync), pytest, Supabase, Slack Web API (`chat.postMessage`).

**Spec:** `docs/superpowers/specs/2026-05-15-slack-issue-notifications-design.md`

---

## File Structure

**Create:**
- `backend/migrations/2026_05_15_projects_repo_branch.sql` — single ALTER TABLE.
- `backend/auth_service/services/slack_notify.py` — Slack post helpers, ~120 lines.
- `backend/auth_service/tests/test_slack_notify.py` — unit tests for the service.
- `backend/auth_service/tests/test_issues_router.py` — integration tests for `routers/issues.py` (no test file exists today).

**Modify:**
- `backend/auth_service/routers/issues.py` — wire notifications into 2 handlers.
- `backend/auth_service/tests/conftest.py` — extend `mock_supabase` + `auth_as` to cover issues router.
- `docs/ENVIRONMENTS.md` — document 3 new env vars.
- `docs/ONBOARDING.md` — add Slack app setup section.
- `docs/DEVELOPMENT.md` — note disabled-mode behavior.

---

## Task 1: DB migration — add `repo_branch` to `projects`

**Files:**
- Create: `backend/migrations/2026_05_15_projects_repo_branch.sql`

- [ ] **Step 1: Write the migration**

Create `backend/migrations/2026_05_15_projects_repo_branch.sql`:

```sql
-- 2026_05_15 — projects.repo_branch
-- Adds the branch name agents (S3) will push fixes to. Defaults to 'dev'
-- because that's the preview-deploy branch in this project's workflow.
-- RLS: covered by existing projects_owner_* policies; no new policy needed.

ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS repo_branch TEXT NOT NULL DEFAULT 'dev';

COMMENT ON COLUMN projects.repo_branch IS
  'Git branch the issue-solver agent pushes fixes to (dev = preview deploy).';
```

- [ ] **Step 2: Apply the migration to local Supabase**

Run via Supabase MCP `apply_migration` OR psql against local DB:

```bash
# If using local supabase CLI:
supabase db push

# OR via MCP / SQL editor: paste the file contents.
```

Expected: no error. New column appears on `projects`.

- [ ] **Step 3: Verify column exists**

Run via Supabase SQL:

```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'projects' AND column_name = 'repo_branch';
```

Expected output: one row, `text`, default `'dev'::text`.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/2026_05_15_projects_repo_branch.sql
git commit -m "feat(db): add projects.repo_branch for issue solver agent"
```

---

## Task 2: Service module skeleton + disabled-mode test

**Files:**
- Create: `backend/auth_service/services/slack_notify.py`
- Create: `backend/auth_service/tests/test_slack_notify.py`

- [ ] **Step 1: Write the failing test**

Create `backend/auth_service/tests/test_slack_notify.py`:

```python
"""Unit tests for slack_notify service."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from ..services import slack_notify


def test_disabled_when_env_missing(monkeypatch):
    """No token + no channel → no HTTP call made."""
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ISSUES_CHANNEL_ID", raising=False)

    with patch.object(slack_notify, "httpx") as mock_httpx:
        slack_notify.notify_issue_created(
            issue={
                "id": "i1",
                "title": "Hero broken",
                "description": "stretches",
                "priority": "High",
                "created_at": "2026-05-15T10:00:00Z",
            },
            project={
                "id": "p1",
                "slug": "acme",
                "name": "Acme",
                "github_repo": "github.com/x/acme",
                "repo_branch": "dev",
            },
            user_email="client@acme.com",
        )
        mock_httpx.post.assert_not_called()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests/test_slack_notify.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'auth_service.services.slack_notify'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/auth_service/services/slack_notify.py`:

```python
"""Slack notifications for project issues (outbound only).

Posts to `chat.postMessage` when an issue is created or resolved.
Disabled silently when env is unset; failures are logged but never
re-raised — Slack outages must not break issue create/update.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api/chat.postMessage"
_TIMEOUT_S = 5.0


def _enabled() -> bool:
    return bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_ISSUES_CHANNEL_ID"))


def notify_issue_created(
    issue: dict[str, Any], project: dict[str, Any], user_email: str | None
) -> None:
    if not _enabled():
        logger.info("slack_notify disabled (no token/channel) — skipping created")
        return
    # Real implementation arrives in later tasks.
    return


def notify_issue_resolved(
    issue: dict[str, Any], project: dict[str, Any], resolver_email: str | None
) -> None:
    if not _enabled():
        logger.info("slack_notify disabled (no token/channel) — skipping resolved")
        return
    return
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest auth_service/tests/test_slack_notify.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/slack_notify.py backend/auth_service/tests/test_slack_notify.py
git commit -m "feat(slack): add slack_notify service skeleton with disabled-mode"
```

---

## Task 3: Build "issue created" Block Kit + payload test

**Files:**
- Modify: `backend/auth_service/services/slack_notify.py`
- Modify: `backend/auth_service/tests/test_slack_notify.py`

- [ ] **Step 1: Write the failing test (append to test file)**

Add to `backend/auth_service/tests/test_slack_notify.py`:

```python
def _sample_issue() -> dict:
    return {
        "id": "i1",
        "title": "Hero image broken on mobile",
        "description": "Image stretches off-screen on iPhone Safari 17.",
        "priority": "High",
        "created_at": "2026-05-15T10:00:00Z",
    }


def _sample_project() -> dict:
    return {
        "id": "p1",
        "slug": "acme-site",
        "name": "Acme Site",
        "github_repo": "https://github.com/stefan/acme-site",
        "repo_branch": "dev",
        "preview_url": "https://acme-site-dev.vercel.app",
    }


def test_created_posts_to_slack_with_expected_payload(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")
    monkeypatch.setenv("CMS_DASHBOARD_URL", "https://cms.example.com")

    captured = {}

    class _OkResp:
        def json(self):
            return {"ok": True}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _OkResp()

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        slack_notify.notify_issue_created(
            issue=_sample_issue(),
            project=_sample_project(),
            user_email="client@acme.com",
        )

    assert captured["url"] == slack_notify.SLACK_API
    assert captured["headers"]["Authorization"] == "Bearer xoxb-test"
    assert captured["timeout"] == 5.0

    body = captured["json"]
    assert body["channel"] == "C123"
    assert "New issue" in body["text"]
    assert "acme-site" in body["text"]
    assert "Hero image broken on mobile" in body["text"]

    # Block kit content: title, priority, submitter, project line, repo line, description, button
    blocks_text = str(body["blocks"])
    assert "Hero image broken on mobile" in blocks_text
    assert "High" in blocks_text
    assert "client@acme.com" in blocks_text
    assert "acme-site" in blocks_text
    assert "dev" in blocks_text
    assert "github.com/stefan/acme-site" in blocks_text
    assert "Image stretches" in blocks_text
    assert "https://cms.example.com" in blocks_text  # dashboard link
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest auth_service/tests/test_slack_notify.py::test_created_posts_to_slack_with_expected_payload -v
```

Expected: FAIL — `notify_issue_created` returns without posting.

- [ ] **Step 3: Implement `_post` + `_build_created_blocks` + wire `notify_issue_created`**

Replace the body of `backend/auth_service/services/slack_notify.py` with the fuller version:

```python
"""Slack notifications for project issues (outbound only).

Posts to `chat.postMessage` when an issue is created or resolved.
Disabled silently when env is unset; failures are logged but never
re-raised — Slack outages must not break issue create/update.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api/chat.postMessage"
_TIMEOUT_S = 5.0

_PRIORITY_EMOJI = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}


def _enabled() -> bool:
    return bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_ISSUES_CHANNEL_ID"))


def _dashboard_url() -> str:
    return os.getenv("CMS_DASHBOARD_URL", "https://roman-technologies.dev").rstrip("/")


def _truncate(text: str, limit: int = 500) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _post(blocks: list[dict], text_fallback: str) -> None:
    """POST one message to Slack. Swallow all errors."""
    if not _enabled():
        logger.info("slack_notify disabled — skipping")
        return
    try:
        resp = httpx.post(
            SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
                "text": text_fallback,
                "blocks": blocks,
            },
            timeout=_TIMEOUT_S,
        )
        body = resp.json()
        if not body.get("ok"):
            logger.warning("slack_notify api error: %s", body.get("error"))
    except Exception:
        logger.exception("slack_notify post failed")


def _build_created_blocks(
    issue: dict[str, Any], project: dict[str, Any], user_email: str | None
) -> list[dict]:
    project_name = project.get("name") or project.get("slug", "unknown")
    slug = project.get("slug", "unknown")
    branch = project.get("repo_branch", "dev")
    repo = project.get("github_repo") or "(repo not set)"
    priority = issue.get("priority", "Medium")
    emoji = _PRIORITY_EMOJI.get(priority, "⚪")
    desc = _truncate(issue.get("description", ""))
    dashboard = f"{_dashboard_url()}/dashboard/projects/{slug}/issues/{issue['id']}"

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🆕 New Issue — {project_name}", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Title:*\n{issue['title']}"},
                {"type": "mrkdwn", "text": f"*Priority:*\n{emoji} {priority}"},
                {"type": "mrkdwn", "text": f"*Submitted by:*\n{user_email or 'unknown'}"},
                {"type": "mrkdwn", "text": f"*Project:*\n{slug} (branch: {branch})"},
                {"type": "mrkdwn", "text": f"*Repo:*\n{repo}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Description:*\n>{desc.replace(chr(10), chr(10) + '>')}"},
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Open in CMS"},
                    "url": dashboard,
                }
            ],
        },
    ]


def notify_issue_created(
    issue: dict[str, Any], project: dict[str, Any], user_email: str | None
) -> None:
    if not _enabled():
        logger.info("slack_notify disabled — skipping created")
        return
    blocks = _build_created_blocks(issue, project, user_email)
    fallback = f"New issue [{project.get('slug', '?')}]: {issue['title']}"
    _post(blocks, fallback)


def notify_issue_resolved(
    issue: dict[str, Any], project: dict[str, Any], resolver_email: str | None
) -> None:
    if not _enabled():
        logger.info("slack_notify disabled — skipping resolved")
        return
    # Implemented in Task 4.
    return
```

- [ ] **Step 4: Run the tests**

```bash
pytest auth_service/tests/test_slack_notify.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/slack_notify.py backend/auth_service/tests/test_slack_notify.py
git commit -m "feat(slack): post block-kit message on issue created"
```

---

## Task 4: Build "issue resolved" Block Kit + payload test

**Files:**
- Modify: `backend/auth_service/services/slack_notify.py`
- Modify: `backend/auth_service/tests/test_slack_notify.py`

- [ ] **Step 1: Append failing test**

Add to `backend/auth_service/tests/test_slack_notify.py`:

```python
def test_resolved_posts_to_slack_with_expected_payload(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")
    monkeypatch.setenv("CMS_DASHBOARD_URL", "https://cms.example.com")

    captured = {}

    class _OkResp:
        def json(self):
            return {"ok": True}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return _OkResp()

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        slack_notify.notify_issue_resolved(
            issue=_sample_issue(),
            project=_sample_project(),
            resolver_email="stefan@example.com",
        )

    body = captured["json"]
    assert "Resolved" in body["text"]
    assert "acme-site" in body["text"]

    blocks_text = str(body["blocks"])
    assert "Issue Resolved" in blocks_text
    assert "Hero image broken on mobile" in blocks_text
    assert "stefan@example.com" in blocks_text
    assert "https://acme-site-dev.vercel.app" in blocks_text  # preview URL
    assert "https://cms.example.com" in blocks_text  # dashboard link


def test_resolved_no_preview_url_omits_preview_section(monkeypatch):
    """Project without preview_url should still produce a valid message."""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    project = _sample_project()
    project["preview_url"] = None

    captured = {}

    class _OkResp:
        def json(self):
            return {"ok": True}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return _OkResp()

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        slack_notify.notify_issue_resolved(
            issue=_sample_issue(),
            project=project,
            resolver_email="stefan@example.com",
        )

    blocks_text = str(captured["json"]["blocks"])
    assert "preview not configured" in blocks_text.lower()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest auth_service/tests/test_slack_notify.py::test_resolved_posts_to_slack_with_expected_payload -v
```

Expected: FAIL — `notify_issue_resolved` no-ops.

- [ ] **Step 3: Implement `_build_resolved_blocks` + wire `notify_issue_resolved`**

In `backend/auth_service/services/slack_notify.py`, add helper above `notify_issue_resolved` and replace its body:

```python
def _build_resolved_blocks(
    issue: dict[str, Any], project: dict[str, Any], resolver_email: str | None
) -> list[dict]:
    project_name = project.get("name") or project.get("slug", "unknown")
    slug = project.get("slug", "unknown")
    preview = project.get("preview_url")
    dashboard = f"{_dashboard_url()}/dashboard/projects/{slug}/issues/{issue['id']}"

    preview_line = preview if preview else "_(preview not configured)_"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"✅ Issue Resolved — {project_name}", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Title:*\n{issue['title']}"},
                {"type": "mrkdwn", "text": f"*Resolved by:*\n{resolver_email or 'unknown'}"},
                {"type": "mrkdwn", "text": f"*Preview:*\n{preview_line}"},
            ],
        },
    ]

    action_elements: list[dict] = []
    if preview:
        action_elements.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Open Preview"},
                "url": preview,
            }
        )
    action_elements.append(
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Open in CMS"},
            "url": dashboard,
        }
    )
    blocks.append({"type": "actions", "elements": action_elements})
    return blocks


def notify_issue_resolved(
    issue: dict[str, Any], project: dict[str, Any], resolver_email: str | None
) -> None:
    if not _enabled():
        logger.info("slack_notify disabled — skipping resolved")
        return
    blocks = _build_resolved_blocks(issue, project, resolver_email)
    fallback = f"Resolved [{project.get('slug', '?')}]: {issue['title']}"
    _post(blocks, fallback)
```

- [ ] **Step 4: Run the tests**

```bash
pytest auth_service/tests/test_slack_notify.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/slack_notify.py backend/auth_service/tests/test_slack_notify.py
git commit -m "feat(slack): post block-kit message on issue resolved"
```

---

## Task 5: Swallow Slack API errors and network exceptions

**Files:**
- Modify: `backend/auth_service/tests/test_slack_notify.py`

- [ ] **Step 1: Append failing tests**

Add to `backend/auth_service/tests/test_slack_notify.py`:

```python
def test_swallows_timeout(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    def fake_post(*args, **kwargs):
        raise slack_notify.httpx.TimeoutException("slow")

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        # Must not raise.
        slack_notify.notify_issue_created(
            issue=_sample_issue(),
            project=_sample_project(),
            user_email="client@acme.com",
        )


def test_swallows_api_error_ok_false(monkeypatch, caplog):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    class _ErrResp:
        def json(self):
            return {"ok": False, "error": "not_in_channel"}

    def fake_post(*args, **kwargs):
        return _ErrResp()

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        with caplog.at_level("WARNING"):
            slack_notify.notify_issue_resolved(
                issue=_sample_issue(),
                project=_sample_project(),
                resolver_email="stefan@example.com",
            )

    assert any("not_in_channel" in rec.message for rec in caplog.records)
```

- [ ] **Step 2: Run to confirm pass (these should already pass)**

```bash
pytest auth_service/tests/test_slack_notify.py -v
```

Expected: 6 passed. The `_post` helper already swallows. If `test_swallows_timeout` fails because `httpx.TimeoutException` isn't caught by the bare `except Exception`, change the implementation to catch `httpx.HTTPError` AND `Exception`. (`TimeoutException` inherits from `Exception`, so this should already work.)

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/tests/test_slack_notify.py
git commit -m "test(slack): cover timeout + ok:false swallowing"
```

---

## Task 6: Extend conftest fixtures for issues router

**Files:**
- Modify: `backend/auth_service/tests/conftest.py`

- [ ] **Step 1: Read current state**

The existing `mock_supabase` fixture patches several routers' `get_supabase_admin` imports. We need to add the issues router. Same for `auth_as`.

- [ ] **Step 2: Add issues router to mock_supabase targets**

In `backend/auth_service/tests/conftest.py`, find the `targets = [...]` list inside `mock_supabase`. Add a new entry:

```python
    targets = [
        "auth_service.routers.content.get_supabase_admin",
        "auth_service.routers.workspace.get_supabase_admin",
        "auth_service.routers.workspace.get_supabase_admin",
        "auth_service.routers.projects.get_supabase_admin",
        "auth_service.routers.publish.get_supabase_admin",
        "auth_service.routers.issues.get_supabase_admin",   # ← NEW
        "auth_service.services.sessions.get_supabase_admin",
        "auth_service.services.supabase_client.get_supabase_admin",
    ]
```

- [ ] **Step 3: Extend `auth_as` to cover issues router**

Inside `auth_as._apply`, after the `publish.py` block, add:

```python
    # issues.py — new in S1
    try:
        monkeypatch.setattr("auth_service.routers.issues.require_user", fake_require_user)
    except (AttributeError, ModuleNotFoundError, ImportError):
        pass
    try:
        monkeypatch.setattr(
            "auth_service.routers.issues.require_project_access", fake_require_project_access
        )
    except (AttributeError, ModuleNotFoundError, ImportError):
        pass
```

Also enhance `fake_require_project_access` so projects include the fields the Slack payload depends on. Replace the existing inline definition:

```python
        def fake_require_project_access(slug, u):
            return {
                "id": f"project-{slug}",
                "slug": slug,
                "name": slug.title(),
                "github_repo": f"https://github.com/test/{slug}",
                "repo_branch": "dev",
                "preview_url": f"https://{slug}-dev.vercel.app",
            }
```

- [ ] **Step 4: Run all existing tests to confirm no regression**

```bash
pytest auth_service/tests -v
```

Expected: existing tests still pass (no new tests yet in this task).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/tests/conftest.py
git commit -m "test(conftest): extend mock_supabase + auth_as to cover issues router"
```

---

## Task 7: Wire `notify_issue_created` into `create_issue` handler

**Files:**
- Modify: `backend/auth_service/routers/issues.py`
- Create: `backend/auth_service/tests/test_issues_router.py`

- [ ] **Step 1: Write the failing integration test**

Create `backend/auth_service/tests/test_issues_router.py`:

```python
"""Integration tests for routers/issues.py — Slack notification wiring."""
from __future__ import annotations

from unittest.mock import MagicMock


def test_create_issue_fires_slack_created(mock_supabase, client, auth_as, client_user, monkeypatch):
    auth_as(client_user)

    # Stub Supabase insert to return one row.
    inserted_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "Hero broken",
        "description": "stretches",
        "priority": "High",
        "created_at": "2026-05-15T10:00:00Z",
        "created_by": client_user.id,
    }
    mock_supabase.execute.return_value = MagicMock(data=[inserted_row])

    calls: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created",
        lambda **kw: calls.append(kw),
    )

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "Hero broken", "description": "stretches", "priority": "High"},
    )
    assert resp.status_code == 201, resp.text

    assert len(calls) == 1
    call = calls[0]
    assert call["user_email"] == client_user.email
    assert call["issue"]["id"] == "issue-1"
    assert call["issue"]["title"] == "Hero broken"
    assert call["project"]["slug"] == "acme"
    assert call["project"]["repo_branch"] == "dev"


def test_create_issue_slack_failure_does_not_break_201(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    """If slack_notify raises, the API still returns 201."""
    auth_as(client_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "issue-2",
                "project_id": "project-acme",
                "title": "x",
                "description": "y",
                "priority": "Low",
                "created_at": "2026-05-15T10:00:00Z",
                "created_by": client_user.id,
            }
        ]
    )

    def boom(**kw):
        raise RuntimeError("slack down")

    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created", boom
    )

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "x", "description": "y", "priority": "Low"},
    )
    # The service itself swallows; if a router-level guard is missing, this test
    # forces it to be added.
    assert resp.status_code == 201, resp.text
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest auth_service/tests/test_issues_router.py::test_create_issue_fires_slack_created -v
```

Expected: FAIL — `AttributeError: module 'auth_service.routers.issues' has no attribute 'slack_notify'`.

- [ ] **Step 3: Wire the import + call in `routers/issues.py`**

At the top of `backend/auth_service/routers/issues.py`, add the import:

```python
from ..services import slack_notify
```

Inside `create_issue` (after the existing `if not result.data: raise ...` block, just before `row = result.data[0]`), keep the existing return-value construction, but wrap the Slack call around it. Replace the tail of `create_issue` (from `row = result.data[0]` onward) with:

```python
    row = result.data[0]
    issue_out = IssueOut(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        description=row["description"],
        priority=row["priority"],
        status="pending",
        created_by=row.get("created_by"),
        created_by_email=user.email,
        created_at=row["created_at"],
    )

    try:
        slack_notify.notify_issue_created(
            issue={
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "priority": row["priority"],
                "created_at": row["created_at"],
            },
            project=project,
            user_email=user.email,
        )
    except Exception:  # noqa: BLE001 — Slack must never break issue creation
        import logging
        logging.getLogger(__name__).exception("slack_notify (created) raised")

    return issue_out
```

The try/except is a belt-and-suspenders guard. The service already swallows, but a future caller using a different mock (as in the second test) could raise. The router must not 5xx.

- [ ] **Step 4: Run the new tests**

```bash
pytest auth_service/tests/test_issues_router.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full slack + issues suite to check for regressions**

```bash
pytest auth_service/tests/test_slack_notify.py auth_service/tests/test_issues_router.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/routers/issues.py backend/auth_service/tests/test_issues_router.py
git commit -m "feat(issues): fire Slack notification on issue create"
```

---

## Task 8: Wire `notify_issue_resolved` into `update_issue_status` handler

**Files:**
- Modify: `backend/auth_service/routers/issues.py`
- Modify: `backend/auth_service/tests/test_issues_router.py`

- [ ] **Step 1: Append failing tests**

Add to `backend/auth_service/tests/test_issues_router.py`:

```python
def test_status_pending_to_done_fires_resolved(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    auth_as(admin_user)

    # First SELECT returns the existing row (status=pending).
    # Then UPDATE returns the new row (status=done).
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
        MagicMock(data=pending_row),       # pre-update SELECT (maybe_single)
        MagicMock(data=[updated_row]),     # UPDATE
        MagicMock(data={"email": "client@acme.com"}),  # email lookup
    ]

    calls: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: calls.append(kw),
    )

    resp = client.patch(
        "/projects/acme/issues/issue-1/status",
        json={"status": "done"},
    )
    assert resp.status_code == 200, resp.text

    assert len(calls) == 1
    assert calls[0]["resolver_email"] == admin_user.email
    assert calls[0]["issue"]["id"] == "issue-1"
    assert calls[0]["project"]["preview_url"] == "https://acme-dev.vercel.app"


def test_status_done_to_done_does_not_fire(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    auth_as(admin_user)
    done_row = {"id": "issue-1", "project_id": "project-acme", "status": "done"}
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
        MagicMock(data=done_row),
        MagicMock(data=[updated_row]),
    ]

    calls: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: calls.append(kw),
    )

    resp = client.patch(
        "/projects/acme/issues/issue-1/status", json={"status": "done"}
    )
    assert resp.status_code == 200, resp.text
    assert calls == []


def test_status_pending_to_in_progress_does_not_fire(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    auth_as(admin_user)
    pending_row = {"id": "issue-1", "project_id": "project-acme", "status": "pending"}
    updated_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "x",
        "description": "y",
        "priority": "Low",
        "status": "in_progress",
        "created_by": None,
        "created_at": "2026-05-15T10:00:00Z",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=pending_row),
        MagicMock(data=[updated_row]),
    ]

    calls: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: calls.append(kw),
    )

    resp = client.patch(
        "/projects/acme/issues/issue-1/status", json={"status": "in_progress"}
    )
    assert resp.status_code == 200, resp.text
    assert calls == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest auth_service/tests/test_issues_router.py::test_status_pending_to_done_fires_resolved -v
```

Expected: FAIL — no Slack call recorded (router doesn't notify yet).

- [ ] **Step 3: Modify `update_issue_status` handler**

In `backend/auth_service/routers/issues.py`, find `update_issue_status`. Modify the pre-update SELECT to also pull `status`:

```python
    issue_result = (
        sb.table("project_issues")
        .select("id, project_id, status")  # ← added status
        .eq("id", issue_id)
        .eq("project_id", project["id"])
        .maybe_single()
        .execute()
    )
    if not issue_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    old_status = issue_result.data.get("status", "pending")
```

Then, after the existing return-value construction (after the final `IssueOut(...)` is built and assigned to a variable), fire the notification if the transition matches. Replace the return statement at the end of `update_issue_status`:

```python
    issue_out = IssueOut(
        id=r["id"],
        project_id=r["project_id"],
        title=r["title"],
        description=r["description"],
        priority=r["priority"],
        status=r["status"],
        created_by=r.get("created_by"),
        created_by_email=(
            email_result.data.get("email") if email_result and email_result.data else None
        ),
        created_at=r["created_at"],
    )

    if old_status != "done" and body.status == "done":
        try:
            slack_notify.notify_issue_resolved(
                issue={"id": r["id"], "title": r["title"]},
                project=project,
                resolver_email=user.email,
            )
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception("slack_notify (resolved) raised")

    return issue_out
```

- [ ] **Step 4: Run the resolved-flow tests**

```bash
pytest auth_service/tests/test_issues_router.py -v -k "status"
```

Expected: 3 status-flow tests pass.

- [ ] **Step 5: Run the full issues test file**

```bash
pytest auth_service/tests/test_issues_router.py -v
```

Expected: 5 passed (2 from Task 7 + 3 from this task).

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/routers/issues.py backend/auth_service/tests/test_issues_router.py
git commit -m "feat(issues): fire Slack notification on issue resolve (pending→done)"
```

---

## Task 9: Documentation updates

**Files:**
- Modify: `docs/ENVIRONMENTS.md`
- Modify: `docs/ONBOARDING.md`
- Modify: `docs/DEVELOPMENT.md`

- [ ] **Step 1: Inspect current docs**

```bash
grep -n "RESEND" docs/ENVIRONMENTS.md
```

Find the existing env-var table to see formatting. Match the style.

- [ ] **Step 2: Update `docs/ENVIRONMENTS.md`**

Add to the backend env-var table (find the section listing backend env vars; append rows):

```markdown
| `SLACK_BOT_TOKEN`           | Bot User OAuth Token from the CMS Issues Bot Slack app. Disabled if unset. | backend | no  |
| `SLACK_ISSUES_CHANNEL_ID`   | Slack channel ID (e.g. `C0123ABCDEF`) for `#issues-websites`. Disabled if unset. | backend | no  |
| `CMS_DASHBOARD_URL`         | Base URL for the CMS dashboard, used as the "Open in CMS" button target in Slack messages. Defaults to `https://roman-technologies.dev`. | backend | no  |
| `AGENT_CACHE_ROOT`          | Filesystem root used by future S2/S3 issue-resolution agents (`<root>/<slug>` per project). Not consumed by S1. | agents  | no  |
```

(Adjust column count if the actual table has more/fewer columns — keep the row shape consistent.)

- [ ] **Step 3: Update `docs/ONBOARDING.md`**

Add a new section after the existing service-setup section:

```markdown
## Slack Issue Notifications

The backend posts to `#issues-websites` when a client submits an issue and when an admin marks it resolved.

### One-time setup

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**.
2. Name: `CMS Issues Bot`. Workspace: your Slack workspace.
3. **OAuth & Permissions** → **Bot Token Scopes** → add `chat:write`.
4. **Install to Workspace** → approve.
5. Copy the **Bot User OAuth Token** (starts with `xoxb-...`) into the backend env as `SLACK_BOT_TOKEN`.
6. In Slack desktop, right-click `#issues-websites` → **View channel details** → copy the **Channel ID** (e.g. `C0123ABCDEF`). Put it in `SLACK_ISSUES_CHANNEL_ID`.
7. Inside `#issues-websites`, run `/invite @CMS Issues Bot`. The bot must be a channel member to post.

### Disabled mode

Leaving `SLACK_BOT_TOKEN` or `SLACK_ISSUES_CHANNEL_ID` unset disables notifications silently — useful for local dev and CI. The service logs `slack_notify disabled` at INFO and never raises.
```

- [ ] **Step 4: Update `docs/DEVELOPMENT.md`**

Add a short note under the "Local dev quirks" or equivalent section (create one if missing):

```markdown
### Slack notifications in local dev

`backend/auth_service/services/slack_notify.py` is silent unless both `SLACK_BOT_TOKEN` and `SLACK_ISSUES_CHANNEL_ID` are set. Local dev does not need to configure Slack; tests use mocks. To smoke-test for real, copy the prod values into `backend/.env` and POST an issue.
```

- [ ] **Step 5: Commit**

```bash
git add docs/ENVIRONMENTS.md docs/ONBOARDING.md docs/DEVELOPMENT.md
git commit -m "docs: document Slack issue notifications setup + env vars"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run the full backend test suite**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests -v
```

Expected: all tests pass, no new failures vs main branch.

- [ ] **Step 2: Lint / type check (if project uses them)**

```bash
# Adjust to project's actual tools:
ruff check backend/auth_service
# or:
# python -m mypy backend/auth_service
```

Expected: no new issues.

- [ ] **Step 3: Manual smoke (local, with real Slack)**

1. Set `SLACK_BOT_TOKEN` and `SLACK_ISSUES_CHANNEL_ID` in `backend/.env`.
2. Start backend: `uvicorn auth_service.main:app --reload --port 8001`.
3. Start frontend: `cd frontend && npm run dev`.
4. Submit an issue from the dashboard as a client user. Observe Slack message in `#issues-websites`.
5. As admin, change status to `done`. Observe resolved message in Slack.
6. Set status back to `pending`, then to `done` again. Observe a second resolved message (re-fire on transition).
7. Unset `SLACK_BOT_TOKEN`, restart backend, submit another issue. Observe `slack_notify disabled` in logs, no Slack message, 201 response.

- [ ] **Step 4: Final commit (if any post-smoke fixes)**

```bash
git status
# if dirty:
git add -p
git commit -m "fix(slack): post-smoke adjustments"
```

- [ ] **Step 5: Open PR**

```bash
git push -u origin <branch>
gh pr create --title "feat(s1): Slack issue notifications" --body "$(cat <<'EOF'
## Summary
- New `services/slack_notify.py` posts to Slack on issue create + resolve.
- `projects.repo_branch` column added (default `'dev'`) — consumed by future S3 solver agent.
- Disabled silently when Slack env unset (local dev + CI).
- Failures swallowed; 5xx invariant preserved on Slack outage.

## Test plan
- [ ] `pytest auth_service/tests` green
- [ ] Local smoke: real Slack message on issue create
- [ ] Local smoke: real Slack message on pending → done transition
- [ ] Local smoke: no message on done → done
- [ ] Local smoke: backend returns 201 with Slack env unset

Spec: docs/superpowers/specs/2026-05-15-slack-issue-notifications-design.md
EOF
)"
```

---

## Self-Review

### Spec coverage
- Architecture diagram → Tasks 2-4 (service module).
- `projects.repo_branch` column → Task 1.
- `local_cache_path` derived, no column → spec says "not a DB column", plan honors it (no task creates one).
- New-issue Block Kit → Task 3.
- Resolved Block Kit → Task 4.
- Service module API (functions + signatures) → Tasks 2-4.
- Hook 1 (`create_issue`) → Task 7.
- Hook 2 (`update_issue_status`) with transition guard → Task 8.
- Env vars (`SLACK_BOT_TOKEN`, `SLACK_ISSUES_CHANNEL_ID`, `AGENT_CACHE_ROOT`, `CMS_DASHBOARD_URL`) → Task 9.
- Slack app setup → Task 9.
- Error handling matrix (timeout, ok:false, network ex, missing env) → Task 5 + the swallow guards in Task 2-4 and Task 7-8.
- Unit tests (5 from spec) → Tasks 2-5 cover them.
- Integration tests (4 from spec) → Tasks 7-8 cover them.
- Disabled mode → Task 2.
- Migration RLS untouched → Task 1 (no policy change).
- Success criteria → smoke-checked in Task 10.

### Placeholders
None remaining. Every code step has executable code. Every commit step has a real message. The `# Adjust to project's actual tools` line in Task 10 step 2 is an instruction to the engineer, not a placeholder in code.

### Type / signature consistency
- `notify_issue_created(issue, project, user_email)` — same signature in Tasks 2, 3, 7.
- `notify_issue_resolved(issue, project, resolver_email)` — same signature in Tasks 2, 4, 8.
- `_post(blocks, text_fallback)` — defined Task 3, unchanged after.
- `_build_created_blocks` / `_build_resolved_blocks` — internal helpers, signatures match calls.
- Project dict keys used in payload: `slug`, `name`, `github_repo`, `repo_branch`, `preview_url` — all set in `fake_require_project_access` (Task 6) and match what real `require_project_access` would return after Task 1 lands `repo_branch`.
- Issue dict keys: `id`, `title`, `description`, `priority`, `created_at` for created; `id`, `title` for resolved — consistent everywhere.

All consistent.
