# CMS Platform — Security

This folder is the **living source of truth for the security posture of the CMS platform**.
It is built to compound: every review reconciles against it, so over time it tracks what's
broken, what's been fixed, and what's been judged not-a-problem — and it tells a future
reviewer (human or agent) exactly what to scan and how.

## Status snapshot — last full review **2026-11-19**

| Critical | High | Medium | Low | Info | Dismissed (false-positive) |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** (fixed) | 5 | 16 | 39 | 12 | 20 |

> Absolute counts are **cumulative-approximate** — the dev tracker header was never reconciled with the
> parallel `SEC-069…095` numbering on the unmerged weekly-review branches (a human-owed reconciliation).
> Trust the per-row `file:line` + status in [`FINDINGS.md`](./FINDINGS.md), not the header totals.

The **2026-11-19 review found no new critical and no cross-tenant IDOR**; injection, XSS/CSS/email, and admin-privilege
were all clean. The net-new **ADR-0013 display-options** feature (toggle/select/colour fields, options service,
dark-theme colour variants) introduced no cross-tenant, injection or XSS issue — the colour→CSS path is validated at
both the backend store boundary (`theme.normalize_hex`) and the kit read boundary (`readColor`). It added **1 high +
3 medium + 1 low** (`SEC-096…100`), all in the **`.claude/hooks/guard.mjs` agent-guardrail** surface plus one CMS
Connector prompt-injection. The 2026-06-07 baseline criticals/highs (`SEC-001…004`/`SEC-056`) remain **fixed**;
`SEC-070/071/072/073/094/095` are fixed on dev. See [`FINDINGS.md`](./FINDINGS.md) + [`review-log.md`](./review-log.md).

### The next things to fix (2026-11-19 remediation order)
1. ~~**`SEC-097` (high)**~~ — **✅ fixed on dev 2026-11-21 (PR #99)**: `guard.mjs` `inspectSegment` now dispatches on `path.basename(cmd)`, so `/bin/bash -c …`, `/usr/bin/env …`, `./sh` resolve to `bash`/`env`/`sh` and the recursive unwrap re-inspects them (8 regression tests, 7 FAIL pre-fix). No action remaining.
2. ~~**`SEC-100` (medium)**~~ — **✅ fixed on dev 2026-11-24 (PR #102)**: `into` added to the `sqlIsReadOnly` write classifier.
3. ~~**`SEC-099` + `SEC-098` (medium)**~~ — **✅ fixed on dev 2026-11-24 (PRs #101/#100)**: H4 now denies `GIT_CONFIG_*`/`--config-env`/bare-`-c` `core.hooksPath` and the `--no-v…` abbreviation family. **The whole guard.mjs cluster (SEC-097/098/099/100) is now closed.**
4. **`SEC-096` (low)** — pin the booking `owner_notification_email` to the operator-resolved client email (don't trust the model's `destination_email`), and add server-side email-format validation to `SettingsPatch`.
5. **Hygiene (reconfirmed open):** `SEC-065` (verify the gitleaks binary checksum in `promote.yml`), `SEC-039` (`needs-decision`: split credentialed vs credential-less CORS), `SEC-040` (tighten CSP), `SEC-066`/`SEC-068` backlog.

> **Note:** all five net-new items are `.claude/` guardrail or agent/application-code edits with no unit-testable
> application seam, so this read-only review **leaves them for a human** (the Saturday Solver routine's auto-fix
> threshold is application-code C/H/M with a testable seam).

## How to read this folder

| File | What it is |
|---|---|
| [`FINDINGS.md`](./FINDINGS.md) | **The live tracker.** Every finding's ID, severity, location, and **status**. Start here. |
| [`findings/critical.md`](./findings/critical.md) · [`high.md`](./findings/high.md) · [`medium.md`](./findings/medium.md) · [`low.md`](./findings/low.md) · [`info.md`](./findings/info.md) | Full detail per finding: description, attack scenario, real code evidence, adversarial verification, exploitability, remediation. |
| [`dismissed.md`](./dismissed.md) | Candidate findings **adversarially verified as false positives** — recorded so we don't re-litigate them. |
| [`methodology.md`](./methodology.md) | How a review is run: architecture facts, the 14 dimensions, severity scale, ID scheme, process. |
| [`scope-checklist.md`](./scope-checklist.md) | The concrete file/area inventory to scan. **Grows with the app.** |
| [`scheduled-review-prompt.md`](./scheduled-review-prompt.md) | The self-contained ultra-effort prompt the **weekly review** runs (now **Friday 00:00 Berlin**, routine `trig_014vxyf4JSNpvucdjNKUSUgH`). A separate **Saturday 06:00 Berlin Solver** routine (`trig_01EsPjxVZGJciYRDYhZq8d9G`) branches/fixes/tests findings and opens PRs. |
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
