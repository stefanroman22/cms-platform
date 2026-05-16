# Solver Agent — cms-preview Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Solver Agent reset `cms-preview` to the production branch HEAD before each run, force-push afterwards, so the S1.5 listener can always fast-forward production to `cms-preview`. Fixes the "diverged, cannot fast-forward" deploy failures.

**Architecture:** Phase 2 (Clone) becomes "Clone + Reset". After cloning the client repo, fetch the production branch (`projects.production_branch` — already in DB) and `git checkout -B cms-preview origin/<prod_branch>`. This single command handles both the reset case AND the first-run case (when `cms-preview` doesn't yet exist). Save the previous `cms-preview` SHA into `/tmp/prev-solver-sha` before reset so the revision-feedback retry path can `git show <sha>` to inspect the rejected commit (object remains in `.git/objects` even after the branch ref moves). Phase 4 (Push) switches to `--force-with-lease` because `cms-preview` history is now rewritten each run.

**Tech Stack:** Python 3.13, `git` CLI via `subprocess`, existing Supabase orchestrator. No new dependencies. No DB migration (column `projects.production_branch` already exists and is already returned by `db.fetch_project`).

**Branch:** `fix/solver-cms-preview-reset` (off latest master).

---

## File Structure

**Modify:**
- `agents/Solver - Issues/repo.py` — replace `clone()` with `clone_and_reset_to_prod()`; switch `commit_and_push()` push to `--force-with-lease`.
- `agents/Solver - Issues/clone_repo.py` — pass `production_branch` through to repo helper; write `/tmp/prev-solver-sha`.
- `agents/Solver - Issues/claim_issue.py` — `_build_prompt` revision_feedback section: read `/tmp/prev-solver-sha`, instruct agent to `git show <sha>` for previous diff.
- `agents/Solver - Issues/AGENTS.md` — document "cms-preview is solver-only" invariant and reset behaviour under Hard rules + Modifying this agent.
- `agents/Solver - Issues/phases/2-clone.md` — describe clone + reset flow.
- `agents/Solver - Issues/phases/4-push.md` — describe force-with-lease push.
- `agents/Solver - Issues/tests/test_repo.py` — update existing tests; add tests for `clone_and_reset_to_prod` + force-with-lease path.
- `agents/Solver - Issues/tests/test_claim_issue.py` — assert prompt references `/tmp/prev-solver-sha` when revision_feedback is present.

**No new files. No DB changes. No new secrets.**

---

## Task 1: repo.py — clone-and-reset helper + force-with-lease push

**Files:**
- Modify: `agents/Solver - Issues/repo.py`
- Modify: `agents/Solver - Issues/tests/test_repo.py`

- [ ] **Step 1: Write failing tests for `clone_and_reset_to_prod`**

Add to `tests/test_repo.py`:

```python
def test_clone_and_reset_to_prod_clones_with_no_single_branch(fake_run):
    repo.clone_and_reset_to_prod(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        prod_branch="main",
        dest="./client-repo",
    )
    clone_call = fake_run[0]
    assert clone_call["args"][0] == "git"
    assert "clone" in clone_call["args"]
    # No --single-branch: we need both prod_branch and dev_branch refs.
    assert "--no-single-branch" in clone_call["args"]
    assert "--branch" in clone_call["args"]
    assert "main" in clone_call["args"]  # initial checkout to prod
    url = next(a for a in clone_call["args"] if a.startswith("https://"))
    assert "x-access-token:ghs_test@github.com/owner/name" in url


def test_clone_and_reset_fetches_dev_branch_and_saves_prev_sha(fake_run, tmp_path, monkeypatch):
    prev_sha_path = tmp_path / "prev-solver-sha"
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(prev_sha_path))

    def fake_run_with_sha(args, **kwargs):
        fake_run.append({"args": args, "kwargs": kwargs})
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        if "rev-parse" in args and "origin/cms-preview" in args:
            result.stdout = "deadbeefcafebabe\n"
            result.returncode = 0
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_with_sha)
    repo.clone_and_reset_to_prod(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        prod_branch="main",
        dest="./client-repo",
    )

    # Fetched dev branch
    fetch_calls = [c for c in fake_run if "fetch" in c["args"]]
    assert any("cms-preview" in str(c["args"]) for c in fetch_calls)
    # Wrote prev SHA
    assert prev_sha_path.read_text().strip() == "deadbeefcafebabe"
    # Checked out cms-preview as a new branch at origin/main
    checkout_calls = [c for c in fake_run if "checkout" in c["args"]]
    assert any("-B" in c["args"] and "cms-preview" in c["args"] for c in checkout_calls)
    assert any("origin/main" in c["args"] for c in checkout_calls)


def test_clone_and_reset_handles_missing_dev_branch(fake_run, tmp_path, monkeypatch):
    """If origin/cms-preview does not exist (first run), prev-sha file is empty."""
    prev_sha_path = tmp_path / "prev-solver-sha"
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(prev_sha_path))

    def fake_run_no_dev(args, **kwargs):
        fake_run.append({"args": args, "kwargs": kwargs})
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        # Simulate fetch failure for cms-preview branch
        if "fetch" in args and "cms-preview" in args:
            result.returncode = 128
            result.stderr = "fatal: couldn't find remote ref refs/heads/cms-preview\n"
        # rev-parse fails too
        if "rev-parse" in args and "origin/cms-preview" in args:
            result.returncode = 128
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_no_dev)
    repo.clone_and_reset_to_prod(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        prod_branch="main",
        dest="./client-repo",
    )

    # Still wrote an empty prev-sha (signals first-run to claim_issue)
    assert prev_sha_path.exists()
    assert prev_sha_path.read_text() == ""


def test_commit_and_push_uses_force_with_lease(fake_run, monkeypatch):
    def fake_run_with_sha(args, **kwargs):
        fake_run.append({"args": args, "kwargs": kwargs})
        result = MagicMock()
        result.returncode = 0
        if "rev-parse" in args:
            result.stdout = "abc123\n"
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_with_sha)
    repo.commit_and_push(path="./client-repo", issue_id="i1", issue_title="t")
    push_call = next(c for c in fake_run if "push" in c["args"])
    assert "--force-with-lease" in push_call["args"]
```

Remove the old `test_clone_uses_shallow_depth_and_branch` and `test_clone_configures_git_user` test bodies' assertions on `clone()` since we're replacing it. Keep the test names but rename them to target `clone_and_reset_to_prod` (already covered above), OR delete and rely on the new tests.

Action: delete the two old `test_clone_*` tests and add the four new tests above.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_repo.py -v
```

Expected: FAIL with `AttributeError: module 'repo' has no attribute 'clone_and_reset_to_prod'` and the force-with-lease assertion failing.

- [ ] **Step 3: Implement repo.py changes**

Replace the `clone()` function and update `commit_and_push()` in `agents/Solver - Issues/repo.py`:

```python
PREV_SHA_PATH = "/tmp/prev-solver-sha"


def clone_and_reset_to_prod(
    *, repo_slug: str, dev_branch: str, prod_branch: str, dest: str
) -> None:
    """Clone client repo, fetch dev_branch, then reset to prod_branch HEAD.

    This guarantees the agent always edits from the current production state.
    Any previous solver commits on dev_branch are NOT in the working tree but
    are still reachable via .git/objects — we save the previous dev_branch SHA
    to PREV_SHA_PATH so the revision-feedback prompt can `git show <sha>` for
    the rejected commit's diff.

    Embeds SOLVER_GITHUB_TOKEN in the HTTPS URL.
    """
    url = f"https://x-access-token:{_token()}@github.com/{repo_slug}.git"

    # Clone, initial checkout on prod_branch, with all remote refs available
    # (no --single-branch) so we can fetch + rev-parse origin/dev_branch.
    _run([
        "git", "clone",
        "--depth", "50",
        "--no-single-branch",
        "--branch", prod_branch,
        url, dest,
    ])
    _run(["git", "-C", dest, "config", "user.email", _GIT_USER_EMAIL])
    _run(["git", "-C", dest, "config", "user.name", _GIT_USER_NAME])

    # Fetch the dev branch ref so origin/<dev_branch> exists. If the branch
    # doesn't exist yet (brand-new repo / first run), fetch fails — that's
    # fine, we'll write an empty prev-sha file and proceed.
    fetch_result = _run(
        ["git", "-C", dest, "fetch", "--depth", "50", "origin", dev_branch],
        check=False,
    )

    # Save previous dev_branch SHA (or empty string if branch doesn't exist).
    prev_sha = ""
    if fetch_result.returncode == 0:
        rev_parse = _run(
            ["git", "-C", dest, "rev-parse", f"origin/{dev_branch}"],
            check=False,
        )
        if rev_parse.returncode == 0:
            prev_sha = rev_parse.stdout.strip()

    Path(PREV_SHA_PATH).write_text(prev_sha)

    # Reset working tree to prod_branch HEAD, locally named as dev_branch.
    # -B creates-or-resets the branch ref. This handles both cases:
    #   (a) dev_branch already exists → reset it to origin/prod_branch
    #   (b) dev_branch doesn't exist → create it from origin/prod_branch
    # Push (with --force-with-lease) in commit_and_push will create the
    # remote ref if missing or overwrite if existing.
    _run(["git", "-C", dest, "checkout", "-B", dev_branch, f"origin/{prod_branch}"])
```

Add `from pathlib import Path` to the imports at top of `repo.py`.

Then update `commit_and_push` to force-with-lease. Change the final push line:

```python
    _run(["git", "-C", path, "push", "--force-with-lease", "origin", "HEAD"])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_repo.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "agents/Solver - Issues/repo.py" "agents/Solver - Issues/tests/test_repo.py"
git commit -m "feat(solver/repo): clone_and_reset_to_prod + force-with-lease push

Replaces clone() with clone_and_reset_to_prod() which clones, fetches
the dev branch, saves its previous SHA to /tmp/prev-solver-sha, and
resets the working tree to origin/<prod_branch>. Handles first-run
(dev branch doesn't exist) and reset (dev branch exists) in one path.

Push now uses --force-with-lease since dev_branch history is rewritten
each run."
```

---

## Task 2: clone_repo.py — wire prod_branch through

**Files:**
- Modify: `agents/Solver - Issues/clone_repo.py`

- [ ] **Step 1: Update clone_repo.py to call the new helper**

Replace the `repo.clone(...)` call in `clone_repo.py` `main()` with:

```python
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
```

`db.fetch_project` already SELECTs `production_branch` so no DB code changes.

- [ ] **Step 2: Smoke test locally (best-effort)**

Skip — `clone_repo.py` makes real network calls; integration tested in the workflow smoke at the end of Task 5.

- [ ] **Step 3: Commit**

```bash
git add "agents/Solver - Issues/clone_repo.py"
git commit -m "feat(solver/clone): pass production_branch through to repo helper"
```

---

## Task 3: claim_issue.py — revision_feedback references prev SHA

**Files:**
- Modify: `agents/Solver - Issues/claim_issue.py`
- Modify: `agents/Solver - Issues/tests/test_claim_issue.py`

- [ ] **Step 1: Write failing test**

Find the existing `test_prompt_includes_revision_feedback_when_present` in `tests/test_claim_issue.py`. Add this assertion at the end:

```python
    assert "/tmp/prev-solver-sha" in prompt
    assert "git show" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_claim_issue.py::test_prompt_includes_revision_feedback_when_present -v
```

Expected: FAIL with `AssertionError`.

- [ ] **Step 3: Update _build_prompt's revision_section**

Replace the existing `revision_section` block in `claim_issue.py` `_build_prompt`:

```python
    revision_section = ""
    if issue.get("revision_feedback"):
        revision_section = (
            "\n## Previous attempt was rejected\n"
            "Stefan's feedback on the last fix attempt:\n"
            f"> {issue['revision_feedback']}\n\n"
            "Your previous commit's SHA is in `/tmp/prev-solver-sha` (if "
            "non-empty). Read it and run `git show <sha>` from inside "
            "`./client-repo/` to see exactly what you changed last time. "
            "The branch ref has been reset to the production HEAD, so the "
            "commit is no longer on `cms-preview`, but the object is still "
            "in `.git/objects` and `git show` works.\n\n"
            "Use that diff to understand what you did, then address "
            "Stefan's feedback this time.\n"
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd "agents/Solver - Issues" && python -m pytest tests/test_claim_issue.py -v
```

Expected: PASS for all 3 prompt tests.

- [ ] **Step 5: Commit**

```bash
git add "agents/Solver - Issues/claim_issue.py" "agents/Solver - Issues/tests/test_claim_issue.py"
git commit -m "feat(solver/prompt): revision_feedback references /tmp/prev-solver-sha

After Task 1's reset, the previous solver commit is no longer on
cms-preview's branch ref, but the object remains in .git/objects.
Prompt now instructs the agent to git show that SHA to inspect the
rejected diff."
```

---

## Task 4: Docs — phase files + AGENTS.md

**Files:**
- Modify: `agents/Solver - Issues/phases/2-clone.md`
- Modify: `agents/Solver - Issues/phases/4-push.md`
- Modify: `agents/Solver - Issues/AGENTS.md`

- [ ] **Step 1: Rewrite phases/2-clone.md**

Replace entire content:

```markdown
# Phase 2 — Clone + Reset

**Goal:** Clone the client repo and reset the working tree to the production branch HEAD, locally tracked as `cms-preview`.

**Inputs:**
- `/tmp/issue.json` (from Phase 1) — includes `project.github_repo`, `project.repo_branch` (= `cms-preview`), `project.production_branch` (= `main` or `master`).
- `SOLVER_GITHUB_TOKEN`.

**Steps:**
1. Read repo + both branches from `/tmp/issue.json`.
2. `git clone --depth 50 --no-single-branch --branch <prod_branch> <auth-url> ./client-repo`.
3. Configure git user as `Solver Agent <solver@roman-technologies.dev>`.
4. `git fetch --depth 50 origin <dev_branch>` (best-effort; OK if branch missing).
5. If fetch succeeded: write `git rev-parse origin/<dev_branch>` to `/tmp/prev-solver-sha`. Otherwise write empty string.
6. `git checkout -B <dev_branch> origin/<prod_branch>` — working tree now matches production HEAD, on a local branch named `cms-preview`.

**Why reset?** Production may have moved forward of `cms-preview` (Stefan committed directly to `main`/`master`). Resetting guarantees the S1.5 listener can fast-forward production to `cms-preview` after the agent commits, regardless of any drift.

**Outputs:**
- `./client-repo/` at `origin/<prod_branch>` HEAD, branch `cms-preview` checked out.
- `/tmp/prev-solver-sha` — previous `cms-preview` SHA (empty on first run).

**Failure messages:**
- 401/403 on clone → PAT scope drift; surface "git clone failed: <code>".
- 404 on clone → repo missing; surface "Repo not found".
- Fetch of `<dev_branch>` failing is non-fatal (first-run); prev-sha just stays empty.
```

- [ ] **Step 2: Rewrite phases/4-push.md**

Replace entire content:

```markdown
# Phase 4 — Push

**Goal:** Commit agent's file changes and force-with-lease push to `cms-preview`.

**Inputs:** `./client-repo/` working tree, `SOLVER_GITHUB_TOKEN`.

**Steps:**
1. If `/tmp/agent-status.md` exists → skip push, mark failed.
2. `git -C client-repo diff --quiet`. If exit 0 (no diff) → mark failed.
3. Otherwise:
   - `git add -A`.
   - Commit with message `fix: <issue.title>\n\nAutomated fix by Solver Agent for CMS issue <id>.\n\nCo-Authored-By: Solver Agent (Claude Code) <solver@roman-technologies.dev>`.
   - Capture HEAD SHA.
   - `git push --force-with-lease origin HEAD`.

**Why --force-with-lease?** Phase 2 reset `cms-preview` to production HEAD, rewriting its history. A plain push would be rejected as non-fast-forward. `--force-with-lease` is safer than `--force`: it only overwrites the remote if the remote ref matches our pre-push expectation (i.e., the SHA we saved in `/tmp/prev-solver-sha`, or empty for first-run). If another solver run or Stefan pushed to `cms-preview` between our clone and our push, the lease fails and we surface a clear error instead of stomping on their work.

**Outputs:** New commit on `cms-preview`, parent = production HEAD.

**Failure messages:**
- Push 403 → PAT scope drift; surface to release step.
- Push rejected (lease failed) → another writer touched `cms-preview` mid-run; surface "cms-preview moved during run, retry on next tick".
```

- [ ] **Step 3: Update AGENTS.md**

Find this row in the Pipeline table:

```markdown
| 2 | Clone | [phases/2-clone.md](./phases/2-clone.md) | Shallow clone client repo at `cms-preview` |
```

Replace with:

```markdown
| 2 | Clone | [phases/2-clone.md](./phases/2-clone.md) | Clone + reset `cms-preview` to production HEAD; save prev SHA |
```

Find this row:

```markdown
| 4 | Push | [phases/4-push.md](./phases/4-push.md) | Commit + push the fix to `cms-preview` |
```

Replace with:

```markdown
| 4 | Push | [phases/4-push.md](./phases/4-push.md) | Commit + force-with-lease push to `cms-preview` |
```

In the "Hard rules — what the agent must NOT do" section, add this bullet at the end:

```markdown
- Treat `cms-preview` as a long-lived branch. It is reset to production HEAD at the start of every solver run — any direct commits to `cms-preview` (from Stefan or anywhere outside the solver) WILL be overwritten. If Stefan needs to hotfix, he commits to the production branch (`main`/`master`) and the next solver run picks it up.
```

In "Modifying this agent", add:

```markdown
If you change Phase 2 reset logic: keep `phases/2-clone.md` in sync with `clone_repo.py` + `repo.clone_and_reset_to_prod`. The `production_branch` column on `projects` is the source of truth — do not hardcode `main` or `master`.
```

- [ ] **Step 4: Commit**

```bash
git add "agents/Solver - Issues/phases/2-clone.md" "agents/Solver - Issues/phases/4-push.md" "agents/Solver - Issues/AGENTS.md"
git commit -m "docs(solver): Phase 2 reset + Phase 4 force-with-lease push"
```

---

## Task 5: PR + smoke

**Files:** none (operational)

- [ ] **Step 1: Push branch + open PR**

```bash
git push -u origin fix/solver-cms-preview-reset
gh pr create --base dev --title "fix(solver): reset cms-preview to prod HEAD before run; force-with-lease push" --body "..."
```

PR body should mention: prevents the diverged/cannot-fast-forward deploy failures, uses existing `production_branch` column, no migration.

- [ ] **Step 2: Wait CI green + admin squash-merge to dev**

```bash
gh pr checks <number> --watch
gh pr merge <number> --squash --delete-branch --admin
```

Auto-merge handles dev→master.

- [ ] **Step 3: Submit a fresh smoke issue**

User submits via dashboard. Or reset an existing one in Supabase.

- [ ] **Step 4: Trigger workflow**

```bash
gh workflow run "Solver Agent (S3)" --ref master
```

- [ ] **Step 5: Verify reset happened**

```bash
gh run view <id> --log | grep -E "(reset cms-preview|force-with-lease|prev-solver-sha)"
```

Expect: clone + reset visible in clone step, force-with-lease in finalize step.

- [ ] **Step 6: Verify production deploy works**

Stefan reacts ✅ on Slack. Listener fast-forwards production to `cms-preview`. No "diverged" error.

```bash
gh api "repos/<owner>/<repo>/compare/<prod_branch>...cms-preview" --jq '{ahead: .ahead_by, behind: .behind_by, status: .status}'
```

Expect: `ahead: 0, behind: 0, status: "identical"` (or `behind: 0` after listener fires).

- [ ] **Step 7: Verify it-global-services + Laurian both deploy clean over multiple cycles**

Submit one issue per project, accept on both, confirm no divergence error. This is the real validation that the fix sticks.

---

## Self-Review

### Spec coverage
- Reset `cms-preview` to prod HEAD before agent runs → Task 1 (`clone_and_reset_to_prod`) + Task 2 (wire-through).
- Save previous SHA so revision-feedback retry can inspect it → Task 1 (writes `/tmp/prev-solver-sha`) + Task 3 (prompt references it).
- Force-with-lease push on `cms-preview` → Task 1 (`commit_and_push` change).
- First-run case (cms-preview doesn't exist) → Task 1 (`git checkout -B` creates the branch; fetch failure handled non-fatally).
- Race protection (listener / parallel writer) → Task 1 (`--force-with-lease`).
- Convention documented → Task 4 (AGENTS.md Hard rules).
- End-to-end validation → Task 5.

### Placeholders
- None. All shell commands, code blocks, and commit messages are concrete.

### Type / signature consistency
- `clone()` is removed in Task 1; `clone_and_reset_to_prod()` replaces it. `clone_repo.py` (Task 2) updated to call the new name. Tests in Task 1 cover the new signature. No remaining references to the old `clone(repo, branch, dest)` signature.
- `commit_and_push()` signature unchanged — internal behaviour change only (force-with-lease).
- `production_branch` is already returned by `db.fetch_project` → safe to reference as `project["production_branch"]` in `clone_repo.py`.

All consistent.
