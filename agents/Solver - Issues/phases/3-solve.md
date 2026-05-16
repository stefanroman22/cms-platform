# Phase 3 — Solve

**Goal:** Let the `claude` CLI read `/tmp/agent-prompt.md` and edit files in `./client-repo/`.

**Inputs:**
- `/tmp/agent-prompt.md` — prompt built by Phase 1.
- `./client-repo/` — cloned repo.
- `CLAUDE_CODE_OAUTH_TOKEN` (from GitHub secrets, pre-written to `~/.claude/.credentials.json` by the workflow).

**Steps (executed by the workflow, not Python):**
1. Workflow installs `@anthropic-ai/claude-code` globally via npm on the runner.
2. Workflow writes `~/.claude/.credentials.json` from the `CLAUDE_CODE_OAUTH_TOKEN` secret so the CLI authenticates via the user's Claude Max subscription (same flow as `claude setup-token` locally).
3. Workflow runs `claude --print --model claude-opus-4-7 --max-turns 30 --allowed-tools "..." --disallowed-tools "..." < /tmp/agent-prompt.md` from inside `./client-repo/`. The prompt is piped via stdin (not command-substituted) to prevent shell injection from client-submitted issue content.
4. CLI executes the 4-step prompt protocol: Step 0 (verify, debugging methodology), Step 1 (plan, writing-plans methodology, writes `/tmp/agent-plan.md`), Step 2 (implement), Step 3 (self-review).
5. If verification rejects the issue OR planning surfaces unfixable risk, agent writes `/tmp/agent-status.md`.
6. CLI terminates when `--max-turns` reached OR agent exits.

**Model + effort:**
- `claude-opus-4-7` (most capable model in the Claude 4.x family).
- `--max-turns 30` is the "high effort" budget — gives the agent room to verify, plan, implement, and self-review without truncation. There is no `--effort` flag in the CLI; turn budget is the lever.

**Outputs:**
- Modified files in `./client-repo/` (if fix succeeded).
- `/tmp/agent-plan.md` (always written before edits; useful for forensics).
- `/tmp/agent-status.md` (if agent could not proceed).

**Why direct CLI vs `anthropics/claude-code-action@v1`:**
The official action has two open OAuth bugs (#1026, #1281) that crash the SDK before the agent runs in `workflow_dispatch` / cron contexts. The standalone CLI handles OAuth correctly. Direct invocation also removes ~30s of middleware overhead per run.

**Failure messages:**
- npm install failure → workflow step fails; release_issue.py increments retry; cron retries.
- Subscription quota exhausted → CLI exits non-zero; `continue-on-error` lets finalize.py detect no-diff → release_issue_failed.
- CLI timeout → 25-min workflow timeout kills the job; stale claim window cleans up on next tick.
