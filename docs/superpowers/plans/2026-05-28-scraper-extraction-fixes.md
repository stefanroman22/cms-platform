# Scraper Extraction Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Google Maps scraper so it reliably extracts opening hours, the 3 newest text reviews (≥4 stars, original language, no duplicates), an always-English category, and the full About-section attributes.

**Architecture:** All DOM access stays in `google_maps.py` + `selectors.py`. Each fix splits a small **pure** parsing/classification helper (unit-tested offline) from the thin Playwright I/O (verified with one live `scrape-url` run). Selectors are updated to match the *current* Google Maps DOM captured during debugging on 2026-05-28.

**Tech Stack:** Python 3.13, Playwright (async), Pydantic v2, Typer, pytest + pytest-asyncio. Tests run from `scraper/` via the project venv.

---

## Root-Cause Summary (from live-DOM investigation, 2026-05-28)

Captured against the Lekkeristic place page with `?hl=en` forced.

1. **Opening hours empty** — `PLACE_HOURS_BUTTON = 'div[data-item-id="oh"]...'` no longer exists. The only `data-item-id`s on the page are `address`, `authority`, `oloc`. So `_extract_opening_hours` bails at the `count()==0` check. The hours actually live in:
   - 7 buttons `button[jsaction*="openhours"]` each with `data-value="Thursday, 12–7 pm"` (visibility-independent → robust), and
   - a `<table class="eK4R0e">` whose rows are `td.ylH6lf` (day) + `td.mxowUb` (hours). The table has **no** `aria-label`, so the old `PLACE_HOURS_TABLE = 'table[aria-label*="hours"]'` never matched.

2. **Reviews** —
   - **Duplicates:** `REVIEW_CARD = 'div[data-review-id], div[jsaction*="reviewerLink"]'` matches the outer card *and* a nested inner `div[data-review-id]` → every review counted twice (20 handles for 10 reviews). The outer card is `div[data-review-id][aria-label="<author>"]`; the inner wrapper has no `aria-label`. Selecting `div[data-review-id][aria-label]` yields 10 distinct cards.
   - **Not newest:** `_extract_reviews` never sets Google's sort; it sorts loaded cards by `(has_text, rating)`. There is a `button[aria-label="Sort reviews"]` opening a menu of `div[role="menuitemradio"]` with text "Most relevant / Newest / Highest rating / Lowest rating".
   - **No ≥4 filter / no text requirement.**
   - **Translation:** reviews in other languages render translated to the UI locale; the original is revealed by a button `aria-label="Translated by Google ・ See original (Hungarian)"`. The visible text span is `span.wiI7pd` inside `div.MyEned`.

3. **Category Dutch** — direct-url mode never sets `hl`. The user URL has no `hl`, and the browser-context `locale` (Accept-Language) is not authoritative for Google Maps; geo defaults the place page to Dutch. Search mode works only because the search URL carries `hl=en` and the cookie persists for same-context place visits. Forcing `?hl=en` yielded category "Grocery store" (English).

4. **About empty** — the About *tab button* selector is correct and the panel exists as `div[role="region"][aria-label^="About "]` with `h2` section headings and `ul.ZQ6we > li.hpLkke`. Two bugs: (a) the old parser falls back to the *first* `div[role="region"]` ("Available search options for this area") when the About region isn't ready, returning `{}`; (b) the available/negated flag is read from the visible text ("Delivery") but the negation marker lives only in the inner `span[aria-label]` ("No delivery"), so negatives would be mis-recorded as available.

**Decision (confirmed with user):** reviews must have text — skip rating-only reviews and keep scanning newest-first until 3 reviews with text **and** rating ≥4 are collected.

---

## File Structure

