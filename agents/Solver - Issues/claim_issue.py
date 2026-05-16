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
    Path(PROMPT_PATH).write_text(_build_prompt(issue, project))

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
            "Look at git log for your previous commit (most recent commit on "
            f"{project['repo_branch']}), understand what you did, and address "
            "Stefan's feedback this time.\n"
        )

    return f"""You are an autonomous code-fixing agent for a client website.

## Repository
Working directory: `./client-repo/` (already cloned at branch `{project['repo_branch']}`).

## Issue submitted by client
**Title:** {issue['title']}
**Priority:** {issue['priority']}
**Description:**
{issue['description']}
{revision_section}

## Step 0 — Verify the issue is real
Before attempting any fix, explore the codebase to confirm the issue actually exists.
The client describes the problem in their own words; that doesn't mean the bug is real.
Reasons it may NOT be a real bug:
- The element/text the client references doesn't exist in the code.
- The behavior the client wants is already in place.
- The "issue" is actually a feature request needing content-side (CMS) changes.
- The description is ambiguous and could describe a working component.

If after a reasonable exploration (Glob/Grep + Read 2-5 likely candidates) you conclude
the issue is NOT a real code-level bug, write one line to `/tmp/agent-status.md`:

> Cannot reproduce: <one-sentence reason>

Then exit. The orchestrator will mark the issue as failed.

If you are unsure but the issue could plausibly be real, proceed to Step 1.

## Step 1 — Fix the issue
1. Explore the repo to find the relevant code.
2. Make the minimum change required to resolve the issue.
3. If you change shared components, verify other call sites still work.
4. Do NOT run `npm install` or modify lockfiles unless adding a dependency is strictly required.
5. Do NOT modify CI configs, GitHub workflows, or env files.

## When you cannot fix the issue
If after exploration you cannot determine what to change, write one line to
`/tmp/agent-status.md`:

> Cannot fix: <one-sentence reason>

Then exit. The orchestrator will mark the issue as failed.

## When you finish a fix
Just exit cleanly. The orchestrator commits and pushes your changes to
`{project['repo_branch']}`. Do NOT run git commit or git push yourself.
"""


if __name__ == "__main__":
    sys.exit(main())
