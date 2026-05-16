# Connector — Persist production_branch + Standardization Guideline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the CMS Connector agent persist the resolved production branch (`main`/`master`) into `projects.production_branch` so the Solver Agent reads accurate data. Document Option A standardization policy: new repos default to `main`, legacy `master` tolerated, no auto-renames.

**Architecture:** Connector already resolves `prod_branch` (Vercel productionBranch > GitHub default_branch) and creates `cms-preview` branch off it. Two missing wires: (1) backend `AdminProjectPatchIn` schema lacks `production_branch` field, so it would silently drop on PATCH; (2) Connector's PATCH body in `scan.py` doesn't include the field. Fix both, then document the policy.

**Tech Stack:** FastAPI + Pydantic v2 (backend schema), Python stdlib + click (Connector), Supabase Postgres. No DB migration (column exists). No new endpoints.

**Branch:** `feat/connector-persist-prod-branch` (off latest master).

---

## File Structure

**Modify:**
- `backend/auth_service/models/schemas.py` — add `production_branch` to `AdminProjectPatchIn` + `AdminProjectDetailOut`.
- `backend/auth_service/routers/workspace.py` — extend the GET `/admin/projects/{slug}` SELECT to return `production_branch`.
- `backend/auth_service/tests/test_workspace_save.py` — assert PATCH persists `production_branch`; assert GET returns it.
- `agents/CMS Connector - Website/scan.py` — include `production_branch` in PATCH body (line 422-433).
- `agents/CMS Connector - Website/phases/4-integration.md` — sub-step 6 "PATCH" lists `production_branch`.
- `agents/CMS Connector - Website/AGENTS.md` — new `## Branch standardization` section documenting Option A.

**No DB migration. No new endpoints. No new tests on the Connector — its PATCH is end-to-end smoked by Phase 5 of the Connector pipeline against a real backend.**

---

## Task 1: Backend schema + GET SELECT + tests

**Files:**
- Modify: `backend/auth_service/models/schemas.py`
- Modify: `backend/auth_service/routers/workspace.py`
- Modify: `backend/auth_service/tests/test_workspace_save.py`

- [ ] **Step 1: Write failing tests**

Open `tests/test_workspace_save.py`. Find `test_admin_patch_project_updates_vercel_fields` (around line 200). Add a new test right after it:

```python
def test_admin_patch_project_persists_production_branch(mock_supabase, client, auth_as, admin_user):
    """Connector calls this endpoint to record the repo's production branch
    so Solver agent can reset cms-preview to the right ref."""
    auth_as(admin_user)
    res = client.patch(
        "/admin/projects/demo",
        json={"production_branch": "main"},
    )
    assert res.status_code == 200
    update = mock_supabase.last_update_for("projects")
    assert update["production_branch"] == "main"


def test_admin_patch_project_accepts_master_branch(mock_supabase, client, auth_as, admin_user):
    """Legacy repos use master. Accept without judgment — see Option A guideline."""
    auth_as(admin_user)
    res = client.patch(
        "/admin/projects/demo",
        json={"production_branch": "master"},
    )
    assert res.status_code == 200


def test_admin_patch_project_rejects_empty_production_branch(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    res = client.patch(
        "/admin/projects/demo",
        json={"production_branch": ""},
    )
    # Empty string is rejected by min_length validator.
    assert res.status_code == 422
```

Then find `test_admin_get_project` (in same file). Add at the end of that test:

```python
    # Verify GET includes production_branch (added with the Solver Agent
    # cms-preview reset feature so admins can see what branch the agent
    # will reset to).
    payload = res.json()
    assert "production_branch" in payload
```

