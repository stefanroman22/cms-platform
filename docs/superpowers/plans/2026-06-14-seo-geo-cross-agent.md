# SEO/GEO Cross-Agent Orchestration — Implementation Plan (Plan 4 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

> **Commit policy (Stefan's rule):** Do NOT `git commit`. "Commit" steps are checkpoints.

**Goal:** Close the loop so the SEO/GEO Optimizer can (a) make new SEO data actually reach the live client site, and (b) create new pages/sections by auto-invoking the Website Builder + CMS Connector through one contract. Deliver: the `site-change-spec` contract (a tested Python builder/validator), the SEO agent's phase 7 (learn + new-page handling + tripwire), and the cross-agent doc changes — Website Builder gains an "incremental add-pages" mode, the CMS Connector becomes SEO-area-aware (its generated-site contract makes `generateMetadata` consume `/seo/public/meta` and a `/blog` route consume `/seo/public/articles`), and `seo-pro` is de-mythed.

**Scope boundary (explicit):** This plan makes the cross-agent CONTRACTS real and adds them to the production agents' specs, so every FUTURE connector run produces SEO-area-consuming sites. **Retrofitting the EXISTING fleet's repos** (samir / Laurian / it-global-services) to consume `/seo/public/meta` + `/seo/public/articles` is a separate per-site operation (a connector re-run or manual wiring) and is documented as a follow-up — NOT a live-repo edit in this plan.

**Architecture:** One stdlib, unit-tested Python module (`site_change_spec.py`) builds + validates the contract the SEO agent emits for `new_page`/`section` plan items; the Website Builder (incremental mode) and CMS Connector consume it. The consumption wiring is a documented generated-site contract (fetch the public SEO endpoints with ISR + fallback), mirroring the existing `lib/cms-content.ts` pattern. Source of truth: `docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md` (the "Cross-agent coordination" section).

**Tech Stack:** Python 3.13 stdlib + pytest; Markdown agent specs/phases; the existing Next.js generated-site fetch pattern.

---

## File structure

```
agents/SEO-GEO Optimizer/
  site_change_spec.py             # CREATE — build + validate the site-change-spec contract (tested)
  tests/test_site_change_spec.py  # CREATE
  phases/7-learn.md               # CREATE — learn + persist + new_page orchestration + tripwire
  AGENTS.md                       # MODIFY — phase 7 built; new_page flow; pipeline complete
.claude/skills/seo-geo-optimizer/SKILL.md     # MODIFY — lazy table adds phase 7
.claude/skills/seo-pro/SKILL.md               # MODIFY — de-myth (drop FAQ-SERP claim) + read seo_page_meta + forbidden note
agents/Website Builder/
  AGENTS.md                       # MODIFY — incremental "add pages/sections" mode + SEO-area awareness
  phases/9-incremental.md         # CREATE — the incremental-build phase (consume a site-change-spec)
agents/CMS Connector - Website/
  AGENTS.md                       # MODIFY — SEO-area hard rule + generated-site SEO consumption contract
  LEARNINGS.md                    # MODIFY — append the SEO-area rules
  phases/4-integration.md         # MODIFY — add the SEO-area provisioning/wiring sub-step
docs/superpowers/specs/2026-06-14-seo-geo-EXISTING-FLEET-RETROFIT.md   # CREATE — follow-up runbook
```

Tests: `python -m pytest "agents/SEO-GEO Optimizer/tests/" -v`.

---

## Task 1: `site_change_spec.py` — the contract builder/validator

**Files:** Create `agents/SEO-GEO Optimizer/site_change_spec.py`; Test `agents/SEO-GEO Optimizer/tests/test_site_change_spec.py`

- [ ] **Step 1: Write the failing test**

```python
# agents/SEO-GEO Optimizer/tests/test_site_change_spec.py
import importlib.util, pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "site_change_spec.py"
_spec = importlib.util.spec_from_file_location("seo_scs", _p)
scs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scs)


def test_build_minimal_blog_spec():
    s = scs.build_site_change_spec(
        project_slug="acme", repo="https://github.com/x/acme", run_id="r1",
        pages=[{"route": "/blog", "page_type": "blog_index", "consumes": "seo_articles",
                "nav": {"add": True, "label_i18n": "nav.blog"}, "locales": ["en", "nl"]}],
        reason="GEO articles need a /blog index",
    )
    assert s["project_slug"] == "acme" and s["branch"] == "cms-preview"
    assert s["pages"][0]["route"] == "/blog" and s["run_id"] == "r1"
    ok, errs = scs.validate_site_change_spec(s)
    assert ok and errs == []


def test_validate_rejects_bad_page_type():
    s = scs.build_site_change_spec(
        project_slug="acme", repo="r", run_id="r1",
        pages=[{"route": "/x", "page_type": "not_a_type", "locales": ["en"]}],
        reason="x",
    )
    ok, errs = scs.validate_site_change_spec(s)
    assert ok is False
    assert any("page_type" in e for e in errs)


def test_validate_requires_route_and_reason():
    s = scs.build_site_change_spec(project_slug="acme", repo="r", run_id="r1",
                                   pages=[{"page_type": "service", "locales": ["en"]}], reason="")
    ok, errs = scs.validate_site_change_spec(s)
    assert ok is False
    assert any("route" in e for e in errs) and any("reason" in e for e in errs)


def test_cms_wiring_defaults_and_passthrough():
    s = scs.build_site_change_spec(
        project_slug="acme", repo="r", run_id="r1",
        pages=[{"route": "/blog", "page_type": "blog_index", "locales": ["en"]}],
        cms_wiring=[{"consumes": "seo_articles", "via": "GET /projects/acme/seo/public/articles"}],
        reason="x",
    )
    assert s["cms_wiring"][0]["consumes"] == "seo_articles"
    ok, _ = scs.validate_site_change_spec(s)
    assert ok
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Write `site_change_spec.py`**

```python
# agents/SEO-GEO Optimizer/site_change_spec.py
"""The site-change-spec contract: the JSON the SEO/GEO agent emits for new_page / section
plan items, which the Website Builder (incremental mode) and CMS Connector consume. PURE.

One interface, no ad-hoc repo edits. The agent NEVER hand-edits client Next.js routing —
new-page CODE only flows through the Builder (then the visual-QA gate before publish).
"""
from __future__ import annotations

PAGE_TYPES = {"blog_index", "blog_post", "local_landing", "service", "section"}
CONSUMES = {"seo_articles", "seo_page_meta", "static", None}
DEFAULT_BRANCH = "cms-preview"


def build_site_change_spec(*, project_slug: str, repo: str, run_id: str,
                           pages=None, sections=None, cms_wiring=None, reason: str = "",
                           branch: str = DEFAULT_BRANCH) -> dict:
    return {
        "project_slug": project_slug,
        "repo": repo,
        "branch": branch,
        "run_id": run_id,
        "pages": list(pages or []),
        "sections": list(sections or []),
        "cms_wiring": list(cms_wiring or []),
        "reason": reason,
    }


def validate_site_change_spec(spec: dict) -> tuple[bool, list[str]]:
    errs: list[str] = []
    for key in ("project_slug", "repo", "run_id"):
        if not spec.get(key):
            errs.append(f"missing required field: {key}")
    if not spec.get("reason"):
        errs.append("missing required field: reason")
    if spec.get("branch") and spec["branch"] != DEFAULT_BRANCH:
        errs.append(f"branch must be {DEFAULT_BRANCH!r} (code changes go via the preview branch)")
    pages = spec.get("pages") or []
    sections = spec.get("sections") or []
    if not pages and not sections:
        errs.append("spec has neither pages nor sections — nothing to build")
    for i, p in enumerate(pages):
        if not p.get("route"):
            errs.append(f"pages[{i}]: missing route")
        if p.get("page_type") not in PAGE_TYPES:
            errs.append(f"pages[{i}]: invalid page_type {p.get('page_type')!r} (allowed: {sorted(PAGE_TYPES)})")
        if "consumes" in p and p.get("consumes") not in CONSUMES:
            errs.append(f"pages[{i}]: invalid consumes {p.get('consumes')!r}")
        if not p.get("locales"):
            errs.append(f"pages[{i}]: missing locales")
    for i, w in enumerate(spec.get("cms_wiring") or []):
        if w.get("consumes") not in CONSUMES:
            errs.append(f"cms_wiring[{i}]: invalid consumes {w.get('consumes')!r}")
    return (not errs), errs
```

- [ ] **Step 4: Run to verify it passes** → 4 passed.
- [ ] **Step 5: Full agent suite green** — `python -m pytest "agents/SEO-GEO Optimizer/tests/" -v` → 23 + 4 = 27 pass.
- [ ] **Step 6: Commit (checkpoint)** — stage only.

---

## Task 2: SEO agent phase 7 + AGENTS/SKILL wiring

**Files:** Create `agents/SEO-GEO Optimizer/phases/7-learn.md`; Modify `agents/SEO-GEO Optimizer/AGENTS.md`, `.claude/skills/seo-geo-optimizer/SKILL.md`

- [ ] **Step 1: `7-learn.md`** (house phase structure). Steps:
  - **new_page orchestration:** for each `seo_plan_items` row with `action_kind == new_page`, build a `site-change-spec` via `site_change_spec.build_site_change_spec` (+ `validate_site_change_spec` — halt the item if invalid); then AUTO-INVOKE the Website Builder (incremental mode) with the spec, then the CMS Connector to provision/wire any new CMS consumption; then run the **seo-visual-qa gate** (phase 6) over the new routes; publish only when green; record `seo_changes`. **New-page-type tripwire:** the first time a brand-new page type ships, print "new page type X went live — glance recommended."
  - **Learn:** distill generalizable cross-client intelligence into the `seo_learnings` Supabase table (global); append agent-mechanics-only lessons to `LEARNINGS.md`. Consume any `feedback/pending/*` notes (clone the Design Prompt Creator loop).
  - **Persist + summary:** ensure the `seo_runs` row is `completed` with final `scores`/`summary`; echo the dashboard path. End with the FORBIDDEN_CLAIMS block.
- [ ] **Step 2:** `AGENTS.md` — mark phase 7 **built (Plan 4)**; the pipeline table is now complete (0–7); document the new_page flow (spec → Builder incremental → Connector → gate → publish → tripwire); add `site_change_spec.py` to Tools; add a "Cross-agent contract" section pointing at `site_change_spec.py` + the Builder/Connector specs.
- [ ] **Step 3:** `SKILL.md` — lazy-phase table adds `phases/7-learn.md`; update the "phases not yet built" note (now all 0–7 exist).
- [ ] **Step 4: Verify** cross-refs (`python -c`: phase 7 exists + referenced in AGENTS.md + SKILL.md; references `site_change_spec` + the gate + tripwire + forbidden block).
- [ ] **Step 5: Commit (checkpoint).**

---

## Task 3: De-myth the `seo-pro` skill

**Files:** Modify `.claude/skills/seo-pro/SKILL.md`

- [ ] **Step 1: Read** `.claude/skills/seo-pro/SKILL.md` and locate the FAQ line (`FAQPage` ... "great for SERP enhancements", ~line 189).
- [ ] **Step 2: Edit** that table cell to remove the unverified SERP-boost framing — change the FAQ note to: "FAQPage — use ONLY where the content is genuinely Q&A. (Google restricted FAQ rich results to authoritative/gov/health sites in 2023; do NOT promise a SERP or AI-Overview boost.)" Keep the row; just de-hype it.
- [ ] **Step 3: Add** a short "GEO note" block near the JSON-LD section: "Treat schema as a Google rich-result + structured signal, NOT an AI-citation multiplier (LLMs tokenize JSON-LD as text). When the CMS has stored SEO for a route (`GET /projects/{slug}/seo/public/meta?route=&locale=`), `generateMetadata` should prefer it (with a static fallback). The SEO/GEO Optimizer agent owns that stored SEO." Add a one-line forbidden-claims pointer: "Never assert the 11 research-refuted SEO/GEO claims (see `agents/SEO-GEO Optimizer/prompts.py` FORBIDDEN_CLAIMS): no FAQ-3.2x, answer-first-67%, llms.txt-as-signal, GBP-32%, NAP-74%, review-click-multipliers, etc."
- [ ] **Step 4: Verify** the old "great for SERP enhancements" phrasing is gone (`grep` returns 0) and the de-myth + GEO note + forbidden pointer are present.
- [ ] **Step 5: Commit (checkpoint).**

---

## Task 4: Website Builder — incremental "add pages/sections" mode

**Files:** Modify `agents/Website Builder/AGENTS.md`; Create `agents/Website Builder/phases/9-incremental.md`

- [ ] **Step 1: Read** `agents/Website Builder/AGENTS.md` (the 8-phase spec + constants).
- [ ] **Step 2: `phases/9-incremental.md`** — a NEW mode (not part of the from-scratch 8-phase build). Goal: given a validated `site-change-spec` (from the SEO agent), ADD the specified routes/sections to an EXISTING generated site without a full rebuild. Steps: read the spec; for each `page`, create `app/[locale]/<route>/page.tsx` with full `seo-pro` metadata + responsive + Motion + the section components; if `consumes: seo_articles`, the page fetches `GET /projects/{slug}/seo/public/articles` (ISR + fallback) and renders the list/post; if `consumes: seo_page_meta`, `generateMetadata` reads `/seo/public/meta`; add the nav entry + i18n keys for every locale; run the per-locale Playwright smoke; push to `cms-preview`. Hand back to the SEO agent's phase-6 gate for verification before publish. End: never break the existing site (additive routes only).
- [ ] **Step 3:** `AGENTS.md` — add an "Incremental mode (invoked by the SEO/GEO Optimizer)" section: it accepts a `site-change-spec`, runs `phases/9-incremental.md`, is additive-only, and SEO-area-aware (generated pages consume `/seo/public/meta` + `/seo/public/articles`). Note the standard 8-phase build now also wires `generateMetadata` to prefer stored `seo_page_meta` when present.
- [ ] **Step 4: Verify** `phases/9-incremental.md` exists + is referenced in `AGENTS.md`; references the site-change-spec + the public SEO endpoints + the SEO agent's gate.
- [ ] **Step 5: Commit (checkpoint).**

---

## Task 5: CMS Connector — SEO-area awareness + generated-site consumption contract

**Files:** Modify `agents/CMS Connector - Website/AGENTS.md`, `LEARNINGS.md`, `phases/4-integration.md`

- [ ] **Step 1: Read** the relevant parts of `agents/CMS Connector - Website/AGENTS.md` (the "Generated client website contracts" + Phase 4 sections) and `phases/4-integration.md`.
- [ ] **Step 2: `AGENTS.md`** — under "Generated client website contracts", ADD an "SEO/GEO area" subsection (binding for all generated sites):
  - Generated sites' `generateMetadata` fetches `GET {backend}/projects/{slug}/seo/public/meta?route=<route>&locale=<locale>` and PREFERS the stored title/description/canonical/og/json_ld when present, falling back to the build-time `seo-pro` output (never throw — fallback on any error; ISR ~60s).
  - When the project has `seo_blog_route` set, the site has a `/blog` index + `/blog/[slug]` that fetch `GET {backend}/projects/{slug}/seo/public/articles?locale=<locale>` (+ `/{articleSlug}`), ISR + fallback.
  - **Hard rule:** the `seo_*` Supabase tables are the SEO/GEO Optimizer agent's area — the Connector NEVER provisions them as normal content services and NEVER clobbers them. It only WIRES the site to consume the public read endpoints.
- [ ] **Step 3: `phases/4-integration.md`** — add a sub-step "4.x SEO-area wiring": set the backend base env the site needs for the SEO endpoints (reuse the existing `{prefix}CMS_ENDPOINT` base / backend base), generate the `lib/seo-meta.ts` fetch helper (mirrors `lib/cms-content.ts`: ISR, never-throw fallback), and wire `generateMetadata` to prefer stored meta. Provisioning the booking/`seo_blog_route` only when the SEO agent has created articles.
- [ ] **Step 4: `LEARNINGS.md`** — append under a new/closest heading:
  - `- <YYYY-MM-DD>: The seo_* tables (seo_page_meta/seo_articles/etc.) are the SEO/GEO Optimizer agent's area. NEVER provision them as content services or clobber them. Generated sites only CONSUME the public read endpoints GET /projects/<slug>/seo/public/{meta,articles} (ISR + never-throw fallback); generateMetadata prefers stored seo_page_meta over build-time seo-pro output. Triggered by: SEO/GEO Optimizer Plan 4 cross-agent contract.`
- [ ] **Step 5: Verify** the SEO-area subsection + hard rule are in `AGENTS.md`, the wiring sub-step is in `phases/4-integration.md`, and the LEARNINGS line is appended (`grep` for `seo/public` + "NEVER provision them").
- [ ] **Step 6: Commit (checkpoint).**

---

## Task 6: Existing-fleet retrofit runbook (follow-up doc)

**Files:** Create `docs/superpowers/specs/2026-06-14-seo-geo-EXISTING-FLEET-RETROFIT.md`

- [ ] **Step 1: Write the runbook** documenting how to retrofit the EXISTING sites (samir-kapsalon, laurian-duma-portfolio, it-global-services) to consume the SEO area, since they were generated before the SEO consumption contract existed. Content: per site — add `lib/seo-meta.ts`, wire `generateMetadata` to prefer `/seo/public/meta`, optionally add `/blog` if articles exist, push to `cms-preview`, run the SEO agent's visual-QA gate, promote. State clearly this is a manual/connector-re-run operation, NOT done by Plan 4, and that until a site is retrofitted, the SEO agent's published `seo_page_meta` lives in the CMS + dashboard but does NOT yet affect that live site.
- [ ] **Step 2: Commit (checkpoint).**

---

## Task 7: Final cross-cutting verification (controller)

**Files:** none.

- [ ] **Step 1:** Full agent Python suite green: `python -m pytest "agents/SEO-GEO Optimizer/tests/" -v` → 27 pass.
- [ ] **Step 2:** Backend + frontend suites unaffected (no code changed in Plan 4 beyond agent docs + the one Python module): `cd backend && python -m pytest auth_service/tests/ -q` (expect prior green) and `cd frontend && npx vitest run src/components/dashboard/seo` (expect green).
- [ ] **Step 3:** Cross-reference sweep — every path referenced in the SEO agent's `SKILL.md`/`AGENTS.md`/phases 0–7 resolves; the Website Builder + Connector AGENTS.md reference the SEO contract; `seo-pro` de-myth applied (grep clean for the old FAQ-SERP phrasing).
- [ ] **Step 4:** Final dispatch a code-reviewer over the whole 4-plan SEO/GEO implementation for a last pass (per subagent-driven-development's "final code reviewer" step). Plan 4 done when Tasks 1–7 pass.

---

## Self-review

**Spec coverage:** the `site-change-spec` contract (built + validated, tested) ✓; SEO agent phase 7 (learn + new_page auto-invoke Builder/Connector + gate + tripwire) ✓; Website Builder incremental mode + SEO-area awareness ✓; Connector SEO-area hard rule + generated-site consumption contract (generateMetadata prefers `/seo/public/meta`; `/blog` from `/seo/public/articles`) ✓; `seo-pro` de-myth ✓; existing-fleet retrofit documented as a follow-up ✓. The full pipeline is now Design Prompt → Website Builder → CMS Connector → SEO/GEO Optimizer, with the agent able to reach the live site (future sites automatically; existing sites via the retrofit runbook).

**Placeholder scan:** Python fully coded + tested; doc tasks are precise edits/sections with exact content + grep verifications; the retrofit is an explicit runbook.

**Type/name consistency:** `site_change_spec.build_site_change_spec`/`validate_site_change_spec` signatures match the phase-7 doc usage; `page_type`/`consumes` enums match the Builder incremental phase + the design spec's contract; the public endpoints `/projects/{slug}/seo/public/{meta,articles}` match the Plan-1 router exactly; `cms-preview` branch matches the Connector's branch convention.

---

## Done

After Plan 4, the SEO/GEO Optimizer is complete: a 4th autonomous pipeline agent that audits + competitively researches + plans + applies (content/meta/schema/articles) + safely publishes behind a visual-QA self-heal gate + creates new pages via the other agents + remembers per client in Supabase + self-improves — surfaced in a client+admin "SEO & GEO" dashboard section, grounded in adversarially-verified guidelines with the 11 refuted claims permanently forbidden.