- **Modify** `scraper/src/scraper/selectors.py` — update hours/review selectors; add sort + see-original + about-panel selectors.
- **Modify** `scraper/src/scraper/google_maps.py` — new pure helpers (`_with_hl`, `_parse_hours_pairs`, `_parse_star_rating`, `_about_available`, `_group_about_items`); rewrite `_extract_opening_hours`, `_extract_reviews` (+ `_sort_reviews_newest`, `_review_rating`, `_expand_review`), `_extract_about_attributes`; force `hl` in `_scrape_one_place`.
- **Modify** `scraper/tests/test_google_maps_pure.py` — add tests for the new pure helpers; replace the stale `test_reviews_sort_prefers_text_then_rating`; update the `review_limit` whitelist comment.
- **Verify (no code)** `scraper/leads-dry-run.json` / `lead-single.json` via a live `scrape-url` run.

All commits run from the repo root. Tests run from `scraper/` using the project venv: `cd scraper && ../backend/venv/Scripts/python.exe -m pytest ...` — **confirm the correct interpreter in Task 0**.

---

### Task 0: Establish the test runner

**Files:** none (environment check)

- [ ] **Step 1: Find the Python that has the scraper deps installed**

Run (from repo root):
```bash
cd scraper && python -m pytest tests/test_google_maps_pure.py -q 2>&1 | tail -5
```
Expected: PASS (all existing pure tests pass). If `ModuleNotFoundError` for `playwright`/`typer`/`loguru`, retry with the scraper venv, e.g. `./.venv/Scripts/python.exe -m pytest ...` or `../backend/venv/Scripts/python.exe -m pytest ...`. Record the working interpreter; use it as `PYTEST` for every later step.

- [ ] **Step 2: Confirm Playwright Chromium is installed (needed only for the live verification task)**

Run:
```bash
cd scraper && <PYTEST_PYTHON> -m playwright install --dry-run chromium 2>&1 | tail -3
```
Expected: reports chromium present, or install it with `<PYTEST_PYTHON> -m playwright install chromium`.

---

### Task 1: Force English UI via `hl` (fixes Dutch category)

**Files:**
- Modify: `scraper/src/scraper/google_maps.py` (add `_with_hl`; use it in `_scrape_one_place`)
- Test: `scraper/tests/test_google_maps_pure.py`

- [ ] **Step 1: Write the failing test**

Add to `test_google_maps_pure.py` (and add `_with_hl` to the import from `scraper.google_maps`):
```python
def test_with_hl_adds_param_when_absent():
    out = _with_hl("https://www.google.com/maps/place/X/data=!1s0x1:0x2", "en")
    assert "hl=en" in out
    assert out.startswith("https://www.google.com/maps/place/X/data=!1s0x1:0x2")


def test_with_hl_overrides_existing_hl_and_keeps_other_params():
    out = _with_hl("https://www.google.com/maps/place/X/data=!1s0x1?hl=nl&entry=ttu", "en")
    assert "hl=en" in out
    assert "hl=nl" not in out
    assert "entry=ttu" in out


def test_with_hl_preserves_data_path_segment():
    # The Google `data=!...` blob lives in the PATH, not the query — must survive.
    out = _with_hl("https://www.google.com/maps/place/Foo/data=!4m6!3m5!1s0xabc:0xdef", "en")
    assert "data=!4m6!3m5!1s0xabc:0xdef" in out
    assert out.endswith("hl=en")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scraper && <PYTEST_PYTHON> -m pytest tests/test_google_maps_pure.py -k with_hl -v`
Expected: FAIL — `ImportError: cannot import name '_with_hl'`.

- [ ] **Step 3: Implement `_with_hl`**

In `google_maps.py`, add to the imports block near the top:
```python
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
```
Add this helper in the "Query building" region (near `_search_url`):
```python
def _with_hl(url: str, language: str) -> str:
    """Force the Google Maps UI language via the `hl` query param so place
    pages render in `language` (category, weekday names, attribute labels)
    instead of geo-defaulting to the local language (e.g. Dutch in NL).
    Overrides any existing hl; leaves the `data=!...` path blob untouched."""
    parts = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "hl"]
    query.append(("hl", language))
    return urlunparse(parts._replace(query=urlencode(query)))
```

