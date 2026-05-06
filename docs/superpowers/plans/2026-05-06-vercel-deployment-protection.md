# Vercel Deployment Protection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disable Vercel Authentication + Password Protection on every per-client website project (existing + future) so CMS clients reach the live preview directly with no SSO gate.

**Architecture:** Two surfaces. (1) `scripts/disable_vercel_auth.py` — one-shot operator script that walks all Vercel projects via REST and PATCHes non-infra projects with `{"ssoProtection": null, "passwordProtection": null}`. (2) `agents/CMS Connector - Website/vercel.py` gets a new `disable_deployment_protection()` helper, called by `scan.py` immediately after `create_project()` so newly-provisioned clients ship public from the very first deploy. Filter rule for "is this an infra project?" matches by GitHub repo link (`stefanroman22/cms-platform`) plus name belt-and-suspenders, surviving future renames.

**Tech Stack:** Python 3.13 stdlib (`urllib.request`), pytest + unittest.mock for the agent test, Vercel REST API v9.

---

## Spec reference

Full design lives at `docs/superpowers/specs/2026-05-06-vercel-deployment-protection-design.md`. Read that for the why; this plan covers the how.

## File structure

| File | Type | Responsibility |
|------|------|----------------|
| `agents/CMS Connector - Website/vercel.py` | MODIFY | Append one new helper `disable_deployment_protection()`. ~10 lines. |
| `agents/CMS Connector - Website/tests/test_vercel.py` | MODIFY | Append one new test asserting PATCH URL + body. ~15 lines. |
| `agents/CMS Connector - Website/scan.py` | MODIFY | Insert one call site after `create_project()` returns. ~3 lines. |
| `agents/CMS Connector - Website/tests/test_scan_vercel_phase.py` | MODIFY | Tighten existing "create_project" test to also assert the new helper is called. ~3 lines. |
| `scripts/disable_vercel_auth.py` | CREATE | New one-shot retrofit script. ~120 lines. |

No new tests for the retrofit script — it follows the pattern of `scripts/seed_e2e.py` (operator-run, manual verification). Lint + ast-parse only.

---

## Task 1: Add `disable_deployment_protection()` helper

**Files:**
- Modify: `agents/CMS Connector - Website/vercel.py` (append below `set_env_var()`)
- Modify: `agents/CMS Connector - Website/tests/test_vercel.py` (append new test)

- [ ] **Step 1: Write the failing test**

Append to `agents/CMS Connector - Website/tests/test_vercel.py`:

```python
def test_disable_deployment_protection_patches_with_null_fields(fake_urlopen):
    """Both ssoProtection and passwordProtection must be sent as null
    in the PATCH body. Vercel returns the updated project on success."""
    fake_urlopen.return_value = _json_response(
        {"id": "prj_xyz", "ssoProtection": None, "passwordProtection": None}
    )

    vercel.disable_deployment_protection(token="tok", project_id="prj_xyz")

    call = fake_urlopen.call_args_list[0][0][0]
    assert call.method == "PATCH"
    assert call.full_url.endswith("/v9/projects/prj_xyz")
    body = json.loads(call.data.decode())
    assert body == {"ssoProtection": None, "passwordProtection": None}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "agents/CMS Connector - Website"
venv/Scripts/python.exe -m pytest tests/test_vercel.py::test_disable_deployment_protection_patches_with_null_fields -v
```
Expected: FAIL with `AttributeError: module 'vercel' has no attribute 'disable_deployment_protection'`.

If the agent's `venv/` doesn't exist, use the backend venv instead:
```bash
"../../backend/venv/Scripts/python.exe" -m pytest tests/test_vercel.py::test_disable_deployment_protection_patches_with_null_fields -v
```

- [ ] **Step 3: Add the helper to `vercel.py`**

Append after the `set_env_var()` function (the existing "Upserts a Vercel env var" helper) in `agents/CMS Connector - Website/vercel.py`:

```python
def disable_deployment_protection(token: str, project_id: str) -> None:
    """Disables Vercel Authentication (ssoProtection) and Password
    Protection on the given project.

    Vercel applies "Standard Protection" by default to new projects,
    which requires the visitor to log into a Vercel team to view the
    deployment. CMS clients are not Vercel team members, so we strip
    both protection types unconditionally. Idempotent — calling on a
    project that already has neither is a no-op.

    Affects production AND preview deployments — Vercel does not
    expose a per-environment toggle for this setting.
    """
    _request(
        token,
        "PATCH",
        f"/v9/projects/{project_id}",
        {"ssoProtection": None, "passwordProtection": None},
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
venv/Scripts/python.exe -m pytest tests/test_vercel.py::test_disable_deployment_protection_patches_with_null_fields -v
```
Expected: PASS.

