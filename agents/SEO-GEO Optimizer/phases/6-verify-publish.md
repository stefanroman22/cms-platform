# Phase 6 — Verify + Publish

**Goal:** Run the **visual-QA + self-heal gate** over everything Phase 5 drafted, then
**publish only when all-green**. Nothing reaches production unless the gate passes. If it
can't be made green within the bounded self-heal budget → **halt and revert**, never publish.

The drafts under test were written in Phase 5 (`seo_page_meta` / `seo_articles` via
`apply.build_page_meta_payload` / `apply.build_article_payload`, content edits authored by
the **`geo-content-writing`** skill). This phase only verifies and publishes them.

**Inputs:** the `seo_changes` ids + the set of **affected routes × locales** from Phase 5;
the project's **cms-preview URL** (drafts) and the **Vercel preview URL** (if any code rode
along); `run_id`, `project_id`, `project_slug`. Drives the **`seo-visual-qa`** skill and the
deterministic verdict in `gate.evaluate_gate`. Cap: `PLAYWRIGHT_RENDER_CAP` ≈ 9 × locales ×
iters.

## Steps

1. **Run the gate.** Invoke the **`seo-visual-qa`** skill over the affected routes × locales
   (drafts on cms-preview; code on the Vercel preview if a Website Builder change was
   involved). The skill renders each route at **375 / 768 / 1440** px per locale with
   Playwright MCP, gathers console errors, `next build` exit, internal-link resolution, the
   `playwright-user-stories` smoke result, and `render_check.fetch_raw` content-in-raw-HTML,
   then assembles the `checks` dict (keys `viewports`, `console_errors`, `build_ok`,
   `broken_links`, `smoke_ok`, `content_in_raw_html`) and calls
   **`gate.evaluate_gate(checks)`** → `{passed, failures, checked_viewports}`. Fail-closed: a
   missing/partial render set is a failure.

2. **If NOT green** → the `seo-visual-qa` skill runs the **bounded self-heal loop**
   (`brainstorming` → `writing-plans` → apply via `ui-ux-pro-max` + `frontend-design` →
   re-render → re-evaluate), **≤ 3 cycles**. If a cycle turns it green → go to step 3. If it
   is **still red after ≤3 cycles → HALT**:
   - Revert the drafts: delete the draft `seo_page_meta` / `seo_articles` rows for this run,
     or restore the prior content draft / discard the `cms-preview` code change.
   - Mark the related changes reverted + store the proof:

     ```sql
     UPDATE seo_changes
     SET reverted = true, verified = '<{"passed":false,"failures":[…],"screenshots":[…]}>'::jsonb
     WHERE run_id = '<run_id>';
     ```
   - Note the halt in the `seo_runs` summary and surface the failure to the operator.
   - **DO NOT publish.** Stop the run.

3. **If green** → **publish.** Store the gate proof on each change
   (`seo_changes.verified` = the per-check pass/fail + screenshot refs), then:
   - **SEO area:** flip the drafted rows to published via Supabase MCP —

     ```sql
     UPDATE seo_page_meta SET status = 'published', updated_at = now()
     WHERE project_id = '<project_id>' AND status = 'draft' AND (route, locale) IN (…);
     UPDATE seo_articles SET status = 'published', updated_at = now()
     WHERE project_id = '<project_id>' AND source_run_id = '<run_id>' AND status = 'draft';
     ```
   - **Site content edits** (the `save_service` drafts): publish via the existing endpoint —
     **`POST /projects/{slug}/publish`** (the platform's publish path, admin bearer).
   - Stamp the changes published + advance the items:

     ```sql
     UPDATE seo_changes SET published_at = now() WHERE run_id = '<run_id>' AND reverted = false;
     UPDATE seo_plan_items SET status = 'published', updated_at = now()
     WHERE run_id = '<run_id>' AND status = 'applied';
     ```

4. **Update the run.** Append what was applied + published to the `seo_runs` row (re-open /
   append if it was already `completed` from the audit), recording the result in
   `summary` / `scores`:

   ```sql
   UPDATE seo_runs
   SET summary = '<… applied N, published M; gate green / halted …>',
       scores = '<{"seo":..,"geo":..,"local":..}>'::jsonb,
       finished_at = now()
   WHERE id = '<run_id>';
   ```
   Echo the dashboard path: *"Phase 6: gate green — published `<M>` change(s). View:
   dashboard → `<project_slug>` → SEO & GEO → History (with visual-QA proof)."* (Or, on halt:
   *"Phase 6: gate could not be made green in 3 self-heal cycles — reverted, nothing
   published. See `<failures>`."*)

5. **New-page tripwire (Plan 4 hook).** If any **newly-published** route is a brand-new page
   type, print the one-line note: *"new page type `<X>` went live — glance recommended."*
   The page-creation itself is **Plan 4** (cross-agent `site-change-spec` → Website Builder
   incremental + Connector); in this build the tripwire is informational only.

## Outputs

- On green: published `seo_page_meta` / `seo_articles` (`status='published'`); published site
  content via `POST /projects/{slug}/publish`; `seo_changes.published_at` set;
  `seo_plan_items.status='published'`; `seo_changes.verified` proof for the History tab.
- On halt: drafts reverted, `seo_changes.reverted=true`, run summary notes the halt, nothing
  published.

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| Gate red after 3 self-heal cycles | "Phase 6: visual-QA gate unrecoverable after 3 self-heal cycles — reverted drafts, nothing published. Failures: `<list>`." (halt) |
| Publish endpoint (`POST /projects/{slug}/publish`) fails | "Phase 6: site-content publish failed (`<error>`). SEO-area rows NOT promoted; re-run to retry. No partial publish." |
| `seo_page_meta`/`seo_articles` status flip fails | "Phase 6: SEO-area publish write failed (`<error>`). Left as draft; re-run to retry." |
| Empty / partial render set | Fail-closed — treated as a red gate (per `gate.py`); never publish. |

## Self-improvement hook

If the gate keeps flagging a recoverable mechanics issue (e.g. a known component overflows at
375 until a specific Tailwind class is applied), append to `LEARNINGS.md` under
`## Phase 6 — Verify + Publish`:
- `- <YYYY-MM-DD>: <one-line gate/self-heal mechanics rule>. Triggered by: <context>.`

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
