# SEO/GEO Optimizer Agent — Design

**Date:** 2026-06-14
**Status:** Approved (shape) — Approach 1 (orchestrator). Pending written-spec review.
**Author:** Stefan + Claude
**Evidence base:** 105-agent deep-research harness (23 sources, 25 claims adversarially verified — 15 confirmed / 10 refuted) + 7-agent design workshop (5 specialists → adversarial critic → synthesis). Verified findings + the 11 forbidden ("refuted") claims are embedded in this spec (see *Guidelines KB* below) and in the project's auto-memory (`project_seo_geo_agent.md`). Re-runnable workshop script: `c:\tmp\seo-geo-agent-design.js`.

---

## Purpose

A 4th first-class pipeline agent — **"SEO/GEO Optimizer"** — that takes a client's live, CMS-wired website and autonomously raises its visibility on **both** Google (classic + local SEO) **and** AI answer engines (GEO: ChatGPT Search, Perplexity, Google AI Overviews, Gemini). It is invoked manually from Claude Code (`Run SEO agent for <project>`), like the CMS Connector, with a clean entrypoint a future Hetzner worker can call. It:

- scans the business category + location and does **deep, reasoned competitor + local intelligence**;
- **audits** the live site (technical SEO + GEO machine-readability + local), per-locale;
- writes a **clear, reasoned plan** (what's been done / what's next / schedule) into Supabase;
- **autonomously applies** improvements — meta/schema/structure + GEO content edits + new articles — into a **dedicated SEO/GEO CMS area** that client and admin can also read/edit/delete;
- when the site needs **new pages/sections**, it **auto-invokes** the Website Builder + CMS Connector through one shared contract;
- **auto-publishes** every change — but only through a hard **visual-QA + self-heal gate** (save → verify on cms-preview at mobile/laptop/desktop → fix breakage itself → re-verify → publish);
- **remembers each client** (audits, plan, history, competitor intel) and **self-improves across clients**, all in **Supabase** (not markdown files);
- **runs in a loop** per project until its scored rubric passes or its budget/iteration cap is hit;
- surfaces everything in a new dashboard **"SEO & GEO"** section beside CMS/Bookings.

**Non-goals for this design:** pricing, tiers, billing, paywalls, and any client-facing monetization (the operator handles pricing separately). No phased feature-rollout — all SEO/GEO capabilities live in **one** agent.

---

## Architecture decision

**Chosen: a skill-driven orchestrator that runs in the main Claude Code thread** (like the CMS Connector and Design Prompt Creator), **not** a restricted subagent.

Rationale: the agent must auto-invoke the Website Builder (a restricted subagent) and the CMS Connector, run multi-agent fan-out for competitor analysis, and drive Playwright. Restricted subagents lack the `Agent`/`Workflow`/MCP surface to do that. The Connector already proves the "skill + `AGENTS.md` + `phases/` + Python helpers, run in the main thread with full tools" model. The SEO/GEO Optimizer follows it exactly.

- **Source-of-truth docs:** `agents/SEO-GEO Optimizer/` (`AGENTS.md`, `phases/`, Python helpers).
- **Executable entry point:** `.claude/skills/seo-geo-optimizer/SKILL.md` (trigger, first steps, token rules) — mirrors `.claude/skills/cms-connector-website/SKILL.md`.
- **Per-client memory + self-improvement:** Supabase tables (replaces the markdown `LEARNINGS.md`/`research/<cat>.md` cache the other agents use). A thin `agents/SEO-GEO Optimizer/LEARNINGS.md` is kept ONLY for agent-mechanics lessons (how the agent itself behaves); all client- and category-level memory is in Supabase.

**Rejected alternatives:**
- *Restricted subagent (like Website Builder).* Cannot orchestrate other agents or drive MCP — fatal for the auto-invoke + Playwright requirements.
- *Monolith that edits the Next.js repo directly.* Duplicates the Website Builder, abandons its proven build quality, and removes the one-contract coordination point. Rejected.
- *Markdown per-client memory in the repo.* Doesn't scale across clients, isn't visible to the dashboard, and pollutes the repo. Supabase chosen (operator request).

---

## Resolved decisions (the four forks)

