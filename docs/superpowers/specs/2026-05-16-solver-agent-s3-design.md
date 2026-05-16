# S3 — Solver Agent (autonomous issue fixer)

**Status:** Design approved 2026-05-16
**Owner:** Stefan Roman
**Scope:** Sub-project 3 of a 4-part roadmap toward an autonomous issue-resolution agent. Builds on S1 (Slack notifications) and S1.5 (approval/revision loop).

## Roadmap context

| Sub-project | Purpose | Status |
|---|---|---|
| **S1** | Outbound Slack notifications on issue create + resolve | shipped 2026-05-15 |
| **S1.5** | Inbound Slack listener: ✅ → publish + email; thread reply → revert + store feedback | shipped 2026-05-15 |
| **S2** | Verifier sub-agent — confirms reported issue actually exists in code | deferred |
| **S3** | Solver sub-agent — auto-fix code, push to `cms-preview`, mark issue done | this spec |

S2 (verifier) is deferred as a SEPARATE workflow stage. S3's solver does prompt-level verification (Step 0 in its prompt — see "Solver prompt" section): the same agent first verifies the issue is real before attempting a fix, and exits with `Cannot reproduce: <reason>` if not. This is lightweight, single-agent-run verification. A heavier two-stage verifier+solver flow can replace this later if false-positive rate justifies the extra Claude call.

## Problem

Today, when a client submits an issue:
1. S1 posts "🆕 New Issue" to `#issues-websites`.
2. **Stefan manually fixes the code on `cms-preview` and marks the issue done.**
3. S1 fires "✅ Issue Resolved" → S1.5 awaits Stefan's ✅ → production promote + email.

Step 2 is the bottleneck. Most CMS issues are small, repetitive frontend fixes (CSS tweaks, copy changes, missing fields, broken link refs). They could be done by an LLM with file-edit access.

## Solution

A GitHub Actions cron workflow runs every 15 min. Each run:

1. Atomically claims the next actionable issue from Supabase (priority-ordered, retry-bounded).
2. Clones the client repo at `cms-preview` HEAD into the workflow workspace.
3. Spawns `anthropics/claude-code-action` with a constructed prompt and tool allowlist scoped to the cloned repo.
4. On agent success (file changes produced): commits + pushes to `cms-preview`, PATCHes backend `/admin/issues/<id>/status` → status=`done` → S1's `notify_issue_resolved` fires → S1.5 awaits Stefan's ✅.
5. On agent failure: releases the claim, increments `agent_retry_count`. After 3 failures, marks `agent_status='blocked'` and posts a Slack notification.

Authentication uses Stefan's Claude Max subscription via `CLAUDE_CODE_OAUTH_TOKEN`. Zero extra API billing.

## Architecture

```
       ┌────────────────────────┐
       │ GitHub Actions cron    │
       │ */15 * * * *           │
       │ concurrency: solver-agent (one at a time)
       └──────────┬─────────────┘
                  ▼
       ┌────────────────────────────────────────────┐
       │ workflow: solver-agent.yml                 │
       │  1. checkout main repo (this repo)         │
       │  2. setup-python 3.13 + pip cache          │
       │  3. install agents/Solver - Issues deps    │
       │  4. claim_issue.py                         │
       │  5. clone_repo.py (if has_issue)           │
       │  6. anthropics/claude-code-action          │
       │  7. finalize.py                            │
       │  8. release_issue.py (on failure())        │
       └────────────────────────────────────────────┘
```

Properties:
- **Stateless runs.** Every workflow run is cold; all state lives in Supabase.
- **One issue per run.** Bounded runtime, no priority inversion. Next cron tick picks up next.
- **Atomic lock via `FOR UPDATE SKIP LOCKED`.** Two concurrent runners pick different rows.
- **Reuses S1/S1.5 flow.** Solver's job ends at "issue done in DB via admin endpoint". Backend's existing slack_notify + slack_resolved_ts persistence picks up.
- **Quota awareness.** Anthropic 429 → action exit non-zero → workflow `failure()` step releases the claim. Next cron tick retries.

## Data model

New columns on `project_issues`:

```sql
ALTER TABLE project_issues
  ADD COLUMN agent_status TEXT NULL,           -- 'idle' | 'claimed' | 'failed' | 'blocked'
  ADD COLUMN agent_claimed_at TIMESTAMPTZ NULL,
  ADD COLUMN agent_retry_count INT NOT NULL DEFAULT 0,
  ADD COLUMN agent_last_error TEXT NULL,
  ADD COLUMN agent_commit_sha TEXT NULL;
```

- `agent_status` — solver's own state, separate from the user-facing `status`. Default NULL == treated as `idle`.
- `agent_claimed_at` — when claimed. Used to release stale claims (>15 min old).
- `agent_retry_count` — incremented on every failure. Reset to 0 when S1.5 stores fresh `revision_feedback`.
- `agent_last_error` — short text (max 500 chars).
- `agent_commit_sha` — short SHA of solver's pushed commit. For audit + Slack thread updates.

### Claim SQL

```sql
UPDATE project_issues
SET
  agent_status = 'claimed',
  agent_claimed_at = now()
WHERE id = (
  SELECT id FROM project_issues
  WHERE
    (
      (status = 'pending' AND COALESCE(agent_status, 'idle') IN ('idle', 'failed'))
      OR
      (status = 'in_progress' AND revision_feedback IS NOT NULL AND COALESCE(agent_status, 'idle') IN ('idle', 'failed'))
    )
    AND agent_retry_count < 3
    AND COALESCE(agent_status, 'idle') != 'blocked'
    AND (agent_claimed_at IS NULL OR agent_claimed_at < now() - interval '15 minutes')
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
RETURNING id, project_id, title, description, priority, status, revision_feedback;
```

Migration filename: `backend/migrations/2026_05_16_solver_agent_columns.sql`.

### Update to S1.5 handler

`slack_handler.handle_message` (revision-feedback path) must also reset agent state so the agent retries from scratch:

```python
sb.table("project_issues").update({
    "status": "in_progress",
    "revision_feedback": text,
    "revision_feedback_at": datetime.now(UTC).isoformat(),
    "agent_status": "idle",           # NEW
    "agent_retry_count": 0,           # NEW
    "agent_last_error": None,         # NEW
}).eq("id", issue["id"]).execute()
```

## Repository layout

```
agents/Solver - Issues/
├── AGENTS.md
├── LEARNINGS.md
├── .env.example
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── requirements.lock
├── requirements-dev.lock
├── main.py                 # not used by CI directly; for local debug
├── claim_issue.py          # workflow step 4
├── clone_repo.py           # workflow step 5
├── finalize.py             # workflow step 7 (success path)
├── release_issue.py        # workflow step 8 (failure path)
├── db.py                   # Supabase wrappers
├── repo.py                 # git clone / commit / push
├── backend_api.py          # PATCH /admin/issues/<id>/status
├── slack.py                # post blocked-issue notification
├── phases/                 # lazy-loaded phase docs
│   ├── 1-claim.md
│   ├── 2-clone.md
│   ├── 3-solve.md
│   ├── 4-push.md
│   └── 5-finalize.md
└── tests/
    ├── test_db_claim.py
    ├── test_db_release.py
    ├── test_repo.py
    ├── test_claim_issue.py
    └── test_finalize.py

.github/workflows/solver-agent.yml
.claude/skills/solver-issues/SKILL.md   (optional, for manual local debug invocation)
agents/README.md                         (append one row)
backend/migrations/2026_05_16_solver_agent_columns.sql
```

## GitHub Actions workflow

`.github/workflows/solver-agent.yml`:

```yaml
name: Solver Agent (S3)

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch: {}

concurrency:
  group: solver-agent
  cancel-in-progress: false

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
```

`anthropics/claude-code-action@v1` is the assumed action name; exact version + parameter shape verified during Task 1 (could be `@v1.x` or different — adapt per docs at implementation time).

## Solver prompt

`/tmp/agent-prompt.md` built by `claim_issue.py`:

```markdown
You are an autonomous code-fixing agent for a client website.

## Repository
Working directory: `./client-repo/` (already cloned at branch `cms-preview`).

## Issue submitted by client
**Title:** {issue.title}
**Priority:** {issue.priority}
**Description:**
{issue.description}

{IF revision_feedback:}
## Previous attempt was rejected
Stefan's feedback on the last fix attempt:
> {issue.revision_feedback}

Look at git log for your previous commit (most recent commit on cms-preview),
understand what you did, and address Stefan's feedback this time.
{END IF}

## Step 0 — Verify the issue is real
Before attempting any fix, explore the codebase to confirm the issue actually exists. The client describes the problem in their own words; that doesn't mean the bug is real. Reasons it may NOT be a real bug:
- The element/text the client references doesn't exist in the code.
- The behavior the client wants is already in place (client may be viewing a stale cache or the wrong site).
- The "issue" is actually a feature request that requires content-side changes the CMS already handles (not code).
- The description is ambiguous and could describe a working component.

If after a reasonable exploration (use Glob/Grep to find relevant files; Read 2-5 likely candidates) you conclude the issue is NOT a real code-level bug, write one line to `/tmp/agent-status.md`:

> Cannot reproduce: <one-sentence reason>

Then exit. The orchestrator will mark the issue as failed and Stefan reviews.

If you are unsure but the issue could plausibly be real, proceed to Step 1 and attempt a fix. False negatives (giving up on a real bug) cost more than false positives (attempting a non-bug — orchestrator detects empty diff and marks failed).

## Step 1 — Fix the issue
1. Explore the repo with Glob/Grep to find the relevant code (if not already done in Step 0).
2. Make the minimum change required to resolve the issue.
3. If you change shared components, verify other call sites still work.
4. Do NOT run npm install or modify lockfiles unless adding a dependency is required.
5. Do NOT modify CI configs, GitHub workflows, or env files.

## When you cannot fix the issue
If after exploration you cannot determine what to change, write one line to
`/tmp/agent-status.md`:

> Cannot fix: <one-sentence reason>

Then exit. The orchestrator will mark the issue as failed.

## When you finish a fix
Just exit cleanly. The orchestrator commits and pushes your changes.
Do NOT run git commit or git push yourself.
```

## Backend admin endpoint

New route in `backend/auth_service/routers/issues.py`:

```python
@router.patch("/admin/issues/{issue_id}/status", response_model=IssueOut)
async def admin_update_issue_status(
    issue_id: str,
    body: IssueStatusRequest,
    request: Request,
):
    """Admin/agent path — same effect as user-facing PATCH but auth'd via
    admin bearer token. Skips project-access ownership check — solver acts
    cross-project."""
    user = await admin_user_via_bearer_or_sid(request)
    # ... rest mirrors update_issue_status, omitting require_project_access ...
```

Auth via existing `admin_user_via_bearer_or_sid` (cookie session OR `Bearer cmsk_...` API key). Solver uses bearer with `CMS_API_TOKEN`.

A small refactor extracts the IssueOut construction from `update_issue_status` into a shared helper to avoid duplication between admin and user paths.

## Failure handling + retry

```
                  ┌─────────────────────┐
                  │ Cron tick fires     │
                  └─────────┬───────────┘
                            ▼
                  ┌─────────────────────┐
                  │ claim_issue.py      │
                  └─────────┬───────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
       has_issue=false           has_issue=true
              │                           │
              ▼                           ▼
       ┌──────────────┐         ┌────────────────────┐
       │ Exit 0       │         │ clone_repo.py      │
       │ (no work)    │         └─────────┬──────────┘
       └──────────────┘                   │
                                          ▼
                                ┌─────────────────────┐
                                │ claude-code-action  │
                                └─────────┬───────────┘
                                          │
                            ┌─────────────┴───────────────┐
                       action SUCCESS               action FAILURE
                            │                             │
                            ▼                             ▼
                  ┌─────────────────────┐    ┌─────────────────────┐
                  │ finalize.py         │    │ release_issue.py    │
                  └─────────┬───────────┘    │ (workflow failure()) │
                            │                └────────┬────────────┘
              ┌─────────────┼─────────────┐           │
              │             │             │           │
        status.md      empty diff     success         │
              │             │             │           │
              ▼             ▼             ▼           ▼
        release_failed  release_failed  mark_done   release_failed
        (gave up)       (no changes)    + commit    (action failed)
                                        + push
                                        + backend PATCH
```

### Retry budget