- [ ] **Step 4: Use it when visiting a place page**

In `_scrape_one_place`, change the navigation line:
```python
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
```
to:
```python
        await page.goto(_with_hl(url, params.language), wait_until="domcontentloaded", timeout=20_000)
```

- [ ] **Step 5: Run to verify pass**

Run: `cd scraper && <PYTEST_PYTHON> -m pytest tests/test_google_maps_pure.py -k with_hl -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add scraper/src/scraper/google_maps.py scraper/tests/test_google_maps_pure.py
git commit -m "fix(scraper): force hl=<language> on place visits so category is English"
```

---

### Task 2: Opening hours from the openhours copy-buttons (+ table fallback)

**Files:**
- Modify: `scraper/src/scraper/selectors.py`
- Modify: `scraper/src/scraper/google_maps.py` (`_parse_hours_pairs`, rewrite `_extract_opening_hours`)
- Test: `scraper/tests/test_google_maps_pure.py`

- [ ] **Step 1: Update selectors**

In `selectors.py`, replace the two hours lines:
```python
PLACE_HOURS_BUTTON = 'div[data-item-id="oh"] button, button[data-item-id="oh"]'
PLACE_HOURS_TABLE = 'table[aria-label*="hours"], table[aria-label*="openingstijden"]'
```
with:
```python
# Hours: each day is a "copy open hours" button carrying data-value="Day, hours"
# (present in the DOM even when the week dropdown is visually collapsed).
PLACE_HOURS_COPY_BUTTONS = 'button[jsaction*="openhours"][data-value]'
# FRAGILE fallback — weekday table when copy-buttons are absent.
PLACE_HOURS_TABLE = "table.eK4R0e"
```

- [ ] **Step 2: Write the failing test**

Add to `test_google_maps_pure.py` (import `_parse_hours_pairs`):
```python
def test_parse_hours_pairs_basic():
    out = _parse_hours_pairs(["Thursday, 12–7 pm", "Monday, Closed", "Saturday, 9 am–5 pm"])
    assert out["Thursday"] == "12–7 pm"
    assert out["Monday"] == "Closed"
    assert out["Saturday"] == "9 am–5 pm"
    # Unspecified days keep the skeleton placeholder.
    assert out["Sunday"] == "___"


def test_parse_hours_pairs_split_daily_hours_keeps_full_value():
    # The value itself contains a comma; only the FIRST comma splits day vs hours.
    out = _parse_hours_pairs(["Monday, 9 am–12 pm, 1–5 pm"])
    assert out["Monday"] == "9 am–12 pm, 1–5 pm"


def test_parse_hours_pairs_returns_none_when_nothing_maps():
    assert _parse_hours_pairs([]) is None
    assert _parse_hours_pairs(["garbage with no comma"]) is None
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd scraper && <PYTEST_PYTHON> -m pytest tests/test_google_maps_pure.py -k parse_hours_pairs -v`
Expected: FAIL — `ImportError: cannot import name '_parse_hours_pairs'`.

- [ ] **Step 4: Implement `_parse_hours_pairs`**

In `google_maps.py`, add near `_default_opening_hours`:
```python
def _parse_hours_pairs(pairs: list[str]) -> dict[str, str] | None:
    """Map ['Thursday, 12–7 pm', 'Monday, Closed', ...] into the 7-day
    skeleton. Each entry is 'Day, hours' split on the FIRST ', ' so split
    daily hours ('9 am–12 pm, 1–5 pm') survive intact. Returns None when no
    weekday matched (so the caller can fall back to the placeholder skeleton)."""
    skeleton = _default_opening_hours()
    matched = False
    for raw in pairs:
        if not raw or ", " not in raw:
            continue
        day, hours = raw.split(", ", 1)
        day, hours = day.strip(), hours.strip()
        for canon in skeleton:
            if canon.lower() == day.lower():
                skeleton[canon] = hours
                matched = True
                break
    return skeleton if matched else None
```

