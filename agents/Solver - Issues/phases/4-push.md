# Phase 4 — Push

**Goal:** Commit agent's file changes and force-with-lease push to `cms-preview`.

**Inputs:** `./client-repo/` working tree, `SOLVER_GITHUB_TOKEN`.

**Steps:**
1. If `/tmp/agent-status.md` exists → skip push, mark failed (Phase 5 handles).
2. `git -C client-repo diff --quiet`. If exit 0 (no diff) → mark failed.
3. Otherwise:
   - `git add -A`.
   - Commit with message `fix: <issue.title>\n\nAutomated fix by Solver Agent for CMS issue <id>.\n\nCo-Authored-By: Solver Agent (Claude Code) <solver@roman-technologies.dev>`.
   - Capture HEAD SHA.
   - `git push --force-with-lease origin HEAD`.

**Why --force-with-lease?** Phase 2 reset `cms-preview` to production HEAD, rewriting its history. A plain push would be rejected as non-fast-forward. `--force-with-lease` is safer than `--force`: it only overwrites the remote if the remote ref matches the expected SHA. If another solver run or Stefan pushed to `cms-preview` between our clone and our push, the lease fails and we surface a clear error instead of stomping on their work.

**Outputs:** New commit on `cms-preview`, parent = production HEAD.

**Failure messages:**
- Push 403 → PAT scope drift; surface to release step.
- Push rejected (lease failed) → another writer touched `cms-preview` mid-run; surface "cms-preview moved during run, retry on next tick".
