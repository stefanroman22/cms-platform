# Solver Agent — Staging-Branch Model + Visibility Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treat `cms-preview` as a real staging branch (no reset), honor `repository_dispatch` payloads so the right issue gets claimed, and close every silent failure mode so the Slack channel reflects every solver exit path.

**Architecture:** Three foundational shifts to the existing S3 Solver Agent pipeline: (1) replace `clone_and_reset_to_prod` with `clone_at_preview_head` + plain push, (2) add `claim_specific_solver_issue` RPC and `DISPATCH_ISSUE_ID` env wiring so dispatch targets the named issue, (3) persist `slack_created_ts` on issue creation and route every silent finalize.py exit through a new `POST /admin/issues/{id}/agent-event` endpoint that posts a Slack thread reply. Full design: [`docs/superpowers/specs/2026-05-18-solver-staging-model-design.md`](../specs/2026-05-18-solver-staging-model-design.md).

**Tech Stack:** Python 3.13, FastAPI 0.136, Supabase (Postgres 17), GitHub Actions, Slack chat.postMessage, pytest + httpx TestClient.

---

## Stefan's commit policy

Stefan's preference: no auto-commits per task — only `git commit` when he says so explicitly. Treat every `git commit` step in this plan as a checkpoint: stage the files, ask Stefan before committing. If Stefan wants to batch, skip the commit steps entirely and group at the end. The TDD discipline (failing test first) still applies inside each task regardless.

## Migration via Supabase MCP

Stefan's preference: apply migrations through the Supabase MCP tool (`mcp__supabase__apply_migration`), not by running `supabase db push` manually. The migration step in Task 1 reflects this.

---

## File structure

**New files:**
- `backend/migrations/2026_05_18_solver_visibility.sql` — column add + RPC create
- `agents/Solver - Issues/tests/test_backend_api.py` — new test module for backend_api.py
- `backend/auth_service/tests/test_agent_event_route.py` — new test module for the agent-event admin route

**Modified files (production):**
- `backend/auth_service/models/schemas.py` — add `AgentEventRequest`
- `backend/auth_service/services/slack_notify.py` — add `notify_agent_event`
- `backend/auth_service/services/solver_dispatch.py` — Slack alert on dispatch failure
- `backend/auth_service/routers/issues.py` — persist `slack_created_ts`; new agent-event route
- `agents/Solver - Issues/db.py` — `claim_specific_issue`
- `agents/Solver - Issues/claim_issue.py` — `DISPATCH_ISSUE_ID` handling; prompt updates
- `agents/Solver - Issues/repo.py` — `clone_at_preview_head`; plain push + `PushRejectedError`
- `agents/Solver - Issues/clone_repo.py` — new call signature
- `agents/Solver - Issues/backend_api.py` — `notify_agent_event` + retry wrapper
- `agents/Solver - Issues/slack.py` — `post_thread_event_direct`
- `agents/Solver - Issues/finalize.py` — restructured decision tree
- `agents/Solver - Issues/release_issue.py` — Slack notify + de-dup guard
- `.github/workflows/solver-agent.yml` — `DISPATCH_ISSUE_ID` env, capture Claude exit code

**Modified files (docs):**
- `agents/Solver - Issues/AGENTS.md` — Pipeline + Failure taxonomy + Hard rules + Modifying-this-agent sections
- `agents/Solver - Issues/phases/2-clone.md` — rewrite for no-reset model
- `agents/Solver - Issues/phases/4-push.md` — rewrite for plain push
- `agents/Solver - Issues/phases/5-finalize.md` — rewrite decision tree

**Modified files (tests):**
- `agents/Solver - Issues/tests/test_db_claim.py` — add `claim_specific_issue` cases
- `agents/Solver - Issues/tests/test_claim_issue.py` — add `DISPATCH_ISSUE_ID` cases
- `agents/Solver - Issues/tests/test_repo.py` — rename existing tests; add `PushRejectedError` cases
- `agents/Solver - Issues/tests/test_finalize.py` — add 5 new branch cases
- `backend/auth_service/tests/test_issues_router.py` — `slack_created_ts` persistence
- `backend/auth_service/tests/test_slack_notify.py` — `notify_agent_event` cases
- `backend/auth_service/tests/test_solver_dispatch.py` — failure alerting cases

---

# Phase 1 — Database migration

## Task 1: Apply migration

**Files:**
- Create: `backend/migrations/2026_05_18_solver_visibility.sql`

- [ ] **Step 1: Write the migration SQL**

Create `backend/migrations/2026_05_18_solver_visibility.sql` with:

```sql
-- 2026_05_18 — Solver agent staging-model + visibility pass
-- Adds slack_created_ts (mirrors slack_resolved_ts) for threading agent-event
-- notifications under the original "New Issue" Slack post. Adds the
-- claim_specific_solver_issue RPC so repository_dispatch can target a
-- specific issue instead of running the priority queue.

-- 1. Persist Slack ts of the "New Issue" message for thread replies
ALTER TABLE project_issues
  ADD COLUMN IF NOT EXISTS slack_created_ts TEXT NULL;

COMMENT ON COLUMN project_issues.slack_created_ts IS
  'Slack ts of the "New Issue" top-level post. Lookup key for agent-event thread replies (rejection, no_diff, agent_crashed, backend_error).';

-- 2. Targeted claim RPC (called when repository_dispatch.client_payload.issue_id is set)
CREATE OR REPLACE FUNCTION public.claim_specific_solver_issue(
  p_issue_id uuid,
  p_max_retries integer DEFAULT 3,
  p_stale_minutes integer DEFAULT 15
)
RETURNS TABLE(id uuid, project_id uuid, title text, description text,
              priority text, status text, revision_feedback text)
LANGUAGE plpgsql SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  WITH target AS (
    SELECT pi.id FROM project_issues pi
    WHERE pi.id = p_issue_id
      AND (
        (pi.status = 'pending' AND COALESCE(pi.agent_status, 'idle') IN ('idle', 'failed'))
        OR
        (pi.status = 'in_progress' AND pi.revision_feedback IS NOT NULL
         AND COALESCE(pi.agent_status, 'idle') IN ('idle', 'failed'))
      )
      AND pi.agent_retry_count < p_max_retries
      AND COALESCE(pi.agent_status, 'idle') != 'blocked'
      AND (pi.agent_claimed_at IS NULL
           OR pi.agent_claimed_at < now() - (p_stale_minutes || ' minutes')::interval)
    FOR UPDATE SKIP LOCKED
  )
  UPDATE project_issues
  SET agent_status = 'claimed', agent_claimed_at = now()
  WHERE project_issues.id = (SELECT target.id FROM target)
  RETURNING
    project_issues.id, project_issues.project_id, project_issues.title,
    project_issues.description, project_issues.priority, project_issues.status,
    project_issues.revision_feedback;
END;
$$;
```

- [ ] **Step 2: Apply migration via Supabase MCP**

Call `mcp__supabase__apply_migration` with:
- `project_id`: `xeluydwpgiddbamysgyu` (the CMS Supabase project — confirmed in conversation history)
- `name`: `2026_05_18_solver_visibility`
- `query`: the full SQL from Step 1

- [ ] **Step 3: Verify column exists**

Call `mcp__supabase__execute_sql` with:
- `project_id`: `xeluydwpgiddbamysgyu`
- `query`: `SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='project_issues' AND column_name='slack_created_ts';`

Expected: one row, `data_type='text'`, `is_nullable='YES'`.

- [ ] **Step 4: Verify RPC exists**

Call `mcp__supabase__execute_sql` with:
- `project_id`: `xeluydwpgiddbamysgyu`
- `query`: `SELECT proname FROM pg_proc WHERE proname='claim_specific_solver_issue';`

Expected: one row, `proname='claim_specific_solver_issue'`.

- [ ] **Step 5: Smoke-test the RPC with a fake id**

Call `mcp__supabase__execute_sql` with:
- `project_id`: `xeluydwpgiddbamysgyu`
- `query`: `SELECT * FROM claim_specific_solver_issue('00000000-0000-0000-0000-000000000000');`

Expected: zero rows (no issue with that id), no error.

- [ ] **Step 6: Stage migration + checkpoint**

```bash
git add backend/migrations/2026_05_18_solver_visibility.sql
```

Pause for Stefan's go-ahead before committing.

---

# Phase 2 — Backend schemas + slack_notify

## Task 2: Add AgentEventRequest schema

**Files:**
- Modify: `backend/auth_service/models/schemas.py`

- [ ] **Step 1: Find where IssueStatusRequest is defined and add new model after it**

Read `backend/auth_service/models/schemas.py`, locate the `IssueStatusRequest` class (used by the existing `/admin/issues/{id}/status` route). Add immediately after it:

```python
from typing import Literal


class AgentEventRequest(BaseModel):
    """Solver agent → backend event notification.

    Each kind maps to a Slack thread reply under the original "New Issue"
    message (or a top-level post if slack_created_ts is NULL on the issue).
    """

    kind: Literal["rejected", "no_diff", "agent_crashed", "backend_error"]
    reason: str = Field(..., min_length=1, max_length=500)
```

If `Literal` and `Field` are not already imported at the top of the file, add them to the existing pydantic imports.

- [ ] **Step 2: Verify file still imports cleanly**

Run from `backend/`:
```bash
python -c "from auth_service.models.schemas import AgentEventRequest; print(AgentEventRequest.model_fields)"
```

Expected: prints model fields dict including `kind` and `reason`, no traceback.

- [ ] **Step 3: Stage + checkpoint**

```bash
git add backend/auth_service/models/schemas.py
```

Pause for Stefan's go-ahead.

## Task 3: Add notify_agent_event in slack_notify

**Files:**
- Modify: `backend/auth_service/services/slack_notify.py`
- Test: `backend/auth_service/tests/test_slack_notify.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/auth_service/tests/test_slack_notify.py`:

```python
def test_notify_agent_event_posts_thread_reply(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    posted = {}

    class FakeResp:
        @staticmethod
        def json():
            return {"ok": True, "ts": "1715865500.000111"}

    def fake_post(url, headers=None, json=None, timeout=None):
        posted["url"] = url
        posted["json"] = json
        return FakeResp()

    monkeypatch.setattr(slack_notify.httpx, "post", fake_post)

    ts = slack_notify.notify_agent_event(
        thread_ts="1715865123.456789",
        kind="rejected",
        reason="Cannot reproduce: header already correct",
        project=_sample_project(),
        issue=_sample_issue(),
    )

    assert ts == "1715865500.000111"
    assert posted["json"]["thread_ts"] == "1715865123.456789"
    assert posted["json"]["channel"] == "C123"
    assert "🤔" in posted["json"]["text"]
    assert "Cannot reproduce" in posted["json"]["text"]


def test_notify_agent_event_kinds_use_distinct_emojis(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    captured: list[dict] = []

    class FakeResp:
        @staticmethod
        def json():
            return {"ok": True, "ts": "0"}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.append(json)
        return FakeResp()

    monkeypatch.setattr(slack_notify.httpx, "post", fake_post)

    for kind in ("rejected", "no_diff", "agent_crashed", "backend_error"):
        slack_notify.notify_agent_event(
            thread_ts="t1",
            kind=kind,
            reason="x",
            project=_sample_project(),
            issue=_sample_issue(),
        )

    emojis = {kind: c["text"][0] for kind, c in zip(
        ("rejected", "no_diff", "agent_crashed", "backend_error"), captured
    )}
    # All four must use different leading emojis so users can scan the thread.
    assert len(set(emojis.values())) == 4


def test_notify_agent_event_swallows_api_error(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    class FakeResp:
        @staticmethod
        def json():
            return {"ok": False, "error": "channel_not_found"}

    monkeypatch.setattr(
        slack_notify.httpx, "post",
        lambda *a, **kw: FakeResp(),
    )

    result = slack_notify.notify_agent_event(
        thread_ts="t1", kind="rejected", reason="x",
        project=_sample_project(), issue=_sample_issue(),
    )
    assert result is None


def test_notify_agent_event_disabled_returns_none(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ISSUES_CHANNEL_ID", raising=False)
    result = slack_notify.notify_agent_event(
        thread_ts="t1", kind="rejected", reason="x",
        project=_sample_project(), issue=_sample_issue(),
    )
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

From repo root:
```bash
cd backend && python -m pytest auth_service/tests/test_slack_notify.py -v -k "notify_agent_event"
```

Expected: 4 ERRORS or FAILUREs with `AttributeError: module 'auth_service.services.slack_notify' has no attribute 'notify_agent_event'`.

- [ ] **Step 3: Implement notify_agent_event**

Add to `backend/auth_service/services/slack_notify.py` (after `post_thread_reply`):

```python
_AGENT_EVENT_EMOJI = {
    "rejected": "🤔",
    "no_diff": "⚠️",
    "agent_crashed": "🔧",
    "backend_error": "🛑",
}