| Fork | Decision |
|---|---|
| **Run environment (now)** | Manual from Claude Code; results written to Supabase; dashboard reads them live. A dashboard "Run"/"Write articles" button enqueues a `seo_jobs` row the operator (or a future worker) executes. Designed server-ready; **no new infra required now**. |
| **SEO CMS area ownership** | Agent writes **autonomously, no approval gate**. Client **and** admin can read/edit/delete the same data via the dashboard. The agent has standing autonomy; humans can override. |
| **Go-live** | **Auto-publish everything**, but only behind the **visual-QA + self-heal gate** (save → verify on cms-preview across mobile/laptop/desktop: responsive, text + images fully visible, no crash, no console errors, build passes, links resolve → if broken, the agent fixes it using brainstorming → writing-plans → ui-ux-pro-max → frontend-design → re-verify → publish). |
| **New pages / cross-agent** | The agent **auto-invokes** Website Builder (incremental mode) + CMS Connector through one `site-change-spec` contract, then runs the same gate before publishing. First time a *new page type* ships, the run summary prints a one-line "new page type X went live — glance recommended" tripwire (still hands-off). |

---

## File layout

```
agents/SEO-GEO Optimizer/
├── AGENTS.md                    # authoritative spec: phases, autonomy, constants, failure modes
├── README.md                    # quick reference: invoke, files, defaults
├── LEARNINGS.md                 # append-only AGENT-MECHANICS lessons ONLY (client memory → Supabase)
├── example-prompts.md
├── prompts.py                   # SYSTEM_PROMPTs: auditor, competitor-analyst, geo-writer, reflector, gate-judge
│                                #   + the FORBIDDEN-CLAIMS block (the 11 refuted claims) embedded verbatim
├── orchestrator.py              # run lifecycle: phase sequencing, the iterate-until-done loop, budget/caps
├── audit.py                     # deterministic SEO scoring + GEO proxy scoring harness → rubric
├── render_check.py              # fetch live/preview HTML with a GPTBot-style UA; assert content in raw HTML
├── competitor.py                # competitor discovery + HTML/JSON-LD extraction helpers (free tools)
├── cms_client.py                # Supabase + backend SEO-router client (read site content, write SEO area)
├── gate.py                      # visual-QA gate helpers (drives Playwright MCP results → pass/fail report)
├── rubric/
│   ├── rubric.yaml              # ~30 atomic checklist items: id, track, check, measure, auto?, weight, threshold
│   └── pass-gate.md             # convergence: per-track thresholds + MAX_ITERS=3 + cost budget + GATE-FACT veto
├── guidelines/                  # the durable best-practice KB (3 tracks) — reference, NOT per-client memory
│   ├── google-technical-onpage.md
│   ├── geo-answer-engines.md
│   └── local-seo.md
├── phases/
│   ├── 0-parse-intent.md
│   ├── 1-load-context.md        # load Supabase client memory + detect business/category/location/locales
│   ├── 2-competitor-intel.md    # deep, reasoned competitor + local analysis (fan-out + synthesis)
│   ├── 3-audit.md               # render + score per-locale → seo_audits
│   ├── 4-plan.md                # reasoned prioritized plan → seo_plan_items (+ schedule)
│   ├── 5-apply.md               # write SEO area; emit site-change-spec + auto-invoke builder/connector
│   ├── 6-verify-publish.md      # the visual-QA + self-heal gate → publish
│   └── 7-learn.md               # persist run, distill seo_learnings, print summary + tripwire
└── tests/                       # pytest for audit.py / render_check.py / competitor.py / gate.py / cms_client.py

.claude/skills/
├── seo-geo-optimizer/SKILL.md   # THE ENTRY POINT (trigger, first steps, token rules) — main-thread skill
├── seo-geo-audit/SKILL.md       # NEW: rubric + scoring + render-check methodology
├── geo-content-writing/SKILL.md # NEW: citation/quote/statistic content with the verbatim-source factual gate
├── competitor-intel/SKILL.md    # NEW: competitor discovery + reasoned analysis methodology
└── seo-visual-qa/SKILL.md       # NEW: the Playwright breakpoint gate + self-heal loop

backend/
├── auth_service/routers/seo.py  # NEW router: agent-write + human-CRUD + public site-consumer endpoints
├── auth_service/models/seo_schemas.py   # NEW Pydantic schemas
└── migrations/2026_06_14_seo_geo.sql    # NEW additive migration (tables + RLS + project columns)

frontend/src/
├── components/dashboard/sectionConfig.ts        # + "seo" SectionKey + PROJECT_SECTIONS row
├── components/dashboard/seo/SeoSection.tsx       # NEW (cloned from BookingsSection)
├── components/dashboard/seo/{Overview,Plan,History,Articles,Competitors,Settings}Tab.tsx
└── components/dashboard/seo/api.ts               # typed fetch helpers for the seo router

# Cross-agent edits (see "Cross-agent coordination"):
.claude/skills/seo-pro/SKILL.md                  # de-myth + add forbidden-claims note
agents/Website Builder/AGENTS.md + phases/        # + incremental "add pages" mode + SEO-area awareness
agents/CMS Connector - Website/AGENTS.md + phases/4-integration.md + LEARNINGS.md  # + SEO-area provisioning/wiring + hard rule
agents/README.md                                  # + catalog row for SEO-GEO Optimizer
```

