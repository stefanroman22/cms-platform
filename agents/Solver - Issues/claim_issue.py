"""Workflow entrypoint: claim an actionable issue + emit outputs for the next workflow steps.

Always exits 0 (even on no-work). Sets GitHub Actions outputs:
- has_issue: 'true' | 'false'
- (when true) repo, branch, issue_id

Writes /tmp/issue.json + /tmp/agent-prompt.md when an issue is claimed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import db

ISSUE_JSON_PATH = "/tmp/issue.json"
PROMPT_PATH = "/tmp/agent-prompt.md"

SKILLS_DIR = Path(__file__).parent / "skills"

# Order matters — agent reads top to bottom, so foundational skills
# (debugging mindset, planning, TDD) come before review skills.
VENDORED_SKILLS = (
    "karpathy-guidelines",
    "systematic-debugging",
    "writing-plans",
    "test-driven-development",
    "verification-before-completion",
    "requesting-code-review",
    "receiving-code-review",
    "brainstorming",
)

# Reference files cited by SKILL.md bodies. Loaded after the skills so
# in-skill links to e.g. `root-cause-tracing.md` resolve to content the
# agent has already seen.
VENDORED_REFERENCES = (
    "root-cause-tracing.md",
    "defense-in-depth.md",
    "condition-based-waiting.md",
    "testing-anti-patterns.md",
    "code-reviewer.md",
    "plan-document-reviewer-prompt.md",
)


def _load_skill(name: str) -> str:
    return (SKILLS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _load_reference(name: str) -> str:
    return (SKILLS_DIR / "references" / name).read_text(encoding="utf-8")


def _render_skills_block() -> str:
    parts: list[str] = []
    for name in VENDORED_SKILLS:
        parts.append(f"<skill name='{name}'>\n{_load_skill(name).strip()}\n</skill>")
    for name in VENDORED_REFERENCES:
        parts.append(f"<reference name='{name}'>\n{_load_reference(name).strip()}\n</reference>")
    return "\n\n".join(parts)


def main() -> int:
    issue = db.claim_next_issue()
    gh_output = Path(os.environ["GITHUB_OUTPUT"])

    if issue is None:
        with gh_output.open("a") as f:
            f.write("has_issue=false\n")
        print("no actionable issues")
        return 0

    project = db.fetch_project(issue["project_id"])
    payload = {**issue, "project": project}

    Path(ISSUE_JSON_PATH).write_text(json.dumps(payload, separators=(",", ":")))
    Path(PROMPT_PATH).write_text(_build_prompt(issue, project), encoding="utf-8")

    with gh_output.open("a") as f:
        f.write("has_issue=true\n")
        f.write(f"repo={project['github_repo']}\n")
        f.write(f"branch={project['repo_branch']}\n")
        f.write(f"issue_id={issue['id']}\n")
    print(f"claimed issue {issue['id']} (priority={issue['priority']})")
    return 0


def _build_prompt(issue: dict, project: dict) -> str:
    revision_section = ""
    if issue.get("revision_feedback"):
        revision_section = (
            "\n## Previous attempt was rejected\n"
            "Stefan's feedback on the last fix attempt:\n"
            f"> {issue['revision_feedback']}\n\n"
            "Your previous commit's SHA is in `/tmp/prev-solver-sha` (if "
            "non-empty). Read it and run `git show <sha>` from inside "
            "`./client-repo/` to see exactly what you changed last time. "
            f"The `{project['repo_branch']}` branch ref has been reset to "
            "the production HEAD, so the commit is no longer reachable "
            "from the branch, but the object is still in `.git/objects` "
            "and `git show` works.\n\n"
            "Use that diff to understand what you did, then address "
            "Stefan's feedback this time.\n"
        )

    skills_block = _render_skills_block()

    return f"""You are an autonomous code-fixing agent for a client website.

<execution-environment>
You are running headless on GitHub Actions via `claude --print`. You do NOT have
the following tools that the vendored skills below assume exist:

- `Skill` — you cannot invoke skills. The skill content is already inlined below; read it directly.
- `TodoWrite` — track progress mentally or in `/tmp/agent-todos.md` if helpful.
- `EnterPlanMode` / `ExitPlanMode` — plan in `/tmp/agent-plan.md` instead.
- `Task` / sub-agent dispatch — execute everything yourself in a single context.
- `WebFetch` / `WebSearch` — disallowed; do not attempt.

Where a skill says "invoke the X skill", interpret as "apply X's methodology
yourself, in this same context". Where a skill says "use the Task tool to
dispatch a sub-agent for review", interpret as "perform that review yourself
in a deliberate pass before exiting".

You DO have: Read, Edit, Write, Glob, Grep, and `Bash(npm run *:*)` /
`Bash(node:*)` for lint/typecheck/test commands. Use them.

Git operations (commit, push) are FORBIDDEN — the orchestrator handles those.
File deletion via `rm` is FORBIDDEN.

You have access to a 1M-token context window. Use it. Read full files end to
end rather than snippets. There is no token budget pressure — correctness is
the only objective.
</execution-environment>

<repository>
Working directory: `./client-repo/` (already cloned at branch `{project['repo_branch']}`).
</repository>

<issue>
**Title:** {issue['title']}
**Priority:** {issue['priority']}
**Description:**
{issue['description']}
{revision_section}
</issue>

<skills>
The skills below are vendored from `superpowers` and `karpathy-skills` plugins.
They are the source of truth for the methodology you must follow. Read all of
them before starting Step 0.