_AGENT_EVENT_HEADER = {
    "rejected": "Agent reviewed, no change",
    "no_diff": "Agent produced no file changes",
    "agent_crashed": "Agent CLI crashed",
    "backend_error": "Backend / push error",
}


def notify_agent_event(
    *,
    thread_ts: str | None,
    kind: str,
    reason: str,
    project: dict[str, Any],
    issue: dict[str, Any],
) -> str | None:
    """Post an agent-event Slack message.

    If thread_ts is provided, posts as a thread reply. If thread_ts is None
    (slack_created_ts was never persisted, e.g. notify_issue_created failed at
    create time), degrades to a top-level message that includes project + title
    for context.

    Returns the resulting Slack ts on success, None on disabled mode or any
    failure. Swallow all errors — slack outages must not break the agent.
    """
    if not _enabled():
        logger.info("slack_notify disabled — skipping agent_event")
        return None

    emoji = _AGENT_EVENT_EMOJI.get(kind, "❔")
    header = _AGENT_EVENT_HEADER.get(kind, "Agent event")
    project_name = project.get("name") or project.get("slug", "unknown")
    title = issue.get("title", "(no title)")
    reason_trimmed = _truncate(reason, 500)

    if thread_ts:
        text = f"{emoji} {header} — {reason_trimmed}"
    else:
        text = (
            f"{emoji} {header} — {project_name}\n"
            f"*Title:* {title}\n"
            f"*Reason:* {reason_trimmed}\n"
            f"_(threaded reply not possible — original 'New Issue' Slack ts unknown)_"
        )

    try:
        body: dict[str, Any] = {
            "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
            "text": text,
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
            logger.warning("notify_agent_event api error: %s", data.get("error"))
            return None
        return data.get("ts")
    except Exception:
        logger.exception("notify_agent_event post failed")
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest auth_service/tests/test_slack_notify.py -v -k "notify_agent_event"
```

Expected: 4 PASS.

- [ ] **Step 5: Run full slack_notify test file to confirm no regressions**

```bash
cd backend && python -m pytest auth_service/tests/test_slack_notify.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Stage + checkpoint**

```bash
git add backend/auth_service/services/slack_notify.py backend/auth_service/tests/test_slack_notify.py
```

Pause for Stefan's go-ahead.

---

# Phase 3 — Backend issues router

## Task 4: Persist slack_created_ts on issue creation

**Files:**
- Modify: `backend/auth_service/routers/issues.py:110-125` (the `notify_issue_created` try/except block in `create_issue`)
- Test: `backend/auth_service/tests/test_issues_router.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/auth_service/tests/test_issues_router.py`:

```python
def test_create_issue_persists_slack_created_ts(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    """When notify_issue_created returns a ts, it is persisted as slack_created_ts."""
    auth_as(client_user)

    inserted_row = {
        "id": "issue-77",
        "project_id": "project-acme",
        "title": "x",
        "description": "y",
        "priority": "Low",
        "created_at": "2026-05-15T10:00:00Z",
        "created_by": client_user.id,
    }
    # First call (insert) returns the row; subsequent UPDATE returns it too.
    mock_supabase.execute.return_value = MagicMock(data=[inserted_row])

    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created",
        lambda **kw: "1715865123.456789",
    )

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "x", "description": "y", "priority": "Low"},
    )
    assert resp.status_code == 201, resp.text

    # Find the UPDATE call that set slack_created_ts.
    update_calls = [
        c for c in mock_supabase.update.call_args_list
        if c.args and "slack_created_ts" in c.args[0]
    ]
    assert len(update_calls) == 1
    assert update_calls[0].args[0]["slack_created_ts"] == "1715865123.456789"


def test_create_issue_no_ts_when_slack_returns_none(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    """When notify_issue_created returns None (disabled/error), no UPDATE is made."""
    auth_as(client_user)
    mock_supabase.execute.return_value = MagicMock(data=[{
        "id": "issue-78", "project_id": "project-acme", "title": "x",
        "description": "y", "priority": "Low",
        "created_at": "2026-05-15T10:00:00Z", "created_by": client_user.id,
    }])
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created",
        lambda **kw: None,
    )
    resp = client.post(
        "/projects/acme/issues",
        json={"title": "x", "description": "y", "priority": "Low"},
    )
    assert resp.status_code == 201
    update_calls = [
        c for c in mock_supabase.update.call_args_list
        if c.args and "slack_created_ts" in c.args[0]
    ]
    assert len(update_calls) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest auth_service/tests/test_issues_router.py -v -k "slack_created_ts"
```

Expected: 2 FAILURES with assertion errors about `update_calls` length.

- [ ] **Step 3: Modify create_issue to capture + persist the ts**

In `backend/auth_service/routers/issues.py`, find the existing block (around line 110):

```python
    try:
        slack_notify.notify_issue_created(
            issue={
                "id": row["id"],
                ...
            },
            project=project,
            user_email=user.email,
        )
    except Exception:  # noqa: BLE001 — Slack must never break issue creation
        import logging

        logging.getLogger(__name__).exception("slack_notify (created) raised")
```

Replace with:

```python
    try:
        ts = slack_notify.notify_issue_created(
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
        if ts:
            sb.table("project_issues").update({"slack_created_ts": ts}).eq(
                "id", row["id"]
            ).execute()
    except Exception:  # noqa: BLE001 — Slack must never break issue creation
        import logging

        logging.getLogger(__name__).exception("slack_notify (created) raised")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest auth_service/tests/test_issues_router.py -v -k "slack_created_ts"
```

Expected: 2 PASS.

- [ ] **Step 5: Run full issues router test file**

```bash
cd backend && python -m pytest auth_service/tests/test_issues_router.py -v
```

Expected: all tests pass (including the unchanged `test_create_issue_fires_slack_created` and `test_create_issue_slack_failure_does_not_break_201`).

- [ ] **Step 6: Stage + checkpoint**

```bash
git add backend/auth_service/routers/issues.py backend/auth_service/tests/test_issues_router.py
```

Pause for Stefan's go-ahead.

## Task 5: Add POST /admin/issues/{id}/agent-event route

**Files:**
- Modify: `backend/auth_service/routers/issues.py` (add new route at the bottom)
- Create: `backend/auth_service/tests/test_agent_event_route.py`

- [ ] **Step 1: Write the failing test file**

Create `backend/auth_service/tests/test_agent_event_route.py`:

```python
"""Tests for POST /admin/issues/{id}/agent-event — solver agent event notifications."""

from __future__ import annotations

from unittest.mock import MagicMock


def _issue_row(slack_created_ts: str | None = None) -> dict:
    return {
        "id": "issue-77",
        "project_id": "project-acme",
        "title": "Hero broken",
        "status": "pending",
        "slack_created_ts": slack_created_ts,
    }


def _project_row() -> dict:
    return {
        "id": "project-acme",
        "slug": "acme",
        "name": "Acme",
        "github_repo": "stefan/acme",
        "repo_branch": "cms-preview",
        "production_branch": "main",
        "preview_url": "https://acme-cms-preview.vercel.app",
        "production_url": "https://acme.example.com",
        "user_id": "u1",
    }


def test_agent_event_threads_when_slack_created_ts_present(
    mock_supabase, client, auth_as_admin, monkeypatch
):
    auth_as_admin()

    # Three select calls expected: issue lookup, project lookup, (optional) issue re-fetch.
    mock_supabase.execute.side_effect = [
        MagicMock(data=_issue_row(slack_created_ts="1715865123.456789")),  # issue lookup
        MagicMock(data=_project_row()),  # project lookup
    ]

    posted = {}
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_agent_event",
        lambda **kw: posted.update(kw) or "1715865500.000111",
    )

    resp = client.post(
        "/admin/issues/issue-77/agent-event",
        json={"kind": "rejected", "reason": "Cannot reproduce"},
    )
    assert resp.status_code == 200, resp.text

    assert posted["thread_ts"] == "1715865123.456789"
    assert posted["kind"] == "rejected"
    assert posted["reason"] == "Cannot reproduce"


def test_agent_event_degrades_to_top_level_when_slack_created_ts_missing(
    mock_supabase, client, auth_as_admin, monkeypatch
):
    auth_as_admin()
    mock_supabase.execute.side_effect = [
        MagicMock(data=_issue_row(slack_created_ts=None)),
        MagicMock(data=_project_row()),
    ]

    posted = {}
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_agent_event",
        lambda **kw: posted.update(kw) or "ts-top-level",
    )

    resp = client.post(
        "/admin/issues/issue-77/agent-event",
        json={"kind": "no_diff", "reason": "no file changes"},
    )
    assert resp.status_code == 200, resp.text
    assert posted["thread_ts"] is None  # degraded path
    assert posted["kind"] == "no_diff"


def test_agent_event_404_when_issue_not_found(
    mock_supabase, client, auth_as_admin
):
    auth_as_admin()
    mock_supabase.execute.return_value = MagicMock(data=None)
    resp = client.post(
        "/admin/issues/does-not-exist/agent-event",
        json={"kind": "rejected", "reason": "x"},
    )
    assert resp.status_code == 404


def test_agent_event_422_on_invalid_kind(client, auth_as_admin):
    auth_as_admin()
    resp = client.post(
        "/admin/issues/issue-77/agent-event",
        json={"kind": "unknown_kind", "reason": "x"},
    )
    assert resp.status_code == 422


def test_agent_event_422_when_reason_too_long(client, auth_as_admin):
    auth_as_admin()
    resp = client.post(
        "/admin/issues/issue-77/agent-event",
        json={"kind": "rejected", "reason": "x" * 501},
    )
    assert resp.status_code == 422


def test_agent_event_requires_admin_auth(client):
    """No bearer/session → 401 or 403."""
    resp = client.post(
        "/admin/issues/issue-77/agent-event",
        json={"kind": "rejected", "reason": "x"},
    )
    assert resp.status_code in (401, 403)
```

Note: this test uses fixture `auth_as_admin` — check `backend/auth_service/tests/conftest.py` to verify it exists. If not, reuse the pattern from `test_admin_keys.py` or whichever existing admin-route test does authentication. Most likely the fixture is named differently (e.g., `auth_as` with an admin-flagged user); adapt the call sites accordingly.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest auth_service/tests/test_agent_event_route.py -v
```

Expected: 6 FAILURES — route does not exist yet, so 404 on all POST calls (the 404 test passes accidentally; the others fail).

- [ ] **Step 3: Add the route to issues.py**

Append to `backend/auth_service/routers/issues.py`:

```python
@router.post(
    "/admin/issues/{issue_id}/agent-event",
    status_code=status.HTTP_200_OK,
)
async def admin_issue_agent_event(
    issue_id: str,
    body: AgentEventRequest,
    request: Request,
):
    """Solver agent → backend event notification.

    Posts a Slack thread reply under the issue's "New Issue" message
    (slack_created_ts). If that ts is missing (notify_issue_created failed at
    create time), degrades to a top-level Slack post that includes project +
    title for context. The agent calls this on every silent finalize.py exit
    so the Slack channel reflects every solver outcome.
    """
    user = await admin_user_via_bearer_or_sid(request)  # noqa: F841 — auth side-effect
    sb = get_supabase_admin()

    issue_result = (
        sb.table("project_issues")
        .select("id, project_id, title, status, slack_created_ts")
        .eq("id", issue_id)
        .maybe_single()
        .execute()
    )
    if not issue_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    issue_row = issue_result.data

    project_row = (
        sb.table("projects")
        .select(
            "id, name, slug, github_repo, repo_branch, production_branch, "
            "preview_url, production_url, user_id"
        )
        .eq("id", issue_row["project_id"])
        .single()
        .execute()
    )
    project = project_row.data or {}

    ts = slack_notify.notify_agent_event(
        thread_ts=issue_row.get("slack_created_ts"),  # None → degrade in slack_notify
        kind=body.kind,
        reason=body.reason,
        project=project,
        issue={"id": issue_row["id"], "title": issue_row["title"]},
    )

    return {"posted_ts": ts}
```

Add this import at the top of the file alongside the existing schema imports:

```python
from ..models.schemas import (
    AgentEventRequest,  # new
    IssueCreateRequest,
    IssueOut,
    IssueStatusRequest,
    IssueUpdateRequest,
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest auth_service/tests/test_agent_event_route.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Run full issues router test file to confirm no regressions**

```bash
cd backend && python -m pytest auth_service/tests/test_issues_router.py auth_service/tests/test_agent_event_route.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Stage + checkpoint**

```bash
git add backend/auth_service/routers/issues.py backend/auth_service/tests/test_agent_event_route.py
```

Pause for Stefan's go-ahead.

## Task 6: Slack alert on dispatch failure

**Files:**
- Modify: `backend/auth_service/services/solver_dispatch.py`
- Modify: `backend/auth_service/routers/issues.py` (the existing try/except around `dispatch_solver_tick`)
- Test: `backend/auth_service/tests/test_solver_dispatch.py`

The current pattern is: `dispatch_solver_tick` raises `SolverDispatchError`; caller (`create_issue` in issues.py) catches + logs. We're adding: when caller catches, also post a top-level Slack alert so the user knows the fast-path is broken (cron will still pick it up within 1h, but they'd otherwise have no signal).

- [ ] **Step 1: Write the failing test**

Append to `backend/auth_service/tests/test_solver_dispatch.py`:

```python
def test_create_issue_posts_slack_alert_when_dispatch_fails(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    """If dispatch_solver_tick raises, create_issue still returns 201 AND posts a Slack alert."""
    auth_as(client_user)
    mock_supabase.execute.return_value = MagicMock(data=[{
        "id": "issue-99", "project_id": "project-acme", "title": "x",
        "description": "y", "priority": "High",
        "created_at": "2026-05-18T10:00:00Z", "created_by": client_user.id,
    }])
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created",
        lambda **kw: "ts-created",
    )

    def boom(**kw):
        from auth_service.services.solver_dispatch import SolverDispatchError
        raise SolverDispatchError("GitHub 503 on dispatch")

    monkeypatch.setattr(
        "auth_service.routers.issues.solver_dispatch.dispatch_solver_tick", boom
    )

    alerts: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_agent_event",
        lambda **kw: alerts.append(kw) or "ts-alert",
    )

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "x", "description": "y", "priority": "High"},
    )
    assert resp.status_code == 201
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "backend_error"
    assert "dispatch" in alerts[0]["reason"].lower()
