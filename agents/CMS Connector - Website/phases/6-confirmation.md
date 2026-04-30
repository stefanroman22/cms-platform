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

UPDATE `projects.user_id` to the new client's user id, via Supabase Management API SQL:

```sql
UPDATE projects SET user_id = '<new_user_id>' WHERE slug = '<project_slug>' RETURNING id, slug, user_id;
```

The previous owner (developer admin account) keeps access via `is_admin` — admin endpoints scope by admin flag, not ownership.

### 6.4 — Send welcome email via Resend

POST to `https://api.resend.com/emails` with bearer auth using `RESEND_API_KEY`. Use the HTML template below. Set:
- `from`: `"Roman Technologies <noreply@roman-technologies.dev>"` (or whatever domain is verified in Resend)
- `to`: `[<client_email>]`
- `subject`: `"Your new website is ready — IT Global Services"` (substitute project name)
- `reply_to`: developer admin email (so the client can reply with questions)

#### HTML template (compact, inline styles, no external images other than the logo)

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#27272a">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f4;padding:40px 20px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border:1px solid #e4e4e7;border-radius:12px;overflow:hidden">

        <!-- Brand band -->
        <tr><td style="background:#18181b;padding:24px 32px">
          <table cellpadding="0" cellspacing="0">
            <tr>
              <td style="vertical-align:middle;padding-right:12px">
                <!-- Inline SVG: Layers mark, white on black -->
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                  <polyline points="2 17 12 22 22 17"></polyline>
                  <polyline points="2 12 12 17 22 12"></polyline>
                </svg>
              </td>
              <td style="vertical-align:middle">
                <p style="margin:0;color:#fff;font-size:18px;font-weight:600;letter-spacing:-0.01em">Roman Technologies</p>
                <p style="margin:2px 0 0;color:#a1a1aa;font-size:12px">Client Portal</p>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Greeting -->
        <tr><td style="padding:32px 32px 8px">
          <h1 style="margin:0 0 12px;font-size:22px;font-weight:600;color:#18181b">Your new website is live.</h1>
          <p style="margin:0;font-size:15px;line-height:1.55;color:#52525b">
            Hi {client_first_name_or_there},<br><br>
            Your <strong>{project_name}</strong> website has been deployed and connected to the Roman Technologies CMS.
            You can now sign in and edit any text, image, or service on the site directly — no developer needed.
          </p>
        </td></tr>

        <!-- Credentials -->
        <tr><td style="padding:8px 32px">
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;background:#fafafa;border:1px solid #e4e4e7;border-radius:8px">
            <tr><td style="padding:18px 22px">
              <p style="margin:0 0 12px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#71717a">Sign-in details</p>
              <table cellpadding="0" cellspacing="0" style="font-size:14px;line-height:1.5">
                <tr>
                  <td style="padding:4px 12px 4px 0;color:#52525b;width:100px">Username</td>
                  <td style="font-family:'SF Mono',Menlo,Consolas,monospace;color:#18181b">{client_email}</td>
                </tr>
                <tr>
                  <td style="padding:4px 12px 4px 0;color:#52525b">Password</td>
                  <td style="font-family:'SF Mono',Menlo,Consolas,monospace;color:#18181b">{generated_password}</td>
                </tr>
                <tr>
                  <td style="padding:4px 12px 4px 0;color:#52525b">Login URL</td>
                  <td><a href="https://roman-technologies.dev/log-in" style="color:#2563eb;text-decoration:none">https://roman-technologies.dev/log-in</a></td>
                </tr>
              </table>
            </td></tr>
          </table>
          <p style="margin:14px 0 0;font-size:13px;line-height:1.5;color:#b45309;background:#fef3c7;border-left:3px solid #f59e0b;padding:10px 14px;border-radius:0 6px 6px 0">
            <strong>Action required:</strong> please change your password the first time you sign in (Account Settings → Change Password).
          </p>
        </td></tr>

        <!-- CTA -->
        <tr><td style="padding:24px 32px 8px" align="center">
          <a href="https://roman-technologies.dev/log-in" style="display:inline-block;background:#18181b;color:#fff;text-decoration:none;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px">Sign in to your dashboard →</a>
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding:32px 32px 28px;border-top:1px solid #f4f4f5;margin-top:24px">
          <p style="margin:0;font-size:12px;color:#a1a1aa;line-height:1.5">
            Questions? Reply directly to this email.<br>
            © {year} Roman Technologies · Client Portal
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
```

Replace `{...}` placeholders before sending.

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
