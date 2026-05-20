# Scraper Defaults + All-Optional Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the scraper runnable with zero form input — every `ScrapeParams` field becomes optional with a sensible default — and verify every form field actually flows into the live scrape so no input is silently ignored.

**Architecture:** Single source of truth for defaults lives in two mirrored Pydantic models (`backend/auth_service/models/schemas.py::ScrapeParams` and `scraper/src/scraper/models.py::ScrapeParams`). Backend defaults gate API submissions; scraper defaults gate CLI + `run-pending`. The frontend `ScraperForm` defaults to the same values and submits an empty body when the user touches nothing. A "field-flow audit" verifies each `ScrapeParams` attribute is read at runtime — no orphan fields.

**Tech Stack:** Pydantic v2 (both sides), FastAPI, Next.js 16 + React 19 TypeScript, Playwright async, Typer CLI, pytest.

---

## Defaults (single source of truth)

These are the agreed defaults for an "empty submit" run:

| Field | Default | Why |
|---|---|---|
| `category` | `"businesses"` | Google Maps needs a query term — `""` would produce `" in NL"` and return junk. `"businesses"` is the broadest accepted term that still returns real places. |
| `country` | `"NL"` | Per spec |
| `cities` | `[]` | Empty → country-wide query |
| `areas` | `[]` | Empty → no narrowing |
| `max_results_per_area` | `120` | Existing default |
| `language` | `"en"` | Existing default |
| `lead_type` | `"website"` | Existing default — this is the *output* classification, not a filter |
| `with_reviews` | `True` | **CHANGED from False** — spec: always include reviews; top-3 by stars returns whatever is available (0–3) |
| `review_limit` | `10` | No-op since top-3 fix; kept for API compat |
| `filters.web_presence` | `["none", "social_only"]` | Spec: only no-website businesses |
| `filters.min_rating` / `max_rating` | `None` | No rating gate |
| `filters.min_reviews` / `max_reviews` | `None` | No review-count gate |

After this plan, **`POST /admin/scrape-jobs {"params": {}}` MUST succeed** and produce a job equivalent to the defaults above.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `backend/auth_service/models/schemas.py` | API contract — what the form sends, what the worker reads back | Make `category` default `"businesses"`, flip `with_reviews` default to `True`. Same defaults already present for cities/areas/filters. |
| `scraper/src/scraper/models.py` | Worker-side schema — what the worker validates on dequeue | Same default changes (mirror) |
| `scraper/src/scraper/cli.py` | Typer CLI for ad-hoc scrapes | Make the `category` positional argument optional with default `"businesses"`; flip `--with-reviews` default to `True`, add `--no-with-reviews` opt-out |
| `frontend/src/components/admin/leads/ScraperForm.tsx` | UI form | Remove "category required" validation, show default as placeholder, pre-check the reviews checkbox |
| `frontend/src/components/admin/leads/types.ts` | TS mirror of `ScrapeParams` for the frontend | Update the local `DEFAULT_PARAMS` constant so the form's reset/initial state matches |
| `backend/auth_service/tests/test_admin_scrape_jobs_router.py` | API test | Add empty-body test |
| `scraper/tests/test_models.py` | Model defaults test | Update existing tests; add empty-init test |
| `scraper/tests/test_google_maps_pure.py` | Field-flow audit + helper test | Add audit test asserting every `ScrapeParams` field is referenced in `scrape()` / `_build_queries` / `_scrape_one_place` / `_passes_filters` |
| `scraper/README.md` | Doc | Note new defaults in the "Quick run" section |

---

## Phase 1 — Backend defaults (API)

### Task 1: Update backend `ScrapeParams` defaults

**Files:**
- Modify: `backend/auth_service/models/schemas.py` — find `class ScrapeParams(BaseModel)` and the `with_reviews` + `category` lines
- Test: `backend/auth_service/tests/test_admin_scrape_jobs_router.py`

- [ ] **Step 1: Write the failing test for empty-body submission**

Append to `backend/auth_service/tests/test_admin_scrape_jobs_router.py`:

