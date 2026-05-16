# Solver Agent (S3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Autonomous GitHub Actions cron worker claims pending CMS issues (priority-ordered), runs Claude Code action with `CLAUDE_CODE_OAUTH_TOKEN` against a cloned client repo, commits the fix to `cms-preview`, and routes back into the S1.5 approval flow.

**Architecture:** New folder `agents/Solver - Issues/` holds claim/clone/finalize/release Python scripts. A new workflow `.github/workflows/solver-agent.yml` fires every 15 min; uses `anthropics/claude-code-action@v1` for the actual code edits. New backend admin endpoint `PATCH /admin/issues/{id}/status` lets the solver trigger S1's resolved-Slack flow without needing project ownership. New DB columns track agent state (`agent_status`, `agent_claimed_at`, `agent_retry_count`, `agent_last_error`, `agent_commit_sha`).

**Tech Stack:** Python 3.13, supabase-py, GitHub Actions, `anthropics/claude-code-action@v1`, FastAPI (backend admin route), Supabase Postgres (atomic `FOR UPDATE SKIP LOCKED` claim).

**Spec:** `docs/superpowers/specs/2026-05-16-solver-agent-s3-design.md`

**Branch:** `feat/solver-agent-s3` (already created off latest master).

---

## File Structure

**Create:**

Agent (Python):
- `agents/Solver - Issues/AGENTS.md` — workflow spec (mirrors CMS Connector style).
- `agents/Solver - Issues/LEARNINGS.md` — empty scaffold for self-improvement log.
- `agents/Solver - Issues/.env.example` — env var template (gitignored real `.env`).
- `agents/Solver - Issues/pytest.ini` — pytest config.
- `agents/Solver - Issues/requirements.txt` — runtime deps.
- `agents/Solver - Issues/requirements-dev.txt` — dev deps.
- `agents/Solver - Issues/db.py` — Supabase wrappers (`claim_next_issue`, `release_issue_failed`, `mark_done`).
- `agents/Solver - Issues/repo.py` — git clone + commit + push.
- `agents/Solver - Issues/backend_api.py` — PATCH `/admin/issues/<id>/status`.
- `agents/Solver - Issues/slack.py` — post blocked-issue Slack notification (via backend admin endpoint).
- `agents/Solver - Issues/claim_issue.py` — workflow entrypoint: claim + write prompt + set outputs.
- `agents/Solver - Issues/clone_repo.py` — workflow entrypoint: clone client repo.
- `agents/Solver - Issues/finalize.py` — workflow entrypoint: commit + push + mark done OR detect agent-status.md.
- `agents/Solver - Issues/release_issue.py` — workflow `failure()` entrypoint: increment retry + transition.
- `agents/Solver - Issues/phases/1-claim.md`
- `agents/Solver - Issues/phases/2-clone.md`
- `agents/Solver - Issues/phases/3-solve.md`
- `agents/Solver - Issues/phases/4-push.md`
- `agents/Solver - Issues/phases/5-finalize.md`
- `agents/Solver - Issues/tests/__init__.py`
- `agents/Solver - Issues/tests/test_db_claim.py`
- `agents/Solver - Issues/tests/test_db_release.py`
- `agents/Solver - Issues/tests/test_repo.py`
- `agents/Solver - Issues/tests/test_claim_issue.py`
- `agents/Solver - Issues/tests/test_finalize.py`

Workflow + skill + docs:
- `.github/workflows/solver-agent.yml` — cron + workflow_dispatch.
- `.claude/skills/solver-issues/SKILL.md` — manual debug invocation entry.
- `backend/migrations/2026_05_16_solver_agent_columns.sql` — DB migration.

**Modify:**
- `backend/auth_service/routers/issues.py` — add `PATCH /admin/issues/{id}/status` endpoint + extract `_build_issue_out` shared helper.
- `backend/auth_service/services/slack_handler.py` — `handle_message` resets `agent_status`/`agent_retry_count`/`agent_last_error` on revision feedback.
- `backend/auth_service/tests/test_issues_router.py` — add 3 admin-endpoint tests.
- `backend/auth_service/tests/test_slack_handler.py` — extend revision happy-path test to assert agent-state reset.
- `agents/README.md` — append the new agent row.

---

## Task 1: DB migration

**Files:**
- Create: `backend/migrations/2026_05_16_solver_agent_columns.sql`

- [ ] **Step 1: Write the migration**

Create `backend/migrations/2026_05_16_solver_agent_columns.sql`:

```sql
-- 2026_05_16 — Solver Agent (S3) columns
-- Adds agent-state tracking to project_issues for the GitHub Actions cron
-- worker that auto-fixes client-submitted issues. The atomic claim query uses
-- FOR UPDATE SKIP LOCKED + a 15-min stale-claim window. See
-- docs/superpowers/specs/2026-05-16-solver-agent-s3-design.md for the data model.

ALTER TABLE project_issues
  ADD COLUMN IF NOT EXISTS agent_status TEXT NULL,
  ADD COLUMN IF NOT EXISTS agent_claimed_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS agent_retry_count INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS agent_last_error TEXT NULL,
  ADD COLUMN IF NOT EXISTS agent_commit_sha TEXT NULL;

COMMENT ON COLUMN project_issues.agent_status IS
  'Solver agent state machine: NULL/idle | claimed | failed | blocked. Separate from user-facing status.';
COMMENT ON COLUMN project_issues.agent_claimed_at IS
  'When the solver claimed this issue. Stale claims (>15 min) are released on the next cron tick.';
COMMENT ON COLUMN project_issues.agent_retry_count IS
  'Count of solver attempts. Reset to 0 when S1.5 stores fresh revision_feedback. Issue blocked at >= SOLVER_MAX_RETRIES (default 3).';
COMMENT ON COLUMN project_issues.agent_last_error IS
  'Short text (<=500 chars) of the last solver failure reason.';
COMMENT ON COLUMN project_issues.agent_commit_sha IS
  'Short SHA of commit the solver pushed to cms-preview. For audit + Slack thread context.';
```

- [ ] **Step 2: Do NOT apply automatically**

**CONTROLLER OVERRIDE:** Do NOT apply this migration. Stefan runs migrations himself via Supabase MCP. Stop after writing the file.

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/2026_05_16_solver_agent_columns.sql
git commit -m "feat(db): S3 — agent_status + retry_count + commit_sha on project_issues"
```

---

## Task 2: Backend admin endpoint + `_build_issue_out` helper

**Files:**
- Modify: `backend/auth_service/routers/issues.py`
- Modify: `backend/auth_service/tests/test_issues_router.py`

- [ ] **Step 1: Read current `update_issue_status` handler**

Open `backend/auth_service/routers/issues.py`. Locate the existing `update_issue_status` handler (lines ~200-280). Note the IssueOut(...) construction near the end.

- [ ] **Step 2: Write 3 failing tests**

Append to `backend/auth_service/tests/test_issues_router.py`:

```python
def test_admin_status_update_requires_bearer(mock_supabase, client):
    """Without Authorization header, admin endpoint returns 401."""
    resp = client.patch(
        "/admin/issues/issue-1/status", json={"status": "done"}
    )
    assert resp.status_code == 401


def test_admin_status_update_fires_slack_resolved(
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
        "created_at": "2026-05-16T10:00:00Z",
    }
    project_row = {
        "id": "project-acme",
        "name": "Acme",
        "slug": "acme",
        "github_repo": "stefan/acme",
        "repo_branch": "cms-preview",
        "preview_url": "https://acme-dev.vercel.app",
        "production_url": "https://acme.vercel.app",
        "production_branch": "master",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=pending_row),         # pre-update SELECT
        MagicMock(data=[updated_row]),       # UPDATE status
        MagicMock(data=project_row),         # project lookup
        MagicMock(data=[updated_row]),       # UPDATE slack_resolved_ts
    ]

    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: "1715789999.000001",
    )

    resp = client.patch(
        "/admin/issues/issue-1/status",
        json={"status": "done"},
        headers={"Authorization": "Bearer cmsk_dummy"},
    )
    assert resp.status_code == 200, resp.text

    update_calls = [c.args[0] for c in mock_supabase.update.call_args_list if c.args]
    ts_updates = [u for u in update_calls if "slack_resolved_ts" in u]
    assert len(ts_updates) == 1
    assert ts_updates[0]["slack_resolved_ts"] == "1715789999.000001"


def test_admin_status_update_skips_when_already_done(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    """No re-fire when old_status was already 'done'."""
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
        "created_at": "2026-05-16T10:00:00Z",
    }
    mock_supabase.execute.side_effect = [
        MagicMock(data=done_row),
        MagicMock(data=[updated_row]),
    ]

    calls = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_resolved",
        lambda **kw: calls.append(kw) or None,
    )

    resp = client.patch(
        "/admin/issues/issue-1/status",
        json={"status": "done"},
        headers={"Authorization": "Bearer cmsk_dummy"},
    )
    assert resp.status_code == 200, resp.text
    assert calls == []
```

Also, in the same file's `auth_as` patches (added in S1 Task 6), the `admin_user_via_bearer_or_sid` dep must be patched. The simplest path is to add to `conftest.py` the bearer-path bypass — but to keep this task isolated, monkeypatch within the test if `auth_as` doesn't already cover the admin endpoint. If a test fails because `admin_user_via_bearer_or_sid` is not patched, fall back to:

```python
monkeypatch.setattr(
    "auth_service.routers.issues.admin_user_via_bearer_or_sid",
    lambda request: admin_user,  # async needed → use AsyncMock if function is async
)
```

Inspect the existing `admin_user_via_bearer_or_sid` in `backend/auth_service/routers/deps.py` to see if it's `async def`. If so, the patch needs to be an async function.

- [ ] **Step 3: Run tests to confirm failure**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests/test_issues_router.py -v -k "admin"
```

