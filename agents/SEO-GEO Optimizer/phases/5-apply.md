# Phase 5 — Apply

**Goal:** Apply the plan into the **SEO/GEO CMS area** and to existing site copy — all as
**DRAFT**. Write SEO meta/schema → `seo_page_meta` drafts; write GEO articles → `seo_articles`
drafts (via the factual-gated content writer); push GEO copy edits to existing pages through
the platform's `save_service` draft path. Record one `seo_changes` row per applied item. No
publishing here — that is the gate in Phase 6.

**Inputs:** the `seo_plan_items` rows from Phase 4 (`action_kind` per item), `run_id`,
`project_id`, `project_slug`, the per-locale URL map, the admin bearer (CMS-admin writes are
pre-authorized). The `geo-content-writing` skill (for `article` + `content` items) and the
`apply.py` helpers (`build_page_meta_payload`, `build_article_payload`, `diff_before_after`).

Nothing here mutates **published** content — every write is a draft. `apply.py` defaults
`status='draft'` and `updated_by='agent'`.

## Steps

Process each `seo_plan_items` row whose `status='planned'`, by `action_kind`:

1. **`action_kind` in {`meta`, `schema`}** → a `seo_page_meta` DRAFT.
   - **Write the DEFAULT locale only.** Build the payload for the project's **default
     locale**: `apply.build_page_meta_payload(project_id, route, default_locale, fields)`
     where `fields` holds the improved `title` (≤ ~60 chars), `description` (140–160 chars),
     and/or `canonical` / `og` / `json_ld` (the schema) / `robots`. (`meta` items touch
     `title`/`description`/`canonical`/`og`; `schema` items touch `json_ld`.) The non-default
     locales are filled by the translate endpoint in step 7 — **never hand-write them here.**
   - Upsert via Supabase MCP **on conflict (project_id, route, locale)**:

     ```sql
     INSERT INTO seo_page_meta (project_id, route, locale, title, description, canonical, og, json_ld, robots, status, updated_by, updated_at)
     VALUES ('<project_id>', '<route>', '<xx>', …, 'draft', 'agent', now())
     ON CONFLICT (project_id, route, locale) DO UPDATE SET
       title = excluded.title, description = excluded.description, canonical = excluded.canonical,
       og = excluded.og, json_ld = excluded.json_ld, robots = excluded.robots,
       status = 'draft', updated_by = 'agent', updated_at = now();
     ```
   - Record the change with a before/after diff: read the prior row (if any), then
     `before_after = apply.diff_before_after(before_fields, after_fields)` and insert a
     `seo_changes` row (`kind='meta'`/`'schema'`, `target=<route>`, `before`/`after` from the
     diff, **no `published_at` yet**).

2. **`action_kind == article`** → a `seo_articles` DRAFT.
   - Invoke the **`geo-content-writing`** skill for the **DEFAULT locale only** (a
     default-locale article cites a default-locale-language source; GATE-FACT runs in the
     default locale). It returns `{title, excerpt, body, json_ld?, claims[]}` — every claim
     already GATE-FACT-verified (verbatim source substring) or dropped. **Do not hand-write
     the other locales** — step 7 translates them via the endpoint.
   - Build the payload: `apply.build_article_payload(project_id, run_id, slug, default_locale, fields)`
     and insert via MCP (`status='draft'`, `source_run_id=run_id`, unique on
     `(project_id, slug, locale)`).
   - Record a `seo_changes` row (`kind='article'`, `target=<slug>`, `after` = the article
     fields; `before` = null for a new article).

3. **`action_kind == content` targeting an EXISTING page/service** → a platform DRAFT edit.
   - Invoke **`geo-content-writing`** (per locale) for the new copy (same factual gate).
   - Write it to the platform's **DRAFT** content for that service via the existing
     `save_service` draft path — the backend content API with the **admin bearer**. **Never**
     directly mutate published content here; the publish happens only in Phase 6 after the gate.
   - Record a `seo_changes` row (`kind='content'`, `target=<service key/route>`, before =
     the current draft copy, after = the new copy via `apply.diff_before_after`).