- [ ] **Step 5: Rewrite `_extract_opening_hours`**

Replace the whole `_extract_opening_hours` function body with:
```python
async def _extract_opening_hours(page: Page) -> dict[str, str] | None:
    """Read the 7-day hours. Primary source is the per-day 'copy open hours'
    buttons (data-value='Day, hours') which exist in the DOM regardless of the
    week dropdown's collapsed/expanded state. Falls back to the weekday table."""
    # Primary: copy-buttons carry a visibility-independent data-value.
    try:
        btns = await page.locator(selectors.PLACE_HOURS_COPY_BUTTONS).element_handles()
        pairs = [dv for b in btns if (dv := await b.get_attribute("data-value"))]
        parsed = _parse_hours_pairs(pairs)
        if parsed:
            return parsed
    except Exception:
        pass
    # Fallback: weekday table — first cell is the day, second the hours.
    try:
        rows = await page.locator(f"{selectors.PLACE_HOURS_TABLE} tr").element_handles()
        pairs = []
        for r in rows:
            cells = await r.query_selector_all("td")
            if len(cells) >= 2:
                day = (await cells[0].inner_text()).strip()
                hours = (await cells[1].inner_text()).strip()
                if day and hours:
                    pairs.append(f"{day}, {hours}")
        return _parse_hours_pairs(pairs)
    except Exception:
        return None
```

- [ ] **Step 6: Run to verify pass**

Run: `cd scraper && <PYTEST_PYTHON> -m pytest tests/test_google_maps_pure.py -k "parse_hours_pairs or opening_hours" -v`
Expected: PASS (3 new + `test_default_opening_hours_has_seven_days`).

- [ ] **Step 7: Commit**

```bash
git add scraper/src/scraper/selectors.py scraper/src/scraper/google_maps.py scraper/tests/test_google_maps_pure.py
git commit -m "fix(scraper): extract opening hours from openhours copy-buttons"
```

---

### Task 3: About attributes — correct region + correct available/negated flag

**Files:**
- Modify: `scraper/src/scraper/selectors.py`
- Modify: `scraper/src/scraper/google_maps.py` (`_about_available`, `_group_about_items`, rewrite `_extract_about_attributes`)
- Test: `scraper/tests/test_google_maps_pure.py`

- [ ] **Step 1: Add an About-panel selector**

In `selectors.py`, under the About section, add:
```python
# The opened About tab renders a region whose aria-label starts with "About".
ABOUT_PANEL = 'div[role="region"][aria-label^="About"]'
```

- [ ] **Step 2: Write the failing tests**

Add to `test_google_maps_pure.py` (import `_about_available`, `_group_about_items`):
```python
def test_about_available_from_aria():
    assert _about_available("Has in-store shopping") is True
    assert _about_available("Accepts credit cards") is True
    assert _about_available("Good for quick visit") is True
    assert _about_available("No delivery") is False
    assert _about_available("No toilet") is False


def test_group_about_items_groups_by_section_and_flags():
    items = [
        {"section": "Service options", "label": "In-store shopping", "aria": "Has in-store shopping"},
        {"section": "Service options", "label": "Delivery", "aria": "No delivery"},
        {"section": "Amenities", "label": "Toilet", "aria": "No toilet"},
    ]
    out = _group_about_items(items)
    assert out["Service options"]["In-store shopping"] is True
    assert out["Service options"]["Delivery"] is False
    assert out["Amenities"]["Toilet"] is False


def test_group_about_items_skips_empty_labels():
    out = _group_about_items([{"section": "X", "label": "", "aria": "Has x"}])
    assert out == {}
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd scraper && <PYTEST_PYTHON> -m pytest tests/test_google_maps_pure.py -k "about" -v`
Expected: FAIL — `ImportError: cannot import name '_about_available'`.

- [ ] **Step 4: Implement the pure helpers**

