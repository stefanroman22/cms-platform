# Phase 0 — Parse intent

**Goal:** Extract `<project_slug>` + flags from the trigger string. If the slug is missing
or unknown, ask once. Echo a one-line plan.

**Inputs:** the raw trigger message. Constants from AGENTS.md.

## Steps

1. Match the trigger `Run SEO agent for <project_slug>` (close paraphrases too:
   *"SEO agent on X"*, *"audit X for SEO/GEO"*). Capture `<project_slug>`.

2. Parse optional flags from the rest of the message:

   | Flag | Field set |
   |---|---|
   | `locale <xx>` | `mode.locale = "<xx>"` (scope to one locale) |
   | `audit-only` | `mode.audit_only = true` |
   | `articles <N>` | `mode.articles = <N>` (recognized; campaign ships in Plan 3) |
   | `dry-run` | `mode.dry_run = true` (no Supabase writes) |

3. If `<project_slug>` is missing or clearly malformed → ask **once**:
   *"Which project? Give me the project slug."* and wait. Do not guess.

   (Whether the slug *exists* is confirmed in Phase 1 against the `projects` table — Phase
   0 only checks that a slug-shaped token was provided.)

4. Echo a one-line plan and proceed:

   *"SEO agent · project `<slug>` · mode: `<flags or 'full'>`. Phases 1–4: load → competitor
   intel → audit → plan."* Do not preview every phase in detail.

## Outputs

- `project_slug` — the captured slug string
- `mode` — `{locale?, audit_only, articles?, dry_run}` (defaults: full run, all locales)

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| Slug missing / malformed | "Which project? Give me the project slug." |
| Trigger unparseable | "I couldn't parse that. Use: `Run SEO agent for <project_slug>`." |

## Self-improvement hook

If a paraphrase of the trigger keeps failing to parse, append to `LEARNINGS.md` under
`## General`:
- `- <YYYY-MM-DD>: Trigger paraphrase "<phrase>" should match. Triggered by: missed parse on <context>.`

---

FORBIDDEN CLAIMS — these failed adversarial verification. NEVER state them as fact,
NEVER use them to justify a recommendation, NEVER score on them:
- FAQPage schema makes a page 3.2x more likely to appear in AI Overviews. (REFUTED)
- Answer-first opening paragraphs are cited 67% more often by AI engines. (REFUTED)
- 92.36% of AI-Overview citations come from domains in the top-10 organic results. (REFUTED)
- llms.txt is an effective or low-downside ranking/citation signal. (REFUTED — treat as speculative only)
- Google Business Profile signals account for ~32% of local-pack weight (with on-page 19% /
  reviews 16% / citations 7%). (REFUTED — do not use these weightings)
- 100% complete Google Business Profiles get ~7x more clicks; 50+ reviews win 4.4x more clicks. (REFUTED)
- NAP inconsistency across 3+ sources excludes a business from AI answers 74% of the time. (REFUTED)
- Filling all 10 Google Business Profile category slots directly improves ranking. (REFUTED)
- AI agencies inherently price SEO higher than traditional agencies. (REFUTED)
- Agent memory must be a short-term/long-term vector-store split. (REFUTED — markdown/Supabase memory is fine)
Treat schema markup as a Google-rich-result + structured signal, NOT an AI-citation multiplier.