---

## The agent — phases

Trigger: **`Run SEO agent for <project_slug>`** (close paraphrases match, per the skill). Optional flags: `locale <xx>` (scope to one locale), `audit-only` (no apply/publish), `articles <N>` (run an article campaign), `dry-run` (plan only, no writes).

**Autonomy:** WebSearch, WebFetch, Playwright MCP, Supabase MCP, and CMS-admin writes are all pre-authorized — the agent never pauses to ask permission for research, fetching, rendering, or writing. It pauses only on the failure modes below.

| # | Phase | Reads | Writes | Notes |
|---|-------|-------|--------|-------|
| 0 | Parse intent | trigger string | — | extract slug + flags |
| 1 | Load context | Supabase client memory (`seo_runs`/`audits`/`plan`/`learnings`), `projects` row, live site, lead link | open `seo_runs` row | detect business name, category bucket, **location/country**, locales, repo, prod + preview URLs |
| 2 | Competitor + local intel | WebSearch/WebFetch (capped), `seo_competitors` cache | `seo_competitors` + analysis | **fan-out** discovery (`<category> <city>`, top services), fetch competitors' server-rendered HTML + JSON-LD, then a **reasoned synthesis** pass (content gaps, schema gaps, GEO-citation gaps); location-agnostic, personalized per business |
| 3 | Audit | live site via `render_check.py`/Playwright, published CMS content, `rubric.yaml` | `seo_audits` (per-locale) | deterministic SEO score + GEO proxy (LLM-as-judge, temp 0) + local score; **GATE-FACT extraction** lists every claim+source |
| 4 | Plan | audit + intel + guidelines KB + `seo_learnings` | `seo_plan_items` (+ schedule, rationale, plain-language) | reasoned, prioritized; marks each item `action_kind`: `content`/`meta`/`schema`/`article`/`new_page`/`manual_human` |
| 5 | Apply | plan | SEO CMS area (`seo_page_meta`, `seo_articles`), `seo_changes`; **`site-change-spec`** for `new_page` items → auto-invoke Website Builder (incremental) + Connector | content/meta/schema/articles written autonomously to **draft**; `manual_human` items (backlinks, GBP) flagged not faked |
| 6 | Verify + publish | cms-preview / Vercel preview | `seo_changes.verified`, publishes | **the gate** (next section); loops with self-heal until green; then publish content + promote code |
| 7 | Learn + persist | run artifacts | `seo_runs` (close), `seo_learnings` (global), summary | distill generalizable rules; print summary + new-page-type tripwire |

### The iterate-until-done loop (Phase 3–6)

```
open_run()
score = audit(project, locales)              # deterministic SEO (per published baseline) + GEO proxy (live)
i = 0
while True:
    if score.passes(rubric) and gate_fact_clean:  return halt("pass")
    if i >= MAX_ITERS (=3):                        return halt("maxiter", gaps)
    if cost.exceeded(BUDGET):                      return halt("budget")
    if no_targeted_fixes_left:                     return halt("converged")
    plan   = plan_fixes(score.misses, intel, guidelines)   # reasoned
    apply_to_DRAFT(plan)                          # content/meta/schema/articles + (new_page → builder/connector)
    gate   = visual_qa_gate(preview)              # render + self-heal until green (own inner loop)
    if not gate.green:                            return halt("gate_unrecoverable", gate.report)
    publish(plan)                                 # content publish + code promote (only after green)
    new    = rescore(project, locales)            # GEO/content items move; SSR/CWV re-measure post-publish
    if new < score: revert_last_publish_safely()  # REGRESSION_GUARD; keep best-so-far
    else: score = new
    i += 1
persist(run, score); distill_learnings()
```

