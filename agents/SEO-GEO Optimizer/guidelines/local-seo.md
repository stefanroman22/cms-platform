# Guidelines — Track L: Local SEO

> Durable best-practice knowledge base (reference, **not** per-client memory).
> Per-client audits, plans, competitor intel all live in Supabase `seo_*`.
> Every rule carries `[confidence | source]`. Refuted myths are listed at the bottom and
> must **never** be asserted or scored on.

Source of truth: `docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md` (Guidelines KB → Track L).

---

## L-1 — LocalBusiness structured data (auto)

Ship valid `LocalBusiness` (or a specific subtype: `HairSalon`, `Restaurant`, `Store`,
`Dentist`, `ProfessionalService`, …) JSON-LD with name, address, phone, geo, opening
hours, and URL. This is the strongest **automatable on-site** local signal and the entity
anchor an AI engine reads for a "near me" answer. `[high | schema.org LocalBusiness]`

- Deterministic check: `L-1_localbusiness_jsonld` (a local-type JSON-LD node is present).
  Weight 60 of the local score — it is the dominant on-site local lever we can verify.

## L-onpage — Local content present in raw HTML

The page must actually carry local content (services + location text) in the raw server
HTML, so the entity is legible to bots. Empty client-rendered shells fail this.
`[high | render_check.py]`

- Deterministic check: `L-onpage_has_content` (`has_main_content`). Weight 40.

## NAP consistency (site-internal, auto)

**N**ame / **A**ddress / **P**hone must be **internally consistent across the client's own
site** (footer, contact page, JSON-LD, schema). The agent checks site-internal NAP
consistency only — it cannot crawl every external directory. Cross-directory NAP and
true citation audits are a paid-API/human concern (below). `[medium | local-SEO consensus;
NOT the refuted "74% AI-exclusion" myth — see forbidden block]`

## Review velocity / recency (ADVICE, never a multiplier)

Recent, steady reviews are **advice** — present them as "keep reviews fresh" guidance,
**hedged**, and **never** as a numeric ranking multiplier. We do not assert any
"N reviews → X× clicks" figure (those are in the forbidden block). Review acquisition
itself is a **human** action (flagged, not automated). `[low | hedged advice only]`

## Geo-grid Share-of-Local-Voice (PAID-API — flagged upsell, never faked)

True geo-grid / map-pack rank tracking ("Share of Local Voice" across a grid of points)
requires a **paid Google Places / SERP API** (e.g. Local Falcon style). The agent **does
not fabricate** rank-grid numbers. It flags this as an optional paid upsell with an
explicit ceiling note — never invents a position. `[high | paid-data honesty rule]`

- Rubric: marked `measure: paid-api`, `deferred: true`.

## MVP — "Local Lite" single-origin organic proxy

For now Local ships as a **single-origin "Local Lite"** proxy: site-internal NAP + valid
`LocalBusiness` JSON-LD + on-page local content + an LLM-judge "would an engine surface
this for a near-me query?" proxy, all from one origin (no grid, no paid API). The
dashboard states the ceiling honestly: this is an on-site readiness proxy, not a live
map-pack rank. `[high | design spec scope boundary]`

---

## Automatable vs paid vs human (set client expectations honestly)

- **Automatable (free, every run):** competitor discovery + server-rendered HTML/JSON-LD
  extraction + content-gap reasoning; site-internal NAP; the local on-site signals above;
  GEO-citation proxy.
- **Paid-API upsell (optional, future):** true geo-grid SoLV, review velocity, rank /
  AI-Overview tracking (Google Places / SERP).
- **Human (flagged, never faked):** backlinks / off-page, E-E-A-T / author authority,
  **actual Google Business Profile edits + review acquisition** — surfaced as
  `manual_human` plan items, never auto-applied or faked.

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
