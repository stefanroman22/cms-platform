# Scraper Polish — Reviews / Hours / About / Min-Reviews Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four lead-quality adjustments — (1) reviews now keep star-only entries and prefer text; (2) opening hours always store a 7-day skeleton with `___` placeholders even when extraction misses; (3) Google Maps "About" attributes extracted into a grouped JSON with new dashboard rendering; (4) `min_reviews` default becomes `5` and is promoted from Advanced to the primary form.

**Architecture:** Selectors broaden (multi-fallback `aria-label` patterns + `[role="tab"]` indices) because live probing got bounced by Google. Engineer iterates selectors during execution against a live scrape and tightens them if too noisy. Storage stays as-is (`opening_hours` JSONB column with new skeleton shape, `extra.attributes` JSONB sub-key for grouped About data). Drawer gets two new presentational components (`OpeningHoursTable`, `AboutAttributesPanel`) — no new API, the data already round-trips through `/admin/leads/{id}`.

**Tech Stack:** Pydantic v2 (backend + scraper), Playwright async, FastAPI, Next.js 16 + React 19 + framer-motion (existing).

---

## Live selector hunt notes

Selectors below are educated guesses based on observed Google patterns. Live probing was inconclusive (direct place URLs bounce in headless / MCP). **During execution: run the engine once against `hairdresser Samir`, watch the per-place log lines. If reviews/about still empty, the engineer should:**

1. Edit the running scraper to `print(await page.content())` for one place
2. Inspect the actual DOM HTML
3. Update `selectors.py` with the matching selectors
4. Re-run

The plan provides 2–3 fallback selectors per field so first-shot success rate stays high.

---

## File Structure

| File | Action | Why |
|------|--------|-----|
| `backend/auth_service/models/schemas.py` | EXTEND | `ScrapeFilters.min_reviews: int \| None = 5` |
| `scraper/src/scraper/models.py` | EXTEND | Mirror same default |
| `scraper/src/scraper/cli.py` | EXTEND | Default `--min-reviews 5` |
| `frontend/src/components/admin/leads/ScraperForm.tsx` | EXTEND | Promote min_reviews to main form; default `5` |
| `scraper/src/scraper/selectors.py` | EXTEND | Multi-fallback Reviews tab + About tab + About items |
| `scraper/src/scraper/google_maps.py` | EXTEND | `_default_opening_hours()` helper; tiebreak sort for reviews; group About by section |
| `frontend/src/components/admin/leads/OpeningHoursTable.tsx` | CREATE | 7-row days × hours visualisation with `___` placeholders |
| `frontend/src/components/admin/leads/AboutAttributesPanel.tsx` | CREATE | Grouped checkmark list (Accessibility / Amenities / Payments / etc.) |
| `frontend/src/components/admin/leads/ReviewsList.tsx` | CREATE | Styled list of top-3 reviews (replaces raw JSON for reviews) |
| `frontend/src/components/admin/leads/LeadDetailDrawer.tsx` | EXTEND | Mount the 3 new presentational components |
| `frontend/src/components/admin/leads/types.ts` | EXTEND | Add review shape type if needed |
| `scraper/tests/test_google_maps_pure.py` | EXTEND | Unit tests for `_default_opening_hours`, review-sort tiebreak |
| `scraper/tests/test_models.py` | EXTEND | Default `min_reviews=5` assertion |
| `backend/auth_service/tests/test_admin_scrape_jobs_router.py` | EXTEND | Update empty-body test to expect `min_reviews=5` |

---

## Phase A — min_reviews default = 5 (promoted to main form)

### Task 1: Backend default

**Files:**
- Modify: `backend/auth_service/models/schemas.py` — find `class ScrapeFilters(BaseModel)`
- Test: `backend/auth_service/tests/test_admin_scrape_jobs_router.py`

- [ ] **Step 1: Update the empty-body test expected `min_reviews`**

In `test_create_job_with_empty_params_uses_defaults`, the mock return data's `filters` dict currently has `"min_reviews": None`. Change to `"min_reviews": 5`. The test also asserts via `body["params"]["filters"]["web_presence"]` etc — add:

```python
    assert body["params"]["filters"]["min_reviews"] == 5
```