```

Note `from unittest.mock import MagicMock` may need to be added to the test file imports if missing.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest auth_service/tests/test_solver_dispatch.py -v -k "dispatch_fails"
```

Expected: FAIL with `assert len(alerts) == 1` (alerts is empty).

- [ ] **Step 3: Update the dispatch try/except in issues.py**

In `backend/auth_service/routers/issues.py`, find the existing block:

```python
    try:
        solver_dispatch.dispatch_solver_tick(issue_id=row["id"])
    except Exception:  # noqa: BLE001 — dispatch failure falls back to hourly cron
        import logging

        logging.getLogger(__name__).exception("solver_dispatch raised")
```

Replace with:

```python
    try:
        solver_dispatch.dispatch_solver_tick(issue_id=row["id"])
    except Exception as e:  # noqa: BLE001 — dispatch failure falls back to hourly cron
        import logging

        logging.getLogger(__name__).exception("solver_dispatch raised")
        # Best-effort alert: tell the user the fast-path is broken; cron will
        # catch the issue within an hour. Threading falls back to top-level
        # when slack_created_ts isn't set yet (notify_issue_created may have
        # also failed in the same window).
        try:
            slack_notify.notify_agent_event(
                thread_ts=None,  # alert goes top-level — needs attention
                kind="backend_error",
                reason=(
                    f"Could not dispatch solver workflow ({type(e).__name__}: {e}). "
                    f"The hourly cron will pick this up within ~1 hour."
                ),
                project=project,
                issue={"id": row["id"], "title": row["title"]},
            )
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("dispatch-failure Slack alert raised")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest auth_service/tests/test_solver_dispatch.py -v -k "dispatch_fails"
```

Expected: PASS.

- [ ] **Step 5: Run full solver_dispatch + issues router tests**

```bash
cd backend && python -m pytest auth_service/tests/test_solver_dispatch.py auth_service/tests/test_issues_router.py -v
```

Expected: all pass.

- [ ] **Step 6: Stage + checkpoint**

```bash
git add backend/auth_service/routers/issues.py backend/auth_service/tests/test_solver_dispatch.py
```

Pause for Stefan's go-ahead.

---

# Phase 4 — Agent documentation updates

## Task 7: Update AGENTS.md + phase docs

**Files:**
- Modify: `agents/Solver - Issues/AGENTS.md`
- Modify: `agents/Solver - Issues/phases/2-clone.md`
- Modify: `agents/Solver - Issues/phases/4-push.md`
- Modify: `agents/Solver - Issues/phases/5-finalize.md`

Documentation-only. No tests apply.

- [ ] **Step 1: Update AGENTS.md Pipeline table**

In `agents/Solver - Issues/AGENTS.md`, find the Pipeline table row 2 ("Clone"):

```
| 2 | Clone | [phases/2-clone.md](./phases/2-clone.md) | Clone + reset `cms-preview` to production HEAD; save prev SHA |
```

Replace with:

```
| 2 | Clone | [phases/2-clone.md](./phases/2-clone.md) | Clone `cms-preview` at its current HEAD; save prev SHA for revision-feedback context |
```

- [ ] **Step 2: Update AGENTS.md Failure-mode taxonomy table**

In the "Failure-mode taxonomy" section, remove this row (now wired to Slack, no longer silent):

```
| Backend PATCH 5xx | Commit is durable; log + exit 0. Slack post + status update missed. Sync via dashboard later. | No |
```

Replace it with these three rows:

```
| Agent rejected (`/tmp/agent-status.md`) | Slack thread reply under "New Issue"; retry counter incremented; cron retries up to 3× | Always — if reason is novel, append rule to LEARNINGS |
| Agent CLI crashed (exit ≠ 0) | Slack thread reply with workflow logs link; retry counter incremented | Only if recurring |
| Push rejected (cms-preview moved during run) | Slack thread reply; workflow exits non-zero; runner workspace is ephemeral so local commit is lost | Only if recurring |
| Backend PATCH 5xx | Retry 3× exp backoff; if still failing → direct Slack thread reply with manual recovery command; commit is durable | Only if recurring |
```

- [ ] **Step 3: Update AGENTS.md Hard rules section — cms-preview bullet**

Find the bullet (last line of "Hard rules"):

```
- Treat `cms-preview` as a long-lived branch. It is reset to production HEAD at the start of every solver run — any direct commits to `cms-preview` (from Stefan or anywhere outside the solver) WILL be overwritten. If Stefan needs to hotfix, he commits to the production branch (`main`/`master`) and the next solver run picks it up.
```

Replace with:

```
- `cms-preview` is a real staging branch. The solver clones it at HEAD without resetting and pushes plain (no `--force`). Direct edits to cms-preview by Stefan or anyone else are preserved across solver runs. If a push conflicts because cms-preview moved during a run, the workflow fails loudly (Slack thread reply + non-zero exit) rather than silently overwriting concurrent work.
```

- [ ] **Step 4: Update AGENTS.md Modifying-this-agent section**

Find the line:

```
If you change Phase 2 reset logic: keep `phases/2-clone.md` in sync with `clone_repo.py` + `repo.clone_and_reset_to_prod`. The `production_branch` column on `projects` is the source of truth — do not hardcode `main` or `master`.
```

Replace with:

```
If you change Phase 2 clone logic: keep `phases/2-clone.md` in sync with `clone_repo.py` + `repo.clone_at_preview_head`. The `repo_branch` column on `projects` is the source of truth for the staging branch name (always `cms-preview` for current clients but do not hardcode).
```

- [ ] **Step 5: Rewrite phases/2-clone.md**

Open `agents/Solver - Issues/phases/2-clone.md` and rewrite the section that describes the reset behavior. The clone now:
1. Clones the client repo at `cms-preview` HEAD (`git clone --branch cms-preview --depth 50`)
2. Saves the current HEAD SHA to `PREV_SHA_PATH` as the diff-anchor for revision-feedback retries (no longer the orphan-recovery hack — with model B, prior attempts live in the branch history)
3. Configures git user.email/user.name for downstream commits

