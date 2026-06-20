# SEO/GEO Localization — Implementation Plan (Plan 5)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

> **Commit policy (Stefan's rule):** Do NOT `git commit`. "Commit" steps are checkpoints.

**Goal:** Make the SEO/GEO Optimizer's output multilingual, *correctly*, per the research-verified policy: human-readable PROSE (meta title/description, OG title/description, visible article/blog body) is written in the website's **default locale** and translated per-locale via the existing DeepL pipeline; CODED FACTS/TAGS (canonical, robots, hreflang, og:locale, JSON-LD data) are language-invariant; and the agent's INTERNAL analysis (audit scores, plan rationale, competitor analysis, run summary) stays **English-only**. On a missing/failed translation, the read path **falls back per-field to default-locale text** (never empty), so a live page is never broken.

**Architecture:** Reuse the existing `backend/auth_service/translation/` provider (DeepL/null). A new pure helper translates ONLY the prose fields of a flat `seo_page_meta`/`seo_articles` row, **omitting** (never blanking) any field whose translation fails. A new admin endpoint fills non-default locales after the agent writes the default-locale row. The public read endpoints deep-merge the requested locale over the default locale **per field** (omit-empty), so missing/failed translations transparently fall back. The agent writes default-locale prose only and runs its analysis in English. Source of truth: the verified localization decision matrix (in the design spec, added by Task 6).

**Tech Stack:** Python 3.13 + the existing `translation` module + pytest; FastAPI; Markdown agent/spec docs.

---

## File structure

```
backend/auth_service/
  translation/seo_translate.py            # CREATE — translate ONLY prose fields of a flat seo row (omit-on-failure)
  services/seo_repo.py                    # MODIFY — published_meta/published_articles get per-field default-locale fallback; + project_default_locale()
  routers/seo.py                          # MODIFY — POST .../seo/translate (admin) + public endpoints pass default_locale
  tests/test_seo_translate.py             # CREATE
  tests/test_seo_router.py                # MODIFY — fallback + translate-endpoint tests
agents/SEO-GEO Optimizer/
  guidelines/localization.md              # CREATE — the decision matrix (durable reference)
  phases/5-apply.md                       # MODIFY — write DEFAULT-locale prose → call translate → per-field fallback contract
  phases/3-audit.md / 4-plan.md           # MODIFY — analysis/plan English-only; audit still runs per-locale (reading)
  AGENTS.md                               # MODIFY — Localization policy section + Tools
.claude/skills/geo-content-writing/SKILL.md   # MODIFY — write DEFAULT-locale prose; English analysis; never per-locale-by-hand
agents/CMS Connector - Website/
  AGENTS.md / phases/4-integration.md     # MODIFY — generated site fetches per-locale seo meta with default fallback (server-side now)
docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md   # MODIFY — add the Localization Policy section
```

Tests: backend from `backend/`: `python -m pytest auth_service/tests/test_seo_translate.py auth_service/tests/test_seo_router.py -v`.

---

## Task 1: `seo_translate.py` — translate prose fields only (omit-on-failure)

**Files:** Create `backend/auth_service/translation/seo_translate.py`; Test `backend/auth_service/tests/test_seo_translate.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_seo_translate.py
from auth_service.translation import seo_translate


class FakeProvider:
    """Echoes UPPER(text) prefixed by target, to prove per-field translation ran."""
    def translate(self, texts, *, source, target, fmt="text"):
        return [f"{target}:{t}" for t in texts]


class FailProvider:
    def translate(self, texts, *, source, target, fmt="text"):
        raise RuntimeError("deepl down")


def test_meta_translates_prose_and_og_only():
    default = {"title": "Home", "description": "Welcome", "canonical": "https://x/",
               "robots": "index", "og": {"title": "Home", "description": "Welcome", "image": "https://x/o.png"},
               "json_ld": {"@type": "LocalBusiness", "telephone": "+31"}}
    out = seo_translate.translate_seo_prose(default, kind="meta", source="en", target="nl", provider=FakeProvider())
    assert out["title"] == "nl:Home" and out["description"] == "nl:Welcome"
    assert out["og"] == {"title": "nl:Home", "description": "nl:Welcome"}  # og.image NOT translated
    # invariant fields are NOT returned (caller keeps default / site generates)
    assert "canonical" not in out and "robots" not in out and "json_ld" not in out


def test_article_translates_body_as_markdown():
    default = {"title": "Fades", "excerpt": "About fades", "body": "# Fades\nGreat cuts.",
               "hero_image_url": "https://x/h.png", "json_ld": {"@type": "Article"}}
    out = seo_translate.translate_seo_prose(default, kind="article", source="en", target="nl", provider=FakeProvider())
    assert out["title"] == "nl:Fades" and out["excerpt"] == "nl:About fades"
    assert out["body"] == "nl:# Fades\nGreat cuts."
    assert "hero_image_url" not in out and "json_ld" not in out


def test_failed_translation_omits_field_never_blanks():
    default = {"title": "Home", "description": "Welcome"}
    out = seo_translate.translate_seo_prose(default, kind="meta", source="en", target="nl", provider=FailProvider())
    # omit (so read-layer falls back to default) — NEVER write "" or None
    assert out == {} or all(v not in (None, "") for v in out.values())
    assert "title" not in out  # omitted, not blanked


def test_empty_source_fields_are_skipped():
    out = seo_translate.translate_seo_prose({"title": "", "description": "Hi"},
                                            kind="meta", source="en", target="nl", provider=FakeProvider())
    assert "title" not in out and out["description"] == "nl:Hi"
```

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Write `seo_translate.py`**

```python
# backend/auth_service/translation/seo_translate.py
"""Translate ONLY the human-readable PROSE fields of a flat seo_page_meta / seo_articles
row from the website's default locale into a target locale, using the existing translation
provider. PURE w.r.t. inputs (provider is injected).

Policy (research-verified): localize prose (title/description/OG text/article body); keep
CODED FACTS invariant (canonical, robots, og.image, json_ld data, hero_image_url, og:locale,
hreflang, inLanguage) — those are generated per-page or repeated verbatim, NEVER translated.

Failure rule: OMIT a field whose translation fails or is empty (never write "" / null), so the
read-layer per-field default-locale fallback can fire and the page is never broken/empty.
"""
from __future__ import annotations

# (field, format) prose specs per kind. Everything not listed here is invariant.
_META_FIELDS = (("title", "text"), ("description", "text"))
_META_OG_FIELDS = (("title", "text"), ("description", "text"))
_ARTICLE_FIELDS = (("title", "text"), ("excerpt", "text"), ("body", "markdown"))


def _one(provider, text: str, *, source: str, target: str, fmt: str) -> str | None:
    if not text:
        return None
    try:
        res = provider.translate([text], source=source, target=target, fmt=fmt)
    except Exception:  # noqa: BLE001 — any provider/network error => omit (fallback fires)
        return None
    out = (res or [None])[0]
    return out or None


def translate_seo_prose(default_content: dict, *, kind: str, source: str, target: str, provider) -> dict:
    """Return {field: translated} for the prose fields that translated successfully.
    Omits any field that is empty in the source or whose translation failed."""
    out: dict = {}
    if kind == "meta":
        for field, fmt in _META_FIELDS:
            t = _one(provider, default_content.get(field), source=source, target=target, fmt=fmt)
            if t is not None:
                out[field] = t
        og = default_content.get("og") or {}
        tog: dict = {}
        for field, fmt in _META_OG_FIELDS:
            t = _one(provider, og.get(field), source=source, target=target, fmt=fmt)
            if t is not None:
                tog[field] = t
        if tog:
            out["og"] = tog
    elif kind == "article":
        for field, fmt in _ARTICLE_FIELDS:
            t = _one(provider, default_content.get(field), source=source, target=target, fmt=fmt)
            if t is not None:
                out[field] = t
    return out
```

- [ ] **Step 4: Run to verify it passes** → 4 passed.
- [ ] **Step 5: Commit (checkpoint)** — stage only.

---

## Task 2: `seo_repo` — per-field default-locale read fallback

**Files:** Modify `backend/auth_service/services/seo_repo.py`; Test `backend/auth_service/tests/test_seo_router.py` (covered via router in Task 3)

- [ ] **Step 1: Add `project_default_locale()` + rewrite `published_meta` / `published_articles`** with per-field fallback. Replace the existing `published_meta`/`published_articles` with:

```python
def project_default_locale(project_id: str) -> str:
    sb = get_supabase_admin()
    res = sb.table("projects").select("default_locale").eq("id", project_id).maybe_single().execute()
    return (res.data or {}).get("default_locale") or "en"


_META_PUBLIC_COLS = "title, description, canonical, og, json_ld, robots"


def _published_meta_row(project_id: str, route: str, locale: str) -> dict | None:
    sb = get_supabase_admin()
    res = (sb.table("seo_page_meta").select(_META_PUBLIC_COLS).eq("project_id", project_id)
           .eq("route", route).eq("locale", locale).eq("status", "published").limit(1).execute())
    rows = res.data or []
    return rows[0] if rows else None


def _merge_nonempty(base: dict, over: dict) -> dict:
    """Overlay `over` onto `base` per field, ignoring empty values (so default survives).
    og is merged one level deep (translated og.title/description over default og.image)."""
    merged = dict(base or {})
    for k, v in (over or {}).items():
        if v in (None, "", {}, []):
            continue
        if k == "og" and isinstance(v, dict) and isinstance(merged.get("og"), dict):
            og = dict(merged["og"])
            for ok, ov in v.items():
                if ov not in (None, "", {}, []):
                    og[ok] = ov
            merged["og"] = og
        else:
            merged[k] = v
    return merged


def published_meta(project_id: str, route: str, locale: str) -> dict | None:
    """Requested-locale published meta with PER-FIELD fallback to the default locale.
    A missing/failed-translation locale transparently shows default-locale text (never empty)."""
    default_locale = project_default_locale(project_id)
    target = _published_meta_row(project_id, route, locale)
    base = _published_meta_row(project_id, route, default_locale) if default_locale != locale else None
    if not target and not base:
        return None
    return _merge_nonempty(base or {}, target or {})


_ARTICLE_PUBLIC_COLS = "slug, locale, title, excerpt, body, json_ld, hero_image_url"


def published_articles(project_id: str, locale: str) -> list[dict]:
    """Published articles for a locale, each per-field-filled from the default-locale article
    of the same slug (so an untranslated article shows default-locale prose, never empty)."""
    sb = get_supabase_admin()
    default_locale = project_default_locale(project_id)

    def rows_for(loc: str) -> dict[str, dict]:
        res = (sb.table("seo_articles").select(_ARTICLE_PUBLIC_COLS).eq("project_id", project_id)
               .eq("locale", loc).eq("status", "published").execute())
        return {r["slug"]: r for r in (res.data or [])}

    target = rows_for(locale)
    base = rows_for(default_locale) if default_locale != locale else {}
    slugs = set(target) | set(base)
    out: list[dict] = []
    for slug in slugs:
        merged = _merge_nonempty(base.get(slug, {}), target.get(slug, {}))
        if merged:
            merged["slug"] = slug
            out.append(merged)
    return out
```

- [ ] **Step 2: Verify imports** — `python -c "from auth_service.services import seo_repo; print('ok')"` → ok.
- [ ] **Step 3: Commit (checkpoint).**

---

## Task 3: `seo.py` router — translate endpoint + public endpoints unchanged signature

**Files:** Modify `backend/auth_service/routers/seo.py`; Test `backend/auth_service/tests/test_seo_router.py`

- [ ] **Step 1: Write the failing tests (append to `test_seo_router.py`)**

```python
def test_public_meta_falls_back_to_default(monkeypatch):
    # requested locale (nl) missing a title → default-locale title shows through
    monkeypatch.setattr("auth_service.routers.seo._project_id_by_slug", lambda slug: "p1")
    with patch("auth_service.routers.seo.seo_repo.published_meta",
               return_value={"title": "Welkom", "description": "NL desc"}):
        r = client.get("/projects/acme/seo/public/meta?route=/&locale=nl")
    assert r.status_code == 200 and r.json()["title"] == "Welkom"


def test_translate_endpoint_fills_locales(monkeypatch):
    _auth(monkeypatch)  # admin
    calls = {}
    def fake_fill(project, kind):
        calls["kind"] = kind
        return {"translated": 2}
    monkeypatch.setattr("auth_service.routers.seo._translate_seo_for_project", lambda project, kind: fake_fill(project, kind))
    r = client.post("/projects/acme/seo/translate", json={"kind": "meta"})
    assert r.status_code == 200 and calls["kind"] == "meta"
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Add the translate endpoint + helper to `seo.py`** (append). The public endpoints already call `seo_repo.published_meta(pid, route, locale)` / `published_articles(pid, locale)` whose signatures are unchanged (the fallback is internal to the repo), so they need NO edit.

```python
# append imports
from ..translation import get_provider  # provider factory (deepl/null) — confirm the exact name in translation/__init__.py
from ..translation import seo_translate
from ..models.seo_schemas import SeoTranslateIn  # add this schema (see below)


def _project_locales(project_id: str) -> tuple[str, list[str]]:
    sb = get_supabase_admin()
    res = sb.table("projects").select("default_locale, locales").eq("id", project_id).maybe_single().execute()
    row = res.data or {}
    return (row.get("default_locale") or "en", list(row.get("locales") or []))


def _translate_seo_for_project(project: dict, kind: str) -> dict:
    """Fill non-default locales for every default-locale seo row of `kind` via the provider.
    Skips a target row a HUMAN edited (updated_by not agent*) so manual edits are preserved.
    Omit-on-failure: a failed field is left unwritten (read-layer falls back to default)."""
    sb = get_supabase_admin()
    pid = project["id"]
    default_locale, locales = _project_locales(pid)
    targets = [l for l in locales if l and l != default_locale]
    if not targets:
        return {"translated": 0}
    provider = get_provider()
    table = "seo_page_meta" if kind == "meta" else "seo_articles"
    defaults = (sb.table(table).select("*").eq("project_id", pid).eq("locale", default_locale).execute().data or [])
    count = 0
    for d in defaults:
        key = {"route": d["route"]} if kind == "meta" else {"slug": d["slug"]}
        for loc in targets:
            q = sb.table(table).select("updated_by").eq("project_id", pid).eq("locale", loc)
            for k, v in key.items():
                q = q.eq(k, v)
            existing = (q.limit(1).execute().data or [])
            if existing and not str(existing[0].get("updated_by", "")).startswith("agent"):
                continue  # preserve a human-edited translation
            prose = seo_translate.translate_seo_prose(d, kind=kind, source=default_locale, target=loc, provider=provider)
            if not prose:
                continue
            payload = {**key, "project_id": pid, "locale": loc, "status": d.get("status", "draft"),
                       "updated_by": "agent-translation", **prose}
            conflict = "project_id,route,locale" if kind == "meta" else "project_id,slug,locale"
            sb.table(table).upsert(payload, on_conflict=conflict).execute()
            count += 1
    return {"translated": count}


@router.post("/projects/{project_slug}/seo/translate")
async def translate_seo(project_slug: str, body: SeoTranslateIn, request: Request) -> dict:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    return _translate_seo_for_project(project, body.kind)
```

Add to `models/seo_schemas.py`:
```python
class SeoTranslateIn(BaseModel):
    kind: str = "meta"  # 'meta' | 'article'
```

> **Note:** confirm the provider-factory name in `backend/auth_service/translation/__init__.py` (the Explore found provider selection there). If it's not `get_provider`, use the real accessor. The provider exposes `.translate(texts, *, source, target, fmt)`.

- [ ] **Step 4: Run to verify they pass.**
- [ ] **Step 5: Full backend SEO + translation suites green** — `python -m pytest auth_service/tests/test_seo_translate.py auth_service/tests/test_seo_router.py auth_service/tests/ -q` (run targeted then full; expect no regressions).
- [ ] **Step 6: Commit (checkpoint).**

---

## Task 4: Agent — write default-locale prose, English analysis, fallback contract

**Files:** Modify `.claude/skills/geo-content-writing/SKILL.md`, `agents/SEO-GEO Optimizer/phases/5-apply.md`, `3-audit.md`, `4-plan.md`, `AGENTS.md`; Create `agents/SEO-GEO Optimizer/guidelines/localization.md`

- [ ] **Step 1: `guidelines/localization.md`** — the durable decision matrix (the three buckets): PROSE→per-locale via DeepL (meta title/description, OG title/description, JSON-LD text, visible article/blog body); CODED FACTS/TAGS→language-invariant (canonical, robots, hreflang, og:locale, JSON-LD inLanguage [a per-locale CODE], JSON-LD data address/phone/geo/openingHours/sameAs/image); INTERNAL→English-only (audit scores, plan rationale, competitor analysis, run summary). Include: the unifying rule ("Google determines page language from visible content, so metadata localization is a CONSISTENCY requirement, not a ranking lever"); the FAILURE rule (omit field, never blank → per-field default fallback; per-field/template fallback is NOT duplicate content; a whole untranslated body must NOT be published as a separate same-language URL); the precise-wording guards (title mismatch = SERP DISPLAY override, NOT a ranking penalty; raw MT = quality-ranking risk, NOT a manual action); SSR-per-locale (G-1 applies to every locale, not just default). End with the FORBIDDEN_CLAIMS block.
- [ ] **Step 2: `geo-content-writing/SKILL.md`** — change the per-locale instruction: WRITE all prose (article body, meta title/description, OG text) in the website's **DEFAULT locale** only; do NOT hand-write other locales — the CMS DeepL pipeline (the `POST /projects/{slug}/seo/translate` endpoint) fills them, with per-field default fallback on failure. The GATE-FACT verbatim-source check runs in the **default locale** (a default-locale claim cites a default-locale-language source). Coded facts/internal analysis are not translated.
- [ ] **Step 3: `phases/5-apply.md`** — after writing the DEFAULT-locale `seo_page_meta`/`seo_articles` rows (via MCP), call `POST /projects/{slug}/seo/translate` (kind=meta, then kind=article) to fill the other locales; document the omit-on-failure + per-field default-fallback contract; never hand-write non-default locales.
- [ ] **Step 4: `phases/3-audit.md` + `4-plan.md`** — clarify: the audit still RUNS per locale (reading the live per-locale pages), but the agent's analysis artifacts (`seo_runs.summary`, `seo_plan_items.rationale`, `seo_competitors.analysis`, scores) are authored in **English** regardless of the site's locales (operator-facing).
- [ ] **Step 5: `AGENTS.md`** — add a "Localization policy" section (pointer to `guidelines/localization.md`); add the translate endpoint to Tools; note the default-locale-prose + English-analysis rule.
- [ ] **Step 6: Verify** the localization guideline + the SKILL/phase edits reference the translate endpoint, the three buckets, the failure rule, and the forbidden block (`grep`/`python -c`).
- [ ] **Step 7: Commit (checkpoint).**

---

## Task 5: Connector + Website Builder — per-locale SEO fetch with default fallback

**Files:** Modify `agents/CMS Connector - Website/AGENTS.md`, `phases/4-integration.md`; `agents/Website Builder/AGENTS.md` (+ `phases/9-incremental.md`)

- [ ] **Step 1: Connector `AGENTS.md` + `phases/4-integration.md`** — in the SEO-area subsection (added in Plan 4), clarify that the public read endpoints now do the per-field default-locale fallback **server-side**, so the generated site simply fetches `GET /projects/{slug}/seo/public/meta?route=&locale=<active-locale>` (and `/articles?locale=`) for the active locale and never has to merge; it still never-throws on error. `generateMetadata` uses the returned (already-fallen-back) prose; it generates canonical/hreflang/og:locale/inLanguage **itself per locale** (these are coded tags, not fetched). Articles render per active locale (default-prose fallback already applied).
- [ ] **Step 2: Website Builder `AGENTS.md` + `phases/9-incremental.md`** — same: incrementally-built `/blog` + pages fetch the active-locale SEO endpoints (server-side fallback); generate canonical/hreflang/og:locale/inLanguage per locale locally; SSR every locale (G-1 per locale).
- [ ] **Step 3: Verify** both reference the active-locale fetch + "canonical/hreflang generated per-locale locally" + "server-side default fallback".
- [ ] **Step 4: Commit (checkpoint).**

---

## Task 6: Design spec — Localization Policy section

**Files:** Modify `docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md`

- [ ] **Step 1: Add a "Localization policy (per-locale vs invariant vs English)" section** with the verified decision matrix (the three buckets + the unifying rule + the failure/fallback rule + the precise-wording guards + the SSR-per-locale prerequisite + the GEO caveat that no source ties metadata LANGUAGE to AI-citation, so it is justified on Google consistency + CTR only). Reference `agents/SEO-GEO Optimizer/guidelines/localization.md` as the agent-facing copy.
- [ ] **Step 2: Commit (checkpoint).**

---

## Task 7: Review + verify (controller)

- [ ] **Step 1:** Backend suites green: `cd backend && python -m pytest auth_service/tests/test_seo_translate.py auth_service/tests/test_seo_router.py auth_service/tests/ -q` — new tests pass, no regressions.
- [ ] **Step 2:** Live smoke (controller): for samir (default locale `nl`), confirm the translate path: write a default-locale (nl) `seo_page_meta` is already published; with `TRANSLATION_PROVIDER=null` the endpoint echoes (no real DeepL spend in this repo), so verify the endpoint runs + the public `/seo/public/meta?locale=en` falls back to the nl default per-field (since en untranslated). Confirm no empty fields are ever returned.
- [ ] **Step 3:** Dispatch a reviewer over the localization change: confirm prose-only translation, omit-on-failure (never blank), per-field default fallback, English-only internal artifacts, and that coded facts (canonical/og:locale/inLanguage/json_ld data) are NEVER translated.

---

## Self-review

**Spec coverage:** prose→per-locale via DeepL (helper + endpoint) ✓; coded facts invariant (helper translates prose only; never canonical/robots/og.image/json_ld-data/hero_image) ✓; internal artifacts English-only (agent doc edits) ✓; omit-on-failure never-blank ✓ (`translate_seo_prose` returns only successful fields); per-field default-locale read fallback ✓ (`_merge_nonempty`); default-locale-prose write + English analysis ✓ (geo-content-writing + phases); connector/builder fetch active locale (server-side fallback) ✓; design-spec policy section ✓.

**Placeholder scan:** backend fully coded + tested; the one runtime unknown (provider-factory accessor name) is flagged with a confirm-step. Doc edits have precise required content.

**Type/name consistency:** `translate_seo_prose(default_content, kind, source, target, provider)` signature matches the endpoint call + tests; `published_meta`/`published_articles` keep their existing `(project_id, route|_, locale)` signatures (fallback is internal — public endpoints + their tests unchanged); `kind` values `meta`/`article` consistent across helper, endpoint, schema, and the apply phase.

---

## Note on existing data

samir already has published `seo_page_meta` rows for nl + en (Plan 3 live test) — both were written directly. After this ships, running the translate endpoint for samir (default `nl`) would fill `en` from `nl` via the provider; with `TRANSLATION_PROVIDER=null` it echoes. No migration needed (uses existing columns + `updated_by` to protect human edits).
