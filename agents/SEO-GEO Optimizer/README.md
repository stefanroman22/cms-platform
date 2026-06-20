# SEO/GEO Optimizer — quick reference

A 4th first-class pipeline agent. Audits a client's live, CMS-wired site for **SEO**
(Google classic + local) and **GEO** (AI answer-engine readiness: ChatGPT Search,
Perplexity, Google AI Overviews, Gemini), does reasoned competitor + local intelligence,
and writes a prioritized plan — all persisted to Supabase `seo_*` and surfaced in the
dashboard "SEO & GEO" section.

## Invoke

> **Run SEO agent for `<project_slug>`**  `[locale <xx>] [audit-only] [articles <N>] [dry-run]`

Runs in the main Claude Code thread (full tools). Autonomous — never pauses for permission
to research / fetch / render / write.

## What it does (this build — Plan 2, phases 0–4)

1. **Parse intent** — slug + flags from the trigger.
2. **Load context** — `projects` row + prior `seo_*` memory + global `seo_learnings`;
   detect category + city; open a `seo_runs` row.
3. **Competitor + local intel** — WebSearch/WebFetch real local competitors, extract their
   server-rendered HTML/JSON-LD, compute content gaps, reason a write-up → `seo_competitors`.
4. **Audit** — per locale: fetch raw HTML → deterministic SEO + local score + LLM-judge
   GEO readiness (+ GATE-FACT claim/source extraction) → `seo_audits`.
5. **Plan** — reasoned prioritized `seo_plan_items`; close the run `completed`; set
   `projects.seo_enabled=true`, `seo_last_run_at=now()`.

Applying/publishing (the visual-QA + self-heal gate) is **Plan 3**; new pages are **Plan 4**.

## File map

| Path | What |
|---|---|
| `AGENTS.md` | authoritative spec (phases, autonomy, constants, memory, failure modes) |
| `LEARNINGS.md` | append-only **agent-mechanics** lessons only (client memory → Supabase) |
| `example-prompts.md` | invocation examples |
| `prompts.py` | system prompts + the `FORBIDDEN_CLAIMS` block + `CONFIRMED_LEVERS` |
| `render_check.py` | fetch raw HTML (GPTBot UA) + extract on-page signals (tested) |
| `audit.py` | deterministic SEO + local scoring; ids align with `rubric/rubric.yaml` (tested) |
| `competitor.py` | competitor signal extraction + content-gap substrate (tested) |
| `guidelines/` | durable best-practice KB — Track G (Google), E (GEO), L (Local) |
| `rubric/rubric.yaml` | scored audit rubric + convergence/pass-gate block |
| `phases/0-4*.md` | per-phase workflow docs |
| `tests/` | pytest for the Python helpers |

## Defaults

- Supabase project: `xeluydwpgiddbamysgyu` (all reads/writes via `mcp__supabase__execute_sql`).
- `MAX_ITERS=3`; pass gate GEO ≥ 75 / SEO ≥ 85 / local ≥ 80 + GATE-FACT clean (the loop is Plan 3).
- Per-locale audit + scoring. Sell **readiness**, never ranking guarantees.
- Pipeline position: **4th — after the CMS Connector**; re-runnable anytime after.

See [`AGENTS.md`](./AGENTS.md) for the full spec and
[`.claude/skills/seo-geo-optimizer/SKILL.md`](../../.claude/skills/seo-geo-optimizer/SKILL.md)
for the entry point.
