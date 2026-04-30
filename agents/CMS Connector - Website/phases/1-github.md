# Phase 1 — Create GitHub repository

**Goal:** New GitHub repo exists, populated with the contents of `<folder_name>`.

**Inputs:** `<folder_name>`, `GITHUB_TOKEN`, GitHub MCP connection.

## Steps

1. Verify `<folder_name>` exists, is a directory, contains source files (not empty, not just `.git`).
2. Derive default repo name from `_slugify(folder_name)`. Confirm with user before creating.
3. Initialize a local git repo if not already present (`git init` only if no `.git`).
4. Create the GitHub repo via the GitHub MCP. Default visibility: **private** unless user says otherwise.
5. Add the new repo as `origin` and push the default branch.
6. Verify the push by reading the remote ref via the MCP.

## Outputs

- `github_repo` = `OWNER/NAME`
- `default_branch` = `main` (or whatever GitHub set)

## Failure feedback (verbatim)

| Cause | Message to user |
|-------|-----------------|
| MCP unavailable | "Cannot access GitHub MCP. Check that the GitHub MCP server is running and connected." |
| Token expired / 401 | "GitHub token rejected (401). Refresh `GITHUB_TOKEN` and re-run." |
| Token lacks scope | "GitHub token is missing required scopes (`repo`, `workflow`). Update token permissions and re-run." |
| Folder empty / missing | "Folder `<folder_name>` is empty or does not exist. Provide a valid path." |
| Repo name collision | "Repo `<owner>/<name>` already exists. Provide a different `--repo-name` or delete the existing repo." |
| Network / 5xx | "GitHub API returned <status>. Retry, then if persistent, check GitHub status page." |

## Self-improvement hook

If a credential / scope error recurs across runs, append to `LEARNINGS.md` under `## GitHub setup`. Example:
- `- 2026-04-29: Verify token scopes include 'workflow' before creating repos with CI files. Triggered by: 403 when pushing .github/workflows/.`