**Termination is guaranteed** by `MAX_ITERS=3` + cost budget + plateau guard (research finding: Reflexion has no convergence guarantee, so the rubric supplies the halt). Pass gate: GEO proxy ≥ 75 AND Track-G ≥ 85 AND local auto+proxy ≥ 80 AND GATE-FACT clean AND no hard item below its own threshold. Cost budget per run: WebSearch ≤ 12, WebFetch ≤ 12 @ 100 KB, proxy-LLM ≤ ~15 × locales, Playwright renders ≤ ~9 × locales × iterations.

---

## The visual-QA + self-heal gate (the load-bearing safety system)

Nothing is published until the gate is **all-green**. For each change set, on cms-preview (content) and the Vercel preview deploy (code):

1. **Render** the affected routes with Playwright MCP at **375 / 768 / 1440** px, per locale.
2. **Assert:** no horizontal overflow; primary text fully visible (not clipped/zero-height/overlapping); images loaded with real dimensions (no broken/0×0); tap targets ≥ 44px on mobile; **no console errors**; `next build` exits 0 (code changes); all internal links resolve (no 404); the existing `playwright-user-stories` smoke still passes; and `render_check.py` confirms the new/edited content is present in **raw server HTML** (GPTBot view).
3. **On any failure → self-heal, do not publish:** invoke `brainstorming` → `writing-plans` (a short fix plan) → apply via `ui-ux-pro-max` + `frontend-design` → re-render → re-assert. Bounded retries (≤ 3 self-heal cycles per change set); if still red, **halt the whole run**, revert the draft/branch, write a `seo_changes` failure record, and surface it — never publish a broken state.
4. **On green → publish:** content via `POST /projects/{slug}/publish`; code via promote cms-preview → production branch (Connector path).

Captured into `seo_changes.verified` (screenshots refs + pass/fail per check) so the dashboard History tab shows proof.

---

## Memory + data model (Supabase) — `2026_06_14_seo_geo.sql` (additive)

All additive + behavior-preserving (a project with no SEO rows behaves exactly as today). RLS mirrors `2026_05_09_tenant_tables_rls.sql` (owner-or-admin reads; agent/admin writes via service role / admin bearer).

```sql
-- project flags (per-column convention, like locales/booking)
alter table public.projects add column if not exists seo_enabled boolean not null default false; -- shows the tab
alter table public.projects add column if not exists seo_blog_route text;                        -- e.g. '/blog' once articles exist
alter table public.projects add column if not exists seo_last_run_at timestamptz;

-- run lifecycle + per-client memory
create table public.seo_runs (id uuid pk, project_id uuid fk, status text, trigger text,
  locale_scope text[], scores jsonb, summary text, started_at timestamptz, finished_at timestamptz);
create table public.seo_audits (id uuid pk, run_id uuid fk, project_id uuid fk, locale text,
  seo_score int, geo_score int, local_score int, scores_detail jsonb, gate_fact_passed boolean, audited_at timestamptz);
create table public.seo_plan_items (id uuid pk, project_id uuid fk, run_id uuid fk, track text,
  title text, description text, rationale text, priority int, effort text,
  action_kind text,            -- content|meta|schema|article|new_page|manual_human
  target text,                 -- route or service key
  status text default 'planned', created_at timestamptz, updated_at timestamptz);
create table public.seo_changes (id uuid pk, project_id uuid fk, run_id uuid fk, plan_item_id uuid fk,
  kind text, target text, before jsonb, after jsonb, verified jsonb, reverted boolean default false,
  applied_at timestamptz, published_at timestamptz);
create table public.seo_competitors (id uuid pk, project_id uuid fk, run_id uuid fk, name text, url text,
  location text, signals jsonb, analysis text, captured_at timestamptz);

-- the dedicated SEO/GEO CMS area (agent writes; client+admin CRUD; site consumes)
create table public.seo_page_meta (id uuid pk, project_id uuid fk, route text, locale text,
  title text, description text, canonical text, og jsonb, json_ld jsonb, robots text,
  status text default 'draft',  -- draft|published
  updated_by text, updated_at timestamptz, unique(project_id, route, locale));
create table public.seo_articles (id uuid pk, project_id uuid fk, slug text, locale text,
  title text, excerpt text, body text, json_ld jsonb, hero_image_url text,
  status text default 'draft', source_run_id uuid, updated_by text, created_at timestamptz, updated_at timestamptz,
  unique(project_id, slug, locale));

-- cross-client self-improvement (global) + job queue (dashboard button → operator/worker)
create table public.seo_learnings (id uuid pk, scope text, category text, rule text, source text, confidence text, created_at timestamptz);
create table public.seo_jobs (id uuid pk, project_id uuid fk, kind text, status text default 'queued',
  requested_by text, requested_at timestamptz, claimed_at timestamptz, result jsonb);
```

