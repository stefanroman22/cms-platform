# Conversions Dashboard + Closed-Amount Field Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Conversions" financial dashboard tab next to Dashboard + Scraper, plus an editable `closed_amount` field per lead (visible only after lead becomes `accepted`). Everything threaded through Supabase, the Google Sheet mirror, and the CMS UI with animated charts.

**Architecture:** One new DB column (`closed_amount` NUMERIC) + bookkeeping column (`closed_at` TIMESTAMPTZ). Backend gates writes to `closed_amount` on `lead_status='accepted'` (set-or-already). Aggregations live in a new `/admin/conversions/summary` endpoint that returns KPI scalars + grouped breakdowns + a monthly timeseries — all from SQL queries against the existing `leads` table, no separate analytics table. Frontend uses Recharts (free, React-native) for line/bar/pie + framer-motion for KPI card stagger + reuses `useQuery` cache for the summary endpoint. The LeadDetailDrawer grows a single "Closed deal" section that appears only when `lead_status === "accepted"`.

**Tech Stack:** PostgreSQL (Supabase), FastAPI 0.136, Pydantic v2, Next.js 16 + React 19 + TypeScript + Tailwind v4, framer-motion (existing), **Recharts ^2.13 (NEW)**, gspread (existing).

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `backend/migrations/2026_05_20_lead_closed_amount.sql` | DB schema delta | CREATE |
| `backend/auth_service/models/schemas.py` | `LeadOut` + `LeadUpdate` | EXTEND with `closed_amount`, `closed_at` |
| `backend/auth_service/routers/admin_leads.py` | PATCH lead | EXTEND: gate `closed_amount` writes on accepted status; auto-set `closed_at` |
| `backend/auth_service/routers/admin_conversions.py` | Aggregation endpoints | CREATE |
| `backend/auth_service/main.py` | Mount routers | EXTEND |
| `backend/auth_service/tests/test_admin_leads_router.py` | Lead PATCH tests | EXTEND |
| `backend/auth_service/tests/test_admin_conversions_router.py` | Conversions tests | CREATE |
| `scraper/src/scraper/sinks/sheets_sink.py` | Field map | EXTEND with two new column names |
| `frontend/package.json` | Recharts dep | EXTEND |
| `frontend/src/components/admin/leads/types.ts` | TS mirror | EXTEND `Lead` with `closed_amount`, `closed_at` + new `ConversionSummary` shape |
| `frontend/src/components/admin/leads/LeadsTab.tsx` | Tab switcher | EXTEND: 3 tabs |
| `frontend/src/components/admin/leads/ConversionsTab.tsx` | Orchestrator | CREATE |
| `frontend/src/components/admin/leads/ConversionStats.tsx` | KPI cards | CREATE |
| `frontend/src/components/admin/leads/RevenueOverTimeChart.tsx` | Line chart | CREATE |
| `frontend/src/components/admin/leads/BreakdownChart.tsx` | Bar chart | CREATE |
| `frontend/src/components/admin/leads/ConversionFilters.tsx` | Date range + filters | CREATE |
| `frontend/src/components/admin/leads/LeadDetailDrawer.tsx` | Closed-deal section | EXTEND |
| `frontend/src/lib/leadEnums.ts` | Breakdown color palette | EXTEND |

---

## Phase A — Database migration

### Task 1: Add `closed_amount` + `closed_at` columns to `leads`

**Files:**
- Create: `backend/migrations/2026_05_20_lead_closed_amount.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Lead closed-deal amount (editable only when lead_status='accepted')
-- + timestamp of first non-null closed_amount write (revenue-over-time
-- queries group by this column).

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS closed_amount NUMERIC(12,2) CHECK (closed_amount IS NULL OR closed_amount >= 0),
    ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;

COMMENT ON COLUMN leads.closed_amount IS
'Deal value in EUR. Writable only when lead_status=''accepted''; backend enforces this.';
COMMENT ON COLUMN leads.closed_at IS
'Set automatically when closed_amount transitions from NULL to a value. Drives revenue-over-time aggregation.';

CREATE INDEX IF NOT EXISTS leads_closed_at_idx ON leads (closed_at);
CREATE INDEX IF NOT EXISTS leads_closed_amount_idx ON leads (closed_amount);
```

- [ ] **Step 2: Apply via Supabase MCP**

Use `mcp__supabase__apply_migration`:
- name: `2026_05_20_lead_closed_amount`
- query: the SQL above

- [ ] **Step 3: Verify columns + indexes exist**

Use `mcp__supabase__execute_sql`:

```sql
SELECT
    (SELECT count(*) FROM information_schema.columns
       WHERE table_name='leads'
       AND column_name IN ('closed_amount','closed_at')) AS cols,
    (SELECT count(*) FROM pg_indexes
       WHERE schemaname='public'
       AND indexname IN ('leads_closed_at_idx','leads_closed_amount_idx')) AS idx;
```

Expected: `cols=2, idx=2`.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/2026_05_20_lead_closed_amount.sql
git commit -m "feat(db): add leads.closed_amount + closed_at for revenue tracking"
```

---

## Phase B — Backend schema + PATCH gating

### Task 2: Extend `LeadOut` + `LeadUpdate` Pydantic models

**Files:**
- Modify: `backend/auth_service/models/schemas.py` — find `class LeadOut` and `class LeadUpdate`

- [ ] **Step 1: Add fields to `LeadOut`**

Find `class LeadOut(BaseModel):` and the `notes: str | None = None` line. ABOVE the `notes` line insert:

```python
    closed_amount: float | None = None
    closed_at: str | None = None
