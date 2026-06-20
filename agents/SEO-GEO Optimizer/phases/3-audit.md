# Phase 3 — Audit

**Goal:** Audit the live site **per locale**: deterministic SEO + local score, LLM-judge
GEO readiness, and the GATE-FACT claim/source extraction. Write one `seo_audits` row per
locale.

**Inputs:** `context` + `run_id` from Phase 1, the per-locale URL map. `rubric/rubric.yaml`
for reference. Cap: proxy-LLM ≤ ~15 × locales (`PROXY_LLM_CAP`).

## Steps

For **each locale** in scope (resolved in Phase 1):

1. **Fetch the raw server HTML** for the per-locale URL:
   `raw = render_check.fetch_raw(locale_urls[xx])`.
   This is the GPTBot-style view — exactly what AI/Google bots see (no JS). If the fetch
   fails for one locale → **skip that locale, never halt** the run; note the skip.

2. **Extract signals:** `signals = render_check.extract_signals(raw)` →
   `{h1_count, heading_order_ok, title_len, meta_desc_len, canonical, jsonld_types,
   jsonld_valid, has_localbusiness, og_present, internal_link_count, word_count,
   has_main_content, ...}`.

3. **Deterministic scores:**
   - `seo_score, seo_detail = audit.score_seo(signals)` (Track G — ids align with
     `rubric.yaml` `_SEO_ITEMS`).
   - `local_score, local_detail = audit.score_local(signals)` (Track L).

4. **GEO readiness (LLM-as-judge, temperature 0):** run `prompts.GEO_JUDGE_PROMPT` over the
   page's **own-locale main text**. The judge returns JSON
   `{score, citable_passages, claims:[{text, source, verifiable}]}`:
   - `geo_score` = the readiness score (0–100), scored as a native reader of that locale.
   - The `claims` array is the **GATE-FACT extraction**: every factual claim/statistic/quote
     + its named source, flagged verifiable or not. A page that would require
     fabricated/unverifiable evidence to look good **must not** score highly.
   - **`gate_fact_passed`** = true only if no extracted claim is fabricated/unverifiable.
     (Phase 3 *audits* GATE-FACT on existing content; the hard verbatim-source veto that
     **drops** an edit applies to content the agent *injects* in Plan 3 — but the extraction
     here is what surfaces a fabrication risk in the current site.)

5. **Assemble + persist** (skip writes in `dry-run`):
   `payload = audit.assemble_audit(seo=seo_score, geo=geo_score, local=local_score,
   scores_detail={**seo_detail, **local_detail, "geo": <judge JSON>})`, then:

   ```sql
   INSERT INTO seo_audits (run_id, project_id, locale, seo_score, geo_score, local_score,
                           scores_detail, gate_fact_passed, audited_at)
   VALUES ('<run_id>', '<project_id>', '<xx>', <seo>, <geo>, <local>,
           '<scores_detail_json>'::jsonb, <gate_fact_passed>, now());
   ```

6. After all locales: compute the **merged run scores** (e.g. min or mean across locales —
   default: the **worst** locale's score per track, so the run reflects the weakest page)
   and carry them + the per-item detail into Phase 4.

> **Audit runs per locale, but is REPORTED in English.** The audit READS each live
> per-locale page and the GEO judge scores as a native reader of that locale (so the audit
> genuinely runs per locale). But the operator-facing analysis artifacts — the
> `scores_detail` prose, any narrative notes, and the downstream `seo_runs.summary` /
> `seo_plan_items.rationale` / `seo_competitors.analysis` — are authored in **English
> regardless of the site's locales** (internal, never shipped to the live site). See
> `guidelines/localization.md` (Bucket 3 — INTERNAL → English-only).

7. Echo: *"Phase 3: audited `<N>` locale(s). SEO `<s>` · GEO `<g>` · local `<l>` (merged)."*

## Outputs

- `audits` — one persisted `seo_audits` row per locale
- `merged_scores` — `{seo, geo, local}` for the run (carried to Phase 4)
- `audit_detail` — the per-item pass/fail + the GEO judge JSON (drives the plan)

## Failure feedback (verbatim)

| Cause | Message |
|---|---|
| One locale's URL 404s / fetch fails | "Phase 3: locale `<xx>` page unreachable (`<error>`) — skipped, other locales audited." (continue) |
| GEO judge returns non-JSON | Re-prompt once for strict JSON; if still bad, record `geo_score` as null + flag, continue. |
| All locale fetches fail | "Phase 3: no locale page reachable. Cannot audit — halting the run." |
| Supabase write fails | "Phase 3: `seo_audits` write failed (`<error>`). Scores kept in-memory for the plan." |

## Self-improvement hook

If the GEO judge mis-scores a locale because of a locale-detection quirk (e.g. judged an
NL page as EN), append to `LEARNINGS.md` under `## Phase 3 — Audit`:
- `- <YYYY-MM-DD>: For locale `<xx>`, pin the judge with "<hint>" so it scores as a native reader. Triggered by: mis-scored <context>.`

(The actual scores are per-client memory → `seo_audits`, not here.)

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
