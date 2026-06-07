# CMS Platform — Security

This folder is the **living source of truth for the security posture of the CMS platform**.
It is built to compound: every review reconciles against it, so over time it tracks what's
broken, what's been fixed, and what's been judged not-a-problem — and it tells a future
reviewer (human or agent) exactly what to scan and how.

## Status snapshot — last full review **2026-06-07**

| Critical | High | Medium | Low | Info | Confirmed total | Dismissed (false-positive) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | **3** | **10** | **31** | **10** | **55** | 14 |

All findings are currently **`open`** (this is the baseline review — nothing fixed yet).

### The three things to fix first
1. **`SEC-001` (critical)** — Client issue text → LLM with `Bash(node:*)` + write tokens on the Solver CI runner = **prompt-injection → RCE**, exfiltrating the Claude OAuth token and the cross-tenant `SOLVER_GITHUB_TOKEN`, and pushing attacker code to client repos. One authenticated issue submission is enough.
2. **`SEC-002`/`SEC-003` (high)** — same injection class in the Solver agent prompt (shared push-capable token), and **anon/authenticated can EXECUTE the `SECURITY DEFINER` `claim_*_solver_issue` RPCs** (unauthenticated cross-tenant issue disclosure + pipeline DoS via the public Supabase anon key).
3. **`SEC-004` (high)** — Booking owner can create a booking against **another tenant's `resource_id`** (cross-tenant calendar DoS via the global GiST exclusion constraint).

## How to read this folder

| File | What it is |
|---|---|
| [`FINDINGS.md`](./FINDINGS.md) | **The live tracker.** Every finding's ID, severity, location, and **status**. Start here. |
| [`findings/critical.md`](./findings/critical.md) · [`high.md`](./findings/high.md) · [`medium.md`](./findings/medium.md) · [`low.md`](./findings/low.md) · [`info.md`](./findings/info.md) | Full detail per finding: description, attack scenario, real code evidence, adversarial verification, exploitability, remediation. |
| [`dismissed.md`](./dismissed.md) | Candidate findings **adversarially verified as false positives** — recorded so we don't re-litigate them. |
| [`methodology.md`](./methodology.md) | How a review is run: architecture facts, the 14 dimensions, severity scale, ID scheme, process. |
| [`scope-checklist.md`](./scope-checklist.md) | The concrete file/area inventory to scan. **Grows with the app.** |
| [`scheduled-review-prompt.md`](./scheduled-review-prompt.md) | The self-contained ultra-effort prompt the **weekly Saturday 08:00** review runs. |
| [`review-log.md`](./review-log.md) | Dated log of each review run (what was scanned, what changed). |

## How this review was produced

A 14-dimension multi-agent workflow (find → **adversarial verification** → synthesize): 84 agents,
one finder per security dimension scanning frontend, backend, services, workflows, agents, scraper,
and the live Supabase/Vercel state via MCP. **Every finding was independently re-verified by a
skeptical agent that re-read the cited code** and defaulted to *false-positive* unless the code
supported the claim — that's why 14 candidates were dismissed and the 55 survivors cite real
`file:line` + code evidence. The recurring methodology and the weekly automation live in this folder
so the next review starts from here, not from scratch.

## Scope reviewed
Frontend (Next.js 16, incl. the embeddable booking widget) · Backend (FastAPI: 15 routers, 30+ services,
core auth/session/limiter) · 26 SQL migrations + live Supabase RLS/RPC/advisor state
(`xeluydwpgiddbamysgyu`) · 8 GitHub Actions workflows · 4 AI agents (CMS Connector, Solver, Design
Prompt, Website Builder) · the lead scraper · dependencies/supply-chain · Vercel deployment posture.

---

## Executive summary (2026-06-07)

> Verbatim from the review's synthesis agent.

### Overall posture