Drop any mention of resetting to production. Drop the rationale about "S1.5 listener can fast-forward production to cms-preview after the fix" — with model B, the fast-forward still works the same way (cms-preview's HEAD is what production catches up to).

- [ ] **Step 6: Rewrite phases/4-push.md**

Open `agents/Solver - Issues/phases/4-push.md` and rewrite to describe plain `git push origin HEAD` (no `--force-with-lease`). Add a "Failure mode: push rejected" subsection:

```
**Failure mode: push rejected**

If cms-preview moved between clone and push (concurrent solver run, manual edit pushed by Stefan, etc.), `git push` returns non-zero. `repo.commit_and_push` raises `PushRejectedError`. `finalize.py` catches it, posts a Slack thread reply (kind=backend_error, "cms-preview moved during run; local commit lost — re-trigger workflow after staging stabilizes"), then re-raises. The `Release on failure` workflow step handles `release_issue_failed` (single retry increment). Runner workspace is ephemeral — the local commit cannot be recovered.
```

- [ ] **Step 7: Rewrite phases/5-finalize.md decision-tree section**

Open `agents/Solver - Issues/phases/5-finalize.md`. Find the section describing the decision tree and replace with:

```
**Decision tree (in order):**

1. `/tmp/agent-status.md` exists → `notify_agent_event(kind="rejected", reason=content[:500])` → `release_issue_failed` → exit 0.
2. `CLAUDE_EXIT_CODE != 0` (Claude CLI crashed: OAuth expired, max-turns, internal error) → `notify_agent_event(kind="agent_crashed", reason=f"CLI exit {code}")` → `release_issue_failed` → exit 0.
3. `not has_diff` (agent ran to completion but produced no file changes and no status.md) → `notify_agent_event(kind="no_diff", reason="Agent ran to completion but produced no file changes")` → `release_issue_failed` → exit 0.
4. Otherwise (happy path) → `commit_and_push` → `mark_done` → `trigger_issue_resolved` (3× exp backoff). On final retry failure → `slack.post_thread_event_direct(kind="backend_error", ...)` → exit 0 (the push is durable).
5. On `PushRejectedError` from commit_and_push → `notify_agent_event(kind="backend_error", reason=...)` → write `/tmp/agent-event-emitted` marker → re-raise. `Release on failure` step handles `release_issue_failed` (does not double-emit because of the marker).

Every notify_agent_event call writes `/tmp/agent-event-emitted` on success so `release_issue.py`'s own notify call in `Release on failure` does not duplicate.
```

- [ ] **Step 8: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/AGENTS.md" "agents/Solver - Issues/phases/2-clone.md" "agents/Solver - Issues/phases/4-push.md" "agents/Solver - Issues/phases/5-finalize.md"
```

Pause for Stefan's go-ahead.

---

# Phase 5 — Solver agent DB layer

## Task 8: Add claim_specific_issue in db.py

**Files:**
- Modify: `agents/Solver - Issues/db.py`
- Test: `agents/Solver - Issues/tests/test_db_claim.py`

- [ ] **Step 1: Write the failing test**

Append to `agents/Solver - Issues/tests/test_db_claim.py`:

```python
def test_claim_specific_returns_row_when_eligible(mock_pg):
    row = {
        "id": "issue-77",
        "project_id": "proj-1",
        "title": "x",
        "description": "y",
        "priority": "High",
        "status": "pending",
        "revision_feedback": None,
    }
    mock_pg["next_result"] = [row]
    assert db.claim_specific_issue("issue-77") == row


def test_claim_specific_returns_none_when_ineligible(mock_pg):
    mock_pg["next_result"] = []
    assert db.claim_specific_issue("issue-77") is None


def test_claim_specific_uses_correct_rpc_name(mock_pg):
    mock_pg["next_result"] = []
    db.claim_specific_issue("issue-77")
    assert mock_pg["calls"][0]["fn"] == "claim_specific_solver_issue"


def test_claim_specific_passes_issue_id_param(mock_pg):
    mock_pg["next_result"] = []
    db.claim_specific_issue("issue-abc")
    assert mock_pg["calls"][0]["params"]["p_issue_id"] == "issue-abc"


def test_claim_specific_respects_env_overrides(monkeypatch, mock_pg):
    monkeypatch.setenv("SOLVER_MAX_RETRIES", "5")
    monkeypatch.setenv("SOLVER_STALE_CLAIM_MINUTES", "30")
    mock_pg["next_result"] = []
    db.claim_specific_issue("issue-x")
    assert mock_pg["calls"][0]["params"]["p_max_retries"] == 5
    assert mock_pg["calls"][0]["params"]["p_stale_minutes"] == 30
```

- [ ] **Step 2: Run tests to verify they fail**

From `agents/Solver - Issues/`:
```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_db_claim.py -v -k "claim_specific"
```

Expected: 5 FAILURES with `AttributeError: module 'db' has no attribute 'claim_specific_issue'`.

- [ ] **Step 3: Implement claim_specific_issue**

Append to `agents/Solver - Issues/db.py` (after `claim_next_issue`):

```python
def claim_specific_issue(issue_id: str) -> dict | None:
    """Atomically claim a specific issue by id.

    Used when repository_dispatch.client_payload.issue_id is set (the user
    submitted an issue and dispatch fired immediately). If the targeted
    issue is no longer eligible (already done, claimed by another run,
    blocked, or maxed retries), returns None — caller should fall through
    to claim_next_issue() so the run still does useful work.
    """
    sb = _supabase()
    response = sb.rpc(
        "claim_specific_solver_issue",
        {
            "p_issue_id": issue_id,
            "p_max_retries": _max_retries(),
            "p_stale_minutes": _stale_minutes(),
        },
    ).execute()
    rows = response.data or []
    return rows[0] if rows else None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_db_claim.py -v -k "claim_specific"
```

Expected: 5 PASS.

- [ ] **Step 5: Run full db_claim test file**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_db_claim.py -v
```

Expected: all pass.

- [ ] **Step 6: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/db.py" "agents/Solver - Issues/tests/test_db_claim.py"
```

Pause for Stefan's go-ahead.

---

# Phase 6 — Solver claim_issue.py

## Task 9: Honor DISPATCH_ISSUE_ID env

**Files:**
- Modify: `agents/Solver - Issues/claim_issue.py`
- Test: `agents/Solver - Issues/tests/test_claim_issue.py`

- [ ] **Step 1: Write the failing tests**

Append to `agents/Solver - Issues/tests/test_claim_issue.py`:

```python
def test_dispatch_issue_id_calls_claim_specific(monkeypatch, tmp_path):
    import claim_issue
    monkeypatch.setenv("DISPATCH_ISSUE_ID", "issue-77")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh-output"))

    specific_calls = []
    next_calls = []
    monkeypatch.setattr(
        claim_issue.db,
        "claim_specific_issue",
        lambda id: specific_calls.append(id) or {
            "id": "issue-77", "project_id": "p1", "title": "t",
            "description": "d", "priority": "High", "status": "pending",
            "revision_feedback": None,
        },
    )
    monkeypatch.setattr(
        claim_issue.db,
        "claim_next_issue",
        lambda: next_calls.append("called") or None,
    )
    monkeypatch.setattr(
        claim_issue.db,
        "fetch_project",
        lambda pid: {"github_repo": "x/y", "repo_branch": "cms-preview", "production_branch": "main"},
    )

    monkeypatch.setattr(claim_issue, "ISSUE_JSON_PATH", str(tmp_path / "issue.json"))
    monkeypatch.setattr(claim_issue, "PROMPT_PATH", str(tmp_path / "prompt.md"))

    claim_issue.main()

    assert specific_calls == ["issue-77"]
    assert next_calls == []  # queue path NOT used


def test_dispatch_issue_id_falls_back_to_queue_when_ineligible(monkeypatch, tmp_path):
    import claim_issue
    monkeypatch.setenv("DISPATCH_ISSUE_ID", "issue-77")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh-output"))

    monkeypatch.setattr(claim_issue.db, "claim_specific_issue", lambda id: None)
    queue_row = {
        "id": "issue-other", "project_id": "p2", "title": "fallback",
        "description": "d", "priority": "Medium", "status": "pending",
        "revision_feedback": None,
    }
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: queue_row)
    monkeypatch.setattr(
        claim_issue.db, "fetch_project",
        lambda pid: {"github_repo": "x/y", "repo_branch": "cms-preview", "production_branch": "main"},
    )
    monkeypatch.setattr(claim_issue, "ISSUE_JSON_PATH", str(tmp_path / "issue.json"))
    monkeypatch.setattr(claim_issue, "PROMPT_PATH", str(tmp_path / "prompt.md"))

    claim_issue.main()

    import json
    written = json.loads((tmp_path / "issue.json").read_text())
    assert written["id"] == "issue-other"  # fallback succeeded


def test_no_dispatch_issue_id_uses_queue(monkeypatch, tmp_path):
    import claim_issue
    monkeypatch.delenv("DISPATCH_ISSUE_ID", raising=False)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh-output"))

    specific_calls = []
    monkeypatch.setattr(
        claim_issue.db, "claim_specific_issue",
        lambda id: specific_calls.append(id) or None,
    )
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: None)

    claim_issue.main()

    assert specific_calls == []  # specific path skipped entirely


def test_empty_dispatch_issue_id_treated_as_unset(monkeypatch, tmp_path):
    """GitHub passes empty string when client_payload is absent."""
    import claim_issue
    monkeypatch.setenv("DISPATCH_ISSUE_ID", "")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh-output"))

    specific_calls = []
    monkeypatch.setattr(
        claim_issue.db, "claim_specific_issue",
        lambda id: specific_calls.append(id) or None,
    )
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: None)

    claim_issue.main()
    assert specific_calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_claim_issue.py -v -k "dispatch"
```

Expected: 4 FAILURES — `claim_issue.main()` ignores `DISPATCH_ISSUE_ID`.

- [ ] **Step 3: Update claim_issue.py main()**

In `agents/Solver - Issues/claim_issue.py`, find the `main()` function. Replace the first line:

```python
def main() -> int:
    issue = db.claim_next_issue()
```

with:

```python
def main() -> int:
    dispatch_id = (os.environ.get("DISPATCH_ISSUE_ID") or "").strip()
    if dispatch_id:
        issue = db.claim_specific_issue(dispatch_id)
        if issue is None:
            # Targeted issue ineligible (already done, claimed by concurrent run,
            # blocked, or maxed retries). Fall back to the queue so the run still
            # does useful work — eg. drains the backlog of older issues.
            print(f"dispatch issue {dispatch_id} not eligible; falling back to queue")
            issue = db.claim_next_issue()
    else:
        issue = db.claim_next_issue()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_claim_issue.py -v -k "dispatch"
```

Expected: 4 PASS.

- [ ] **Step 5: Run full claim_issue test file**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_claim_issue.py -v
```

Expected: all pass.

- [ ] **Step 6: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/claim_issue.py" "agents/Solver - Issues/tests/test_claim_issue.py"
```

Pause for Stefan's go-ahead.

## Task 10: Update prompt builder

**Files:**
- Modify: `agents/Solver - Issues/claim_issue.py` (the `_build_prompt` function)
- Test: `agents/Solver - Issues/tests/test_claim_issue.py`

- [ ] **Step 1: Write the failing tests**

Append to `agents/Solver - Issues/tests/test_claim_issue.py`:

```python
def test_prompt_includes_source_of_truth_note():
    import claim_issue
    issue = {
        "id": "i1", "title": "t", "description": "d",
        "priority": "Medium", "revision_feedback": None,
    }
    project = {"repo_branch": "cms-preview"}
    prompt = claim_issue._build_prompt(issue, project)
    # Agent must understand it's reading staging, not prod.
    assert "cms-preview" in prompt
    assert "staging" in prompt.lower()
    assert "not production" in prompt.lower() or "not prod" in prompt.lower()


def test_prompt_revision_feedback_acknowledges_branch_head():
    import claim_issue
    issue = {
        "id": "i1", "title": "t", "description": "d",
        "priority": "Medium",
        "revision_feedback": "logo too small",
    }
    project = {"repo_branch": "cms-preview"}
    prompt = claim_issue._build_prompt(issue, project)
    # Revision flow with model B: prev attempt is at HEAD, not orphaned.
    assert "logo too small" in prompt
    assert "HEAD" in prompt
    # Must NOT contain the obsolete orphan-recovery prose.
    assert "no longer reachable" not in prompt
    assert ".git/objects" not in prompt


def test_prompt_content_not_code_rejection_hint():
    import claim_issue
    issue = {
        "id": "i1", "title": "t", "description": "d",
        "priority": "Medium", "revision_feedback": None,
    }
    project = {"repo_branch": "cms-preview"}
    prompt = claim_issue._build_prompt(issue, project)
    # Step 0 rejection guidance must include "name the dashboard tab".
    assert "dashboard" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_claim_issue.py -v -k "prompt"
```

Expected: 3 FAILURES — current prompt lacks source-of-truth note, HEAD-acknowledgement, and dashboard hint.

- [ ] **Step 3: Update _build_prompt — replace revision_section block**

In `agents/Solver - Issues/claim_issue.py`, find the existing `revision_section` block at the top of `_build_prompt`:

```python
def _build_prompt(issue: dict, project: dict) -> str:
    revision_section = ""
    if issue.get("revision_feedback"):
        revision_section = (
            "\n## Previous attempt was rejected\n"
            "Stefan's feedback on the last fix attempt:\n"
            f"> {issue['revision_feedback']}\n\n"
            "Your previous commit's SHA is in `/tmp/prev-solver-sha` (if "
            "non-empty). Read it and run `git show <sha>` from inside "
            "`./client-repo/` to see exactly what you changed last time. "
            f"The `{project['repo_branch']}` branch ref has been reset to "
            "the production HEAD, so the commit is no longer reachable "
            "from the branch, but the object is still in `.git/objects` "
            "and `git show` works.\n\n"
            "Use that diff to understand what you did, then address "
            "Stefan's feedback this time.\n"
        )
```

Replace with:

```python
def _build_prompt(issue: dict, project: dict) -> str:
    revision_section = ""
    if issue.get("revision_feedback"):
        revision_section = (
            "\n## Previous attempt was rejected\n"
            "Stefan's feedback on the last fix attempt:\n"
            f"> {issue['revision_feedback']}\n\n"
            f"Your previous commit is the HEAD of `{project['repo_branch']}` "
            "(it was NOT reverted server-side). Run `git log -3 --oneline` "
            "inside `./client-repo/` to see recent history, and `git show HEAD` "
            "to see the rejected diff.\n\n"
            "Decide: amend with a better fix on top of HEAD, OR revert HEAD "
            "first (`git revert --no-edit HEAD`) then write the correct fix. "
            "Amend is preferred when the rejection was about a missing detail; "
            "revert is preferred when the prior approach was fundamentally wrong.\n"
        )
