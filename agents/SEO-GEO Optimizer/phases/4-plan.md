# Phase 4 — Plan

**Goal:** Turn the audit + competitor gaps + guidelines into a **prioritized, plain-language
plan**, persist it to `seo_plan_items`, close the run, and flip the project's SEO flags.
This is where Plan 2 stops — no applying or publishing (that is Plan 3).

**Inputs:** `merged_scores` + `audit_detail` (Phase 3), `content_gaps` +
`competitor_analysis` (Phase 2), the guidelines KB (`guidelines/*.md`), global
`seo_learnings` (Phase 1). `run_id` + `project_id`.

## Steps

1. **Run the planner** (`prompts.PLANNER_PROMPT`) over: the per-locale audit detail (failed
   rubric items + the GEO judge's citability notes), the competitor gap list + reasoned
   analysis, and the guidelines. Produce a prioritized list. Each item carries:
   - `title` — clear, plain-language;
   - `description` — what to do;
   - `rationale` — a one-sentence "why it matters", grounded **only** in the confirmed
     levers (`prompts.CONFIRMED_LEVERS` / `guidelines/`), **never** a refuted claim;
   - `priority` — 0–10 (highest first);
   - `effort` — `low` | `medium` | `high`;
   - `track` — `seo` | `geo` | `local`;
   - `action_kind` — one of `content` | `meta` | `schema` | `article` | `new_page` |
     `manual_human` (these match the `seo_plan_items.action_kind` CHECK constraint);
   - `target` — the route or service key the item applies to.

   > **Analysis is English-only.** The plan's `title` / `description` / `rationale`, the
   > `seo_runs.summary` (step 4), and the competitor `analysis` are authored in **English
   > regardless of the site's locales** — they are operator-facing and never shipped to the
   > live site. (The audit still RUNS per locale; only the *reporting* is English.) Localized
   > PROSE for the live site — meta/OG/article text — is written in the **default locale** in
   > Phase 5 and translated per-locale by the pipeline; the plan itself is not translated. See
   > `guidelines/localization.md` (Bucket 3 — INTERNAL → English-only).

2. **Honesty rule:** use `manual_human` for items that are not automatable — backlinks /
   off-page authority, E-E-A-T / author authority, **actual Google Business Profile edits +
   review acquisition**, and paid geo-grid rank work. Flag them, never fake them, never
   promise rankings. Sell **readiness**, not positions.

3. **Persist** each item (skip writes in `dry-run`):

   ```sql
   INSERT INTO seo_plan_items (project_id, run_id, track, title, description, rationale,
                               priority, effort, action_kind, target, status, created_at, updated_at)
   VALUES ('<project_id>', '<run_id>', '<track>', '<title>', '<description>', '<rationale>',
           <priority>, '<effort>', '<action_kind>', '<target>', 'planned', now(), now());
   ```

   If `mode.audit_only`: skip the plan-item inserts (the audit rows from Phase 3 are the
   deliverable). Still close the run (step 4).

4. **Close the run** + flip the flags:

   ```sql
   UPDATE seo_runs
   SET status = 'completed', finished_at = now(),
       scores = '<{"seo":..,"geo":..,"local":..}>'::jsonb,
       summary = '<plain-language run summary>'
   WHERE id = '<run_id>';

   UPDATE projects
   SET seo_enabled = true, seo_last_run_at = now()
   WHERE id = '<project_id>';
   ```

   `seo_enabled = true` makes the dashboard "SEO & GEO" tab appear; it is an activation
   flag, **not** a paywall.

5. **Echo the dashboard path** and stop (Phase 4 is the end of this build):

   *"Phase 4: `<N>` plan items written. Run `<run_id>` completed (SEO `<s>` · GEO `<g>` ·
   local `<l>`). View: dashboard → `<project_slug>` → SEO & GEO. (Applying changes ships in
   Plan 3.)"*

## Outputs

- `seo_plan_items` — the persisted prioritized plan (unless dry-run / audit-only)
- `seo_runs` row closed `completed` with merged `scores` + `summary`
- `projects.seo_enabled = true`, `seo_last_run_at = now()`

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| Planner returns an item with an invalid `action_kind` | Re-map to the nearest valid kind or drop the item; never insert a CHECK-violating value. |
| Supabase plan write fails | "Phase 4: `seo_plan_items` write failed (`<error>`). Run NOT closed — re-run to retry." |
| `seo_runs` close fails | "Phase 4: could not close run `<run_id>` (`<error>`). Plan items were written; close manually or re-run." |

## Self-improvement hook

If the planner keeps producing an action-kind/effort split that Stefan corrects (a mechanics
preference about how plans are shaped), append to `LEARNINGS.md` under `## Phase 4 — Plan`:
- `- <YYYY-MM-DD>: Plan-shape rule — <preference>. Triggered by: feedback on <context>.`

Generalizable *SEO/GEO intelligence* learned from a run (e.g. "salon homepages almost always
miss `LocalBusiness` openingHours") is client/category knowledge → distill into the
`seo_learnings` Supabase table (global), not this file.

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