- [ ] **Step 5: Run the whole test_vercel.py to confirm no regression**

```bash
venv/Scripts/python.exe -m pytest tests/test_vercel.py -v
```
Expected: 8 passed (7 existing + 1 new).

- [ ] **Step 6: Lint**

From repo root:
```bash
backend/venv/Scripts/python.exe -m ruff check "agents/CMS Connector - Website/vercel.py" "agents/CMS Connector - Website/tests/test_vercel.py"
backend/venv/Scripts/python.exe -m black --check "agents/CMS Connector - Website/vercel.py" "agents/CMS Connector - Website/tests/test_vercel.py"
```
Expected: both clean.

- [ ] **Step 7: Commit**

```bash
git add "agents/CMS Connector - Website/vercel.py" "agents/CMS Connector - Website/tests/test_vercel.py"
git commit -m "feat(agent/vercel): disable_deployment_protection() helper (PATCH ssoProtection+passwordProtection null)"
```

---

## Task 2: Wire the helper into the orchestrator

**Files:**
- Modify: `agents/CMS Connector - Website/scan.py:351-353`
- Modify: `agents/CMS Connector - Website/tests/test_scan_vercel_phase.py`

- [ ] **Step 1: Read the existing orchestrator block**

Current code at `agents/CMS Connector - Website/scan.py` around line 343:

```python
found = vercel.find_project_by_repo(vercel_token, github_repo)
if found:
    project_id = found["id"]
    prod_branch = found.get("production_branch") or github.get_default_branch(
        github_token, github_repo
    )
    click.echo(f"  ✓ Found existing Vercel project: {project_id} (prod branch: {prod_branch})")
else:
    project_id = vercel.create_project(vercel_token, name=slug, github_repo=github_repo)
    prod_branch = github.get_default_branch(github_token, github_repo)
    click.echo(f"  ✓ Created Vercel project: {project_id} (prod branch: {prod_branch})")
```

We will call the new helper in BOTH branches — newly-created projects need it, but found-existing projects also benefit (idempotent re-run on a previously-protected project will fix it). Doing both means re-running the agent on an old client implicitly retrofits that client.

- [ ] **Step 2: Write the failing test in `test_scan_vercel_phase.py`**

First read the existing file to understand the mocking pattern:

```bash
cat "agents/CMS Connector - Website/tests/test_scan_vercel_phase.py" | head -60
```

Find the existing test that mocks `mock_vercel` and asserts `mock_vercel.create_project.assert_called_once()`. We're going to add an assertion that `mock_vercel.disable_deployment_protection.assert_called_once_with(<token>, <project_id>)` is also true after the agent runs through Phase 4.

Edit the test that exercises the "creates a brand-new project" path (the one near `mock_vercel.create_project.return_value = "prj_abc"` at line 21). After the existing `mock_vercel.create_project.assert_called_once()` line, append:

```python
    mock_vercel.disable_deployment_protection.assert_called_once_with(
        "fake-vercel-token", "prj_abc"
    )
```

(Use whatever the test's existing token literal and project-id literal are — the values above match what's set near line 21.)

Also edit the test that exercises the "found existing project" path. After whatever `mock_vercel.find_project_by_repo` assertion exists in that test, add:

```python
    # Found-existing path also triggers the protection PATCH so re-running
    # the agent on a previously-protected client retrofits it.
    mock_vercel.disable_deployment_protection.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd "agents/CMS Connector - Website"
venv/Scripts/python.exe -m pytest tests/test_scan_vercel_phase.py -v
```
Expected: FAIL on the two assertions above (helper not called).

- [ ] **Step 4: Modify scan.py to call the helper in both branches**

In `agents/CMS Connector - Website/scan.py`, replace the block from line 343 through the closing `click.echo("  ✓ Created Vercel project: ...")` with:

```python
    found = vercel.find_project_by_repo(vercel_token, github_repo)
    if found:
        project_id = found["id"]
        prod_branch = found.get("production_branch") or github.get_default_branch(
            github_token, github_repo
        )
        click.echo(f"  ✓ Found existing Vercel project: {project_id} (prod branch: {prod_branch})")
    else:
        project_id = vercel.create_project(vercel_token, name=slug, github_repo=github_repo)
        prod_branch = github.get_default_branch(github_token, github_repo)
        click.echo(f"  ✓ Created Vercel project: {project_id} (prod branch: {prod_branch})")

    # Disable Vercel Authentication on every project we touch. Idempotent.
    # Doing this BEFORE env vars + deployment trigger means the very first
    # deployment is already public — no client ever sees the SSO gate.
    vercel.disable_deployment_protection(vercel_token, project_id)
    click.echo("  ✓ Vercel deployment protection disabled (public preview/production)")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
venv/Scripts/python.exe -m pytest tests/test_scan_vercel_phase.py -v
```
Expected: all tests pass (both modified assertions now satisfied).