```

- [ ] **Step 4: Update _build_prompt — add Source-of-truth note**

In the same function, find the `<repository>` section:

```python
<repository>
Working directory: `./client-repo/` (already cloned at branch `{project['repo_branch']}`).
</repository>
```

Replace with:

```python
<repository>
Working directory: `./client-repo/` (already cloned at branch `{project['repo_branch']}`).

**Source of truth:** You are reading the CURRENT state of `{project['repo_branch']}`, which IS the staging branch (not production). If the bug describes staging behavior, you should be able to reproduce it in this code. Production may have different state. Reason about staging, not prod.
</repository>
```

- [ ] **Step 5: Update _build_prompt — extend Step 0 rejection guidance**

Find Step 0's rejection guidance, which currently reads (around the "If you reject, write one line" section):

```python
If you reject, write one line to `/tmp/agent-status.md`:

> Cannot reproduce: <one-sentence reason naming what you looked at and why it does not match>

Then exit. Do not proceed to Step 1 on a guess.
```

Replace with:

```python
If you reject, write one line to `/tmp/agent-status.md` using the most appropriate prefix:

- `Cannot reproduce: <one-sentence reason naming what you looked at and why it does not match>`
- `Already fixed: <commit-sha-or-file-line that already implements the requested state>`
- `Wrong layer (content not code): <which dashboard tab the user should edit instead, eg "Content → Hero section" or "Content → Footer text">`
- `Cannot locate: <what you searched for and where>`
- `Ambiguous: <which two or more interpretations make the description unresolvable>`

For "Wrong layer (content not code)" rejections, the reason MUST name a specific
dashboard tab so the user has an actionable next step. The CMS dashboard has tabs
for editable content per page; tell them where to go.

Then exit. Do not proceed to Step 1 on a guess.
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_claim_issue.py -v -k "prompt"
```

Expected: 3 PASS.

- [ ] **Step 7: Run full claim_issue test file**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_claim_issue.py -v
```

Expected: all pass.

- [ ] **Step 8: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/claim_issue.py" "agents/Solver - Issues/tests/test_claim_issue.py"
```

Pause for Stefan's go-ahead.

---

# Phase 7 — Solver repo.py + clone_repo.py

## Task 11: Rename clone_and_reset_to_prod → clone_at_preview_head

**Files:**
- Modify: `agents/Solver - Issues/repo.py`
- Test: `agents/Solver - Issues/tests/test_repo.py`

- [ ] **Step 1: Write the failing tests**

In `agents/Solver - Issues/tests/test_repo.py`, append new tests (the existing `test_clone_and_reset_to_prod_*` tests will be replaced in Step 4):

```python
def test_clone_at_preview_head_clones_at_preview_no_reset(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(tmp_path / "prev-solver-sha"))
    repo.clone_at_preview_head(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        dest="./client-repo",
    )
    clone_call = fake_run[0]
    assert clone_call["args"][0] == "git"
    assert "clone" in clone_call["args"]
    assert "--branch" in clone_call["args"]
    branch_idx = clone_call["args"].index("--branch")
    assert clone_call["args"][branch_idx + 1] == "cms-preview"
    # No checkout/reset to a different branch should be issued.
    checkout_calls = [c for c in fake_run if "checkout" in str(c["args"])]
    assert checkout_calls == [], f"unexpected checkout: {checkout_calls}"


def test_clone_at_preview_head_saves_current_sha(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(tmp_path / "prev-solver-sha"))

    # Make `git rev-parse HEAD` return a deterministic sha.
    def run_with_sha(args, **kwargs):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.returncode = 0
        r.stdout = "abc1234defabc1234defabc1234defabc1234de\n" if args[-1] == "HEAD" else ""
        r.stderr = ""
        return r

    monkeypatch.setattr(repo.subprocess, "run", run_with_sha)

    repo.clone_at_preview_head(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        dest="./client-repo",
    )
    saved = (tmp_path / "prev-solver-sha").read_text().strip()
    assert saved == "abc1234defabc1234defabc1234defabc1234de"


def test_clone_at_preview_head_configures_git_user(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(tmp_path / "prev-solver-sha"))
    repo.clone_at_preview_head(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        dest="./client-repo",
    )
    user_email = [c for c in fake_run if "user.email" in str(c["args"])]
    user_name = [c for c in fake_run if "user.name" in str(c["args"])]
    assert len(user_email) == 1
    assert len(user_name) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_repo.py -v -k "clone_at_preview_head"
```

Expected: 3 FAILURES with `AttributeError: module 'repo' has no attribute 'clone_at_preview_head'`.

- [ ] **Step 3: Add clone_at_preview_head to repo.py**

In `agents/Solver - Issues/repo.py`, replace the entire existing `clone_and_reset_to_prod` function with:

```python
def clone_at_preview_head(
    *, repo_slug: str, dev_branch: str, dest: str
) -> None:
    """Clone client repo at dev_branch HEAD (no reset).

    With the staging-branch model (S3.5), cms-preview is a real staging
    branch — manual edits and prior unapproved solver attempts are preserved
    across runs. PREV_SHA_PATH stores the cloned HEAD SHA so revision-feedback
    retries can diff against the prior attempt's commit.
    """
    url = f"https://x-access-token:{_token()}@github.com/{repo_slug}.git"

    _run(
        [
            "git",
            "clone",
            "--depth",
            "50",
            "--branch",
            dev_branch,
            url,
            dest,
        ]
    )
    _run(["git", "-C", dest, "config", "user.email", _GIT_USER_EMAIL])
    _run(["git", "-C", dest, "config", "user.name", _GIT_USER_NAME])

    # Save current HEAD for revision-feedback diff context.
    sha_result = _run(["git", "-C", dest, "rev-parse", "HEAD"], check=False)
    prev_sha = sha_result.stdout.strip() if sha_result.returncode == 0 else ""
    Path(PREV_SHA_PATH).write_text(prev_sha)
```

Also remove the now-unused `--no-single-branch` flag (was needed for the dual-branch fetch under the old model; not needed for single-branch clone).

- [ ] **Step 4: Delete the now-orphan tests for clone_and_reset_to_prod**

In `agents/Solver - Issues/tests/test_repo.py`, delete the two tests that reference the removed function:
- `test_clone_and_reset_to_prod_clones_with_no_single_branch`
- `test_clone_and_reset_configures_git_user`

(Their coverage is replaced by the new tests added in Step 1.)

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_repo.py -v
```

Expected: all pass; the deleted tests no longer appear in the collected set; new `test_clone_at_preview_head_*` tests pass.

- [ ] **Step 6: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/repo.py" "agents/Solver - Issues/tests/test_repo.py"
```

Pause for Stefan's go-ahead.

## Task 12: Update clone_repo.py call signature

**Files:**
- Modify: `agents/Solver - Issues/clone_repo.py`

- [ ] **Step 1: Update the call in main()**

In `agents/Solver - Issues/clone_repo.py`, find:

```python
    repo.clone_and_reset_to_prod(
        repo_slug=project["github_repo"],
        dev_branch=project["repo_branch"],
        prod_branch=project["production_branch"],
        dest=dest,
    )
    print(
        f"cloned {project['github_repo']}: "
        f"reset {project['repo_branch']} → origin/{project['production_branch']} → {dest}"
    )
```

Replace with:

```python
    repo.clone_at_preview_head(
        repo_slug=project["github_repo"],
        dev_branch=project["repo_branch"],
        dest=dest,
    )
    prev_sha = Path(repo.PREV_SHA_PATH).read_text().strip()
    print(
        f"cloned {project['github_repo']}: "
        f"{project['repo_branch']} HEAD = {prev_sha[:7] if prev_sha else '(empty)'} → {dest}"
    )
```

Add `from pathlib import Path` to the imports if not already present.

- [ ] **Step 2: Manually verify the file imports cleanly**

```bash
cd "agents/Solver - Issues" && python -c "import clone_repo; print('ok')"
```

Expected: prints `ok` with no traceback.

- [ ] **Step 3: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/clone_repo.py"
```

Pause for Stefan's go-ahead.

## Task 13: Plain push + PushRejectedError

**Files:**
- Modify: `agents/Solver - Issues/repo.py`
- Test: `agents/Solver - Issues/tests/test_repo.py`

- [ ] **Step 1: Write the failing tests**

Append to `agents/Solver - Issues/tests/test_repo.py`:

```python
def test_commit_and_push_uses_plain_push_no_force(fake_run, tmp_path):
    sha = repo.commit_and_push(path=str(tmp_path), issue_id="i1", issue_title="t")
    push_calls = [c for c in fake_run if "push" in c["args"]]
    assert len(push_calls) == 1
    push_args = push_calls[0]["args"]
    assert "--force" not in str(push_args)
    assert "--force-with-lease" not in str(push_args)


def test_commit_and_push_raises_push_rejected_error(monkeypatch, tmp_path):
    """When git push exits non-zero, raise PushRejectedError instead of CalledProcessError."""
    from subprocess import CompletedProcess, CalledProcessError

    def run(args, **kwargs):
        if "push" in args:
            raise CalledProcessError(
                returncode=1, cmd=args, stderr="rejected — non-fast-forward",
            )
        return CompletedProcess(args=args, returncode=0, stdout="abc123\n", stderr="")

    monkeypatch.setattr(repo.subprocess, "run", run)
    monkeypatch.setenv("SOLVER_GITHUB_TOKEN", "ghs_test")

    with pytest.raises(repo.PushRejectedError):
        repo.commit_and_push(path=str(tmp_path), issue_id="i1", issue_title="t")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_repo.py -v -k "push"
```

Expected: 2 FAILURES — current code uses `--force-with-lease`, no `PushRejectedError` class exists.

- [ ] **Step 3: Update repo.py**

In `agents/Solver - Issues/repo.py`:

(a) Add at module level (after the `_MAX_TITLE_LEN` constant):

```python
class PushRejectedError(Exception):
    """Raised when git push fails because the remote branch moved.

    The runner workspace is ephemeral — when this is raised, the local
    commit cannot be recovered. finalize.py catches this and emits a
    distinct Slack event (kind=backend_error, "cms-preview moved during run").
    """
```

(b) Replace the existing `commit_and_push` function:

```python
def commit_and_push(*, path: str, issue_id: str, issue_title: str) -> str:
    """Stage all changes, commit, push current HEAD to origin (plain push).

    Plain `git push` (no --force-with-lease) — cms-preview is now a real
    staging branch with potentially-meaningful state. If the remote moved
    during the run, raise PushRejectedError so finalize.py can emit the
    distinct "branch moved" Slack event.

    Returns the new HEAD SHA on success.
    """
    short_title = issue_title[:_MAX_TITLE_LEN]
    message = (
        f"fix: {short_title}\n\n"
        f"Automated fix by Solver Agent for CMS issue {issue_id}.\n\n"
        f"Co-Authored-By: Solver Agent (Claude Code) <{_GIT_USER_EMAIL}>"
    )
    _run(["git", "-C", path, "add", "-A"])
    _run(["git", "-C", path, "commit", "-m", message])
    sha_result = _run(["git", "-C", path, "rev-parse", "HEAD"])
    sha = sha_result.stdout.strip()
    try:
        _run(["git", "-C", path, "push", "origin", "HEAD"])
    except subprocess.CalledProcessError as e:
        raise PushRejectedError(
            f"git push to {path} HEAD failed: {e.stderr or e.stdout or 'unknown'}"
        ) from e
    return sha
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_repo.py -v -k "push"
```

Expected: 2 PASS.

- [ ] **Step 5: Run full repo test file**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_repo.py -v
```

Expected: all pass.

- [ ] **Step 6: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/repo.py" "agents/Solver - Issues/tests/test_repo.py"
```

Pause for Stefan's go-ahead.

---

# Phase 8 — Solver backend_api.py + slack.py

## Task 14: Add notify_agent_event + retry wrapper in backend_api.py

**Files:**
- Modify: `agents/Solver - Issues/backend_api.py`
- Create: `agents/Solver - Issues/tests/test_backend_api.py`

- [ ] **Step 1: Write the failing tests**