In `google_maps.py`, add near `_extract_about_attributes`:
```python
def _about_available(aria: str) -> bool:
    """Google encodes a negated attribute as 'No <thing>' in the attribute
    span's aria-label (e.g. 'No delivery'). Everything else ('Has X',
    'Accepts X', 'Good for X') means the attribute is available."""
    return re.match(r"^no\b", (aria or "").strip(), re.IGNORECASE) is None


def _group_about_items(items: list[dict[str, Any]]) -> dict[str, dict[str, bool]]:
    """Group flat About items [{section,label,aria}] into
    {section: {label: available_bool}}. Empty labels are dropped."""
    out: dict[str, dict[str, bool]] = {}
    for it in items:
        label = (it.get("label") or "").strip()
        if not label:
            continue
        section = (it.get("section") or "Other").strip() or "Other"
        out.setdefault(section, {})[label] = _about_available(it.get("aria") or label)
    return out
```

- [ ] **Step 5: Rewrite `_extract_about_attributes`**

Replace the whole function with:
```python
_ABOUT_EXTRACT_JS = """() => {
    const panel = document.querySelector('div[role="region"][aria-label^="About"]');
    if (!panel) return [];
    const items = [];
    let section = "Other";
    for (const node of panel.querySelectorAll('h2, ul li')) {
        if (node.tagName.toLowerCase() === 'h2') {
            section = (node.innerText || '').trim() || section;
            continue;
        }
        const span = node.querySelector('span[aria-label]');
        if (!span) continue;
        const label = (span.innerText || '').trim();
        if (!label) continue;
        items.push({ section, label, aria: span.getAttribute('aria-label') || label });
    }
    return items;
}"""


async def _extract_about_attributes(page: Page) -> dict[str, dict[str, bool]]:
    """Open the About tab and read attributes grouped by section heading.
    Returns {} when the tab is absent or the panel never renders.

    Shape: {"Service options": {"In-store shopping": True, "Delivery": False}, ...}
    """
    try:
        btn = page.locator(selectors.ABOUT_TAB_BUTTON).first
        if await btn.count() == 0:
            return {}
        await btn.click(timeout=2000)
        # Wait for the *About* region specifically — never fall back to an
        # arbitrary region (the first region on the page is the map search box).
        await page.wait_for_selector(selectors.ABOUT_PANEL, timeout=4000)
        items = await page.evaluate(_ABOUT_EXTRACT_JS)
        return _group_about_items(items or [])
    except Exception:
        return {}
```

- [ ] **Step 6: Run to verify pass**

Run: `cd scraper && <PYTEST_PYTHON> -m pytest tests/test_google_maps_pure.py -k "about" -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add scraper/src/scraper/selectors.py scraper/src/scraper/google_maps.py scraper/tests/test_google_maps_pure.py
git commit -m "fix(scraper): read About panel correctly and flag negated attributes"
```

---

### Task 4: Reviews — newest-first, ≥4 stars, text required, original language, no dupes

**Files:**
- Modify: `scraper/src/scraper/selectors.py`
- Modify: `scraper/src/scraper/google_maps.py` (`_parse_star_rating`, `_sort_reviews_newest`, `_review_rating`, `_expand_review`, rewrite `_extract_reviews`)
- Test: `scraper/tests/test_google_maps_pure.py`

- [ ] **Step 1: Update review selectors**