```python
def test_create_job_with_empty_params_uses_defaults(mock_supabase, client, auth_as, admin_user):
    """An empty params body must succeed — every field is optional with a default."""
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "job-defaults",
                "created_at": "2026-05-20T10:00:00Z",
                "status": "pending",
                "params": {
                    "category": "businesses",
                    "country": "NL",
                    "cities": [],
                    "areas": [],
                    "max_results_per_area": 120,
                    "language": "en",
                    "lead_type": "website",
                    "with_reviews": True,
                    "review_limit": 10,
                    "filters": {
                        "min_rating": None,
                        "max_rating": None,
                        "min_reviews": None,
                        "max_reviews": None,
                        "web_presence": ["none", "social_only"],
                    },
                },
                "started_at": None,
                "finished_at": None,
                "results_found": None,
                "results_inserted": None,
                "results_skipped": None,
                "error": None,
                "triggered_by": "cms",
            }
        ]
    )
    resp = client.post("/admin/scrape-jobs", json={"params": {}})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["params"]["category"] == "businesses"
    assert body["params"]["country"] == "NL"
    assert body["params"]["with_reviews"] is True
    assert body["params"]["filters"]["web_presence"] == ["none", "social_only"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests/test_admin_scrape_jobs_router.py::test_create_job_with_empty_params_uses_defaults -v
```
Expected: FAIL — `ScrapeParams.category` field is currently required, so empty body returns 422.

- [ ] **Step 3: Edit `schemas.py` — make `category` default `"businesses"` and `with_reviews` default `True`**

In `backend/auth_service/models/schemas.py`, find the `ScrapeParams` class. Change:

```python
class ScrapeParams(BaseModel):
    category: str
    country: str
```

to:

```python
class ScrapeParams(BaseModel):
    category: str = "businesses"
    country: str = "NL"
```

And change:

```python
    with_reviews: bool = False
```

to:

```python
    with_reviews: bool = True
```

Leave everything else (cities, areas, max_results_per_area, language, lead_type, review_limit, filters) untouched — they already default sensibly.

- [ ] **Step 4: Run the test, verify it passes**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests/test_admin_scrape_jobs_router.py::test_create_job_with_empty_params_uses_defaults -v
```
Expected: PASS.

- [ ] **Step 5: Run the full backend suite to confirm nothing broke**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests/ -q
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/models/schemas.py backend/auth_service/tests/test_admin_scrape_jobs_router.py
git commit -m "feat(api): ScrapeParams — every field optional, with_reviews defaults to True"
```

---

## Phase 2 — Scraper-side defaults (Pydantic mirror + CLI)

### Task 2: Update scraper `ScrapeParams` defaults

**Files:**
- Modify: `scraper/src/scraper/models.py`
- Test: `scraper/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Replace the body of `test_scrape_params_minimal_required_fields` in `scraper/tests/test_models.py` with:

```python
def test_scrape_params_default_construction_all_optional():
    """ScrapeParams() with no args must succeed and produce the agreed defaults."""
    p = ScrapeParams()
    assert p.category == "businesses"
    assert p.country == "NL"
    assert p.cities == []
    assert p.areas == []
    assert p.max_results_per_area == 120
    assert p.language == "en"
    assert p.lead_type == "website"
    assert p.with_reviews is True
    assert p.filters.web_presence == ["none", "social_only"]
    assert p.filters.min_rating is None
    assert p.filters.max_rating is None


def test_scrape_params_explicit_override():
    """Explicit fields still win over defaults."""
    p = ScrapeParams(category="restaurants", country="DE", cities=["Berlin"])
    assert p.category == "restaurants"
    assert p.country == "DE"
    assert p.cities == ["Berlin"]
```

(Delete the old `test_scrape_params_minimal_required_fields` test entirely — the contract it asserted is no longer true.)

- [ ] **Step 2: Run, verify fails**

```bash
cd scraper && source .venv/Scripts/activate && pytest tests/test_models.py::test_scrape_params_default_construction_all_optional -v
```
Expected: FAIL — `category` field required, can't construct `ScrapeParams()`.

- [ ] **Step 3: Edit `scraper/src/scraper/models.py`**

Find the `ScrapeParams` class. Change:

```python
class ScrapeParams(BaseModel):
    ...
    category: str
    country: str
```

to:

```python
class ScrapeParams(BaseModel):
    ...
    category: str = "businesses"
    country: str = "NL"
```

Change:

```python
    with_reviews: bool = False
```

to:

```python
    with_reviews: bool = True
