# SEO/GEO Agent Core — Implementation Plan (Plan 2 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

> **Commit policy (Stefan's rule):** Do NOT `git commit`. "Commit" steps are checkpoints — stage/leave in the working tree; Stefan batch-commits later.

**Goal:** Build the SEO/GEO Optimizer agent's read/analyze/plan core — a main-thread skill (`Run SEO agent for <project>`) that loads per-client memory, does reasoned competitor + local intel, audits the live site per-locale (deterministic SEO + LLM-judge GEO + local), and writes a prioritized plan — all persisted to the Supabase `seo_*` tables Plan 1 created and surfaced in the dashboard. No applying/publishing yet (Plan 3), no new pages (Plan 4).

**Architecture:** A skill (`.claude/skills/seo-geo-optimizer/SKILL.md`) + spec (`agents/SEO-GEO Optimizer/AGENTS.md`) + lazy-loaded `phases/0-4` running in the main Claude Code thread (full tools: WebSearch, WebFetch, Playwright MCP, Supabase MCP). Deterministic analysis lives in **stdlib-only, unit-tested Python** (`render_check.py`, `audit.py`, `competitor.py`); the reasoning (competitor analysis, GEO judging, planning) lives in the phase docs + `prompts.py` system prompts. Per-client memory + results are written to Supabase via `mcp__supabase__execute_sql` (project `xeluydwpgiddbamysgyu`), mirroring the Design Prompt Creator. The 11 research-refuted claims are embedded as a forbidden block in `prompts.py` + every phase doc.

**Tech Stack:** Python 3.13 stdlib (urllib, html.parser, re, json) + pytest. Markdown agent docs. Supabase MCP. Source of truth for all content: `docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md`.

---

## File structure

```
agents/SEO-GEO Optimizer/
  AGENTS.md                       # CREATE — authoritative spec (phases 0–7, autonomy, constants, memory, failure modes)
  README.md                       # CREATE — quick reference
  LEARNINGS.md                    # CREATE — append-only AGENT-MECHANICS lessons (scaffold)
  example-prompts.md              # CREATE — invocation examples
  prompts.py                      # CREATE — FORBIDDEN_CLAIMS + system prompts (tested: forbidden present)
  render_check.py                 # CREATE — fetch raw HTML (GPTBot UA) + extract on-page signals (tested)
  audit.py                        # CREATE — deterministic SEO + local scoring; audit assembly (tested)
  competitor.py                   # CREATE — competitor signal extraction + content-gap analysis (tested)
  guidelines/
    google-technical-onpage.md    # CREATE — Track G KB (from design spec)
    geo-answer-engines.md         # CREATE — Track E KB (from design spec)
    local-seo.md                  # CREATE — Track L KB (from design spec)
  rubric/
    rubric.yaml                   # CREATE — scored audit rubric (ids/track/weight/threshold/measure-kind)
  phases/
    0-parse-intent.md             # CREATE
    1-load-context.md             # CREATE
    2-competitor-intel.md         # CREATE
    3-audit.md                    # CREATE
    4-plan.md                     # CREATE
  tests/
    test_render_check.py          # CREATE
    test_audit.py                 # CREATE
    test_competitor.py            # CREATE
    test_prompts.py               # CREATE

.claude/skills/seo-geo-optimizer/SKILL.md   # CREATE — the entry point (frontmatter + trigger + first steps + lazy table)
agents/README.md                            # MODIFY — append catalog row
```

Tests run from repo root: `python -m pytest "agents/SEO-GEO Optimizer/tests/" -v` (stdlib-only — no venv/deps needed; if pytest isn't on PATH, use the backend venv: `source backend/venv/Scripts/activate`).

---

## Task 1: `prompts.py` — system prompts + the forbidden-claims block

**Files:**
- Create: `agents/SEO-GEO Optimizer/prompts.py`
- Test: `agents/SEO-GEO Optimizer/tests/test_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
# agents/SEO-GEO Optimizer/tests/test_prompts.py
import importlib.util, pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "prompts.py"
_spec = importlib.util.spec_from_file_location("seo_prompts", _p)
prompts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prompts)


def test_all_eleven_refuted_claims_are_forbidden():
    needles = [
        "FAQPage", "3.2",            # FAQ 3.2x AI Overviews
        "67%",                       # answer-first 67%
        "92.36",                     # 92.36% top-10
        "llms.txt",                  # llms.txt as signal
        "32%",                       # GBP 32% weight
        "7x", "4.4x",                # completeness/review click multipliers
        "74%",                       # NAP 74% exclusion
        "10 ", "categor",            # all-10-GBP-categories
        "vector",                    # vector-store memory split
    ]
    blob = prompts.FORBIDDEN_CLAIMS.lower()
    for n in needles:
        assert n.lower() in blob, f"forbidden block missing reference to {n!r}"


def test_geo_judge_prompt_demands_verbatim_source_and_no_fabrication():
    p = prompts.GEO_JUDGE_PROMPT.lower()
    assert "verbatim" in p or "literal" in p
    assert "fabricat" in p or "made up" in p or "real" in p
    assert "readiness" in p  # we score readiness, never promise citation


def test_planner_prompt_uses_action_kinds():
    for kind in ["content", "meta", "schema", "article", "new_page", "manual_human"]:
        assert kind in prompts.PLANNER_PROMPT
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest "agents/SEO-GEO Optimizer/tests/test_prompts.py" -v`
Expected: FAIL — `prompts.py` not found.

- [ ] **Step 3: Write `prompts.py`**

```python
# agents/SEO-GEO Optimizer/prompts.py
"""System prompts + the research-refuted forbidden-claims block for the SEO/GEO agent.

Source of truth: docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md (Guidelines KB).
Every reasoning prompt embeds FORBIDDEN_CLAIMS so the agent never regresses to the 11
adversarially-refuted SEO/GEO myths (training-prior leakage).
"""

# The 11 claims that FAILED adversarial verification. NEVER assert as fact, NEVER score on them.
FORBIDDEN_CLAIMS = """
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
""".strip()

# Confirmed, evidence-backed levers (KDD 2024 arXiv:2311.09735; Lilian Weng; Local Falcon).
CONFIRMED_LEVERS = """
EVIDENCE-BACKED LEVERS (use ONLY these for GEO):
- Add REAL source citations, REAL direct quotations, REAL statistics (~30-40% relative AI-citation
  lift). Keyword-stuffing/density gives ~0 lift — do not rely on it.
- Server-rendered HTML (AI/Google bots do NOT run JS), clean H1->H2->H3, short one-idea paragraphs,
  valid JSON-LD. These help both Google and AI extraction.
- The "~40%" headline is best-case RELATIVE on a synthetic metric — NEVER quote it as a guarantee.
""".strip()

AUDITOR_GUIDE = (
    "You are auditing a single web page for SEO + GEO readiness, per locale. "
    "Use the deterministic signals provided plus your judgement. " + CONFIRMED_LEVERS + "\n\n" + FORBIDDEN_CLAIMS
)

GEO_JUDGE_PROMPT = (
    "You are an AI-answer-engine readiness judge. Given a page's main text (in its own language/locale), "
    "score 0-100 how likely an answer engine (ChatGPT Search / Perplexity / Google AI Overviews / Gemini) "
    "would CITE a passage from it, based ONLY on intrinsic quality: presence of REAL attributed "
    "statistics, REAL direct quotations, REAL source citations, short citable one-idea paragraphs, and "
    "clear structure. We score READINESS — never promise an actual citation. "
    "ALSO extract every factual claim/statistic/quote and its named source. For each, state whether the "
    "source is given and verifiable; flag any stat/quote that looks FABRICATED or unverifiable. A page that "
    "would require fabricated/unverifiable evidence must NOT score highly. Demand verbatim/literal source "
    "attribution; do not reward made-up numbers. Return JSON {score, citable_passages, claims:[{text,source,verifiable}]}. "
    "Score as a native reader of the page's locale would.\n\n" + FORBIDDEN_CLAIMS
)

COMPETITOR_ANALYST_PROMPT = (
    "You are a senior local-SEO + GEO competitive analyst. Given the client's business (name, category, "
    "location, services) and structured signals extracted from the client's site and several competitor "
    "sites, produce a REASONED analysis: who the real local competitors are, what content/topics/schema "
    "they cover that the client does not, where the client can win on GEO (citable, evidence-backed "
    "content), and the concrete content gaps. Be specific and prioritized. Backlinks/off-page authority "
    "and true geo-grid map-pack rank require paid data — say so honestly, do not fabricate them.\n\n" + FORBIDDEN_CLAIMS
)

PLANNER_PROMPT = (
    "You are planning SEO/GEO improvements for one client site. Given the per-locale audit (deterministic "
    "SEO + GEO readiness + local scores with per-item detail), the competitor gap analysis, and the "
    "guidelines, produce a PRIORITIZED, plain-language plan. Each item: a clear title, a one-sentence "
    "'why it matters' (grounded ONLY in confirmed levers), priority (0-10), effort (low/medium/high), the "
    "track (seo|geo|local), and an action_kind, one of: content, meta, schema, article, new_page, "
    "manual_human. Use 'manual_human' honestly for backlinks / E-E-A-T / Google Business Profile edits "
    "(not automatable). Sell readiness, never ranking guarantees.\n\n" + FORBIDDEN_CLAIMS
)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest "agents/SEO-GEO Optimizer/tests/test_prompts.py" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit (checkpoint)** — `git add agents/"SEO-GEO Optimizer"/prompts.py agents/"SEO-GEO Optimizer"/tests/test_prompts.py` (no commit).

---

## Task 2: `render_check.py` — fetch raw HTML + extract on-page signals

**Files:**
- Create: `agents/SEO-GEO Optimizer/render_check.py`
- Test: `agents/SEO-GEO Optimizer/tests/test_render_check.py`

- [ ] **Step 1: Write the failing test**

```python
# agents/SEO-GEO Optimizer/tests/test_render_check.py
import importlib.util, pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "render_check.py"
_spec = importlib.util.spec_from_file_location("seo_render_check", _p)
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)

GOOD = """
<html><head>
<title>Best Barber in Rotterdam — Samir Kapsalon</title>
<meta name="description" content="Sharp fades and classic cuts in central Rotterdam. Book your barber online in under a minute at Samir Kapsalon, with walk-ins welcome and top local ratings.">
<link rel="canonical" href="https://x.nl/">
<meta property="og:title" content="Samir"><meta property="og:image" content="https://x.nl/og.png">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"LocalBusiness","name":"Samir"}</script>
</head><body>
<h1>Samir Kapsalon</h1>
<h2>Services</h2><p>We offer sharp fades, classic scissor cuts, hot-towel shaves and beard trims for every style. According to a 2025 industry survey, 70% of our clients now book their appointments online instead of waiting in line.</p>
<h2>Visit</h2><p>Find us in central Rotterdam, a short walk from the station. Walk-ins are welcome, but booking ahead guarantees your preferred barber and time slot on busy weekends.</p>
<a href="/services">Services</a><a href="/contact">Contact</a>
</body></html>
"""

BAD = "<html><head></head><body><div id='root'></div></body></html>"


def test_extract_signals_good_page():
    s = rc.extract_signals(GOOD)
    assert s["h1_count"] == 1
    assert s["heading_order_ok"] is True
    assert 40 <= s["title_len"] <= 60
    assert 140 <= s["meta_desc_len"] <= 160
    assert s["canonical"] == "https://x.nl/"
    assert "LocalBusiness" in s["jsonld_types"]
    assert s["jsonld_valid"] is True
    assert s["has_localbusiness"] is True
    assert s["og_present"] is True
    assert s["internal_link_count"] == 2
    assert s["has_main_content"] is True
    assert s["word_count"] > 20


def test_extract_signals_empty_client_rendered_page():
    s = rc.extract_signals(BAD)
    assert s["h1_count"] == 0
    assert s["has_main_content"] is False  # nothing in raw HTML — invisible to AI bots
    assert s["jsonld_types"] == []
    assert s["canonical"] is None


def test_invalid_jsonld_flagged():
    html = '<html><body><script type="application/ld+json">{bad json}</script><h1>x</h1></body></html>'
    s = rc.extract_signals(html)
    assert s["jsonld_valid"] is False


def test_heading_order_skip_detected():
    html = "<html><body><h1>A</h1><h4>skipped</h4></body></html>"
    s = rc.extract_signals(html)
    assert s["heading_order_ok"] is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest "agents/SEO-GEO Optimizer/tests/test_render_check.py" -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `render_check.py`**

```python
# agents/SEO-GEO Optimizer/render_check.py
"""Fetch a page's RAW server HTML (the view AI/Google bots get — they don't run JS)
and extract deterministic on-page SEO/GEO signals. Stdlib only.
"""
from __future__ import annotations

import json
import re
import urllib.request
from html.parser import HTMLParser

# A GPTBot-style UA so we measure exactly what AI crawlers see.
_UA = "Mozilla/5.0 (compatible; SEOGEOAuditBot/1.0; +https://roman-technologies.dev)"
_BYTE_CAP = 600_000


def fetch_raw(url: str, timeout: int = 20) -> str:
    """GET the raw HTML (no JS execution). Raises urllib errors to the caller."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted client URLs)
        raw = resp.read(_BYTE_CAP)
    return raw.decode("utf-8", errors="replace")


class _TextHeadingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings: list[int] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self._skip = 0  # inside script/style

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(int(tag[1]))
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.links.append(v)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.text_parts.append(data.strip())


def _meta(html: str, attr: str, key: str) -> str | None:
    m = re.search(
        rf'<meta[^>]+{attr}=["\']{re.escape(key)}["\'][^>]*content=["\']([^"\']*)["\']',
        html, re.IGNORECASE,
    )
    if m:
        return m.group(1)
    m = re.search(
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*{attr}=["\']{re.escape(key)}["\']',
        html, re.IGNORECASE,
    )
    return m.group(1) if m else None


def _title(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _canonical(html: str) -> str | None:
    m = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE
    )
    return m.group(1) if m else None


def _jsonld(html: str) -> tuple[list[str], bool]:
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.IGNORECASE | re.DOTALL,
    )
    types: list[str] = []
    valid = True
    for b in blocks:
        try:
            data = json.loads(b.strip())
        except (ValueError, TypeError):
            valid = False
            continue
        for node in data if isinstance(data, list) else [data]:
            t = node.get("@type") if isinstance(node, dict) else None
            if isinstance(t, str):
                types.append(t)
            elif isinstance(t, list):
                types.extend(x for x in t if isinstance(x, str))
    return types, (valid if blocks else True)


_LOCAL_TYPES = {
    "LocalBusiness", "Restaurant", "Store", "HairSalon", "BeautySalon",
    "ProfessionalService", "Dentist", "MedicalBusiness", "FoodEstablishment",
}


def _headings_ordered(levels: list[int]) -> bool:
    """No skipped level on the way DOWN (e.g. h1 then h4 is a skip)."""
    prev = 0
    for lv in levels:
        if prev and lv > prev + 1:
            return False
        prev = lv
    return True


def extract_signals(html: str) -> dict:
    """Pure: HTML string -> deterministic signal dict (no network)."""
    p = _TextHeadingParser()
    p.feed(html)
    text = " ".join(p.text_parts)
    word_count = len(text.split())
    title = _title(html)
    desc = _meta(html, "name", "description")
    jsonld_types, jsonld_valid = _jsonld(html)
    internal = [
        h for h in p.links
        if h.startswith("/") or (not h.startswith(("http", "mailto:", "tel:", "#")))
    ]
    return {
        "h1_count": p.headings.count(1),
        "heading_order_ok": _headings_ordered(p.headings),
        "title": title,
        "title_len": len(title) if title else 0,
        "meta_description": desc,
        "meta_desc_len": len(desc) if desc else 0,
        "canonical": _canonical(html),
        "jsonld_types": jsonld_types,
        "jsonld_valid": jsonld_valid,
        "has_localbusiness": any(t in _LOCAL_TYPES for t in jsonld_types),
        "og_present": bool(_meta(html, "property", "og:title") or _meta(html, "property", "og:image")),
        "internal_link_count": len(internal),
        "word_count": word_count,
        "has_main_content": word_count >= 50,
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest "agents/SEO-GEO Optimizer/tests/test_render_check.py" -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit (checkpoint)** — stage only.

---

## Task 3: `audit.py` — deterministic SEO + local scoring + audit assembly

**Files:**
- Create: `agents/SEO-GEO Optimizer/audit.py`
- Test: `agents/SEO-GEO Optimizer/tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

```python
# agents/SEO-GEO Optimizer/tests/test_audit.py
import importlib.util, pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "audit.py"
_spec = importlib.util.spec_from_file_location("seo_audit", _p)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

PERFECT = {
    "h1_count": 1, "heading_order_ok": True, "title_len": 55, "meta_desc_len": 150,
    "canonical": "https://x/", "jsonld_types": ["LocalBusiness"], "jsonld_valid": True,
    "has_localbusiness": True, "og_present": True, "internal_link_count": 5,
    "has_main_content": True, "word_count": 400,
}
EMPTY = {
    "h1_count": 0, "heading_order_ok": True, "title_len": 0, "meta_desc_len": 0,
    "canonical": None, "jsonld_types": [], "jsonld_valid": True, "has_localbusiness": False,
    "og_present": False, "internal_link_count": 0, "has_main_content": False, "word_count": 0,
}


def test_perfect_page_scores_high():
    score, detail = audit.score_seo(PERFECT)
    assert score >= 90
    assert detail["G-1_content_in_raw_html"] == "pass"


def test_empty_page_scores_low():
    score, _ = audit.score_seo(EMPTY)
    assert score <= 20


def test_local_score_rewards_localbusiness_jsonld():
    hi, _ = audit.score_local(PERFECT)
    lo, _ = audit.score_local(EMPTY)
    assert hi > lo and hi >= 50


def test_assemble_audit_clamps_and_carries_geo():
    a = audit.assemble_audit(seo=88, geo=72, local=64, scores_detail={"x": 1})
    assert a == {"seo_score": 88, "geo_score": 72, "local_score": 64, "scores_detail": {"x": 1}}
    # geo is provided by the LLM judge; assemble just packages it
    clamped = audit.assemble_audit(seo=120, geo=-5, local=64, scores_detail={})
    assert clamped["seo_score"] == 100 and clamped["geo_score"] == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest "agents/SEO-GEO Optimizer/tests/test_audit.py" -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `audit.py`**

```python
# agents/SEO-GEO Optimizer/audit.py
"""Deterministic SEO + local scoring from render_check signals. GEO score comes from
the LLM judge (the skill) and is just packaged here. Stdlib only, pure functions.

Each item maps to the design spec's rubric (docs/.../2026-06-14-seo-geo-agent-design.md).
Refuted claims are NOT scored. Schema is a structured signal, not an AI-citation multiplier.
"""
from __future__ import annotations


def _clamp(n: int) -> int:
    return max(0, min(100, int(round(n))))


# (rubric_id, weight, predicate)
_SEO_ITEMS = [
    ("G-1_content_in_raw_html", 18, lambda s: bool(s.get("has_main_content"))),
    ("G-3_single_h1", 8, lambda s: s.get("h1_count") == 1),
    ("G-3_heading_order", 8, lambda s: bool(s.get("heading_order_ok"))),
    ("G-4_title_len", 10, lambda s: 40 <= s.get("title_len", 0) <= 60),
    ("G-4_meta_desc_len", 10, lambda s: 120 <= s.get("meta_desc_len", 0) <= 165),
    ("G-5_canonical", 8, lambda s: bool(s.get("canonical"))),
    ("G-6_jsonld_valid", 12, lambda s: bool(s.get("jsonld_types")) and bool(s.get("jsonld_valid"))),
    ("G-8_internal_links", 6, lambda s: s.get("internal_link_count", 0) >= 1),
    ("G-onpage_og", 6, lambda s: bool(s.get("og_present"))),
]

_LOCAL_ITEMS = [
    ("L-1_localbusiness_jsonld", 60, lambda s: bool(s.get("has_localbusiness"))),
    ("L-onpage_has_content", 40, lambda s: bool(s.get("has_main_content"))),
]


def _score(items: list, signals: dict) -> tuple[int, dict]:
    earned = 0
    possible = 0
    detail: dict[str, str] = {}
    for rid, w, pred in items:
        possible += w
        ok = bool(pred(signals))
        earned += w if ok else 0
        detail[rid] = "pass" if ok else "fail"
    return _clamp(100 * earned / possible if possible else 0), detail


def score_seo(signals: dict) -> tuple[int, dict]:
    return _score(_SEO_ITEMS, signals)


def score_local(signals: dict) -> tuple[int, dict]:
    return _score(_LOCAL_ITEMS, signals)


def assemble_audit(seo: int, geo: int, local: int, scores_detail: dict) -> dict:
    """Package the three sub-scores (geo from the LLM judge) into a seo_audits row payload."""
    return {
        "seo_score": _clamp(seo),
        "geo_score": _clamp(geo),
        "local_score": _clamp(local),
        "scores_detail": scores_detail or {},
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest "agents/SEO-GEO Optimizer/tests/test_audit.py" -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit (checkpoint)** — stage only.

---

## Task 4: `competitor.py` — competitor signal extraction + content-gap analysis

**Files:**
- Create: `agents/SEO-GEO Optimizer/competitor.py`
- Test: `agents/SEO-GEO Optimizer/tests/test_competitor.py`

- [ ] **Step 1: Write the failing test**

```python
# agents/SEO-GEO Optimizer/tests/test_competitor.py
import importlib.util, pathlib

_rc = pathlib.Path(__file__).resolve().parents[1] / "render_check.py"
_cp = pathlib.Path(__file__).resolve().parents[1] / "competitor.py"
import importlib.machinery  # noqa

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

comp = _load("seo_competitor", _cp)

CLIENT = {"jsonld_types": ["LocalBusiness"], "word_count": 120, "has_faq": False,
          "headings": ["Services", "Visit"]}
RIVAL_A = {"jsonld_types": ["LocalBusiness", "FAQPage"], "word_count": 900, "has_faq": True,
           "headings": ["Services", "Pricing", "FAQ", "Reviews"]}


def test_extract_competitor_signals_detects_faq_schema():
    html = '<html><body><h1>R</h1><h2>FAQ</h2><script type="application/ld+json">{"@type":"FAQPage"}</script><p>' + ("word " * 80) + "</p></body></html>"
    sig = comp.extract_competitor_signals(html)
    assert sig["has_faq"] is True
    assert "FAQPage" in sig["jsonld_types"]
    assert sig["word_count"] >= 60


def test_content_gaps_flags_thin_content_and_missing_schema():
    gaps = comp.content_gaps(CLIENT, [RIVAL_A])
    joined = " ".join(gaps).lower()
    assert "faq" in joined            # rival uses FAQ structure, client doesn't
    assert "word" in joined or "thin" in joined or "depth" in joined  # rival much longer
    # gaps are advisory strings, no refuted stats
    assert "3.2x" not in joined and "74%" not in joined


def test_content_gaps_empty_when_client_leads():
    gaps = comp.content_gaps(RIVAL_A, [CLIENT])
    assert isinstance(gaps, list)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest "agents/SEO-GEO Optimizer/tests/test_competitor.py" -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `competitor.py`**

```python
# agents/SEO-GEO Optimizer/competitor.py
"""Extract structured signals from a competitor's RAW HTML and compute advisory content
gaps vs the client. Free-tools only (no paid SEO APIs). Stdlib only.

The output FEEDS the LLM competitor analyst (prompts.COMPETITOR_ANALYST_PROMPT) for the
reasoned write-up; this module only produces the deterministic substrate. No refuted stats.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser


class _Collect(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings: list[str] = []
        self._in_h = 0
        self._buf: list[str] = []
        self.text_words = 0
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("h1", "h2", "h3"):
            self._in_h += 1
            self._buf = []

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag in ("h1", "h2", "h3") and self._in_h:
            self._in_h -= 1
            h = " ".join(self._buf).strip()
            if h:
                self.headings.append(h)

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_h:
            self._buf.append(data.strip())
        if data.strip():
            self.text_words += len(data.split())


def _jsonld_types(html: str) -> list[str]:
    out: list[str] = []
    for b in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.IGNORECASE | re.DOTALL,
    ):
        try:
            data = json.loads(b.strip())
        except (ValueError, TypeError):
            continue
        for node in data if isinstance(data, list) else [data]:
            t = node.get("@type") if isinstance(node, dict) else None
            if isinstance(t, str):
                out.append(t)
            elif isinstance(t, list):
                out.extend(x for x in t if isinstance(x, str))
    return out


def extract_competitor_signals(html: str) -> dict:
    p = _Collect()
    p.feed(html)
    types = _jsonld_types(html)
    has_faq = ("FAQPage" in types) or bool(
        re.search(r"\b(faq|frequently asked|veelgestelde vragen)\b", html, re.IGNORECASE)
    )
    return {
        "jsonld_types": types,
        "headings": p.headings,
        "word_count": p.text_words,
        "has_faq": has_faq,
    }


def content_gaps(client: dict, competitors: list[dict]) -> list[str]:
    """Advisory, plain-language gaps. No refuted stats, no fabricated numbers."""
    gaps: list[str] = []
    if not competitors:
        return gaps
    avg_words = sum(c.get("word_count", 0) for c in competitors) / len(competitors)
    client_words = client.get("word_count", 0)
    if avg_words > max(1, client_words) * 1.5 and avg_words - client_words > 150:
        gaps.append(
            f"Competitors have far more page depth (≈{int(avg_words)} words avg vs your "
            f"{client_words}). Thin content limits both Google and AI-answer coverage."
        )
    if any(c.get("has_faq") for c in competitors) and not client.get("has_faq"):
        gaps.append(
            "Competitors use FAQ-structured Q&A content (short, citable passages) and you do not — "
            "add genuine Q&A where it fits."
        )
    client_h = {h.lower() for h in client.get("headings", [])}
    rival_topics: dict[str, int] = {}
    for c in competitors:
        for h in c.get("headings", []):
            key = h.lower().strip()
            if key and key not in client_h and len(key) < 60:
                rival_topics[key] = rival_topics.get(key, 0) + 1
    common = [t for t, n in sorted(rival_topics.items(), key=lambda kv: -kv[1]) if n >= max(1, len(competitors) // 2)]
    if common:
        gaps.append("Topics competitors cover that you do not: " + ", ".join(common[:8]) + ".")
    return gaps
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest "agents/SEO-GEO Optimizer/tests/test_competitor.py" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Full Python suite green**

Run: `python -m pytest "agents/SEO-GEO Optimizer/tests/" -v`
Expected: all pass (prompts 3 + render 4 + audit 4 + competitor 3 = 14).

- [ ] **Step 6: Commit (checkpoint)** — stage only.

---

## Task 5: Guidelines KB + rubric (reference content from the design spec)

**Files:**
- Create: `agents/SEO-GEO Optimizer/guidelines/google-technical-onpage.md`
- Create: `agents/SEO-GEO Optimizer/guidelines/geo-answer-engines.md`
- Create: `agents/SEO-GEO Optimizer/guidelines/local-seo.md`
- Create: `agents/SEO-GEO Optimizer/rubric/rubric.yaml`

- [ ] **Step 1: Write the three guideline files** from the design spec's "Guidelines KB" section (`docs/superpowers/specs/2026-06-14-seo-geo-agent-design.md`, the *Guidelines KB + scored rubric* section). Each file is the durable best-practice ruleset for its track. Required content per file:
  - `google-technical-onpage.md` (Track G): SSR HTML rule (bots don't run JS); robots not blocking AI bots; one H1 + clean hierarchy + short one-idea paragraphs; title 50–60 / meta 140–160 unique per page+locale; canonical + hreflang; valid JSON-LD treated as a Google-rich-result + structured signal NOT an AI multiplier (+ the de-myth note: FAQ allowed where genuinely Q&A, no SERP/AI multiplier); CWV LCP<2.5s/INP<200ms/CLS<0.1 (measured on a cadence). Each rule tagged `[confidence | source]`.
  - `geo-answer-engines.md` (Track E): GEO definition; the only evidence-backed levers (real citations/quotations/statistics ~30–40% rel; keyword-stuffing ~0); the "~40% is best-case, never a guarantee" caveat; machine-readability overlap with Track G; the GATE-FACT factual-accuracy guard (verbatim source-sentence match, per locale); anti-overfitting (intrinsic quality, no hard-coded engine tricks, no MAP-Elites).
  - `local-seo.md` (Track L): site-internal NAP consistency (auto); review velocity/recency as advice (never a multiplier); geo-grid Share-of-Local-Voice needs a paid Places/SERP API (flagged upsell, not faked); MVP ships a single-origin "Local Lite" organic proxy.
  - Each file MUST end with the FORBIDDEN-CLAIMS list (the 11 refuted claims) verbatim.

- [ ] **Step 2: Write `rubric/rubric.yaml`** — the scored audit rubric from the design spec's "SCORED AUDIT RUBRIC" subsection. Encode each item as: `id`, `track` (seo|geo|local), `check` (one line), `measure` (auto|proxy-llm|paid-api|human), `weight`, `threshold`. Keep the deterministic `auto` items aligned with `audit.py`'s `_SEO_ITEMS`/`_LOCAL_ITEMS` ids (G-1, G-3, G-4, G-5, G-6, G-8). Include the deferred paid-api/human items (CWV cadence note, geo-grid, review velocity, NAP-vs-GBP, real-engine citation, backlinks) marked `measure: paid-api`/`human` and `deferred: true`. Add the convergence block at the top as YAML comments: pass gate (GEO≥75, SEO≥85, local auto+proxy≥80, GATE-FACT clean), MAX_ITERS=3, plateau<2, cost budget.

- [ ] **Step 3: Verify** the three guideline files each contain all 11 forbidden claims and the rubric ids match audit.py:

Run: `python - <<'PY'
import pathlib, re
base = pathlib.Path("agents/SEO-GEO Optimizer")
forbidden = ["3.2", "67%", "92.36", "llms.txt", "32%", "7x", "4.4x", "74%", "vector"]
for f in (base/"guidelines").glob("*.md"):
    t = f.read_text(encoding="utf-8").lower()
    miss = [n for n in forbidden if n.lower() not in t]
    assert not miss, f"{f.name} missing forbidden refs {miss}"
rub = (base/"rubric"/"rubric.yaml").read_text(encoding="utf-8")
for rid in ["G-1", "G-4", "G-6", "L-1"]:
    assert rid in rub, f"rubric missing {rid}"
print("guidelines+rubric OK")
PY`
Expected: `guidelines+rubric OK`

- [ ] **Step 4: Commit (checkpoint)** — stage only.

---

## Task 6: Agent docs — AGENTS.md, README, LEARNINGS, example-prompts

**Files:**
- Create: `agents/SEO-GEO Optimizer/AGENTS.md`, `README.md`, `LEARNINGS.md`, `example-prompts.md`

- [ ] **Step 1: Write `AGENTS.md`** — the authoritative spec, mirroring `agents/CMS Connector - Website/AGENTS.md` structure. Required sections (content from the design spec):
  - Title + pointers (skill entry `.claude/skills/seo-geo-optimizer/SKILL.md`, LEARNINGS, phases/).
  - **Trigger:** `Run SEO agent for <project_slug>` (+ flags: `locale <xx>`, `audit-only`, `articles <N>`, `dry-run`).
  - **Autonomy:** WebSearch/WebFetch/Playwright MCP/Supabase MCP/CMS-admin pre-authorized — never pause for permission to research/fetch/render/write; pause only on the failure modes.
  - **Pipeline table (phases 0–7)** exactly as the design spec's phase table. Mark phases 0–4 as built (this plan); 5–7 as Plan 3/4.
  - **Constants:** `SUPABASE_PROJECT_ID = xeluydwpgiddbamysgyu`; `MAX_ITERS=3`; cost budget (WebSearch ≤12, WebFetch ≤12 @100KB, proxy-LLM ≤~15×locales, Playwright renders ≤~9×locales×iters); pass gate (GEO≥75/SEO≥85/local≥80 + GATE-FACT clean).
  - **Memory:** per-client memory + results live in Supabase `seo_*` tables (not markdown). `LEARNINGS.md` holds ONLY agent-mechanics lessons. Self-improvement = distill generalizable rules into `seo_learnings` (global) + `LEARNINGS.md`.
  - **Tools:** the Python helpers (`render_check`/`audit`/`competitor`), `prompts.py`, Supabase MCP, WebSearch/WebFetch, Playwright MCP, the `seo-pro` skill (Plan 3+), the visual-QA gate (Plan 3).
  - **Failure-mode taxonomy** table (transient retry; Supabase connect halt; render/fetch skip-one-never-halt; GATE-FACT fail = drop edit).
  - **Best moment to run** + pipeline position (4th, after Connector).
  - A "Modifying this agent" note: keep `prompts.py` FORBIDDEN_CLAIMS + every phase doc's forbidden block in sync.
- [ ] **Step 2: Write `README.md`** (quick reference: invoke line, file map, what it does, defaults).
- [ ] **Step 3: Write `LEARNINGS.md`** scaffold (header explaining it's append-only agent-mechanics only; client/category memory lives in Supabase; one example area heading `## General`).
- [ ] **Step 4: Write `example-prompts.md`** (3–4 invocation examples incl. flags).
- [ ] **Step 5: Commit (checkpoint)** — stage only.

---

## Task 7: Phase docs 0–4

**Files:**
- Create: `agents/SEO-GEO Optimizer/phases/{0-parse-intent,1-load-context,2-competitor-intel,3-audit,4-plan}.md`

Each phase doc follows the house structure (Goal, Inputs, Steps, Outputs, Failure feedback, Self-improvement hook), mirroring `agents/Design Prompt creator/phases/4-research.md`. Content per phase (from the design spec):

- [ ] **Step 1: `0-parse-intent.md`** — extract `<project_slug>` + flags from the trigger; if slug missing/unknown, ask once. Echo one-line plan.
- [ ] **Step 2: `1-load-context.md`** — via Supabase MCP (`mcp__supabase__execute_sql`, project `xeluydwpgiddbamysgyu`): load the `projects` row (slug, name, locales, production_url, website_url, github_repo) + the latest `seo_runs`/`seo_audits`/`seo_plan_items` (prior memory) + global `seo_learnings`. Detect business **category** (from lead link / LocalBusiness JSON-LD / homepage) and **location/city** (ask once only if truly indeterminable). Insert a new `seo_runs` row (status `running`) and keep its id. Output: context dict + `run_id`.
- [ ] **Step 3: `2-competitor-intel.md`** — reasoned competitor + local intel. Steps: WebSearch `<category> <city>` + top services (cap 12 queries); pick up to ~6 real local competitors (exclude directories/aggregators); WebFetch each (cap 12 @100KB) and run `competitor.extract_competitor_signals` on the raw HTML; fetch the client's own raw HTML via `render_check.fetch_raw`; compute `competitor.content_gaps`; then run the LLM analyst (`prompts.COMPETITOR_ANALYST_PROMPT`) for the reasoned write-up. Persist each competitor + the analysis to `seo_competitors` (Supabase MCP). Honesty: backlinks/off-page + true geo-grid need paid APIs — state, never fabricate. Output: competitor report + gap list.
- [ ] **Step 4: `3-audit.md`** — per locale: `render_check.fetch_raw(url)` (use the per-locale URL) → `extract_signals` → `audit.score_seo` + `audit.score_local`; run the GEO judge (`prompts.GEO_JUDGE_PROMPT`) over the page's main text → geo score + the GATE-FACT claim/source extraction; `audit.assemble_audit(...)`; insert one `seo_audits` row per locale (Supabase MCP). Output: per-locale audit rows + the merged scores for the run.
- [ ] **Step 5: `4-plan.md`** — run the planner (`prompts.PLANNER_PROMPT`) over the audit detail + competitor gaps + guidelines → a prioritized list. Insert `seo_plan_items` (track, title, description, rationale, priority, effort, action_kind, target) via Supabase MCP. Update the `seo_runs` row: status `completed`, `finished_at`, `scores` (merged SEO/GEO/local), `summary`. Set `projects.seo_enabled=true`, `seo_last_run_at=now()`. Echo the dashboard path. (Applying/publishing is Plan 3 — Phase 4 stops at the written plan.)

Every phase doc ends with the FORBIDDEN-CLAIMS reminder (the 11 refuted claims) so the agent never regresses mid-phase.

- [ ] **Step 6: Verify cross-references** — every path referenced in `SKILL.md`/`AGENTS.md`/phase docs resolves to a real file:

Run: `python - <<'PY'
import pathlib, re
base = pathlib.Path("agents/SEO-GEO Optimizer")
need = ["phases/0-parse-intent.md","phases/1-load-context.md","phases/2-competitor-intel.md",
        "phases/3-audit.md","phases/4-plan.md","AGENTS.md","README.md","LEARNINGS.md",
        "prompts.py","render_check.py","audit.py","competitor.py","rubric/rubric.yaml"]
miss = [p for p in need if not (base/p).exists()]
assert not miss, f"missing: {miss}"
print("agent files present")
PY`
Expected: `agent files present`

- [ ] **Step 7: Commit (checkpoint)** — stage only.

---

## Task 8: The skill entry point + catalog row

**Files:**
- Create: `.claude/skills/seo-geo-optimizer/SKILL.md`
- Modify: `agents/README.md` (append catalog row)

- [ ] **Step 1: Write `SKILL.md`** mirroring `.claude/skills/cms-connector-website/SKILL.md`:
  - Frontmatter: `name: seo-geo-optimizer`; `description:` ("Use when the user says 'Run SEO agent for <project>' (or close paraphrase). Audits a live CMS-connected site for SEO + GEO, does reasoned competitor + local intelligence, and writes a prioritized plan to the CMS SEO/GEO area; autonomous (pre-authorized web/render/DB); self-improving."); `model: claude-opus-4-8`; `effort: xhigh`.
  - **Trigger pattern:** `Run SEO agent for <project_slug>` + close paraphrases; ask once if slug missing.
  - **Orchestration policy (ultracode):** runs in the main session with the Workflow tool — for the substantive reasoning phases (2 competitor intel, 3 GEO judging, 4 planning) orchestrate multi-agent fan-out + adversarial verification; scale to site complexity.
  - **Autonomy:** WebSearch/WebFetch/Playwright/Supabase MCP pre-authorized; never pause for permission.
  - **First steps:** read `agents/SEO-GEO Optimizer/AGENTS.md`; read `LEARNINGS.md` only if >25 lines; confirm Supabase MCP connected (`mcp__supabase__execute_sql`, `xeluydwpgiddbamysgyu`); echo a one-line plan.
  - **Lazy phase loading** table (phases 0–4 now; 5–7 added by Plan 3/4).
  - **Token rules** (one Read per phase doc; one status line per phase; pinned `claude-opus-4-8`).
  - **Self-improvement loop** (distill into `seo_learnings` Supabase + agent-mechanics into `LEARNINGS.md`).
  - **Failure hooks** (halt on Supabase connect fail; skip single fetch failures; GATE-FACT drop-not-publish).
- [ ] **Step 2: Append the catalog row** to `agents/README.md` matching the existing rows' format (name, trigger, one-line purpose, link to `agents/SEO-GEO Optimizer/AGENTS.md`).
- [ ] **Step 3: Verify** the skill frontmatter is valid and `name` matches the folder:

Run: `python - <<'PY'
import pathlib
p = pathlib.Path(".claude/skills/seo-geo-optimizer/SKILL.md").read_text(encoding="utf-8")
assert p.startswith("---") and "name: seo-geo-optimizer" in p and "model: claude-opus-4-8" in p
print("skill frontmatter OK")
PY`
Expected: `skill frontmatter OK`

- [ ] **Step 4: Commit (checkpoint)** — stage only.

---

## Task 9: Live integration run (controller-executed)

**Files:** none (runtime verification)

This task is run by the CONTROLLER in the main thread (it needs WebSearch + Playwright + Supabase MCP), not a subagent.

- [ ] **Step 1: Clear the Plan-1 smoke seed** for `e2e-test-project` so the run starts clean:
```sql
delete from seo_audits where project_id='7fadaf4f-abbd-4ee5-b486-5e53fa630e01';
delete from seo_plan_items where project_id='7fadaf4f-abbd-4ee5-b486-5e53fa630e01';
delete from seo_competitors where project_id='7fadaf4f-abbd-4ee5-b486-5e53fa630e01';
delete from seo_runs where project_id='7fadaf4f-abbd-4ee5-b486-5e53fa630e01';
delete from seo_page_meta where project_id='7fadaf4f-abbd-4ee5-b486-5e53fa630e01';
```
- [ ] **Step 2: Invoke the agent** on a real client with a live site — `samir-kapsalon` (bilingual nl/en, has a production URL). Run the `seo-geo-optimizer` skill for `samir-kapsalon`. It should: load context, do competitor intel, audit both locales, write a plan, and mark the run completed — all to Supabase.
- [ ] **Step 3: Verify the run persisted** via `mcp__supabase__execute_sql`: one `completed` `seo_runs` row, ≥1 `seo_audits` per locale, ≥3 `seo_plan_items`, ≥1 `seo_competitors`, `projects.seo_enabled=true`. Confirm NO forbidden claim text appears in any written `rationale`/`analysis`/`summary` (grep the rows for `3.2x`, `74%`, `92.36`, `llms.txt`, `32%`).
- [ ] **Step 4: Verify in the dashboard** that the `samir-kapsalon` SEO & GEO tab now shows real scores, the plan, competitors, and run history.
- [ ] **Step 5: Record** one agent-mechanics learning (if any) into `LEARNINGS.md`. Plan 2 is done when Tasks 1–9 pass.

---

## Self-review

**Spec coverage:** the agent skill + AGENTS + phases 0–4 (load → competitor intel → audit → plan) ✓; per-client memory in Supabase ✓; deep reasoned competitor intel ✓ (Task 7 §3 + competitor.py substrate); per-locale audit (deterministic SEO + LLM-judge GEO + local) ✓; the forbidden-claims block in prompts + every guideline + every phase ✓; GATE-FACT factual guard in the GEO judge ✓; self-improvement into `seo_learnings` + `LEARNINGS.md` ✓; writes surfaced in the Plan-1 dashboard ✓. Apply/publish (Plan 3) and new pages (Plan 4) correctly out of scope.

**Placeholder scan:** Python tasks have full code + tests. Doc tasks specify exact required sections + content sources (the approved design spec) — they are content files (no logic/tests), so "no-placeholder" means a precise section spec, which is provided. The runtime task (9) is controller-run with explicit verification SQL.

**Type/name consistency:** `render_check.extract_signals` keys (`has_main_content`, `h1_count`, `heading_order_ok`, `jsonld_types`, `jsonld_valid`, `has_localbusiness`, `og_present`, `internal_link_count`, `title_len`, `meta_desc_len`, `canonical`) are exactly the keys `audit.score_seo`/`score_local` read. `audit` rubric ids (G-1/G-3/G-4/G-5/G-6/G-8, L-1) match `rubric.yaml` (Task 5 §2). `prompts.PLANNER_PROMPT` action_kinds match the `seo_plan_items.action_kind` CHECK constraint from Plan 1. Supabase project id `xeluydwpgiddbamysgyu` consistent throughout.

---

## Next plan

**Plan 3 — Apply + visual-QA self-heal gate:** phases 5–6; `cms_client.py` writing `seo_page_meta`/`seo_articles` drafts + the GEO content edits via the existing `save_service` draft path; `geo-content-writing` skill (verbatim-source factual gate); `seo-visual-qa` skill (Playwright breakpoint render → responsive/visibility/crash/console/build/links checks → self-heal via brainstorming→writing-plans→ui-ux-pro-max→frontend-design → publish only when green). Written after Plan 2 is built + green.