Expected: 3 failures (route doesn't exist → 404 or 405).

- [ ] **Step 4: Extract `_build_issue_out` helper**

In `backend/auth_service/routers/issues.py`, add at the top (after `router = APIRouter(...)`):

```python
def _build_issue_out(row: dict, sb) -> IssueOut:
    """Build IssueOut from a project_issues row, looking up creator email."""
    email_result = (
        sb.table("users")
        .select("email")
        .eq("id", row["created_by"])
        .maybe_single()
        .execute()
        if row.get("created_by")
        else None
    )
    return IssueOut(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        description=row["description"],
        priority=row["priority"],
        status=row.get("status", "pending"),
        created_by=row.get("created_by"),
        created_by_email=(
            email_result.data.get("email") if email_result and email_result.data else None
        ),
        created_at=row["created_at"],
    )
```

Then replace the duplicated `IssueOut(...)` constructions in the existing `update_issue_status`, `create_issue`, `update_issue`, and `list_issues` handlers (where they appear) with calls to `_build_issue_out(row, sb)`. Be careful with `create_issue` — its `status` is hardcoded `"pending"` and `created_by_email` is `user.email` not from the lookup; LEAVE that one as-is. Only refactor handlers that lookup email.

- [ ] **Step 5: Add the admin endpoint**

Append to `backend/auth_service/routers/issues.py` (after existing handlers, before module end):

```python
@router.patch(
    "/admin/issues/{issue_id}/status",
    response_model=IssueOut,
)
async def admin_update_issue_status(
    issue_id: str,
    body: IssueStatusRequest,
    request: Request,
):
    """Admin/agent path — same effect as the user-facing PATCH but auth'd
    via admin bearer token (or cookie session). Skips the project-access
    ownership check — the solver acts cross-project.
    """
    user = await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()

    issue_result = (
        sb.table("project_issues")
        .select("id, project_id, status")
        .eq("id", issue_id)
        .maybe_single()
        .execute()
    )
    if not issue_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    old_status = issue_result.data.get("status", "pending")

    updated = (
        sb.table("project_issues").update({"status": body.status}).eq("id", issue_id).execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail="Status could not be updated.")

    r = updated.data[0]

    project_row = (
        sb.table("projects")
        .select(
            "id, name, slug, github_repo, repo_branch, production_branch, "
            "preview_url, production_url, user_id"
        )
        .eq("id", r["project_id"])
        .single()
        .execute()
    )
    project = project_row.data or {}

    resolver_email = getattr(user, "email", None) or "solver@roman-technologies.dev"

    issue_out = _build_issue_out(r, sb)

    if old_status != "done" and body.status == "done":
        try:
            ts = slack_notify.notify_issue_resolved(
                issue={"id": r["id"], "title": r["title"]},
                project=project,
                resolver_email=resolver_email,
            )
            if ts:
                sb.table("project_issues").update({"slack_resolved_ts": ts}).eq(
                    "id", r["id"]
                ).execute()
        except Exception:  # noqa: BLE001 — Slack must never break admin endpoint
            import logging

            logging.getLogger(__name__).exception("slack_notify (admin resolve) raised")

    return issue_out
```

You'll need to add `admin_user_via_bearer_or_sid` to the imports at the top:

```python
from .deps import admin_user_via_bearer_or_sid, require_project_access, require_user
```

- [ ] **Step 6: Run admin-endpoint tests**

```bash
pytest auth_service/tests/test_issues_router.py -v -k "admin"
```

Expected: 3 passed.

- [ ] **Step 7: Run full suite to verify no regression**

```bash
pytest auth_service/tests -v 2>&1 | tail -10
```

Expected: previous tests (167 from S1 + S1.5) still pass + 3 new tests pass. Total ~170+.

- [ ] **Step 8: Commit**

```bash
git add backend/auth_service/routers/issues.py backend/auth_service/tests/test_issues_router.py
git commit -m "feat(issues): admin PATCH /admin/issues/{id}/status endpoint for solver agent"
```

---

## Task 3: S1.5 handler agent-state reset on revision feedback

**Files:**
- Modify: `backend/auth_service/services/slack_handler.py`
- Modify: `backend/auth_service/tests/test_slack_handler.py`

- [ ] **Step 1: Append failing test**

Add to `backend/auth_service/tests/test_slack_handler.py`:

```python
def test_message_happy_path_resets_agent_state(slack_env, monkeypatch):
    """Revision feedback must clear solver agent state so the agent retries from scratch."""
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())

    updates = []
    fake_sb = MagicMock()
    for m in ("table", "update", "eq", "execute"):
        getattr(fake_sb, m).return_value = fake_sb

    def capture_update(payload):
        updates.append(payload)
        return fake_sb

    fake_sb.update = capture_update

    with patch.object(slack_handler, "get_supabase_admin", return_value=fake_sb), \
         patch.object(slack_handler, "_post_thread_reply"):
        slack_handler.handle_message(_event_message(text="please fix the spacing on hero"))

    assert len(updates) == 1
    update = updates[0]
    assert update["status"] == "in_progress"
    assert update["agent_status"] == "idle"
    assert update["agent_retry_count"] == 0
    assert update["agent_last_error"] is None
```

- [ ] **Step 2: Run test to confirm failure**

```bash
pytest auth_service/tests/test_slack_handler.py -v -k "resets_agent_state"
```

Expected: FAIL — `agent_status` key not present in update payload.

- [ ] **Step 3: Modify `handle_message` in slack_handler.py**

In `backend/auth_service/services/slack_handler.py`, find the `handle_message` function. Locate the `sb.table("project_issues").update({...})` call inside the happy path. Add 3 keys:

```python
    sb = get_supabase_admin()
    sb.table("project_issues").update(
        {
            "status": "in_progress",
            "revision_feedback": text,
            "revision_feedback_at": datetime.now(UTC).isoformat(),
            "agent_status": "idle",        # S3: clear lock
            "agent_retry_count": 0,        # S3: fresh attempt budget
            "agent_last_error": None,      # S3: clear stale error
        }
    ).eq("id", issue["id"]).execute()
```

- [ ] **Step 4: Run all slack_handler tests**

```bash
pytest auth_service/tests/test_slack_handler.py -v
```

Expected: all pass (the new test + 18 previous).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/slack_handler.py backend/auth_service/tests/test_slack_handler.py
git commit -m "feat(slack): reset solver agent state on revision feedback"
```

---

## Task 4: Solver agent — folder scaffold

**Files:**
- Create: `agents/Solver - Issues/AGENTS.md`
- Create: `agents/Solver - Issues/LEARNINGS.md`
- Create: `agents/Solver - Issues/.env.example`
- Create: `agents/Solver - Issues/pytest.ini`
- Create: `agents/Solver - Issues/requirements.txt`
- Create: `agents/Solver - Issues/requirements-dev.txt`
- Create: `agents/Solver - Issues/tests/__init__.py`
- Create: `agents/Solver - Issues/phases/1-claim.md`
- Create: `agents/Solver - Issues/phases/2-clone.md`
- Create: `agents/Solver - Issues/phases/3-solve.md`
- Create: `agents/Solver - Issues/phases/4-push.md`
- Create: `agents/Solver - Issues/phases/5-finalize.md`

- [ ] **Step 1: Write AGENTS.md**

Create `agents/Solver - Issues/AGENTS.md`:

```markdown
# Solver — Issues Agent (S3)

Authoritative spec for **this agent only**. Each agent owns its own AGENTS.md.

> Skill entry: [`.claude/skills/solver-issues/SKILL.md`](../../.claude/skills/solver-issues/SKILL.md)
> Self-improvement log: [`LEARNINGS.md`](./LEARNINGS.md)
> Per-phase detail: [`phases/`](./phases/)

---

## Trigger

This agent is invoked **automatically** by GitHub Actions cron (`.github/workflows/solver-agent.yml`) every 15 minutes. Manual invocation via `workflow_dispatch` from the GitHub Actions UI is supported for testing.

Local skill invocation:

> "Run Solver Issues agent locally for debug"

The local skill replays a single workflow step against a real claimed issue. Not used in production.

## Pipeline (strict order)

| # | Phase | Doc | Goal |
|---|-------|-----|------|
| 1 | Claim | [phases/1-claim.md](./phases/1-claim.md) | Atomic priority-ordered claim from Supabase |
| 2 | Clone | [phases/2-clone.md](./phases/2-clone.md) | Shallow clone client repo at `cms-preview` |
| 3 | Solve | [phases/3-solve.md](./phases/3-solve.md) | Run `anthropics/claude-code-action` with verification + fix prompt |
| 4 | Push | [phases/4-push.md](./phases/4-push.md) | Commit + push the fix to `cms-preview` |
| 5 | Finalize | [phases/5-finalize.md](./phases/5-finalize.md) | PATCH backend `/admin/issues/{id}/status` to mark done → S1 fires |

Each phase doc contains: goal, inputs, steps, outputs, failure messages, self-improvement hook.

## Required credentials

GitHub Actions secrets (set in repo Settings → Secrets and variables → Actions):

| Tool | Secret | Used in |
|------|--------|---------|
| Claude Code subscription | `CLAUDE_CODE_OAUTH_TOKEN` | Phase 3 |
| Supabase service-role | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Phase 1, 4, 5 (release path) |
| GitHub (client repos) | `SOLVER_GITHUB_TOKEN` | Phase 2, 4 |
| Backend admin | `CMS_API_TOKEN` | Phase 5 |
| Backend URL | `CMS_BACKEND_URL` (=`https://cms-backend-roman.vercel.app`) | Phase 5 |

If a credential is missing, the affected workflow step fails; the `failure()` release step decrements the lock and increments `agent_retry_count`. Stefan investigates.

## Failure-mode taxonomy

| Class | Action | Self-improve? |
|-------|--------|---------------|
| Transient (network 5xx, Supabase timeout) | Step fails; `release_issue.py` increments retry; next cron tick retries. | No |
| Quota exhausted (Anthropic 429 / Claude subscription quota) | Action step exits non-zero; release increments retry; cron resumes when quota replenishes. | No |
| Agent cannot reproduce / fix (writes `/tmp/agent-status.md`) | `finalize.py` reads status, marks failed without commit. | Always — append rule to LEARNINGS if reason is novel. |
| Empty diff (agent finished but produced no changes) | `finalize.py` marks failed. | Always — usually indicates ambiguous issue or prompt drift. |
| Git push 403 | Likely PAT scope drift. Mark failed; Stefan fixes PAT. | Only if recurring. |
| Backend PATCH 5xx | Commit is durable; log + exit 0. Slack post + status update missed. Sync via dashboard later. | No |

## Hard rules — what the agent must NOT do

- Run `git commit` or `git push` from within the agent. The orchestrator does both. Agent only edits files.
- Run `npm install` or modify lockfiles unless adding a dependency is strictly required for the fix.
- Modify CI configs, GitHub workflows, env files, or `.git/` internals.
- Fetch external code or URLs (`WebFetch` is disallowed).
- Delete files via `rm` (Bash(rm:*) is disallowed).

## Self-improvement loop

Same as CMS Connector: when an issue fails for a non-transient, non-covered reason, append a one-line rule to `LEARNINGS.md` under the matching phase heading:

`- <YYYY-MM-DD>: <one-line rule>. Triggered by: <short context>.`

LEARNINGS.md is **append-only**.

## Modifying this agent

If you change Phase 3 prompt: keep `phases/3-solve.md` in sync with `claim_issue.py` `_build_prompt`.
If you change Phase 5 backend call: update the route in `backend/auth_service/routers/issues.py` to match.
If you change Phase 1 claim SQL: update the data model in `docs/superpowers/specs/2026-05-16-solver-agent-s3-design.md`.
```

- [ ] **Step 2: Write LEARNINGS.md scaffold**

Create `agents/Solver - Issues/LEARNINGS.md`:

```markdown
# Solver Agent — Learnings

Append-only log of self-improvement rules. Group by phase. Format:

`- YYYY-MM-DD: <one-line rule>. Triggered by: <short context>.`

## Phase 1 — Claim

(none yet)

## Phase 2 — Clone

(none yet)

## Phase 3 — Solve

(none yet)

## Phase 4 — Push

(none yet)

## Phase 5 — Finalize

(none yet)
```

- [ ] **Step 3: Write .env.example**

Create `agents/Solver - Issues/.env.example`:

```
# GitHub Actions secrets — these are set in the repo's Actions secrets,
# NOT in this file. This file documents what the workflow expects.
# Local debug via .claude/skills/solver-issues can populate a real .env
# for one-shot reruns.

CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
SUPABASE_URL=https://xeluydwpgiddbamysgyu.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SOLVER_GITHUB_TOKEN=github_pat_11A...
CMS_API_TOKEN=cmsk_...
CMS_BACKEND_URL=https://cms-backend-roman.vercel.app

# Optional tuning
SOLVER_MAX_RETRIES=3
SOLVER_STALE_CLAIM_MINUTES=15
```

- [ ] **Step 4: Write pytest.ini**

Create `agents/Solver - Issues/pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
pythonpath = .
```

- [ ] **Step 5: Write requirements files**

Create `agents/Solver - Issues/requirements.txt`:

```
# Runtime deps for Solver Agent (S3).
# Regenerate lockfile: pip-compile --generate-hashes --output-file=requirements.lock requirements.txt

supabase==2.9.1
requests==2.32.3
python-dotenv==1.2.2
```

Create `agents/Solver - Issues/requirements-dev.txt`:

```
-r requirements.txt

pytest==8.3.3
pytest-mock==3.14.0
```

(Lockfiles will be generated in Task 12 manually with `pip-compile`. Skip in this scaffold task.)

- [ ] **Step 6: Write empty tests __init__**

Create `agents/Solver - Issues/tests/__init__.py` with content:

```python
# pytest discovery anchor
```

- [ ] **Step 7: Write phase docs**

Create `agents/Solver - Issues/phases/1-claim.md`:

```markdown
# Phase 1 — Claim

**Goal:** Atomic priority-ordered claim of the next actionable issue, or exit cleanly if queue empty.

**Inputs:** Supabase service-role credentials.

**Steps:**
1. Build the priority-ordered claim UPDATE using `FOR UPDATE SKIP LOCKED`.
2. Query: pending issues OR in_progress + revision_feedback set; skip blocked; skip claims < 15 min old; skip retry_count >= SOLVER_MAX_RETRIES.
3. If no row returned, write `has_issue=false` to `GITHUB_OUTPUT` and exit 0.
4. If a row is returned: write `/tmp/issue.json` + `/tmp/agent-prompt.md`; write 4 outputs (`has_issue=true`, `repo`, `branch`, `issue_id`).

**Outputs:**
- `/tmp/issue.json` — full issue + project context for downstream steps.
- `/tmp/agent-prompt.md` — verification + fix instructions for the Claude action.
- `$GITHUB_OUTPUT` keys: `has_issue`, `repo`, `branch`, `issue_id`.

**Failure messages:**
- Supabase connection 500 → workflow fails at this step; release step skipped (no claim recorded).
```

Create `agents/Solver - Issues/phases/2-clone.md`:

```markdown
# Phase 2 — Clone

**Goal:** Shallow-clone the claimed issue's client repo into `./client-repo/` at the `cms-preview` HEAD.

**Inputs:**
- `/tmp/issue.json` (from Phase 1).
- `SOLVER_GITHUB_TOKEN`.

**Steps:**
1. Read repo `owner/name` and branch from `/tmp/issue.json` -> `project.github_repo` + `project.repo_branch`.
2. Run `git clone --depth 50 --branch <branch> https://x-access-token:<token>@github.com/<repo>.git ./client-repo`.
3. Configure git user as `Solver Agent <solver@roman-technologies.dev>` inside `./client-repo/`.

**Outputs:** `./client-repo/` working tree.

**Failure messages:**
- 401/403 → PAT scope drift; surface to release step with error "git clone failed: <code>".
- 404 → repo missing OR wrong branch; surface "Repo or branch not found".
```

Create `agents/Solver - Issues/phases/3-solve.md`:

```markdown
# Phase 3 — Solve

**Goal:** Let `anthropics/claude-code-action@v1` read `/tmp/agent-prompt.md` and edit files in `./client-repo/`.

**Inputs:**
- `/tmp/agent-prompt.md` — prompt built by Phase 1.
- `./client-repo/` — cloned repo.
- `CLAUDE_CODE_OAUTH_TOKEN`.

**Steps (executed by the action, not Python):**
1. Action sets up the Claude Code runtime.
2. Action reads the prompt file.
3. Agent executes Step 0 (verify) and Step 1 (fix) per prompt.
4. If verification fails OR agent gives up, agent writes `/tmp/agent-status.md`.
5. Action terminates when `max_turns` reached OR agent exits.

**Outputs:**
- Modified files in `./client-repo/` (if fix succeeded).
- `/tmp/agent-status.md` (if agent could not proceed).

**Failure messages:**
- Quota exhausted → action step exits non-zero; release step increments retry.
- Action timeout → workflow timeout (25 min) kills the job; stale claim window cleans up on next tick.
```

Create `agents/Solver - Issues/phases/4-push.md`:

```markdown
# Phase 4 — Push

**Goal:** Commit agent's file changes and push to `cms-preview`.

**Inputs:** `./client-repo/` working tree, `SOLVER_GITHUB_TOKEN`.

**Steps:**
1. If `/tmp/agent-status.md` exists → skip push, mark failed (Phase 5 handles).
2. Run `git -C client-repo diff --quiet`. If exit 0 (no diff) → mark failed.
3. Otherwise:
   - `git add -A`.
   - Commit with message `fix: <issue.title>\n\nAutomated fix by Solver Agent for CMS issue <id>.\n\nCo-Authored-By: Solver Agent (Claude Code) <solver@roman-technologies.dev>`.
   - Capture HEAD SHA.
   - `git push origin HEAD` (which is `cms-preview` from the clone).

**Outputs:** New commit on `cms-preview` of the client repo, SHA written to `/tmp/commit_sha`.

**Failure messages:**
- Push 403 → PAT scope drift OR branch protection; surface to release step.
- Push non-fast-forward → unlikely (we just cloned HEAD), but surface as "cms-preview moved during run".
```

Create `agents/Solver - Issues/phases/5-finalize.md`:

```markdown
# Phase 5 — Finalize

**Goal:** Mark issue `status='done'` via backend admin endpoint, persist `agent_commit_sha`, trigger S1 resolved-Slack flow.

**Inputs:** `/tmp/commit_sha`, `/tmp/issue.json`, `CMS_API_TOKEN`, `CMS_BACKEND_URL`.

**Steps:**
1. Write `agent_commit_sha = <sha>` and `agent_status = NULL` via Supabase (clears lock).
2. PATCH `<backend>/admin/issues/<issue_id>/status` with `{"status": "done"}` and bearer auth.
3. Backend's admin handler fires `slack_notify.notify_issue_resolved` → posts "✅ Issue Resolved" to `#issues-websites` → persists `slack_resolved_ts` → S1.5 awaits Stefan's ✅.

**Outputs:** Issue in DB: `status='done'`, `agent_commit_sha=<sha>`, `agent_status=NULL`, `slack_resolved_ts=<from notify>`.

**Failure messages:**
- Backend PATCH 5xx → log; do NOT mark failed (commit is durable). Stefan can manually flip the status from the dashboard, which fires S1 the normal way.
```

- [ ] **Step 8: Commit**

```bash
git add "agents/Solver - Issues/"
git commit -m "feat(solver): S3 agent folder scaffold + phase docs"
```

---

## Task 5: db.py — Supabase wrappers + claim SQL

**Files:**
- Create: `agents/Solver - Issues/db.py`
- Create: `agents/Solver - Issues/tests/test_db_claim.py`
- Create: `agents/Solver - Issues/tests/test_db_release.py`

- [ ] **Step 1: Write failing tests for claim**

Create `agents/Solver - Issues/tests/test_db_claim.py`:

```python
"""Atomic claim SQL behavior tests."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

import db  # local module


@pytest.fixture
def mock_pg(monkeypatch):
    """Stubs db._exec_sql to return canned rows."""
    monkeypatch.setenv("SUPABASE_URL", "http://localhost")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setenv("SOLVER_MAX_RETRIES", "3")
    monkeypatch.setenv("SOLVER_STALE_CLAIM_MINUTES", "15")

    captured = {}

    def fake_exec(sql: str, params: dict | None = None):
        captured.setdefault("calls", []).append({"sql": sql, "params": params})
        return captured.get("next_result", [])

    monkeypatch.setattr(db, "_exec_sql", fake_exec)
    return captured


def test_claim_returns_none_when_queue_empty(mock_pg):
    mock_pg["next_result"] = []
    assert db.claim_next_issue() is None


def test_claim_returns_first_row_when_present(mock_pg):
    row = {
        "id": "issue-1",
        "project_id": "proj-1",
        "title": "x",
        "description": "y",
        "priority": "High",
        "status": "pending",
        "revision_feedback": None,
    }
    mock_pg["next_result"] = [row]
    result = db.claim_next_issue()
    assert result == row


def test_claim_sql_contains_priority_ordering(mock_pg):
    mock_pg["next_result"] = []
    db.claim_next_issue()
    sql = mock_pg["calls"][0]["sql"]
    # Priority CASE ordering: High=1, Medium=2, Low=3
    assert "CASE priority" in sql
    assert "'High' THEN 1" in sql
    assert "'Medium' THEN 2" in sql
    assert "'Low' THEN 3" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql


def test_claim_sql_respects_max_retries(mock_pg):
    mock_pg["next_result"] = []
    db.claim_next_issue()
    sql = mock_pg["calls"][0]["sql"]
    assert "agent_retry_count < 3" in sql


def test_claim_sql_includes_revision_path(mock_pg):
    """Issues in_progress with revision_feedback must also be claimable."""
    mock_pg["next_result"] = []
    db.claim_next_issue()
    sql = mock_pg["calls"][0]["sql"]
    assert "in_progress" in sql
    assert "revision_feedback IS NOT NULL" in sql


def test_claim_sql_excludes_blocked(mock_pg):
    mock_pg["next_result"] = []
    db.claim_next_issue()
    sql = mock_pg["calls"][0]["sql"]
    assert "'blocked'" in sql


def test_claim_sql_handles_stale_lock(mock_pg):
    """Claims older than SOLVER_STALE_CLAIM_MINUTES are re-claimable."""
    mock_pg["next_result"] = []
    db.claim_next_issue()
    sql = mock_pg["calls"][0]["sql"]
    assert "interval '15 minutes'" in sql
```

- [ ] **Step 2: Write failing tests for release**

Create `agents/Solver - Issues/tests/test_db_release.py`:

```python
"""Release + retry counter behavior tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import db


@pytest.fixture
def stub_sb(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://localhost")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setenv("SOLVER_MAX_RETRIES", "3")

    sb = MagicMock()
    for m in ("table", "select", "eq", "single", "update", "execute"):
        getattr(sb, m).return_value = sb

    monkeypatch.setattr(db, "_supabase", lambda: sb)
    return sb


def test_release_failed_increments_retry_below_max(stub_sb):
    stub_sb.execute.return_value = MagicMock(data={"agent_retry_count": 1})
    db.release_issue_failed("issue-1", "transient")
    # 2 calls: SELECT, UPDATE
    update_payloads = [c.args[0] for c in stub_sb.update.call_args_list if c.args]
    assert len(update_payloads) == 1
    p = update_payloads[0]
    assert p["agent_status"] == "failed"
    assert p["agent_retry_count"] == 2
    assert p["agent_last_error"] == "transient"
    assert p["agent_claimed_at"] is None


def test_release_failed_marks_blocked_at_max(stub_sb):
    stub_sb.execute.return_value = MagicMock(data={"agent_retry_count": 2})
    db.release_issue_failed("issue-1", "third strike")
    p = [c.args[0] for c in stub_sb.update.call_args_list if c.args][0]
    assert p["agent_status"] == "blocked"
    assert p["agent_retry_count"] == 3


def test_release_failed_truncates_long_error(stub_sb):
    stub_sb.execute.return_value = MagicMock(data={"agent_retry_count": 0})
    db.release_issue_failed("issue-1", "x" * 1000)
    p = [c.args[0] for c in stub_sb.update.call_args_list if c.args][0]
    assert len(p["agent_last_error"]) == 500


def test_mark_done_writes_commit_sha_and_clears_lock(stub_sb):
    db.mark_done("issue-1", commit_sha="abc1234def")
    p = [c.args[0] for c in stub_sb.update.call_args_list if c.args][0]
    assert p["agent_commit_sha"] == "abc1234def"
    assert p["agent_status"] is None
    assert p["agent_claimed_at"] is None
```

- [ ] **Step 3: Run tests to confirm failure**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_db_claim.py tests/test_db_release.py -v
```

(Or from repo root: `cd "agents/Solver - Issues" && pytest tests/test_db_claim.py tests/test_db_release.py -v`. Use whichever venv is active; CMS Connector has its own; this agent will too in Task 12. For now, the backend venv from `backend/venv` works since these tests only need `pytest` + `pytest-mock`.)

Expected: collection error / import error (module doesn't exist).

- [ ] **Step 4: Implement db.py**

Create `agents/Solver - Issues/db.py`:

```python
"""Supabase wrappers for the Solver Agent.

Uses raw SQL via Supabase RPC for the atomic claim (the supabase-py client
doesn't expose FOR UPDATE SKIP LOCKED). Update/select for the other helpers
use the regular client.
"""
from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client


_MAX_ERROR_LEN = 500
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_STALE_MINUTES = 15


@lru_cache(maxsize=1)
def _supabase() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _max_retries() -> int:
    return int(os.environ.get("SOLVER_MAX_RETRIES", _DEFAULT_MAX_RETRIES))


def _stale_minutes() -> int:
    return int(os.environ.get("SOLVER_STALE_CLAIM_MINUTES", _DEFAULT_STALE_MINUTES))


def _build_claim_sql() -> str:
    """The atomic claim SQL. Returns a single matching row or empty."""
    return f"""
WITH next_issue AS (
  SELECT id FROM project_issues
  WHERE
    (
      (status = 'pending' AND COALESCE(agent_status, 'idle') IN ('idle', 'failed'))
      OR
      (status = 'in_progress' AND revision_feedback IS NOT NULL AND COALESCE(agent_status, 'idle') IN ('idle', 'failed'))
    )
    AND agent_retry_count < {_max_retries()}
    AND COALESCE(agent_status, 'idle') != 'blocked'
    AND (agent_claimed_at IS NULL OR agent_claimed_at < now() - interval '{_stale_minutes()} minutes')
  ORDER BY
    CASE priority
      WHEN 'High' THEN 1
      WHEN 'Medium' THEN 2
      WHEN 'Low' THEN 3
      ELSE 4
    END,
    created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
)
UPDATE project_issues
SET
  agent_status = 'claimed',
  agent_claimed_at = now()
WHERE id = (SELECT id FROM next_issue)
RETURNING id, project_id, title, description, priority, status, revision_feedback;
""".strip()


def _exec_sql(sql: str, params: dict | None = None) -> list[dict]:
    """Execute raw SQL via Supabase RPC `exec_sql` (server-side function).

    Note: Supabase Postgres doesn't expose arbitrary SQL via the REST API.
    We use a stored procedure `exec_sql_select` (created via migration) that
    runs the SQL with elevated privileges and returns rows as JSON.

    For unit tests this function is monkeypatched.
    """
    sb = _supabase()
    response = sb.rpc("exec_sql_select", {"sql": sql}).execute()
    return response.data or []


def claim_next_issue() -> dict | None:
    """Returns claimed issue row, or None if nothing actionable."""
    rows = _exec_sql(_build_claim_sql())
    return rows[0] if rows else None


def fetch_project(project_id: str) -> dict:
    sb = _supabase()
    result = (
        sb.table("projects")
        .select(
            "id, name, slug, github_repo, repo_branch, production_branch, "
            "preview_url, production_url, user_id"
        )
        .eq("id", project_id)
        .single()
        .execute()
    )
    return result.data or {}


def release_issue_failed(issue_id: str, error: str) -> None:
    """Increment retry counter; transition to 'failed' or 'blocked'."""
    sb = _supabase()
    current = (
        sb.table("project_issues")
        .select("agent_retry_count")
        .eq("id", issue_id)
        .single()
        .execute()
    )
    new_count = current.data["agent_retry_count"] + 1
    new_status = "blocked" if new_count >= _max_retries() else "failed"

    sb.table("project_issues").update(
        {
            "agent_status": new_status,
            "agent_claimed_at": None,
            "agent_retry_count": new_count,
            "agent_last_error": error[:_MAX_ERROR_LEN],
        }
    ).eq("id", issue_id).execute()


def mark_done(issue_id: str, *, commit_sha: str) -> None:
    """Clear lock and record the commit SHA. The status='done' transition
    is done by the backend admin endpoint (separate call) because that's
    what fires the S1 Slack notification."""
    sb = _supabase()
    sb.table("project_issues").update(
        {
            "agent_commit_sha": commit_sha,
            "agent_status": None,
            "agent_claimed_at": None,
        }
    ).eq("id", issue_id).execute()
```

**Important note on `exec_sql_select`**: The atomic claim requires `FOR UPDATE SKIP LOCKED` which supabase-py's REST client doesn't expose. We need a Postgres function deployed via migration. Add this to the same Task 1 migration file:

Edit `backend/migrations/2026_05_16_solver_agent_columns.sql` and append:

```sql
-- Server-side function used by the Solver Agent for the atomic claim.
-- Called via Supabase RPC. service_role-only by default grants.
CREATE OR REPLACE FUNCTION exec_sql_select(sql TEXT)
RETURNS SETOF jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY EXECUTE 'SELECT to_jsonb(t) FROM (' || sql || ') t';
END;
$$;

-- Lock down: only service_role can call. anon + authenticated cannot.
REVOKE ALL ON FUNCTION exec_sql_select(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION exec_sql_select(TEXT) TO service_role;
```

Actually — `exec_sql_select` allowing arbitrary SQL is a **major security risk**. Even though grants restrict to service_role, the JWT we use IS service_role, and any agent code or compromised env could call it with destructive SQL. Better: ship a dedicated `claim_next_solver_issue()` function with no parameters.

**Revise the migration addition to:**

```sql
-- Atomic claim function used by Solver Agent. No parameters → no SQL injection surface.
CREATE OR REPLACE FUNCTION claim_next_solver_issue(
  p_max_retries INT DEFAULT 3,
  p_stale_minutes INT DEFAULT 15
)
RETURNS TABLE (
  id UUID,
  project_id UUID,
  title TEXT,
  description TEXT,
  priority TEXT,
  status TEXT,
  revision_feedback TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  WITH next_issue AS (
    SELECT pi.id FROM project_issues pi
    WHERE
      (
        (pi.status = 'pending' AND COALESCE(pi.agent_status, 'idle') IN ('idle', 'failed'))
        OR
        (pi.status = 'in_progress' AND pi.revision_feedback IS NOT NULL AND COALESCE(pi.agent_status, 'idle') IN ('idle', 'failed'))
      )
      AND pi.agent_retry_count < p_max_retries
      AND COALESCE(pi.agent_status, 'idle') != 'blocked'
      AND (pi.agent_claimed_at IS NULL OR pi.agent_claimed_at < now() - (p_stale_minutes || ' minutes')::interval)
    ORDER BY
      CASE pi.priority
        WHEN 'High' THEN 1
        WHEN 'Medium' THEN 2
        WHEN 'Low' THEN 3
        ELSE 4
      END,
      pi.created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  UPDATE project_issues
  SET
    agent_status = 'claimed',
    agent_claimed_at = now()
  WHERE project_issues.id = (SELECT next_issue.id FROM next_issue)
  RETURNING
    project_issues.id, project_issues.project_id, project_issues.title,
    project_issues.description, project_issues.priority, project_issues.status,
    project_issues.revision_feedback;
END;
$$;

REVOKE ALL ON FUNCTION claim_next_solver_issue(INT, INT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION claim_next_solver_issue(INT, INT) TO service_role;
```

And update `db.py`:

- Remove the `_build_claim_sql()` + `_exec_sql()` helpers.
- Replace `claim_next_issue()` body with:

```python
def claim_next_issue() -> dict | None:
    """Returns claimed issue row, or None if nothing actionable."""
    sb = _supabase()
    response = sb.rpc(
        "claim_next_solver_issue",
        {
            "p_max_retries": _max_retries(),
            "p_stale_minutes": _stale_minutes(),
        },
    ).execute()
    rows = response.data or []
    return rows[0] if rows else None
```

Update the test fixture `mock_pg` to stub `sb.rpc(...).execute()` instead of `_exec_sql`. The 7 claim tests that assert "SQL contains X" need to change — they were testing the SQL string. Since the SQL is now in a stored function, the unit tests should instead assert:
- The RPC call uses function name `claim_next_solver_issue`.
- The RPC params include `p_max_retries` and `p_stale_minutes` with env-driven values.

**Replace** the 7 `claim` tests with:

```python
def test_claim_returns_none_when_queue_empty(mock_pg):
    mock_pg["next_result"] = []
    assert db.claim_next_issue() is None


def test_claim_returns_first_row_when_present(mock_pg):
    row = {
        "id": "issue-1",
        "project_id": "proj-1",
        "title": "x",
        "description": "y",
        "priority": "High",
        "status": "pending",
        "revision_feedback": None,
    }
    mock_pg["next_result"] = [row]
    assert db.claim_next_issue() == row


def test_claim_uses_correct_rpc_name(mock_pg):
    mock_pg["next_result"] = []
    db.claim_next_issue()
    assert mock_pg["calls"][0]["fn"] == "claim_next_solver_issue"


def test_claim_passes_env_overrides_to_rpc(monkeypatch, mock_pg):
    monkeypatch.setenv("SOLVER_MAX_RETRIES", "5")
    monkeypatch.setenv("SOLVER_STALE_CLAIM_MINUTES", "30")
    mock_pg["next_result"] = []
    db.claim_next_issue()
    params = mock_pg["calls"][0]["params"]
    assert params["p_max_retries"] == 5
    assert params["p_stale_minutes"] == 30
```

And update the `mock_pg` fixture to patch `db._supabase`:

```python
@pytest.fixture
def mock_pg(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://localhost")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setenv("SOLVER_MAX_RETRIES", "3")
    monkeypatch.setenv("SOLVER_STALE_CLAIM_MINUTES", "15")

    captured = {"calls": [], "next_result": []}

    fake_sb = MagicMock()
    fake_rpc_chain = MagicMock()

    def fake_rpc(fn_name, params):
        captured["calls"].append({"fn": fn_name, "params": params})
        return fake_rpc_chain

    fake_sb.rpc.side_effect = fake_rpc
    fake_rpc_chain.execute = lambda: MagicMock(data=captured["next_result"])

    monkeypatch.setattr(db, "_supabase", lambda: fake_sb)
    return captured
```

- [ ] **Step 5: Run tests**

```bash
cd "agents/Solver - Issues" && pytest tests/test_db_claim.py tests/test_db_release.py -v
```

Expected: all pass (4 claim + 4 release = 8 tests).

- [ ] **Step 6: Commit (DB part split into two commits)**

```bash
git add backend/migrations/2026_05_16_solver_agent_columns.sql
git commit --amend --no-edit  # extend Task 1's commit with the RPC function
git add "agents/Solver - Issues/db.py" "agents/Solver - Issues/tests/test_db_claim.py" "agents/Solver - Issues/tests/test_db_release.py"
git commit -m "feat(solver): db.py with atomic claim via Supabase RPC + retry helpers"
```

(Note: `--amend --no-edit` modifies Task 1's commit to include the RPC function. If you've already pushed Task 1's commit, do NOT amend — instead make a new commit titled `feat(db): add claim_next_solver_issue RPC`.)

---

## Task 6: repo.py — git clone + commit + push

**Files:**
- Create: `agents/Solver - Issues/repo.py`
- Create: `agents/Solver - Issues/tests/test_repo.py`

- [ ] **Step 1: Write failing tests**

Create `agents/Solver - Issues/tests/test_repo.py`:

```python
"""Git clone + commit + push tests (mocked subprocess)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

import repo


@pytest.fixture
def fake_run(monkeypatch):
    monkeypatch.setenv("SOLVER_GITHUB_TOKEN", "ghs_test")
    calls = []

    def run(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    monkeypatch.setattr(repo.subprocess, "run", run)
    return calls


def test_clone_uses_shallow_depth_and_branch(fake_run):
    repo.clone("owner/name", "cms-preview", "./client-repo")
    clone_call = fake_run[0]
    assert clone_call["args"][0] == "git"
    assert "clone" in clone_call["args"]
    assert "--depth" in clone_call["args"]
    assert "50" in clone_call["args"]
    assert "--branch" in clone_call["args"]
    assert "cms-preview" in clone_call["args"]
    # Token embedded in URL via x-access-token user
    url = next(a for a in clone_call["args"] if a.startswith("https://"))
    assert "x-access-token:ghs_test@github.com/owner/name" in url


def test_clone_configures_git_user(fake_run):
    repo.clone("owner/name", "cms-preview", "./client-repo")
    # 2 user-config calls after clone
    user_email = [c for c in fake_run if "user.email" in str(c["args"])]
    user_name = [c for c in fake_run if "user.name" in str(c["args"])]
    assert len(user_email) == 1
    assert len(user_name) == 1
    assert "solver@roman-technologies.dev" in str(user_email[0]["args"])
    assert "Solver Agent" in str(user_name[0]["args"])


def test_has_diff_returns_true_when_changes(fake_run, monkeypatch):
    def fake_run_with_diff(args, **kwargs):
        result = MagicMock()
        if "--quiet" in args:
            result.returncode = 1  # diff exists
        else:
            result.returncode = 0
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_with_diff)
    assert repo.has_diff("./client-repo") is True


def test_has_diff_returns_false_when_clean(fake_run, monkeypatch):
    def fake_run_clean(args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_clean)
    assert repo.has_diff("./client-repo") is False


def test_commit_uses_required_message_format(fake_run, monkeypatch):
    def fake_run_with_sha(args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        if "rev-parse" in args:
            result.stdout = "abc123def4567\n"
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_with_sha)

    sha = repo.commit_and_push(
        path="./client-repo",
        issue_id="issue-1",
        issue_title="Hero broken",
    )

    assert sha == "abc123def4567"
    commit_call = next(c for c in fake_run if "commit" in c["args"])
    msg = next(a for a in commit_call["args"] if a.startswith("fix:"))
    assert "fix: Hero broken" in msg
    assert "Automated fix by Solver Agent" in msg
    assert "Co-Authored-By: Solver Agent" in msg


def test_commit_truncates_long_title(fake_run, monkeypatch):
    monkeypatch.setattr(repo.subprocess, "run", lambda args, **kw: MagicMock(returncode=0, stdout="sha\n"))
    long_title = "a" * 200
    repo.commit_and_push(path="./client-repo", issue_id="issue-1", issue_title=long_title)
    # No exception; truncation enforced internally
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
cd "agents/Solver - Issues" && pytest tests/test_repo.py -v
```

Expected: collection error.

- [ ] **Step 3: Implement repo.py**

Create `agents/Solver - Issues/repo.py`:

```python
"""Git operations for the Solver Agent.

Shallow clone, has-diff check, commit-and-push. Token-authed via
SOLVER_GITHUB_TOKEN env. Uses subprocess directly — no GitPython dep.
"""
from __future__ import annotations

import os
import subprocess

_GIT_USER_EMAIL = "solver@roman-technologies.dev"
_GIT_USER_NAME = "Solver Agent"
_MAX_TITLE_LEN = 60


def _token() -> str:
    return os.environ["SOLVER_GITHUB_TOKEN"]


def _run(args: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)


def clone(repo: str, branch: str, dest: str) -> None:
    """Shallow-clone repo (owner/name) at branch into dest.

    Embeds SOLVER_GITHUB_TOKEN in the HTTPS URL via the x-access-token user.
    """
    url = f"https://x-access-token:{_token()}@github.com/{repo}.git"
    _run(["git", "clone", "--depth", "50", "--branch", branch, url, dest])
    _run(["git", "-C", dest, "config", "user.email", _GIT_USER_EMAIL])
    _run(["git", "-C", dest, "config", "user.name", _GIT_USER_NAME])


def has_diff(path: str) -> bool:
    """True iff there are uncommitted changes in path's working tree."""
    result = _run(["git", "-C", path, "diff", "--quiet"], check=False)
    return result.returncode != 0


def commit_and_push(*, path: str, issue_id: str, issue_title: str) -> str:
    """Stage all changes, commit, push current HEAD to origin.

    Returns the new HEAD SHA.
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
    _run(["git", "-C", path, "push", "origin", "HEAD"])
    return sha
```

- [ ] **Step 4: Run tests**

```bash
cd "agents/Solver - Issues" && pytest tests/test_repo.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add "agents/Solver - Issues/repo.py" "agents/Solver - Issues/tests/test_repo.py"
git commit -m "feat(solver): repo.py shallow clone + commit + push helpers"
```

---

## Task 7: backend_api.py + slack.py — orchestrator clients

**Files:**
- Create: `agents/Solver - Issues/backend_api.py`
- Create: `agents/Solver - Issues/slack.py`

(No dedicated tests for these — they're thin HTTP wrappers; coverage comes from `test_finalize.py` and integration smoke.)

- [ ] **Step 1: Implement backend_api.py**

Create `agents/Solver - Issues/backend_api.py`:

```python
"""HTTP client for the backend admin endpoints.

Used by finalize.py to mark issues done via the new
PATCH /admin/issues/{id}/status route (which fires S1 Slack post +
persists slack_resolved_ts).
"""
from __future__ import annotations

import os

import requests


def _backend_url() -> str:
    return os.environ["CMS_BACKEND_URL"].rstrip("/")


def _token() -> str:
    return os.environ["CMS_API_TOKEN"]


def trigger_issue_resolved(issue_id: str, *, timeout: int = 15) -> dict:
    """PATCH /admin/issues/{id}/status with status='done'. Raises on non-2xx."""
    url = f"{_backend_url()}/admin/issues/{issue_id}/status"
    response = requests.patch(
        url,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
            "User-Agent": "solver-agent/1.0",
        },
        json={"status": "done"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()
```

- [ ] **Step 2: Implement slack.py (for blocked-issue notifications)**

Create `agents/Solver - Issues/slack.py`:

```python
"""Slack notifications from the Solver Agent.

For routine outcomes (success, retry), we let the existing backend Slack
machinery (via admin endpoint) handle the Slack post. For agent-internal
events that the backend doesn't know about — specifically the 'agent
blocked after N retries' notification — we POST directly to the
chat.postMessage API using the SLACK_BOT_TOKEN.

Disabled silently when SLACK_BOT_TOKEN or SLACK_ISSUES_CHANNEL_ID is unset.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

_SLACK_API = "https://slack.com/api/chat.postMessage"
_TIMEOUT = 10


def _enabled() -> bool:
    return bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_ISSUES_CHANNEL_ID"))


def post_blocked_notification(
    *,
    issue_id: str,
    title: str,
    project_name: str,
    retry_count: int,
    last_error: str,
) -> None:
    if not _enabled():
        logger.info("slack disabled — skipping blocked notification")
        return
    text = (
        f"🛑 *Agent gave up — {project_name}*\n"
        f"*Title:* {title}\n"
        f"*Tried:* {retry_count} times\n"
        f"*Last error:* {last_error[:300]}\n\n"
        f"This issue needs manual attention. Use the dashboard to reset agent_retry_count when ready."
    )
    try:
        response = requests.post(
            _SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
                "text": text,
            },
            timeout=_TIMEOUT,
        )
        body = response.json()
        if not body.get("ok"):
            logger.warning("slack post_blocked failed: %s", body.get("error"))
    except Exception:
        logger.exception("slack post_blocked exception")
```

Note: `SLACK_BOT_TOKEN` and `SLACK_ISSUES_CHANNEL_ID` are added to GitHub Actions secrets in Task 11 deploy.

- [ ] **Step 3: Commit**

```bash
git add "agents/Solver - Issues/backend_api.py" "agents/Solver - Issues/slack.py"
git commit -m "feat(solver): backend_api.py + slack.py thin HTTP clients"
```

---

## Task 8: claim_issue.py — workflow entrypoint

**Files:**
- Create: `agents/Solver - Issues/claim_issue.py`
- Create: `agents/Solver - Issues/tests/test_claim_issue.py`

- [ ] **Step 1: Write failing tests**

Create `agents/Solver - Issues/tests/test_claim_issue.py`:

```python
"""Tests for the workflow's first step: claim + write outputs."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import claim_issue


@pytest.fixture
def gh_output(tmp_path, monkeypatch):
    """Stub GITHUB_OUTPUT to a tmp file we can inspect."""
    output_path = tmp_path / "gh_output"
    output_path.write_text("")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    return output_path


@pytest.fixture
def tmp_files(tmp_path, monkeypatch):
    """Redirect /tmp paths to tmp_path so tests don't pollute the host."""
    monkeypatch.setattr(claim_issue, "ISSUE_JSON_PATH", str(tmp_path / "issue.json"))
    monkeypatch.setattr(claim_issue, "PROMPT_PATH", str(tmp_path / "agent-prompt.md"))
    return tmp_path


def test_no_actionable_issue_writes_false_output(monkeypatch, gh_output, tmp_files):
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: None)
    assert claim_issue.main() == 0
    out = gh_output.read_text()
    assert "has_issue=false" in out
    assert not (tmp_files / "issue.json").exists()
    assert not (tmp_files / "agent-prompt.md").exists()


def test_actionable_issue_writes_outputs_and_prompt(monkeypatch, gh_output, tmp_files):
    issue = {
        "id": "issue-1",
        "project_id": "proj-1",
        "title": "Hero broken",
        "description": "stretches on iPhone",
        "priority": "High",
        "status": "pending",
        "revision_feedback": None,
    }
    project = {
        "id": "proj-1",
        "slug": "acme",
        "name": "Acme",
        "github_repo": "stefan/acme",
        "repo_branch": "cms-preview",
    }
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: issue)
    monkeypatch.setattr(claim_issue.db, "fetch_project", lambda pid: project)

    assert claim_issue.main() == 0

    out = gh_output.read_text()
    assert "has_issue=true" in out
    assert "repo=stefan/acme" in out
    assert "branch=cms-preview" in out
    assert "issue_id=issue-1" in out

    issue_json = json.loads((tmp_files / "issue.json").read_text())
    assert issue_json["id"] == "issue-1"
    assert issue_json["project"]["slug"] == "acme"

    prompt = (tmp_files / "agent-prompt.md").read_text()
    assert "Hero broken" in prompt
    assert "stretches on iPhone" in prompt
    assert "Step 0 — Verify the issue is real" in prompt
    assert "Previous attempt was rejected" not in prompt  # no revision_feedback


def test_prompt_includes_revision_feedback_when_present(monkeypatch, gh_output, tmp_files):
    issue = {
        "id": "issue-2",
        "project_id": "proj-1",
        "title": "Footer year",
        "description": "should be 2026",
        "priority": "Low",
        "status": "in_progress",
        "revision_feedback": "the change you made broke the header",
    }
    project = {"slug": "acme", "github_repo": "stefan/acme", "repo_branch": "cms-preview"}
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: issue)
    monkeypatch.setattr(claim_issue.db, "fetch_project", lambda pid: project)

    claim_issue.main()
    prompt = (tmp_files / "agent-prompt.md").read_text()
    assert "Previous attempt was rejected" in prompt
    assert "the change you made broke the header" in prompt
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
cd "agents/Solver - Issues" && pytest tests/test_claim_issue.py -v
```

Expected: collection error.

- [ ] **Step 3: Implement claim_issue.py**

Create `agents/Solver - Issues/claim_issue.py`:

```python
"""Workflow entrypoint: claim an actionable issue + emit outputs for the next workflow steps.

Always exits 0 (even on no-work). Sets GitHub Actions outputs:
- has_issue: 'true' | 'false'
- (when true) repo, branch, issue_id

Writes /tmp/issue.json + /tmp/agent-prompt.md when an issue is claimed.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import db


ISSUE_JSON_PATH = "/tmp/issue.json"
PROMPT_PATH = "/tmp/agent-prompt.md"


def main() -> int:
    issue = db.claim_next_issue()
    gh_output = Path(os.environ["GITHUB_OUTPUT"])

    if issue is None:
        with gh_output.open("a") as f:
            f.write("has_issue=false\n")
        print("no actionable issues")
        return 0

    project = db.fetch_project(issue["project_id"])
    payload = {**issue, "project": project}

    Path(ISSUE_JSON_PATH).write_text(json.dumps(payload, separators=(",", ":")))
    Path(PROMPT_PATH).write_text(_build_prompt(issue, project))

    with gh_output.open("a") as f:
        f.write("has_issue=true\n")
        f.write(f"repo={project['github_repo']}\n")
        f.write(f"branch={project['repo_branch']}\n")
        f.write(f"issue_id={issue['id']}\n")
    print(f"claimed issue {issue['id']} (priority={issue['priority']})")
    return 0


def _build_prompt(issue: dict, project: dict) -> str:
    revision_section = ""
    if issue.get("revision_feedback"):
        revision_section = (
            "\n## Previous attempt was rejected\n"
            "Stefan's feedback on the last fix attempt:\n"
            f"> {issue['revision_feedback']}\n\n"
            "Look at git log for your previous commit (most recent commit on "
            f"{project['repo_branch']}), understand what you did, and address "
            "Stefan's feedback this time.\n"
        )

    return f"""You are an autonomous code-fixing agent for a client website.

## Repository
Working directory: `./client-repo/` (already cloned at branch `{project['repo_branch']}`).

## Issue submitted by client
**Title:** {issue['title']}
**Priority:** {issue['priority']}
**Description:**
{issue['description']}
{revision_section}

## Step 0 — Verify the issue is real
Before attempting any fix, explore the codebase to confirm the issue actually exists.
The client describes the problem in their own words; that doesn't mean the bug is real.
Reasons it may NOT be a real bug:
- The element/text the client references doesn't exist in the code.
- The behavior the client wants is already in place.
- The "issue" is actually a feature request needing content-side (CMS) changes.
- The description is ambiguous and could describe a working component.

If after a reasonable exploration (Glob/Grep + Read 2-5 likely candidates) you conclude
the issue is NOT a real code-level bug, write one line to `/tmp/agent-status.md`:

> Cannot reproduce: <one-sentence reason>

Then exit. The orchestrator will mark the issue as failed.

If you are unsure but the issue could plausibly be real, proceed to Step 1.

## Step 1 — Fix the issue
1. Explore the repo to find the relevant code.
2. Make the minimum change required to resolve the issue.
3. If you change shared components, verify other call sites still work.
4. Do NOT run `npm install` or modify lockfiles unless adding a dependency is strictly required.
5. Do NOT modify CI configs, GitHub workflows, or env files.

## When you cannot fix the issue
If after exploration you cannot determine what to change, write one line to
`/tmp/agent-status.md`:

> Cannot fix: <one-sentence reason>

Then exit. The orchestrator will mark the issue as failed.

## When you finish a fix
Just exit cleanly. The orchestrator commits and pushes your changes to
`{project['repo_branch']}`. Do NOT run git commit or git push yourself.
"""


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests**

```bash
cd "agents/Solver - Issues" && pytest tests/test_claim_issue.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add "agents/Solver - Issues/claim_issue.py" "agents/Solver - Issues/tests/test_claim_issue.py"
git commit -m "feat(solver): claim_issue.py — claim + build prompt + write outputs"
```

---

## Task 9: clone_repo.py — workflow entrypoint

**Files:**
- Create: `agents/Solver - Issues/clone_repo.py`

(No dedicated unit test — thin wrapper over `repo.clone`. Smoke-tested in workflow.)

- [ ] **Step 1: Implement clone_repo.py**

Create `agents/Solver - Issues/clone_repo.py`:

```python
"""Workflow entrypoint: clone the claimed client repo into ./client-repo/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import repo


def main() -> int:
    issue = json.loads(Path("/tmp/issue.json").read_text())
    project = issue["project"]
    dest = "./client-repo"

    # Clean if a previous failed run left a stale dir.
    if Path(dest).exists():
        import shutil
        shutil.rmtree(dest)

    repo.clone(
        repo=project["github_repo"],
        branch=project["repo_branch"],
        dest=dest,
    )
    print(f"cloned {project['github_repo']} @ {project['repo_branch']} → {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add "agents/Solver - Issues/clone_repo.py"
git commit -m "feat(solver): clone_repo.py — shallow clone the claimed client repo"
```

---

## Task 10: finalize.py + release_issue.py — workflow finalize steps

**Files:**
- Create: `agents/Solver - Issues/finalize.py`
- Create: `agents/Solver - Issues/release_issue.py`
- Create: `agents/Solver - Issues/tests/test_finalize.py`

- [ ] **Step 1: Write failing tests for finalize**

Create `agents/Solver - Issues/tests/test_finalize.py`:

```python
"""Tests for finalize.py — the post-agent-step handler."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import finalize


@pytest.fixture
def issue_payload(tmp_path, monkeypatch):
    issue = {
        "id": "issue-1",
        "project_id": "proj-1",
        "title": "Hero broken",
        "description": "stretches",
        "priority": "High",
        "status": "pending",
        "project": {
            "slug": "acme",
            "github_repo": "stefan/acme",
            "repo_branch": "cms-preview",
        },
    }
    issue_path = tmp_path / "issue.json"
    issue_path.write_text(json.dumps(issue))
    status_path = tmp_path / "agent-status.md"

    monkeypatch.setattr(finalize, "ISSUE_JSON_PATH", str(issue_path))
    monkeypatch.setattr(finalize, "STATUS_MD_PATH", str(status_path))
    monkeypatch.setattr(finalize, "REPO_DIR", "./client-repo")

    return {"issue": issue, "issue_path": issue_path, "status_path": status_path}


def test_agent_status_md_cannot_reproduce_marks_failed(monkeypatch, issue_payload):
    issue_payload["status_path"].write_text("Cannot reproduce: hero section already responsive")

    release_calls = []
    monkeypatch.setattr(
        finalize.db,
        "release_issue_failed",
        lambda iid, err: release_calls.append({"id": iid, "err": err}),
    )
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)  # would-be-true otherwise
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push"))

    assert finalize.main() == 0
    assert len(release_calls) == 1
    assert "Cannot reproduce" in release_calls[0]["err"]


def test_agent_status_md_cannot_fix_marks_failed(monkeypatch, issue_payload):
    issue_payload["status_path"].write_text("Cannot fix: too complex")

    release_calls = []
    monkeypatch.setattr(
        finalize.db, "release_issue_failed", lambda iid, err: release_calls.append(err)
    )
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: False)
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push"))

    finalize.main()
    assert "Cannot fix" in release_calls[0]


def test_empty_diff_marks_failed(monkeypatch, issue_payload):
    release_calls = []
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: False)
    monkeypatch.setattr(
        finalize.db, "release_issue_failed", lambda iid, err: release_calls.append(err)
    )
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push"))

    finalize.main()
    assert any("no file changes" in e for e in release_calls)


def test_happy_path_commits_pushes_marks_done(monkeypatch, issue_payload):
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(
        finalize.repo,
        "commit_and_push",
        lambda **kw: "abc1234def5678",
    )

    mark_done_calls = []
    monkeypatch.setattr(
        finalize.db, "mark_done", lambda iid, commit_sha: mark_done_calls.append((iid, commit_sha))
    )

    backend_calls = []
    monkeypatch.setattr(
        finalize.backend_api,
        "trigger_issue_resolved",
        lambda iid: backend_calls.append(iid) or {},
    )

    assert finalize.main() == 0
    assert mark_done_calls == [("issue-1", "abc1234def5678")]
    assert backend_calls == ["issue-1"]


def test_backend_5xx_does_not_fail_finalize(monkeypatch, issue_payload):
    import requests

    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: "sha123")
    monkeypatch.setattr(finalize.db, "mark_done", lambda *a, **kw: None)

    def fake_trigger(iid):
        raise requests.HTTPError("500 Internal Server Error")

    monkeypatch.setattr(finalize.backend_api, "trigger_issue_resolved", fake_trigger)

    # Must exit 0 — commit is durable, backend post is best-effort.
    assert finalize.main() == 0
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
cd "agents/Solver - Issues" && pytest tests/test_finalize.py -v
```

Expected: collection error.

- [ ] **Step 3: Implement finalize.py**

Create `agents/Solver - Issues/finalize.py`:

```python
"""Workflow entrypoint after the Claude Code action runs.

Decision tree:
- /tmp/agent-status.md exists → release_issue_failed(content), no push
- no diff in working tree → release_issue_failed("no file changes"), no push
- otherwise → commit + push + mark_done + trigger_issue_resolved
"""
from __future__ import annotations

import logging
import json
import sys
from pathlib import Path

import db
import repo
import backend_api


logger = logging.getLogger(__name__)

ISSUE_JSON_PATH = "/tmp/issue.json"
STATUS_MD_PATH = "/tmp/agent-status.md"
REPO_DIR = "./client-repo"


def main() -> int:
    issue = json.loads(Path(ISSUE_JSON_PATH).read_text())
    status_md = Path(STATUS_MD_PATH)

    if status_md.exists():
        reason = status_md.read_text().strip()[:500]
        db.release_issue_failed(issue["id"], reason or "agent wrote empty status.md")
        print(f"released as failed: {reason}")
        return 0

    if not repo.has_diff(REPO_DIR):
        db.release_issue_failed(issue["id"], "agent produced no file changes")
        print("released as failed: no diff")
        return 0

    sha = repo.commit_and_push(
        path=REPO_DIR,
        issue_id=issue["id"],
        issue_title=issue["title"],
    )
    print(f"pushed commit {sha[:7]}")

    db.mark_done(issue["id"], commit_sha=sha)

    try:
        backend_api.trigger_issue_resolved(issue["id"])
        print("backend mark-done + Slack notify dispatched")
    except Exception:
        logger.exception("backend trigger_issue_resolved failed (commit is durable)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Implement release_issue.py**

Create `agents/Solver - Issues/release_issue.py`:

```python
"""Workflow entrypoint on `failure()` — increment retry counter for the
currently-claimed issue.

Reads issue id from /tmp/issue.json (claim_issue.py wrote it). If the
file doesn't exist, no issue was claimed → nothing to release.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import db
import slack as slack_client


logger = logging.getLogger(__name__)

ISSUE_JSON_PATH = "/tmp/issue.json"


def main() -> int:
    path = Path(ISSUE_JSON_PATH)
    if not path.exists():
        print("no claim to release")
        return 0

    issue = json.loads(path.read_text())
    error = _failure_reason()

    db.release_issue_failed(issue["id"], error)
    print(f"released issue {issue['id']} as failed: {error[:80]}")

    # If we just transitioned to 'blocked', send a top-level Slack notification.
    # Re-read the row to know the new state.
    new_count = _current_retry_count(issue["id"])
    if new_count >= int(__import__("os").environ.get("SOLVER_MAX_RETRIES", "3")):
        slack_client.post_blocked_notification(
            issue_id=issue["id"],
            title=issue["title"],
            project_name=issue.get("project", {}).get("name", issue.get("project", {}).get("slug", "unknown")),
            retry_count=new_count,
            last_error=error,
        )

    return 0


def _failure_reason() -> str:
    """Best-effort: read the most-recent step's failure hint from the env.
    Falls back to a generic message."""
    import os
    failed_step = os.environ.get("FAILED_STEP", "")
    return f"workflow step failed: {failed_step}" if failed_step else "workflow failure (no specific step recorded)"


def _current_retry_count(issue_id: str) -> int:
    sb = db._supabase()
    row = (
        sb.table("project_issues")
        .select("agent_retry_count")
        .eq("id", issue_id)
        .single()
        .execute()
    )
    return row.data["agent_retry_count"]


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run finalize tests**

```bash
cd "agents/Solver - Issues" && pytest tests/test_finalize.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Run full agent test suite**

```bash
cd "agents/Solver - Issues" && pytest -v
```

Expected: claim (4) + release (4) + repo (6) + claim_issue (3) + finalize (5) = 22 passed.

- [ ] **Step 7: Commit**

```bash
git add "agents/Solver - Issues/finalize.py" "agents/Solver - Issues/release_issue.py" "agents/Solver - Issues/tests/test_finalize.py"
git commit -m "feat(solver): finalize.py + release_issue.py workflow entrypoints"
```

---

## Task 11: GitHub Actions workflow + lockfile

**Files:**
- Create: `.github/workflows/solver-agent.yml`
- Create: `agents/Solver - Issues/requirements.lock`
- Create: `agents/Solver - Issues/requirements-dev.lock` (optional, but matches CMS Connector hygiene)

- [ ] **Step 1: Generate the lockfile**

```bash
cd "agents/Solver - Issues"
pip install pip-tools==7.4.1
pip-compile --generate-hashes --output-file=requirements.lock requirements.txt
pip-compile --generate-hashes --output-file=requirements-dev.lock requirements-dev.txt
```

(This requires the backend venv or any Python 3.13 env. Activate with `source ../../backend/venv/Scripts/activate` if convenient.)

- [ ] **Step 2: Write the workflow YAML**

Create `.github/workflows/solver-agent.yml`:

```yaml
name: Solver Agent (S3)

on:
  schedule:
    - cron: '*/15 * * * *'   # every 15 min UTC
  workflow_dispatch: {}      # manual trigger for testing

concurrency:
  group: solver-agent
  cancel-in-progress: false  # let in-flight run finish

jobs:
  solve:
    runs-on: ubuntu-latest
    timeout-minutes: 25

    permissions:
      contents: read

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
          cache: pip
          cache-dependency-path: agents/Solver - Issues/requirements.lock

      - name: Install agent deps
        run: |
          cd "agents/Solver - Issues"
          pip install --require-hashes -r requirements.lock

      - name: Claim next issue
        id: claim
        run: python "agents/Solver - Issues/claim_issue.py"
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}

      - name: Clone client repo
        if: steps.claim.outputs.has_issue == 'true'
        run: python "agents/Solver - Issues/clone_repo.py"
        env:
          SOLVER_GITHUB_TOKEN: ${{ secrets.SOLVER_GITHUB_TOKEN }}

      - name: Run Claude Code agent
        if: steps.claim.outputs.has_issue == 'true'
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt_file: /tmp/agent-prompt.md
          working_directory: ./client-repo
          allowed_tools: 'Read,Edit,Write,Glob,Grep,Bash(npm run *:*),Bash(node:*)'
          disallowed_tools: 'Bash(git push:*),Bash(git commit:*),Bash(rm:*),WebFetch'
          max_turns: '15'
          model: claude-sonnet-4-6

      - name: Commit, push, mark done
        if: steps.claim.outputs.has_issue == 'true'
        run: python "agents/Solver - Issues/finalize.py"
        env:
          SOLVER_GITHUB_TOKEN: ${{ secrets.SOLVER_GITHUB_TOKEN }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          CMS_API_TOKEN: ${{ secrets.CMS_API_TOKEN }}
          CMS_BACKEND_URL: https://cms-backend-roman.vercel.app

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

**Note on `anthropics/claude-code-action@v1`:** Before running for real, verify the exact action name + version + parameter shape at `https://github.com/marketplace?type=actions&query=anthropics+claude+code`. The version may be `@v1`, `@v0`, or a SHA pin. Adapt as needed. If `prompt_file` isn't the parameter name, swap for `prompt: ${{ cat /tmp/agent-prompt.md }}` style or whatever the action's README specifies.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/solver-agent.yml "agents/Solver - Issues/requirements.lock" "agents/Solver - Issues/requirements-dev.lock"
git commit -m "feat(ci): solver-agent.yml workflow + locked deps"
```

---

## Task 12: Skill entry + README index

**Files:**
- Create: `.claude/skills/solver-issues/SKILL.md`
- Modify: `agents/README.md`

- [ ] **Step 1: Write SKILL.md**

Create `.claude/skills/solver-issues/SKILL.md`:

```markdown
---
name: solver-issues
description: Manual debug entry for the Solver Agent (S3). In production this agent runs via GitHub Actions cron and rarely needs manual invocation. Use this skill ONLY for local debugging when an issue keeps failing in CI and you want to replay it interactively. Trigger phrases: "Run Solver Issues agent locally for debug", "Replay solver for issue <id>".
---

# Solver — Issues (skill)

## When to invoke

Only on explicit user request. This skill is a debugging tool, not the production trigger. Production runs are scheduled via `.github/workflows/solver-agent.yml`.

User will say something like:

> "Run Solver Issues agent locally for debug"
> "Replay solver for issue 452832e0-dd7d-4330-ab37-9ead3c4c9290"

If the trigger fires without an issue id, ask which issue to replay. Do not auto-claim from production DB — that risks racing the CI cron.

## First steps

1. Read `agents/Solver - Issues/AGENTS.md` — workflow index.
2. Read `agents/Solver - Issues/LEARNINGS.md` only if `wc -l` reports more than 25 lines.
3. Confirm `agents/Solver - Issues/.env` exists with all 6 secrets. If missing, halt.
4. Activate the agent's venv (or backend's venv if you haven't set one up locally): `source backend/venv/Scripts/activate`.

## Lazy phase loading

Same convention as CMS Connector: read each phase doc only when entering that phase.

| Phase | When entering, Read |
|-------|---------------------|
| 1 | `agents/Solver - Issues/phases/1-claim.md` |
| 2 | `agents/Solver - Issues/phases/2-clone.md` |
| 3 | `agents/Solver - Issues/phases/3-solve.md` |
| 4 | `agents/Solver - Issues/phases/4-push.md` |
| 5 | `agents/Solver - Issues/phases/5-finalize.md` |

## Production trigger

GitHub Actions cron `*/15 * * * *` calls `claim_issue.py` → `clone_repo.py` → `anthropics/claude-code-action` → `finalize.py`. Manual workflow_dispatch is also supported via the Actions tab.

## Self-improvement

Append rules to `LEARNINGS.md` (per phase) when a non-transient failure mode isn't already documented. Format:

`- YYYY-MM-DD: <rule>. Triggered by: <context>.`
```

- [ ] **Step 2: Append to agents/README.md**

In `agents/README.md`, find the existing table row for `CMS Connector — Website` and add below it:

```markdown
| **Solver — Issues** | [`Solver - Issues/`](./Solver%20-%20Issues/) | [`.claude/skills/solver-issues/SKILL.md`](../.claude/skills/solver-issues/SKILL.md) | Autonomous code-fixing worker. Triggered by GitHub Actions cron every 15 min. Claims pending CMS issues (priority-ordered), runs Claude Code action against a cloned client repo, commits the fix to `cms-preview`, then routes back into the S1.5 approval flow. |
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/solver-issues/ agents/README.md
git commit -m "docs(solver): skill entry for manual debug + README index"
```

---

## Task 13: Final verification + PR

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests -v 2>&1 | tail -10
```

Expected: 167 (S1/S1.5) + 3 (admin endpoint) + 1 (slack_handler resets agent state) = 171 passed.

- [ ] **Step 2: Run full agent test suite**

```bash
cd "agents/Solver - Issues" && pytest -v 2>&1 | tail -5
```

Expected: 22 passed.

- [ ] **Step 3: Ruff check**

```bash
cd backend && source venv/Scripts/activate && ruff check auth_service/ 2>&1 | tail -3
```

Expected: clean.

```bash
cd "agents/Solver - Issues" && ruff check . 2>&1 | tail -3
```

(If ruff isn't installed in that env, skip — pre-commit handles it on commit.)

- [ ] **Step 4: List commits**

```bash
git log --oneline origin/master..HEAD
```

Expected: ~13 commits.

- [ ] **Step 5: Open PR**

YOU PAUSE HERE. Tell Stefan:
- Migration ready, NOT applied (he applies via MCP)
- 5 secrets need adding to GitHub repo (see Section 9 of spec)
- Push command ready: `git push -u origin feat/solver-agent-s3`
- After secrets + migration done, run `gh pr create --base dev --title "feat(s3): autonomous solver agent for CMS issues" --body @<descriptive>` (descriptive body should reference the spec + plan).

Do NOT push or open the PR yourself without confirmation. Stefan must:
1. Apply the DB migration via Supabase MCP.
2. Generate `CLAUDE_CODE_OAUTH_TOKEN` via `claude setup-token` on his logged-in machine.
3. Generate fine-grained PAT for client repos (contents:write).
4. Generate / reuse `CMS_API_TOKEN`.
5. Add all 5 secrets to `stefanroman22/cms-platform` → Settings → Secrets → Actions.
6. Confirm with Stefan that secrets are in place.
7. Then push + open PR.

---

## Self-Review

### Spec coverage

- DB schema (5 columns + RPC function) → Task 1.
- Backend admin endpoint → Task 2.
- S1.5 agent-state reset on revision feedback → Task 3.
- Agent folder scaffold + AGENTS.md + LEARNINGS.md + phase docs → Task 4.
- `db.py` with atomic claim + retry helpers → Task 5.
- `repo.py` with clone/push → Task 6.
- `backend_api.py` + `slack.py` HTTP clients → Task 7.
- `claim_issue.py` entrypoint + prompt builder (with Step 0 verification) → Task 8.
- `clone_repo.py` entrypoint → Task 9.
- `finalize.py` + `release_issue.py` entrypoints → Task 10.
- GitHub Actions workflow + lockfile → Task 11.
- Skill entry + README index → Task 12.
- Final verification + PR handoff → Task 13.

All success-criteria from the spec map to tests:
- Priority ordering → `test_db_claim::test_claim_uses_correct_rpc_name` (sanity) + the RPC SQL itself (verified at apply time).
- Atomic concurrent claim → relies on `FOR UPDATE SKIP LOCKED` in the RPC; no Python unit test (would require integration DB).
- Commit message format + Co-Authored-By → `test_repo::test_commit_uses_required_message_format`.
- Backend PATCH fires slack_notify → `test_admin_status_update_fires_slack_resolved`.
- Stefan ✅ → S1.5 promote → unchanged from S1.5; no regression test required here.
- Agent failure (no diff) → `test_finalize::test_empty_diff_marks_failed`.
- 3 retries → blocked → covered by `test_db_release::test_release_failed_marks_blocked_at_max`.
- Slack blocked notification → `slack.py::post_blocked_notification` (manual smoke covers).
- S1 + S1.5 unaffected → full suite re-run in Task 13 step 1.

### Placeholder scan

- No "TBD" / "TODO" remaining.
- Every code step has complete code or exact commands with expected output.
- One known-unknown: exact `anthropics/claude-code-action` parameter shape — flagged in Task 11 Step 2 with mitigation (verify against action README at apply time).

### Type / signature consistency

- `db.claim_next_issue() -> dict | None` — same shape used by `claim_issue.py` and tests.
- `db.fetch_project(project_id) -> dict` — consistent.
- `db.release_issue_failed(issue_id, error)` — keyword-positional consistent across Task 5 + Task 10.
- `db.mark_done(issue_id, *, commit_sha)` — keyword-only `commit_sha` consistent.
- `repo.clone(repo, branch, dest)` — positional, consistent in Task 6 + Task 9.
- `repo.commit_and_push(*, path, issue_id, issue_title) -> str` — keyword-only, returns SHA. Consistent in Task 6 + Task 10.
- `backend_api.trigger_issue_resolved(issue_id) -> dict` — consistent.

All consistent.