```python
def release_issue_failed(issue_id: str, error: str) -> None:
    sb = get_supabase_admin()
    current = sb.table("project_issues").select("agent_retry_count").eq("id", issue_id).single().execute()
    new_count = current.data["agent_retry_count"] + 1
    max_retries = int(os.environ.get("SOLVER_MAX_RETRIES", "3"))
    new_status = "blocked" if new_count >= max_retries else "failed"

    sb.table("project_issues").update({
        "agent_status": new_status,
        "agent_claimed_at": None,
        "agent_retry_count": new_count,
        "agent_last_error": error[:500],
    }).eq("id", issue_id).execute()

    if new_status == "blocked":
        _notify_blocked_to_slack(issue_id, error, new_count)
```

### Stale-claim recovery

If a workflow run crashes between claim and finalize, `agent_status='claimed'` persists. The 15-min `agent_claimed_at` window in the claim SQL means the next run re-claims the issue and tries again. `agent_retry_count` is NOT incremented on stale-claim re-claim (we never recorded a failure).

### Blocked notification format

```
🛑 Agent gave up — [Acme Site]
*Title:* Hero image broken on mobile
*Tried:* 3 times
*Last error:* agent produced no file changes

This issue needs manual attention.
```

Posted top-level to `#issues-websites` (no thread to reply to — the issue has no `slack_resolved_ts` yet).

## Configuration + secrets

