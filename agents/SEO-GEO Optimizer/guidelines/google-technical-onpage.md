# Guidelines — Track G: Google technical + on-page

> Durable best-practice knowledge base (reference, **not** per-client memory).
> Per-client audits, plans, history, competitor intel all live in Supabase `seo_*`.
> This file is the rule set the auditor (`audit.py` + the GEO judge) and the planner
> consult. Every rule carries `[confidence | source]`. Refuted myths are listed at the
> bottom and must **never** be asserted or scored on.

Source of truth: `docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md` (Guidelines KB → Track G).

---

## G-1 — Content must live in the raw server HTML

AI crawlers (GPTBot, OAI-SearchBot, PerplexityBot, Google-Extended) **do not execute
JavaScript**; Googlebot defers JS to a second render pass. Any text/heading/link that
only appears after client-side hydration is invisible to AI answer engines and risky for
Google. **Server-render (SSR/SSG) the primary content.** Audit by fetching with a
GPTBot-style UA (`render_check.fetch_raw`) and asserting the content is present in the
raw bytes. `[high | render_check.py; OpenAI/Perplexity crawler docs]`

- Deterministic check: `G-1_content_in_raw_html` (`has_main_content`, word_count ≥ 50).
- A client-rendered shell (`<div id="root">`) scores zero here — flag it as the highest-priority fix.

## G-2 — robots / crawl access for AI bots

Do not block AI answer-engine crawlers in `robots.txt` unless the client explicitly opts
out of GEO. A page no bot can fetch cannot be cited or ranked. Treat an AI-bot
`Disallow` as a `manual_human` decision surfaced to the client, never a silent block.
`[high | crawler robots policies]`

## G-3 — One H1 + clean heading hierarchy + short one-idea paragraphs

Exactly **one `<h1>`** per page. Headings descend without skipping a level
(`h1 → h2 → h3`, never `h1 → h4`). Paragraphs are short and carry **one idea each** —
this is the citable unit for both Google featured snippets and AI extraction.
`[high | on-page SEO consensus; KDD 2024 arXiv:2311.09735 for citable structure]`

- Deterministic checks: `G-3_single_h1`, `G-3_heading_order`.

## G-4 — Title + meta description: length and uniqueness, per page + per locale

- Title **50–60 chars**, unique per page and per locale.
- Meta description **140–160 chars**, unique per page and per locale.
- Never reuse the same title/description across pages or across locales (a translated
  page needs its own translated title + description).
`[high | SERP-snippet truncation behaviour]`

- Deterministic checks: `G-4_title_len` (40–60), `G-4_meta_desc_len` (120–165). The
  audit predicate band is slightly wider than the ideal target so a "good-enough" title
  passes; the *plan* still nudges toward 50–60 / 140–160.

## G-5 — Canonical + hreflang

Every indexable page declares a self-referential `rel="canonical"`. Multilingual pages
declare reciprocal `hreflang` alternates (one per locale + `x-default`). Missing
canonicals cause duplicate-content dilution; missing hreflang causes the wrong-locale
page to surface. `[high | Google canonical/hreflang docs]`

- Deterministic check: `G-5_canonical` (canonical present). hreflang correctness is
  assessed by the auditor's judgement layer per locale (not a single deterministic flag).

## G-6 — Valid JSON-LD structured data

Ship valid `application/ld+json` (e.g. `LocalBusiness`, `Organization`, `BreadcrumbList`,
`Article` for blog posts). Treat schema as a **Google rich-result + structured machine
signal** that helps both Google and AI extraction parse the entity — **NOT** as an
AI-citation multiplier. FAQ markup is allowed **only where the content is genuinely a
Q&A**; it carries no SERP-ranking or AI-citation multiplier (see the de-myth note and the
forbidden block). Invalid JSON (parse failure) is worse than none — it gets ignored and
signals sloppiness. `[high | schema.org; de-mythed per adversarial verification]`

- Deterministic check: `G-6_jsonld_valid` (≥1 JSON-LD block AND all blocks parse).

## G-8 — Internal linking

Every page links to at least one other internal page; orphan pages get crawled and ranked
poorly. Use descriptive anchor text. `[medium | crawl-depth / link-equity consensus]`

- Deterministic check: `G-8_internal_links` (≥1 internal link).

## G-onpage_og — Open Graph / social cards

Provide `og:title` + `og:image` (and Twitter card equivalents) so shared links render a
card. Indirect SEO value (CTR on social), direct UX value. `[medium | OG protocol]`

- Deterministic check: `G-onpage_og` (`og:title` or `og:image` present).

## CWV — Core Web Vitals (measured on a cadence, NOT every iteration)

Targets: **LCP < 2.5 s, INP < 200 ms, CLS < 0.1** (field/lab). Measure on a cadence
(e.g. once per run or weekly), **not** on every self-heal iteration — per-iteration
headless-browser / PageSpeed Insights runs blow the cost budget and add noise. Flag CWV
as a `paid-api`/cadence item in the rubric (`deferred: true`), not a per-iteration gate.
`[high | web.dev CWV thresholds]`

---

## De-myth note (read before recommending schema)

Schema markup (incl. FAQ) is a **structured signal + Google rich-result enabler**, never
an AI-citation or ranking multiplier. Recommend FAQ schema **only** when the page already
contains genuine question-and-answer content the user would ask — never bolt on a fake FAQ
to chase a multiplier that does not exist. The only evidence-backed GEO levers are real
citations / quotations / statistics (Track E), not schema volume.

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
