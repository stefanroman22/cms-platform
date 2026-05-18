# Solver — Issues Agent (S3)

Authoritative spec for **this agent only**. Each agent owns its own AGENTS.md.

> Skill entry: [`.claude/skills/solver-issues/SKILL.md`](../../.claude/skills/solver-issues/SKILL.md)
> Self-improvement log: [`LEARNINGS.md`](./LEARNINGS.md)
> Per-phase detail: [`phases/`](./phases/)

---

## Trigger

Primary trigger: `repository_dispatch` event of type `solver-tick`. The backend (`backend/auth_service/services/solver_dispatch.py`) fires this immediately after a client submits a new issue, so the solver runs within ~30s of submission.

Safety-net trigger: hourly cron (`7 * * * *`, off-peak minute) catches issues whose dispatch failed silently (token expired, GitHub API blip), retry queue, stale claims, and manual DB inserts that bypass the API.

Manual trigger: `workflow_dispatch` from the GitHub Actions UI for ad-hoc testing.

Local skill invocation:

> "Run Solver Issues agent locally for debug"

The local skill replays a single workflow step against a real claimed issue. Not used in production.

## Pipeline (strict order)

| # | Phase | Doc | Goal |
|---|-------|-----|------|
| 1 | Claim | [phases/1-claim.md](./phases/1-claim.md) | Atomic priority-ordered claim from Supabase |
| 2 | Clone | [phases/2-clone.md](./phases/2-clone.md) | Clone `cms-preview` at its current HEAD; save prev SHA for revision-feedback context |
| 3 | Solve | [phases/3-solve.md](./phases/3-solve.md) | Install `claude` CLI + invoke headless with verification + fix prompt |
| 4 | Push | [phases/4-push.md](./phases/4-push.md) | Commit + plain push to `cms-preview`; fail loudly on conflict |
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
| Slack | `SLACK_BOT_TOKEN`, `SLACK_ISSUES_CHANNEL_ID` | Phase 5 (release path, blocked notification) |
| Backend URL | `CMS_BACKEND_URL` (=`https://cms-backend-roman.vercel.app`) | Phase 5 |

If a credential is missing, the affected workflow step fails; the `failure()` release step decrements the lock and increments `agent_retry_count`. Stefan investigates.

## Failure-mode taxonomy

| Class | Action | Self-improve? |
|-------|--------|---------------|
| Transient (network 5xx, Supabase timeout) | Step fails; `release_issue.py` increments retry; next cron tick retries. | No |
| Quota exhausted (Anthropic 429 / Claude subscription quota) | Action step exits non-zero; release increments retry; cron resumes when quota replenishes. | No |
| Agent rejected (`/tmp/agent-status.md`) | Slack thread reply under "New Issue"; retry counter incremented; cron retries up to 3× | Always — if reason is novel, append rule to LEARNINGS |
| Agent CLI crashed (exit ≠ 0) | Slack thread reply with workflow logs link; retry counter incremented | Only if recurring |
| Push rejected (cms-preview moved during run) | Slack thread reply; workflow exits non-zero; runner workspace is ephemeral so local commit is lost | Only if recurring |
| Git push 403 | Likely PAT scope drift. Mark failed; Stefan fixes PAT. | Only if recurring. |
| Backend PATCH 5xx | Retry 3× exp backoff; if still failing → direct Slack thread reply with manual recovery command; commit is durable | Only if recurring |

## Hard rules — what the agent must NOT do

- Run `git commit` or `git push` from within the agent. The orchestrator does both. Agent only edits files.
- Run `npm install` or modify lockfiles unless adding a dependency is strictly required for the fix.
- Modify CI configs, GitHub workflows, env files, or `.git/` internals.
- Fetch external code or URLs (`WebFetch` is disallowed).
- Delete files via `rm` (Bash(rm:*) is disallowed).
- `cms-preview` is a real staging branch. The solver clones it at HEAD without resetting and pushes plain (no `--force`). Direct edits to cms-preview by Stefan or anyone else are preserved across solver runs. If a push conflicts because cms-preview moved during a run, the workflow fails loudly (Slack thread reply + non-zero exit) rather than silently overwriting concurrent work.

## Self-improvement loop

Same as CMS Connector: when an issue fails for a non-transient, non-covered reason, append a one-line rule to `LEARNINGS.md` under the matching phase heading:

`- <YYYY-MM-DD>: <one-line rule>. Triggered by: <short context>.`

LEARNINGS.md is **append-only**.

## Modifying this agent

If you change Phase 2 clone logic: keep `phases/2-clone.md` in sync with `clone_repo.py` + `repo.clone_at_preview_head`. The `repo_branch` column on `projects` is the source of truth for the staging branch name (always `cms-preview` for current clients but do not hardcode).
If you change Phase 3 prompt: keep `phases/3-solve.md` in sync with `claim_issue.py` `_build_prompt`.
If you change Phase 3 methodology: edit the vendored skill files in `skills/`, not the inline prompt text in `claim_issue.py`. The prompt builder injects skill content via `_render_skills_block()`. To re-sync from upstream, copy SKILL.md bodies from `~/.claude/plugins/cache/claude-plugins-official/superpowers/<version>/skills/<name>/SKILL.md` into `skills/<name>.md`. See `skills/README.md` for sources + last sync date.
If you change Phase 5 backend call: update the route in `backend/auth_service/routers/issues.py` to match.
If you change Phase 1 claim SQL: update the data model in `docs/superpowers/specs/2026-05-16-solver-agent-s3-design.md`.
