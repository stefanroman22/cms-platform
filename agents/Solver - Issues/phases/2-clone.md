# Phase 2 — Clone

**Goal:** Shallow-clone the claimed issue's client repo into `./client-repo/` at the `cms-preview` HEAD.

**Inputs:**
- `/tmp/issue.json` (from Phase 1).
- `SOLVER_GITHUB_TOKEN`.

**Steps:**
1. Read repo `owner/name` and branch from `/tmp/issue.json` -> `project.github_repo` + `project.repo_branch`.
2. Run `git clone --depth 50 --branch <branch> https://x-access-token:<token>@github.com/<repo>.git ./client-repo`.
3. Configure git user as `Solver Agent <solver@roman-technologies.dev>` inside `./client-repo/`.

**Outputs:** `./client-repo/` working tree.

**Failure messages:**
- 401/403 → PAT scope drift; surface to release step with error "git clone failed: <code>".
- 404 → repo missing OR wrong branch; surface "Repo or branch not found".