```

- [ ] **Step 4: Run, verify passes**

```bash
cd scraper && source .venv/Scripts/activate && pytest tests/test_models.py -v
```
Expected: 2 PASS (the two new tests) + existing tests still green.

- [ ] **Step 5: Full scraper suite**

```bash
pytest tests/ -q
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add scraper/src/scraper/models.py scraper/tests/test_models.py
git commit -m "feat(scraper): ScrapeParams — empty construction yields agreed defaults"
```

---

### Task 3: Update CLI — make `category` optional, flip `--with-reviews` default

**Files:**
- Modify: `scraper/src/scraper/cli.py`

- [ ] **Step 1: Read the existing CLI signature**

Open `scraper/src/scraper/cli.py`. Locate the `scrape` Typer command. Current signature:

```python
@app.command()
def scrape(
    category: Annotated[str, typer.Argument()],
    country: Annotated[str, typer.Argument()],
    ...
    with_reviews: Annotated[bool, typer.Option("--with-reviews")] = False,
    ...
)
```

- [ ] **Step 2: Edit the signature**

Change `category` and `country` to options with defaults (NOT positional, since both now have defaults):

```python
@app.command()
def scrape(
    category: Annotated[str, typer.Option("--category")] = "businesses",
    country: Annotated[str, typer.Option("--country")] = "NL",
    city: Annotated[list[str], typer.Option("--city")] = [],  # noqa: B006
    area: Annotated[list[str], typer.Option("--area")] = [],  # noqa: B006
    max: Annotated[int, typer.Option("--max")] = 120,
    language: Annotated[str, typer.Option("--language")] = "en",
    with_reviews: Annotated[bool, typer.Option("--with-reviews/--no-with-reviews")] = True,
    review_limit: Annotated[int, typer.Option("--review-limit")] = 10,
    lead_type: Annotated[str, typer.Option("--lead-type")] = "website",
    min_rating: Annotated[Optional[float], typer.Option("--min-rating")] = None,
    max_rating: Annotated[Optional[float], typer.Option("--max-rating")] = None,
    min_reviews: Annotated[Optional[int], typer.Option("--min-reviews")] = None,
    max_reviews: Annotated[Optional[int], typer.Option("--max-reviews")] = None,
    web_presence: Annotated[list[str], typer.Option("--web-presence")] = _DEFAULT_WEB_PRESENCE,  # noqa: B006
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    no_headless: Annotated[bool, typer.Option("--no-headless")] = False,
    no_supabase: Annotated[bool, typer.Option("--no-supabase")] = False,
    no_sheet: Annotated[bool, typer.Option("--no-sheet")] = False,
    out: Annotated[Optional[Path], typer.Option("--out")] = None,
) -> None:
```

If `_DEFAULT_WEB_PRESENCE` already exists at module level, reuse it. Otherwise leave the existing inline default and only change `category`/`country`/`with_reviews`.

The `--with-reviews/--no-with-reviews` syntax is Typer's pattern for a boolean with both on/off flags — `--with-reviews` (the default) leaves reviews on; `--no-with-reviews` turns them off.

- [ ] **Step 3: Smoke-test the CLI parses**

```bash
cd scraper && source .venv/Scripts/activate && python -m scraper.cli scrape --help
```
Expected: `--category` and `--country` shown as options (with defaults), `--with-reviews/--no-with-reviews` shown together.

- [ ] **Step 4: Smoke-test empty invocation parses (don't actually run — would scrape live)**

```bash
python -m scraper.cli scrape --help
```
Verify `[default: businesses]` near `--category`. Verify `[default: NL]` near `--country`. Verify `[default: with-reviews]` near the boolean.

- [ ] **Step 5: Commit**

```bash
git add scraper/src/scraper/cli.py
git commit -m "feat(scraper/cli): category + country optional with defaults; --with-reviews default on"
```

---

## Phase 3 — Frontend form: every field optional, sensible placeholders

### Task 4: Update `ScraperForm.tsx` defaults + validation

**Files:**
- Modify: `frontend/src/components/admin/leads/ScraperForm.tsx`

- [ ] **Step 1: Find the `DEFAULT_PARAMS` constant and the `valid` check**

Open `frontend/src/components/admin/leads/ScraperForm.tsx`. Locate `const DEFAULT_PARAMS: ScrapeParams = { ... }` and the line `const valid = params.category.trim() !== "" && params.country.trim() !== "";`.

- [ ] **Step 2: Replace `DEFAULT_PARAMS`**

```tsx
const DEFAULT_PARAMS: ScrapeParams = {
  category: "businesses",
  country: "NL",
  cities: [],
  areas: [],
  max_results_per_area: 120,
  language: "en",
  lead_type: "website",
  with_reviews: true,
  review_limit: 10,
  filters: {
    min_rating: null,
    max_rating: null,
    min_reviews: null,
    max_reviews: null,
    web_presence: ["none", "social_only"],
  },
};
```

- [ ] **Step 3: Remove the validation gate**

Change:

```tsx
const valid = params.category.trim() !== "" && params.country.trim() !== "";
```

to:

```tsx
// All fields have server-side defaults; submission is always allowed.
const valid = true;
```

And remove the `<span className="text-red-400">*</span>` markers from the Category + Country labels — they're no longer required:

Find:

```tsx
<label className={dashboardFieldLabelCn}>
  Category <span className="text-red-400">*</span>