Create `agents/Solver - Issues/tests/test_backend_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_backend_api.py -v
```

Expected: tests fail with `AttributeError` (notify_agent_event missing, retry logic missing).

- [ ] **Step 3: Rewrite backend_api.py**

Replace the entire contents of `agents/Solver - Issues/backend_api.py` with:

```python
"""HTTP client for the backend admin endpoints.

Used by finalize.py to:
- mark issues done via PATCH /admin/issues/{id}/status (with 3× exp backoff
  on 5xx; 4xx fails immediately as it indicates a permission or schema bug
  rather than a transient outage)
- post solver agent events (rejection / no-diff / crash / backend-error) via
  POST /admin/issues/{id}/agent-event (best-effort; log on failure but never
  raise — agent events are a visibility feature, not a correctness one).
"""

from __future__ import annotations

import logging
import os
import time

import requests
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

_TIMEOUT = 15
_RETRY_BACKOFFS = (1.0, 2.0, 4.0)


def _backend_url() -> str:
    return os.environ["CMS_BACKEND_URL"].rstrip("/")


def _token() -> str:
    return os.environ["CMS_API_TOKEN"]


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
        "User-Agent": "solver-agent/1.0",
    }


def trigger_issue_resolved(issue_id: str) -> dict:
    """PATCH /admin/issues/{id}/status with status='done'.

    Retries up to 3 times with exponential backoff (1s/2s/4s) on 5xx errors.
    Does NOT retry on 4xx (likely permission/schema bug — fail fast).
    Raises HTTPError on final failure or 4xx.
    """
    url = f"{_backend_url()}/admin/issues/{issue_id}/status"
    last_error: Exception | None = None

    for attempt, backoff in enumerate(_RETRY_BACKOFFS, start=1):
        try:
            response = requests.patch(
                url, headers=_headers(), json={"status": "done"}, timeout=_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            last_error = e
            status_code = e.response.status_code if e.response is not None else 0
            if 400 <= status_code < 500:
                # Client error — don't retry.
                raise
            logger.warning(
                "trigger_issue_resolved attempt %d/%d failed: %s; sleeping %.1fs",
                attempt, len(_RETRY_BACKOFFS), e, backoff,
            )
            if attempt < len(_RETRY_BACKOFFS):
                time.sleep(backoff)
        except (ConnectionError, requests.exceptions.Timeout) as e:
            last_error = e
            logger.warning(
                "trigger_issue_resolved attempt %d/%d network error: %s; sleeping %.1fs",
                attempt, len(_RETRY_BACKOFFS), e, backoff,
            )
            if attempt < len(_RETRY_BACKOFFS):
                time.sleep(backoff)

    assert last_error is not None  # at least one attempt must have failed
    raise last_error


def notify_agent_event(issue_id: str, *, kind: str, reason: str) -> None:
    """POST /admin/issues/{id}/agent-event for a solver-side event.

    Best-effort: logs but never raises. Slack/observability is not allowed
    to break the workflow — if this fails, the DB state is still correct
    (release_issue_failed already committed the retry-counter increment).
    """
    url = f"{_backend_url()}/admin/issues/{issue_id}/agent-event"
    try:
        response = requests.post(
            url, headers=_headers(),
            json={"kind": kind, "reason": reason[:500]},
            timeout=_TIMEOUT,
        )
        if response.status_code >= 400:
            logger.warning(
                "notify_agent_event returned %d: %s",
                response.status_code,
                response.text[:200],
            )
    except Exception:
        logger.exception("notify_agent_event POST failed (swallowed)")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_backend_api.py -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/backend_api.py" "agents/Solver - Issues/tests/test_backend_api.py"
```

Pause for Stefan's go-ahead.

## Task 15: Add post_thread_event_direct in slack.py

**Files:**
- Modify: `agents/Solver - Issues/slack.py`

This is the fallback used in finalize.py when the backend itself is the failing target (backend-trigger-resolved-failed path). It posts the same thread reply that the backend's `/admin/issues/{id}/agent-event` route would have posted, but via direct Slack chat.postMessage from the runner.

- [ ] **Step 1: Write the test (no separate file needed; extend slack.py self-tests if any; otherwise add to test_backend_api.py)**

Append to `agents/Solver - Issues/tests/test_backend_api.py`:

```python
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
    slack_client.post_thread_event_direct(
        thread_ts="x", kind="backend_error", reason="y"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_backend_api.py -v -k "post_thread_event_direct"
```

Expected: 2 FAILURES with `AttributeError`.

- [ ] **Step 3: Add post_thread_event_direct to slack.py**

Append to `agents/Solver - Issues/slack.py`:

```python
_EVENT_EMOJI = {
    "rejected": "🤔",
    "no_diff": "⚠️",
    "agent_crashed": "🔧",
    "backend_error": "🛑",
}

_EVENT_HEADER = {
    "rejected": "Agent reviewed, no change",
    "no_diff": "Agent produced no file changes",
    "agent_crashed": "Agent CLI crashed",
    "backend_error": "Backend / push error",
}


def post_thread_event_direct(
    *,
    thread_ts: str | None,
    kind: str,
    reason: str,
) -> None:
    """Direct chat.postMessage thread reply — fallback when backend is failing.

    Used by finalize.py when trigger_issue_resolved exhausts its retries; at
    that point we can't reach the backend's /admin/issues/{id}/agent-event
    route to post the event, so we go direct to Slack with the same emoji +
    header convention.

    Silently disabled when SLACK_BOT_TOKEN or SLACK_ISSUES_CHANNEL_ID is unset.
    Never raises.
    """
    if not _enabled():
        logger.info("slack disabled — skipping post_thread_event_direct")
        return

    emoji = _EVENT_EMOJI.get(kind, "❔")
    header = _EVENT_HEADER.get(kind, "Agent event")
    reason_trimmed = (reason or "")[:500]
    text = f"{emoji} {header} — {reason_trimmed}"

    try:
        body: dict = {
            "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
            "text": text,
        }
        if thread_ts:
            body["thread_ts"] = thread_ts
        response = requests.post(
            _SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=body,
            timeout=_TIMEOUT,
        )
        body = response.json()
        if not body.get("ok"):
            logger.warning("post_thread_event_direct failed: %s", body.get("error"))
    except Exception:
        logger.exception("post_thread_event_direct exception")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_backend_api.py -v -k "post_thread_event_direct"
```

Expected: 2 PASS.

- [ ] **Step 5: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/slack.py" "agents/Solver - Issues/tests/test_backend_api.py"
```

Pause for Stefan's go-ahead.

---

# Phase 9 — Solver finalize.py + release_issue.py

## Task 16: Restructure finalize.py decision tree

**Files:**
- Modify: `agents/Solver - Issues/finalize.py`
- Test: `agents/Solver - Issues/tests/test_finalize.py`

- [ ] **Step 1: Write the failing tests**

Append to `agents/Solver - Issues/tests/test_finalize.py`:

```python
def test_status_md_rejected_calls_notify_agent_event(monkeypatch, issue_payload):
    issue_payload["status_path"].write_text("Cannot reproduce: x")
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")

    notify_calls: list[dict] = []
    monkeypatch.setattr(
        finalize.backend_api,
        "notify_agent_event",
        lambda iid, *, kind, reason: notify_calls.append({"iid": iid, "kind": kind, "reason": reason}),
    )
    monkeypatch.setattr(finalize.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push"))

    assert finalize.main() == 0
    assert len(notify_calls) == 1
    assert notify_calls[0]["kind"] == "rejected"
    assert "Cannot reproduce" in notify_calls[0]["reason"]


def test_claude_exit_nonzero_calls_notify_agent_crashed(monkeypatch, issue_payload):
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "1")

    notify_calls: list[dict] = []
    monkeypatch.setattr(
        finalize.backend_api,
        "notify_agent_event",
        lambda iid, *, kind, reason: notify_calls.append({"kind": kind, "reason": reason}),
    )
    monkeypatch.setattr(finalize.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push"))

    assert finalize.main() == 0
    assert notify_calls[0]["kind"] == "agent_crashed"
    assert "exit 1" in notify_calls[0]["reason"].lower()


def test_no_diff_calls_notify_no_diff(monkeypatch, issue_payload):
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")

    notify_calls: list[dict] = []
    monkeypatch.setattr(
        finalize.backend_api,
        "notify_agent_event",
        lambda iid, *, kind, reason: notify_calls.append({"kind": kind, "reason": reason}),
    )
    monkeypatch.setattr(finalize.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: False)

    assert finalize.main() == 0
    assert notify_calls[0]["kind"] == "no_diff"


def test_push_rejected_calls_notify_backend_error_and_reraises(monkeypatch, issue_payload):
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")

    notify_calls: list[dict] = []
    monkeypatch.setattr(
        finalize.backend_api,
        "notify_agent_event",
        lambda iid, *, kind, reason: notify_calls.append({"kind": kind, "reason": reason}),
    )
    monkeypatch.setattr(finalize.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)

    def push_fail(**kw):
        raise finalize.repo.PushRejectedError("rejected — non-fast-forward")

    monkeypatch.setattr(finalize.repo, "commit_and_push", push_fail)

    with pytest.raises(finalize.repo.PushRejectedError):
        finalize.main()
    assert notify_calls[0]["kind"] == "backend_error"
    assert "moved during run" in notify_calls[0]["reason"]


def test_backend_trigger_failure_falls_back_to_direct_slack(monkeypatch, issue_payload, tmp_path):
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")

    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: "abc123")
    monkeypatch.setattr(finalize.db, "mark_done", lambda *a, **kw: None)

    def boom(issue_id):
        from requests.exceptions import HTTPError
        raise HTTPError("500 after retries")

    monkeypatch.setattr(finalize.backend_api, "trigger_issue_resolved", boom)

    # Need slack_created_ts lookup — stub via supabase or environment.
    monkeypatch.setattr(
        finalize, "_fetch_slack_created_ts", lambda iid: "ts-original",
        raising=False,  # function may not exist yet — defined in impl step
    )

    direct_calls: list[dict] = []
    import slack as slack_client
    monkeypatch.setattr(
        slack_client,
        "post_thread_event_direct",
        lambda **kw: direct_calls.append(kw),
    )

    assert finalize.main() == 0  # commit is durable; exit 0
    assert direct_calls[0]["kind"] == "backend_error"


def test_happy_path_writes_event_marker(monkeypatch, issue_payload, tmp_path):
    """Successful flows should write /tmp/agent-event-emitted only when an event was emitted."""
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")
    marker = tmp_path / "agent-event-emitted"
    monkeypatch.setattr(finalize, "EVENT_MARKER_PATH", str(marker))

    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: "abc123")
    monkeypatch.setattr(finalize.db, "mark_done", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.backend_api, "trigger_issue_resolved", lambda iid: {"ok": True})

    finalize.main()
    # Happy path emits NO agent event → marker should NOT exist.
    assert not marker.exists()