In `selectors.py`, replace the Reviews block:
```python
REVIEW_CARD = 'div[data-review-id], div[jsaction*="reviewerLink"]'
REVIEW_AUTHOR = "div.d4r55"  # FRAGILE
REVIEW_RATING = 'span[role="img"][aria-label*="star"], span[role="img"][aria-label*="ster"]'
REVIEW_RELATIVE_DATE = "span.rsqaWe"  # FRAGILE
REVIEW_TEXT = "span.wiI7pd, div[data-review-id] span[jscontroller]"
```
with:
```python
# Outer review card only — it carries BOTH data-review-id and aria-label
# (the author name). The inner content wrapper also has data-review-id but no
# aria-label, so requiring aria-label de-duplicates each review.
REVIEW_CARD = "div[data-review-id][aria-label]"
REVIEW_AUTHOR = "div.d4r55"  # FRAGILE fallback; author is normally the card aria-label
REVIEW_RATING = 'span[role="img"][aria-label*="star"], span[role="img"][aria-label*="ster"]'
REVIEW_RELATIVE_DATE = "span.rsqaWe"  # FRAGILE
REVIEW_TEXT = "span.wiI7pd"
# Sort control + "Newest" option.
REVIEW_SORT_BUTTON = 'button[aria-label="Sort reviews"], button[aria-label*="Sort"]'
REVIEW_SORT_MENUITEM = '[role="menuitemradio"]'
# Reveal the review's original language (Google auto-translates to the hl locale).
REVIEW_SEE_ORIGINAL = 'button[aria-label*="See original"]'
```

- [ ] **Step 2: Write the failing test for `_parse_star_rating`; replace the stale sort test**

In `test_google_maps_pure.py`, **delete** `test_reviews_sort_prefers_text_then_rating` (lines defining it) and add (import `_parse_star_rating`):
```python
def test_parse_star_rating():
    assert _parse_star_rating("5 stars") == 5
    assert _parse_star_rating("1 star") == 1
    assert _parse_star_rating("4,0 sterren") == 4  # NL aria fallback
    assert _parse_star_rating(None) is None
    assert _parse_star_rating("no number here") is None
```
Also update the whitelist comment in `test_every_scrape_params_field_is_referenced_in_engine` from "no-op since the top-3-by-stars rewrite" to "no-op since reviews are fixed at the 3 newest ≥4-star reviews".

- [ ] **Step 3: Run to verify it fails**

Run: `cd scraper && <PYTEST_PYTHON> -m pytest tests/test_google_maps_pure.py -k parse_star_rating -v`
Expected: FAIL — `ImportError: cannot import name '_parse_star_rating'`.

- [ ] **Step 4: Implement `_parse_star_rating`**

In `google_maps.py`, add near `_parse_rating`:
```python
def _parse_star_rating(aria: str | None) -> int | None:
    """Pull the integer star count from a review star aria-label such as
    '5 stars' / '1 star' / '4,0 sterren'. Returns None if no digit present."""
    if not aria:
        return None
    m = re.search(r"(\d+)", aria)
    return int(m.group(1)) if m else None
```

- [ ] **Step 5: Add the review-interaction helpers**