### Backend `seo.py` router

| Verb + path | Auth | Purpose |
|---|---|---|
| `GET /projects/{slug}/seo/overview` | owner/admin | scores, status, last run (drives the dashboard Overview) |
| `GET /projects/{slug}/seo/plan` | owner/admin | `seo_plan_items` + schedule |
| `GET /projects/{slug}/seo/history` | owner/admin | runs + `seo_changes` (before/after + verified proof) |
| `GET/PUT/DELETE /projects/{slug}/seo/meta` | owner/admin | human CRUD of `seo_page_meta` |
| `GET/POST/PUT/DELETE /projects/{slug}/seo/articles[/{id}]` | owner/admin | human CRUD of `seo_articles` |
| `POST /projects/{slug}/seo/jobs` | owner/admin | enqueue a run/article-campaign job (the dashboard button) |
| `POST /admin/projects/{slug}/seo/*` | admin bearer | agent writes audits/plan/changes/meta/articles (RLS-safe) |
| `GET /projects/{slug}/seo/public/meta?route=&locale=` | public + ETag/ISR | **site consumer**: per-route SEO meta + JSON-LD |
| `GET /projects/{slug}/seo/public/articles?locale=` (+ `/{articleSlug}`) | public + ETag/ISR | **site consumer**: published articles for `/blog` |

**Route-collision safety:** all SEO routes are namespaced under `/projects/{slug}/seo/...` — they never touch the `content.py` `/{slug}/{locale}` catch-all that would swallow a literal `/seo` segment. No new route is added under `/content/...`.

---

## Dashboard "SEO & GEO" section

Add `"seo"` to `SectionKey` + a `PROJECT_SECTIONS` row (icon from lucide), shown when `seo_enabled` (not a paywall — just "has the agent run / is this turned on"). `SeoSection.tsx` clones `BookingsSection` (inner no-scrollbar tab strip, motion `layoutId` underline, `useQuery` hooks). Tabs:

- **Overview** — SEO / GEO / Local score dials, status, last-run, "Run now" + "Run article campaign" buttons (enqueue `seo_jobs`).
- **Plan** — prioritized items, each with plain-language "what & why", effort/impact, `action_kind` badge, **the schedule and the logic, made explicit** (the operator-readable reasoning).
- **History** — per run: what was done, before/after diffs, and the visual-QA proof (screenshots/pass-fail).
- **Articles** — generated articles; read/edit/delete (writes through the seo router).
- **Competitors** — the reasoned competitor + local analysis.
- **Settings** — toggle `seo_enabled`, blog route, locale scope.

All readable + editable by **client and admin** (the agent writes the same rows autonomously).

---

## Cross-agent coordination — the `site-change-spec` contract

The SEO agent sits **above** Website Builder + Connector and triggers them through one JSON contract (the single interface; no ad-hoc repo edits):

```jsonc
// site-change-spec.json (SEO agent emits; Builder + Connector consume)
{
  "project_slug": "...", "repo": "...", "branch": "cms-preview", "run_id": "...",
  "pages":    [{ "route": "/blog", "page_type": "blog_index", "nav": {"add": true, "label_i18n": "nav.blog"},
                 "consumes": "seo_articles", "schema_type": "Blog", "locales": ["en","nl"] }],
  "sections": [{ "target_route": "/", "component": "LocalAreasServed", "schema_type": "LocalBusiness" }],
  "cms_wiring": [{ "consumes": "seo_page_meta", "via": "GET /projects/{slug}/seo/public/meta" }],
  "reason": "..."  // human-readable
}
```