(Adjust the mock supabase fixture to include `production_branch` in the returned row if it doesn't already — check existing `_make_mock_supabase` or equivalent setup.)

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd backend && source venv/Scripts/activate && python -m pytest auth_service/tests/test_workspace_save.py::test_admin_patch_project_persists_production_branch -v
```

Expected: FAIL — Pydantic drops `production_branch` from `model_dump()` because the field doesn't exist on the model yet.

- [ ] **Step 3: Add production_branch to AdminProjectPatchIn**

In `schemas.py`, find `class AdminProjectPatchIn`. Add after the `website_url` field:

```python
    # Production branch (`main` for new repos per Option A guideline,
    # `master` tolerated for legacy repos). Persisted so the Solver
    # Agent's clone+reset path knows which ref to base cms-preview on.
    # Validated as a git-safe ref name fragment.
    production_branch: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("production_branch", mode="after")
    @classmethod
    def _safe_ref_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("production_branch cannot be empty")
        # Conservative ref-name allowlist — git refs allow more but we
        # don't need to: solver uses this in shell args, keep it boring.
        import re
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", v):
            raise ValueError("production_branch contains invalid characters")
        return v
```

- [ ] **Step 4: Add production_branch to AdminProjectDetailOut**

In `schemas.py`, find `class AdminProjectDetailOut`. Add after `github_repo`:

```python
    production_branch: str | None = None
```

- [ ] **Step 5: Extend GET SELECT in workspace.py**

In `routers/workspace.py`, find `admin_get_project` (line 439). Update the SELECT:

```python
        .select(
            "slug, name, github_repo, production_branch, vercel_project_id, "
            "production_url, preview_url, preview_token, last_published_at"
        )
```

- [ ] **Step 6: Run tests, verify they pass**

```bash
cd backend && source venv/Scripts/activate && python -m pytest auth_service/tests/test_workspace_save.py -v
```

Expected: PASS for all `production_branch`-related tests + no regression on existing tests.

- [ ] **Step 7: Commit**

```bash
git add backend/auth_service/models/schemas.py backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_save.py
git commit -m "feat(backend): admin PATCH/GET project accepts + returns production_branch

Connector resolves the repo's production branch (Vercel productionBranch
fallback to GitHub default_branch) but couldn't persist it because the
admin schema dropped the field. Now accepted, validated as a git-safe
ref name fragment, and surfaced via GET so admins can see what branch
the Solver Agent will reset cms-preview to.

See docs/superpowers/plans/2026-05-16-connector-persist-prod-branch.md
for the Option A standardization guideline."
```

---

## Task 2: Connector — include production_branch in PATCH

**Files:**
- Modify: `agents/CMS Connector - Website/scan.py`

- [ ] **Step 1: Update the PATCH body**

Find the PATCH at line 422-434 in `scan.py`. Add `production_branch` to the body:

```python
    # 6. Save to CMS project row via admin PATCH (base + headers defined at top)
    _http(
        "PATCH",
        f"{base}/admin/projects/{slug}",
        headers,
        {
            "github_repo": github_repo,
            "production_branch": prod_branch,
            "vercel_project_id": project_id,
            "production_url": production_url,
            "preview_url": preview_url,
            "preview_token": preview_token,
        },
    )
    click.echo(f"  ✓ Saved Vercel metadata to CMS project row (prod branch: {prod_branch})")
```

- [ ] **Step 2: Commit**

```bash
git add "agents/CMS Connector - Website/scan.py"
git commit -m "feat(connector): persist production_branch to CMS project row

Closes the wire from prod_branch resolution to the projects table so
Solver Agent's clone_and_reset_to_prod can read it. Reused the same
PATCH that already saves vercel_project_id and URLs — no new call."
```

---

## Task 3: Docs — Phase 4 + standardization guideline

**Files:**
- Modify: `agents/CMS Connector - Website/phases/4-integration.md`
- Modify: `agents/CMS Connector - Website/AGENTS.md`

- [ ] **Step 1: Update phases/4-integration.md sub-step 6**

Find sub-step 6 (PATCH) under "Vercel project setup". Change `PATCH the CMS project row with` line to:

```markdown
   - PATCH the CMS project row with `github_repo`, `production_branch` (resolved in step 2), `vercel_project_id`, `production_url`, `preview_url`, `preview_token`.
```

- [ ] **Step 2: Add Branch standardization section to AGENTS.md**

In `agents/CMS Connector - Website/AGENTS.md`, insert this section right after "Hard rules — what is / isn't a CMS service" and before "Generated client website contracts":

```markdown
## Branch standardization (Option A)

Two branches per client repo:

- **`<production_branch>`** — `main` for new repos (GitHub's default since 2020). Legacy repos with `master` are tolerated; we do not auto-rename. Solver Agent reads the resolved name from `projects.production_branch` so its clone+reset path is branch-agnostic.
- **`cms-preview`** — long-lived dev branch, solver-only. Auto-created from `<production_branch>` in Phase 4 (`github.create_branch`) if missing.

Policy:

- New repos: do not override GitHub's `default_branch`. Whatever the user's GitHub account default is (typically `main`), record it as `production_branch`.
- Legacy repos: when `default_branch == "master"`, accept it. Do not propose renaming inside this agent — branch renames break external PRs, CI badges, and downstream service hooks.
- The resolution order in [`scan.py`](./scan.py) `_vercel_setup` is **Vercel `productionBranch` first, then GitHub `default_branch`** — this lets the operator override per-project if needed without changing the GitHub repo itself.

Solver Agent reads `production_branch` from the `projects` table on every run. Phase 4 of this agent is responsible for writing it. If the value is `NULL` after a Connector run, the Solver run will fail at clone time — verify the Phase 4 PATCH log line `✓ Saved Vercel metadata to CMS project row (prod branch: <branch>)`.
```

- [ ] **Step 3: Commit**

```bash
git add "agents/CMS Connector - Website/phases/4-integration.md" "agents/CMS Connector - Website/AGENTS.md"
git commit -m "docs(connector): Branch standardization guideline (Option A)

Documents the two-branch convention (production_branch + cms-preview),
the new-repo policy (use GitHub default, typically main), legacy-master
tolerance, and the resolution order (Vercel > GitHub)."
```

---

## Task 4: Backfill existing projects + PR + smoke

**Files:** none (operational)

- [ ] **Step 1: Backfill the projects that currently have production_branch set manually**

```sql
-- Sanity check: confirm current values are sane before relying on Connector
-- to maintain them going forward.
SELECT slug, github_repo, production_branch FROM projects WHERE github_repo IS NOT NULL;
```

Expected: `it-global-services → main`, `Laurian-Duma → master`. No-op if so. Controller applies via Supabase MCP.

- [ ] **Step 2: Push branch + open PR**

```bash
git push -u origin feat/connector-persist-prod-branch
gh pr create --base dev --head feat/connector-persist-prod-branch \
  --title "feat(connector): persist production_branch + standardization guideline" \
  --body "..."
```

- [ ] **Step 3: Wait CI + admin squash-merge**

```bash
gh pr checks <number> --watch
gh pr merge <number> --squash --delete-branch --admin
```

- [ ] **Step 4: Smoke against a real repo (next Connector run)**

The next time Stefan runs the CMS Connector skill against a real folder, verify:
1. `prod_branch` resolved (Vercel > GitHub default).
2. `cms-preview` branch created from `prod_branch` if missing.
3. PATCH log shows `(prod branch: <branch>)`.
4. `SELECT production_branch FROM projects WHERE slug = '<new-slug>'` returns the resolved value.

Then run a Solver issue against the new repo to confirm end-to-end works (cms-preview reset reads `production_branch` correctly).

---

## Self-Review

### Spec coverage
- Persist `production_branch` to DB → Task 1 (schema) + Task 2 (Connector PATCH body).
- Standardization guideline → Task 3 (AGENTS.md new section + Phase 4 update).
- New repos use `main`, legacy `master` tolerated, no auto-renames → guideline language explicit.
- cms-preview auto-creation already shipped in Connector — no change needed.
- Solver Agent reads `production_branch` — already shipped (previous plan).
- Backfill check → Task 4 step 1.

### Placeholders
- None. All commands, code blocks, and schema additions are concrete.

### Type / signature consistency
- `AdminProjectPatchIn.production_branch` — `str | None`, validated.
- `AdminProjectDetailOut.production_branch` — `str | None`, matches.
- Connector PATCH body sends `prod_branch` (local var) which is a `str` returned by `github.get_default_branch` or Vercel's productionBranch — always a string, never None.
- DB column `projects.production_branch` already TEXT; backend `model_dump` strips None values so a None payload doesn't overwrite.

All consistent.