This platform's internet-facing edges (auth, public forms, the booking widget, PostgREST) are
generally fail-closed and well-tested, but the **agentic/CI automation layer is the dominant risk
theme** and it is materially exposed. The single highest-impact path is a client-to-runner pipeline
where authenticated tenants submit free-form issue text that flows verbatim into an LLM wielding
`Bash(node:*)` and write-scoped tokens — turning ordinary prompt injection into credential theft and
code-push into client repos. A second concentrated weakness is **Supabase `SECURITY DEFINER`
functions/tables exposed to the public `anon` key**, which yields unauthenticated cross-tenant reads
and pipeline DoS today. The bulk of the remaining findings are low/info defense-in-depth gaps
(unescaped HTML in owner/tenant emails, self-owned XSS chains, supply-chain hardening) where blast
radius is bounded by ownership, human approval gates, or email-client sandboxing. **Net: not broadly
exploitable by anonymous attackers, but one authenticated tenant account plus the automation layer is
enough to reach platform secrets and other tenants.**

### Systemic themes (fix as a class, not one-off)

- **No data/instruction separation for untrusted text fed to LLMs** — spans the critical RCE, the
  Solver token-exfil/force-push, the CMS Connector scan prompt, the Design-Prompt writeback XSS, and
  Slack mrkdwn injection. Client/scraped content is concatenated verbatim into prompts with no
  fencing. Fix: nonce-fenced data blocks + system guards, strip secrets from the agent's reach, and a
  machine-checked diff-policy gate before any push/promote.
- **`SECURITY DEFINER` + public `anon` grants on Supabase** — `claim_*_solver_issue`,
  `slack_processed_events` (RLS off + anon DML), `tenant_rls_status` view, mutable `search_path`. All
  stem from assuming "no frontend Supabase client ⇒ anon is unreachable" — false, PostgREST is
  internet-reachable with the public key. Fix: `REVOKE EXECUTE/ALL FROM anon, authenticated, PUBLIC`,
  RLS default-deny, pin `search_path=''`, + a CI assertion (since `CREATE OR REPLACE` restores grants).
- **Missing tenant-scoped validation on body-supplied resource IDs (IDOR)** — booking cross-tenant
  write + cross-tenant resource-link both trust client `resource_id`(s) without membership checks. Fix:
  validate every inbound resource ID against the tenant's eligible set + composite tenant-scoped FKs.
- **Unescaped HTML interpolated into outbound emails** — form keys/values, booking brand chrome, and
  `email_copy` overrides interpolate raw while sibling templates escape. Fix: one
  `html.escape()`-on-interpolation helper for every template.
- **Rate-limiting that doesn't hold on serverless** — per-process counters, no per-account lockout,
  attacker-controlled `X-Forwarded-For`, unlimited expensive booking/availability endpoints. Fix:
  shared-store limiter, per-account backoff, trusted-proxy XFF position, hard span caps.
- **Supply-chain trust without a human/lockfile gate** — Dependabot auto-merge to prod, scraper deps
  unpinned, two unpinned CI actions. Fix: hold auto-merge for non-patch ranges, hash-pin + lockfile
  the scraper, SHA-pin all actions.

### Recommended remediation order

1. **Sever the injection→secrets path on the Solver/runner** (`SEC-001` + the two high agent findings) —
   remove `Bash(node:*)`/npm executors, strip `SOLVER_GITHUB_TOKEN`/`CLAUDE_CODE_OAUTH_TOKEN` from the
   injectable process, add nonce-fenced data/instruction separation. Depends on nothing; collapses the
   worst three at once.
2. **Lock down the Supabase `anon` surface** — `REVOKE EXECUTE … FROM anon, authenticated, PUBLIC` on
   both `claim_*` functions, enable RLS on `slack_processed_events`, tighten `tenant_rls_status`. Add
   the CI assertion so `CREATE OR REPLACE` can't silently regress it.
3. **Add a diff-policy + visible-diff approval gate** before prod promotion (closes the blind-✅ force-push path).
4. **Fix tenant-scoped resource validation** (booking IDOR + link) — schema change, sequence after step 2.
5. **Harden rate-limiting as a unit** — shared store, per-account backoff, XFF fix, availability span caps.
6. **Escape all outbound email templates** — one shared `html.escape()` helper; closes four findings.
7. **Tighten the supply-chain pipeline** — human review for non-patch bumps, hash-pin scraper, SHA-pin actions.
8. **Sweep remaining defense-in-depth/info items** — constant-time cron-secret compares, `sort`-column
   allowlist, scope credentialed CORS, admin-key rotation, manage-token expiry, CSP, purge committed scraper PII.
