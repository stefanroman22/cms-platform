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
