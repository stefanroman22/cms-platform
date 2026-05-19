# Phase 4 — Push

**Goal:** Commit agent's file changes and push to `cms-preview`.

**Inputs:** `./client-repo/` working tree, `SOLVER_GITHUB_TOKEN`.

**Steps:**
1. If `/tmp/agent-status.md` exists → skip push, mark failed (Phase 5 handles).
2. `git -C client-repo diff --quiet`. If exit 0 (no diff) → mark failed.
3. Otherwise:
   - `git add -A`.
   - Commit with message `fix: <issue.title>\n\nAutomated fix by Solver Agent for CMS issue <id>.\n\nCo-Authored-By: Solver Agent (Claude Code) <solver@roman-technologies.dev>`.
   - Capture HEAD SHA.
   - `git push origin HEAD`.

**Outputs:** New commit on `cms-preview`, parent = previous `cms-preview` HEAD.

**Failure messages:**
- Push 403 → PAT scope drift; surface to release step.

**Failure mode: push rejected**

If cms-preview moved between clone and push (concurrent solver run, manual edit pushed by Stefan, etc.), `git push` returns non-zero. `repo.commit_and_push` raises `PushRejectedError`. `finalize.py` catches it, posts a Slack thread reply (kind=backend_error, "cms-preview moved during run; local commit lost — re-trigger workflow after staging stabilizes"), then re-raises. The `Release on failure` workflow step handles `release_issue_failed` (single retry increment). Runner workspace is ephemeral — the local commit cannot be recovered.