</label>
```

Replace with:

```tsx
<label className={dashboardFieldLabelCn}>Category</label>
```

Same for the Country label.

- [ ] **Step 4: Add placeholder text showing the default**

For the category input, set `placeholder="businesses (default)"`. For the country input, set `placeholder="NL (default)"`. These show the user what'll be used if they leave the field empty.

- [ ] **Step 5: Make `handleSubmit` send blanks-as-defaults**

Currently `handleSubmit` POSTs `{params}` directly. If the user clears the category field, it'd send `category: ""` — which Pydantic accepts but produces a `" in NL"` query. Instead, fall back to the default before sending:

After `const valid = true;`, add a helper just inside the `handleSubmit` function (or right above) that strips empty strings:

```tsx
function buildSubmitParams(p: ScrapeParams): ScrapeParams {
  return {
    ...p,
    category: p.category.trim() || "businesses",
    country: p.country.trim() || "NL",
  };
}
```

Then in `handleSubmit`:

```tsx
body: JSON.stringify({ params: buildSubmitParams(params) }),
```

- [ ] **Step 6: Verify typecheck + lint**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -5 && npm run lint 2>&1 | tail -5
```
Expected: clean.

- [ ] **Step 7: Manual UI check**

Restart `npm run dev`. Open `/dashboard/admin/leads` → Scraper tab. Verify:
- Category field is empty by default with placeholder "businesses (default)"
- Country field shows "NL"
- "Include reviews" checkbox is checked
- Submit button is enabled even when everything is empty
- Click Submit → job appears in Job History as `pending` with category="businesses", country="NL", with_reviews=true

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/admin/leads/ScraperForm.tsx
git commit -m "feat(ui): ScraperForm — every field optional; placeholders show defaults; reviews on by default"
```

---

## Phase 4 — Field-flow audit: prove every form field reaches the scrape

### Task 5: Add a test that enforces every `ScrapeParams` attribute is actually read by the scraper

**Files:**
- Modify: `scraper/tests/test_google_maps_pure.py`

This is a guard against future drift — if someone adds a field to `ScrapeParams` but forgets to wire it into `scrape()` / `_build_queries` / `_passes_filters` / `_scrape_one_place`, this test catches it.

- [ ] **Step 1: Add the audit test**

Append to `scraper/tests/test_google_maps_pure.py`:

```python
import inspect

from scraper import google_maps
from scraper.models import ScrapeFilters, ScrapeParams


def test_every_scrape_params_field_is_referenced_in_engine():
    """Every attribute on ScrapeParams must be read somewhere in google_maps.py
    by name. Catches the "added a knob but forgot to wire it" bug.

    Whitelisted fields are knobs the engine intentionally does not read
    (e.g. `review_limit` is a no-op after the top-3-by-stars rewrite).
    Document each whitelist entry inline.
    """
    whitelist = {
        "review_limit",  # no-op since top-3-by-stars; kept for API compat
    }
    engine_src = inspect.getsource(google_maps)
    missing: list[str] = []

    for field_name in ScrapeParams.model_fields:
        if field_name in whitelist:
            continue
        if field_name == "filters":
            # filters is a nested model — its leaves must each be referenced.
            for sub in ScrapeFilters.model_fields:
                if f"{sub}" not in engine_src:
                    missing.append(f"filters.{sub}")
            continue
        if field_name not in engine_src:
            missing.append(field_name)

    assert not missing, (
        f"ScrapeParams fields not referenced in scraper.google_maps: {missing}. "
        "Either wire them into the engine, or add to the whitelist with a comment "
        "explaining why."
    )
```

- [ ] **Step 2: Run, verify it passes against the current engine**

```bash
cd scraper && source .venv/Scripts/activate && pytest tests/test_google_maps_pure.py::test_every_scrape_params_field_is_referenced_in_engine -v
```
Expected: PASS (the engine already reads every field except `review_limit`).

If FAIL: the listed field is genuinely not used → wire it in OR add to whitelist with rationale.

- [ ] **Step 3: Commit**

```bash
git add scraper/tests/test_google_maps_pure.py
git commit -m "test(scraper): audit — every ScrapeParams field must be referenced in engine"
```

---

### Task 6: Update README with new "Quick run" section

**Files:**
- Modify: `scraper/README.md`

- [ ] **Step 1: Find the existing "CLI" section in `scraper/README.md`**

- [ ] **Step 2: Add a "Quick run" subsection at the top of "CLI"**

```markdown
### Quick run (defaults)

