# Phase 7 — Learn + Persist (new pages)

**Goal:** Close the run. Handle every `new_page` plan item through the cross-agent
`site-change-spec` contract (auto-invoke Website Builder incremental + CMS Connector → the
visual-QA gate → publish → new-page-type tripwire), then **distil generalizable
intelligence into Supabase** (`seo_learnings`, global) + **agent-mechanics-only lessons into
`LEARNINGS.md`**, ensure the `seo_runs` row is `completed`, and echo the dashboard path. End
with the FORBIDDEN_CLAIMS block.

The content/meta/schema/article items were applied (Phase 5) + published (Phase 6) already.
This phase handles the **new-page** items those phases deferred, then learns + persists.

**Inputs:** `run_id`, `project_id`, `project_slug`, the repo + branch, the active locales;
the `seo_plan_items` rows (especially those with `action_kind == 'new_page'`); the run
artifacts (audits, scores, competitor intel, the Phase 6 gate proof). Uses
`site_change_spec.build_site_change_spec` / `validate_site_change_spec`,
`mcp__supabase__execute_sql` (project `xeluydwpgiddbamysgyu`), the **Website Builder**
(incremental mode) + **CMS Connector** agents, and the **`seo-visual-qa`** skill (Phase 6
gate). Cap: `PLAYWRIGHT_RENDER_CAP` ≈ 9 × locales × iters for the gate over new routes.

## Steps

### 1. new_page orchestration (per `new_page` plan item)

For each `seo_plan_items` row with `action_kind == 'new_page'` (status `planned`/`applied`):

1. **Build the spec.** Call
   `site_change_spec.build_site_change_spec(project_slug=…, repo=…, run_id=…, pages=[…],
   sections=[…], cms_wiring=[…], reason=…)`. Map each new-page item to a `pages` entry:
   `route`, `page_type` (one of `site_change_spec.PAGE_TYPES`:
   `blog_index`/`blog_post`/`local_landing`/`service`/`section`), `consumes`
   (`seo_articles`/`seo_page_meta`/`static`), `nav` (`{add, label_i18n}`), `schema_type`,
   and `locales` (ALL active locales). For a `/blog` index that renders generated articles,
   set `consumes: "seo_articles"` and a `cms_wiring` entry
   `{"consumes": "seo_articles", "via": "GET /projects/<slug>/seo/public/articles"}`.
   The `branch` defaults to `cms-preview` (code changes ride the preview branch — never push
   straight to production).

2. **Validate — halt the item if invalid.** Call
   `site_change_spec.validate_site_change_spec(spec)` → `(ok, errs)`. If `ok` is false, **do
   NOT invoke the Builder** for this item: record the validation failure on the item
   (`status='dismissed'` — the only CHECK-legal "won't-do" value; do NOT write `'blocked'`,
   it is not in the `seo_plan_items.status` CHECK and would raise a constraint violation) and
   capture `errs` in the item's `description`/a `seo_changes` note. Skip to the next item; a
   malformed spec never reaches the Builder.

