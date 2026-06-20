# SEO/GEO Apply + Visual-QA Gate — Implementation Plan (Plan 3 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

> **Commit policy (Stefan's rule):** Do NOT `git commit`. "Commit" steps are checkpoints.

**Goal:** Give the SEO/GEO Optimizer the ability to APPLY its plan and PUBLISH safely. Two phases: **5-apply** (write SEO meta/schema → `seo_page_meta` drafts; write GEO articles → `seo_articles` drafts via factual-gated content writing; record `seo_changes`) and **6-verify-publish** (the **visual-QA + self-heal gate**: render the affected routes with Playwright at mobile/laptop/desktop per locale, assert responsive/visibility/no-crash/no-console-errors/build-ok/links-resolve/content-in-raw-HTML; if broken, self-heal via brainstorming→writing-plans→ui-ux-pro-max→frontend-design; publish ONLY when all-green; else halt+revert). Plus two skills: `geo-content-writing` (verbatim-source factual gate) and `seo-visual-qa` (the gate methodology).

**Architecture:** Deterministic, unit-tested stdlib Python for the gate evaluation (`gate.py`) and apply-payload building + diffs (`apply.py`); the rendering itself is Playwright-MCP-driven by the `seo-visual-qa` skill in the main thread, which feeds raw check results into `gate.evaluate_gate`. Content writing is LLM-driven by the `geo-content-writing` skill, gated by a verbatim-source substring check. SEO area writes go to `seo_page_meta`/`seo_articles` via Supabase MCP; edits to EXISTING site copy go through the platform's `save_service` draft path; publish flips `status`→`published` (SEO area) and/or calls the existing publish endpoint (site content). Source of truth: `docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md`.

**Tech Stack:** Python 3.13 stdlib + pytest; Playwright MCP; Supabase MCP; Markdown skill/phase docs.

---

## File structure

```
agents/SEO-GEO Optimizer/
  gate.py                         # CREATE — evaluate Playwright/build/link check results → pass/fail report (tested)
  apply.py                        # CREATE — build seo_page_meta / seo_article payloads + before/after diff (tested)
  tests/test_gate.py              # CREATE
  tests/test_apply.py             # CREATE
  phases/5-apply.md               # CREATE
  phases/6-verify-publish.md      # CREATE
  AGENTS.md                       # MODIFY — pipeline table: phases 5,6 now built; lazy table; gate constants
.claude/skills/
  seo-visual-qa/SKILL.md          # CREATE — the Playwright breakpoint gate + self-heal loop methodology
  geo-content-writing/SKILL.md    # CREATE — citation/quote/statistic writing with verbatim-source GATE-FACT
.claude/skills/seo-geo-optimizer/SKILL.md   # MODIFY — lazy phase table adds 5,6
```

Tests: `python -m pytest "agents/SEO-GEO Optimizer/tests/" -v` (stdlib-only).

---

## Task 1: `gate.py` — visual-QA gate evaluation

**Files:** Create `agents/SEO-GEO Optimizer/gate.py`; Test `agents/SEO-GEO Optimizer/tests/test_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# agents/SEO-GEO Optimizer/tests/test_gate.py
import importlib.util, pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "gate.py"
_spec = importlib.util.spec_from_file_location("seo_gate", _p)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _clean_viewport(w):
    return {"width": w, "overflow": False, "text_clipped": False, "broken_images": 0, "tap_targets_ok": True}


def test_all_green_passes():
    checks = {
        "viewports": [_clean_viewport(375), _clean_viewport(768), _clean_viewport(1440)],
        "console_errors": [], "build_ok": True, "broken_links": [], "smoke_ok": True,
        "content_in_raw_html": True,
    }
    r = gate.evaluate_gate(checks)
    assert r["passed"] is True
    assert r["failures"] == []


def test_overflow_fails_and_names_viewport():
    vp = [_clean_viewport(375), _clean_viewport(768), _clean_viewport(1440)]
    vp[0]["overflow"] = True
    checks = {"viewports": vp, "console_errors": [], "build_ok": True,
              "broken_links": [], "smoke_ok": True, "content_in_raw_html": True}
    r = gate.evaluate_gate(checks)
    assert r["passed"] is False
    assert any("375" in f and "overflow" in f.lower() for f in r["failures"])


def test_console_errors_and_broken_build_fail():
    checks = {"viewports": [_clean_viewport(375)], "console_errors": ["TypeError x"],
              "build_ok": False, "broken_links": ["/gone"], "smoke_ok": False,
              "content_in_raw_html": False}
    r = gate.evaluate_gate(checks)
    assert r["passed"] is False
    kinds = " ".join(r["failures"]).lower()
    for must in ["console", "build", "link", "smoke", "raw server html"]:
        assert must in kinds


def test_missing_viewports_is_a_failure_not_a_pass():
    # never green-light on an empty/partial render set
    r = gate.evaluate_gate({"viewports": [], "console_errors": [], "build_ok": True,
                            "broken_links": [], "smoke_ok": True, "content_in_raw_html": True})
    assert r["passed"] is False
    assert any("viewport" in f.lower() for f in r["failures"])
```

- [ ] **Step 2: Run to verify it fails** — `python -m pytest "agents/SEO-GEO Optimizer/tests/test_gate.py" -v` → module not found.

- [ ] **Step 3: Write `gate.py`**

```python
# agents/SEO-GEO Optimizer/gate.py
"""Evaluate the visual-QA gate results. PURE: the seo-visual-qa skill drives Playwright
(render each route at each viewport per locale) + the build/link/smoke checks, then passes
the raw results here. Nothing publishes unless evaluate_gate(...)['passed'] is True.

Fail-closed: an empty/partial render set is a FAILURE, never a silent pass.
"""
from __future__ import annotations

REQUIRED_VIEWPORTS = (375, 768, 1440)  # mobile / tablet / desktop


def evaluate_gate(checks: dict) -> dict:
    failures: list[str] = []

    viewports = checks.get("viewports") or []
    seen = {v.get("width") for v in viewports}
    if not viewports:
        failures.append("No viewports rendered — cannot verify (fail-closed).")
    for w in REQUIRED_VIEWPORTS:
        if w not in seen:
            failures.append(f"Viewport {w}px not rendered.")
    for v in viewports:
        w = v.get("width", "?")
        if v.get("overflow"):
            failures.append(f"Horizontal overflow at {w}px.")
        if v.get("text_clipped"):
            failures.append(f"Text clipped/overlapping at {w}px.")
        if v.get("broken_images"):
            failures.append(f"{v['broken_images']} broken/zero-size image(s) at {w}px.")
        if v.get("tap_targets_ok") is False:
            failures.append(f"Tap targets below 44px at {w}px.")

    if checks.get("console_errors"):
        failures.append(f"{len(checks['console_errors'])} console error(s): {checks['console_errors'][:3]}")
    if not checks.get("build_ok", False):
        failures.append("Build failed (next build did not exit 0).")
    if checks.get("broken_links"):
        failures.append(f"Broken internal link(s): {checks['broken_links'][:5]}")
    if not checks.get("smoke_ok", False):
        failures.append("playwright-user-stories smoke failed.")
    if not checks.get("content_in_raw_html", False):
        failures.append("Edited content NOT present in raw server HTML (invisible to AI/Google bots).")

    return {"passed": not failures, "failures": failures, "checked_viewports": sorted(seen - {None})}
```

- [ ] **Step 4: Run to verify it passes** — `python -m pytest "agents/SEO-GEO Optimizer/tests/test_gate.py" -v` → 4 passed.
- [ ] **Step 5: Commit (checkpoint)** — stage only.

---

## Task 2: `apply.py` — payload building + diff

**Files:** Create `agents/SEO-GEO Optimizer/apply.py`; Test `agents/SEO-GEO Optimizer/tests/test_apply.py`

- [ ] **Step 1: Write the failing test**

```python
# agents/SEO-GEO Optimizer/tests/test_apply.py
import importlib.util, pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "apply.py"
_spec = importlib.util.spec_from_file_location("seo_apply", _p)
apply = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apply)


def test_page_meta_payload_defaults_to_draft():
    p = apply.build_page_meta_payload("pid", "/", "en", {"title": "Home", "description": "d"})
    assert p["project_id"] == "pid" and p["route"] == "/" and p["locale"] == "en"
    assert p["title"] == "Home" and p["status"] == "draft" and p["updated_by"] == "agent"


def test_article_payload_carries_run_and_draft():
    p = apply.build_article_payload("pid", "run1", "guide-fades", "nl",
                                    {"title": "Gids", "body": "x", "excerpt": "e"})
    assert p["slug"] == "guide-fades" and p["locale"] == "nl"
    assert p["status"] == "draft" and p["source_run_id"] == "run1" and p["updated_by"] == "agent"


def test_diff_before_after_lists_changed_fields_only():
    d = apply.diff_before_after({"title": "Old", "description": "same"},
                                {"title": "New", "description": "same"})
    assert d == {"title": {"before": "Old", "after": "New"}}


def test_diff_handles_added_field():
    d = apply.diff_before_after({}, {"title": "New"})
    assert d == {"title": {"before": None, "after": "New"}}
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Write `apply.py`**

```python
# agents/SEO-GEO Optimizer/apply.py
"""Build the Supabase payloads the apply phase writes (seo_page_meta / seo_articles),
and compute before/after diffs for the seo_changes audit trail. PURE / stdlib only.
Everything is written as DRAFT (status='draft'); publishing happens only after the
visual-QA gate is green (phase 6). updated_by defaults to 'agent'.
"""
from __future__ import annotations


def build_page_meta_payload(project_id: str, route: str, locale: str, fields: dict) -> dict:
    allowed = ("title", "description", "canonical", "og", "json_ld", "robots")
    out = {"project_id": project_id, "route": route, "locale": locale,
           "status": "draft", "updated_by": "agent"}
    for k in allowed:
        if k in fields:
            out[k] = fields[k]
    return out


def build_article_payload(project_id: str, run_id: str, slug: str, locale: str, fields: dict) -> dict:
    allowed = ("title", "excerpt", "body", "json_ld", "hero_image_url")
    out = {"project_id": project_id, "source_run_id": run_id, "slug": slug, "locale": locale,
           "status": "draft", "updated_by": "agent"}
    for k in allowed:
        if k in fields:
            out[k] = fields[k]
    return out


def diff_before_after(before: dict, after: dict) -> dict:
    """Only changed/added fields. Used for the seo_changes.before/after record."""
    diff: dict[str, dict] = {}
    for k in set(before) | set(after):
        b = before.get(k)
        a = after.get(k)
        if b != a:
            diff[k] = {"before": b, "after": a}
    return diff
```

- [ ] **Step 4: Run to verify it passes** → 4 passed.
- [ ] **Step 5: Full Python suite green** — `python -m pytest "agents/SEO-GEO Optimizer/tests/" -v` → 15 (Plan 2) + 4 + 4 = 23 pass.
- [ ] **Step 6: Commit (checkpoint)** — stage only.

---

## Task 3: `seo-visual-qa` skill

**Files:** Create `.claude/skills/seo-visual-qa/SKILL.md`

- [ ] **Step 1: Write the skill** (frontmatter `name: seo-visual-qa`, `description:` triggering on "verify before publish / visual QA / responsive check for the SEO agent"). Content — the gate methodology (from design spec "The visual-QA + self-heal gate"):
  - **Inputs:** a list of affected routes + the project's cms-preview URL (drafts) and/or Vercel preview URL (code), the locales.
  - **Render:** for each route × locale × viewport in {375, 768, 1440}, use Playwright MCP: `browser_navigate`, `browser_resize`, `browser_snapshot`/`browser_take_screenshot`, `browser_console_messages`, and `browser_evaluate` to measure `document.documentElement.scrollWidth > clientWidth` (overflow), image `naturalWidth>0` (broken images), visible text not clipped/zero-height, tap-target sizes on mobile.
  - **Build/link/smoke:** `next build` exit 0 (code changes); internal links resolve (no 404); the existing `playwright-user-stories` smoke still passes; `render_check.fetch_raw` confirms edited content is in raw HTML.
  - **Evaluate:** assemble the raw results into the dict shape `gate.evaluate_gate` expects (`viewports`, `console_errors`, `build_ok`, `broken_links`, `smoke_ok`, `content_in_raw_html`) and call it. NOTHING publishes unless `passed is True`.
  - **Self-heal loop (on failure):** invoke `brainstorming` → `writing-plans` (a short fix plan) → apply via `ui-ux-pro-max` + `frontend-design` → re-render → re-evaluate. Bounded: ≤3 self-heal cycles. If still red → HALT the run, revert the draft/branch, record a `seo_changes` failure row, surface it. NEVER publish a red state.
  - **Fail-closed:** an empty/partial render set is a failure (per `gate.py`).

- [ ] **Step 2: Verify** frontmatter valid + references Playwright MCP tools + `gate.evaluate_gate`. (`python -c` substring check for `name: seo-visual-qa`, `evaluate_gate`, `375`, `browser_navigate`.)
- [ ] **Step 3: Commit (checkpoint).**

---

## Task 4: `geo-content-writing` skill

**Files:** Create `.claude/skills/geo-content-writing/SKILL.md`

- [ ] **Step 1: Write the skill** (frontmatter `name: geo-content-writing`, `description:` triggering on "write GEO content / AI-citable copy / SEO articles for the agent"). Content (from design spec Track E + GATE-FACT):
  - **Purpose:** write or rewrite copy/articles to be AI-citable using ONLY the evidence-backed levers: real source citations, real direct quotations, real statistics; short one-idea paragraphs; clean headings. Per locale (write Dutch content as a native Dutch writer; a Dutch claim cites a Dutch source).
  - **GATE-FACT (hard):** for EVERY injected statistic/quotation/citation, the writer must (a) name a source + URL, (b) `WebFetch` it, (c) confirm the VERBATIM claim sentence (or numeric value + entity) appears as a literal substring in the fetched page. If the source can't be fetched or the sentence isn't literally present, DROP the claim — do not weaken it, do not keep an unverifiable number. No fabricated stats/quotes, ever.
  - **Output contract:** returns the new title/body/excerpt (+ optional JSON-LD) ready for `apply.build_article_payload` / `apply.build_page_meta_payload`, plus a `claims:[{text, source_url, verified:true}]` ledger (only verified claims survive).
  - **Tone/positioning:** sell "AI-answer readiness," never "we get you cited"; no ranking guarantees. Embed the FORBIDDEN_CLAIMS block (copy from `agents/SEO-GEO Optimizer/prompts.py`).
- [ ] **Step 2: Verify** frontmatter valid + the GATE-FACT + the forbidden block present + "readiness" present + "never ... cited" present.
- [ ] **Step 3: Commit (checkpoint).**

---

## Task 5: Phase docs 5–6

**Files:** Create `agents/SEO-GEO Optimizer/phases/5-apply.md`, `6-verify-publish.md`

- [ ] **Step 1: `5-apply.md`** (house structure: Goal/Inputs/Steps/Outputs/Failure/Self-improvement). Steps:
  - For each `seo_plan_items` row with `action_kind` in {meta, schema}: build a `seo_page_meta` DRAFT payload via `apply.build_page_meta_payload` and upsert via Supabase MCP (`on conflict (project_id,route,locale)`). Record a `seo_changes` row (kind, target, before/after via `apply.diff_before_after`, no `published_at` yet).
  - For each `action_kind == article`: invoke the `geo-content-writing` skill (per locale) → build `seo_articles` DRAFT via `apply.build_article_payload` → insert via MCP; record `seo_changes`.
  - For each `action_kind == content` targeting an EXISTING page: invoke `geo-content-writing` for the new copy; write it to the platform's DRAFT content for that service via the existing `save_service` draft path (the backend content API with the admin bearer) — never directly mutating published content; record `seo_changes`.
  - `action_kind == new_page` items are DEFERRED to Plan 4 (cross-agent) — mark them `status='planned'` and skip in this phase.
  - `action_kind == manual_human` items are surfaced only (no write) — they need a human.
  - Update each applied item `status='applied'`. Output: list of `seo_changes` ids + the set of affected routes/locales for the gate.
- [ ] **Step 2: `6-verify-publish.md`** Steps:
  - Invoke the `seo-visual-qa` skill over the affected routes × locales (drafts on cms-preview; code on the Vercel preview if any). It returns `gate.evaluate_gate(...)`.
  - **If not green:** run the bounded self-heal loop (the skill handles it). If still red after ≤3 cycles → HALT: revert the drafts (delete the draft `seo_page_meta`/`seo_articles` rows or restore prior content draft), set the related `seo_changes.reverted=true`, set the run `status` summary to note the halt, surface the failure. DO NOT publish.
  - **If green:** publish — set `seo_page_meta`/`seo_articles` `status='published'` (MCP); for site-content edits call the existing publish endpoint (`POST /projects/{slug}/publish`); set `seo_changes.published_at=now()`; set the applied `seo_plan_items.status='published'`.
  - Update the `seo_runs` row (already `completed` from the audit, or re-open/append): record what was applied+published in `summary`/`scores`. Echo the dashboard path.
  - **New-page tripwire (Plan 4 hook):** if any newly-published route is a brand-new page type, print the one-line "new page type X went live — glance recommended" note (the page-creation itself is Plan 4).
  - Each phase doc ends with the FORBIDDEN-CLAIMS block (copy from `prompts.py`).
- [ ] **Step 3: Verify** both phase docs reference `gate.evaluate_gate`, `apply.build_*`, the `seo-visual-qa` + `geo-content-writing` skills, the right tables, `POST /projects/{slug}/publish`, and end with the forbidden block. (`python -c` substring checks.)
- [ ] **Step 4: Commit (checkpoint).**

---

## Task 6: Wire phases 5–6 into AGENTS.md + SKILL.md

**Files:** Modify `agents/SEO-GEO Optimizer/AGENTS.md`, `.claude/skills/seo-geo-optimizer/SKILL.md`

- [ ] **Step 1:** In `AGENTS.md` pipeline table, mark phases 5 (apply) and 6 (verify+publish) as **built (Plan 3)** (was "Plan 3"); add the gate constants (viewports 375/768/1440; self-heal ≤3 cycles; fail-closed; GATE-FACT verbatim-source veto active) to the Constants section; add `seo-visual-qa` + `geo-content-writing` skills + Playwright MCP to the Tools list.
- [ ] **Step 2:** In `SKILL.md` lazy-phase-loading table, add rows for `phases/5-apply.md` and `phases/6-verify-publish.md`.
- [ ] **Step 3: Verify** cross-references resolve (`python -c` checks both phase files exist + are referenced in AGENTS.md + SKILL.md).
- [ ] **Step 4: Commit (checkpoint).**

---

## Task 7: Scoped live apply-through-gate test (controller-executed)

**Files:** none (runtime verification). SAFE: writing `seo_page_meta` does NOT change samir's live site yet (the site doesn't consume `/seo/public/meta` until Plan 4), so this test exercises the apply + gate machinery without altering the live site.

- [ ] **Step 1:** Take the samir-kapsalon plan item "Lengthen the homepage title…" + "Expand the meta description…". Build a `seo_page_meta` DRAFT for route `/`, locales `nl` + `en`, with an improved title (≤60 chars) + a 140–160-char description, via `apply.build_page_meta_payload`; upsert via Supabase MCP. Record `seo_changes` rows.
- [ ] **Step 2:** Run the `seo-visual-qa` gate against samir's PRODUCTION URL (`/nl` + `/en`) at 375/768/1440 via Playwright MCP (render, console, overflow, images, `render_check.fetch_raw` content-in-raw-HTML). Assemble results → `gate.evaluate_gate`. Expected: **green** (samir's current site is healthy) — this validates the gate runs end-to-end. (The self-heal path is exercised in real breakage, not here.)
- [ ] **Step 3:** On green, publish the `seo_page_meta` (status→published) + set `seo_changes.published_at`. Verify via MCP: 2 published `seo_page_meta` rows for samir; the dashboard SEO → (future Meta tab) / History shows the change.
- [ ] **Step 4:** Confirm no forbidden claims in any written meta (literal substring check, per the LEARNINGS note — NOT LIKE-wildcard).
- [ ] **Step 5:** Record any agent-mechanics learning. Plan 3 done when Tasks 1–7 pass.

---

## Self-review

**Spec coverage:** apply phase writes SEO meta/articles drafts + GEO content edits ✓; the visual-QA gate (render 375/768/1440 per locale, overflow/visibility/crash/console/build/links/smoke/raw-HTML, self-heal, publish-only-when-green, fail-closed) ✓ (`gate.py` + `seo-visual-qa`); GATE-FACT verbatim-source factual guard in content writing ✓ (`geo-content-writing`); never-auto-publish-broken + halt+revert ✓; new-page tripwire hook ✓; new pages deferred to Plan 4 ✓.

**Placeholder scan:** Python fully coded + tested; skill/phase docs are content with precise required sections + sources; live test is controller-run with explicit steps.

**Type/name consistency:** `gate.evaluate_gate` input keys (`viewports`,`console_errors`,`build_ok`,`broken_links`,`smoke_ok`,`content_in_raw_html`) match the `seo-visual-qa` skill's output contract and the phase-6 doc. `apply.build_page_meta_payload`/`build_article_payload` field sets match the Plan-1 `seo_page_meta`/`seo_articles` columns + `apply.diff_before_after` feeds `seo_changes.before/after`. `status='draft'`→`'published'` matches the Plan-1 CHECK. Forbidden block sourced from `prompts.py` (consistent with Plan 2).

---

## Next plan

**Plan 4 — Cross-agent new-page orchestration:** the `site-change-spec` contract; Website Builder incremental "add pages/sections" mode; CMS Connector SEO-area provisioning + wiring generated sites to consume `/seo/public/meta` + `/seo/public/articles` (so published meta/articles actually reach the live site); phase 7 (learn + new-page tripwire); `seo-pro` de-myth. Written after Plan 3 is built + green.