def test_event_emission_writes_marker(monkeypatch, issue_payload, tmp_path):
    """Any branch that calls notify_agent_event must write the marker."""
    issue_payload["status_path"].write_text("Cannot reproduce: x")
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")
    marker = tmp_path / "agent-event-emitted"
    monkeypatch.setattr(finalize, "EVENT_MARKER_PATH", str(marker))

    monkeypatch.setattr(finalize.backend_api, "notify_agent_event", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push"))

    finalize.main()
    assert marker.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_finalize.py -v -k "notify_agent_event or no_diff or push_rejected or backend_trigger_failure or event_marker"
```

Expected: 7 FAILURES across the tests above.

- [ ] **Step 3: Rewrite finalize.py**

Replace the entire contents of `agents/Solver - Issues/finalize.py` with:

```python
"""Workflow entrypoint after the Claude Code action runs.

Decision tree (in order):
1. /tmp/agent-status.md exists                → notify_agent_event(rejected)        → release_failed, exit 0
2. CLAUDE_EXIT_CODE != 0                       → notify_agent_event(agent_crashed)   → release_failed, exit 0
3. no diff in working tree                     → notify_agent_event(no_diff)         → release_failed, exit 0
4. otherwise (happy path)                      → commit_and_push → mark_done →
                                                  trigger_issue_resolved (3× retry) →
                                                  on retry exhaustion: direct Slack fallback
5. PushRejectedError from commit_and_push      → notify_agent_event(backend_error)   → write marker → re-raise

Every notify_agent_event call writes /tmp/agent-event-emitted; release_issue.py
checks for it on the failure path to avoid double-posting.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import backend_api
import db
import repo
import slack as slack_client
from supabase import create_client

logger = logging.getLogger(__name__)

ISSUE_JSON_PATH = "/tmp/issue.json"
STATUS_MD_PATH = "/tmp/agent-status.md"
EVENT_MARKER_PATH = "/tmp/agent-event-emitted"
REPO_DIR = "./client-repo"


def _write_event_marker() -> None:
    """Marker so release_issue.py knows finalize already emitted an event."""
    try:
        Path(EVENT_MARKER_PATH).write_text("1")
    except Exception:
        logger.exception("could not write event marker (continuing)")


def _emit_event(issue_id: str, kind: str, reason: str) -> None:
    backend_api.notify_agent_event(issue_id, kind=kind, reason=reason)
    _write_event_marker()


def _fetch_slack_created_ts(issue_id: str) -> str | None:
    """Direct supabase lookup — used only on the backend-error fallback path
    where the backend admin endpoint itself is the failing target."""
    try:
        sb = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        result = (
            sb.table("project_issues")
            .select("slack_created_ts")
            .eq("id", issue_id)
            .single()
            .execute()
        )
        return (result.data or {}).get("slack_created_ts")
    except Exception:
        logger.exception("could not fetch slack_created_ts for fallback")
        return None


def main() -> int:
    issue = json.loads(Path(ISSUE_JSON_PATH).read_text())
    issue_id = issue["id"]
    status_md = Path(STATUS_MD_PATH)
    claude_exit_code = int(os.environ.get("CLAUDE_EXIT_CODE", "0") or "0")

    # Branch 1: Agent rejected with a written reason.
    if status_md.exists():
        reason = status_md.read_text().strip()[:500] or "agent wrote empty status.md"
        _emit_event(issue_id, kind="rejected", reason=reason)
        db.release_issue_failed(issue_id, reason)
        print(f"released as failed (rejected): {reason}")
        return 0

    # Branch 2: Claude CLI exited non-zero (OAuth, max-turns, internal error).
    if claude_exit_code != 0:
        reason = f"CLI exit {claude_exit_code} — see workflow logs"
        _emit_event(issue_id, kind="agent_crashed", reason=reason)
        db.release_issue_failed(issue_id, reason)
        print(f"released as failed (agent crashed): {reason}")
        return 0

    # Branch 3: No file changes and no status.md (likely agent forgot to write).
    if not repo.has_diff(REPO_DIR):
        reason = (
            "Agent ran to completion but produced no file changes and no status.md "
            "— likely forgot to write a reject reason before exiting"
        )
        _emit_event(issue_id, kind="no_diff", reason=reason)
        db.release_issue_failed(issue_id, "no file changes")
        print("released as failed (no diff)")
        return 0

    # Branch 4 (happy path) or Branch 5 (push rejected).
    try:
        sha = repo.commit_and_push(
            path=REPO_DIR, issue_id=issue_id, issue_title=issue["title"],
        )
    except repo.PushRejectedError as e:
        reason = (
            f"cms-preview moved during run; local commit lost (runner workspace "
            f"is ephemeral). Re-trigger the workflow after staging stabilizes. "
            f"Detail: {e}"
        )
        _emit_event(issue_id, kind="backend_error", reason=reason)
        # Do NOT release_issue_failed here — let `Release on failure` workflow
        # step do it (via release_issue.py). The event marker we just wrote
        # prevents release_issue.py from double-posting.
        raise

    print(f"pushed commit {sha[:7]}")
    db.mark_done(issue_id, commit_sha=sha)

    # Branch 4 happy path: tell backend, which fires the "✅ Resolved" Slack post.
    try:
        backend_api.trigger_issue_resolved(issue_id)
        print("backend mark-done + Slack notify dispatched")
    except Exception as e:
        # Backend is the failing target — go direct to Slack so the user sees
        # SOMETHING. The push and mark_done already happened, so the work is
        # durable; this is just observability.
        logger.exception("backend trigger_issue_resolved failed after retries")
        thread_ts = _fetch_slack_created_ts(issue_id)
        slack_client.post_thread_event_direct(
            thread_ts=thread_ts,
            kind="backend_error",
            reason=(
                f"Fix pushed (sha {sha[:7]}) but backend mark-done failed: {e}. "
                f"Manual recovery: PATCH /admin/issues/{issue_id}/status with "
                f'{{"status": "done"}}'
            ),
        )
        _write_event_marker()
        # exit 0 — the push is durable; this is observability only.

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_finalize.py -v
```

Expected: all tests pass (existing tests for status_md branches still pass; new tests for the kind-specific notify calls pass; marker tests pass).

- [ ] **Step 5: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/finalize.py" "agents/Solver - Issues/tests/test_finalize.py"
```

Pause for Stefan's go-ahead.

## Task 17: Update release_issue.py with notify + de-dup

**Files:**
- Modify: `agents/Solver - Issues/release_issue.py`
- Test: `agents/Solver - Issues/tests/test_db_release.py`

- [ ] **Step 1: Write the failing tests**

Append to `agents/Solver - Issues/tests/test_db_release.py`:

```python
def test_release_issue_emits_agent_event_when_no_marker(monkeypatch, tmp_path):
    """Release_issue.py called from Release on failure (no marker present) → emits event."""
    import release_issue, json

    issue_path = tmp_path / "issue.json"
    issue_path.write_text(json.dumps({
        "id": "issue-77", "title": "t", "project": {"slug": "acme", "name": "Acme"},
    }))
    marker = tmp_path / "agent-event-emitted"

    monkeypatch.setattr(release_issue, "ISSUE_JSON_PATH", str(issue_path))
    monkeypatch.setattr(release_issue, "EVENT_MARKER_PATH", str(marker))
    monkeypatch.setenv("FAILED_STEP", "Clone client repo")

    notify_calls: list[dict] = []
    monkeypatch.setattr(
        release_issue.backend_api, "notify_agent_event",
        lambda iid, *, kind, reason: notify_calls.append({"kind": kind, "reason": reason}),
    )
    monkeypatch.setattr(release_issue.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(release_issue, "_current_retry_count", lambda iid: 1)

    release_issue.main()

    assert len(notify_calls) == 1
    assert notify_calls[0]["kind"] == "agent_crashed"
    assert "Clone client repo" in notify_calls[0]["reason"]


def test_release_issue_skips_emit_when_marker_present(monkeypatch, tmp_path):
    """When finalize.py already emitted an event (marker exists), don't double-post."""
    import release_issue, json

    issue_path = tmp_path / "issue.json"
    issue_path.write_text(json.dumps({
        "id": "issue-77", "title": "t", "project": {"slug": "acme", "name": "Acme"},
    }))
    marker = tmp_path / "agent-event-emitted"
    marker.write_text("1")  # finalize.py already wrote it

    monkeypatch.setattr(release_issue, "ISSUE_JSON_PATH", str(issue_path))
    monkeypatch.setattr(release_issue, "EVENT_MARKER_PATH", str(marker))

    notify_calls: list = []
    monkeypatch.setattr(
        release_issue.backend_api, "notify_agent_event",
        lambda *a, **kw: notify_calls.append(1),
    )
    monkeypatch.setattr(release_issue.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(release_issue, "_current_retry_count", lambda iid: 1)

    release_issue.main()
    assert notify_calls == []  # de-dup'd


def test_release_issue_no_claim_skips_everything(monkeypatch, tmp_path):
    """When /tmp/issue.json doesn't exist, no claim was made → exit clean."""
    import release_issue
    monkeypatch.setattr(release_issue, "ISSUE_JSON_PATH", str(tmp_path / "missing.json"))

    notify_calls: list = []
    monkeypatch.setattr(
        release_issue.backend_api, "notify_agent_event",
        lambda *a, **kw: notify_calls.append(1),
    )

    assert release_issue.main() == 0
    assert notify_calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_db_release.py -v -k "release_issue_emits or release_issue_skips or release_issue_no_claim"
```

Expected: 3 FAILURES (release_issue.py doesn't import backend_api yet, doesn't have EVENT_MARKER_PATH, doesn't call notify_agent_event).

- [ ] **Step 3: Rewrite release_issue.py**

Replace the entire contents of `agents/Solver - Issues/release_issue.py` with:

```python
"""Workflow entrypoint on `failure()` — increment retry counter + notify Slack.

Reads issue id from /tmp/issue.json (claim_issue.py wrote it). If the file
doesn't exist, no issue was claimed → exit clean.

De-dup with finalize.py: if /tmp/agent-event-emitted exists, finalize already
posted the relevant Slack thread reply (eg. on PushRejectedError) — skip our
own emission to avoid posting two messages for one failure.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import backend_api
import db
import slack as slack_client

logger = logging.getLogger(__name__)

ISSUE_JSON_PATH = "/tmp/issue.json"
EVENT_MARKER_PATH = "/tmp/agent-event-emitted"


def main() -> int:
    path = Path(ISSUE_JSON_PATH)
    if not path.exists():
        print("no claim to release")
        return 0

    issue = json.loads(path.read_text())
    error = _failure_reason()

    db.release_issue_failed(issue["id"], error)
    print(f"released issue {issue['id']} as failed: {error[:80]}")

    # De-dup: if finalize.py already emitted an event for this failure, skip.
    if Path(EVENT_MARKER_PATH).exists():
        print("event already emitted by finalize.py — skipping duplicate")
    else:
        try:
            backend_api.notify_agent_event(
                issue["id"],
                kind="agent_crashed",
                reason=error,
            )
        except Exception:  # noqa: BLE001 — best-effort
            logger.exception("backend notify_agent_event failed (continuing)")

    new_count = _current_retry_count(issue["id"])
    max_retries = int(os.environ.get("SOLVER_MAX_RETRIES", "3"))
    if new_count >= max_retries:
        project = issue.get("project", {}) or {}
        slack_client.post_blocked_notification(
            issue_id=issue["id"],
            title=issue["title"],
            project_name=project.get("name") or project.get("slug", "unknown"),
            retry_count=new_count,
            last_error=error,
        )

    return 0


def _failure_reason() -> str:
    failed_step = os.environ.get("FAILED_STEP", "")
    if failed_step:
        return f"workflow step failed: {failed_step}"
    return "workflow failure (no specific step recorded)"


def _current_retry_count(issue_id: str) -> int:
    sb = db._supabase()
    row = (
        sb.table("project_issues").select("agent_retry_count").eq("id", issue_id).single().execute()
    )
    return row.data["agent_retry_count"]


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_db_release.py -v
```

Expected: all pass (existing tests still work; new 3 pass).

- [ ] **Step 5: Stage + checkpoint**

```bash
git add "agents/Solver - Issues/release_issue.py" "agents/Solver - Issues/tests/test_db_release.py"
```

Pause for Stefan's go-ahead.

---

# Phase 10 — Workflow yml

## Task 18: Update solver-agent.yml

**Files:**
- Modify: `.github/workflows/solver-agent.yml`

- [ ] **Step 1: Read current workflow**

Read `.github/workflows/solver-agent.yml` to confirm current step layout (steps named "Claim next issue", "Run Claude headless against client repo", "Commit, push, mark done", "Release on failure").

- [ ] **Step 2: Pass DISPATCH_ISSUE_ID env to Claim step**

Find:

```yaml
      - name: Claim next issue
        id: claim
        run: python "agents/Solver - Issues/claim_issue.py"
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
```

Replace with:

```yaml
      - name: Claim next issue
        id: claim
        run: python "agents/Solver - Issues/claim_issue.py"
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          DISPATCH_ISSUE_ID: ${{ github.event.client_payload.issue_id }}
```

- [ ] **Step 3: Capture Claude CLI exit code**

Find the "Run Claude headless against client repo" step. Add `id: claude`, remove `continue-on-error: true`, and wrap the claude command to capture exit code:

```yaml
      - name: Run Claude headless against client repo
        id: claude
        if: steps.claim.outputs.has_issue == 'true'
        # Captures the CLI exit code so finalize.py can distinguish "agent
        # crashed" (exit ≠ 0) from "agent exited normally with no diff" (exit
        # = 0, no /tmp/agent-status.md, no file changes). Without this split,
        # all silent exits look identical in Slack.
        env:
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
        run: |
          cd ./client-repo
          set +e
          claude --print \
            --model claude-opus-4-7 \
            --max-turns 80 \
            --allowed-tools "Read,Edit,Write,Glob,Grep,Bash(npm run *:*),Bash(node:*),Bash(npx tsc:*),Bash(git diff:*),Bash(git status:*),Bash(git show:*)" \
            --disallowed-tools "Bash(git push:*),Bash(git commit:*),Bash(rm:*),WebFetch,WebSearch" \
            < /tmp/agent-prompt.md
          EXIT_CODE=$?
          set -e
          echo "exit_code=${EXIT_CODE}" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 4: Pass CLAUDE_EXIT_CODE to finalize step**

Find:

```yaml
      - name: Commit, push, mark done
        if: steps.claim.outputs.has_issue == 'true'
        run: python "agents/Solver - Issues/finalize.py"
        env:
          SOLVER_GITHUB_TOKEN: ${{ secrets.SOLVER_GITHUB_TOKEN }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          CMS_API_TOKEN: ${{ secrets.CMS_API_TOKEN }}
          CMS_BACKEND_URL: https://cms-backend-roman.vercel.app
```

Replace with:

```yaml
      - name: Commit, push, mark done
        if: steps.claim.outputs.has_issue == 'true'
        run: python "agents/Solver - Issues/finalize.py"
        env:
          SOLVER_GITHUB_TOKEN: ${{ secrets.SOLVER_GITHUB_TOKEN }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          CMS_API_TOKEN: ${{ secrets.CMS_API_TOKEN }}
          CMS_BACKEND_URL: https://cms-backend-roman.vercel.app
          CLAUDE_EXIT_CODE: ${{ steps.claude.outputs.exit_code }}
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          SLACK_ISSUES_CHANNEL_ID: ${{ secrets.SLACK_ISSUES_CHANNEL_ID }}
```

(SLACK_BOT_TOKEN + SLACK_ISSUES_CHANNEL_ID are new here — needed for the direct-Slack fallback path when backend trigger fails.)

- [ ] **Step 5: Pass CMS_BACKEND_URL/CMS_API_TOKEN/SLACK_* to Release on failure step**

Find the existing Release on failure step:

```yaml
      - name: Release on failure
        if: failure() && steps.claim.outputs.has_issue == 'true'
        run: python "agents/Solver - Issues/release_issue.py"
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          SOLVER_MAX_RETRIES: '3'
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          SLACK_ISSUES_CHANNEL_ID: ${{ secrets.SLACK_ISSUES_CHANNEL_ID }}
```

Add CMS_BACKEND_URL + CMS_API_TOKEN env (release_issue.py now calls backend_api.notify_agent_event):

```yaml
      - name: Release on failure
        if: failure() && steps.claim.outputs.has_issue == 'true'
        run: python "agents/Solver - Issues/release_issue.py"
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          SOLVER_MAX_RETRIES: '3'
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          SLACK_ISSUES_CHANNEL_ID: ${{ secrets.SLACK_ISSUES_CHANNEL_ID }}
          CMS_API_TOKEN: ${{ secrets.CMS_API_TOKEN }}
          CMS_BACKEND_URL: https://cms-backend-roman.vercel.app
```

- [ ] **Step 6: Validate YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/solver-agent.yml'))" && echo "YAML OK"
```

Expected: prints `YAML OK`, no traceback.

- [ ] **Step 7: Stage + checkpoint**

```bash
git add .github/workflows/solver-agent.yml
```

Pause for Stefan's go-ahead.

---

# Phase 11 — Smoke test + cleanup

## Task 19: Smoke test + unblock the stuck issue

**Files:** none (operational task)

Run AFTER both PRs (backend + solver) have been merged to master and deployed.

- [ ] **Step 1: Verify backend deploy**

```bash
curl -i https://cms-backend-roman.vercel.app/admin/issues/dummy/agent-event \
  -X POST -H "Content-Type: application/json" -d '{"kind":"rejected","reason":"smoke"}'
```

Expected: HTTP 401 (no bearer token) or 404 ("Issue not found"). NOT 404 with "Not Found" route error and NOT 422 with route-not-matched. 401/404-issue-not-found means the route exists and is responding.

- [ ] **Step 2: Unblock the stuck issue from prior runs**

Call `mcp__supabase__execute_sql` with:
- `project_id`: `xeluydwpgiddbamysgyu`
- `query`:
```sql
-- The IT Global "header change" issue rejected twice against the wrong source-of-truth.
-- With the new staging-model code, the agent will read actual cms-preview state.
-- Reset retry counter so it gets another shot.
UPDATE project_issues
SET agent_retry_count = 0, agent_status = NULL, agent_claimed_at = NULL
WHERE id = '25d37190-54a5-4770-82c4-f68273a05dc6'
RETURNING id, title, agent_retry_count;
```

Expected: one row updated.

- [ ] **Step 3: Trigger the workflow manually for that issue**

```bash
gh workflow run solver-agent.yml --repo stefanroman22/cms-platform
```

(Manual workflow_dispatch uses the queue path, not targeted dispatch — but that's fine because retry_count=0 makes it eligible again.)

- [ ] **Step 4: Watch the workflow run**

```bash
gh run watch --repo stefanroman22/cms-platform
```

Expected outcomes (one of):
- Agent fixes the issue → cms-preview gets a commit → Slack "✅ Resolved" appears
- Agent legitimately rejects (e.g., it really IS already fixed on staging) → Slack thread reply "🤔 Agent reviewed, no change — Cannot reproduce: ..." appears under the original "🆕 New Issue"

Either outcome confirms the visibility pass works. If you get the rejection path, verify cms-preview actually has the correct header (don't trust browser cache — check via `git show origin/cms-preview:src/components/layout/Header.tsx`).

- [ ] **Step 5: Submit a fresh test issue on a different project**

Submit an issue via the CMS dashboard (or POST `/projects/{slug}/issues`) for a project that you can verify the agent should be able to either fix or rejet sanely. Confirm:
1. Slack "🆕 New Issue" appears.
2. Workflow fires within ~30s (dispatch path).
3. Workflow log shows `DISPATCH_ISSUE_ID=<the id you just submitted>` in the Claim step.
4. Claim step claims THAT id (check log: `claimed issue <id> ...`).
5. Outcome lands as either "✅ Resolved" or "🤔 Agent reviewed, no change" thread reply.

- [ ] **Step 6: Verify slack_created_ts persistence**

Call `mcp__supabase__execute_sql`:
```sql
SELECT id, title, slack_created_ts FROM project_issues
WHERE created_at > now() - interval '10 minutes'
ORDER BY created_at DESC LIMIT 5;
```

Expected: latest row(s) have non-NULL `slack_created_ts` matching the Slack ts of their "New Issue" post.

---

# Self-review

After writing all 19 tasks, the spec-coverage check:

**A — Silent failure modes:**
1. Agent rejects → Task 16 (notify_agent_event in finalize, kind=rejected) ✓
2. Agent no-diff/crash split → Task 16 (CLAUDE_EXIT_CODE branch; kind=agent_crashed vs no_diff) + Task 18 (workflow captures exit code) ✓
3. Backend trigger fails → Task 14 (3× retry) + Task 16 (direct-Slack fallback) + Task 15 (post_thread_event_direct) ✓
4. notify_issue_created fails → existing log+swallow retained (no change needed per spec) ✓
5. dispatch_solver_tick fails → Task 6 (Slack alert in issues.py except block) ✓
6. Clone crashes → Task 17 (release_issue.py emits agent_crashed event) + Task 18 (env vars added to Release on failure step) ✓

**B — Queue/dispatch:**
7. Dispatch payload honored → Task 9 (DISPATCH_ISSUE_ID env handling) + Task 18 (workflow passes env) + Task 8 (claim_specific_issue) + Task 1 (RPC) ✓
8. Starvation reduced → covered by 7 (targeted dispatch bypasses queue) ✓

**C — Staging integrity:**
10. No reset → Task 11 (clone_at_preview_head) + Task 12 (clone_repo.py call site) ✓
11. Plain push → Task 13 (no --force-with-lease + PushRejectedError) ✓
12. Stefan ✅ FF failure — no regression (existing slack_handler unchanged per spec) ✓
13. PREV_SHA_PATH obsolete → Task 11 (semantics changed to anchor not orphan) + Task 10 (prompt updated) ✓

**E — Agent prompt:**
19. Source-of-truth note → Task 10 (prompt addition) ✓
21. Content-not-code dashboard hint → Task 10 (Step 0 rejection categories) ✓

**G — Slack message lifecycle:**
27. slack_created_ts persisted → Task 1 (column) + Task 4 (create_issue persists ts) + Task 5 (agent-event endpoint uses it) ✓

**Documentation:**
- AGENTS.md + phases/*.md → Task 7 ✓

**Testing additions:**
- test_finalize.py extended → Task 16 ✓
- test_claim_issue.py extended → Task 9, Task 10 ✓
- test_repo.py extended → Task 11, Task 13 ✓
- test_db_claim.py extended → Task 8 ✓
- test_db_release.py extended → Task 17 ✓
- test_issues_router.py extended → Task 4 ✓
- test_agent_event_route.py created → Task 5 ✓
- test_slack_notify.py extended → Task 3 ✓
- test_solver_dispatch.py extended → Task 6 ✓
- test_backend_api.py created → Task 14, Task 15 ✓

**Migration / rollout (per spec):**
- Migration first → Task 1 (apply via MCP) ✓
- Backend PR (issues.py + slack_notify.py + schemas.py + solver_dispatch.py + AGENTS.md/phases) → Tasks 2-7 ✓
- Solver PR (repo.py + claim_issue.py + db.py + finalize.py + backend_api.py + slack.py + clone_repo.py + release_issue.py + workflow yml) → Tasks 8-18 ✓
- Smoke test → Task 19 ✓

**Placeholder scan:** No TBDs, TODOs, "implement later", "similar to Task N", or vague handwaves found. Every code step has the actual code.

**Type consistency:**
- `notify_agent_event` signature is consistent across files:
  - Backend `slack_notify.notify_agent_event(*, thread_ts, kind, reason, project, issue) -> str | None` (Task 3)
  - Backend route's call: `slack_notify.notify_agent_event(thread_ts=..., kind=..., reason=..., project=..., issue=...)` (Task 5) ✓
  - Solver `backend_api.notify_agent_event(issue_id, *, kind, reason)` (Task 14) — distinct signature, distinct purpose (HTTP client for the route) ✓
  - Solver `slack.post_thread_event_direct(*, thread_ts, kind, reason)` (Task 15) ✓
- `AgentEventRequest.kind` values: `"rejected", "no_diff", "agent_crashed", "backend_error"` — same set used in all emoji/header dicts and in finalize.py / release_issue.py call sites ✓
- `PushRejectedError` defined in repo.py (Task 13), caught in finalize.py (Task 16) ✓
- `EVENT_MARKER_PATH = "/tmp/agent-event-emitted"` consistent in finalize.py (Task 16) and release_issue.py (Task 17) ✓
- `DISPATCH_ISSUE_ID` env var name consistent in claim_issue.py (Task 9) and workflow yml (Task 18) ✓
- `CLAUDE_EXIT_CODE` env var name consistent in finalize.py (Task 16) and workflow yml (Task 18) ✓

No issues found in self-review.

---

# Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-18-solver-staging-model.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, with two-stage review between tasks. Best for catching issues early, fast iteration, keeps the main session context clean.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review. Best when you want to watch every step in real time.

Which approach?
