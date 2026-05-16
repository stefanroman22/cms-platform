"""Workflow entrypoint: clone the claimed client repo into ./client-repo/."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import repo


def main() -> int:
    issue = json.loads(Path("/tmp/issue.json").read_text())
    project = issue["project"]
    dest = "./client-repo"

    # Clean if a previous failed run left a stale dir.
    if Path(dest).exists():
        shutil.rmtree(dest)

    repo.clone(
        repo=project["github_repo"],
        branch=project["repo_branch"],
        dest=dest,
    )
    print(f"cloned {project['github_repo']} @ {project['repo_branch']} → {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
