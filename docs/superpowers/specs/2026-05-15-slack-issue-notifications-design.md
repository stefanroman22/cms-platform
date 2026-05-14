# S1 — Slack Issue Notifications (outbound)

**Status:** Design approved 2026-05-15
**Owner:** Stefan Roman
**Scope:** Sub-project 1 of a 4-part roadmap toward an autonomous issue-resolution agent.

## Roadmap context

This spec covers **S1 only**. The full roadmap:

| Sub-project | Purpose | Status |
|---|---|---|
| **S1** | Outbound Slack notifications on issue create + resolve | this spec |
| **S1.5** | Inbound Slack listener: "looks good" → promote dev→prod + Resend email to client | next |
| **S2** | Verifier sub-agent — confirms reported issue actually exists in code | future |
| **S3** | Solver sub-agent — edits code, pushes to dev branch, comments preview URL on Slack | future |
| **S4** | Full approval loop tied to S3 retries | future |

Each ships independently. S1 has standalone value: Stefan knows when clients submit issues and when admins resolve them, without watching the dashboard.

## Problem

Today, when a client submits an issue via the CMS dashboard, it lands in the `project_issues` table silently. Stefan has no real-time signal. Same for resolutions — no audit trail outside the DB. Future agents (S2/S3) need a notification surface to report their progress.

## Solution

Backend FastAPI hooks fire a Slack message via `chat.postMessage` after Supabase writes succeed, posting to `#issues-websites` in Stefan's workspace.

## Architecture

```
┌─────────────────┐         ┌──────────────────────────┐
│  CMS Dashboard  │ ──────► │ FastAPI: routers/issues  │
│  (client/admin) │   HTTP  │  POST   /issues          │
└─────────────────┘         │  PATCH  /issues/:id/status│
                            └────────────┬─────────────┘
                                         │
                            (1) Supabase insert/update
                                         │
                                         ▼
                            ┌──────────────────────────┐
                            │ services/slack_notify.py │
                            │  - notify_issue_created()│
                            │  - notify_issue_resolved│
                            └────────────┬─────────────┘
                                         │
                                         ▼
                            ┌──────────────────────────┐
                            │ Slack chat.postMessage   │
                            │ channel #issues-websites │
                            └──────────────────────────┘
```

Flow:
1. Router writes to Supabase (existing behavior, unchanged).
2. Router calls `slack_notify` service synchronously.
3. Service joins issue + project + user context, builds Block Kit message, POSTs to Slack.
4. Slack failures swallowed (logged, never re-raised). Issue write must not roll back on Slack outage.

No new infrastructure. No queue. No webhook. Just one Python module + env vars.

## Data model

### `project_issues`
No changes. All notification context derivable via join to `projects` and `users`.

### `projects`
Add one column:

```sql
ALTER TABLE projects
  ADD COLUMN repo_branch TEXT NOT NULL DEFAULT 'dev';
```

- Future solver agent (S3) reads this to know which branch to push fixes to.
- Default `'dev'` matches Stefan's workflow ("push to dev → preview URL").
- Existing rows backfilled via DEFAULT.
- RLS: covered by existing `projects_owner_*` policies. No new policy needed.

Migration file: `backend/migrations/2026_05_15_projects_repo_branch.sql`.

### `local_cache_path`
**Not a DB column.** Computed deterministically by future agents:

```python
local_cache_path = f"{AGENT_CACHE_ROOT}/{project.slug}"
```

`AGENT_CACHE_ROOT` is an env var. Same input → same path. No DB row required.

## Slack message format

Both messages use Slack Block Kit JSON via `chat.postMessage`.

### New issue
```
🆕 New Issue — [Acme Site]
*Title:*        Hero image broken on mobile
*Priority:*     🔴 High
*Submitted by:* client@acme.com
*Project:*      acme-site  (branch: dev)
*Repo:*         https://github.com/stefan/acme-site

Description:
> Image stretches off-screen on iPhone. Repro: load homepage
> on Safari iOS 17, scroll to hero section.

[Open in CMS]  ← button link
```

### Issue resolved
```
✅ Issue Resolved — [Acme Site]
*Title:*       Hero image broken on mobile
*Resolved by:* stefan@roman-technologies.dev
*Preview:*     https://acme-site-dev.vercel.app

[Open Preview]  [Open in CMS]
```

Priority emoji: `🔴 High` / `🟡 Medium` / `🟢 Low`.

Threading is out of scope for S1 — S1.5 will introduce thread tracking by persisting Slack `ts` per issue.

## Service module API

`backend/auth_service/services/slack_notify.py`

```python
import os
import logging
import httpx

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api/chat.postMessage"


def _enabled() -> bool:
    return bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_ISSUES_CHANNEL_ID"))


def _post(blocks: list[dict], text_fallback: str) -> None:
    """Fire one Slack message. Swallow all errors — never break caller."""
    if not _enabled():
        logger.info("slack_notify disabled (no token/channel) — skipping")
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
            timeout=5.0,
        )
        body = resp.json()
        if not body.get("ok"):
            logger.warning("slack_notify failed: %s", body.get("error"))
    except Exception:
        logger.exception("slack_notify post failed")


def notify_issue_created(issue: dict, project: dict, user_email: str | None) -> None:
    blocks = _build_created_blocks(issue, project, user_email)
    fallback = f"New issue [{project['slug']}]: {issue['title']}"
    _post(blocks, fallback)


def notify_issue_resolved(issue: dict, project: dict, resolver_email: str | None) -> None:
    blocks = _build_resolved_blocks(issue, project, resolver_email)
    fallback = f"Resolved [{project['slug']}]: {issue['title']}"
    _post(blocks, fallback)
```

