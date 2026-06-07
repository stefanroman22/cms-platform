# Security Review Methodology

This document defines **how** a security review of the CMS platform is run, so every
review (manual or scheduled) is consistent, repeatable, and comparable over time.
It is the companion to:

- [`README.md`](./README.md) — entry point + current status
- [`FINDINGS.md`](./FINDINGS.md) — the live finding tracker (source of truth for status)
- [`scope-checklist.md`](./scope-checklist.md) — the concrete file/area checklist
- [`scheduled-review-prompt.md`](./scheduled-review-prompt.md) — the prompt the weekly agent runs

---

## 1. Architecture facts the review relies on

These are verified and should be re-confirmed (not re-derived) each review:

- **Backend**: FastAPI at `backend/auth_service` (Python 3.13, deployed via `@vercel/python`).
- **Frontend**: Next.js 16 App Router at `frontend/src/app` (Vercel).
- **DB/Auth/Storage**: Supabase Postgres — project ref **`xeluydwpgiddbamysgyu`** (name "CMS", eu-west-1).
- **The backend uses the Supabase SERVICE ROLE key** (`services/supabase_client.py`), which
  **bypasses Postgres RLS**. ⇒ **Object-level authorization is enforced in FastAPI app code,
  not in RLS.** RLS is defense-in-depth only. *Cross-tenant/IDOR bugs live in router/service code.*
- **The frontend has no direct Supabase client** (no `createClient` in `frontend/src`) — it calls the
  backend API. Browser-side DB access is not a vector; cookie/session handling + API authZ are.
- **Multi-tenant model: tenant == project.** Users own projects; clients access their project(s);
  admins are elevated. The booking module is multi-tenant (tenant = project).
- **Two FastAPI apps / CORS**: the main app (`allow_credentials=True`, methods `*`, configured origins)
  and a separate public **forms** sub-app (`allow_origins=["*"]`, credentials-less, POST/OPTIONS).
- **Vercel projects**: `cms-backend-roman` (backend) and `roman-technologies` (frontend). Slack/GitHub/
  Supabase env vars belong on `cms-backend-roman`, not the frontend project.

## 2. Dimensions (parallel scan axes)

Each review fans out **one agent per dimension**, in parallel, then **adversarially verifies**
every finding before it is recorded. The 14 dimensions:

| # | Dimension | Primary question |
|---|-----------|------------------|
| 1 | **AuthZ / IDOR / tenant ownership** | Does every endpoint check the caller owns the project/resource? (highest priority — service-role model) |
| 2 | **AuthN / sessions / cookies / JWT** | Can auth be bypassed, fixed, or replayed? Are cookies HttpOnly/Secure/SameSite? |
| 3 | **Admin privilege gating** | Is every admin route actually gated? Constant-time key compare? |
| 4 | **Public endpoints & token security** | Are booking/forms/manage-link/Slack tokens unguessable, scoped, expiring, signature-verified? |
| 5 | **XSS / HTML / email-template injection** | Does untrusted input reach HTML/JS unescaped (emails, `dangerouslySetInnerHTML`, widget)? |
| 6 | **Injection (SQL/command/template)** | PostgREST filter injection, raw SQL, subprocess/shell from user/model input? |
| 7 | **SSRF / outbound requests** | Are server-fetched URLs (scraper, connector, calendar, DeepL) host/scheme-validated? |
| 8 | **Secrets / config / CORS / logging** | Hardcoded secrets, secrets in logs/errors, over-broad CORS, weak headers? |
| 9 | **CI/CD workflows** | `pull_request_target` + untrusted checkout, `${{ }}` shell injection, auto-merge gates, token scope? |
| 10 | **AI agents** | Prompt injection from client sites / issue bodies driving privileged file/git/API actions? |
| 11 | **Scraper** | Path traversal, unsafe deserialization, resource exhaustion, trusted-by-backend scraped data? |
| 12 | **Supabase DB (RLS/RPC/definer)** | Public tables w/o RLS, security-definer views, anon-executable RPCs, function search_path? |
| 13 | **Dependencies / supply chain** | Vulnerable/unpinned deps, lockfile hashes, postinstall risk? |
| 14 | **Rate limiting / DoS** | Unauth endpoints without limits (booking/email spam, login brute force), serverless limiter resets? |

## 3. Severity scale

| Severity | Definition |
|----------|------------|
| **critical** | Unauthenticated RCE; auth bypass; **any user reading/modifying another tenant's data**; secret leak enabling takeover; SQLi with data access. |
| **high** | Authenticated priv-esc; cross-tenant IDOR (auth required); stored XSS in admin/other-user context; SSRF to internal/metadata; missing authZ on a sensitive mutation; webhook/manage-token signature bypass. |
| **medium** | Reflected XSS; CSRF on state change; sensitive info disclosure; weak/missing rate limiting enabling abuse; authZ on read but not write; predictable tokens; open redirect. |
| **low** | Hardening gaps; verbose errors; defense-in-depth; missing security headers. |
| **info** | Best-practice nit. |

## 4. Process

1. **Confirm architecture facts** (§1) and pull live state:
   - `mcp__supabase__get_advisors` (security **and** performance) on `xeluydwpgiddbamysgyu`.
   - `mcp__supabase__list_tables` / `execute_sql` (read-only) for RLS/GRANT/policy state.
   - `mcp__vercel__get_project` for `cms-backend-roman` (+ frontend) deployment/env posture.
2. **Fan out** the 14 dimensions as parallel finder agents (use the Workflow tool — ultra effort).
3. **Adversarially verify** every finding: a skeptical agent re-reads the cited code and
   defaults to *false_positive* unless the code genuinely supports the claim. Records an
   adjusted severity + concrete exploitability.
4. **Record** confirmed/partial findings in [`FINDINGS.md`](./FINDINGS.md) with a stable ID,
   severity, status, and location. Dismissed findings are logged (with reason) so future
   reviews don't re-litigate them.
5. **Re-verify open findings** from the previous review — has a fix landed? mark
   `fixed` (with the commit) or keep `open` / `in-progress`.
6. **Synthesize** an executive summary + dependency-aware remediation order.

## 5. Finding ID scheme

`SEC-<NNN>` — monotonic, never reused. Once assigned, an ID keeps its meaning across reviews
so status history is traceable. New findings continue the sequence.

## 6. Status values

`open` · `in-progress` · `fixed` · `accepted-risk` · `false-positive` · `wont-fix`

A `fixed` row must cite the commit/PR that fixed it. An `accepted-risk` row must cite who
accepted it and why.
