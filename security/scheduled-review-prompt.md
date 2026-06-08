# Weekly Security Review — Scheduled Agent Prompt

> This is the exact instruction the **weekly scheduled security review** runs (Saturdays 08:00).
> It is intentionally self-contained: the agent that runs it may have **no prior context**.
> Keep it in sync with [`methodology.md`](./methodology.md) and [`scope-checklist.md`](./scope-checklist.md).
> When the app grows, update those two files — this prompt points at them rather than duplicating detail.

---

## PROMPT (copy verbatim into the schedule)

You are running the **weekly automated security review** of the CMS platform. Give this your
**maximum effort — ultra-high effort. Use the Workflow tool to orchestrate a multi-agent review**;
do not do this single-threaded. Token cost is not a constraint. The goal is the most exhaustive,
correct, well-documented security review possible. Be thorough over fast.

**0. Orient (read these first):**
- `security/methodology.md` — how this review works, the 14 dimensions, severity scale, architecture facts.
- `security/scope-checklist.md` — the concrete file/area inventory to cover (grows with the app).
- `security/FINDINGS.md` — the live tracker of every known finding and its status.
- `security/findings/` — the per-severity detail docs.
- Skim `git log` since the last review's date (top of `FINDINGS.md`) to see what code is new/changed — **new code is the highest-yield target.**

**1. Pull live infra state via the MCP connections:**
- Supabase (`mcp__supabase__get_advisors` security **and** performance) on project `xeluydwpgiddbamysgyu`;
  `list_tables` + read-only `execute_sql` to confirm RLS/policy/GRANT state.
- Vercel (`mcp__vercel__get_project`) for `cms-backend-roman` and the frontend project — env scoping & deployment protection.
- If an MCP server is unavailable in the headless run, note it in the report and continue with code review.

**2. Run the review as a Workflow** (find → adversarially verify → synthesize), one finder agent per
dimension in `methodology.md` §2, scanning everything in `scope-checklist.md` **in parallel**. Every
finding must cite `file:line` and a real code snippet, and must be adversarially verified by an
independent skeptical agent before it is recorded. Prioritize, in order:
   1. **Cross-tenant / project-ownership (IDOR)** — the dominant risk because the backend uses the
      Supabase service-role key (RLS bypassed; authZ is in app code).
   2. **Authentication** for users/clients (sessions, cookies, tokens).
   3. **Admin privilege** gating.
   4. **Public endpoints & tokens** (booking, forms, manage links, Slack webhook, embeddable widget).
   5. **XSS / HTML-email injection**, **SSRF** (scraper + connector agent), **injection**, **CI workflows**, **agents**, **Supabase DB**, **deps**, **rate-limiting**.

**3. Reconcile with the tracker** — for every finding currently `open`/`in-progress` in `FINDINGS.md`,
re-read the cited code and decide: still present (keep), or fixed (mark `fixed` + cite the commit). Do
**not** silently drop a finding. Add new findings with the next `SEC-NNN` id. Keep dismissed/
false-positive findings recorded so they aren't re-litigated.

**4. Update the documentation so it stays healthy for future reviews:**
- Update `security/FINDINGS.md` (the tracker): new findings, status changes, the new "last reviewed" date, and the severity counts.
- Update `security/findings/critical.md`, `high.md`, `medium.md`, `low.md` with full detail for each (description, location, attack scenario, evidence snippet, remediation, status).
- Append a dated entry to `security/review-log.md` summarizing this run (what was scanned, counts, what changed since last time, any MCP gaps).
- If you discovered a **new surface/file area**, add it to `scope-checklist.md`.
- Refresh `security/README.md`'s status snapshot (counts + headline risks).

**5. Report.** End with a concise executive summary: posture, top risks, what changed since last week,
and the recommended remediation order. If anything is **critical**, call it out unmissably at the top.

**Guardrails:** This is a **read-only audit** — do **not** modify application/source code, run
exploits against production, or change Supabase/Vercel configuration. Only write inside `security/`.
Do not commit unless explicitly configured to; leave the docs updated in the working tree.

---

## Why this prompt is shaped this way

- **Self-contained + points at living docs** so it survives context loss and stays correct as the
  codebase grows (the detail lives in `methodology.md` / `scope-checklist.md`, which evolve).
- **Mandates Workflow + ultra effort** so coverage is parallel and adversarially verified, not a
  shallow single pass.
- **Forces reconciliation** with the tracker so the review compounds over time instead of starting
  from zero each week.
- **Read-only guardrails** so an automated Saturday run can never damage prod or rewrite app code.