4. **`action_kind == new_page`** → **DEFERRED to Plan 4** (cross-agent `site-change-spec` →
   Website Builder incremental + Connector). In this phase, **do not** build any new page.
   Mark the item `status='planned'` (leave it pending) and **skip** it. (Phase 6 emits the
   one-line new-page tripwire only when a new page type actually ships — which is Plan 4.)

5. **`action_kind == manual_human`** → **surfaced only, no write.** These need a human
   (backlinks / off-page, E-E-A-T / author authority, actual Google Business Profile edits +
   review acquisition, paid geo-grid). Leave the item as-is and include it in the run summary
   so the operator sees it. Never fake it, never promise rankings.

6. **Fill the non-default locales — call the translate endpoint.** After the default-locale
   `seo_page_meta` / `seo_articles` rows are written (steps 1–2), translate the **prose**
   into every non-default project locale via the CMS pipeline. Call (admin bearer):

   ```
   POST /projects/{slug}/seo/translate   { "kind": "meta" }     # then
   POST /projects/{slug}/seo/translate   { "kind": "article" }
   ```

   This is the **only** path that fills non-default locales — **never hand-write them.** The
   endpoint translates only the **prose** fields (meta `title`/`description`, OG
   `title`/`description`; article `title`/`excerpt`/`body`) from the default locale; it
   **never** touches coded facts/tags (`canonical`/`robots`/`og.image`/JSON-LD data/
   `hero_image_url` — those are language-invariant) and never touches internal analysis
   (English-only). **Contract:**
   - **Omit-on-failure, never blank:** a field whose translation fails (or whose source is
     empty) is left **unwritten** — never written as `""`/`null`. An explicit empty would
     block the fallback.
   - **Per-field default-locale fallback (server-side):** the public read endpoints
     (`/seo/public/meta`, `/seo/public/articles`) fill each missing/omitted locale field
     from the default-locale row, so a missing/failed translation transparently shows
     default-locale text — a live page is never broken or empty.
   - A whole untranslated body is **not** published as a separate same-language URL — until
     it is translated, that locale is excluded from hreflang/index (see
     `guidelines/localization.md`).
   - With `TRANSLATION_PROVIDER=null` the provider echoes the source (no DeepL spend); the
     endpoint still runs and the fallback contract still holds.

7. **Mark applied items** `status='applied'` (the `meta`/`schema`/`article`/`content` items
   that were written). `new_page` stays `planned`; `manual_human` stays as surfaced.

   ```sql
   UPDATE seo_plan_items SET status = 'applied', updated_at = now()
   WHERE id = '<plan_item_id>';
   ```

## Outputs

- DRAFT rows in `seo_page_meta` / `seo_articles`, and DRAFT content edits via `save_service`.
- One `seo_changes` row per applied item (with `before`/`after`, no `published_at`).
- The list of `seo_changes` ids + the **set of affected routes × locales** — handed to
  **Phase 6**, where the **`seo-visual-qa`** skill renders them and calls
  `gate.evaluate_gate(...)`; nothing is published here. Phase 6 publishes the SEO-area drafts
  (status → published) and the site-content drafts via `POST /projects/{slug}/publish` **only
  when the gate is all-green**.

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| `geo-content-writing` drops all claims for an article (nothing verifiable) | "Phase 5: article `<slug>` (`<xx>`) had no verifiable claims — not written (GATE-FACT). Item left planned." (continue) |
| Supabase upsert fails for one item | "Phase 5: `<kind>` write for `<target>` failed (`<error>`). Item left planned; other items applied." (continue) |
| `save_service` draft write fails (admin bearer) | "Phase 5: content draft for `<target>` failed (`<error>`). Re-run to retry; no published content touched." |
| A `new_page` item is encountered | "Phase 5: `<target>` is a new page — deferred to Plan 4 (cross-agent). Left planned." (continue) |

## Self-improvement hook

If the apply path keeps hitting a mechanics issue (e.g. a route's `seo_page_meta` upsert
conflicts because the route string drifts between audit and apply), append to `LEARNINGS.md`
under `## Phase 5 — Apply`:
- `- <YYYY-MM-DD>: <one-line mechanics rule>. Triggered by: <context>.`

Generalizable SEO/GEO intelligence (e.g. "salon homepages need a `LocalBusiness` JSON-LD
draft by default") is client/category knowledge → the `seo_learnings` Supabase table, not here.

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
