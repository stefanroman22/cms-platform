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

    repo.clone_and_reset_to_prod(
        repo_slug=project["github_repo"],
        dev_branch=project["repo_branch"],
        prod_branch=project["production_branch"],
        dest=dest,
    )
    print(
        f"cloned {project['github_repo']}: "
        f"reset {project['repo_branch']} → origin/{project['production_branch']} → {dest}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