| Secret | Source | Purpose |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude setup-token` on logged-in machine | Claude Code subscription auth |
| `SUPABASE_URL` | `backend/.env` | DB read/write |
| `SUPABASE_SERVICE_ROLE_KEY` | `backend/.env` | Bypass RLS for atomic claim |
| `SOLVER_GITHUB_TOKEN` | new fine-grained PAT, `contents:write` on client repos | Clone + push |
| `CMS_API_TOKEN` | new admin API key from backend | PATCH `/admin/issues/<id>/status` |

No new Vercel envs.

Deploy ordering:
1. Apply DB migration via Supabase MCP.
2. Generate `CLAUDE_CODE_OAUTH_TOKEN`, fine-grained PAT, admin API key.
3. Add 5 secrets to GitHub repo.
4. Merge PR → backend deploys new admin endpoint.
5. Manually trigger workflow via `workflow_dispatch` to validate wiring.

## Error handling matrix

| Stage | Failure | Behavior |
|---|---|---|
| `claim_issue.py`: DB connection | RuntimeError raised | Workflow fails, no claim made. Next cron tick retries. |
| `clone_repo.py`: PAT 403 | RuntimeError, action fails | `release_issue_failed` increments retry. Likely PAT scope drift — Stefan investigates. |
| `claude-code-action`: 429 / quota exhausted | non-zero exit | `release_issue_failed` (will retry on next cron tick when quota replenishes). |
| `claude-code-action`: agent hits max_turns | Exits with no diff | `finalize.py` detects empty diff → `release_issue_failed("no file changes")`. |
| `finalize.py`: git push 403 | RuntimeError | `release_issue_failed("git push 403")`. Likely PAT scope drift. |
| `finalize.py`: backend PATCH 5xx | log + exit 0 | Commit is durable. Slack post + status update missed. Manual sync via dashboard. |
| Workflow timeout (25 min) | Job killed | `agent_status='claimed'` stuck. Next run sees stale claim, re-claims. |

## Testing

### Unit — `agents/Solver - Issues/tests/`

**`test_db_claim.py`** — atomic claim
- Returns highest-priority pending issue.
- Skips `blocked`.
- Picks `agent_claimed_at < now() - 15min` (stale-claim recovery).
- Skips `agent_retry_count >= 3`.
- Picks `in_progress` issues with `revision_feedback IS NOT NULL`.
- Priority ordering: High before Medium before Low; same priority → oldest first.

**`test_db_release.py`** — retry counter
- `release_issue_failed` increments retry_count, sets `failed` when count < max.
- 3rd failure → `blocked` + triggers `_notify_blocked_to_slack`.
- `mark_done(commit_sha)` writes `agent_commit_sha` + clears `agent_status` to `idle`.

**`test_repo.py`** — git ops
- Clone uses `--depth 50 --branch cms-preview`.
- Commit message format: `fix: <title>\n\nAutomated fix by Solver Agent...`.
- Git user is `solver@roman-technologies.dev`.

**`test_claim_issue.py`** — orchestrator entry
- No actionable issue → `has_issue=false` in GITHUB_OUTPUT, no temp files.
- Actionable issue → writes `/tmp/issue.json` + `/tmp/agent-prompt.md` + sets 4 outputs.
- Prompt template embeds revision_feedback when present.
- Prompt template omits revision_feedback section when None.

**`test_finalize.py`**
- `/tmp/agent-status.md` with "Cannot reproduce: ..." → `release_issue_failed("Cannot reproduce: ...")`, never pushes (verification-fail path).
- `/tmp/agent-status.md` with "Cannot fix: ..." → `release_issue_failed("Cannot fix: ...")`, never pushes (gave-up path).
- Empty diff → `release_issue_failed("agent produced no file changes")`, never pushes.
- Happy path → commits + pushes + `mark_done` + backend PATCH.
- Backend PATCH 5xx → log + exit 0.

### Backend — additions to `test_issues_router.py`

- `test_admin_status_update_requires_bearer` — no token → 401.
- `test_admin_status_update_fires_slack_resolved` — valid bearer + `status=done` → calls `notify_issue_resolved`, persists `slack_resolved_ts`.
- `test_admin_status_update_skips_when_already_done` — old_status=`done` → no Slack call.

### Workflow validation

YAML lint via existing tooling (manual review if not automated).

### Manual smoke (post-deploy)

1. **Empty queue cold start** — manual `workflow_dispatch` → `claim_issue.py` outputs `has_issue=false`, workflow exits 0 in ~30s.
2. **Real simple fix** — submit "Change footer year 2024 → 2026" issue. Run workflow. Expected: agent commits + pushes, S1 "Issue Resolved" Slack post arrives, ✅ react triggers S1.5 promote + email.
3. **Hard issue, agent gives up** — submit vague/nonsense issue. Run workflow. Expected: agent writes `/tmp/agent-status.md`, retry_count=1, `agent_status='failed'`. Next cron tick re-attempts. After 3 attempts → `blocked` + Slack notification.
4. **Non-existent bug (verification fail)** — submit "Remove the [thing that doesn't exist in the code]". Run workflow. Expected: agent verifies via Glob/Grep, finds no matching code, writes `Cannot reproduce: <element> not present in codebase` to `/tmp/agent-status.md`, exits. `finalize.py` marks failed with that reason. After 3 such attempts → `blocked`.

### Coverage

`agents/Solver - Issues/` excluded from backend coverage report. Agent tests run in their own CI job, mirroring the CMS Connector convention.

## Out of scope (deferred)

- **S2 verifier** — pre-check whether issue is real before invoking solver.
- **Model escalation** — automatically retry with Opus 4.7 after Sonnet 4.6 fails. Adds complexity; defer until needed.
- **Per-project tool allowlists** — currently one allowlist for all client repos.
- **`npm install` permission** — solver cannot add new dependencies. If a fix legitimately requires one, agent writes "Cannot fix: requires new dependency" to status.md.
- **Slack "retry" thread reply** — manual reset of `agent_retry_count` via thread message. Stefan unblocks via dashboard / SQL for now.
- **Cost telemetry** — track per-issue token usage. Add later if quota becomes a concern.

## Success criteria

- A pending issue with priority `High` is picked up by the next cron tick before any `Medium` or `Low` issue.
- Two concurrent workflow runs do not work the same issue (atomic claim).
- Agent makes file changes → commit lands on `cms-preview` with `Co-Authored-By` line citing the agent.
- Backend `/admin/issues/<id>/status` PATCH fires S1 "Issue Resolved" Slack post with the agent's commit SHA in context.
- Stefan ✅ → S1.5 promotes to production → email lands.
- Agent failure (no diff, action error, 429) → issue back to `failed`, retry_count incremented.
- After 3 failures → `blocked` + Slack notification posted to `#issues-websites`.
- All new unit + integration tests pass in CI.
- S1 + S1.5 flows unaffected (no regressions in existing 167 tests).

## Open questions

None — all resolved during brainstorm.