```

(Pydantic v2 serializes `NUMERIC` from Supabase as either str or float; using `float | None` lets it accept both; the frontend will parse.)

- [ ] **Step 2: Add field to `LeadUpdate`**

Find `class LeadUpdate(BaseModel):` block. Add a new optional field:

```python
    closed_amount: float | None = None
```

The existing pipeline fields stay. Order doesn't matter; group after `notes`.

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/models/schemas.py
git commit -m "feat(api): LeadOut + LeadUpdate carry closed_amount + closed_at"
```

---

### Task 3: PATCH endpoint — gate `closed_amount` writes on accepted status, auto-set `closed_at`

**Files:**
- Modify: `backend/auth_service/routers/admin_leads.py` — find `patch_lead` function
- Test: `backend/auth_service/tests/test_admin_leads_router.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/auth_service/tests/test_admin_leads_router.py`:

```python
def test_patch_closed_amount_rejected_when_not_accepted(
    mock_supabase, client, auth_as, admin_user
):
    """closed_amount may only be set when the lead is (or becomes) accepted."""
    auth_as(admin_user)
    # Pre-update SELECT returns current row with lead_status='sent'.
    mock_supabase.execute.side_effect = [
        MagicMock(data={"lead_status": "sent", "closed_amount": None}),
    ]
    resp = client.patch("/admin/leads/lead-1", json={"closed_amount": 1500})
    assert resp.status_code == 422
    assert "accepted" in resp.json()["detail"].lower()


def test_patch_closed_amount_allowed_when_accepted(
    mock_supabase, client, auth_as, admin_user
):
    """When the lead is already accepted, closed_amount can be set."""
    auth_as(admin_user)
    accepted_row = _lead_row(lead_status="accepted")
    updated_row = _lead_row(lead_status="accepted", closed_amount=1500.0, closed_at="2026-05-20T10:00:00Z")
    mock_supabase.execute.side_effect = [
        MagicMock(data={"lead_status": "accepted", "closed_amount": None}),  # pre-SELECT
        MagicMock(data=[updated_row]),                                       # UPDATE
    ]
    resp = client.patch("/admin/leads/lead-1", json={"closed_amount": 1500})
    assert resp.status_code == 200
    assert resp.json()["closed_amount"] == 1500.0


def test_patch_status_and_amount_together_allowed(
    mock_supabase, client, auth_as, admin_user
):
    """Setting lead_status='accepted' and closed_amount in the same PATCH succeeds."""
    auth_as(admin_user)
    updated_row = _lead_row(lead_status="accepted", closed_amount=2500.0, closed_at="2026-05-20T10:00:00Z")
    mock_supabase.execute.side_effect = [
        MagicMock(data={"lead_status": "sent", "closed_amount": None}),  # current
        MagicMock(data=[updated_row]),                                   # UPDATE
    ]
    resp = client.patch(
        "/admin/leads/lead-1",
        json={"lead_status": "accepted", "closed_amount": 2500},
    )
    assert resp.status_code == 200
    assert resp.json()["closed_amount"] == 2500.0
```