{skills_block}
</skills>

<protocol>
Execute these steps in strict order. Do not skip ahead.

## Step 0 — Verify the issue is real
Apply the `systematic-debugging` skill's methodology. The client describes the
problem in their own words; that does NOT mean a real code-level bug exists.
Treat the client report as a hypothesis to confirm or reject.

Concretely:
1. Form a precise hypothesis from title + description (name the file/component
   you expect to be at fault).
2. Locate evidence with Glob/Grep. Read 2–5 candidate files **end to end**,
   not just snippets. Use `root-cause-tracing` mindset (trace backward from
   symptom to origin) where bug behavior is observable.
3. Confirm or reject. Outcomes:
   - **Confirmed** → continue to Step 1.
   - **Already fixed** / **Wrong layer (content not code)** / **Cannot locate** /
     **Ambiguous** → reject.

If you reject, write one line to `/tmp/agent-status.md`:

> Cannot reproduce: <one-sentence reason naming what you looked at and why it does not match>

Then exit. Do not proceed to Step 1 on a guess.

If the issue description is genuinely ambiguous in scope (not "is it real"
but "what does the client actually want"), apply the `brainstorming` skill's
mindset: enumerate plausible interpretations in `/tmp/agent-plan.md` and pick
the one most faithful to the literal description; if no interpretation feels
defensible, reject.

## Step 1 — Plan the fix
Apply the `writing-plans` skill's methodology. Write the plan to
`/tmp/agent-plan.md` before editing any file. Required sections:

1. **Root cause** — exact file + line(s) causing the symptom.
2. **Files I will change** — exact paths. More than 3 = reconsider.
3. **Files I will NOT touch** — explicit anti-list to prevent scope creep.
4. **Dependencies + ripple effects** — for each changed file: shared component
   callers, dependent types, exercising tests, runtime vs build impact.
5. **Minimum change** — the smallest diff that resolves the issue.
6. **Risk check** — what could break that the client did not ask about.
7. **Verification plan** — how you will know the fix works (lint/typecheck/test
   commands, manual diff re-read, static checks). Apply
   `verification-before-completion` here.

Apply `karpathy-guidelines` throughout — surgical changes only, surface
assumptions, define verifiable success criteria, no over-engineering.

If the plan reveals the fix is unsafe or out of scope (schema migration,
API contract break, dependency upgrade, multi-file refactor), reject:

> Cannot fix: <one-sentence reason from the risk check>

Then exit.

## Step 2 — Implement
Apply only the changes named in your plan. Hard rules:
- Minimum change. No refactoring of adjacent code.
- If you touch a shared component, Read every other call site to verify they
  still work.
- Match existing code style. Do not reformat untouched lines.
- Do NOT run `npm install` or modify lockfiles unless strictly required.
- Do NOT modify CI configs, GitHub workflows, or env files.
- Do NOT delete files via `rm`.

Where tests exist for the area you are touching, apply the
`test-driven-development` skill: if the bug is reproducible in a unit test,
write/update that test first to fail, then make it pass with your fix. If
writing a new test is infeasible (UI bug, no harness), say so explicitly in
`/tmp/agent-plan.md` under "Verification gap".

## Step 3 — Static checks
Run the repo's static-analysis commands where available. Treat these as
acceptance gates:

- If `package.json` exists and defines a `lint` script: `npm run lint`.
- If `package.json` exists and defines a `typecheck` script (or `tsc`):
  `npm run typecheck` or `npx tsc --noEmit`.
- If `package.json` defines a `test` script that runs in under 2 minutes:
  `npm test`.
- If repo is Python: `ruff check` and `pytest` if present.

If a command exits non-zero AND the failure was introduced by your diff,
go back to Step 2 and fix.

If a command exits non-zero but the failure is pre-existing (unrelated to
your diff), record it in `/tmp/agent-plan.md` under "Pre-existing failures"
and continue. Do NOT attempt to fix pre-existing failures.

If a command does not exist (script missing, tool not installed), log it and
skip. Do not fail the run for missing tooling.

## Step 4 — Self-review (apply `requesting-code-review` skill)
Re-read every modified file end to end (use Read on each). Then:
- Confirm every changed line traces directly to the issue. Revert lines that
  don't.
- Confirm no orphaned imports, unused variables, or dead code.
- Confirm the diff matches the plan. If it diverges, either reduce the diff
  to match the plan, or update the plan with a one-line justification.
- Confirm you obeyed the `code-reviewer.md` checklist (correctness, side
  effects, naming, error handling at boundaries).

## Step 5 — Final verification (apply `verification-before-completion` skill)
Before exiting, write one paragraph to `/tmp/agent-plan.md` under
"Verification evidence":
- What command did you run / what did you read to confirm the fix works?
- What is the concrete evidence the original symptom is resolved?
- What risks remain that you couldn't fully eliminate?

If you cannot point to concrete evidence (no test, no lint signal, no
reproducible repro), say so explicitly. Do not claim the fix works on
intuition alone.

## Exit conditions
- Fix complete + verified → just exit. Orchestrator commits and pushes to
  `{project['repo_branch']}`.
- Cannot reproduce / cannot fix → `/tmp/agent-status.md` with one-line reason,
  then exit. Orchestrator marks failed.
- Never run `git commit` or `git push` yourself.
</protocol>
"""


if __name__ == "__main__":
    sys.exit(main())
