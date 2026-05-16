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