Properties:
- Pure functions. No state. Easy to test.
- Disabled mode (no env) = silent no-op. Dev/test environments don't need Slack credentials.
- 5s timeout. Failures logged, never raised. Caller never sees Slack error.
- Sync httpx. Volume is low (~10 messages/day expected); no async benefit.

## Router integration

`backend/auth_service/routers/issues.py` — 2 hook points.

### Hook 1: `create_issue`
After Supabase insert and before return:

```python
from ..services import slack_notify

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
```

### Hook 2: `update_issue_status`
Only fire when status transitions to `done` from a non-done state.

Modify existing pre-update SELECT to also fetch current `status`:

```python
issue_result = (
    sb.table("project_issues")
    .select("id, project_id, status")  # added: status
    .eq("id", issue_id)
    .eq("project_id", project["id"])
    .maybe_single()
    .execute()
)
old_status = issue_result.data["status"]

# ... existing update ...

if old_status != "done" and body.status == "done":
    slack_notify.notify_issue_resolved(
        issue={"id": r["id"], "title": r["title"]},
        project=project,
        resolver_email=user.email,
    )
```

Why two-query is not added: the existing handler already reads the row before update for auth/scoping. We extend the existing SELECT by one column.

Suppression rules:
- `done → done` → no notify (idempotent reset).
- `done → pending` (re-open) → no notify in S1; S1.5 may add a "re-opened" notification.

## Configuration

### Env vars (backend)

```
SLACK_BOT_TOKEN=xoxb-...                # bot user OAuth token (chat:write scope)
SLACK_ISSUES_CHANNEL_ID=C0123ABCDEF     # channel ID, NOT name — name is brittle
AGENT_CACHE_ROOT=/tmp/cms-agent-cache   # for S2/S3; can be unset for S1
```

Channel ID lookup: Slack desktop → right-click `#issues-websites` → "View channel details" → bottom of pane.

### Slack app setup (one-time, manual)
1. https://api.slack.com/apps → "Create New App" → "From scratch"
2. Name: `CMS Issues Bot`. Workspace: Stefan's.
3. **OAuth & Permissions** → Bot Token Scopes → add `chat:write`.
4. **Install to Workspace** → approve → copy `xoxb-...` Bot User OAuth Token into `SLACK_BOT_TOKEN`.
5. In Slack: `/invite @CMS Issues Bot` inside `#issues-websites` (bot must be channel member to post).

### Where env vars live
- Local dev: `backend/.env` (gitignored — verify before commit).
- Vercel: backend project → Environment Variables → all envs (preview + production).
- CI: GitHub Actions — no value needed; disabled mode kicks in when env is missing.

### Docs updates
- `docs/ENVIRONMENTS.md` — add 3 new vars to env table.
- `docs/ONBOARDING.md` — Slack app setup section.
- `docs/DEVELOPMENT.md` — note `slack_notify` disabled mode for local dev.

## Error handling

| Scenario | Behavior |
|---|---|
| `SLACK_BOT_TOKEN` or channel ID unset | Service returns no-op. Log INFO. |
| HTTP timeout (>5s) | Caught, logged WARNING. Caller returns 201/200. |
| Slack API `ok:false` (e.g. `not_in_channel`, `invalid_auth`) | Log WARNING with `error` field. Caller proceeds. |
| Network exception | Caught, logged ERROR with stack. Caller proceeds. |
| Pre-update status read fails | Skip notification, do not fail PATCH. |

**Invariant**: Slack failure NEVER causes a 5xx on issue create/update. Notifications are best-effort.

## Testing

### Unit — `backend/auth_service/tests/test_slack_notify.py`
- `test_disabled_when_env_missing` — no token/channel → no HTTP made.
- `test_created_payload_shape` — env set, mock httpx, assert body has blocks/channel/fallback/auth header.
- `test_resolved_payload_shape` — symmetric.
- `test_swallows_timeout` — mock httpx raises TimeoutException, assert no bubble.
- `test_swallows_api_error` — mock `{"ok": false, "error": "not_in_channel"}`, assert no raise.

### Integration — additions to `backend/auth_service/tests/test_issues_router.py`
- `test_create_issue_fires_slack` — POST issue, assert `notify_issue_created` called once with project + email present.
- `test_status_done_fires_resolved` — pending → done PATCH, assert `notify_issue_resolved` called.
- `test_status_done_to_done_no_double_fire` — done → done, assert no call.
- `test_slack_failure_does_not_break_create` — mock httpx raises, verify POST still returns 201.

### Migration
Existing migration tests verify `projects` RLS unbroken after the column add. No new test needed.

### No live Slack E2E
Would require a test workspace + token. Mocks cover behavior. Manual smoke after deploy is sufficient.

## Out of scope (deferred)

- **Inbound Slack** (Events API, signing secret) — S1.5.
- **Production promote on "looks good"** — S1.5.
- **Resend client email** — S1.5.
- **Slack threading per issue** (persisting `ts`) — S1.5.
- **Verifier / solver agents** — S2 / S3.
- **Per-project channels** — not needed at current volume.

## Success criteria

- Client submits issue → Stefan sees Slack message within 1s of HTTP response, containing project name + slug + title + description + priority + submitter email + repo URL + branch + dashboard link.
- Admin sets status `done` → Stefan sees resolved message with preview URL link.
- Backend never returns 5xx because of a Slack outage.
- All new unit + integration tests pass in CI.
- Disabled mode (no env) works silently in local dev and CI.

## Open questions
None — all resolved during brainstorm.