In `google_maps.py`, replace `_review_from_card` (no longer used) and the old `_extract_reviews` with the following set. Keep `_card_text` and `_open_reviews_tab` as-is.
```python
async def _sort_reviews_newest(page: Page) -> None:
    """Switch the reviews sort to 'Newest'. Best-effort: if the control or
    option is missing we leave the default order (caller still filters)."""
    try:
        await page.locator(selectors.REVIEW_SORT_BUTTON).first.click(timeout=2000)
        await (
            page.locator(selectors.REVIEW_SORT_MENUITEM)
            .filter(has_text="Newest")
            .first.click(timeout=2000)
        )
        # The pane re-renders client-side; give it a beat to reorder.
        await page.wait_for_timeout(1200)
    except Exception:
        logger.debug("could not set reviews sort to Newest")


async def _review_rating(card: ElementHandle) -> int | None:
    try:
        star = await card.query_selector(selectors.REVIEW_RATING)
        if star is None:
            return None
        return _parse_star_rating(await star.get_attribute("aria-label"))
    except Exception:
        return None


async def _expand_review(card: ElementHandle) -> None:
    """Reveal the original language (undo Google's auto-translation) and
    expand truncated text, so the stored review is the full original text."""
    try:
        see_original = await card.query_selector(selectors.REVIEW_SEE_ORIGINAL)
        if see_original is not None:
            await see_original.click(timeout=1500)
    except Exception:
        pass
    # Click a "More"/"See more" button by text — class is volatile.
    try:
        await card.evaluate(
            """(el) => {
                const b = [...el.querySelectorAll('button')].find((x) => {
                    const t = (x.getAttribute('aria-label') || x.innerText || '')
                        .trim().toLowerCase();
                    return t === 'more' || t === 'see more';
                });
                if (b) b.click();
            }"""
        )
    except Exception:
        pass


async def _extract_reviews(page: Page, limit: int) -> list[dict[str, Any]]:
    """Return the 3 newest reviews that have text and a rating >= 4, in
    original language, de-duplicated by review id. `limit` is ignored (kept
    for API compatibility) — the spec fixes the count at 3."""
    if not await _open_reviews_tab(page):
        return []
    await _sort_reviews_newest(page)

    cards = await page.locator(selectors.REVIEW_CARD).element_handles()
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for card in cards:
        rid = await card.get_attribute("data-review-id")
        if rid:
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
        rating = await _review_rating(card)
        if rating is None or rating < 4:
            continue
        await _expand_review(card)
        text = await _card_text(card, selectors.REVIEW_TEXT)
        if not text:
            continue  # spec: skip rating-only reviews
        author = await card.get_attribute("aria-label") or await _card_text(
            card, selectors.REVIEW_AUTHOR
        )
        selected.append(
            {
                "author": author,
                "text": text,
                "relative_date": await _card_text(card, selectors.REVIEW_RELATIVE_DATE),
                "rating": rating,
            }
        )
        if len(selected) >= 3:
            break
    return selected
```

- [ ] **Step 6: Remove the now-unused `import re` shadow inside `_review_from_card`**

`_review_from_card` is deleted in Step 5; confirm there is no remaining reference to it (`grep -n "_review_from_card" scraper/src/scraper/google_maps.py` → no matches). The module already imports `re` at the top, so the deleted inner `import re` is gone with the function.

- [ ] **Step 7: Run to verify pass**

Run: `cd scraper && <PYTEST_PYTHON> -m pytest tests/test_google_maps_pure.py -v`
Expected: PASS (all, including new `test_parse_star_rating`; the deleted sort test no longer collected).

- [ ] **Step 8: Commit**

```bash
git add scraper/src/scraper/selectors.py scraper/src/scraper/google_maps.py scraper/tests/test_google_maps_pure.py
git commit -m "fix(scraper): reviews = 3 newest >=4-star with text, original language, deduped"
```

---

### Task 5: Full offline test sweep

**Files:** none (verification)

- [ ] **Step 1: Run the whole pure-test suite**

Run: `cd scraper && <PYTEST_PYTHON> -m pytest tests/ -q`
Expected: PASS. In particular `test_every_scrape_params_field_is_referenced_in_engine` still passes (`language` is referenced via `_with_hl(url, params.language)` and `_new_context`; `review_limit` remains whitelisted).

- [ ] **Step 2: Lint/format check (match repo tooling)**

