# Guidelines — Localization (per-locale prose vs language-invariant facts vs English-only analysis)

> Durable best-practice knowledge base (reference, **not** per-client memory).
> Per-client audits, plans, history all live in Supabase `seo_*`.
> This is the authoritative agent-facing copy of the research-verified localization
> decision matrix. The design-spec mirror is
> `docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md` (Localization policy).

Source of truth: the verified localization decision matrix. The CMS already ships the
per-locale translation pipeline (DeepL/null provider) + the per-field default-locale
read fallback this guideline relies on. This file tells the agent **what** to localize,
**what** never to localize, and **what** to keep English-only.

---

## The decision matrix — three buckets

Every SEO/GEO output falls into exactly one of three buckets.

### Bucket 1 — PROSE → per-locale via DeepL

Human-readable prose is authored in the website's **DEFAULT locale** and translated
per-locale by the CMS pipeline (`POST /projects/{slug}/seo/translate`, kind `meta` then
`article`). The agent **never hand-writes the non-default locales** for these fields.

- meta `title`
- meta `description`
- OG `title`, OG `description`
- JSON-LD **text** fields only: `name`, `description`, `headline`
- the visible **article / blog / news body** (and `excerpt`)

### Bucket 2 — CODED FACTS / TAGS → language-invariant

Generated per-page or repeated verbatim; **NEVER translated**. These are codes/data, not
prose. The generated site emits the per-page tags itself per locale; the agent never
translates them and the translate endpoint never touches them.

- `canonical`
- `robots`
- `hreflang` (`alternates.languages`)
- `og:locale`
- JSON-LD `inLanguage` — a per-locale **BCP-47 code** on the **WebPage / Article** node
  (NOT on the `LocalBusiness` node)
- JSON-LD **data**: address, telephone/phone, geo, `openingHours`, `sameAs`, `image`
- `og:image`
- `hero_image_url`

### Bucket 3 — INTERNAL → English-only

Operator-facing analysis is authored in **English regardless of the site's locales**; it
is **never shipped** to the live site.

- audit scores (`seo_audits` scores + detail)
- plan rationale (`seo_plan_items.rationale`)
- competitor analysis (`seo_competitors.analysis`)
- run summary (`seo_runs.summary`)

> The audit **RUNS per locale** (it reads each live per-locale page and the GEO judge
> scores as a native reader of that locale) — but the audit is **REPORTED in English**.
> Running per-locale and reporting in English are not in tension.

---

## Unifying rule

**Google determines a page's language from its VISIBLE CONTENT — not the metadata, not the
`lang` attribute, not hreflang.** So localizing metadata is a **CONSISTENCY requirement
with already-translated visible content**, not a standalone ranking lever. We localize meta
because shipping default-locale metadata over translated body text is *inconsistent*, not
because translated metadata ranks on its own.

---

## Failure / fallback rule

On a missing or failed translation, **OMIT the field** — never write `""` or `null`. An
explicit empty value *blocks* the fallback; an omitted field lets it fire. The public read
path then falls back **per field** to the default-locale text, so a live page is never
broken or empty.

- **Per-field / template fallback is NOT duplicate content.** A page that shows a
  translated body with a few default-locale meta fields filled in by fallback is one page,
  not a duplicate.
- **A WHOLE untranslated body MUST NOT be published as a separate same-language URL.**
  Until a body is actually translated, exclude that locale URL from hreflang and from the
  index — do not ship the default-locale body under a second locale's route as if it were
  translated content.

---

## Precise-wording guards (do not overstate)

- A title/metadata in a different language than the body is a **SERP DISPLAY override**
  (Google may rewrite what it shows in the result), **NOT a ranking penalty**.
- Raw machine translation is a **QUALITY-based ranking risk** (thin/awkward content can
  rank worse), **NOT a manual action / penalty**. There is no "auto-translation penalty"
  flag to trip; the risk is quality, full stop.

---

## SSR prerequisite (per locale)

Gate item **G-1 — content present in the raw server HTML** applies to **EVERY locale, not
just the default**. AI crawlers and Google bots do **not** run JS, so every locale's page
must server-render its (translated) content into the raw HTML. A locale that only fills in
client-side fails G-1 the same as the default would.

---

## GEO caveat (no AI-citation promise)

**No source ties metadata LANGUAGE to AI-citation.** Justify per-locale metadata on Google
**consistency + CTR** only — never as an AI-citation lever. Do not claim that localizing
metadata makes a page more likely to be cited by an answer engine.

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