All fields are optional. With zero arguments the scraper runs against
**Netherlands**, category **"businesses"**, **all cities country-wide**,
**reviews on (top 3 by stars)**, and the **no-website filter**.

```bash
python -m scraper.cli scrape --dry-run
```

Override any field with the matching `--option`. See `scrape --help` for the
full list.
```

- [ ] **Step 3: Commit**

```bash
git add scraper/README.md
git commit -m "docs(scraper): document zero-arg default run"
```

---

## Phase 5 — Live verification

### Task 7: End-to-end verification on local

This is a manual step the engineer (or human) performs after all code tasks land.

- [ ] **Step 1: Restart backend + frontend dev servers**

```bash
# Terminal A (backend)
cd backend && source venv/Scripts/activate && uvicorn auth_service.main:app --reload --port 8001

# Terminal B (frontend)
cd frontend && npm run dev
```

- [ ] **Step 2: Open `/dashboard/admin/leads` → Scraper tab. Click **Submit scrape** without touching any field.**

Expected:
- Job appears in Job History as `pending`
- Click into the job (or query Supabase directly) — `params` should be exactly the default object above

```sql
SELECT params FROM scrape_jobs ORDER BY created_at DESC LIMIT 1;
```
Expected: `category=businesses, country=NL, with_reviews=true, filters.web_presence=[none, social_only]`, all other defaults.

- [ ] **Step 3: Run the worker once to consume the job**

```bash
cd scraper && source .venv/Scripts/activate && python -m scraper.cli run-pending
```
Expected:
- Job transitions `pending → running → done`
- `results_found > 0` (some no-website businesses in NL country-wide)
- Each lead has `reviews` populated (possibly empty array if no reviews available, but the field is present)

- [ ] **Step 4: Verify a single submitted-field override actually flows through**

In the Scraper form, submit a job with **only** `city = ["Lelystad"]` set (leave everything else blank). Run the worker. Inspect the result:

```sql
SELECT params FROM scrape_jobs ORDER BY created_at DESC LIMIT 1;
SELECT city, count(*) FROM leads
WHERE scrape_job_id = (SELECT id FROM scrape_jobs ORDER BY created_at DESC LIMIT 1)
GROUP BY city;
```
Expected: all leads from that job should have `city='Lelystad'` (modulo edge cases where the address parser misses).

- [ ] **Step 5: No commit — manual verification only**

---

## Acceptance criteria (run at end)

- [ ] `ScrapeParams()` with zero arguments succeeds on both backend and scraper sides
- [ ] `POST /admin/scrape-jobs {"params": {}}` returns 201 with default-populated row
- [ ] Frontend ScraperForm submit succeeds with every field cleared
- [ ] The "Include reviews" checkbox is **checked** by default
- [ ] `python -m scraper.cli scrape --dry-run` (no other args) produces a JSON file
- [ ] Field-flow audit test passes (every form field is read by the engine)
- [ ] All existing tests still pass: backend 200+, scraper 47+

---

## Self-Review

**1. Spec coverage:**
- "Run scraper without filling all required input" → Task 1 + 2 (model defaults), Task 4 (form validation)
- "Default: no category" → defaulted to `"businesses"` (Task 1, 2); pragmatic substitute since Google Maps needs a query term
- "Default: country Netherlands" → Task 1, 2
- "Default: any area, any location" → cities=`[]`, areas=`[]` (already default)
- "Default: lead type find businesses without websites" → `filters.web_presence=["none", "social_only"]` (already default)
- "Default: no min/max rating, no min/max reviews" → already default
- "Always include reviews + fewer than 3 OK" → Task 1, 2 flip `with_reviews=True`; the existing top-3 sort already returns 0–3 gracefully
- "web presence: no website" → already default
- "Scan scraper, make sure every form field actually feeds the run" → Task 5 (audit test)
- "Why include-reviews checkbox" → answered in conversation, not a code task

**2. Placeholder scan:** no TBDs, every step has concrete code, exact commands, expected output.

**3. Type consistency:**
- `ScrapeParams.category: str = "businesses"` consistent across backend, scraper, frontend TS, CLI
- `with_reviews: True` consistent
- `filters.web_presence` list shape unchanged
- `buildSubmitParams` in TS matches the backend `category: str = "businesses"` fallback semantics

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-20-scraper-defaults-and-all-optional-form.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans.

**Which approach?**