- [ ] **Step 6: Run full agent suite to catch any other regression**

```bash
venv/Scripts/python.exe -m pytest tests/ -q
```
Expected: all green.

- [ ] **Step 7: Lint**

From repo root:
```bash
backend/venv/Scripts/python.exe -m ruff check "agents/CMS Connector - Website/scan.py" "agents/CMS Connector - Website/tests/test_scan_vercel_phase.py"
backend/venv/Scripts/python.exe -m black --check "agents/CMS Connector - Website/scan.py" "agents/CMS Connector - Website/tests/test_scan_vercel_phase.py"
```
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add "agents/CMS Connector - Website/scan.py" "agents/CMS Connector - Website/tests/test_scan_vercel_phase.py"
git commit -m "feat(agent/scan): call disable_deployment_protection after create_project (idempotent on re-run)"
```

---

## Task 3: Retrofit script

**Files:**
- Create: `scripts/disable_vercel_auth.py`

- [ ] **Step 1: Create the script**

Create `scripts/disable_vercel_auth.py` with this exact content:

```python
"""disable_vercel_auth.py — retrofit per-client Vercel projects.

Walks every Vercel project the configured token can see and disables
Vercel Authentication (ssoProtection) + Password Protection on each
non-infra project. Idempotent: re-running on a project that's already
public is a no-op.

Why: clients click "See Preview" in our CMS dashboard and land on the
deployed Vercel URL. Default Vercel project protection forces them
through a "Request Access" SSO gate. We don't want that — the deployed
preview is meant to be publicly viewable.

Filter: skip any project whose GitHub link points at our monorepo
(stefanroman22/cms-platform) — that covers `roman-technologies` and
`cms-backend-roman` in one rule and survives renames. Belt-and-
suspenders: also skip a project whose name matches the legacy infra
names so a misconfigured project missing its repo link is still safe.

Required env:
    VERCEL_TOKEN   Personal access token from
                   https://vercel.com/account/tokens

Run:
    python scripts/disable_vercel_auth.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.vercel.com"
INFRA_REPO = "stefanroman22/cms-platform"
INFRA_NAMES = {"roman-technologies", "cms-backend-roman"}


def _request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode() or "{}"
        return json.loads(raw)


def list_all_projects(token: str) -> list[dict]:
    """Pages through /v9/projects and returns every project the token can see."""
    projects: list[dict] = []
    path = "/v9/projects?limit=100"
    while True:
        data = _request(token, "GET", path)
        projects.extend(data.get("projects", []))
        pagination = data.get("pagination") or {}
        next_ts = pagination.get("next")
        if not next_ts:
            return projects
        path = f"/v9/projects?limit=100&until={next_ts}"


def is_infra(project: dict) -> tuple[bool, str]:
    """Returns (skip?, reason). Reason is empty when not skipped."""
    link = project.get("link") or {}
    repo = f"{link.get('org', '')}/{link.get('repo', '')}".strip("/")
    if repo == INFRA_REPO:
        return True, f"linked to monorepo {INFRA_REPO}"
    if project.get("name") in INFRA_NAMES:
        return True, f"name in infra denylist ({project['name']})"
    return False, ""


def disable_protection(token: str, project_id: str) -> None:
    _request(
        token,
        "PATCH",
        f"/v9/projects/{project_id}",
        {"ssoProtection": None, "passwordProtection": None},
    )


def main() -> int:
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        print(
            "error: VERCEL_TOKEN not set.\n"
            "       export it from https://vercel.com/account/tokens, then re-run.",
            file=sys.stderr,
        )
        return 1

    print("\n🔓 Disabling Vercel deployment protection\n")

    try:
        projects = list_all_projects(token)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"error: failed to list projects: {e.code} {body}", file=sys.stderr)
        return 1

    skipped = 0
    patched = 0
    errors = 0

    for proj in projects:
        name = proj.get("name", "<no name>")
        skip, reason = is_infra(proj)
        if skip:
            print(f"  - skip {name} ({reason})")
            skipped += 1
            continue
        try:
            disable_protection(token, proj["id"])
            print(f"  ✓ {name} protection disabled")
            patched += 1
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(
                f"  ✗ {name} ({proj['id']}): {e.code} {err_body[:200]}",
                file=sys.stderr,
            )
            errors += 1

    print(f"\nDone. {skipped} skipped, {patched} patched, {errors} errors.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Static checks**

The script reads `os.environ.get("VERCEL_TOKEN")` lazily inside `main()`, so it can be imported / parsed without env. Verify:

```bash
python -c "import ast; ast.parse(open('scripts/disable_vercel_auth.py').read())"
python -m py_compile scripts/disable_vercel_auth.py
```
Expected: no output, exit 0.

- [ ] **Step 3: Lint**

From repo root:
```bash
backend/venv/Scripts/python.exe -m ruff check scripts/disable_vercel_auth.py
backend/venv/Scripts/python.exe -m black --check scripts/disable_vercel_auth.py
```
Expected: both clean. If black reformats, run `backend/venv/Scripts/python.exe -m black scripts/disable_vercel_auth.py` and re-add.

- [ ] **Step 4: Commit**

```bash
git add scripts/disable_vercel_auth.py
git commit -m "build(scripts): disable_vercel_auth.py retrofits per-client Vercel projects (skip monorepo)"
```

---

## Task 4: Manual verification

**Files:** none (operator step)

This is the only test of the retrofit script. The agent helper is unit-tested in Task 1.

- [ ] **Step 1: Run the retrofit script**

```bash
export VERCEL_TOKEN=<personal access token from https://vercel.com/account/tokens>
python scripts/disable_vercel_auth.py
```

Expected output shape:
```
🔓 Disabling Vercel deployment protection

  - skip roman-technologies (linked to monorepo stefanroman22/cms-platform)
  - skip cms-backend-roman (linked to monorepo stefanroman22/cms-platform)
  ✓ it-global-services protection disabled
  ✓ <other client projects> protection disabled

Done. 2 skipped, N patched, 0 errors.
```

If a project shows `name in infra denylist` instead of `linked to monorepo`, that means its GitHub link is missing in Vercel — investigate the project but the skip is still correct.

- [ ] **Step 2: Probe a previously-gated client URL**

```bash
curl -sI https://it-global-services.vercel.app/ | head -5
```

Expected: `HTTP/2 200` and a `content-type: text/html` line.

Old/broken behaviour (what we're fixing):
- `HTTP/2 401` with a `set-cookie: _vercel_sso_nonce=...` line, or
- `HTTP/2 308` with `location: https://vercel.com/sso-api?url=...`.

If you still see 401/308, double-check the script printed `✓ it-global-services` (not skipped or errored), then wait ~30s for Vercel's edge to propagate and re-probe.

- [ ] **Step 3: Open the URL in an incognito browser tab**

Same URL, no Vercel session cookies. The actual website renders. No "Request Access" prompt, no Vercel header.

- [ ] **Step 4: (Optional, only if you provision a brand-new client soon) verify the agent path**

Run the CMS Connector agent on a new client, watch the orchestrator log emit:
```
  ✓ Vercel deployment protection disabled (public preview/production)
```
Then probe the new project's `*.vercel.app` URL exactly as in Step 2.

- [ ] **Step 5: No commit needed**

Manual-only step; no files changed.

---

## Self-review

**Spec coverage:**

| Spec section | Covered by |
|---|---|
| Vercel API mechanism (PATCH ssoProtection + passwordProtection null) | Task 1 helper, Task 3 script |
| Filter rule (repo link + name belt-and-suspenders) | Task 3 `is_infra()` function |
| Surface 1 — retrofit script | Task 3 |
| Surface 2 — agent flow | Tasks 1 + 2 |
| Pagination of `/v9/projects` | Task 3 `list_all_projects()` |
| Per-project 403/404 → log + continue | Task 3 main loop's try/except |
| Bad token → exit 1 | Task 3 main: `_request` raises HTTPError on 401, caught at the top-level list call |
| Idempotency | Built-in: PATCH with the same null body is a no-op. Verified by re-running script. |
| Verification (curl probe) | Task 4 step 2 |
| Tests asserting PATCH body shape | Task 1 step 1 |

No gaps.

**Placeholder scan:** No "TBD", "TODO", "implement later", "similar to Task N", or vague "handle edge cases" — every step shows the exact code or command. Test code is fully written. Commit messages are spelled out.

**Type consistency:**
- Helper name: `disable_deployment_protection(token, project_id)` everywhere (Task 1 implementation, Task 1 test, Task 2 orchestrator call site, Task 2 test assertions).
- Script function name: `disable_protection()` inside `disable_vercel_auth.py` (different name on purpose — the script's helper is internal, not exposed). No collision.
- Constants: `INFRA_REPO`, `INFRA_NAMES` in the script match the spec verbatim.
- Project name `it-global-services` used consistently in verification steps.
