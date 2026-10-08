# CMS Platform — Security

This folder is the **living source of truth for the security posture of the CMS platform**.
It is built to compound: every review reconciles against it, so over time it tracks what's
broken, what's been fixed, and what's been judged not-a-problem — and it tells a future
reviewer (human or agent) exactly what to scan and how.

## Status snapshot — last full review **2026-10-08** (branch `main`)

**Currently OPEN (actionable):**

| Critical | High | Medium | Low | Info | needs-decision |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **0** | **0** | **2** | **14** | **4** | **2** |

**Cumulative confirmed (all-time, incl. fixed/obsolete):** 74 · **Dismissed (false-positive):** 16.

The 2026-06-07 baseline's criticals/highs (`SEC-001`–`004`/`056`/`003`) are **fixed or obsolete**. The former
dominant risk theme — the agentic/CI **Solver** pipeline + the public Supabase **anon** surface (Slack/scraper) —
is **gone**: that code and its DB objects were removed (teardown 2026-08-26, DB drop applied 2026-09-27), obsoleting
~15 findings. The **2026-10-08** review found **no new critical/high** and confirmed the large new **rich-text /
ADR-0010** surface is sound (allow-list tree-rebuild + default-deny `safe_href`, not a filter). It added **6** findings
(2 medium, 4 low; all `open`) and flipped `SEC-024`/`SEC-046`→fixed and `SEC-067`→obsolete. See the 2026-10-08 note +
full table in [`FINDINGS.md`](./FINDINGS.md) and [`review-log.md`](./review-log.md).

> **⚠ MCP gap (2026-10-08):** this headless cloud run had **no Supabase/Vercel MCP** — the DB layer was reviewed from
> migration SQL + repo only. Live `get_advisors`/`execute_sql`/`get_project` state was **not** re-pulled; re-check on
> the next local run.

### The next things to fix (2026-10-08 remediation order)
1. **`SEC-069` (medium)** — the `.claude/hooks/guard.mjs` PreToolUse guard (CLAUDE.md's non-negotiable push-to-main / prod-SQL / no-verify hard stop) is bypassed by any `bash -c`/`sh -c` wrapper or `$VAR`/`$(…)` expansion. Recurse into interpreter wrappers / deny them in git+psql+supabase contexts, or document that the guard is advisory, not a security boundary.
2. **`SEC-070` (medium)** — add `Depends(_public_read_limit)` to the public booking `/{slug}/availability` read (the one sibling left off the shared limiter) and apply the `max_span_days` cap when `max_advance_days==0`.
3. **`SEC-060` (low)** — stop using tenant `email_copy` overrides as a `str.format` template (explicit `.replace()` of known keys; broaden the caught exceptions to include `MemoryError`/`OverflowError`).
4. **`SEC-071` (low)** — narrow `.gitleaks.toml`'s whole-tree `tests/`/`docs/` path allowlist to content-based exceptions so real secrets there are still caught.
5. **`SEC-068` (low)** — add a durable secondary brake on the login-lockout fail-open path.
6. **Agent-input hardening:** `SEC-073` (`json.dumps`/slug-allowlist the model `public_slug` before `lib/booking.ts`), `SEC-074` (soften the per-account lockout DoS), `SEC-072` (randomized dollar-quote tag / bound param in the Design-Prompt writeback).
7. **Hygiene carried over:** `SEC-066` (enforce admin-key `scopes`), `SEC-065` (verify the gitleaks binary checksum), `SEC-015` (admin-key rotation/revoke surface), `SEC-040` (tighten frontend CSP), `SEC-027` (prune the stale `backend/auth_service/requirements.txt`).

> **Note:** the auto-fixing "Saturday Solver routine" referenced below no longer exists (its code was removed). Open
> findings now require **manual** remediation. A human should reconcile the automation references in this folder.

## How to read this folder

| File | What it is |
|---|---|
| [`FINDINGS.md`](./FINDINGS.md) | **The live tracker.** Every finding's ID, severity, location, and **status**. Start here. |
| [`findings/critical.md`](./findings/critical.md) · [`high.md`](./findings/high.md) · [`medium.md`](./findings/medium.md) · [`low.md`](./findings/low.md) · [`info.md`](./findings/info.md) | Full detail per finding: description, attack scenario, real code evidence, adversarial verification, exploitability, remediation. |
| [`dismissed.md`](./dismissed.md) | Candidate findings **adversarially verified as false positives** — recorded so we don't re-litigate them. |
| [`methodology.md`](./methodology.md) | How a review is run: architecture facts, the 14 dimensions, severity scale, ID scheme, process. |
| [`scope-checklist.md`](./scope-checklist.md) | The concrete file/area inventory to scan. **Grows with the app.** |
| [`scheduled-review-prompt.md`](./scheduled-review-prompt.md) | The self-contained ultra-effort prompt the **weekly review** runs. _(The previously-referenced Saturday "Solver" auto-fix routine no longer exists — its code was removed 2026-08-26; open findings now need manual remediation.)_ |
| [`review-log.md`](./review-log.md) | Dated log of each review run (what was scanned, what changed). |

## How this review was produced

A 14-dimension multi-agent workflow (find → **adversarial verification** → synthesize). The latest run
(2026-10-08) used 32 agents: a reconciliation pass over every open tracker finding plus one finder per
security dimension (two for XSS, covering the new rich-text backend + the TS client kit), each candidate
re-verified by an independent skeptic that re-read the cited code and defaulted to *false-positive* unless
the code supported the claim. The 2026-06-07 baseline ran 84 agents over a wider surface (frontend,
backend, services, workflows, agents, the since-removed scraper, and live Supabase/Vercel MCP state).
Surviving findings cite real `file:line` + code evidence. The recurring methodology lives in this folder
so the next review starts from here, not from scratch.

## Scope reviewed
Frontend (Next.js 16, incl. the embeddable booking widget) · Backend (FastAPI: 15 routers, 30+ services,
core auth/session/limiter) · 26 SQL migrations + live Supabase RLS/RPC/advisor state
(`xeluydwpgiddbamysgyu`) · 2 GitHub Actions workflows (promote, CodeQL) · 3 AI agents (CMS Connector,
Design Prompt, Website Builder) · dependencies/supply-chain · Vercel deployment posture. (The Solver
agent + solver workflow and the lead scraper were removed 2026-08-26.)

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