- [ ] **Step 2: Run, verify 3 tests FAIL**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests/test_admin_leads_router.py -v -k "closed_amount" 2>&1 | tail -10
```

Expected: 3 fails — the current endpoint accepts `closed_amount` unconditionally without the gate.

- [ ] **Step 3: Edit `admin_leads.py::patch_lead`**

Find the `async def patch_lead(...)` function. Replace its body with:

```python
@router.patch("/{lead_id}", response_model=LeadOut)
async def patch_lead(lead_id: str, body: LeadUpdate, request: Request) -> LeadOut:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    patch = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not patch:
        raise HTTPException(status_code=422, detail="No fields to update")

    # Gate closed_amount writes on lead_status='accepted' — either the current
    # row is already accepted, OR this same PATCH transitions it to accepted.
    if "closed_amount" in patch:
        current = (
            sb.table("leads")
            .select("lead_status, closed_amount")
            .eq("id", lead_id)
            .maybe_single()
            .execute()
        )
        if not current.data:
            raise HTTPException(status_code=404, detail="Lead not found")
        new_status = patch.get("lead_status", current.data["lead_status"])
        if new_status != "accepted":
            raise HTTPException(
                status_code=422,
                detail="closed_amount can only be set when lead_status is 'accepted'",
            )
        # Auto-set closed_at on first non-null write.
        if current.data["closed_amount"] is None and patch["closed_amount"] is not None:
            patch["closed_at"] = datetime.now(UTC).isoformat()

    res = sb.table("leads").update(patch).eq("id", lead_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Update failed")
    return LeadOut(**res.data[0])
```

At the top of the file, ensure `from datetime import UTC, datetime` is imported (add if missing).

- [ ] **Step 4: Run, verify 3 tests PASS**

```bash
pytest auth_service/tests/test_admin_leads_router.py -v -k "closed_amount" 2>&1 | tail -10
```

Expected: 3 PASS.

- [ ] **Step 5: Full backend suite still green**

```bash
pytest auth_service/tests/ -q 2>&1 | tail -3
```

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/routers/admin_leads.py backend/auth_service/tests/test_admin_leads_router.py
git commit -m "feat(api): PATCH /admin/leads — gate closed_amount on accepted + autoset closed_at"
```

Note for the test file: the existing `_lead_row` helper does NOT include `closed_amount` / `closed_at`. **Inside the new tests, pass `closed_amount=...` and `closed_at=...` via the existing `**overrides` mechanism**, and add the fields to `_lead_row`'s `base` dict (defaulting to `None`) — these are now part of the `LeadOut` contract per Task 2. If you skip this, response_model validation will reject the test fixtures.

---

## Phase C — Conversions aggregation endpoint

### Task 4: Create `/admin/conversions/summary` router

**Files:**
- Create: `backend/auth_service/routers/admin_conversions.py`
- Modify: `backend/auth_service/main.py` (mount)
- Create: `backend/auth_service/tests/test_admin_conversions_router.py`

- [ ] **Step 1: Pydantic models for the response shape**

Append to `backend/auth_service/models/schemas.py`:

```python
class ConversionTimePoint(BaseModel):
    month: str            # "2026-04"
    revenue: float        # EUR sum that month
    accepted: int         # count of leads with status=accepted whose closed_at falls in this month
    sent: int             # count of leads with lead_status IN ('sent','accepted','refused') created that month


class ConversionBreakdownRow(BaseModel):
    key: str              # e.g. "Lelystad", "restaurants", "website"
    accepted: int
    revenue: float


class ConversionSummary(BaseModel):
    total_sent: int           # leads with lead_status IN ('sent','accepted','refused')
    total_accepted: int       # leads with lead_status='accepted'
    total_refused: int
    conversion_rate: float    # accepted / (sent + accepted + refused), 0..1
    total_revenue: float      # sum(closed_amount) where lead_status='accepted'
    average_deal_size: float  # total_revenue / total_accepted, 0 if no deals
    timeseries: list[ConversionTimePoint]
    by_lead_type: list[ConversionBreakdownRow]
    by_category: list[ConversionBreakdownRow]
    by_city: list[ConversionBreakdownRow]
```

- [ ] **Step 2: Write the failing tests**

Create `backend/auth_service/tests/test_admin_conversions_router.py`:

```python
"""Integration tests for routers/admin_conversions.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _patch_admin_conversions_supabase(monkeypatch, mock_supabase):
    """Bind the conversions router's get_supabase_admin to the shared mock."""
    from auth_service.routers import admin_conversions

    monkeypatch.setattr(admin_conversions, "get_supabase_admin", lambda: mock_supabase)


def test_summary_requires_admin(client, auth_as, client_user):
    auth_as(client_user)
    assert client.get("/admin/conversions/summary").status_code == 403


def test_summary_empty_dataset(mock_supabase, client, auth_as, admin_user):
    """No leads in the DB → all scalars zero, all lists empty."""
    auth_as(admin_user)
    # The router will issue multiple .execute() calls; return empty for all.
    mock_supabase.execute.return_value = MagicMock(data=[])
    resp = client.get("/admin/conversions/summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_sent"] == 0
    assert body["total_accepted"] == 0
    assert body["conversion_rate"] == 0.0
    assert body["total_revenue"] == 0.0
    assert body["timeseries"] == []
    assert body["by_lead_type"] == []


def test_summary_computes_conversion_rate(mock_supabase, client, auth_as, admin_user):
    """Given mocked aggregate rows, scalars + ratio + average size compute correctly."""
    auth_as(admin_user)
    # The router pulls all leads with status in (sent,accepted,refused)
    # and aggregates in Python — see the implementation.
    rows = [
        {"lead_status": "sent",     "closed_amount": None, "closed_at": None,                 "lead_type": "website",    "category": "restaurants", "city": "Lelystad"},
        {"lead_status": "sent",     "closed_amount": None, "closed_at": None,                 "lead_type": "website",    "category": "barber",      "city": "Almere"},
        {"lead_status": "accepted", "closed_amount": 1500, "closed_at": "2026-04-10T10:00Z",  "lead_type": "website",    "category": "restaurants", "city": "Lelystad"},
        {"lead_status": "accepted", "closed_amount": 2500, "closed_at": "2026-05-05T10:00Z",  "lead_type": "automation", "category": "barber",      "city": "Almere"},
        {"lead_status": "refused",  "closed_amount": None, "closed_at": None,                 "lead_type": "website",    "category": "barber",      "city": "Lelystad"},
    ]
    mock_supabase.execute.return_value = MagicMock(data=rows)
    resp = client.get("/admin/conversions/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_sent"] == 2          # status='sent'
    assert body["total_accepted"] == 2
    assert body["total_refused"] == 1
    assert body["conversion_rate"] == pytest.approx(2 / 5)
    assert body["total_revenue"] == 4000.0
    assert body["average_deal_size"] == 2000.0
    # Timeseries: two months with one accepted each
    months = {p["month"]: p for p in body["timeseries"]}
    assert "2026-04" in months
    assert months["2026-04"]["revenue"] == 1500.0
    assert months["2026-04"]["accepted"] == 1
    assert "2026-05" in months
    assert months["2026-05"]["revenue"] == 2500.0
    # Breakdowns
    by_type = {r["key"]: r for r in body["by_lead_type"]}
    assert by_type["website"]["accepted"] == 1
    assert by_type["automation"]["accepted"] == 1
    by_city = {r["key"]: r for r in body["by_city"]}
    assert by_city["Lelystad"]["accepted"] == 1
    assert by_city["Lelystad"]["revenue"] == 1500.0
```

- [ ] **Step 3: Run, verify FAIL**

```bash
pytest auth_service/tests/test_admin_conversions_router.py -v 2>&1 | tail -10
```

Expected: ModuleNotFoundError — router not created yet.

- [ ] **Step 4: Create the router**

Create `backend/auth_service/routers/admin_conversions.py`:

```python
"""Admin-only aggregations over public.leads for the Conversions tab.

Pulls all rows with status in (sent, accepted, refused) once, then
aggregates in Python — simpler than 4 SQL GROUP BYs and fast enough
for the current scale (< 10k leads). Replace with materialised views
when the dataset crosses 100k rows."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Query, Request

from ..models.schemas import (
    ConversionBreakdownRow,
    ConversionSummary,
    ConversionTimePoint,
)
from ..services.supabase_client import get_supabase_admin
from .deps import admin_user_via_bearer_or_sid

router = APIRouter(prefix="/admin/conversions", tags=["admin", "conversions"])


_PIPELINE_STATUSES = ("sent", "accepted", "refused")


def _month_key(iso_ts: str | None) -> str | None:
    if not iso_ts:
        return None
    # "2026-04-10T10:00:00Z" → "2026-04"
    return iso_ts[:7]


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


@router.get("/summary", response_model=ConversionSummary)
async def conversion_summary(
    request: Request,
    lead_type: str | None = Query(None),
    city: str | None = Query(None),
    category: str | None = Query(None),
    since: str | None = Query(None, description="ISO month or date; filters closed_at >= since"),
) -> ConversionSummary:
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()

    q = sb.table("leads").select(
        "lead_status, closed_amount, closed_at, lead_type, category, city"
    ).in_("lead_status", list(_PIPELINE_STATUSES))
    if lead_type:
        q = q.eq("lead_type", lead_type)
    if city:
        q = q.eq("city", city)
    if category:
        q = q.eq("category", category)
    rows: list[dict[str, Any]] = q.execute().data or []

    if since:
        # Filter timeseries-side only — keep counts for the full window so
        # conversion_rate stays meaningful. Aggregations honour the filter.
        rows = [r for r in rows if (r.get("closed_at") or "") >= since or r["lead_status"] != "accepted"]

    total_sent = sum(1 for r in rows if r["lead_status"] == "sent")
    total_accepted = sum(1 for r in rows if r["lead_status"] == "accepted")
    total_refused = sum(1 for r in rows if r["lead_status"] == "refused")
    total_revenue = sum(float(r["closed_amount"]) for r in rows if r["closed_amount"] is not None)
    denom = total_sent + total_accepted + total_refused
    conversion_rate = _safe_div(total_accepted, denom)
    average_deal_size = _safe_div(total_revenue, total_accepted)

    # Timeseries by month (closed_at)
    by_month_rev: dict[str, float] = defaultdict(float)
    by_month_acc: dict[str, int] = defaultdict(int)
    by_month_sent: dict[str, int] = defaultdict(int)
    for r in rows:
        m = _month_key(r.get("closed_at"))
        if r["lead_status"] == "accepted" and m:
            by_month_rev[m] += float(r["closed_amount"] or 0)
            by_month_acc[m] += 1
        # Sent counter approximates "leads attempted this month" — using
        # closed_at would miss un-closed leads; for v1 we count by month
        # of any pipeline-status lead (proxy). Refine later if needed.
        if m:
            by_month_sent[m] += 1
    timeseries = sorted(
        (
            ConversionTimePoint(
                month=m,
                revenue=by_month_rev[m],
                accepted=by_month_acc[m],
                sent=by_month_sent[m],
            )
            for m in set(by_month_rev) | set(by_month_acc) | set(by_month_sent)
        ),
        key=lambda p: p.month,
    )

    # Breakdowns
    def _group_by(key: str) -> list[ConversionBreakdownRow]:
        acc: dict[str, dict[str, float]] = defaultdict(lambda: {"accepted": 0, "revenue": 0.0})
        for r in rows:
            if r["lead_status"] != "accepted":
                continue
            k = r.get(key) or "(unknown)"
            acc[k]["accepted"] += 1
            acc[k]["revenue"] += float(r["closed_amount"] or 0)
        return sorted(
            (ConversionBreakdownRow(key=k, accepted=int(v["accepted"]), revenue=v["revenue"]) for k, v in acc.items()),
            key=lambda r: r.revenue,
            reverse=True,
        )

    return ConversionSummary(
        total_sent=total_sent,
        total_accepted=total_accepted,
        total_refused=total_refused,
        conversion_rate=conversion_rate,
        total_revenue=total_revenue,
        average_deal_size=average_deal_size,
        timeseries=timeseries,
        by_lead_type=_group_by("lead_type"),
        by_category=_group_by("category"),
        by_city=_group_by("city"),
    )
```

- [ ] **Step 5: Mount in `main.py`**

Find the existing `from .routers import (...)` block. Add `admin_conversions` to the list and `app.include_router(admin_conversions.router)` next to the other `admin_*` mounts.

- [ ] **Step 6: Run tests, verify PASS**

```bash
pytest auth_service/tests/test_admin_conversions_router.py -v 2>&1 | tail -15
```

Expected: 3 PASS.

- [ ] **Step 7: Full suite green**

```bash
pytest auth_service/tests/ -q 2>&1 | tail -3
```

- [ ] **Step 8: Commit**

```bash
git add backend/auth_service/routers/admin_conversions.py backend/auth_service/main.py backend/auth_service/models/schemas.py backend/auth_service/tests/test_admin_conversions_router.py
git commit -m "feat(api): GET /admin/conversions/summary — KPIs, timeseries, breakdowns"
```

---

## Phase D — Google Sheets mirror

### Task 5: Add Closed Amount + Closed Date columns to the sheets sink

**Files:**
- Modify: `scraper/src/scraper/sinks/sheets_sink.py` — find the `_FIELD_MAP` dict

- [ ] **Step 1: Edit `_FIELD_MAP`**

Add two entries:

```python
    "closed amount": lambda lead: getattr(lead, "closed_amount", None),
    "closed date": lambda lead: getattr(lead, "closed_at", None),
```

(Use `getattr` because the scraper's `Lead` Pydantic model does NOT have these fields — they're CMS-only. `getattr` returns None at scrape time, and the new sheet columns will be empty for scrape inserts. Humans fill them via the dashboard, and a follow-up sync job can re-write rows once these fields land on the scraper-side model — out of scope here.)

- [ ] **Step 2: Manually add the columns to the live sheet**

Document in a comment above `_FIELD_MAP`: the human must add two new header cells to the sheet — **"Closed Amount"** and **"Closed Date"** — so the sink's header-driven mapping picks them up. The sink reads `row_values(1)` so any column order works; if the columns aren't present, the sink ignores them harmlessly.

- [ ] **Step 3: Commit**

```bash
git add scraper/src/scraper/sinks/sheets_sink.py
git commit -m "feat(sheets): map Closed Amount + Closed Date columns (CMS-managed)"
```

**Acceptance:** the scraper continues to work whether or not the new sheet columns exist. The human adds them when ready.

---

## Phase E — Frontend: types + Recharts install

### Task 6: Extend `types.ts` and install Recharts

**Files:**
- Modify: `frontend/src/components/admin/leads/types.ts`
- Modify: `frontend/package.json` (via npm)

- [ ] **Step 1: Install Recharts**

```bash
cd frontend && npm install recharts@^2.13
```

(If version conflict with React 19 surfaces, try `recharts@^2.15`. Recharts 2.x added React 19 compat in 2.15.0+.)

- [ ] **Step 2: Add `closed_amount` + `closed_at` to `Lead` interface**

In `frontend/src/components/admin/leads/types.ts`, find `interface Lead`. Add ABOVE the `notes` field:

```typescript
  closed_amount: number | null;
  closed_at: string | null;
```

- [ ] **Step 3: Add the new `ConversionSummary` shape**

Append to `frontend/src/components/admin/leads/types.ts`:

```typescript
export interface ConversionTimePoint {
  month: string;
  revenue: number;
  accepted: number;
  sent: number;
}

export interface ConversionBreakdownRow {
  key: string;
  accepted: number;
  revenue: number;
}

export interface ConversionSummary {
  total_sent: number;
  total_accepted: number;
  total_refused: number;
  conversion_rate: number;
  total_revenue: number;
  average_deal_size: number;
  timeseries: ConversionTimePoint[];
  by_lead_type: ConversionBreakdownRow[];
  by_category: ConversionBreakdownRow[];
  by_city: ConversionBreakdownRow[];
}

export interface ConversionFilters {
  lead_type: string;
  city: string;
  category: string;
  since: string;     // ISO month, e.g. "2026-01"; "" means all-time
}

export const EMPTY_CONVERSION_FILTERS: ConversionFilters = {
  lead_type: "",
  city: "",
  category: "",
  since: "",
};
```

- [ ] **Step 4: Typecheck**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -3
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/admin/leads/types.ts
git commit -m "feat(ui): install recharts; extend Lead + ConversionSummary types"
```

---

## Phase F — Frontend: ConversionsTab orchestrator + KPI cards

### Task 7: Wire `Conversions` into the tab switcher

**Files:**
- Modify: `frontend/src/components/admin/leads/LeadsTab.tsx`

- [ ] **Step 1: Read the current LeadsTab.tsx**

Note the existing `Section = "dashboard" | "scraper"` type and the segmented control.

- [ ] **Step 2: Add the new tab**

In `LeadsTab.tsx`, change:

```typescript
type Section = "dashboard" | "scraper";
```

to:

```typescript
type Section = "dashboard" | "scraper" | "conversions";
```

In the segmented control loop, change:

```typescript
{(["dashboard", "scraper"] as Section[]).map((s) => (
  ...
  {s === "dashboard" ? "Dashboard" : "Scraper"}
```

to:

```typescript
{(["dashboard", "scraper", "conversions"] as Section[]).map((s) => (
  ...
  {s === "dashboard" ? "Dashboard" : s === "scraper" ? "Scraper" : "Conversions"}
```

In the body, change:

```typescript
{section === "dashboard" ? <LeadsDashboard /> : <ScraperControl />}
```

to:

```typescript
{section === "dashboard" ? (
  <LeadsDashboard />
) : section === "scraper" ? (
  <ScraperControl />
) : (
  <ConversionsTab />
)}
```

Add the import at the top: `import { ConversionsTab } from "./ConversionsTab";`

- [ ] **Step 3: Stub `ConversionsTab.tsx` so the build doesn't break**

Create `frontend/src/components/admin/leads/ConversionsTab.tsx`:

```tsx
"use client";

export function ConversionsTab() {
  return (
    <div className="text-sm text-zinc-500 dark:text-zinc-400">Conversions coming soon…</div>
  );
}
```

- [ ] **Step 4: Typecheck + smoke**

```bash
cd frontend && npx tsc --noEmit && npm run lint 2>&1 | tail -3
```

Restart dev server, verify the Conversions tab appears in the switcher and renders the stub.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/admin/leads/LeadsTab.tsx frontend/src/components/admin/leads/ConversionsTab.tsx
git commit -m "feat(ui): add Conversions tab stub to leads page"
```

---

### Task 8: Implement KPI cards (`ConversionStats.tsx`)

**Files:**
- Create: `frontend/src/components/admin/leads/ConversionStats.tsx`

- [ ] **Step 1: Write the component**

```tsx
"use client";

import { motion } from "framer-motion";
import { Banknote, CheckCircle2, Percent, Send, TrendingUp, XCircle } from "lucide-react";
import { staggerFast, fadeUp } from "@/lib/animations";
import type { ConversionSummary } from "./types";

interface Props {
  summary: ConversionSummary;
  loading: boolean;
}

function formatCurrency(n: number): string {
  return new Intl.NumberFormat("nl-NL", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(n);
}

function formatPercent(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

export function ConversionStats({ summary, loading }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-24 rounded-xl bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
        ))}
      </div>
    );
  }

  const stats = [
    { label: "Total revenue", value: formatCurrency(summary.total_revenue), icon: Banknote, accent: "text-emerald-600 dark:text-emerald-400" },
    { label: "Conversion rate", value: formatPercent(summary.conversion_rate), icon: Percent, accent: "text-blue-600 dark:text-blue-400" },
    { label: "Average deal", value: formatCurrency(summary.average_deal_size), icon: TrendingUp, accent: "text-violet-600 dark:text-violet-400" },
    { label: "Accepted", value: summary.total_accepted.toString(), icon: CheckCircle2, accent: "text-emerald-600 dark:text-emerald-400" },
    { label: "Sent", value: summary.total_sent.toString(), icon: Send, accent: "text-zinc-600 dark:text-zinc-400" },
    { label: "Refused", value: summary.total_refused.toString(), icon: XCircle, accent: "text-red-600 dark:text-red-400" },
  ];

  return (
    <motion.div
      variants={staggerFast}
      initial="hidden"
      animate="visible"
      className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3"
    >
      {stats.map((s) => (
        <motion.div
          key={s.label}
          variants={fadeUp}
          className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4"
        >
          <div className="flex items-center justify-between">
            <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              {s.label}
            </div>
            <s.icon className={`h-4 w-4 ${s.accent}`} />
          </div>
          <div className="mt-1 text-2xl font-semibold text-zinc-900 dark:text-zinc-100 tabular-nums">
            {s.value}
          </div>
        </motion.div>
      ))}
    </motion.div>
  );
}
```

- [ ] **Step 2: Typecheck + lint**

```bash
npx tsc --noEmit && npm run lint 2>&1 | tail -3
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/admin/leads/ConversionStats.tsx
git commit -m "feat(ui): ConversionStats — 6 KPI cards with stagger animation"
```

---

## Phase G — Charts

### Task 9: `RevenueOverTimeChart.tsx` (line chart)

**Files:**
- Create: `frontend/src/components/admin/leads/RevenueOverTimeChart.tsx`

- [ ] **Step 1: Write the component**

```tsx
"use client";

import { motion } from "framer-motion";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ConversionTimePoint } from "./types";

interface Props {
  data: ConversionTimePoint[];
}

function formatEur(n: number): string {
  return new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
}

export function RevenueOverTimeChart({ data }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4"
    >
      <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
        Revenue over time
      </h3>
      {data.length === 0 ? (
        <div className="py-12 text-center text-sm text-zinc-400 dark:text-zinc-500">
          No accepted deals yet. Close a lead with a deal amount to start tracking revenue.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} stroke="currentColor" className="text-zinc-500" />
            <YAxis tickFormatter={formatEur} tick={{ fontSize: 12 }} stroke="currentColor" className="text-zinc-500" />
            <Tooltip
              formatter={(value: number) => formatEur(value)}
              contentStyle={{ backgroundColor: "rgb(24 24 27)", border: "1px solid rgb(63 63 70)", borderRadius: 8 }}
              labelStyle={{ color: "rgb(212 212 216)" }}
            />
            <Line
              type="monotone"
              dataKey="revenue"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
              animationDuration={800}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </motion.div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/admin/leads/RevenueOverTimeChart.tsx
git commit -m "feat(ui): RevenueOverTimeChart — animated line chart of monthly revenue"
```

---

### Task 10: `BreakdownChart.tsx` (bar chart, reused for lead_type / category / city)

**Files:**
- Create: `frontend/src/components/admin/leads/BreakdownChart.tsx`

- [ ] **Step 1: Write the component**

```tsx
"use client";

import { motion } from "framer-motion";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ConversionBreakdownRow } from "./types";

interface Props {
  title: string;
  data: ConversionBreakdownRow[];
  metric: "accepted" | "revenue";
}

const PALETTE = ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#84cc16"];

function formatValue(v: number, metric: "accepted" | "revenue"): string {
  if (metric === "revenue") {
    return new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(v);
  }
  return v.toString();
}

export function BreakdownChart({ title, data, metric }: Props) {
  const top = data.slice(0, 7);   // keep bars readable
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4"
    >
      <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
        {title}
      </h3>
      {top.length === 0 ? (
        <div className="py-12 text-center text-sm text-zinc-400 dark:text-zinc-500">
          No data yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={top} layout="vertical" margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
            <XAxis
              type="number"
              tickFormatter={(v) => formatValue(v, metric)}
              tick={{ fontSize: 12 }}
              stroke="currentColor"
              className="text-zinc-500"
            />
            <YAxis type="category" dataKey="key" tick={{ fontSize: 12 }} width={100} stroke="currentColor" className="text-zinc-500" />
            <Tooltip
              formatter={(value: number) => formatValue(value, metric)}
              contentStyle={{ backgroundColor: "rgb(24 24 27)", border: "1px solid rgb(63 63 70)", borderRadius: 8 }}
              labelStyle={{ color: "rgb(212 212 216)" }}
            />
            <Bar dataKey={metric} animationDuration={800}>
              {top.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </motion.div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/admin/leads/BreakdownChart.tsx
git commit -m "feat(ui): BreakdownChart — animated bar chart (reusable for lead_type / category / city)"
```

---

## Phase H — Filters

### Task 11: `ConversionFilters.tsx`

**Files:**
- Create: `frontend/src/components/admin/leads/ConversionFilters.tsx`

- [ ] **Step 1: Write the component**

```tsx
"use client";

import { dashboardFieldLabelCn, dashboardInputCn } from "@/lib/styles";
import { AnimatedSelect } from "@/components/dashboard/AnimatedSelect";
import { LEAD_TYPE_LABEL, type LeadType } from "@/lib/leadEnums";
import type { ConversionFilters as Filters } from "./types";

interface Props {
  value: Filters;
  onChange: (v: Filters) => void;
}

export function ConversionFilters({ value, onChange }: Props) {
  function set<K extends keyof Filters>(k: K, v: Filters[K]) {
    onChange({ ...value, [k]: v });
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
      <div>
        <label className={dashboardFieldLabelCn}>From month</label>
        <input
          type="month"
          className={dashboardInputCn}
          value={value.since}
          onChange={(e) => set("since", e.target.value)}
        />
      </div>
      <div>
        <label className={dashboardFieldLabelCn}>Lead type</label>
        <AnimatedSelect
          value={value.lead_type}
          onChange={(v) => set("lead_type", v as LeadType | "")}
          ariaLabel="Lead type filter"
          options={[
            { value: "", label: "All" },
            ...(Object.keys(LEAD_TYPE_LABEL) as LeadType[]).map((k) => ({
              value: k,
              label: LEAD_TYPE_LABEL[k],
            })),
          ]}
        />
      </div>
      <div>
        <label className={dashboardFieldLabelCn}>City</label>
        <input
          type="text"
          className={dashboardInputCn}
          value={value.city}
          onChange={(e) => set("city", e.target.value)}
        />
      </div>
      <div>
        <label className={dashboardFieldLabelCn}>Category</label>
        <input
          type="text"
          className={dashboardInputCn}
          value={value.category}
          onChange={(e) => set("category", e.target.value)}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/admin/leads/ConversionFilters.tsx
git commit -m "feat(ui): ConversionFilters — date range + lead_type + city + category"
```

---

### Task 12: `ConversionsTab.tsx` — compose everything

**Files:**
- Modify: `frontend/src/components/admin/leads/ConversionsTab.tsx`

- [ ] **Step 1: Replace the stub**

```tsx
"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@/hooks/useQuery";
import { ConversionStats } from "./ConversionStats";
import { RevenueOverTimeChart } from "./RevenueOverTimeChart";
import { BreakdownChart } from "./BreakdownChart";
import { ConversionFilters } from "./ConversionFilters";
import { EMPTY_CONVERSION_FILTERS } from "./types";
import type { ConversionFilters as Filters, ConversionSummary } from "./types";

function buildQuery(f: Filters): string {
  const p = new URLSearchParams();
  if (f.lead_type) p.set("lead_type", f.lead_type);
  if (f.city) p.set("city", f.city);
  if (f.category) p.set("category", f.category);
  if (f.since) p.set("since", f.since);
  return p.toString();
}

export function ConversionsTab() {
  const [filters, setFilters] = useState<Filters>(EMPTY_CONVERSION_FILTERS);
  const qs = useMemo(() => buildQuery(filters), [filters]);

  const { data, loading } = useQuery<ConversionSummary>(
    `conversions:${qs}`,
    () =>
      fetch(`/api/admin/conversions/summary?${qs}`, { credentials: "include" }).then(async (r) => {
        if (!r.ok) throw new Error(`Failed to load conversions (${r.status})`);
        return r.json();
      }),
    { ttl: 30 * 1000 },
  );

  const summary = data ?? {
    total_sent: 0,
    total_accepted: 0,
    total_refused: 0,
    conversion_rate: 0,
    total_revenue: 0,
    average_deal_size: 0,
    timeseries: [],
    by_lead_type: [],
    by_category: [],
    by_city: [],
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
        <ConversionFilters value={filters} onChange={setFilters} />
      </div>

      <ConversionStats summary={summary} loading={loading} />

      <RevenueOverTimeChart data={summary.timeseries} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <BreakdownChart title="By lead type" data={summary.by_lead_type} metric="revenue" />
        <BreakdownChart title="By category" data={summary.by_category} metric="revenue" />
        <BreakdownChart title="By city" data={summary.by_city} metric="revenue" />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + lint**

```bash
npx tsc --noEmit && npm run lint 2>&1 | tail -3
```

- [ ] **Step 3: Manual smoke**

Restart dev server → navigate to Conversions tab. With an empty `leads` table you'll see 0s + "No data" placeholders. After accepting a few leads with `closed_amount`, the KPIs + charts populate.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/admin/leads/ConversionsTab.tsx
git commit -m "feat(ui): ConversionsTab — KPIs + revenue chart + 3 breakdown charts + filters"
```

---

## Phase I — LeadDetailDrawer: closed-amount editor

### Task 13: Add closed-deal section to drawer when `lead_status === "accepted"`

**Files:**
- Modify: `frontend/src/components/admin/leads/LeadDetailDrawer.tsx`

- [ ] **Step 1: Find the existing Notes/Pipeline section**

The drawer has a "Pipeline" section that renders `SelectField` for each status field plus a notes textarea. The closed-amount block should appear right after the Pipeline section, conditional on `lead.lead_status === "accepted"`.

- [ ] **Step 2: Add local state for the closed amount**

Inside the `DrawerBody` function, alongside the existing `notes` state, add:

```tsx
const [closedAmount, setClosedAmount] = useState<string>(
  lead.closed_amount != null ? String(lead.closed_amount) : "",
);

// Reset when lead changes.
useEffect(() => {
  setClosedAmount(lead.closed_amount != null ? String(lead.closed_amount) : "");
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [lead.id]);

// Debounced PATCH — only when value differs from server.
useEffect(() => {
  const serverValue = lead.closed_amount != null ? String(lead.closed_amount) : "";
  if (closedAmount === serverValue) return;
  const t = setTimeout(() => {
    const parsed = closedAmount.trim() === "" ? null : Number(closedAmount);
    if (closedAmount.trim() !== "" && (Number.isNaN(parsed) || (parsed as number) < 0)) {
      return;  // invalid input — wait for correction
    }
    patch({ closed_amount: parsed }).catch(() => {});
  }, 700);
  return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [closedAmount]);
```

Also extend the `patch` function signature to accept `number | null` values — change its type from `Record<string, string | null>` to `Record<string, string | number | null>` in the function signature.

- [ ] **Step 3: Render the closed-deal section conditionally**

Below the closing `</section>` of the Pipeline block, add:

```tsx
{lead.lead_status === "accepted" && (
  <section className="mt-5">
    <h3 className="text-xs uppercase tracking-wider text-emerald-600 dark:text-emerald-400 font-semibold mb-2">
      Closed deal
    </h3>
    <div className="rounded-lg border border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/30 p-3 space-y-2">
      <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
        Deal amount (EUR)
      </label>
      <div className="flex items-center gap-2">
        <span className="text-zinc-500 dark:text-zinc-400">€</span>
        <input
          type="number"
          step="0.01"
          min="0"
          className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-emerald-400"
          value={closedAmount}
          placeholder="0.00"
          onChange={(e) => setClosedAmount(e.target.value)}
        />
      </div>
      {lead.closed_at && (
        <div className="text-xs text-zinc-500 dark:text-zinc-400">
          First closed on {new Date(lead.closed_at).toLocaleDateString()}
        </div>
      )}
    </div>
  </section>
)}
```

- [ ] **Step 4: Typecheck + lint**

```bash
npx tsc --noEmit && npm run lint 2>&1 | tail -3
```

- [ ] **Step 5: Manual smoke**

1. Open a lead in the drawer
2. Change `lead_status` to `accepted` → wait for the new section to appear
3. Type a number (e.g. `1500`) → wait 700ms → PATCH fires
4. Reopen the drawer → value persists; `closed_at` line appears with today's date
5. Change lead_status back to `sent` → trying to set amount fails with 422 in network tab (expected — server-side gate)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/admin/leads/LeadDetailDrawer.tsx
git commit -m "feat(ui): LeadDetailDrawer — closed-deal section visible only when accepted"
```

---

## Phase J — Acceptance + final verification

### Task 14: End-to-end acceptance test (manual)

- [ ] **Step 1:** Run all backend + scraper tests:

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests/ -q
cd ../scraper && source .venv/Scripts/activate && pytest tests/ -q
```

Expected: backend ≥ 205 passing (was 200 + 5 new conversion tests), scraper ≥ 50 passing.

- [ ] **Step 2:** Typecheck + lint frontend:

```bash
cd ../frontend && npx tsc --noEmit && npm run lint
```

Expected: clean.

- [ ] **Step 3:** End-to-end workflow:

1. Submit a tiny scrape → 5 leads land in DB with `lead_status='not_sent'`, `closed_amount=null`
2. Open dashboard → click a lead → set `lead_status='sent'`
3. Click another lead → set `lead_status='accepted'` → green Closed Deal section appears → enter `1500` → wait 700ms → reopen → persists
4. Open Conversions tab → KPIs show 1 accepted, €1,500 revenue, 50% conversion (1 accepted / 2 in pipeline) — adjust based on real ratios
5. Revenue chart shows a single point for the current month
6. Breakdown charts show the deal grouped by lead_type / category / city
7. Refresh filters by month → empty datasets render gracefully (no chart crashes)

- [ ] **Step 4:** Sheet check:
   - Manually add "Closed Amount" + "Closed Date" columns to the Google Sheet header row
   - Re-scrape a few leads → new sheet rows have those columns empty (correct — scraper doesn't set them)
   - Future: humans manually fill / a sync job back-fills

---

## Acceptance criteria

- [ ] Migration applied; `leads.closed_amount` and `leads.closed_at` columns + indexes exist
- [ ] `LeadUpdate.closed_amount` writes are rejected (422) when `lead_status !== "accepted"`
- [ ] `closed_at` is auto-set on the first non-null `closed_amount` write
- [ ] `GET /admin/conversions/summary` returns the 6 scalars + timeseries + 3 breakdowns
- [ ] Conversions tab visible alongside Dashboard + Scraper, admin-only
- [ ] 6 KPI cards animate in with stagger
- [ ] Revenue line chart + 3 breakdown bar charts animate on mount
- [ ] Closed-deal section in LeadDetailDrawer is **conditional on `lead_status === "accepted"`**; debounced 700ms PATCH; `closed_at` timestamp shown after first save
- [ ] Filters (since, lead_type, city, category) actually narrow the API result
- [ ] Sheets sink picks up "Closed Amount" / "Closed Date" columns when they exist on the sheet
- [ ] Backend test suite green; frontend typecheck + lint clean

---

## Self-Review

**1. Spec coverage:**
- "New tab Conversions" → Task 7
- "Percentage conversion sent→accepted" → Task 4 (`conversion_rate`), Task 8 (KPI card)
- "Financial dashboard, revenue coming in" → Task 4 (`total_revenue`), Task 8 + 9
- "Closed clients by lead_type / category / city / services" → Task 4 (3 breakdowns), Task 10 (3 charts)
- "Sum of money" → Task 4 + 8 + 9
- "Modern interactive dashboard with all settings" → Task 11 (filters)
- "Nice graph animations + progress over time" → Task 9 (line chart), Recharts built-in `animationDuration` + framer-motion fade-up on mount
- "Editable closed-amount field after accepted" → Task 13
- "Field in Supabase" → Task 1
- "Field in Excel/Sheet" → Task 5

**2. Placeholder scan:** no TBDs; every step has concrete code and exact commands.

**3. Type consistency:**
- `closed_amount: float | None` Python ↔ `number | null` TS ↔ `NUMERIC(12,2)` SQL — consistent
- `closed_at: str | None` Python ↔ `string | null` TS ↔ `TIMESTAMPTZ` SQL — consistent
- `ConversionSummary` shape identical Python ↔ TS
- `ConversionFilters` only on TS side (just query-string params) — fine

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-20-conversions-dashboard.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session.

**Which approach?**
