# Disable Vercel Deployment Protection on Client Websites — Design

## Problem

Per-client website projects provisioned by the CMS Connector agent (one
Vercel project per client, e.g. `it-global-services`) inherit Vercel's
default "Vercel Authentication" deployment protection. Result: when a
CMS user clicks **See Preview** in our dashboard, the new tab opens the
Vercel deployment URL and shows a "Request Access" SSO gate instead of
the actual website. Clients cannot view their own preview without
holding a Vercel team invitation that they should not need.

## Goal

Every per-client website project — both currently-provisioned and
future ones — must serve **production and preview** deployments
publicly with no Vercel SSO gate and no password prompt. Our own infra
projects (`roman-technologies`, `cms-backend-roman`) are out of scope
for this change.

## Mechanism

Vercel exposes deployment protection on a project via the REST API:

```
PATCH /v9/projects/{idOrName}
Authorization: Bearer <VERCEL_TOKEN>
Content-Type: application/json

{"ssoProtection": null, "passwordProtection": null}
```

- `ssoProtection: null` removes Vercel Authentication (the SSO gate).
- `passwordProtection: null` removes the shared-password gate. Belt
  and suspenders — most client projects never enabled it, but the
  PATCH is idempotent so listing both fields is harmless.
- The PATCH applies to **production and preview** deployments alike.
  It is the only project-level toggle Vercel offers; there is no way
  to leave preview-deployments protected while opening production.
- Idempotent: re-PATCHing a project whose protection is already `null`
  returns 200 OK with no change.

The Vercel MCP cannot be used. The user's account has no team
(`list_teams` returns empty), so MCP tools that require a `teamId`
fail. All API calls in this design go through `urllib.request`.

## Filter rule for "per-client website project"

Hardcoding project names is brittle — `cms-frontend-roman` was renamed
to `roman-technologies` on 2026-05-06 and a name-based denylist would
have silently started PATCHing the production frontend. Filter by
GitHub repo link instead:

- `GET /v9/projects` returns each project's `link.repo` (e.g.
  `"stefanroman22/cms-platform"` for our monorepo, or
  `"stefanroman22/it-global-services"` for a client website).
- **Skip** any project whose `link.repo == "stefanroman22/cms-platform"`.
  That covers both `roman-technologies` and `cms-backend-roman`
  in one rule and survives future renames.
- **Belt-and-suspenders**: also skip a project whose `name` matches
  `roman-technologies` or `cms-backend-roman`, so a misconfigured
  project missing its repo link still cannot accidentally be opened.

Pseudocode:

```python
INFRA_REPO = "stefanroman22/cms-platform"
INFRA_NAMES = {"roman-technologies", "cms-backend-roman"}

def is_infra(project: dict) -> bool:
    link = project.get("link") or {}
    repo = f"{link.get('org', '')}/{link.get('repo', '')}".strip("/")
    if repo == INFRA_REPO:
        return True
    if project.get("name") in INFRA_NAMES:
        return True
    return False
```

## Two surfaces of change

### Surface 1 — Retrofit script

**File:** `scripts/disable_vercel_auth.py` (NEW)

One-shot script that walks every Vercel project the token can see and
disables deployment protection on per-client ones.

Behaviour:
1. Read `VERCEL_TOKEN` from env. Exit 1 with a clear message if missing.
2. `GET /v9/projects?limit=100`, follow `pagination.next` until null.
3. For each project, classify via `is_infra(project)` above.
4. For non-infra projects: PATCH with `{"ssoProtection": null,
   "passwordProtection": null}`.
5. Log one line per project. Exit 0 on full success; per-project 403 /
   404 errors logged but do not abort the whole run.

Output shape:

```
🔓 Disabling Vercel deployment protection

  - skip roman-technologies (infra: matches monorepo repo link)
  - skip cms-backend-roman (infra: matches monorepo repo link)
  ✓ it-global-services protection disabled
  ✓ <next client project> protection disabled

Done. 1 skipped, 2 patched, 0 errors.
```

Run:
```bash
export VERCEL_TOKEN=<personal access token from https://vercel.com/account/tokens>
python scripts/disable_vercel_auth.py
```

### Surface 2 — Agent project-creation flow

**Files:**
- `agents/CMS Connector - Website/vercel.py` (MOD)
- `agents/CMS Connector - Website/phases/<provisioning phase>` (MOD)
- `agents/CMS Connector - Website/tests/test_vercel.py` (MOD)

Add a new helper to `vercel.py`:

```python
def disable_deployment_protection(token: str, project_id: str) -> None:
    """Disables Vercel Authentication + Password Protection on the
    given project. Idempotent — calling on a project that already has
    no protection is a no-op."""
    _request(
        token,
        "PATCH",
        f"/v9/projects/{project_id}",
        {"ssoProtection": None, "passwordProtection": None},
    )
```

Wire it into the orchestrator: immediately after `create_project()`
returns the new project id, call
`disable_deployment_protection(token, project_id)` **before** any env
vars are set or any deployment is triggered. Doing it first means the
very first deployment Vercel kicks off (when env vars + git link
finalise) is already public — no client ever sees the SSO gate.

The retrofit script and the agent helper share the exact same payload
shape; if Vercel ever adds a third protection field, both surfaces
need to be updated together.

### Tests

`agents/CMS Connector - Website/tests/test_vercel.py` gets a new test
that mocks the underlying HTTP layer and asserts:
- The PATCH URL is `/v9/projects/<project_id>`.
- The PATCH body is exactly `{"ssoProtection": None,
  "passwordProtection": None}`.
- The function returns without raising on a successful response.

The retrofit script does not need a unit test — it is a one-shot
operator script in the `scripts/` tier (same tier as `seed_e2e.py`,
which also has no tests). Manual verification is the test.

## Error handling

| Scenario | Behaviour |
|---|---|
| `VERCEL_TOKEN` not set | Script exits 1 immediately with a help message. |
| Bad token (401 from list call) | Script exits 1 — no per-project errors to swallow. |
| Per-project 403 (token lacks access to one project) | Log error line, continue with next project. |
| Per-project 404 (project deleted between list and patch) | Log error line, continue. |
| Vercel-side 5xx | Log error line, continue. Operator re-runs the script. |
| Project with no `link` (manually-created project) | Treated as non-infra unless its `name` matches the denylist. Operator-controlled fleet — the conservative default is to PATCH it (matches the user goal of "every per-client project"). |

## Verification

After the retrofit script runs, manually probe one of the client URLs:

```bash
curl -sI https://it-global-services.vercel.app/
```

Expected: `HTTP/2 200`, `content-type: text/html`. Old behaviour:
`HTTP/2 401` with a `Location` redirect to `vercel.com/sso-api`.

Repeat the probe right after the agent provisions a brand-new client
to confirm the in-line PATCH succeeded.

## Out of scope

- Updating `MEMORY.md` to replace the stale "Django backend" note —
  separate housekeeping.
- Updating the README architecture diagram to use the new project
  name `roman-technologies` in the box (currently still labelled
  `cms-frontend-roman`) — separate housekeeping.
- Vercel domain redirects (`cms-frontend-roman.vercel.app` →
  `roman-technologies.dev`) are configured at the Vercel domain
  level; deployment-protection PATCHes do not touch them.
- Production-vs-preview asymmetric protection — Vercel's API does not
  expose a preview-only knob, and the user goal is "no gate
  anywhere", so this question is settled by the API rather than by
  policy.