at the end of that test.

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests/test_admin_scrape_jobs_router.py::test_create_job_with_empty_params_uses_defaults -v
```
Expected: assertion fails because backend still defaults `min_reviews` to None.

- [ ] **Step 3: Edit `schemas.py::ScrapeFilters`**

Find:

```python
class ScrapeFilters(BaseModel):
    min_rating: float | None = None
    max_rating: float | None = None
    min_reviews: int | None = None
```

Change `min_reviews` to:

```python
    min_reviews: int | None = 5
```

- [ ] **Step 4: Run, verify PASS**

```bash
pytest auth_service/tests/test_admin_scrape_jobs_router.py::test_create_job_with_empty_params_uses_defaults -v
```

- [ ] **Step 5: Full backend suite**

```bash
pytest auth_service/tests/ -q 2>&1 | tail -3
```

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/models/schemas.py backend/auth_service/tests/test_admin_scrape_jobs_router.py
git commit -m "feat(api): ScrapeFilters.min_reviews defaults to 5 — filter out unproven businesses"
```

---

### Task 2: Scraper model mirror

**Files:**
- Modify: `scraper/src/scraper/models.py::ScrapeFilters`
- Test: `scraper/tests/test_models.py`

- [ ] **Step 1: Update the existing default-construction test**

In `scraper/tests/test_models.py::test_scrape_params_default_construction_all_optional`, currently asserts `assert p.filters.min_rating is None`. Add right after:

```python
    assert p.filters.min_reviews == 5
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd scraper && source .venv/Scripts/activate && pytest tests/test_models.py -v 2>&1 | tail -5
```

- [ ] **Step 3: Edit `models.py::ScrapeFilters`**

Find `min_reviews: int | None = None` and change to:

```python
    min_reviews: int | None = 5
```

- [ ] **Step 4: Verify PASS**

```bash
pytest tests/test_models.py -v 2>&1 | tail -5
```

- [ ] **Step 5: Full scraper suite + lint**

```bash
pytest tests/ -q && ruff check . 2>&1 | tail -3
```

- [ ] **Step 6: Commit**

```bash
git add scraper/src/scraper/models.py scraper/tests/test_models.py
git commit -m "feat(scraper): ScrapeFilters.min_reviews mirror — default 5"
```

---

### Task 3: CLI default

**Files:**
- Modify: `scraper/src/scraper/cli.py` — find the `--min-reviews` option

- [ ] **Step 1: Edit the option signature**

Find:

```python
    min_reviews: Annotated[int | None, typer.Option("--min-reviews")] = None,
```

Change to:

```python
    min_reviews: Annotated[int | None, typer.Option("--min-reviews")] = 5,
```

- [ ] **Step 2: Verify the CLI shows the new default**

```bash
cd scraper && source .venv/Scripts/activate && python -m scraper.cli scrape --help 2>&1 | grep -A1 "min-reviews"
```

Expected: `--min-reviews ... [default: 5]`.

- [ ] **Step 3: Commit**

```bash
git add scraper/src/scraper/cli.py
git commit -m "feat(scraper/cli): --min-reviews default 5"
```

---

### Task 4: Frontend default + promote to main form

**Files:**
- Modify: `frontend/src/components/admin/leads/ScraperForm.tsx`

- [ ] **Step 1: Read the existing form layout**

Find `DEFAULT_PARAMS` and the `filters: { ... }` block. Also find the "Advanced filters" `AnimatePresence` block.

- [ ] **Step 2: Update default**

In `DEFAULT_PARAMS`, change:

```typescript
    min_reviews: null,
```

to:

```typescript
    min_reviews: 5,
```

- [ ] **Step 3: Add a visible min_reviews input above Advanced**

Find the `<div className="grid grid-cols-2 md:grid-cols-4 gap-3">` block that holds `Max / area`, `Language`, `Lead type`, `Include reviews`. Change its grid to 5 columns OR keep 4 and replace `Include reviews` with `Min reviews` (move `Include reviews` into a label-styled row above/below).

Concrete change — replace the existing 4-col block with this expanded version:

```tsx
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div>
          <label className={dashboardFieldLabelCn}>Max / area</label>
          <input
            type="number"
            className={dashboardInputCn}
            value={params.max_results_per_area}
            onChange={(e) =>
              setParams((p) => ({
                ...p,
                max_results_per_area: Math.max(1, Number(e.target.value) || 1),
              }))
            }
          />
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>Language</label>
          <input
            type="text"
            className={dashboardInputCn}
            value={params.language}
            onChange={(e) => setParams((p) => ({ ...p, language: e.target.value }))}
          />
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>Lead type</label>
          <AnimatedSelect
            value={params.lead_type}
            onChange={(v) => setParams((p) => ({ ...p, lead_type: v as LeadType }))}
            ariaLabel="Lead type"
            options={(Object.keys(LEAD_TYPE_LABEL) as LeadType[]).map((k) => ({
              value: k,
              label: LEAD_TYPE_LABEL[k],
            }))}
          />
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>Min reviews</label>
          <input
            type="number"
            min="0"
            className={dashboardInputCn}
            value={params.filters.min_reviews ?? ""}
            placeholder="5"
            onChange={(e) =>
              setFilter(
                "min_reviews",
                e.target.value === "" ? null : Number(e.target.value),
              )
            }
          />
        </div>
        <div className="flex items-end">
          <label className="inline-flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              checked={params.with_reviews}
              onChange={(e) =>
                setParams((p) => ({ ...p, with_reviews: e.target.checked }))
              }
            />
            Include reviews
          </label>
        </div>
      </div>
```

Then in the Advanced filters section, REMOVE the existing `Min reviews` FilterNumber to avoid duplication. Keep only `Reviews max` in advanced if you like, or move both there. Cleanest: keep `Reviews min`/`Reviews max` in Advanced too, but the main form's "Min reviews" overrides. Actually — to avoid sync confusion, just keep min_reviews in main form only and leave max in Advanced:

In the Advanced section's FilterNumber list, change:

```tsx
                <FilterNumber
                  label="Reviews min"
                  value={params.filters.min_reviews}
                  onChange={(v) => setFilter("min_reviews", v)}
                />
                <FilterNumber
                  label="Reviews max"
                  ...
```

To remove the `Reviews min` block (keep `Reviews max`):

```tsx
                <FilterNumber
                  label="Reviews max"
                  value={params.filters.max_reviews}
                  onChange={(v) => setFilter("max_reviews", v)}
                />
```

- [ ] **Step 4: Typecheck + lint**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -3 && npm run lint 2>&1 | tail -3
```

- [ ] **Step 5: Manual smoke**

Restart dev server → Scraper tab → confirm "Min reviews" is in the main 5-col row with placeholder/default `5`. Confirm Advanced doesn't double-show it.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/admin/leads/ScraperForm.tsx
git commit -m "feat(ui): ScraperForm — min_reviews promoted to main form, defaults to 5"
```

---

## Phase B — Opening hours skeleton

### Task 5: Default skeleton + extraction fallback

**Files:**
- Modify: `scraper/src/scraper/google_maps.py`
- Test: `scraper/tests/test_google_maps_pure.py`

- [ ] **Step 1: Add the failing test**

Append to `scraper/tests/test_google_maps_pure.py`:

```python
def test_default_opening_hours_has_seven_days():
    from scraper.google_maps import _default_opening_hours

    hours = _default_opening_hours()
    assert set(hours.keys()) == {
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    }
    assert all(v == "___" for v in hours.values())
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd scraper && source .venv/Scripts/activate && pytest tests/test_google_maps_pure.py::test_default_opening_hours_has_seven_days -v
```

Expected: ImportError on `_default_opening_hours`.

- [ ] **Step 3: Add the helper to `google_maps.py`**

Near the existing `_split_address` helper (around line 220), add:

```python
def _default_opening_hours() -> dict[str, str]:
    """7-day skeleton with `___` placeholders. Used when extraction
    misses (selector drift or place has no hours block) so downstream
    consumers (website builder agent, dashboard) always see all days."""
    return {
        "Monday": "___",
        "Tuesday": "___",
        "Wednesday": "___",
        "Thursday": "___",
        "Friday": "___",
        "Saturday": "___",
        "Sunday": "___",
    }
```

- [ ] **Step 4: Use the helper in `_scrape_one_place`**

Find:

```python
        opening_hours = await _extract_opening_hours(page)
```

Change to:

```python
        opening_hours = await _extract_opening_hours(page) or _default_opening_hours()
```

Also: when `_extract_opening_hours` returns a partial dict (only some days), merge with the skeleton so missing days fall back to `___`. Modify `_extract_opening_hours` so its returned dict is always merged from the skeleton:

Find the existing `_extract_opening_hours` function. Replace its final `return hours or None` with:

```python
        if not hours:
            return None
        # Merge into the skeleton so every day key is present.
        skeleton = _default_opening_hours()
        for k, v in hours.items():
            # Normalise day key: take the first 2 chars + lower then map
            # to the canonical day name. Simpler: if extraction's key
            # contains a known day stem (case-insensitive), copy.
            for canon in skeleton.keys():
                if canon.lower() in k.lower():
                    skeleton[canon] = v
                    break
        return skeleton
```

(Order matters — define `_default_opening_hours()` ABOVE `_extract_opening_hours` so it's in scope.)

- [ ] **Step 5: Run tests**

```bash
pytest tests/ -q
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scraper/src/scraper/google_maps.py scraper/tests/test_google_maps_pure.py
git commit -m "feat(scraper): opening_hours always has 7-day skeleton with ___ placeholders"
```

---

### Task 6: OpeningHoursTable dashboard component

**Files:**
- Create: `frontend/src/components/admin/leads/OpeningHoursTable.tsx`

- [ ] **Step 1: Write the component**

```tsx
"use client";

import { motion } from "framer-motion";
import { Clock } from "lucide-react";
import { fadeUp, staggerFast } from "@/lib/animations";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;

interface Props {
  hours: Record<string, string> | null;
}

export function OpeningHoursTable({ hours }: Props) {
  // Merge whatever we have with the 7-day skeleton so every row renders.
  const merged: Record<string, string> = Object.fromEntries(
    DAYS.map((d) => [d, hours?.[d] ?? "___"]),
  );

  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2 flex items-center gap-1.5">
        <Clock className="h-3.5 w-3.5" />
        Opening hours
      </h3>
      <motion.div
        variants={staggerFast}
        initial="hidden"
        animate="visible"
        className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800"
      >
        {DAYS.map((day) => {
          const value = merged[day];
          const isPlaceholder = value === "___";
          return (
            <motion.div
              key={day}
              variants={fadeUp}
              className="flex items-center justify-between px-3 py-2 text-sm"
            >
              <span className="text-zinc-600 dark:text-zinc-400 font-medium">{day}</span>
              <span
                className={
                  isPlaceholder
                    ? "text-zinc-400 dark:text-zinc-600 font-mono italic"
                    : "text-zinc-900 dark:text-zinc-100 tabular-nums"
                }
              >
                {value}
              </span>
            </motion.div>
          );
        })}
      </motion.div>
    </section>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -3
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/admin/leads/OpeningHoursTable.tsx
git commit -m "feat(ui): OpeningHoursTable — 7-day rendering with ___ placeholders"
```

---

## Phase C — Reviews: capture star-only, prefer text, fix selector

### Task 7: Broaden Reviews tab selector + sort tiebreak

**Files:**
- Modify: `scraper/src/scraper/selectors.py`
- Modify: `scraper/src/scraper/google_maps.py`

- [ ] **Step 1: Update the Reviews tab selector**

In `selectors.py`, find:

```python
REVIEWS_TAB_BUTTON = 'button[aria-label*="Reviews"], button[aria-label*="recensies"]'
```

Replace with a multi-fallback union including the common `[role="tab"]` form and the "Reviews for X" pattern:

```python
REVIEWS_TAB_BUTTON = (
    'button[aria-label^="Reviews for "],'
    'button[aria-label="Reviews"],'
    'button[aria-label*="recensies"],'
    '[role="tab"][aria-label^="Reviews for "],'
    '[role="tab"][aria-label="Reviews"],'
    'button[jsaction*="reviewChart"]'
)
```

Also broaden REVIEW_CARD slightly — replace:

```python
REVIEW_CARD = "div[data-review-id]"
```

with:

```python
REVIEW_CARD = 'div[data-review-id], div[jsaction*="reviewerLink"]'
```

REVIEW_AUTHOR / REVIEW_TEXT / REVIEW_RATING / REVIEW_RELATIVE_DATE remain as-is for now — they're fragile but were working before; if reviews still come back empty after the tab fix, the engineer iterates these next.

- [ ] **Step 2: Fix the sort tiebreak**

In `google_maps.py::_extract_reviews`, find:

```python
    candidates.sort(key=lambda r: (r.get("rating") or -1), reverse=True)
```

Replace with:

```python
    # Sort: reviews with text rank above star-only; within each bucket,
    # higher rating first. Achieved by sorting on a tuple (has_text, rating).
    candidates.sort(
        key=lambda r: (1 if r.get("text") else 0, r.get("rating") or -1),
        reverse=True,
    )
```

- [ ] **Step 3: Add a test for the sort tiebreak**

Append to `scraper/tests/test_google_maps_pure.py`:

```python
def test_reviews_sort_prefers_text_then_rating():
    """In-memory check that the same logic used inside _extract_reviews
    prefers a 4-star with text over a 5-star without text."""
    reviews = [
        {"author": "A", "text": None, "rating": 5},
        {"author": "B", "text": "great place", "rating": 4},
        {"author": "C", "text": "loved it", "rating": 5},
    ]
    reviews.sort(
        key=lambda r: (1 if r.get("text") else 0, r.get("rating") or -1),
        reverse=True,
    )
    # Order should be: C (text + 5), B (text + 4), A (no text + 5)
    assert [r["author"] for r in reviews] == ["C", "B", "A"]
```

- [ ] **Step 4: Run tests + lint**

```bash
cd scraper && source .venv/Scripts/activate && pytest tests/ -q && ruff check . 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

```bash
git add scraper/src/scraper/selectors.py scraper/src/scraper/google_maps.py scraper/tests/test_google_maps_pure.py
git commit -m "feat(scraper): broaden Reviews tab selectors + tiebreak prefers text over star-only"
```

---

### Task 8: ReviewsList dashboard component

**Files:**
- Create: `frontend/src/components/admin/leads/ReviewsList.tsx`

- [ ] **Step 1: Write the component**

```tsx
"use client";

import { motion } from "framer-motion";
import { Star } from "lucide-react";
import { fadeUp, staggerFast } from "@/lib/animations";

interface Review {
  author: string | null;
  text: string | null;
  relative_date: string | null;
  rating: number | null;
}

interface Props {
  reviews: Review[] | null;
}

export function ReviewsList({ reviews }: Props) {
  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
        Top reviews
      </h3>
      {!reviews || reviews.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 text-xs text-zinc-500 dark:text-zinc-400 italic">
          No reviews captured.
        </div>
      ) : (
        <motion.div
          variants={staggerFast}
          initial="hidden"
          animate="visible"
          className="space-y-2"
        >
          {reviews.map((r, i) => (
            <motion.div
              key={`${r.author ?? "anon"}-${i}`}
              variants={fadeUp}
              className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
                  {r.author ?? "Anonymous"}
                </span>
                <span className="inline-flex items-center gap-0.5 text-xs text-amber-600 dark:text-amber-400 tabular-nums">
                  <Star className="h-3 w-3 fill-current" />
                  {r.rating ?? "—"}
                </span>
              </div>
              {r.text && (
                <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">
                  {r.text}
                </p>
              )}
              {r.relative_date && (
                <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  {r.relative_date}
                </div>
              )}
            </motion.div>
          ))}
        </motion.div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -3
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/admin/leads/ReviewsList.tsx
git commit -m "feat(ui): ReviewsList — styled top-3 review cards with star + text"
```

---

## Phase D — About attributes: extract grouped + dashboard panel

### Task 9: Broaden About tab + items selectors; group by section

**Files:**
- Modify: `scraper/src/scraper/selectors.py`
- Modify: `scraper/src/scraper/google_maps.py`

- [ ] **Step 1: Update About selectors**

In `selectors.py`, find:

```python
ABOUT_TAB_BUTTON = 'button[aria-label*="About"], button[aria-label*="Over"]'
ABOUT_ATTRIBUTE_ITEMS = 'div[role="group"] li[aria-label], div[role="region"] li[aria-label]'
```

Replace with:

```python
ABOUT_TAB_BUTTON = (
    'button[aria-label^="About "],'
    'button[aria-label="About"],'
    'button[aria-label*="Over "],'
    '[role="tab"][aria-label^="About "],'
    '[role="tab"][aria-label="About"]'
)

# About-tab structure (best-effort): when the tab is opened, the right-
# hand panel contains rows. Each visible attribute exposes its label via
# `aria-label` on a `li`, OR is text inside a `div[role="img"]` icon row.
ABOUT_ATTRIBUTE_ITEMS = (
    'div[role="region"] li[aria-label],'
    'div[role="group"] li[aria-label],'
    'div[aria-label*="About"] li[aria-label]'
)

# Section-heading selector — the About panel groups attributes under
# headings like "Accessibility", "Amenities", "Payments". Each section
# is a sibling div whose first child is a heading-like element.
ABOUT_SECTION_HEADINGS = (
    'div[role="region"] h2,'
    'div[role="region"] h3,'
    'div[role="region"] [role="heading"]'
)
```

- [ ] **Step 2: Rewrite `_extract_about_attributes` to group by section**

In `google_maps.py`, find the existing `_extract_about_attributes` function (returns `dict[str, bool]`). Replace with a grouped version returning `dict[str, dict[str, bool]]`:

```python
async def _extract_about_attributes(page: Page) -> dict[str, dict[str, bool]]:
    """Open the About tab and read attributes grouped by section heading.
    Returns {} when the tab is absent or unparseable.

    Shape:
        {
            "Accessibility": {"Wheelchair-accessible car park": True, ...},
            "Amenities": {"Toilet": True},
            "Payments": {"Debit cards": True, ...},
            ...
        }
    """
    try:
        btn = page.locator(selectors.ABOUT_TAB_BUTTON).first
        if await btn.count() == 0:
            return {}
        await btn.click(timeout=2000)
        await page.wait_for_load_state("networkidle", timeout=3000)

        # Read the entire About panel as raw HTML, parse with JS in-page
        # so we capture grouped structure.
        grouped = await page.evaluate(
            """() => {
                const panel = document.querySelector('div[role="region"][aria-label*="About"]')
                    || document.querySelector('div[role="region"]');
                if (!panel) return {};
                const out = {};
                let current = "Other";
                for (const node of panel.querySelectorAll('h2, h3, [role="heading"], li')) {
                    const tag = node.tagName.toLowerCase();
                    if (tag === 'h2' || tag === 'h3' || node.getAttribute('role') === 'heading') {
                        current = (node.innerText || '').trim() || current;
                        continue;
                    }
                    // li with aria-label = an attribute
                    const aria = node.getAttribute('aria-label');
                    const label = (aria || node.innerText || '').trim();
                    if (!label) continue;
                    const isNo = /^no\\s+/i.test(label);
                    const key = label.replace(/^no\\s+/i, '').trim();
                    if (!out[current]) out[current] = {};
                    out[current][key] = !isNo;
                }
                return out;
            }"""
        )
        return grouped or {}
    except Exception:
        return {}
```

- [ ] **Step 3: Update the call site to store under `extra.attributes`**

The existing code in `_scrape_one_place` does:

```python
        about_attrs = await _extract_about_attributes(page)
        ...
        extra: dict[str, Any] = {}
        if about_attrs:
            extra["attributes"] = about_attrs
```

No change needed at the call site — the new dict-of-dicts shape replaces the old flat dict transparently (both go under `extra.attributes`). Drop the old `_normalize_attribute_key` helper since the new code uses raw labels as keys.

- [ ] **Step 4: Remove `_normalize_attribute_key` if unused after the rewrite**

```bash
cd scraper && source .venv/Scripts/activate && grep -n "_normalize_attribute_key" src/scraper/google_maps.py tests/
```

If only used by the old extractor, remove the function + the test `test_normalize_attribute_key_spaces` from `tests/test_google_maps_pure.py`.

- [ ] **Step 5: Run tests + lint**

```bash
pytest tests/ -q && ruff check . 2>&1 | tail -3
```

Expected: green. If `mypy` complains about the new dict-of-dicts return type vs the old call-site annotation, update the annotation accordingly.

- [ ] **Step 6: Commit**

```bash
git add scraper/src/scraper/selectors.py scraper/src/scraper/google_maps.py scraper/tests/test_google_maps_pure.py
git commit -m "feat(scraper): About attributes grouped by section (Accessibility / Amenities / Payments / ...)"
```

---

### Task 10: AboutAttributesPanel dashboard component

**Files:**
- Create: `frontend/src/components/admin/leads/AboutAttributesPanel.tsx`

- [ ] **Step 1: Write the component**

```tsx
"use client";

import { motion } from "framer-motion";
import { Check, X } from "lucide-react";
import { fadeUp, staggerFast } from "@/lib/animations";

interface Props {
  attributes: Record<string, Record<string, boolean>> | null | undefined;
}

export function AboutAttributesPanel({ attributes }: Props) {
  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
        About this business
      </h3>
      {!attributes || Object.keys(attributes).length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 text-xs text-zinc-500 dark:text-zinc-400 italic">
          No "About" data on Google Maps for this place.
        </div>
      ) : (
        <motion.div
          variants={staggerFast}
          initial="hidden"
          animate="visible"
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-3"
        >
          {Object.entries(attributes).map(([section, items]) => (
            <motion.div key={section} variants={fadeUp}>
              <div className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                {section}
              </div>
              <ul className="space-y-0.5">
                {Object.entries(items).map(([attr, value]) => (
                  <li
                    key={attr}
                    className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300"
                  >
                    {value ? (
                      <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    ) : (
                      <X className="h-3.5 w-3.5 text-zinc-400 dark:text-zinc-600 shrink-0" />
                    )}
                    <span className={value ? "" : "text-zinc-500 dark:text-zinc-500 line-through"}>
                      {attr}
                    </span>
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </motion.div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -3
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/admin/leads/AboutAttributesPanel.tsx
git commit -m "feat(ui): AboutAttributesPanel — grouped checkmark list of Google Maps attributes"
```

---

### Task 11: Wire the 3 new components into LeadDetailDrawer

**Files:**
- Modify: `frontend/src/components/admin/leads/LeadDetailDrawer.tsx`

- [ ] **Step 1: Find the existing `<CollapsibleJson>` calls for opening_hours / reviews / extra**

There are 3 calls near the bottom of `DrawerBody`:

```tsx
<CollapsibleJson title="Opening hours" data={lead.opening_hours} />
<CollapsibleJson title="Reviews" data={lead.reviews} />
<CollapsibleJson title="Extra (extensibility seam)" data={lead.extra} />
```

- [ ] **Step 2: Add imports for the new components**

At the top of the file, alongside other component imports:

```tsx
import { OpeningHoursTable } from "./OpeningHoursTable";
import { ReviewsList } from "./ReviewsList";
import { AboutAttributesPanel } from "./AboutAttributesPanel";
```

- [ ] **Step 3: Replace the 3 collapsible JSON blocks**

Replace:

```tsx
<CollapsibleJson title="Opening hours" data={lead.opening_hours} />
<CollapsibleJson title="Reviews" data={lead.reviews} />
<CollapsibleJson title="Extra (extensibility seam)" data={lead.extra} />
```

With:

```tsx
<OpeningHoursTable hours={lead.opening_hours as Record<string, string> | null} />
<ReviewsList reviews={(lead.reviews ?? []) as { author: string | null; text: string | null; relative_date: string | null; rating: number | null; }[]} />
<AboutAttributesPanel
  attributes={
    (lead.extra && typeof lead.extra === "object" && "attributes" in lead.extra
      ? (lead.extra.attributes as Record<string, Record<string, boolean>>)
      : null) ?? null
  }
/>
{/* Keep the raw "extra" JSON viewer as a debug aid — collapsed by default */}
<CollapsibleJson title="Raw extra (debug)" data={lead.extra} />
```

(Leave the `CollapsibleJson` definition in the file — still used for the debug viewer.)

- [ ] **Step 4: Typecheck + lint**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -3 && npm run lint 2>&1 | tail -3
```

- [ ] **Step 5: Manual smoke**

Restart dev server → open any existing lead in drawer:
- Opening hours: see 7-row table, each day either real hours or `___`
- Reviews: cards with star + text + author + date OR empty placeholder
- About: grouped sections or "No About data" placeholder

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/admin/leads/LeadDetailDrawer.tsx
git commit -m "feat(ui): LeadDetailDrawer — render hours, reviews, About via dedicated components"
```

---

## Phase E — Verification

### Task 12: Live re-scrape

- [ ] **Step 1: Wipe stale leads (optional, for clarity)**

```sql
DELETE FROM leads WHERE business_name IN ('hairdresser Samir', 'Novica International Business Consultancy', 'Color Business Center Nijmegen Krayenhoff');
```

- [ ] **Step 2: Re-scrape Samir's category in Nijmegen with the new defaults**

```bash
cd scraper && source .venv/Scripts/activate
python -m scraper.cli scrape --category "kappers" --city Nijmegen
```

Expected: hairdresser Samir found, `review_count=105`, `reviews` has up to 3 cards (text-first sort), `extra.attributes` populated with grouped sections (Accessibility, Amenities, Planning, Payments, Children), `opening_hours` has 7 days with `___` for unknowns.

- [ ] **Step 3: Inspect the row**

```sql
SELECT business_name, review_count,
       jsonb_array_length(reviews) AS num_reviews,
       opening_hours,
       extra->'attributes' AS about_attrs
FROM leads WHERE business_name='hairdresser Samir';
```

Expected:
- `num_reviews >= 1` (ideally 3)
- `opening_hours` has all 7 day keys
- `about_attrs` has grouped sections matching the user's screenshot (Accessibility / Amenities / Planning / Payments / Children)

- [ ] **Step 4: Open the drawer in the CMS**

`/dashboard/admin/leads` → Dashboard tab → click Samir → drawer shows:
- Pipeline section
- Opening hours: 7-row table
- Top reviews: 1-3 cards
- About this business: grouped checkmark list
- Raw extra (debug): collapsed JSON

- [ ] **Step 5: If reviews / About still empty**

The selectors are best-effort. Iterate:

```bash
# Add a temp print inside _scrape_one_place to dump page HTML for one place:
# print(await page.content())
# Re-run, inspect the HTML, grep for aria-labels containing "Review" or "About"
# Update selectors.py accordingly
# Commit follow-up
```

Don't block the rest of the plan on this — the storage + UI shape is correct; only the live extraction selectors may need tweaking.

---

## Acceptance criteria

- [ ] `ScrapeFilters()` defaults `min_reviews=5` on backend + scraper + frontend
- [ ] ScraperForm shows "Min reviews" as a top-row input with default `5`
- [ ] CLI `--min-reviews` default is `5`
- [ ] `_default_opening_hours()` returns 7-day skeleton with `___`
- [ ] Lead rows always have all 7 days in `opening_hours` (either real hours or `___`)
- [ ] Drawer renders Opening hours as a 7-row table (not raw JSON)
- [ ] `_extract_reviews` returns up to 3 reviews, text-first then highest-rating
- [ ] Drawer renders Reviews as styled cards (not raw JSON)
- [ ] `_extract_about_attributes` returns grouped dict by section heading
- [ ] Drawer renders About as a grouped checkmark list (Accessibility / Amenities / ...)
- [ ] `extra.attributes` does NOT leak into the Google Sheet
- [ ] All scraper tests pass; ruff clean; frontend typecheck + lint clean

---

## Self-Review

**1. Spec coverage:**
- "Reviews keep star-only + prefer text" → Task 7 (selector broadening + tiebreak sort) + Task 8 (UI)
- "Opening hours always show 7-day skeleton" → Task 5 (Pydantic-side skeleton) + Task 6 (UI)
- "About info in dashboard, not in sheet" → Task 9 (grouped extraction → `extra.attributes`) + Task 10 (UI). Sheet sink already ignores `extra` — verified by reading `_FIELD_MAP` keys; no entry references `extra` or `attributes`. ✓
- "min_reviews default 5, prominent" → Tasks 1-4 (full stack default) + Task 4 specifically promotes it to the main form row.
- "Use Playwright to probe" → noted in plan header: live probing was inconclusive; selector hunt continues during execution via real-scrape inspection.

**2. Placeholder scan:** no TBDs; every step has concrete code or exact command. The note in Task 12 Step 5 about iterating selectors if extraction misses is a guide for the engineer, not a placeholder in the plan itself.

**3. Type consistency:**
- `lead.opening_hours: Record<string, string> | null` — same in TS + Pydantic ✓
- `lead.extra.attributes: Record<string, Record<string, boolean>>` — grouped shape consistent between Task 9 (Python emit) + Task 10 (TS consume) ✓
- `reviews: { author, text, relative_date, rating }[]` — shape consistent between Task 7 (engine emit) + Task 8 (UI consume) ✓
- `min_reviews: int | None = 5` — consistent across backend, scraper, CLI, frontend types ✓

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-20-scraper-polish-reviews-hours-about.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session.

**Which approach?**
