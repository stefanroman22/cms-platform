# Guidelines — Track E: GEO (Generative-Engine / AI answer-engine optimization)

> Durable best-practice knowledge base (reference, **not** per-client memory).
> Per-client audits, plans, history all live in Supabase `seo_*`.
> Every rule carries `[confidence | source]`. Refuted myths are listed at the bottom and
> must **never** be asserted or scored on.

Source of truth: `docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md` (Guidelines KB → Track E).

---

## What GEO is

**GEO = optimizing a page so AI answer engines (ChatGPT Search, Perplexity, Google AI
Overviews, Gemini) are more likely to CITE it.** We score and sell **readiness**, never an
actual citation — there is no obtainable ground truth for "did engine X cite us," so the
product contract is "AI-answer readiness," never "we get you cited." `[high | Goodhart
risk; design spec hard constraint #5]`

## E-1 — The only evidence-backed levers

The measured levers are **real source citations, real direct quotations, and real
statistics**, which lift AI-citation likelihood by roughly **30–40% relative** on a
synthetic metric. Keyword-stuffing / keyword density gives **~0 lift** — do not rely on
it. `[high | KDD 2024 GEO study arXiv:2311.09735]`

- **REAL** is load-bearing: every injected statistic/quote/citation must name a real,
  fetchable source (see GATE-FACT below). A fabricated stat is worse than none.
- Optimize **intrinsic content quality** (would a knowledgeable human cite this passage?),
  not fixed engine tricks.

## E-2 — The "~40%" caveat (never a guarantee)

The ~30–40% headline is **best-case RELATIVE lift on a synthetic benchmark metric**, not a
promise of ranking, traffic, or an actual citation. **Never** quote it to a client as a
guarantee or an absolute number. The plan and dashboard copy sell readiness, never a
position. `[high | design spec; honest-expectations rule]`

## E-3 — Machine-readability overlap with Track G

GEO and technical SEO share a substrate: **server-rendered HTML (bots don't run JS),
clean `h1 → h2 → h3`, short one-idea paragraphs, valid JSON-LD.** A page that fails Track
G's G-1 (content not in raw HTML) cannot be cited by an AI engine at all. Fix the Track-G
floor first; it is a prerequisite for any GEO gain. `[high | cross-track; render_check.py]`

## E-4 — GATE-FACT (factual-accuracy guard) — the hard veto

Every injected statistic / quotation / citation MUST:
1. Name a **source + URL**.
2. Be **WebFetched** at audit/apply time.
3. Have its **verbatim claim sentence found as a literal substring** in the fetched page.

A miss ⇒ the edit is **dropped** and the iteration **fails** (the score is not averaged
away). Per-locale: a Dutch claim must verify against a Dutch source. This defeats the
SAGEO fabrication failure mode — an LLM judging an LLM is insufficient, so we require a
deterministic verbatim-substring check, not just judge confidence. `[high | SAGEO
fabrication finding; design spec hard constraint #2]`

The GEO judge prompt (`prompts.GEO_JUDGE_PROMPT`) extracts every claim + source and flags
fabricated/unverifiable ones; a page that would require fabricated evidence to score well
**must not** score highly.

## E-5 — Anti-overfitting

Score **intrinsic quality**, not hard-coded per-engine tricks. **No** MAP-Elites /
evolutionary trick-search over a synthetic citation metric (Goodhart trap), **no** engine
fingerprinting, **no** keyword/density hacks. The GEO judge runs at temperature 0 over the
page's own-locale main text and rewards genuine citability (real evidence + clean
structure). `[high | design spec anti-overfitting note]`

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
