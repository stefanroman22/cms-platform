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