3. **Auto-invoke the Website Builder (incremental mode).** Hand the validated spec to the
   Website Builder via its incremental phase
   ([`agents/Website Builder/phases/9-incremental.md`](../../Website%20Builder/phases/9-incremental.md)).
   The Builder ADDS the routes/sections to the EXISTING site (additive only — never a full
   rebuild, never breaks existing routes), with full `seo-pro` metadata + responsive + Motion,
   wires `generateMetadata` to prefer stored `seo_page_meta`, fetches `seo/public/articles`
   where `consumes: seo_articles`, adds the nav entry + i18n keys for every locale, and pushes
   to `cms-preview`. The SEO agent **never hand-edits the client's Next.js routing/layout** —
   new-page CODE only flows through the Builder (hard constraint #6).

4. **Auto-invoke the CMS Connector.** Run the Connector to provision/wire any new CMS
   consumption the new page needs (the SEO-area read endpoints — `seo/public/meta` /
   `seo/public/articles` — per its
   [`AGENTS.md` SEO/GEO area](../../CMS%20Connector%20-%20Website/AGENTS.md) +
   [`phases/4-integration.md` SEO-area wiring](../../CMS%20Connector%20-%20Website/phases/4-integration.md)).
   The Connector **only WIRES consumption** of the public read endpoints; it NEVER provisions
   or clobbers the `seo_*` tables (they are this agent's area). When the page is a blog index,
   set `projects.seo_blog_route` (e.g. `/blog`) so the Connector contract knows to wire `/blog`.

5. **Run the visual-QA gate over the new routes.** Invoke the **`seo-visual-qa`** skill
   (Phase 6 gate) over the new routes × locales on cms-preview + the Vercel preview deploy:
   render at **375 / 768 / 1440** px per locale, assert responsive / text+images visible /
   no crash / no console error / `next build` exit 0 / links resolve / `playwright-user-stories`
   smoke still green / new content present in raw server HTML, then `gate.evaluate_gate(checks)`.
   On red → the bounded ≤3-cycle self-heal loop; if still red, **HALT** the item: revert the
   `cms-preview` code change, mark the `seo_changes` row `reverted=true` with the gate proof,
   note it in the run summary, and **do not publish** this page.

6. **Publish only when green.** On an all-green gate, publish: promote `cms-preview` →
   production branch (the Connector promotion path), flip any related drafted `seo_page_meta`
   / `seo_articles` rows to `published`, and stamp the `seo_changes` published. Record the
   new-page change:

   ```sql
   UPDATE seo_plan_items SET status = 'published', updated_at = now()
   WHERE id = '<plan_item_id>';
   UPDATE seo_changes SET published_at = now()
   WHERE run_id = '<run_id>' AND plan_item_id = '<plan_item_id>' AND reverted = false;
   ```

7. **New-page-type tripwire.** The **first** time a brand-new page type ships for this
   project, print the one-line note: *"new page type `<X>` went live — glance recommended."*
   The flow stays hands-off; the tripwire is an informational nudge only.

### 2. Learn

- **Generalizable SEO/GEO intelligence** (cross-client — e.g. "barbershop homepages routinely
  miss `LocalBusiness.openingHours`", "a `/blog` index lifts GEO-citation readiness when
  articles carry real attributed statistics") → the **`seo_learnings`** Supabase table
  (global, queryable by the dashboard) via `mcp__supabase__execute_sql`:

  ```sql
  INSERT INTO seo_learnings (scope, category, rule, source, confidence, created_at)
  VALUES ('<global|category>', '<category>', '<one-line rule>', 'run:<run_id>', '<low|med|high>', now());
  ```
  Ground every `rule` ONLY in confirmed levers — **never** a refuted claim.

- **Agent-mechanics-only lessons** (how the agent itself behaves — a locale-URL quirk, a
  Builder/Connector hand-off edge case, a gate mechanics rule) → append to `LEARNINGS.md`
  under the closest heading, append-only:
  `- <YYYY-MM-DD>: <one-line agent-mechanics rule>. Triggered by: <context>.`
  Client- and category-level intelligence does **not** go here — it goes to `seo_learnings`.

- **Consume pending feedback.** Read any `feedback/pending/*` notes (mirrors the Design
  Prompt Creator loop): fold a distilled, generalizable lesson into `seo_learnings` (or
  `LEARNINGS.md` if it is pure agent-mechanics), then clear/age the note.

### 3. Persist + summary

- Ensure the `seo_runs` row is closed `completed` with the final `scores` + `summary`
  (re-open/append if Phase 4 already marked it `completed` from the audit):

  ```sql
  UPDATE seo_runs
  SET status = 'completed',
      scores = '<{"seo":..,"geo":..,"local":..}>'::jsonb,
      summary = '<… applied N, published M, new pages P (gate green); learnings L …>',
      finished_at = now()
  WHERE id = '<run_id>';
  ```

- Echo the dashboard path: *"Phase 7: run complete — published `<M>` change(s), `<P>` new
  page(s). View: dashboard → `<project_slug>` → SEO & GEO → History (with visual-QA proof)."*
  Append any new-page-type tripwire line from step 1.7.

## Outputs

- New-page items: shipped through Builder + Connector + the gate (published) OR halted +
  reverted with proof; `seo_plan_items.status` advanced; `seo_changes` rows recorded.
- `seo_learnings` rows for generalizable cross-client intelligence (global).
- `LEARNINGS.md` agent-mechanics lessons appended (if any).
- `seo_runs` row `completed` with final `scores` + `summary`; dashboard path echoed; the
  new-page-type tripwire printed when one shipped.

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| `validate_site_change_spec` rejects a `new_page` item | "Phase 7: site-change-spec invalid for `<route>` (`<errs>`) — item blocked, Builder NOT invoked. Fix the plan item and re-run." (skip item) |
| Visual-QA gate red after 3 self-heal cycles on a new route | "Phase 7: new page `<route>` failed the visual-QA gate after 3 self-heal cycles — reverted cms-preview, nothing published. Failures: `<list>`." (halt item) |
| Supabase MCP write fails (learnings / run close) | "Phase 7: Supabase write failed (`<error>`). Run NOT closed; re-run to persist. No partial learn." |

## Self-improvement hook

If the Builder/Connector hand-off or the new-route gate keeps flagging a recoverable
mechanics issue (e.g. a known nav-injection quirk per framework), append to `LEARNINGS.md`
under `## Phase 7 — Learn + Persist`:
- `- <YYYY-MM-DD>: <one-line new-page / hand-off mechanics rule>. Triggered by: <context>.`

Generalizable SEO/GEO intelligence stays in the `seo_learnings` Supabase table, not here.

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