**Changes to each agent:**

- **`seo-pro` skill** — stays the build-time technical floor; **de-mythed**: remove the stale "FAQPage great for SERP enhancements" framing (line 189), add the FORBIDDEN-CLAIMS note (no FAQ-3.2x / answer-first-67% / etc.), and add a line that `generateMetadata` should read `seo_page_meta` when present.
- **Website Builder** — new **incremental "add pages/sections" mode** (today it only builds from scratch): consume `pages`/`sections` from the spec, build them with full SEO + responsive + Playwright self-test on the existing site, push to `cms-preview`. AGENTS.md + a new phase doc; it now knows the SEO CMS area exists (generateMetadata reads `seo_page_meta`; `/blog` reads `seo_articles`).
- **CMS Connector** — Phase 4 **provisions + wires the SEO area** for every site (generated sites fetch `seo/public/meta` in `generateMetadata` and `seo/public/articles` for `/blog`); a **hard rule + LEARNINGS line**: `seo_*` tables are the SEO agent's area — never treat them as normal content services, never clobber them; consume the `cms_wiring` block.
- **Design Prompt Creator** — unaffected (the SEO agent reuses its category-research *pattern* but keeps its own Supabase-backed intel, not the markdown cache).

**Best moment to run (pipeline position):** **4th stage, right after the CMS Connector finishes** — only then is there a live, CMS-wired site with content to audit and write into. Two things shift earlier so sites are *born* SEO-ready: the Builder's `seo-pro` floor at build time, and the Connector provisioning the SEO area at integration. After that the SEO agent is **re-runnable anytime** (after content changes, monthly, on a ranking drop). Pipeline: **Design Prompt → Website Builder → CMS Connector → SEO/GEO Optimizer.**

---

## Guidelines KB + scored rubric (condensed; full text in `guidelines/` + `rubric/`)

Three durable tracks (reference knowledge, not per-client memory). Every rule carries `[confidence | source]`.

