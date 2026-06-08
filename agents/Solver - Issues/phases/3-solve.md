# Phase 3 — Solve

**Goal:** Let the `claude` CLI read `/tmp/agent-prompt.md` and edit files in `./client-repo/`.

**Inputs:**
- `/tmp/agent-prompt.md` — prompt built by Phase 1.
- `./client-repo/` — cloned repo.
- `CLAUDE_CODE_OAUTH_TOKEN` (from GitHub secrets, pre-written to `~/.claude/.credentials.json` by the workflow).

**Steps (executed by the workflow, not Python):**
1. Workflow installs `@anthropic-ai/claude-code` globally via npm on the runner.
2. Workflow writes `~/.claude/.credentials.json` from the `CLAUDE_CODE_OAUTH_TOKEN` secret so the CLI authenticates via the user's Claude Max subscription (same flow as `claude setup-token` locally).
3. Workflow runs `claude --print --model claude-opus-4-8 --max-turns 80 --allowed-tools "..." --disallowed-tools "..." < /tmp/agent-prompt.md` from inside `./client-repo/`. The prompt is piped via stdin (not command-substituted) to prevent shell injection from client-submitted issue content.
4. CLI executes the 6-step prompt protocol embedded in `/tmp/agent-prompt.md`: Step 0 (verify — `systematic-debugging` skill), Step 1 (plan — `writing-plans` + `karpathy-guidelines` skills, writes `/tmp/agent-plan.md`), Step 2 (implement — `test-driven-development` mindset where tests exist), Step 3 (static checks — lint/typecheck/test), Step 4 (self-review — `requesting-code-review` + `code-reviewer.md` checklist), Step 5 (final verification — `verification-before-completion` skill).
5. If verification rejects the issue OR planning surfaces unfixable risk, agent writes `/tmp/agent-status.md`.
6. CLI terminates when `--max-turns` reached OR agent exits.

**Model + effort:**
- `claude-opus-4-8` (most capable model in the Claude 4.x family).
- `--max-turns 80` is the budget — gives the agent room to verify, plan, implement, run static checks, multi-pass self-review, and final verification without truncation. The CLI now supports `--effort` (low|medium|high|xhigh|max); the Solver relies on `--max-turns 80` as its budget and leaves effort at the session default.

**Skills bundle:**
- Vendored under `agents/Solver - Issues/skills/` (SKILL.md bodies + cited reference files).
- `claim_issue.py._build_prompt` injects the full bundle inline into the prompt with `<skill>` / `<reference>` XML tags. Agent reads them before Step 0.
- Source-of-truth for methodology lives in the vendored files, not in inline prompt text. To update methodology: re-copy SKILL.md from upstream `superpowers` plugin cache into `skills/`.
- Skills assume tools (`Skill`, `TodoWrite`, `Task`) that headless `--print` does not expose. The prompt's `<execution-environment>` preamble neutralizes those references — agent applies the methodology as mindset and uses available tools (Read/Edit/Write/Glob/Grep/Bash) directly.

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
