# Learnings — SEO/GEO Optimizer

> **Agent-mechanics lessons ONLY.** This file records how the *agent itself* should
> behave — workflow quirks, tool gotchas, per-locale URL conventions, MCP edge cases.
>
> **Per-client and per-category memory does NOT live here — it lives in Supabase.**
> Client audits, plans, history, competitor intel → the `seo_*` tables. Generalizable
> cross-client *intelligence* rules → the `seo_learnings` table (global). This markdown
> file is intentionally thin.
>
> Each entry: short, dated, generalisable, append-only. Format:
> `- <YYYY-MM-DD>: <one-line rule>. Triggered by: <short context>.`
> Append-only — never delete or rewrite existing rules.

## General

- 2026-06-14: When self-checking written rows for the 11 forbidden claims, match the actual claim PHRASES with LITERAL substring/word-boundary checks (e.g. `strpos`, or `grep -F`), NOT SQL `LIKE` with bare number fragments. A needle like `32%` in a `LIKE '%32%%'` pattern treats `%` as a wildcard and false-positives on any "...32..." (it flagged "532 words", a real competitor word count). Use phrases like `32% of local`, `FAQ schema makes`, `3.2x`. Triggered by: samir-kapsalon first run — a LIKE-based forbidden-claim scan reported a phantom hit.

## Phase 6 — Verify / publish (visual-QA gate)

- 2026-06-14: The mobile tap-target check must EXCLUDE inline text links (footer/nav/body `<a>`) — only flag standalone interactive controls (buttons, primary CTAs, icon links). A naive `a,button[height<44]` query counted 24 "small" targets on a perfectly healthy shipped site (samir) and would false-fail the gate. Scope the selector or treat raw tap-target counts as advisory, not a hard publish-blocker. Triggered by: samir-kapsalon scoped gate test — Playwright reported 24 sub-44px interactive els, all inline links, site is fine.
- 2026-06-14: CONFIRMED-GOOD: the gate works end-to-end — real Playwright renders at 375/768/1440 + console + raw-HTML → `gate.evaluate_gate` → publish only when green. samir passed clean (no overflow/console/broken-images) and the meta improvement published to `seo_page_meta`. Triggered by: Plan 3 live test.

## Phase 1 — Load context

- 2026-06-14: Locale URLs use the next-intl `always` prefix style — fetch `<production_url>/<locale>` (e.g. `/nl`, `/en`), NOT the bare root. The bare root usually 308-redirects to the default locale. Triggered by: samir-kapsalon (nl/en) audited via `/nl` and `/en`.

## Phase 2 — Competitor intel

- 2026-06-14: Keep agent-emitted strings ASCII-safe (use `~` not `≈`, `-` not `—`). On a Windows cp1252 console, printing/capturing non-ASCII gap strings raises `UnicodeEncodeError` and can abort a run; Supabase stores UTF-8 fine but the run dies before the write. `competitor.content_gaps` was de-unicoded for this reason. Triggered by: samir-kapsalon competitor run crashed on `≈` (U+2248) at stdout.
- 2026-06-14: Exclude directory/aggregator domains from competitor sets (yelp, barberhead, allebarbershops, treatwell, google, facebook) — they are listings to BE in, not competitors. Triggered by: a Nijmegen search surfaced allebarbershops.nl (a directory with BlogPosting/BreadcrumbList schema) alongside real shops.

## Phase 3 — Audit

(none yet)

## Phase 4 — Plan

(none yet)

## Supabase / MCP

(none yet)