- **Track G — Google technical + on-page:** SSR HTML (AI/Google bots don't run JS); one H1 + clean hierarchy; short one-idea paragraphs; title 50–60 / desc 140–160 unique per page+locale; canonical + hreflang; valid JSON-LD (a Google rich-result + structured signal, **not** an AI-citation multiplier); CWV LCP<2.5s/INP<200ms/CLS<0.1 (measured on a cadence, not every iteration — no headless-browser/PSI per-iteration).
- **Track E — GEO:** the only evidence-backed levers are **real source citations, direct quotations, and statistics** (~30–40% relative lift; KDD 2024 arXiv:2311.09735); keyword-stuffing gives ~0 lift. Optimize **intrinsic content quality**, not fixed tricks. The "~40%" is best-case relative on a synthetic metric — **never** stated as a guarantee.
- **Track L — Local:** site-internal NAP consistency (auto); review velocity/recency as advice (hedged, never a multiplier); true geo-grid Share-of-Local-Voice needs a paid Places/SERP API — flagged optional, not faked.

**GATE-FACT (factual-accuracy veto):** every injected stat/quote/citation must name a source + URL, be WebFetched, and have its **verbatim claim sentence found as a literal substring** in the fetched page. Miss ⇒ the edit is dropped and the iteration fails (not averaged away). Per-locale (Dutch claim ⇒ Dutch source). This defeats the SAGEO fabrication failure mode — an LLM judging an LLM is insufficient.

**FORBIDDEN CLAIMS — embedded verbatim in `prompts.py` + every phase doc; the agent must never assert these or score on them (all failed adversarial verification):** FAQPage 3.2× AI Overviews · answer-first 67% more citations · 92.36% AIO citations from top-10 organic · llms.txt as a real signal · GBP 32% local-pack weight (+19/16/7 splits) · 100% GBP completeness 7× clicks · 50+ reviews 4.4× · NAP inconsistency 74% AI exclusion · all-10-GBP-categories matters · AI agencies inherently price higher · short/long-term vector-store memory split.

**Competitor/local intel — automatable vs paid vs human (set client expectations honestly):**
- **Automatable (free, every run):** competitor discovery + server-rendered HTML/JSON-LD extraction + content-gap reasoning; site-internal NAP; GEO-citation *proxy* (LLM-judge "would an engine cite this, and is every stat verifiable?").
- **Paid-API upsell (optional, future):** true geo-grid SoLV, review velocity, rank/AI-Overview tracking (Google Places/SERP).
- **Human (flagged, never faked):** backlinks/off-page, E-E-A-T/author authority, actual Google Business Profile edits + review acquisition.

---

## Localization policy (per-locale vs invariant vs English)

> Agent-facing copy: [`agents/SEO-GEO Optimizer/guidelines/localization.md`](../../../agents/SEO-GEO%20Optimizer/guidelines/localization.md). The research-verified decision matrix; this section is the design-spec mirror.

Every SEO/GEO output falls into exactly one of three buckets:

- **PROSE → per-locale via DeepL.** meta `title`/`description`, OG `title`/`description`, JSON-LD text (`name`/`description`/`headline`), and the visible article/blog/news body. The agent writes these in the project's **DEFAULT locale** (Phase 5); the CMS pipeline translates them per-locale via `POST /projects/{slug}/seo/translate` (kind `meta` then `article`), reusing the existing `backend/auth_service/translation/` provider (DeepL/null). The agent **never hand-writes the non-default locales**.
- **CODED FACTS / TAGS → language-invariant.** `canonical`, `robots`, `hreflang`, `og:locale`, JSON-LD `inLanguage` (a per-locale BCP-47 **code** on the WebPage/Article node, **not** on LocalBusiness), JSON-LD **data** (address/phone/geo/openingHours/sameAs/image), `og:image`, `hero_image_url`. Generated per-page or repeated verbatim; **never translated**. The generated site emits these itself per locale.
- **INTERNAL → English-only.** audit scores, plan rationale, competitor analysis, run summary. The audit **RUNS per locale** (reads each live per-locale page; the GEO judge scores as a native reader) but is **REPORTED in English** — operator-facing, never shipped.

**Unifying rule:** Google determines a page's language from its **VISIBLE CONTENT**, not the metadata / `lang` attribute / hreflang. So localizing metadata is a **CONSISTENCY requirement with already-translated content**, not a standalone ranking lever.

**Failure / fallback rule:** on a missing/failed translation, **OMIT the field** — never write `""`/`null` (an explicit empty blocks the fallback). The public read endpoints (`/seo/public/meta`, `/seo/public/articles`) fall back **per field, server-side** to the default-locale text, so a live page is never broken/empty. Per-field/template fallback is **NOT duplicate content**; a **whole untranslated body MUST NOT be published as a separate same-language URL** (exclude that locale from hreflang/index until translated).

**Precise-wording guards (do not overstate):** a mismatched-language title is a **SERP DISPLAY override**, NOT a ranking penalty; raw machine translation is a **QUALITY-based ranking risk**, NOT a manual action / penalty.

**SSR prerequisite (per locale):** gate item **G-1 (content present in raw HTML)** applies to **EVERY locale, not just the default** — AI/Google bots don't run JS, so every locale must server-render its translated content.

**GEO caveat:** **no source ties metadata LANGUAGE to AI-citation.** Per-locale metadata is justified on **Google consistency + CTR only** — never as an AI-citation lever or promise.

---

## Hard constraints

1. **Never publish without an all-green visual-QA gate.** Broken responsiveness, clipped text, broken images, console errors, failing build, dead links, or content missing from raw HTML ⇒ self-heal or halt; never publish.
2. **GATE-FACT** on every injected stat/quote/citation (verbatim source match, per-locale).
3. **Never assert the 11 forbidden claims**; the forbidden block lives in `prompts.py` + every phase doc.
4. **Per-locale** audit, scoring, content, and factual verification.
5. **Sell readiness, not rankings:** plan/dashboard copy never promises "we get you cited" or guarantees positions (real AI-citation ground truth is unobtainable with the toolset).
6. **No mistakes on new pages:** new-page code only flows through the Website Builder (incremental mode) + the gate — the SEO agent never hand-edits client Next.js routing/layout directly.
7. **Client-repo writes mirror the Connector** (cms-preview branch, then promote). The SEO agent **never** auto-commits to the `cms-platform` repo itself without Stefan's say.
8. **`MAX_ITERS=3`**, cost budget, plateau + regression guards — the loop always halts.

---

## Scope boundaries

- **Full power** (audit + content + new pages) on **pipeline-built Next.js sites** where we own the repo + the CMS. For arbitrary external sites we don't control, the agent does **audit + recommendations only** (no code changes).
- **No pricing/billing/paywall** in this build (operator handles separately). `seo_enabled` only toggles visibility/activation, not payment.
- **No autonomous cron/server** in this build — manual from Claude Code; the `seo_jobs` queue + a clean entrypoint make a Hetzner worker a drop-in later.
- **Paid SEO APIs** (Places/SERP) are out of scope now — Local ships as the free single-origin "Lite" proxy with an explicit ceiling note.
- **Backlinks/off-page/E-E-A-T/GBP edits** are human, flagged not automated.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Auto-invoking the Builder + auto-publishing breaks a live client site | The visual-QA + self-heal gate (responsive/visibility/crash/console/build/links/E2E) is mandatory pre-publish; self-heal bounded; halt-and-revert if unrecoverable; new-page-type tripwire note. |
| Goodhart: no real AI-citation ground truth | Product contract is "AI-answer readiness," never "we get you cited"; proxy honestly labeled; real-engine spot-check deferred to a possible Playwright path later. |
| Factual fabrication in GEO edits | GATE-FACT verbatim source-sentence match, per-locale; drop-not-weaken veto. |
| Training-prior leakage of refuted SEO myths | Forbidden-claims block in `prompts.py` + every phase doc + a `seo_learnings` neutralizing line for the seo-pro FAQ framing. |
| Connector clobbering the SEO area on a re-run | Hard rule + LEARNINGS line: `seo_*` tables are off-limits to normal content provisioning; consume `cms_wiring` only. |
| Draft auto-items (SSR/CWV) can't be re-scored before publish | Loop re-scores GEO/content on draft; technical re-measured post-publish; surfaced in the run summary so a small delta isn't read as "did nothing." |
| Per-locale doubles cost; NL judge calibration | Budget accounts for ×locales; judge prompted to score "as a Dutch reader/engine"; NL long-form generation gated on `TRANSLATION_PROVIDER=deepl`, else audit NL + flag the gap. |

---

## Success criteria

1. `Run SEO agent for <project>` executes phases 0–7 end-to-end on a pipeline-built site (samir / Laurian / it-global-services), writing a complete `seo_runs` + `seo_audits` + `seo_plan_items` set to Supabase.
2. The `2026_06_14_seo_geo.sql` migration applies cleanly via Supabase MCP; all tables + RLS + project columns present; behavior-preserving for projects with no SEO data.
3. The agent writes `seo_page_meta` + at least one `seo_article`, and the generated site consumes both (meta in `generateMetadata`, article on `/blog`) — verified live.
4. The visual-QA gate provably blocks a publish on an injected breakage and self-heals it (a test that introduces overflow/broken image and confirms no-publish-until-green).
5. GATE-FACT provably drops an unverifiable injected statistic (test with a fabricated source).
6. The dashboard "SEO & GEO" section renders Overview/Plan/History/Articles/Competitors/Settings; client + admin can read/edit/delete SEO content.
7. A `new_page` plan item triggers the Website Builder (incremental) + Connector via `site-change-spec`, ships a new `/blog` route through the gate, and prints the new-page-type tripwire.
8. `seo-pro`, Website Builder `AGENTS.md`, and Connector `AGENTS.md`/`phases/4-integration.md`/`LEARNINGS.md` are updated for SEO-area awareness; a catalog row exists in `agents/README.md`.
9. No phase doc or prompt asserts any of the 11 forbidden claims (grep clean).
10. All new Python helpers have passing pytest; backend tests green; frontend builds.

---

## Open items intentionally deferred (not in this build)

- Hetzner worker + autonomous cron (entrypoint + `seo_jobs` queue make it a drop-in).
- Paid Places/SERP API integration (true geo-grid, review velocity, rank tracking).
- Real per-engine AI-citation measurement (evaluate a Playwright real-browser path later).
- Pricing / billing / Stripe (operator-owned).
