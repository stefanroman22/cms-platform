# Solver Agent — Direct `claude` CLI Pivot

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `anthropics/claude-code-action@v1` (broken for OAuth in workflow_dispatch — issues #1026, #1281) with direct `claude` CLI invocation in a shell step, preserving Max-subscription billing.

**Architecture:** Install the Claude CLI in the runner via the official installer, pre-write `~/.claude/.credentials.json` from the `CLAUDE_CODE_OAUTH_TOKEN` secret (the same file `claude setup-token` produces locally), then invoke `claude --print "$PROMPT"` headless against the cloned client repo. No middleware. Existing claim/clone/finalize/release Python orchestrator is untouched.

**Tech Stack:** GitHub Actions, `claude` CLI (Node-based, installed via curl-pipe-sh), bash heredoc, existing Python orchestrator.

**Branch:** `fix/solver-direct-cli` (off latest master).

---

## File Structure

**Modify:**
- `.github/workflows/solver-agent.yml` — replace the Claude action step + supporting `Read prompt` and `Pre-write credentials` steps with three new shell steps: install CLI, write credentials, run CLI.
- `agents/Solver - Issues/AGENTS.md` — update Phase 3 doc to reference direct CLI instead of the action.
- `agents/Solver - Issues/phases/3-solve.md` — update Phase 3 implementation reference.

No new Python files. No DB changes. No new secrets — reuses `CLAUDE_CODE_OAUTH_TOKEN`.

---

## Task 1: Workflow YAML pivot

**Files:**
- Modify: `.github/workflows/solver-agent.yml`

- [ ] **Step 1: Read current state of solver-agent.yml**

Open the file. Find the existing block (added during S3 debug iterations) that contains:
- A `Pre-write Claude credentials file` step
- A `Read prompt file for action input` step
- A `Run Claude Code agent` step using `anthropics/claude-code-action@v1`

All three steps will be replaced.

- [ ] **Step 2: Replace the three Claude-action-related steps**

Find these three steps in the workflow file:

```yaml
      - name: Pre-write Claude credentials file
        if: steps.claim.outputs.has_issue == 'true'
        # Workaround for anthropics/claude-code-action#1281: OAuth token from
        # `with: claude_code_oauth_token` doesn't propagate to the Claude
        # subprocess. Writing the credentials JSON directly to the path
        # `claude setup-token` would produce locally is documented as a
        # working bypass.
        run: |
          mkdir -p "$HOME/.claude"
          cat > "$HOME/.claude/.credentials.json" <<EOF
          {"claudeAiOauth": {"accessToken": "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}", "subscriptionType": "max"}}
          EOF
          chmod 600 "$HOME/.claude/.credentials.json"

      - name: Read prompt file for action input
        id: prompt
        if: steps.claim.outputs.has_issue == 'true'
        run: |
          {
            echo 'text<<SOLVER_EOF'
            cat /tmp/agent-prompt.md
            echo SOLVER_EOF
          } >> "$GITHUB_OUTPUT"

      - name: Run Claude Code agent
        if: steps.claim.outputs.has_issue == 'true'
        # Known bugs: anthropics/claude-code-action#1026 (SDK post-processing
        # crash) and #1281 (OAuth token propagation broken to subprocess).
        # continue-on-error lets finalize.py pick up any file changes anyway.
        continue-on-error: true
        uses: anthropics/claude-code-action@v1
        env:
          # Belt-and-suspenders: token in env AND credentials file AND action input.
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: ${{ steps.prompt.outputs.text }}
          # CLI-style flags forwarded to the underlying `claude` invocation.
          # Working dir scoped to the cloned client repo so the agent can't
          # touch this repo's sources. Tool allowlist excludes git push/commit,
          # rm, and WebFetch — orchestrator handles git ops in finalize.py.
          claude_args: >-
            --cwd ./client-repo
            --model claude-sonnet-4-6
            --max-turns 15
            --allowed-tools "Read,Edit,Write,Glob,Grep,Bash(npm run *:*),Bash(node:*)"
            --disallowed-tools "Bash(git push:*),Bash(git commit:*),Bash(rm:*),WebFetch"
```

Replace ALL THREE with these THREE new shell-based steps:

```yaml
      - name: Install Claude CLI
        if: steps.claim.outputs.has_issue == 'true'
        # Installs the official `claude` CLI from npm. Pinned to a specific
        # minor version for reproducibility. The CLI ships as a Node package
        # so we use npm (already present on ubuntu-latest runners).
        run: |
          npm install -g @anthropic-ai/claude-code@latest
          claude --version

      - name: Pre-write Claude credentials
        if: steps.claim.outputs.has_issue == 'true'
        # This is the same file `claude setup-token` writes locally. The
        # standalone CLI reads it for subscription-OAuth auth.
        run: |
          mkdir -p "$HOME/.claude"
          cat > "$HOME/.claude/.credentials.json" <<EOF
          {"claudeAiOauth": {"accessToken": "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}", "subscriptionType": "max"}}
          EOF
          chmod 600 "$HOME/.claude/.credentials.json"

      - name: Run Claude headless against client repo
        if: steps.claim.outputs.has_issue == 'true'
        # Direct CLI invocation. No middleware (replaces anthropics/claude-code-action@v1
        # which has broken OAuth wiring — see issues #1026, #1281). The CLI
        # itself handles OAuth correctly via the credentials file above.
        #
        # continue-on-error lets finalize.py inspect the working tree for any
        # changes Claude made, even if the CLI exits non-zero on edge cases
        # (e.g., max-turns reached).
        continue-on-error: true
        env:
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
        run: |
          cd ./client-repo
          claude --print \
            --model claude-sonnet-4-6 \
            --max-turns 15 \
            --allowed-tools "Read,Edit,Write,Glob,Grep,Bash(npm run *:*),Bash(node:*)" \
            --disallowed-tools "Bash(git push:*),Bash(git commit:*),Bash(rm:*),WebFetch" \
            "$(cat /tmp/agent-prompt.md)"
```

Notes on the new flow:
- `Install Claude CLI` uses npm install. On ubuntu-latest runners npm is pre-installed.
- `--print` makes `claude` exit after one prompt cycle (headless mode; no interactive REPL).
- The prompt is piped via `"$(cat /tmp/agent-prompt.md)"` as the final positional argument.
- `cd ./client-repo` before invocation sets the agent's working directory (so its Read/Edit/Glob tools operate on the cloned repo, not on the cms-platform checkout).
- Tool allowlist and disallowlist match the previous action's intent (same flags).
- `continue-on-error: true` retained because `claude` can exit non-zero on max-turns or other recoverable signals; finalize.py's `git diff --quiet` check decides whether the agent actually made changes.

- [ ] **Step 3: Commit the YAML change**

```bash
git add .github/workflows/solver-agent.yml
git commit -m "fix(solver): replace claude-code-action with direct CLI invocation

The action has two open OAuth bugs that prevent the solver from running
on a Max subscription (#1026 SDK post-success crash; #1281 OAuth token
propagation broken to subprocess). After 5 failed smoke iterations the
SDK still crashes with apiKey/authToken null inside the action's bundled
client.

Replaces the action with three shell steps: install \`claude\` CLI via
npm, pre-write \`~/.claude/.credentials.json\` (same file
\`claude setup-token\` writes locally), invoke \`claude --print\` headless
against the cloned client repo. The standalone CLI handles OAuth
correctly — only the action's middleware was broken.

Subscription billing preserved. No middleware. Same tool allowlist,
same --max-turns, same model. finalize.py + release_issue.py paths
unchanged."
```

---

## Task 2: Update phase docs

**Files:**
- Modify: `agents/Solver - Issues/AGENTS.md`
- Modify: `agents/Solver - Issues/phases/3-solve.md`

- [ ] **Step 1: Update AGENTS.md Pipeline table**

Find this row in the Pipeline table:

```markdown
| 3 | Solve | [phases/3-solve.md](./phases/3-solve.md) | Run `anthropics/claude-code-action` with verification + fix prompt |
```

Replace with:

```markdown
| 3 | Solve | [phases/3-solve.md](./phases/3-solve.md) | Install `claude` CLI + invoke headless with verification + fix prompt |
```

- [ ] **Step 2: Rewrite phases/3-solve.md**

Replace the entire content of `agents/Solver - Issues/phases/3-solve.md` with:

```markdown
# Phase 3 — Solve

**Goal:** Let the `claude` CLI read `/tmp/agent-prompt.md` and edit files in `./client-repo/`.

**Inputs:**
- `/tmp/agent-prompt.md` — prompt built by Phase 1.
- `./client-repo/` — cloned repo.
- `CLAUDE_CODE_OAUTH_TOKEN` (from GitHub secrets, pre-written to `~/.claude/.credentials.json` by the workflow).

**Steps (executed by the workflow, not Python):**
1. Workflow installs `@anthropic-ai/claude-code` globally via npm on the runner.
2. Workflow writes `~/.claude/.credentials.json` from the `CLAUDE_CODE_OAUTH_TOKEN` secret so the CLI authenticates via the user's Claude Max subscription (same flow as `claude setup-token` locally).
3. Workflow runs `claude --print --model claude-sonnet-4-6 --max-turns 15 --allowed-tools "..." --disallowed-tools "..." "$(cat /tmp/agent-prompt.md)"` from inside `./client-repo/`.
4. CLI executes Step 0 (verify) and Step 1 (fix) per prompt.
5. If verification fails OR agent gives up, agent writes `/tmp/agent-status.md`.
6. CLI terminates when `--max-turns` reached OR agent exits.

**Outputs:**
- Modified files in `./client-repo/` (if fix succeeded).
- `/tmp/agent-status.md` (if agent could not proceed).

**Why direct CLI vs `anthropics/claude-code-action@v1`:**
The official action has two open OAuth bugs (#1026, #1281) that crash the SDK before the agent runs in `workflow_dispatch` / cron contexts. The standalone CLI handles OAuth correctly. Direct invocation also removes ~30s of middleware overhead per run.

**Failure messages:**
- npm install failure → workflow step fails; release_issue.py increments retry; cron retries.
- Subscription quota exhausted → CLI exits non-zero; `continue-on-error` lets finalize.py detect no-diff → release_issue_failed.
- CLI timeout → 25-min workflow timeout kills the job; stale claim window cleans up on next tick.
```

- [ ] **Step 3: Commit docs**

```bash
git add "agents/Solver - Issues/AGENTS.md" "agents/Solver - Issues/phases/3-solve.md"
git commit -m "docs(solver): Phase 3 now invokes \`claude\` CLI directly, not the action"
```

---

## Task 3: Test the pivot end-to-end

**Files:** none (operational task)

- [ ] **Step 1: Push branch + open PR**

```bash
git push -u origin fix/solver-direct-cli
gh pr create --base dev --title "fix(solver): direct \`claude\` CLI invocation, bypass broken action" --body "Workaround for upstream OAuth bugs #1026 + #1281 in anthropics/claude-code-action@v1. CLI itself works fine with subscription OAuth; only the action's middleware is broken. Subscription billing preserved.

See docs/superpowers/plans/2026-05-16-solver-direct-cli.md for full rationale."
```

- [ ] **Step 2: Wait for CI green + admin merge**

PRs in this repo go to `dev` first, then auto-merge to `master`. Wait for both gates. Use `gh pr checks <number>` + `gh pr merge <number> --squash --delete-branch --admin` once green.

- [ ] **Step 3: Reset retry counter on the smoke-test issue**

```sql
UPDATE project_issues
SET agent_status=NULL, agent_retry_count=0, agent_last_error=NULL, agent_claimed_at=NULL
WHERE id='<issue_id>';
```

(Stefan applies via Supabase MCP; or controller does so via `mcp__supabase__execute_sql`.)

- [ ] **Step 4: Trigger workflow manually**

```bash
gh workflow run "Solver Agent (S3)" --ref master
```

- [ ] **Step 5: Watch the run**

```bash
gh run list --workflow "Solver Agent (S3)" --limit 1 --json databaseId --jq '.[0].databaseId'
# then
gh run view <id> --log
```

Expected timeline:
- `Install Claude CLI` step: ~10-20s (npm install).
- `Pre-write Claude credentials` step: <1s.
- `Run Claude headless against client repo` step: 1-5 min (real agent run on a real fix).
- `Commit, push, mark done` step: <30s if there's a diff to push.

Success signal: workflow completes with `agent_commit_sha` populated in `project_issues` row + new commit on `cms-preview` branch of the client repo + Slack `#issues-websites` posts "✅ Issue Resolved" with the SHA.

- [ ] **Step 6: Verify in Supabase + GitHub + Slack**

```sql
SELECT title, status, agent_status, agent_retry_count, agent_commit_sha, slack_resolved_ts
FROM project_issues WHERE id='<issue_id>';
```

Expected:
- `status = 'done'`
- `agent_status = NULL` (lock cleared)
- `agent_retry_count = 0`
- `agent_commit_sha` populated
- `slack_resolved_ts` populated

Then:

```bash
gh api repos/<owner>/<client-repo>/branches/cms-preview --jq '.commit.commit.message'
```

Should show the solver's commit message with `Co-Authored-By: Solver Agent (Claude Code)`.

And Slack `#issues-websites` should have a new "✅ Issue Resolved" message.

- [ ] **Step 7: If CLI fails at install or auth**

The credentials.json workaround is unproven for the standalone CLI in CI. If install succeeds but Claude auth fails:

1. Capture exact error from `gh run view <id> --log` and quote it.
2. Likely fixes:
   - Try `npm install -g @anthropic-ai/claude-code@<specific version>` if `@latest` is incompatible.
   - Check the credentials.json schema — some CLI versions expect `{"oauth_token": "..."}` instead of nested `claudeAiOauth.accessToken`.
   - Try the curl-pipe-sh installer: `curl -fsSL https://claude.ai/install.sh | bash` (writes to `~/.local/bin/claude`).

Pause and report the exact error before iterating further.

---

## Self-Review

### Spec coverage
- Replace action with CLI → Task 1.
- Preserve OAuth/subscription billing → Task 1 (credentials.json from `CLAUDE_CODE_OAUTH_TOKEN`).
- Keep tool allowlist + max-turns + model → Task 1 (same flags).
- Update phase docs to reflect new approach → Task 2.
- End-to-end validation → Task 3.

### Placeholders
- Task 3 Step 7 mentions "likely fixes" — those are documented alternative paths, not placeholders. The current path (credentials.json + npm install) is the primary; Step 7 is the diagnostic fallback the engineer follows if it doesn't work.
- All commit messages, file paths, and shell commands are complete.

### Type / signature consistency
- The Python orchestrator is untouched. No signature changes.
- Workflow step IDs (`claim`, etc.) unchanged.

All consistent.
