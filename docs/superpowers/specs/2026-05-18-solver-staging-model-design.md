# Solver Agent — Staging-Branch Model + Visibility Pass

**Status:** Design approved 2026-05-18
**Owner:** Stefan Roman
**Scope:** Architectural rework of the Solver Agent (S3) to (a) treat `cms-preview` as a real staging branch instead of a solver-owned sandbox, (b) honor `repository_dispatch` payloads so the right issue gets claimed, and (c) close every silent failure mode so the Slack channel reflects every exit path. Covers edge case clusters A (silent failures), B (queue/dispatch mismatch), C (staging integrity), E (agent prompt gaps), and G (Slack message lifecycle).

## Roadmap context

| Sub-project | Purpose | Status |
|---|---|---|
| **S1** | Outbound Slack notifications on issue create + resolve | shipped 2026-05-15 |
| **S1.5** | Inbound Slack listener: ✅ → publish + email; thread reply → revert + store feedback | shipped 2026-05-15 |
| **S3** | Solver sub-agent — auto-fix code, push to `cms-preview`, mark issue done | shipped 2026-05-16, hardened 2026-05-17 |
| **S3.5** | **This spec** — staging-branch model + visibility pass | designed 2026-05-18 |

S3.5 is a hardening pass on S3. It does not change the high-level workflow (cron + dispatch → claim → clone → claude → finalize → Slack), but it shifts the underlying model from "solver-owned ephemeral cms-preview" to "solver-aware real staging" and closes the silent-failure paths that were never wired up to Slack.

## Problem

After running S3 in production for ~36 hours, three classes of symptom appeared:

