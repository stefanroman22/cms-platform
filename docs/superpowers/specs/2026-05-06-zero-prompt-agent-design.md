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

`cmsk_<env>_<32 base64url chars>`

- `<env>` is `dev` or `prod`, sourced from the bootstrap script's
  `--env` flag (default: `dev`). The split is informational — the
  backend doesn't enforce which keys hit which deployment.
- Generated via `secrets.token_urlsafe(24)` → ~32 chars after
  trimming padding.
- The first 12 chars (e.g. `cmsk_dev_a1b2`) are stored in
  `key_prefix` for audit/listing UI; the full key is shown ONCE at
  creation, never again.

### Auth dependency

`backend/auth_service/services/admin_keys.py` (new):

```python
def verify_admin_api_key(plain_key: str) -> dict | None:
    """Returns the user row if `plain_key` matches an active key,
    else None. Updates last_used_at on success."""
    if not plain_key.startswith("cmsk_"):
        return None
    sb = get_supabase_admin()
    rows = (
        sb.table("admin_api_keys")
        .select("id, user_id, key_hash, expires_at, scopes, "
                "users(email, is_admin, is_active)")
        .is_("revoked_at", "null")
        .or_(f"expires_at.is.null,expires_at.gt.{now_iso()}")
        .execute()
    ).data or []
    ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
    for row in rows:
        try:
            ph.verify(row["key_hash"], plain_key)
        except VerifyMismatchError:
            continue
        # Match — verify the user is still admin + active
        u = row["users"]
        if not (u and u["is_admin"] and u["is_active"]):
            return None
        sb.table("admin_api_keys").update({"last_used_at": now_iso()}).eq("id", row["id"]).execute()
        return {"id": row["user_id"], **u}
    return None
```

`backend/auth_service/routers/auth_deps.py` adds:

```python
async def admin_user_via_bearer_or_sid(
    request: Request,
    sid: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict:
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
    # Fall back to existing sid-cookie path:
    if not sid:
        raise HTTPException(401, "Not authenticated")
    return require_admin_via_sid(sid)  # the existing dep, factored out
```

Every existing admin route swaps its current `Depends(require_admin)`
for `Depends(admin_user_via_bearer_or_sid)`. No semantic change for
the dashboard (which keeps sending the sid cookie); agents now have
a header-based path that doesn't depend on the browser session
machinery.

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

### Endpoint 1: welcome email

`POST /admin/clients/{email}/welcome`
- **Auth**: `Depends(admin_user_via_bearer_or_sid)`
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

### Endpoint 2: project ownership transfer

`POST /admin/projects/{slug}/transfer`
- **Auth**: same dep
- **Body**: `{ to_user_email: str }`
- **Behaviour**:
  1. Resolve target user by email; 404 if not found.
  2. UPDATE `projects` SET `user_id` = target WHERE `slug` = `slug`.
  3. Return updated project row.

These two endpoints absorb every direct call the agent currently
makes against Resend or the Supabase Management API. The backend
already has `RESEND_API_KEY` and the Supabase service-role key on
its Vercel env (verified in Subsystem 1's manual smoke).

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
| `backend/auth_service/routers/auth_deps.py` | MOD | 1 | `admin_user_via_bearer_or_sid()` dep |
| `backend/auth_service/routers/admin_*.py` (existing admin routers) | MOD | 1 | Swap dep |
| `backend/auth_service/routers/admin_clients.py` | MOD | 2 | New welcome endpoint |
| `backend/auth_service/routers/admin_projects.py` | MOD | 2 | New transfer endpoint |
| `backend/auth_service/services/welcome_email.py` | NEW | 2 | Welcome HTML template |
| `backend/auth_service/tests/test_admin_keys.py` | NEW | 1 | Unit tests |
| `backend/auth_service/tests/test_admin_welcome.py` | NEW | 2 | Unit tests |
| `backend/auth_service/tests/test_admin_transfer.py` | NEW | 2 | Unit tests |
| `backend/auth_service/tests_integration/test_admin_keys.py` | NEW | 1 | Integration tests |
| `backend/auth_service/tests_integration/test_admin_delegation.py` | NEW | 2 | Integration tests |
| `scripts/mint_admin_api_key.py` | NEW | 1 | Operator bootstrap |
| `agents/CMS Connector - Website/.env.example` | NEW | 3 | Token template |
| `agents/CMS Connector - Website/requirements.txt` | MOD | 3 | `python-dotenv` |
| `agents/CMS Connector - Website/scan.py` | MOD | 3 + 4 | Loader + refactor |
| `agents/CMS Connector - Website/AGENTS.md` | MOD | 4 | Credentials table |
| `agents/CMS Connector - Website/phases/4-integration.md` | MOD | 4 | Replace Resend + Supabase steps |
| `agents/CMS Connector - Website/phases/6-confirmation.md` | MOD | 4 | Replace Resend + Supabase steps |
| `agents/CMS Connector - Website/tests/test_scan_*.py` | MOD | 4 | Update mocks for new auth header |

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