Run: `cd scraper && <PYTEST_PYTHON> -m ruff check src/scraper/google_maps.py src/scraper/selectors.py` (skip if ruff isn't configured here; otherwise fix reported issues).
Expected: no errors.

---

### Task 6: Live end-to-end verification against Lekkeristic

**Files:** none (manual live run; the user must run this — it needs a real browser/network)

- [ ] **Step 1: Run a single-URL dry-run, non-headless, against the reported business**

Run (from `scraper/`, using the scraper venv):
```bash
<PYTEST_PYTHON> -m scraper.cli scrape-url \
  "https://www.google.com/maps/place/Lekkeristic+Magazin+romanesc+si+maghiar+-+Magyar+es+roman+bolt/@52.1907099,5.963634,17z/data=!4m16!1m9!3m8!1s0x47c7b913f52b9671:0xf9f9170c363873d9!2sLekkeristic+Magazin+romanesc+si+maghiar+-+Magyar+es+roman+bolt!8m2!3d52.1907099!4d5.9662089!9m1!1b1!16s%2Fg%2F11s0vd_x71!3m5!1s0x47c7b913f52b9671:0xf9f9170c363873d9!8m2!3d52.1907099!4d5.9662089!16s%2Fg%2F11s0vd_x71?entry=ttu" \
  --dry-run --no-supabase --no-headless --out ./lead-single.json
```
Note: invoke the CLI however the project runs it (e.g. `python -m scraper.cli`, an installed `scraper` entry point, or `python src/scraper/cli.py`). Confirm the working invocation, then use it.

- [ ] **Step 2: Inspect the output and assert every fixed field**

Open `scraper/lead-single.json` and confirm:
- `category` == "Grocery store" (English, **not** Dutch like "Supermarkt").
- `opening_hours` has real values, e.g. `"Thursday": "12–7 pm"`, `"Saturday": "9 am–5 pm"`, `"Monday": "Closed"` — not all `"___"`.
- `extra.attributes` is populated, e.g. `extra.attributes["Service options"]["In-store shopping"] == true` and `["Service options"]["Delivery"] == false` and `["Amenities"]["Toilet"] == false`.
- `reviews` has up to 3 entries, each with non-empty `text`, `rating >= 4`, distinct `author`/text (no duplicate), and the text reads in its original language (Hungarian/Romanian where applicable), **not** an English translation.

If `opening_hours` is empty: the place loaded a layout where the copy-buttons aren't present — capture `button[jsaction*="openhours"]` / `table.eK4R0e` presence with `--no-headless` devtools and adjust `PLACE_HOURS_COPY_BUTTONS` accordingly, then re-run. If `reviews` is empty: confirm the Reviews tab opened and "Newest" was clickable (text may differ if `hl` wasn't applied — Task 1 must be in place).

- [ ] **Step 3: (Optional) second business to guard against per-page luck**

Re-run Step 1 against one more Google Maps place URL of a different category and re-check the same fields.

- [ ] **Step 4: Commit any selector adjustments discovered during verification**

```bash
git add scraper/src/scraper/selectors.py scraper/src/scraper/google_maps.py
git commit -m "fix(scraper): adjust selectors per live verification"
```
(Skip if no changes were needed.)

---

## Self-Review

**Spec coverage:**
- Hours not found → Task 2 (copy-buttons + table fallback). ✓
- 3 newest reviews, ≥4 stars, skip <4 → Task 4 (`_sort_reviews_newest` + rating filter + cap 3). ✓
- No duplicate reviews → Task 4 (`REVIEW_CARD = div[data-review-id][aria-label]` + `seen_ids`). ✓
- Original language, no translation → Task 4 (`_expand_review` clicks "See original"). ✓
- Category always English → Task 1 (`_with_hl`). ✓
- About filled with all details → Task 3 (correct region wait + grouped extraction + correct negation flag). ✓
- User decision "require text" → Task 4 (`if not text: continue`). ✓

**Placeholder scan:** No "TBD"/"handle edge cases"/"similar to" — every code step shows full code. The only text-matched selector ("More") is implemented concretely via in-page `querySelectorAll('button')` text matching, not a guessed class. Live verification (Task 6) is explicitly the user's to run because it needs a real browser.

**Type consistency:** Helper names are used identically across tasks: `_with_hl`, `_parse_hours_pairs`, `_about_available`, `_group_about_items`, `_parse_star_rating`, `_sort_reviews_newest`, `_review_rating`, `_expand_review`. Review dict shape `{author, text, relative_date, rating}` is unchanged from the existing model (`Lead.reviews: list[dict]`), so sinks/DB need no migration.

**Known limitations (acceptable for v1):** `_extract_reviews` selects from the initially-loaded cards (~10). For a business whose 3 newest *textual* ≥4-star reviews fall outside the first batch, fewer than 3 may be returned; add reviews-pane scrolling in a follow-up if this shows up in practice.
