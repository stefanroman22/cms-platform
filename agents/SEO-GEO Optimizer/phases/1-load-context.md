# Phase 1 — Load context

**Goal:** Load the project + its prior SEO memory from Supabase, detect business
category + location, and open a new `seo_runs` row. Everything is read/written via
Supabase MCP (`mcp__supabase__execute_sql`, project `xeluydwpgiddbamysgyu`).

**Inputs:** `project_slug` + `mode` from Phase 0. Supabase MCP connection.

## Steps

1. Load the `projects` row:

   ```sql
   SELECT id, slug, name, locales, default_locale, production_url, website_url,
          github_repo, lead_id, seo_enabled, seo_last_run_at
   FROM projects WHERE slug = '<project_slug>';
   ```

   If empty → halt: *"Project `<slug>` not found."*
   Keep `project_id` (uuid) for every subsequent write.

2. Load prior per-client memory (most recent first — this is the agent's memory):

   ```sql
   SELECT * FROM seo_runs        WHERE project_id = '<project_id>' ORDER BY started_at DESC LIMIT 5;
   SELECT * FROM seo_audits      WHERE project_id = '<project_id>' ORDER BY audited_at DESC LIMIT 10;
   SELECT * FROM seo_plan_items  WHERE project_id = '<project_id>' ORDER BY created_at DESC LIMIT 30;
   ```

   These give prior scores, the last plan, and what's already been done. A project with no
   rows is a first run — that's fine.

3. Load the **global** cross-client learnings:

   ```sql
   SELECT scope, category, rule, source, confidence FROM seo_learnings ORDER BY created_at DESC LIMIT 50;
   ```

   These are generalizable rules distilled from prior runs across ALL clients — thread the
   relevant ones into Phases 2–4.

4. **Detect business category** (a bucket like salon / restaurant / cafe / venue / retail /
   service) and **location/city**, in this order of preference:
   - the linked lead row (if `projects.lead_id` is set):
     `SELECT category, city, region, country, business_name FROM leads WHERE id = '<lead_id>';`
   - the live site's `LocalBusiness` JSON-LD (fetch the homepage with
     `render_check.fetch_raw` and read `@type` / `address` / `name`);
   - failing both, infer category + city from the homepage text.

   Ask **once** for the city **only if it is truly indeterminable** from all three. Never
   ask about routine category bucketing — infer it.

5. Resolve the **locale set** to audit:
   - default: every locale in `projects.locales`;
   - if `mode.locale` is set: just that one locale.
   Resolve the per-locale URL from `production_url` (or `website_url` as fallback) +
   next-intl locale routing (e.g. `/`, `/nl`, `/en`). The default locale is usually the
   bare root; non-default locales carry a `/<xx>` prefix. Record the per-locale URL map.

6. Open a new run row (unless `mode.dry_run`):

   ```sql
   INSERT INTO seo_runs (project_id, status, trigger, locale_scope, started_at)
   VALUES ('<project_id>', 'running', '<raw trigger>', ARRAY[<locales>], now())
   RETURNING id;
   ```

   Keep the returned `run_id` for every Phase 2–4 write. In `dry-run`, skip the INSERT and
   use a placeholder `run_id` locally (write nothing).

7. Echo: *"Phase 1: `<business_name>` · category `<bucket>` · `<city>` · locales `<list>`.
   Run `<run_id>` open."*

## Outputs

- `context` — `{project_id, slug, name, business_name, category, city, region, country,
  locales, locale_urls, production_url, github_repo, prior: {runs, audits, plan_items},
  learnings}`
- `run_id` — the open `seo_runs` id (or a local placeholder in dry-run)

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| Project not found | "Project `<slug>` not found in Supabase." |
| Supabase MCP connect failure | "Supabase MCP unavailable: `<error>`. The run + all memory live in Supabase — halting." |
| City truly indeterminable | "I can't determine the business city from the lead, JSON-LD, or homepage. What city/area should I target?" |

## Self-improvement hook

If a project's per-locale URL convention surprises the agent (e.g. the NL page is at `/nl-NL`
not `/nl`), append to `LEARNINGS.md` under `## Phase 1 — Load context`:
- `- <YYYY-MM-DD>: Project `<slug>` locale `<xx>` URL is `<path>`. Triggered by: 404 on the guessed path.`

(Do NOT record the project's category/city/scores here — those are per-client memory and
belong in the `seo_*` Supabase tables.)

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
