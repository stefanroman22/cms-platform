# Zero-Prompt CMS Connector Agent — Architecture Design

## Goal

The CMS Connector — Website agent currently requires the operator to
re-supply six credentials on every invocation: a GitHub PAT, a Vercel
PAT, a Supabase Management PAT, a Resend API key, an Anthropic API
key, and a short-lived CMS admin **session cookie** copied out of
DevTools after a fresh login. The cookie alone is friction enough to
discourage running the agent regularly. We want the agent to run with
zero credential prompts after a one-time bootstrap.

End state: a single per-agent `.env` (gitignored) holds four
long-lived tokens; the backend issues a long-lived admin API key
that replaces the session cookie; backend admin endpoints absorb the
two operations the agent was doing directly against external
services (Resend welcome email, Supabase Management project-row
work) so those secrets never leave the backend's Vercel env.

## Why this design

**Professional**: each long-lived secret is hashed at rest in the
database (argon2id, same parameters as user passwords), is
individually revocable, has an audit timestamp (`last_used_at`),
carries a human-readable `name`, and uses a Stripe-style prefix
(`cmsk_dev_…` vs `cmsk_prod_…`) so a leaked key is unambiguous about
which environment it can access. No secret ever logs in plaintext.

**Scalable**: the admin-key model accommodates additional agents (a
second agent down the road gets its own key, separate from the CMS
Connector's). Per-key `scopes` (JSON) is a forward hook for narrower
permissions when a future agent only needs a subset of admin
routes — start with a single `agent` scope and extend without a
schema migration. The auth dependency is additive on the backend
(Bearer or sid), so the dashboard's existing session flow keeps
working untouched.

**Minimal blast radius**: removing Resend and Supabase Management
secrets from the agent's surface means a compromised laptop only
exposes GitHub + Vercel write access (already mitigated by GitHub
fine-grained token scopes and Vercel project scoping) plus the
admin API key (revocable in seconds via SQL or a future UI).

## Architecture

Four subsystems, ordered so each phase produces independently
shippable, independently testable software:

1. **Admin API key auth** (backend-only)
2. **Delegation endpoints** (backend-only; depends on 1 for auth)
3. **Per-agent `.env` loader** (agent-only; independent of 1+2 — agent
   keeps using sid cookie until phase 4 lands)
4. **Agent refactor** (agent-only; depends on 1, 2, 3)

Each subsystem section below ends with a **Testing matrix** spelling
out what passes/fails locally vs. against production.

---

## Subsystem 1 — Backend admin API key auth

### Schema

Migration `backend/migrations/2026_05_06_admin_api_keys.sql`:

```sql
CREATE TABLE admin_api_keys (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key_hash      text NOT NULL,
  key_prefix    text NOT NULL,                 -- "cmsk_dev_a1b2..." (first 12 chars)
                                                -- shown in audit views; full key never stored
  name          text NOT NULL,
  scopes        jsonb NOT NULL DEFAULT '["agent"]'::jsonb,
  last_used_at  timestamptz,
  expires_at    timestamptz,                   -- nullable; null = never expires
  created_at    timestamptz NOT NULL DEFAULT now(),
  revoked_at    timestamptz,
  CONSTRAINT admin_api_keys_unique_prefix UNIQUE (key_prefix)
);

-- Active-key fast lookup: WHERE revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())
CREATE INDEX admin_api_keys_active
  ON admin_api_keys (user_id)
  WHERE revoked_at IS NULL;
```

### Key format

`cmsk_<env>_<lookup>_<32 base64url chars>`

Three structural parts so the verifier can avoid argon2-iterating
over every active key on every request:

1. `<env>` — `dev` or `prod`, sourced from the bootstrap script's
   `--env` flag (default: `dev`). Informational only; the backend
   does not enforce which env hits which deployment.
2. `<lookup>` — 16 base64url chars from `secrets.token_urlsafe(12)`.
   Used as the lookup index against `admin_api_keys.key_prefix`. NOT
   secret on its own (can't be used to authenticate without the
   secret half) but uniquely identifies which row to argon2-verify
   against.
3. `<secret>` — 32 base64url chars from `secrets.token_urlsafe(24)`.
   The high-entropy half. Argon2-hashed at rest.

The full key shown to the operator at creation is the concatenation
of all three parts, e.g.
`cmsk_dev_a1b2c3d4e5f6g7h8_zXyV9wRk7Pj4mN2qLh8bGsDcF6tT1nM3`.
Stored in DB: `key_prefix = "a1b2c3d4e5f6g7h8"` (the lookup half) and
`key_hash = argon2(<secret>)` (just the secret half). The constant
prefix `cmsk_<env>_` is reconstructable from context and not stored.

### Auth dependency

`backend/auth_service/services/admin_keys.py` (new):

```python
def verify_admin_api_key(plain_key: str) -> dict | None:
    """Returns the user row if `plain_key` matches an active,
    non-expired, non-revoked key. Updates last_used_at on success.

    Lookup strategy: parse the lookup half out of the plain key, fetch
    that ONE candidate row by key_prefix, argon2-verify the secret
    half against key_hash. Constant-time per request regardless of
    how many keys exist in the table.
    """
    parts = plain_key.split("_")
    # Expect: ["cmsk", "<env>", "<lookup>", "<secret>"]
    if len(parts) != 4 or parts[0] != "cmsk" or parts[1] not in {"dev", "prod"}:
        return None
    lookup, secret = parts[2], parts[3]

    sb = get_supabase_admin()
    res = (
        sb.table("admin_api_keys")
        .select("id, user_id, key_hash, expires_at, scopes, "
                "users(email, is_admin, is_active)")
        .eq("key_prefix", lookup)
        .is_("revoked_at", "null")
        .maybe_single()
        .execute()
    )
    row = res.data if res else None
    if not row:
        return None
    if row.get("expires_at") and row["expires_at"] <= now_iso():
        return None

    ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
    try:
        ph.verify(row["key_hash"], secret)
    except VerifyMismatchError:
        return None

    u = row["users"]
    if not (u and u["is_admin"] and u["is_active"]):
        return None
    sb.table("admin_api_keys").update({"last_used_at": now_iso()}).eq("id", row["id"]).execute()
    return {"id": row["user_id"], **u}
```

**Centralisation of `_require_admin`** — today the function lives
twice (once in `backend/auth_service/routers/workspace.py:60` and
once in `backend/auth_service/routers/publish.py:177`), both
implementing the same sid-cookie check. Subsystem 1 also factors
that out into a single shared module so the new Bearer path doesn't
have to be duplicated. The new file is
`backend/auth_service/services/admin_auth.py`:

```python
async def require_admin_via_sid(request: Request) -> dict:
    """The pre-existing sid-cookie path, hoisted from workspace.py /
    publish.py so the new Bearer dep can fall back to it without
    duplicating logic."""
    # body: copy verbatim from workspace.py:_require_admin
    ...

async def admin_user_via_bearer_or_sid(request: Request) -> dict:
    """Auth gate for admin routes. Accepts EITHER a sid cookie OR an
    Authorization: Bearer cmsk_… header. Bearer wins if both are
    present (session cookies aren't expected on agent-driven calls)."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        plain = auth_header.split(" ", 1)[1].strip()
        user = verify_admin_api_key(plain)
        if user:
            return user
        raise HTTPException(401, "Invalid or revoked admin API key")
    return await require_admin_via_sid(request)
```

`workspace.py:60` and `publish.py:177` lose their local
`_require_admin` and import `admin_user_via_bearer_or_sid` from
`admin_auth`. Every existing `await _require_admin(request)` call
becomes `await admin_user_via_bearer_or_sid(request)`. Semantic
behaviour for the dashboard (which keeps sending the sid cookie) is
identical; agents now have a Bearer path.

**CORS implication**: the production backend's CORS config must
include `Authorization` in `allow_headers`. Verify and, if absent,
add — most FastAPI CORS configs default to `["*"]` for headers,
which already covers it, but spell-check it explicitly.

**Dashboard regression test**: the dashboard never sends an
`Authorization` header. After the swap, the dashboard's existing
admin pages (All Clients, All Projects, Service Types) must still
load. Captured in the testing matrix below.

### Bootstrap script

`scripts/mint_admin_api_key.py` — interactive operator script:

1. Reads `SUPABASE_*` from `backend/.env` (uses the existing helper
   pattern from `seed_e2e.py`).
2. Prompts: admin email (must exist in `users` with `is_admin=true`),
   key name (free text, e.g. "cms-connector-agent"), env tier
   (`dev`/`prod`, default `dev`), expiry (none / 90 / 180 / 365
   days, default none).
3. Generates `cmsk_<env>_<random>`, computes argon2 hash, INSERTs row
   with `key_prefix` = first 12 chars.
4. Prints the key ONCE in an obvious banner, instructs operator to
   copy it into the agent's `.env` immediately.

### Testing matrix — Subsystem 1

| Test | Local | Production |
|---|---|---|
| **Unit**: `verify_admin_api_key()` with valid key returns user | pytest mocked Supabase | n/a (pure unit) |
| **Unit**: `verify_admin_api_key()` with bad/revoked/expired key returns None | pytest mocked Supabase | n/a |
| **Unit**: argon2 hashing produces verifiable hash | pytest | n/a |
| **Integration (backend `tests_integration/`)**: mint key via SQL fixture, hit `/admin/projects` with Bearer header → 200 | pytest pointing at local uvicorn | pytest pointing at `cms-backend-roman.vercel.app` (gated by `E2E_ADMIN_API_KEY` GH secret minted from production Supabase) |
| **Integration**: revoked key returns 401 | as above | as above |
| **Manual smoke**: run `mint_admin_api_key.py` against local backend.env, curl admin endpoint with returned key | yes | re-run script with prod backend.env, repeat curl against prod URL |

CI hook: the existing `e2e.yml` workflow's `backend-integration` job
gains the new tests. New GH Actions secret `E2E_ADMIN_API_KEY` is
minted once against production Supabase, stored encrypted, used by CI
on every push to dev/master.

---

## Subsystem 2 — Backend delegation endpoints

All three new endpoints live in `backend/auth_service/routers/workspace.py`
(matches the existing convention of grouping admin routes there) and
use the new `admin_user_via_bearer_or_sid` dep from Subsystem 1.

### Endpoint 1: project row create

`POST /admin/projects`
- **Auth**: `Depends(admin_user_via_bearer_or_sid)`
- **Body**: `{ slug, name, owner_email, github_repo? }`
- **Behaviour**:
  1. Resolve `owner_email` → user_id; 404 if not found.
  2. Reject if a project with `slug` already exists (409). Idempotent
     re-runs use PATCH on the existing slug, not POST.
  3. INSERT into `projects` with `user_id`, `name`, `slug`,
     `is_active=true`, `github_repo` if provided.
  4. Return the inserted row.

This endpoint **must exist** before agent migration: today the agent
relies on Supabase Management API SQL to insert the project row
(documented in `phases/4-integration.md`). Without this endpoint the
agent has no Bearer-auth path to create rows.

### Endpoint 2: welcome email

`POST /admin/clients/{email}/welcome`
- **Auth**: same dep
- **Body**: `{ project_slug: str, project_name: str, website_url: str }`
- **Behaviour**:
  1. Lookup `users` by email; 404 if not found.
  2. Render welcome email HTML via the new
     `backend/auth_service/services/welcome_email.py` template (move
     verbatim from `agents/CMS Connector - Website/phases/6-confirmation.md`
     so the source of truth lives next to the code that sends it).
  3. POST to `https://api.resend.com/emails` with backend's existing
     `RESEND_API_KEY` env var.
  4. On Resend 4xx → return 502 with the Resend body inlined.
  5. On success → `200 {"success": true, "resend_id": "<id>"}`.

### Endpoint 3: project ownership transfer

`POST /admin/projects/{slug}/transfer`
- **Auth**: same dep
- **Body**: `{ to_user_email: str }`
- **Behaviour**:
  1. Resolve target user by email; 404 if not found.
  2. UPDATE `projects` SET `user_id` = target WHERE `slug` = `slug`.
  3. Return updated project row.

These three endpoints absorb every direct call the agent currently
makes against Resend or the Supabase Management API. The backend
already has `RESEND_API_KEY` and the Supabase service-role key on
its Vercel env (verified in Subsystem 1's manual smoke). Local dev
backend requires `RESEND_API_KEY` in `backend/.env`; if absent the
welcome endpoint returns 503 with a clear "RESEND_API_KEY not
configured on this backend" message rather than 500.

### Testing matrix — Subsystem 2

| Test | Local | Production |
|---|---|---|
| **Unit**: welcome endpoint with mocked Resend returns 200 | pytest | n/a |
| **Unit**: welcome endpoint with Resend 422 returns 502 | pytest | n/a |
| **Unit**: transfer endpoint updates `projects.user_id` | pytest mocked Supabase | n/a |
| **Unit**: transfer endpoint with unknown email returns 404 | pytest | n/a |
| **Integration**: POST `/admin/clients/<e2e-user>/welcome` with `[E2E-TEST]` body, Resend returns success | local uvicorn → real Resend (sandbox FROM domain `noreply@roman-technologies.dev`, TO `e2e-user@cms-test.dev`) | prod uvicorn, same body |
| **Integration**: POST `/admin/projects/<e2e-test-project>/transfer` to e2e-admin then back to e2e-user (round trip preserves seed state) | local | prod via E2E suite |

The integration tests live in `backend/auth_service/tests_integration/`,
gated by the `integration` marker so unit CI stays fast. Production
tests run in the existing `e2e.yml` workflow.

---

## Subsystem 3 — Per-agent `.env` loader

### Files

- `agents/CMS Connector - Website/.env.example` (new):
  ```bash
  # CMS Connector — Website agent. Copy to .env (gitignored) and fill
  # in the four long-lived tokens.

  # GitHub PAT with `repo` scope (and `workflow` if pushing CI files).
  # https://github.com/settings/tokens?type=beta
  GITHUB_TOKEN=

  # Vercel PAT, full account scope.
  # https://vercel.com/account/tokens
  VERCEL_TOKEN=

  # Anthropic API key for the Phase 2 LLM scan. Optional if the
  # `claude` CLI is on PATH.
  # https://console.anthropic.com/settings/keys
  ANTHROPIC_API_KEY=

  # CMS admin API key, format: cmsk_<env>_<32 chars>. Minted once via
  # scripts/mint_admin_api_key.py — see docs/SECURITY.md for rotation.
  CMS_ADMIN_API_KEY=

  # Backend base URL (no trailing slash). Defaults to production if
  # omitted.
  CMS_API_URL=https://cms-backend-roman.vercel.app
  ```
- `agents/CMS Connector - Website/.gitignore` already covers
  `**/.env` via the root `.gitignore`. No change.
- `agents/CMS Connector - Website/requirements.txt` adds
  `python-dotenv>=1.0.0`.
- `agents/CMS Connector - Website/scan.py` — at the very top of the
  file, after stdlib imports and before any `click` decorators or
  module-level code that reads env, add:
  ```python
  from dotenv import load_dotenv
  from pathlib import Path
  load_dotenv(Path(__file__).parent / ".env")
  ```
  Click's `envvar=` lookup happens at decoration evaluation time, so
  the load-dotenv call must execute before `@click.option(...)` is
  imported. Putting it at the top of the module guarantees this.

### Why per-agent, not shared

`backend/.env` exists already and could be reused. We don't, for two
reasons:
1. The agent will some day live outside this repo (extracted into a
   pip-installable tool). Coupling its runtime to a sibling backend
   directory locks that move.
2. Each agent will eventually have its OWN admin API key (one
   revocation per agent). Sharing `backend/.env` would force all
   future agents to share one key — exactly the antipattern this
   plan removes.

### Testing matrix — Subsystem 3

| Test | Local | Production |
|---|---|---|
| `.env` filled, no shell env: agent picks up all 4 tokens | manual run + `--help` showing values resolved | n/a |
| Shell env set + `.env` empty: shell wins (dotenv `override=False`) | manual | n/a |
| `.env` missing: agent falls back to shell env or fails with clear message | pytest in agent test suite | n/a |
| Bad `CMS_ADMIN_API_KEY`: agent first call returns 401 with a clear remediation | manual against local backend | manual against prod |

This subsystem touches no backend code; "production" testing here
just means running the agent with `CMS_API_URL` pointed at the
production backend.

---

## Subsystem 4 — Agent refactor

Once Subsystems 1–3 land, refactor `scan.py` and the phase docs:

### scan.py changes

- Replace every `Cookie: access_token=<sid>` header (in `_resolve_client`,
  `_provision`, `_vercel_setup`, etc.) with
  `Authorization: Bearer <admin_key>`.
- Add `--admin-key` CLI option with `envvar="CMS_ADMIN_API_KEY"`.
- Remove the `--api-token` flag (dashboard sid path) — the agent
  doesn't need it once the admin key path lands. The dashboard
  itself keeps using the sid cookie path; only this agent migrates.
- Remove the direct Resend POST in Phase 6 → POST
  `/admin/clients/{email}/welcome` instead. Drop the Resend imports
  and the `RESEND_API_KEY` requirement.
- Remove the direct Supabase Management calls in Phase 4 (project-row
  insert) and Phase 6 (ownership transfer) → POST `/admin/projects`
  (existing CMS endpoint) and POST `/admin/projects/<slug>/transfer`
  (new, from Subsystem 2). Drop the `SUPABASE_ACCESS_TOKEN`
  requirement.

### Documentation changes

- `agents/CMS Connector - Website/AGENTS.md` "Required credentials"
  table shrinks from 6 rows to 4:

  | Tool | Var | Used in |
  |------|-----|---------|
  | GitHub | `GITHUB_TOKEN` | 1, 4 |
  | Anthropic Claude | `claude` CLI preferred; `ANTHROPIC_API_KEY` fallback | 2, 5 |
  | Vercel | `VERCEL_TOKEN` | 4 |
  | CMS admin | `CMS_ADMIN_API_KEY` (`cmsk_<env>_…`) | 4, 5, 6 |

  Resend + Supabase rows move to a new "Backend-only credentials"
  block with an explanatory note: those secrets live on the backend's
  Vercel env, not on the agent's host.

- Phase doc updates:
  - `phases/4-integration.md`: replace the "set Resend env on backend
    Vercel project" step with "verify backend `RESEND_API_KEY` is
    set; if missing, halt — backend was supposed to be configured
    before agent runs". Replace the project-row insert with a POST
    to `/admin/projects`.
  - `phases/6-confirmation.md`: replace the inline Resend POST
    template with a single POST to `/admin/clients/{email}/welcome`.
    Replace the Supabase Management ownership-transfer SQL with a
    POST to `/admin/projects/<slug>/transfer`.

### Testing matrix — Subsystem 4

| Test | Local | Production |
|---|---|---|
| **Unit**: `_resolve_client` sends `Authorization: Bearer …`, not `Cookie:` | pytest with mocked `_http` | n/a |
| **Unit**: Phase 6 welcome step POSTs to `/admin/clients/{email}/welcome`, not Resend | pytest | n/a |
| **Unit**: Phase 4 project-row insert POSTs to `/admin/projects`, not Supabase | pytest | n/a |
| **End-to-end smoke** (single short-lived test client): provision a sandbox repo through the agent, watch all 6 phases finish with no token prompts beyond the existing functional ones | local backend, sandbox client | rerun against prod backend with prod admin key, sandbox client repo deleted afterward |
| **Welcome email arrives** in operator's inbox | local (Resend dashboard shows local-origin send) | prod |
| **Ownership transferred** in Supabase `projects.user_id` | confirm via SQL | confirm via Supabase prod dashboard |

---

## File summary

| File | Type | Subsystem | Purpose |
|------|------|-----------|---------|
| `backend/migrations/2026_05_06_admin_api_keys.sql` | NEW | 1 | Schema |
| `backend/auth_service/services/admin_keys.py` | NEW | 1 | `verify_admin_api_key()`, hashing |
| `backend/auth_service/services/admin_auth.py` | NEW | 1 | `require_admin_via_sid()` (factored out) + `admin_user_via_bearer_or_sid()` |
| `backend/auth_service/routers/workspace.py` | MOD | 1 + 2 | Drop local `_require_admin` + import shared dep + add 3 new endpoints (POST /admin/projects, POST /admin/projects/{slug}/transfer, POST /admin/clients/{email}/welcome) |
| `backend/auth_service/routers/publish.py` | MOD | 1 | Drop local `_require_admin` + import shared dep |
| `backend/auth_service/services/welcome_email.py` | NEW | 2 | Welcome HTML template |
| `backend/auth_service/tests/test_admin_keys.py` | NEW | 1 | Unit tests for `verify_admin_api_key` |
| `backend/auth_service/tests/test_admin_auth_dep.py` | NEW | 1 | Unit tests for the auth dep (Bearer + sid + fallback) |
| `backend/auth_service/tests/test_admin_welcome.py` | NEW | 2 | Welcome endpoint unit |
| `backend/auth_service/tests/test_admin_transfer.py` | NEW | 2 | Transfer endpoint unit |
| `backend/auth_service/tests/test_admin_create_project.py` | NEW | 2 | Create-project endpoint unit |
| `backend/auth_service/tests_integration/test_admin_keys.py` | NEW | 1 | Integration tests against live backend |
| `backend/auth_service/tests_integration/test_admin_delegation.py` | NEW | 2 | Integration: create + welcome + transfer |
| `scripts/mint_admin_api_key.py` | NEW | 1 | Operator bootstrap |
| `agents/CMS Connector - Website/.env.example` | NEW | 3 | Token template |
| `agents/CMS Connector - Website/requirements.txt` | MOD | 3 | `python-dotenv` |
| `agents/CMS Connector - Website/scan.py` | MOD | 3 + 4 | Loader + refactor (Bearer everywhere; new admin endpoints) |
| `agents/CMS Connector - Website/AGENTS.md` | MOD | 4 | Credentials table shrinks 6 → 4 |
| `agents/CMS Connector - Website/phases/4-integration.md` | MOD | 4 | POST /admin/projects + POST /admin/clients/{email}/welcome |
| `agents/CMS Connector - Website/phases/6-confirmation.md` | MOD | 4 | POST /admin/clients/{email}/welcome + POST /admin/projects/{slug}/transfer |
| `agents/CMS Connector - Website/tests/test_scan_*.py` | MOD | 4 | Update mocks for Bearer header + new endpoint URLs |

## Functionality preservation matrix

Every existing capability must work after migration. Each row maps an
old code path to its new equivalent and the test that proves it.

| Existing capability | Old path | New path | Test |
|---|---|---|---|
| Dashboard admin login | sid cookie via `/auth/login` | unchanged | E2E `02-login.spec.ts` |
| Dashboard "All Clients" page | sid cookie → `/admin/clients` | sid cookie → `/admin/clients` (same) | E2E `07-admin.spec.ts` |
| Dashboard "All Projects" page | sid cookie → `/admin/projects` | unchanged | E2E `07-admin.spec.ts` |
| Dashboard PATCH project | sid cookie → `PATCH /admin/projects/{slug}` | unchanged | manual smoke after deploy |
| Dashboard rotate preview token | sid cookie → `POST /admin/projects/{slug}/rotate-preview-token` | unchanged | manual smoke after deploy |
| Agent creates client account | sid cookie → `POST /admin/clients` | Bearer → `POST /admin/clients` | unit + integration |
| Agent looks up client by email | sid cookie → `GET /admin/clients/lookup` | Bearer → same | unit + integration |
| Agent creates project row | Supabase Management SQL INSERT | Bearer → `POST /admin/projects` (new) | unit + integration |
| Agent saves Vercel ids on project | sid cookie → `PATCH /admin/projects/{slug}` | Bearer → same | unit + integration |
| Agent creates services | sid cookie → `POST /projects/{slug}/services` | Bearer → same | E2E |
| Agent transfers project ownership | Supabase Management SQL UPDATE | Bearer → `POST /admin/projects/{slug}/transfer` (new) | unit + integration |
| Agent sends welcome email | Direct POST to api.resend.com with `RESEND_API_KEY` | Bearer → `POST /admin/clients/{email}/welcome` (new) | unit + integration |
| Public `/content/<slug>` reads | unauthenticated | unchanged | E2E backend integration |
| Public `/forms/<slug>/<form_key>` POST | unauthenticated | unchanged | E2E backend integration |
| `/auth/me`, `/auth/logout`, etc. | sid cookie | unchanged | E2E backend integration |

Phase 4 of the plan (rollout) ends only when EVERY row in this table
is verified green on production.

## Out of scope

- Token rotation automation. Manual: revoke old key in DB, mint new
  one, paste into `.env`.
- Encrypting `.env` at rest (`keyring`/Windows Credential Manager).
  Considered; deferred — the simplicity-vs-security trade is worse
  than the simplicity-vs-friction trade we're solving here.
- Removing `GITHUB_TOKEN` and `VERCEL_TOKEN` from the agent. Those
  services don't have a clean delegation pattern (Vercel has no
  "create-project-on-behalf-of" semantics; GitHub has installation
  tokens but they require a GitHub App which is its own multi-day
  project). Keep PATs.
- Migrating dashboard auth off the sid cookie. The cookie path
  remains; the new Bearer path is purely additive.