1. **Agent rejects valid issues against the wrong source-of-truth.** The clone step hard-resets `cms-preview` → `origin/{prod_branch}` before the agent reads any code (see [`repo.py:76`](../../agents/Solver - Issues/repo.py#L76)). When the bug genuinely lives on staging but not yet on prod (manual edits, unapproved solver fixes, deployment lag), the agent reads prod state, finds the bug "already fixed", writes `/tmp/agent-status.md`, and exits. Repeated for the same issue across all retries.

2. **New issues are starved by old failing issues.** `repository_dispatch` carries `client_payload.issue_id` from `solver_dispatch.dispatch_solver_tick`, but [`claim_issue.py`](../../agents/Solver - Issues/claim_issue.py) ignores the payload and runs the priority-ordered queue function. A High-priority issue at `retry_count=2` always wins over a freshly-submitted High-priority issue (older `created_at`). The newly-submitted issue waits behind ~3 dispatches before the failing one hits `blocked` and frees the queue.

3. **Silent failure paths.** Three branches in [`finalize.py`](../../agents/Solver - Issues/finalize.py) exit success without any Slack notification: agent rejection (`status_md` exists), agent no-diff (CLI exit 0 with no file changes), and backend trigger failure. The user submits an issue, sees the workflow turn green, and never hears anything back. They have no way to tell "fix succeeded" from "agent declined to act" from "system error" without reading the workflow logs.

A force-push model (`git push --force-with-lease origin HEAD` on top of the reset-to-prod base) compounds (1) by silently overwriting any cms-preview state that wasn't authored by the solver itself.

## Solution overview

Three foundational shifts, plus mechanical follow-on changes:

1. **`cms-preview` is treated as a real staging branch.** The solver clones cms-preview at its current HEAD without resetting. Push is plain `git push origin HEAD` (no `--force-with-lease`). When push is rejected because cms-preview moved during the run, the workflow fails loudly with a Slack admin error rather than overwriting concurrent work.

2. **Dispatch is targeted; cron stays queue-driven.** A new RPC `claim_specific_solver_issue(uuid)` enforces the same eligibility rules as the existing claim function but for one specific id. [`claim_issue.py`](../../agents/Solver - Issues/claim_issue.py) reads `DISPATCH_ISSUE_ID` from the workflow env (sourced from `github.event.client_payload.issue_id`) and claims that issue directly. If the targeted issue is no longer eligible (already done, claimed by a concurrent run, or maxed retries), claim falls back to the existing queue function so the run still does useful work. Cron + manual `workflow_dispatch` skip the payload path entirely.

3. **Every exit path produces a Slack signal.** Schema gains `slack_created_ts` (mirrors `slack_resolved_ts`); `create_issue` persists it after `notify_issue_created` returns. A new backend route `POST /admin/issues/{id}/agent-event` accepts `{kind, reason}` and posts a thread reply on `slack_created_ts`. [`finalize.py`](../../agents/Solver - Issues/finalize.py) calls this on the four formerly-silent branches: agent-rejected, agent-crashed (CLI exit ≠ 0), no-diff, backend-trigger-failed. The `Release on failure` workflow step (which runs on prior-step crashes like clone failures) also calls the new endpoint.

Stefan's ❌-rejection lifecycle (his Slack response to a "✅ Resolved" message that wasn't actually good enough) is unchanged at the handler level: it still sets `revision_feedback` and triggers a solver-tick dispatch. The bad solver commit **stays at cms-preview HEAD** rather than being reverted server-side. The agent's revision-feedback prompt is reworded to acknowledge this: "Your last attempt is HEAD on this branch. Stefan said: {feedback}. Decide: amend with a better fix on top, or revert + retry."

## Architecture

```
                ┌─────────────────────────────────┐
                │ user POST /projects/X/issues    │
                └───────────────┬─────────────────┘
                                ▼
        ┌───────────────────────────────────────────────┐
        │ create_issue (issues.py)                      │
        │  1. insert project_issues row                 │
        │  2. notify_issue_created → ts                 │
        │  3. UPDATE project_issues                     │
        │       SET slack_created_ts = ts  ◄── NEW      │
        │  4. dispatch_solver_tick(issue_id) ───┐       │
        └───────────────────────────────────────┼───────┘
                                                │ client_payload.issue_id
                                                ▼
        ┌───────────────────────────────────────────────┐
        │ workflow: solver-agent.yml                    │
        │  env: DISPATCH_ISSUE_ID = client_payload.id   │
        └───────────────┬───────────────────────────────┘
                        ▼
        ┌──────────────────────────────────────┐
        │ claim_issue.py                       │
        │  if DISPATCH_ISSUE_ID:               │
        │    issue = claim_specific_issue(id)  │  ◄── NEW
        │    if issue is None:                 │
        │      issue = claim_next_issue()      │  fallback
        │  else:                               │
        │    issue = claim_next_issue()        │  cron path
        └───────────────┬──────────────────────┘
                        ▼
        ┌───────────────────────────────────────────┐
        │ clone_repo.py + repo.py                   │
        │  clone_at_preview_head:                   │
        │    git clone --branch cms-preview         │  ◄── no reset
        │    (PREV_SHA = current HEAD)              │
        └───────────────┬───────────────────────────┘
                        ▼
        ┌────────────────────────────────────┐
        │ Run Claude headless                │
        │  capture exit code → $GITHUB_OUTPUT│  ◄── no continue-on-error
        └───────────────┬────────────────────┘
                        ▼
        ┌─────────────────────────────────────────────────────────┐
        │ finalize.py                                             │
        │                                                         │
        │  if status_md exists:                                   │
        │    notify_agent_event(kind="rejected", reason=...)      │  ◄── NEW
        │    release_issue_failed                                 │
        │  elif claude_exit_code != 0:                            │  ◄── NEW
        │    notify_agent_event(kind="agent_crashed", reason=...) │
        │    release_issue_failed                                 │
        │  elif not has_diff:                                     │
        │    notify_agent_event(kind="no_diff", reason="...")     │  ◄── NEW
        │    release_issue_failed                                 │
        │  else:                                                  │
        │    commit_and_push (plain push)                         │  ◄── no --force
        │    mark_done                                            │
        │    trigger_issue_resolved (3× retry)                    │  ◄── retry
        │    if all retries fail:                                 │
        │      notify_agent_event(kind="backend_error", ...)      │
        └─────────────────────────────────────────────────────────┘
```

## Components changed

### Backend (`backend/auth_service/`)

- **`routers/issues.py`**
  - `create_issue`: capture ts returned by `notify_issue_created`; UPDATE row to persist `slack_created_ts`.
  - Add `POST /admin/issues/{id}/agent-event`: accepts `AgentEventRequest`, looks up `slack_created_ts`. If present, calls `slack_notify.notify_agent_event` to post a thread reply. If NULL (because `notify_issue_created` failed at create time), gracefully degrades to a top-level post with project name + issue title for context. Returns the resulting Slack ts. 404 only if the issue id itself doesn't exist.

- **`services/slack_notify.py`**
  - Add `notify_agent_event(thread_ts, kind, reason, project, issue) -> str | None`. Internally wraps `post_thread_reply` with kind-specific emoji + format. Swallows errors like sibling functions.

- **`models/schemas.py`**
  - Add `AgentEventRequest` Pydantic model: `kind: Literal["rejected", "no_diff", "agent_crashed", "backend_error"]`, `reason: str` (max 500 chars — matches existing `_MAX_ERROR_LEN` slice in `db.release_issue_failed`).

- **`services/solver_dispatch.py`**
  - Wrap GH dispatch call in try/except; on failure log + post a Slack admin error message to the issues channel (top-level, since the dispatch is the primary trigger and a silent failure here means the user gets no signal at all).

- **`services/slack_handler.py`** — unchanged.

### Database (`backend/migrations/2026_05_18_solver_visibility.sql`)

```sql
-- 1. Slack ts for thread replies from agent-event notifications
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

### Solver agent (`agents/Solver - Issues/`)

- **`repo.py`**
  - Rename `clone_and_reset_to_prod` → `clone_at_preview_head`. Drop the `prod_branch` reset (line 76). `PREV_SHA_PATH` now stores the cms-preview HEAD at clone time (used for diff-back-from-attempt hints in revision-feedback retries; no longer the orphan-recovery hack).
  - `commit_and_push`: replace `--force-with-lease` with plain `git push origin HEAD`. On push rejection, raise a distinct `PushRejectedError` so finalize.py can route to the right Slack event.

- **`clone_repo.py`**
  - Update call signature (drops `prod_branch` argument). Log line becomes `"cloned {repo}: cms-preview HEAD = {sha[:7]}"`.

- **`claim_issue.py`**
  - Read `os.environ.get("DISPATCH_ISSUE_ID")`. If non-empty: call new `db.claim_specific_issue(id)`; if that returns None, fall through to `db.claim_next_issue()`. Otherwise just call `db.claim_next_issue()`.
  - Prompt builder: rework the revision-feedback section to acknowledge that the prior attempt lives at `cms-preview` HEAD, not as an orphaned object. Wording: *"Your previous attempt is the HEAD commit on this branch. Stefan's rejection feedback: {feedback}. Decide whether to amend (commit a fix on top) or revert (git revert HEAD, then write the correct fix)."*
  - Prompt builder: add a "Source of truth" note: *"You are reading the CURRENT state of `cms-preview`, which IS the staging branch. Not production. If the bug describes staging behavior, you should see it in this code."*
  - Prompt builder: extend Step 0 rejection categories — when rejecting as "wrong layer (content not code)", agent must name the dashboard tab where the user should make the change.

- **`db.py`**
  - Add `claim_specific_issue(issue_id: str) -> dict | None` calling the new RPC.

- **`finalize.py`**
  - Read `CLAUDE_EXIT_CODE` from env (set by workflow step output).
  - Restructure the decision tree:
    1. `status_md` exists → `notify_agent_event(kind="rejected", reason=status_md_content[:500])`, `release_issue_failed`, exit 0.
    2. `claude_exit_code != 0` → `notify_agent_event(kind="agent_crashed", reason=f"CLI exit {code} — see workflow logs")`, `release_issue_failed`, exit 0.
    3. `not has_diff` → `notify_agent_event(kind="no_diff", reason="Agent ran to completion but produced no file changes and no status.md — likely the agent forgot to write a reject reason before exiting")`, `release_issue_failed`, exit 0.
    4. Otherwise (happy path): `commit_and_push` → `mark_done` → `trigger_issue_resolved` (with retry wrapper). On final retry failure → `notify_agent_event(kind="backend_error", reason=...)` via direct-Slack fallback, exit 0 (the push happened).
    5. On `PushRejectedError` from `commit_and_push` → `notify_agent_event(kind="backend_error", reason="cms-preview moved during run; local commit lost (runner workspace is ephemeral). Re-trigger the workflow after staging stabilizes.")`, then **re-raise**. The `Release on failure` step handles `release_issue_failed` — do NOT call it from finalize.py on this path or the retry counter increments twice.

- **`backend_api.py`**
  - Add `notify_agent_event(issue_id, kind, reason)`: POST to `/admin/issues/{id}/agent-event`. Best-effort; log on failure but do not raise.
  - Wrap `trigger_issue_resolved` body with 3-try exponential backoff (1s/2s/4s). 4xx errors are not retried (likely permission/bug — fail fast).

- **`slack.py`**
  - Add `post_thread_event_direct(thread_ts, kind, reason)`: direct chat.postMessage thread reply, used only as the fallback when the backend itself is the failing target. Same channel + token mechanism as the existing `post_blocked_notification`.

- **`release_issue.py`**
  - When called from `Release on failure` workflow step (prior-step crash like clone failure OR finalize.py re-raise on push rejection), additionally call `backend_api.notify_agent_event(kind="agent_crashed", reason=f"workflow step failed: {failed_step}")` so failures are visible in Slack, not just bumping the retry counter silently.
  - **De-dup guard:** check for the existence of `/tmp/agent-event-emitted` marker file before posting. `finalize.py` writes this marker after a successful `notify_agent_event` call so `release_issue.py` does NOT post a second message on the push-rejected path (where finalize already emitted the backend_error event before raising).

### Agent documentation (`agents/Solver - Issues/`)

- **`AGENTS.md`** — update three sections to reflect the new model:
  - "Pipeline" table row 2 ("Clone"): change goal from *"Clone + reset `cms-preview` to production HEAD; save prev SHA"* to *"Clone `cms-preview` at its current HEAD; save prev SHA for revision-feedback context"*.
  - "Failure-mode taxonomy" table: add rows for `agent_rejected → Slack thread reply`, `agent_crashed → Slack thread reply + retry`, `push_rejected → Slack thread reply + workflow fails`. Remove the "Backend PATCH 5xx → log + exit 0" silent-failure entry (no longer silent).
  - "Hard rules" section: rewrite the bullet about cms-preview being reset. New wording: *"`cms-preview` is now a real staging branch. The solver clones it at HEAD without resetting and pushes plain (no `--force`). Direct edits to cms-preview by Stefan or anyone else are preserved. If a push conflicts, the workflow fails loudly rather than overwriting."*
  - "Modifying this agent" section: replace the line referencing `clone_and_reset_to_prod` with the new function name `clone_at_preview_head`.

- **`phases/2-clone.md`** — rewrite to describe `clone_at_preview_head` (no reset). Drop the "save prev SHA for orphan recovery" rationale; replace with "save prev SHA as anchor for revision-feedback diff context."

- **`phases/4-push.md`** — rewrite to describe plain `git push origin HEAD` (no `--force-with-lease`). Add a "Failure mode: push rejected" subsection pointing to the new Slack event flow.

- **`phases/5-finalize.md`** — rewrite the decision tree section to match the new 5-branch structure (status_md / claude_exit_code / no_diff / happy / push_rejected). Add explicit references to each `notify_agent_event` kind.

### Workflow (`.github/workflows/solver-agent.yml`)

- "Claim next issue" step: add env `DISPATCH_ISSUE_ID: ${{ github.event.client_payload.issue_id }}`.
- "Run Claude headless" step:
  - Remove `continue-on-error: true`.
  - Wrap the `claude --print …` call to capture exit code: `claude ... < /tmp/agent-prompt.md || EXIT_CODE=$?; echo "exit_code=${EXIT_CODE:-0}" >> $GITHUB_OUTPUT`.
  - Step `id: claude` so finalize step can read `${{ steps.claude.outputs.exit_code }}`.
- "Commit, push, mark done" step: add env `CLAUDE_EXIT_CODE: ${{ steps.claude.outputs.exit_code }}`.

## Data flow — happy path

```
1. user POST /projects/laurian-duma-portfolio/issues
   {title: "Change color of header text", priority: "High", description: "..."}

2. create_issue:
   - INSERT project_issues row → id 6b786aa1...
   - notify_issue_created → Slack post ts="1715865123.456789"
   - UPDATE project_issues SET slack_created_ts='1715865123.456789' WHERE id=6b786aa1...
   - dispatch_solver_tick({issue_id: '6b786aa1...'})

3. GitHub fires workflow with client_payload.issue_id=6b786aa1...

4. claim_issue.py:
   - DISPATCH_ISSUE_ID=6b786aa1...
   - claim_specific_issue(6b786aa1...) → row (id, project_id, title, ...)
   - writes /tmp/issue.json
   - GITHUB_OUTPUT: has_issue=true, issue_id=6b786aa1...

5. clone_repo.py:
   - clone_at_preview_head(repo_slug='stefanroman22/Laurian-Duma...', dev_branch='cms-preview', dest='./client-repo')
   - clone --branch cms-preview --depth 50, no reset
   - PREV_SHA_PATH = cms-preview HEAD sha

6. claude --print ... runs against ./client-repo (current staging state). Makes edit, exits 0.

7. finalize.py:
   - status_md absent ✓
   - claude_exit_code=0 ✓
   - has_diff=true ✓
   - commit_and_push → sha 'abc123'
   - mark_done(issue_id, commit_sha='abc123')
   - trigger_issue_resolved(6b786aa1...) → backend admin endpoint:
     - status='done', notify_issue_resolved → Slack post ts="1715865456.123456"
     - UPDATE project_issues SET slack_resolved_ts='1715865456.123456'

8. user sees in Slack:
   #issues-websites
   🆕 New Issue — Laurian Duma Portfolio
   "Change color of header text" ...
   ─────────────────────
   ✅ Issue Resolved — Laurian Duma Portfolio
   Title: Change color of header text
   Resolved by: solver@roman-technologies.dev
   Preview: https://laurian-duma-cms-preview.vercel.app
   [Open Preview]  [Open in CMS]
```

## Data flow — sad paths (all now visible in Slack)

### Agent rejects after Step 0 verification

```
finalize.py:
  status_md = "Cannot reproduce: Header.tsx:89-96 already renders logo before text"
  notify_agent_event(
    kind="rejected",
    reason="Cannot reproduce: Header.tsx:89-96 already renders logo before text"
  )
  release_issue_failed(issue_id, status_md)

user sees in Slack:
  🆕 New Issue — Laurian Duma Portfolio   [top-level, existing]
  ↳ 🤔 Agent reviewed, no change — reason: Cannot reproduce: Header.tsx:89-96 already renders logo before text   [thread reply]
```

### Agent CLI crashed (exit ≠ 0, no status.md)

```
finalize.py:
  status_md absent
  claude_exit_code = 1  (e.g., OAuth token expired, max-turns reached, internal error)
  notify_agent_event(
    kind="agent_crashed",
    reason="CLI exit 1 — see workflow logs: https://github.com/.../actions/runs/{N}"
  )
  release_issue_failed(issue_id, "CLI exit 1")

user sees in Slack:
  🆕 New Issue — Laurian Duma Portfolio   [top-level, existing]
  ↳ ⚠️ Agent CLI crashed (exit 1). Logs: <workflow url>   [thread reply]
```

### No-diff (CLI exit 0 but no file changes and no status.md)

```
finalize.py:
  status_md absent
  claude_exit_code = 0
  has_diff = false
  notify_agent_event(
    kind="no_diff",
    reason="Agent ran to completion but produced no file changes. This usually means it forgot to write status.md before exiting."
  )
  release_issue_failed(issue_id, "no file changes")

user sees in Slack:
  🆕 New Issue — Laurian Duma Portfolio   [top-level, existing]
  ↳ ⚠️ Agent produced no file changes and didn't write a reject reason — treating as failed attempt   [thread reply]
```

### Backend trigger fails after successful push

```
finalize.py:
  push successful, sha=abc123
  mark_done OK
  trigger_issue_resolved retry 1 → 500 (1s sleep)
  trigger_issue_resolved retry 2 → 500 (2s sleep)
  trigger_issue_resolved retry 3 → 500
  → all retries failed; fall back to direct Slack:
  slack.post_thread_event_direct(
    thread_ts=slack_created_ts,   # fetched via supabase select before retry loop
    kind="backend_error",
    reason="Fix pushed (sha abc123) but backend mark-done failed after 3 retries: HTTP 500. Manually run: curl -X PATCH .../admin/issues/{id}/status -d '{\"status\":\"done\"}'"
  )
  exit 0  (commit is durable)

user sees in Slack:
  🆕 New Issue — Laurian Duma Portfolio   [top-level, existing]
  ↳ 🛑 Fix pushed (abc123) but backend mark-done failed. Manual recovery needed. <details>   [thread reply]
```

### Push rejected (cms-preview moved during run)

```
finalize.py:
  commit_and_push raises PushRejectedError
  notify_agent_event(
    kind="backend_error",
    reason="cms-preview moved during run; local commit lost (runner workspace is ephemeral). Re-trigger the workflow after staging stabilizes."
  )
  re-raise (workflow exits non-zero)
  → Release on failure step runs → release_issue.py → release_issue_failed (single retry increment)

user sees in Slack:
  🆕 New Issue — Laurian Duma Portfolio   [top-level, existing]
  ↳ 🛑 cms-preview moved during run; local commit lost. Re-trigger workflow after staging stabilizes.   [thread reply]
```

### Clone failed (repo missing, token expired, etc.)

```
release_issue.py (from Release on failure step):
  failed_step = "Clone client repo"
  backend_api.notify_agent_event(
    kind="agent_crashed",
    reason=f"workflow step failed: {failed_step}"
  )
  release_issue_failed

user sees in Slack:
  🆕 New Issue — Laurian Duma Portfolio   [top-level, existing]
  ↳ ⚠️ Workflow step failed: Clone client repo — see logs   [thread reply]
```

## Error handling policy

| Failure | Retry | Slack | Workflow exit |
|---|---|---|---|
| `trigger_issue_resolved` 5xx | 3× exp backoff (1s/2s/4s) | If all fail → direct Slack thread reply (kind=backend_error) | 0 (commit is durable) |
| `trigger_issue_resolved` 4xx | None (likely bug/permission) | Direct Slack thread reply | non-zero |
| `notify_agent_event` POST fails | None | Log + swallow | continues |
| Slack chat.postMessage fails | None | Log + swallow | continues |
| `git push origin HEAD` rejected | None | `notify_agent_event(kind=backend_error)` with rebase hint | non-zero |
| Claude CLI exit ≠ 0 | None | `notify_agent_event(kind=agent_crashed)` | continues to finalize |
| `clone_at_preview_head` raises | None | `notify_agent_event(kind=agent_crashed)` via release_issue.py | non-zero (existing) |

## Edge case coverage matrix

Lists each in-scope edge case from the audit and the specific change that resolves it.

| # | Cluster | Case | Resolved by |
|---|---|------|---|
| 1 | A | Agent rejects → silent | `notify_agent_event(kind="rejected")` in finalize.py |
| 2 | A | Agent no-diff/crash → silent | Split into `agent_crashed` (exit≠0) and `no_diff` (exit=0+no-diff) |
| 3 | A | Backend trigger fails → silent | 3× exp backoff + direct-Slack fallback |
| 4 | A | `notify_issue_created` fails | Pre-existing log-and-swallow retained; user can re-submit |
| 5 | A | `dispatch_solver_tick` fails | Slack admin alert added in `solver_dispatch.py` except block |
| 6 | A | Clone crashes → silent until blocked | `release_issue.py` calls `notify_agent_event(kind="agent_crashed")` |
| 7 | B | Dispatch payload ignored | `DISPATCH_ISSUE_ID` env + `claim_specific_issue` |
| 8 | B | Failed issue starves newer | Targeted dispatch bypasses queue; cron-only starvation ≤ 1 hour |
| 10 | C | Hard reset wipes edits | `clone_at_preview_head` (no reset) |
| 11 | C | Force-push wipes intentional state | Plain push + fail-loud on rejection |
| 12 | C | Stefan ✅ → FF fails → silent loss | No regression — existing slack_handler error response unchanged |
| 13 | C | PREV_SHA_PATH GC risk | Obsolete — prior attempts live in cms-preview history |
| 19 | E | Agent reads prod state | Solved by model B (cms-preview is real staging) |
| 21 | E | "Content not code" rejections have no hint | Prompt addition: name the dashboard tab |
| 27 | G | No slack_created_ts → no threading | Added as column + persisted in `create_issue` |

## Out of scope

Deferred to follow-up specs:

- **D — Repo edge cases**: LFS, submodules, `--depth 50` insufficient for old SHAs, untracked-file detection in `has_diff`, whitespace-only commit detection.
- **F — Issue lifecycle races**: PATCH to issue while solver is running, retry-counter reset semantics on Stefan ❌, stuck `in_progress` with no `revision_feedback`.
- **H — Observability**: dashboard view of blocked issues, per-exit-path metrics, retry-counter reset UI.
- **I — Cleanup**: blocked-issue auto-archive, `slack_processed_events` GC.
- **E.20 — Vercel deploy lag awareness**: requires Vercel API token + project lookup; not in scope.
- **E.22 — Write tool path scoping**: security hardening; runner is ephemeral so impact is limited.
- **E.23 — Test-thrash budget**: would need per-step turn limits in CLI; not currently exposed.
- **G.28 — Stale "✅ Resolved" on re-open**: needs message-update flow; rare in practice.
- **B.9 — Priority bump UI**: frontend work; deferred until needed.

## Testing

New / updated tests:

- **`agents/Solver - Issues/tests/test_finalize.py`** — table-test each finalize.py branch: rejected, agent_crashed, no_diff, happy, backend_error (mock requests, verify the right `notify_agent_event` kind is called).
- **`agents/Solver - Issues/tests/test_claim.py`** — `DISPATCH_ISSUE_ID` honored when targeted issue is eligible; falls back to queue when ineligible (already done, claimed, blocked); cron path unchanged.
- **`agents/Solver - Issues/tests/test_repo.py`** — `clone_at_preview_head` does not reset; `commit_and_push` plain push; `PushRejectedError` raised on simulated push rejection.
- **`backend/auth_service/tests/test_issues_router.py`** — new `agent-event` route: each `kind` formats correctly; thread_ts lookup; 404 if issue missing; 404 if `slack_created_ts` missing.
- **`backend/auth_service/tests/test_slack_notify.py`** — `notify_agent_event` posts to thread, returns ts, swallows API errors.
- **Integration test (manual)** — submit issue → verify dispatch payload sets DISPATCH_ISSUE_ID → verify targeted claim hits the right id → verify all 4 sad paths produce the right Slack thread reply.

## Migration / rollout

**Strict ordering — each step must complete before the next:**

1. **Migration first**: land `2026_05_18_solver_visibility.sql` via MCP. Column add is backward-compatible (NULL allowed); RPC creation is additive. Zero risk to existing code.
2. **Backend PR second**: issues.py + slack_notify.py + schemas.py + solver_dispatch.py + AGENTS.md/phases updates that document state but don't change runtime. Old solver agents continue working (they don't call the new endpoint yet).
3. **Solver PR third** (must wait for backend to be deployed to prod): repo.py + claim_issue.py + finalize.py + backend_api.py + slack.py + clone_repo.py + release_issue.py + workflow yml. The new solver's `notify_agent_event` POST is best-effort (swallows errors), but if it lands before backend deploys, every solver run during the gap will silently lose Slack notifications — defeating half the value of this work. Confirm backend is live (`curl https://cms-backend-roman.vercel.app/admin/issues/.../agent-event` returns 401 or 422, not 404) before merging the solver PR.
4. **Smoke test**: submit one issue per project, verify happy path. Submit one issue with intentionally-wrong description (something the agent will reject), verify thread reply appears under "New Issue".

No data backfill needed — `slack_created_ts` populates on next issue submission. The currently-stuck `25d37190` issue (IT Global "header change", retry=2) won't auto-recover from this change; manual reset documented in "Open follow-ups" below.

## Open follow-ups (track separately)

- **One-off cleanup of stuck issue `25d37190` (IT Global "header change", retry=2):** manually run the SQL to set `agent_status='blocked'` (or reset `agent_retry_count=0` if Stefan wants the agent to try once more after the staging-model fix lands).
- **Backfill `slack_created_ts` for in-flight issues?** Probably not worth it — only one issue is currently mid-lifecycle (`6b786aa1` Laurian "Change color of header text" still `pending`).
