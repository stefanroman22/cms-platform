# Phase 6 — Client onboarding, confirmation & cleanup

**Goal:** Hand the project off to the actual client — create their CMS account, transfer project ownership, send a welcome email — then clean up temp files.

## Inputs (collected at the start of this phase)

- **Client email** — prompt the user once. The agent has been running with the developer's account as the project owner; this phase reassigns ownership.
- **`RESEND_API_KEY`** — required for the welcome email. If not set in env, prompt for it. (Future: replace with a backend `POST /admin/clients/{email}/welcome` endpoint that uses the backend's existing `RESEND_API_KEY` env var so the agent never sees the secret.)

If either is missing, halt this phase. Do not invent emails. Do not skip the welcome email.

## Steps

### 6.1 — Prompt for client email

Wait for the user to reply with the actual client's email. Validate it's a well-formed email; re-prompt if not.

### 6.2 — Create the client account

Call `POST /admin/clients` with `{"email": "<client>", "full_name": "<optional>"}`.
- If the response has `created: true`, capture `generated_password` — this is the **one and only chance** to read it. Never log it to disk.
- If `created: false`, the account already existed; re-issue a password reset via `POST /auth/admin/reset-password` (or surface a clear message asking the user to send a manual reset link if no admin reset endpoint exists).

### 6.3 — Transfer project ownership

POST to the backend admin API (NOT Supabase Management):

```http
POST {CMS_API_URL}/admin/projects/{project_slug}/transfer
Authorization: Bearer {CMS_ADMIN_API_KEY}
Content-Type: application/json

{"to_user_email": "<client_email>"}
```

200 = ownership transferred. The previous owner (developer admin
account) keeps access via `is_admin` — admin endpoints scope by
admin flag, not ownership.

### 6.4 — Send welcome email

POST to the backend (which uses its own RESEND_API_KEY env — the
agent never holds the secret):

```http
POST {CMS_API_URL}/admin/clients/{client_email}/welcome
Authorization: Bearer {CMS_ADMIN_API_KEY}
Content-Type: application/json

{
  "project_slug": "<project_slug>",
  "project_name": "<project_name>",
  "website_url": "<deployed website URL>"
}
```

200 with `{"success": true, "resend_id": "<id>"}` = email sent. 502 =
backend's RESEND_API_KEY misconfigured or Resend rejected; check the
detail field. 404 = client account doesn't exist (run Phase 6.1
first).

The agent no longer holds RESEND_API_KEY or RESEND_FROM_EMAIL.

### 6.5 — Cleanup

- Delete `agents/CMS Connector - Website/cms-integration-report.md`.
- Delete `agents/CMS Connector - Website/.last-llm-output.txt` if present.
- Delete any `/tmp/` provisioning helpers the run wrote.

### 6.6 — Final confirmation message in chat

> ✅ CMS integration complete for `<project_slug>`.
> • GitHub: `<repo URL>`
> • Production: `<production_url>`
> • Preview: `<preview_url>`
> • CMS dashboard: `<cms_dashboard_url>`
> • Client account: `<client_email>` (welcome email sent)
> • Project ownership transferred to client.

### 6.7 — Append to LEARNINGS.md

Under `## Successful runs`:
- `- <date>: <slug>. Owner = <client_email>. Welcome email sent. Phases 1–6 clean.`

LEARNINGS.md is **never** deleted.

## Token tactics

- Do not paste the welcome email body into chat. Print only "email sent to <addr>".
- Do not re-Read AGENTS.md or any other phase doc here.
- Single confirmation block, no per-phase recap.

## Self-improvement hook

If a sub-step fails (account create 409 vs "already exists" handled gracefully? ownership transfer fails because of FK constraint? Resend domain not verified for the from-address?), append a rule under `## Phase 6 — Onboarding rules`. Examples:
- `- 2026-04-29: Resend "from" domain must be verified BEFORE Phase 6 sends. Trigger: 403 from Resend on unverified domain.`
- `- 2026-04-29: When client account already exists, prompt user: reuse + send password-reset link, or abort. Trigger: 409 on /admin/clients.`
