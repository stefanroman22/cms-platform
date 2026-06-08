# Lead Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Location, Contact, Design prompt, Opening hours, and About-this-business sections of the Lead Detail drawer editable, with one section in edit mode at a time, framer-motion reveal, a TipTap rich-text editor for Design prompt, and a single shared PATCH endpoint with light client validation + server defense-in-depth.

**Architecture:** Per-section pencil → edit reveal driven by a drawer-level `EditingSectionContext`. Each section is its own component under `frontend/src/components/admin/leads/sections/`, sharing an `EditableSectionShell` (header chrome + framer reveal) and a `useLeadPatch(leadId)` hook (wraps `PATCH /api/admin/leads/{id}` and the `onPatched` glue). Backend expands the `LeadUpdate` Pydantic whitelist to include the new fields, plus a virtual `about_attributes` field that the router merges into `extra.attributes` so unrelated `extra` keys survive. Design prompt HTML is sanitized server-side with `bleach` before being persisted.

**Tech Stack:** Next.js 16 App Router + React + TypeScript + Tailwind v4 + framer-motion (existing). New deps: `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-link`, `@tailwindcss/typography`, `bleach` (Python).

**Spec:** [docs/superpowers/specs/2026-05-21-lead-editing-design.md](../specs/2026-05-21-lead-editing-design.md)

---

## Commit policy

Per the user's `no-auto-commit` preference, **do not run `git commit` unilaterally**. Each task ends with a `git add` + a pause for Stefan to inspect the diff and approve the commit. Commit messages in this plan are suggested, not auto-executed.

## Pre-flight

- Backend dev server: `cd backend && source venv/Scripts/activate && uvicorn auth_service.main:app --reload --port 8002 --host 127.0.0.1` (port 8001 has an orphaned socket).
- Frontend dev server: `cd frontend && FASTAPI_URL=http://localhost:8002 npm run dev`.
- Branch: `feat/lead-scraper-system` (already current).

---

## Phase A — Backend

### Task A1: Add `bleach` to backend deps

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements.lock`

- [ ] **Step 1: Add `bleach` to `requirements.txt`**

Append the following line to `backend/requirements.txt` (alphabetically sorted within its group; if there's no clear group, add it near `pydantic`):

```text
bleach==6.2.0
```

- [ ] **Step 2: Regenerate the lock file**

Run from the repo root:

```bash
cd backend && source venv/Scripts/activate && pip install bleach==6.2.0 && pip-compile --generate-hashes --output-file=requirements.lock requirements.txt
```

Expected: `requirements.lock` updates to include `bleach==6.2.0 --hash=...` and its transitive dep `webencodings`.

- [ ] **Step 3: Verify import works**

```bash
python -c "import bleach; print(bleach.__version__)"
```

Expected output: `6.2.0`

- [ ] **Step 4: Stage**

```bash
git add backend/requirements.txt backend/requirements.lock
```

**Suggested commit:** `chore(backend): add bleach for HTML sanitization`

---

### Task A2: Expand `LeadUpdate` schema with location + contact + design_prompt + opening_hours

**Files:**
- Modify: `backend/auth_service/models/schemas.py` (around `class LeadUpdate`)
- Test: `backend/auth_service/tests/test_admin_leads_router.py`

- [ ] **Step 1: Write the failing test (single round-trip with all the new fields)**

Append to `backend/auth_service/tests/test_admin_leads_router.py`:

```python
def test_patch_location_and_contact_fields(mock_supabase, client, auth_as, admin_user):
    """Patching location + contact fields persists each one. exclude_unset
    keeps them in the patch dict; HttpUrl / EmailStr coerce to str before DB."""
    auth_as(admin_user)
    updated = _lead_row(
        address="Main St 1",
        city="Lelystad",
        country="NL",
        postal_code="8232",
        lat=52.5,
        lng=5.5,
        phone="+31 6 12345678",
        email="hi@acme.test",
        website_url="https://acme.test/",
        facebook_url="https://facebook.com/acme",
        instagram_url="https://instagram.com/acme",
        menu_url="https://acme.test/menu",
    )
    mock_supabase.execute.return_value = MagicMock(data=[updated])
    resp = client.patch(
        "/admin/leads/lead-1",
        json={
            "address": "Main St 1",
            "city": "Lelystad",
            "country": "NL",
            "postal_code": "8232",
            "lat": 52.5,
            "lng": 5.5,
            "phone": "+31 6 12345678",
            "email": "hi@acme.test",
            "website_url": "https://acme.test/",
            "facebook_url": "https://facebook.com/acme",
            "instagram_url": "https://instagram.com/acme",
            "menu_url": "https://acme.test/menu",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["address"] == "Main St 1"
    assert body["email"] == "hi@acme.test"
    assert body["website_url"] == "https://acme.test/"


def test_patch_design_prompt_plain_text(mock_supabase, client, auth_as, admin_user):
    """design_prompt accepts arbitrary text and persists it."""
    auth_as(admin_user)
    updated = _lead_row(design_prompt="<p>Modern, minimal, dark.</p>")
    mock_supabase.execute.return_value = MagicMock(data=[updated])
    resp = client.patch(
        "/admin/leads/lead-1",
        json={"design_prompt": "<p>Modern, minimal, dark.</p>"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["design_prompt"] == "<p>Modern, minimal, dark.</p>"


def test_patch_opening_hours_replaces_map(mock_supabase, client, auth_as, admin_user):
    """opening_hours is a full replacement of the day->string map."""
    auth_as(admin_user)
    hours = {"Monday": "9–17", "Tuesday": "Closed"}
    updated = _lead_row(opening_hours=hours)
    mock_supabase.execute.return_value = MagicMock(data=[updated])
    resp = client.patch("/admin/leads/lead-1", json={"opening_hours": hours})
    assert resp.status_code == 200, resp.text
    assert resp.json()["opening_hours"] == hours


def test_patch_invalid_email_returns_422(client, auth_as, admin_user):
    """Pydantic EmailStr rejects malformed emails with 422 — no DB write."""
    auth_as(admin_user)
    resp = client.patch("/admin/leads/lead-1", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_patch_invalid_url_returns_422(client, auth_as, admin_user):
    """Pydantic HttpUrl rejects malformed URLs with 422."""
    auth_as(admin_user)
    resp = client.patch("/admin/leads/lead-1", json={"website_url": "not a url"})
    assert resp.status_code == 422
```

Extend `_lead_row` defaults so the new fields exist on returned rows. Replace its body with:

```python
def _lead_row(**overrides):
    base = {
        "id": "lead-1",
        "external_id": "ext-1",
        "primary_source": "google_maps",
        "lead_type": "website",
        "business_name": "Acme",
        "name_normalized": "acme",
        "web_presence": "none",
        "website_build_status": "not_started",
        "ai_workflow_status": "not_started",
        "lead_status": "not_sent",
        "lead_contact_type": "not_contacted",
        "payment_status": "not_applicable",
        "extra": {},
        "photo_urls": [],
        "address": None,
        "city": None,
        "country": None,
        "postal_code": None,
        "lat": None,
        "lng": None,
        "phone": None,
        "email": None,
        "website_url": None,
        "facebook_url": None,
        "instagram_url": None,
        "menu_url": None,
        "design_prompt": None,
        "opening_hours": None,
        "closed_amount": None,
        "closed_at": None,
        "created_at": "2026-05-17T10:00:00Z",
        "updated_at": "2026-05-17T10:00:00Z",
    }
    base.update(overrides)
    return base
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && source venv/Scripts/activate && pytest auth_service/tests/test_admin_leads_router.py -v -k "location_and_contact or design_prompt_plain_text or opening_hours_replaces or invalid_email or invalid_url"
```

Expected: 5 FAILS — fields not on `LeadUpdate`, so Pydantic strips them, patch becomes empty, server returns 422 "No fields to update" (wrong message) OR Pydantic rejects unknown fields.

- [ ] **Step 3: Expand `LeadUpdate` and `LeadOut`**

In `backend/auth_service/models/schemas.py`, find `class LeadUpdate(BaseModel):` (around line 471). Replace the entire class with:

```python
from pydantic import EmailStr, HttpUrl

class LeadUpdate(BaseModel):
    """Only pipeline-status + scraped-data fields are editable from the admin tab.
    Everything else is owned by the scraper or the future AI agent."""

    # pipeline (existing)
    website_build_status: WebsiteBuildStatus | None = None
    ai_workflow_status: AiWorkflowStatus | None = None
    lead_status: LeadStatus | None = None
    lead_contact_type: LeadContactType | None = None
    payment_status: PaymentStatus | None = None
    notes: str | None = None
    closed_amount: float | None = None

    # location
    address: str | None = None
    city: str | None = None
    country: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None

    # contact
    phone: str | None = None
    email: EmailStr | None = None
    website_url: HttpUrl | None = None
    facebook_url: HttpUrl | None = None
    instagram_url: HttpUrl | None = None
    menu_url: HttpUrl | None = None

    # design prompt — sanitized HTML (server-side bleach allow-list)
    design_prompt: str | None = None

    # opening hours — full replacement of the day -> string map
    opening_hours: dict[str, str] | None = None

    # about — virtual field; router merges into extra.attributes
    about_attributes: dict[str, dict[str, bool]] | None = None
```

Also add to `LeadOut` (same file, around line 458) the fields that aren't already on it: it already has `address`, `city`, `country`, `postal_code`, `lat`, `lng`, `phone`, `email`, `website_url`, `facebook_url`, `instagram_url`, `menu_url`, `design_prompt`, `opening_hours`. **Verify** by reading the existing class; add only the missing ones, if any. If `opening_hours` is typed as `dict | None` already, no change needed.

If `EmailStr` import is new, also add `email-validator` is already in `requirements.lock` (verified pre-flight) — no extra dependency needed.

- [ ] **Step 4: Convert HttpUrl / EmailStr to str before Supabase**

In `backend/auth_service/routers/admin_leads.py`, inside `patch_lead`, right after `patch = dict(body.model_dump(exclude_unset=True))`, add:

```python
# HttpUrl / EmailStr are pydantic types; Supabase wants plain strings.
for url_field in ("website_url", "facebook_url", "instagram_url", "menu_url"):
    if url_field in patch and patch[url_field] is not None:
        patch[url_field] = str(patch[url_field])
if "email" in patch and patch["email"] is not None:
    patch["email"] = str(patch["email"])
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest auth_service/tests/test_admin_leads_router.py -v -k "location_and_contact or design_prompt_plain_text or opening_hours_replaces or invalid_email or invalid_url"
```

Expected: 5 PASS.

- [ ] **Step 6: Run full backend test suite to catch regressions**

```bash
pytest auth_service/tests/ -v
```

Expected: all PASS.

- [ ] **Step 7: Stage**

```bash
git add backend/auth_service/models/schemas.py backend/auth_service/routers/admin_leads.py backend/auth_service/tests/test_admin_leads_router.py
```

**Suggested commit:** `feat(api): expand LeadUpdate whitelist with location/contact/design_prompt/opening_hours`

---

### Task A3: HTML sanitization for `design_prompt`

**Files:**
- Create: `backend/auth_service/services/html_sanitizer.py`
- Modify: `backend/auth_service/routers/admin_leads.py`
- Test: `backend/auth_service/tests/test_admin_leads_router.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/auth_service/tests/test_admin_leads_router.py`:

```python
def test_patch_design_prompt_strips_script_tags(mock_supabase, client, auth_as, admin_user):
    """Server-side bleach must strip dangerous tags before persisting."""
    auth_as(admin_user)
    # Capture what gets sent to Supabase .update(...)
    captured = {}

    def capture_update(payload):
        captured["payload"] = payload
        # Return a chainable mock so .eq(...).execute() works.
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(
            data=[_lead_row(design_prompt=payload["design_prompt"])]
        )
        return chain

    mock_supabase.update.side_effect = capture_update

    resp = client.patch(
        "/admin/leads/lead-1",
        json={"design_prompt": "<p>hi</p><script>alert(1)</script>"},
    )
    assert resp.status_code == 200, resp.text
    # script tag stripped, <p>hi</p> preserved
    assert "<script>" not in captured["payload"]["design_prompt"]
    assert "<p>hi</p>" in captured["payload"]["design_prompt"]


def test_patch_design_prompt_preserves_allowed_formatting(mock_supabase, client, auth_as, admin_user):
    """Bold, italic, headings, lists, links must survive sanitization."""
    auth_as(admin_user)
    captured = {}

    def capture_update(payload):
        captured["payload"] = payload
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(
            data=[_lead_row(design_prompt=payload["design_prompt"])]
        )
        return chain

    mock_supabase.update.side_effect = capture_update

    html = (
        "<h2>Brief</h2>"
        "<p><strong>Bold</strong> <em>italic</em></p>"
        "<ul><li>Point</li></ul>"
        '<a href="https://example.com">link</a>'
    )
    resp = client.patch("/admin/leads/lead-1", json={"design_prompt": html})
    assert resp.status_code == 200, resp.text
    saved = captured["payload"]["design_prompt"]
    assert "<h2>Brief</h2>" in saved
    assert "<strong>Bold</strong>" in saved
    assert "<em>italic</em>" in saved
    assert "<ul>" in saved and "<li>Point</li>" in saved
    assert 'href="https://example.com"' in saved
    # Forced safety attrs on <a>
    assert 'rel="noopener nofollow"' in saved
    assert 'target="_blank"' in saved
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest auth_service/tests/test_admin_leads_router.py -v -k "design_prompt_strips_script or design_prompt_preserves"
```

Expected: 2 FAILS — script tag not stripped; no rel/target forced.

- [ ] **Step 3: Create the sanitizer module**

Create `backend/auth_service/services/html_sanitizer.py`:

```python
"""Single source of truth for the HTML allow-list used by user-authored
fields (currently only leads.design_prompt). Run every UGC HTML string
through `sanitize_design_prompt()` before persisting it."""

import bleach

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "code", "pre",
    "h1", "h2", "h3",
    "ul", "ol", "li",
    "a",
}

ALLOWED_ATTRS = {
    "a": ["href", "title"],
}


def sanitize_design_prompt(html: str) -> str:
    """Strip every tag/attribute outside the allow-list. Force noopener
    nofollow and target=_blank on anchors so a malicious link can't break
    the admin tab via window.opener or get reputation-weighted by Google."""
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True,
    )
    cleaned = cleaned.replace("<a ", '<a rel="noopener nofollow" target="_blank" ')
    return cleaned
```

- [ ] **Step 4: Apply the sanitizer in the router**

In `backend/auth_service/routers/admin_leads.py`, add the import at the top:

```python
from ..services.html_sanitizer import sanitize_design_prompt
```

Inside `patch_lead`, right after the URL-coercion block from Task A2, add:

```python
if "design_prompt" in patch and patch["design_prompt"] is not None:
    patch["design_prompt"] = sanitize_design_prompt(patch["design_prompt"])
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest auth_service/tests/test_admin_leads_router.py -v -k "design_prompt_strips_script or design_prompt_preserves"
```

Expected: 2 PASS.

- [ ] **Step 6: Stage**

```bash
git add backend/auth_service/services/html_sanitizer.py backend/auth_service/routers/admin_leads.py backend/auth_service/tests/test_admin_leads_router.py
```

**Suggested commit:** `feat(api): sanitize lead design_prompt HTML via bleach allow-list`

---

### Task A4: `about_attributes` virtual field — merge into `extra.attributes`

**Files:**
- Modify: `backend/auth_service/routers/admin_leads.py`
- Test: `backend/auth_service/tests/test_admin_leads_router.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/auth_service/tests/test_admin_leads_router.py`:

```python
def test_patch_about_attributes_merges_into_extra(mock_supabase, client, auth_as, admin_user):
    """about_attributes is a virtual field: the router fetches the current
    row's extra, replaces extra.attributes with the new map, and writes the
    merged extra back. Other extra keys must survive untouched."""
    auth_as(admin_user)
    new_attrs = {"Service options": {"Dine-in": True, "Takeout": False}}
    captured = {}

    def capture_update(payload):
        captured["payload"] = payload
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(
            data=[_lead_row(extra={"scraped_at": "2026-05-17", "attributes": new_attrs})]
        )
        return chain

    mock_supabase.update.side_effect = capture_update
    # The current-row fetch returns extra with an unrelated key.
    mock_supabase.execute.return_value = MagicMock(
        data={"lead_status": "not_sent", "closed_amount": None, "extra": {"scraped_at": "2026-05-17", "attributes": {"old": {"x": True}}}}
    )

    resp = client.patch(
        "/admin/leads/lead-1",
        json={"about_attributes": new_attrs},
    )
    assert resp.status_code == 200, resp.text
    # Payload to Supabase must have extra (not about_attributes) with both keys.
    assert "about_attributes" not in captured["payload"]
    assert captured["payload"]["extra"]["attributes"] == new_attrs
    assert captured["payload"]["extra"]["scraped_at"] == "2026-05-17"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest auth_service/tests/test_admin_leads_router.py -v -k "about_attributes_merges_into_extra"
```

Expected: FAIL — `about_attributes` reaches Supabase verbatim (unknown column error or silently ignored).

- [ ] **Step 3: Extend `patch_lead` to handle `about_attributes`**

In `backend/auth_service/routers/admin_leads.py`, modify the block that currently fetches the current row only when `closed_amount` is in the patch. Replace it with a unified fetch when either `closed_amount` or `about_attributes` is present, and add the merge:

```python
needs_current = "closed_amount" in patch or "about_attributes" in patch
if needs_current:
    current = (
        sb.table("leads")
        .select("lead_status, closed_amount, extra")
        .eq("id", lead_id)
        .maybe_single()
        .execute()
    )
    if not current.data:
        raise HTTPException(status_code=404, detail="Lead not found")

if "closed_amount" in patch:
    new_status = patch.get("lead_status", current.data["lead_status"])
    if new_status != "accepted":
        raise HTTPException(
            status_code=422,
            detail="closed_amount can only be set when lead_status is 'accepted'",
        )
    if current.data["closed_amount"] is None and patch["closed_amount"] is not None:
        patch["closed_at"] = datetime.now(UTC).isoformat()

if "about_attributes" in patch:
    new_attrs = patch.pop("about_attributes")
    current_extra = current.data.get("extra") or {}
    if not isinstance(current_extra, dict):
        current_extra = {}
    current_extra["attributes"] = new_attrs
    patch["extra"] = current_extra
```

(Delete the old `if "closed_amount" in patch:` block that did its own fetch — the unified fetch replaces it.)

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest auth_service/tests/test_admin_leads_router.py -v -k "about_attributes_merges_into_extra"
```

Expected: PASS.

- [ ] **Step 5: Run full backend suite — the closed_amount tests must still pass**

```bash
pytest auth_service/tests/ -v
```

Expected: all PASS, including the four pre-existing `test_patch_closed_amount_*` cases.

- [ ] **Step 6: Stage**

```bash
git add backend/auth_service/routers/admin_leads.py backend/auth_service/tests/test_admin_leads_router.py
```

**Suggested commit:** `feat(api): about_attributes virtual field merges into leads.extra.attributes`

---

## Phase B — Frontend infrastructure

### Task B1: Add TipTap + tailwind-typography deps

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/postcss.config.mjs` or `frontend/src/app/globals.css` (Tailwind v4 plugin registration)

- [ ] **Step 1: Install deps**

```bash
cd frontend && npm install @tiptap/react@^3 @tiptap/starter-kit@^3 @tiptap/extension-link@^3 @tailwindcss/typography@^0.5
```

Expected: dependencies appear under `dependencies` in `package.json`.

- [ ] **Step 2: Register the typography plugin in Tailwind v4**

Tailwind v4 registers plugins inside the CSS file via `@plugin`. Open `frontend/src/app/globals.css`, find the `@import "tailwindcss"` line at the top, and immediately below it add:

```css
@plugin "@tailwindcss/typography";
```

(If the file uses a different Tailwind entry path, place the `@plugin` directive directly after wherever `tailwindcss` is imported. Do not add it at the end of the file.)

- [ ] **Step 3: Verify type-check + dev build pass**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no new TS errors.

```bash
npm run dev
```

Visit http://localhost:3000/dashboard/admin/leads — page should still render without runtime errors. Kill the dev server when done.

- [ ] **Step 4: Stage**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/app/globals.css
```

**Suggested commit:** `chore(frontend): add TipTap + tailwind typography for rich text editing`

---

### Task B2: Add framer-motion variants to `animations.ts`

**Files:**
- Modify: `frontend/src/lib/animations.ts`

- [ ] **Step 1: Read the existing file to match style**

```bash
cat frontend/src/lib/animations.ts
```

Note the existing `fadeUp`, `staggerFast` style.

- [ ] **Step 2: Append the three new variants**

Append to `frontend/src/lib/animations.ts`:

```ts
export const editReveal = {
  hidden: { height: 0, opacity: 0 },
  visible: {
    height: "auto" as const,
    opacity: 1,
    transition: { duration: 0.22, ease: "easeOut" as const },
  },
};

export const rowAdd = {
  hidden: { x: -8, opacity: 0 },
  visible: {
    x: 0,
    opacity: 1,
    transition: { duration: 0.18, ease: "easeOut" as const },
  },
};

export const errorBlip = {
  hidden: { y: -2, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { duration: 0.16, ease: "easeOut" as const },
  },
};
```

- [ ] **Step 3: Verify type-check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Stage**

```bash
git add frontend/src/lib/animations.ts
```

**Suggested commit:** `feat(ui): editReveal/rowAdd/errorBlip animation variants`

---

### Task B3: Create `EditingSectionContext`

**Files:**
- Create: `frontend/src/components/admin/leads/context/EditingSectionContext.tsx`

- [ ] **Step 1: Write the file**

```tsx
"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

interface Ctx {
  editingId: string | null;
  /** Returns true if this section now holds the edit slot. */
  requestEdit: (id: string) => boolean;
  /** Releases the slot if this section currently holds it. */
  release: (id: string) => void;
}

const EditingSectionContext = createContext<Ctx | null>(null);

export function EditingSectionProvider({ children }: { children: ReactNode }) {
  const [editingId, setEditingId] = useState<string | null>(null);

  const requestEdit = useCallback((id: string) => {
    setEditingId(id);
    return true;
  }, []);

  const release = useCallback((id: string) => {
    setEditingId((curr) => (curr === id ? null : curr));
  }, []);

  return (
    <EditingSectionContext.Provider value={{ editingId, requestEdit, release }}>
      {children}
    </EditingSectionContext.Provider>
  );
}

export function useEditingSection(id: string) {
  const ctx = useContext(EditingSectionContext);
  if (!ctx) throw new Error("useEditingSection must be used inside EditingSectionProvider");
  return {
    isEditing: ctx.editingId === id,
    isAnyEditing: ctx.editingId !== null,
    requestEdit: () => ctx.requestEdit(id),
    release: () => ctx.release(id),
  };
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Stage**

```bash
git add frontend/src/components/admin/leads/context/EditingSectionContext.tsx
```

**Suggested commit:** `feat(ui): EditingSectionContext for one-at-a-time edit slot`

---

### Task B4: Create `useLeadPatch` hook

**Files:**
- Create: `frontend/src/components/admin/leads/hooks/useLeadPatch.ts`

- [ ] **Step 1: Write the hook**

```ts
"use client";

import { useCallback, useState } from "react";
import type { Lead } from "../types";

export interface LeadUpdatePayload {
  // pipeline
  lead_status?: string;
  website_build_status?: string;
  ai_workflow_status?: string;
  lead_contact_type?: string;
  payment_status?: string;
  notes?: string | null;
  closed_amount?: number | null;
  // location
  address?: string | null;
  city?: string | null;
  country?: string | null;
  postal_code?: string | null;
  lat?: number | null;
  lng?: number | null;
  // contact
  phone?: string | null;
  email?: string | null;
  website_url?: string | null;
  facebook_url?: string | null;
  instagram_url?: string | null;
  menu_url?: string | null;
  // design prompt
  design_prompt?: string | null;
  // opening hours — full replacement of the day -> string map
  opening_hours?: Record<string, string> | null;
  // about — virtual field; backend merges into extra.attributes
  about_attributes?: Record<string, Record<string, boolean>> | null;
}

export interface UseLeadPatchResult {
  patch: (body: LeadUpdatePayload) => Promise<Lead>;
  saving: boolean;
  error: string | null;
  clearError: () => void;
}

export function useLeadPatch(
  leadId: string,
  onPatched: (lead: Lead) => void,
): UseLeadPatchResult {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const patch = useCallback(
    async (body: LeadUpdatePayload): Promise<Lead> => {
      setSaving(true);
      setError(null);
      try {
        const res = await fetch(`/api/admin/leads/${leadId}`, {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const detail = (await res.json().catch(() => ({}))) as { detail?: string };
          throw new Error(detail.detail ?? `Update failed (${res.status})`);
        }
        const updated = (await res.json()) as Lead;
        onPatched(updated);
        return updated;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Update failed";
        setError(msg);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [leadId, onPatched],
  );

  return { patch, saving, error, clearError: () => setError(null) };
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Stage**

```bash
git add frontend/src/components/admin/leads/hooks/useLeadPatch.ts
```

**Suggested commit:** `feat(ui): useLeadPatch hook for PATCH /admin/leads/{id}`

---

### Task B5: Create `EditableSectionShell` (read/edit chrome + reveal)

**Files:**
- Create: `frontend/src/components/admin/leads/sections/EditableSectionShell.tsx`
- Test: `frontend/src/components/admin/leads/sections/__tests__/EditableSectionShell.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/admin/leads/sections/__tests__/EditableSectionShell.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { EditableSectionShell } from "../EditableSectionShell";

function setup(props: Partial<React.ComponentProps<typeof EditableSectionShell>> = {}) {
  const onSave = vi.fn().mockResolvedValue(undefined);
  const onCancel = vi.fn();
  render(
    <EditingSectionProvider>
      <EditableSectionShell
        id="test"
        title="Test"
        readView={<div>READ</div>}
        editView={<div>EDIT</div>}
        onSave={onSave}
        onCancel={onCancel}
        saving={false}
        error={null}
        canSave
        {...props}
      />
    </EditingSectionProvider>,
  );
  return { onSave, onCancel };
}

describe("EditableSectionShell", () => {
  it("shows the read view by default", () => {
    setup();
    expect(screen.getByText("READ")).toBeTruthy();
    expect(screen.queryByText("EDIT")).toBeNull();
  });

  it("reveals the edit view when the pencil is clicked", () => {
    setup();
    fireEvent.click(screen.getByLabelText("Edit Test"));
    expect(screen.getByText("EDIT")).toBeTruthy();
  });

  it("calls onSave when Save is clicked", async () => {
    const { onSave } = setup();
    fireEvent.click(screen.getByLabelText("Edit Test"));
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel and returns to read view when Cancel is clicked", () => {
    const { onCancel } = setup();
    fireEvent.click(screen.getByLabelText("Edit Test"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(screen.getByText("READ")).toBeTruthy();
  });

  it("disables Save when canSave is false", () => {
    setup({ canSave: false });
    fireEvent.click(screen.getByLabelText("Edit Test"));
    const saveBtn = screen.getByText("Save").closest("button")!;
    expect(saveBtn.hasAttribute("disabled")).toBe(true);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail (component missing)**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/EditableSectionShell.test.tsx
```

Expected: 5 FAILS — module `../EditableSectionShell` not found.

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/admin/leads/sections/EditableSectionShell.tsx`:

```tsx
"use client";

import { useEffect, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Pencil, Save, X } from "lucide-react";
import { editReveal, errorBlip } from "@/lib/animations";
import { useEditingSection } from "../context/EditingSectionContext";

export interface EditableSectionShellProps {
  /** Stable id, used as the EditingSectionContext slot key. */
  id: string;
  title: string;
  readView: ReactNode;
  editView: ReactNode;
  onSave: () => Promise<void> | void;
  onCancel: () => void;
  saving: boolean;
  error: string | null;
  canSave: boolean;
}

export function EditableSectionShell({
  id,
  title,
  readView,
  editView,
  onSave,
  onCancel,
  saving,
  error,
  canSave,
}: EditableSectionShellProps) {
  const { isEditing, requestEdit, release } = useEditingSection(id);

  // ESC closes edit mode; Cmd/Ctrl+S saves.
  useEffect(() => {
    if (!isEditing) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        handleCancel();
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (canSave && !saving) void onSave();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditing, canSave, saving]);

  function handleStartEdit() {
    requestEdit();
  }

  function handleCancel() {
    onCancel();
    release();
  }

  async function handleSave() {
    try {
      await onSave();
      release();
    } catch {
      // error is surfaced via the `error` prop; stay in edit mode.
    }
  }

  return (
    <section className="mt-5 group">
      <div className="flex items-center justify-between mb-2 min-h-[1.25rem]">
        <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold">
          {title}
        </h3>
        {isEditing ? (
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleCancel}
              disabled={saving}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-md text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <X className="h-3 w-3" />
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={!canSave || saving}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-md bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
            >
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
              Save
            </button>
          </div>
        ) : (
          <button
            type="button"
            aria-label={`Edit ${title}`}
            onClick={handleStartEdit}
            className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity inline-flex items-center justify-center h-6 w-6 rounded-md text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <AnimatePresence initial={false}>
        {error && (
          <motion.div
            key="err"
            variants={errorBlip}
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="mb-2 rounded-md bg-red-50 dark:bg-red-950 px-3 py-1.5 text-xs text-red-700 dark:text-red-300"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait" initial={false}>
        {isEditing ? (
          <motion.div
            key="edit"
            variants={editReveal}
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="overflow-hidden"
          >
            {editView}
          </motion.div>
        ) : (
          <motion.div
            key="read"
            variants={editReveal}
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="overflow-hidden"
          >
            {readView}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/EditableSectionShell.test.tsx
```

Expected: 5 PASS.

- [ ] **Step 5: Stage**

```bash
git add frontend/src/components/admin/leads/sections/EditableSectionShell.tsx frontend/src/components/admin/leads/sections/__tests__/EditableSectionShell.test.tsx
```

**Suggested commit:** `feat(ui): EditableSectionShell — pencil/Save/Cancel chrome + reveal`

---

## Phase C — Section components

Each section follows the same template: read view, edit view, local draft state, validation, `patch()` call. Tests for each section assert (a) pencil reveals edit view, (b) Save with no change is a no-op, (c) Save with a change calls the patch hook with the right diff.

### Task C1: `LocationSection`

**Files:**
- Create: `frontend/src/components/admin/leads/sections/LocationSection.tsx`
- Test: `frontend/src/components/admin/leads/sections/__tests__/LocationSection.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/admin/leads/sections/__tests__/LocationSection.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { LocationSection } from "../LocationSection";
import type { Lead } from "../../types";

const baseLead = {
  id: "lead-1",
  address: "Main 1",
  city: "Lelystad",
  country: "NL",
  postal_code: "8232",
  lat: 52.5,
  lng: 5.5,
} as unknown as Lead;

describe("LocationSection", () => {
  it("renders address read row", () => {
    render(
      <EditingSectionProvider>
        <LocationSection lead={baseLead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    expect(screen.getByText("Main 1")).toBeTruthy();
  });

  it("flags lat/lng error when only one is set", () => {
    render(
      <EditingSectionProvider>
        <LocationSection lead={baseLead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    fireEvent.click(screen.getByLabelText("Edit Location"));
    const lng = screen.getByLabelText("Longitude") as HTMLInputElement;
    fireEvent.change(lng, { target: { value: "" } });
    expect(screen.getByText(/both latitude and longitude/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/LocationSection.test.tsx
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the section**

Create `frontend/src/components/admin/leads/sections/LocationSection.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch, type LeadUpdatePayload } from "../hooks/useLeadPatch";

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

export function LocationSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);

  const [address, setAddress] = useState(lead.address ?? "");
  const [city, setCity] = useState(lead.city ?? "");
  const [country, setCountry] = useState(lead.country ?? "");
  const [postal, setPostal] = useState(lead.postal_code ?? "");
  const [lat, setLat] = useState(lead.lat != null ? String(lead.lat) : "");
  const [lng, setLng] = useState(lead.lng != null ? String(lead.lng) : "");

  // Reset drafts when the lead changes (different lead opened, or server patch returned).
  useEffect(() => {
    setAddress(lead.address ?? "");
    setCity(lead.city ?? "");
    setCountry(lead.country ?? "");
    setPostal(lead.postal_code ?? "");
    setLat(lead.lat != null ? String(lead.lat) : "");
    setLng(lead.lng != null ? String(lead.lng) : "");
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.address, lead.city, lead.country, lead.postal_code, lead.lat, lead.lng]);

  // Validation
  const latNum = lat.trim() === "" ? null : Number(lat);
  const lngNum = lng.trim() === "" ? null : Number(lng);
  const latValid = latNum === null || (!Number.isNaN(latNum) && latNum >= -90 && latNum <= 90);
  const lngValid = lngNum === null || (!Number.isNaN(lngNum) && lngNum >= -180 && lngNum <= 180);
  const bothOrNeither = (latNum === null) === (lngNum === null);
  const latLngError = !latValid || !lngValid || !bothOrNeither
    ? !bothOrNeither
      ? "Provide both latitude and longitude, or neither."
      : !latValid
        ? "Latitude must be between -90 and 90."
        : "Longitude must be between -180 and 180."
    : null;

  function buildDiff(): LeadUpdatePayload {
    const out: LeadUpdatePayload = {};
    const a = address.trim() === "" ? null : address.trim();
    if (a !== (lead.address ?? null)) out.address = a;
    const c = city.trim() === "" ? null : city.trim();
    if (c !== (lead.city ?? null)) out.city = c;
    const co = country.trim() === "" ? null : country.trim();
    if (co !== (lead.country ?? null)) out.country = co;
    const p = postal.trim() === "" ? null : postal.trim();
    if (p !== (lead.postal_code ?? null)) out.postal_code = p;
    if (latNum !== (lead.lat ?? null)) out.lat = latNum;
    if (lngNum !== (lead.lng ?? null)) out.lng = lngNum;
    return out;
  }

  async function handleSave() {
    const diff = buildDiff();
    if (Object.keys(diff).length === 0) return;
    await patch(diff);
  }

  function handleCancel() {
    // Drafts reset via the lead-id useEffect when onPatched fires; on plain
    // Cancel (no save), re-sync to the live lead.
    setAddress(lead.address ?? "");
    setCity(lead.city ?? "");
    setCountry(lead.country ?? "");
    setPostal(lead.postal_code ?? "");
    setLat(lead.lat != null ? String(lead.lat) : "");
    setLng(lead.lng != null ? String(lead.lng) : "");
    clearError();
  }

  const readView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-1.5">
      <Row label="Address" value={lead.address} />
      <Row label="City" value={lead.city} />
      <Row label="Country" value={lead.country} />
      <Row label="Postal" value={lead.postal_code} />
      <Row
        label="Lat / Lng"
        value={lead.lat != null && lead.lng != null ? `${lead.lat}, ${lead.lng}` : null}
      />
    </div>
  );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Address" colSpan={2}>
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className={inputCls}
            aria-label="Address"
          />
        </Field>
        <Field label="City">
          <input
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            className={inputCls}
            aria-label="City"
          />
        </Field>
        <Field label="Country">
          <input
            type="text"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className={inputCls}
            aria-label="Country"
          />
        </Field>
        <Field label="Postal code">
          <input
            type="text"
            value={postal}
            onChange={(e) => setPostal(e.target.value)}
            className={inputCls}
            aria-label="Postal code"
          />
        </Field>
        <div />
        <Field label="Latitude">
          <input
            type="text"
            inputMode="decimal"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
            className={inputCls}
            aria-label="Latitude"
          />
        </Field>
        <Field label="Longitude">
          <input
            type="text"
            inputMode="decimal"
            value={lng}
            onChange={(e) => setLng(e.target.value)}
            className={inputCls}
            aria-label="Longitude"
          />
        </Field>
      </div>
      {latLngError && (
        <p className="mt-2 text-xs text-red-600 dark:text-red-400">{latLngError}</p>
      )}
    </div>
  );

  return (
    <EditableSectionShell
      id="location"
      title="Location"
      readView={readView}
      editView={editView}
      onSave={handleSave}
      onCancel={handleCancel}
      saving={saving}
      error={error}
      canSave={latLngError === null}
    />
  );
}

const inputCls =
  "w-full rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600";

function Field({
  label,
  colSpan,
  children,
}: {
  label: string;
  colSpan?: 1 | 2;
  children: React.ReactNode;
}) {
  return (
    <div className={colSpan === 2 ? "col-span-2" : undefined}>
      <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-baseline gap-3 text-xs">
      <span className="text-zinc-500 dark:text-zinc-400 w-24 shrink-0">{label}</span>
      {value == null || value === "" ? (
        <span className="text-zinc-400 dark:text-zinc-600">—</span>
      ) : (
        <span className="text-zinc-900 dark:text-zinc-100 break-words">{value}</span>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/LocationSection.test.tsx
```

Expected: 2 PASS.

- [ ] **Step 5: Stage**

```bash
git add frontend/src/components/admin/leads/sections/LocationSection.tsx frontend/src/components/admin/leads/sections/__tests__/LocationSection.test.tsx
```

**Suggested commit:** `feat(ui): LocationSection — read + edit with lat/lng validation`

---

### Task C2: `ContactSection`

**Files:**
- Create: `frontend/src/components/admin/leads/sections/ContactSection.tsx`
- Test: `frontend/src/components/admin/leads/sections/__tests__/ContactSection.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/admin/leads/sections/__tests__/ContactSection.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { ContactSection } from "../ContactSection";
import type { Lead } from "../../types";

const lead = {
  id: "lead-1",
  phone: "+31",
  email: "hi@acme.test",
  website_url: "https://acme.test/",
  facebook_url: null,
  instagram_url: null,
  menu_url: null,
} as unknown as Lead;

describe("ContactSection", () => {
  it("flags invalid email", () => {
    render(
      <EditingSectionProvider>
        <ContactSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    fireEvent.click(screen.getByLabelText("Edit Contact"));
    const email = screen.getByLabelText("Email");
    fireEvent.change(email, { target: { value: "broken" } });
    expect(screen.getByText(/valid email/i)).toBeTruthy();
  });

  it("auto-prepends https:// on URL blur", () => {
    render(
      <EditingSectionProvider>
        <ContactSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    fireEvent.click(screen.getByLabelText("Edit Contact"));
    const fb = screen.getByLabelText("Facebook URL") as HTMLInputElement;
    fireEvent.change(fb, { target: { value: "facebook.com/acme" } });
    fireEvent.blur(fb);
    expect(fb.value).toBe("https://facebook.com/acme");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/ContactSection.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement the section**

Create `frontend/src/components/admin/leads/sections/ContactSection.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Facebook, Globe, Instagram, Mail, Menu, Phone } from "lucide-react";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch, type LeadUpdatePayload } from "../hooks/useLeadPatch";

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

const EMAIL_RE = /^\S+@\S+\.\S+$/;

function normalizeUrl(v: string): string {
  const t = v.trim();
  if (t === "") return "";
  if (/^https?:\/\//i.test(t)) return t;
  return `https://${t}`;
}

export function ContactSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);

  const [phone, setPhone] = useState(lead.phone ?? "");
  const [email, setEmail] = useState(lead.email ?? "");
  const [website, setWebsite] = useState(lead.website_url ?? "");
  const [facebook, setFacebook] = useState(lead.facebook_url ?? "");
  const [instagram, setInstagram] = useState(lead.instagram_url ?? "");
  const [menu, setMenu] = useState(lead.menu_url ?? "");

  useEffect(() => {
    setPhone(lead.phone ?? "");
    setEmail(lead.email ?? "");
    setWebsite(lead.website_url ?? "");
    setFacebook(lead.facebook_url ?? "");
    setInstagram(lead.instagram_url ?? "");
    setMenu(lead.menu_url ?? "");
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.phone, lead.email, lead.website_url, lead.facebook_url, lead.instagram_url, lead.menu_url]);

  const emailError =
    email.trim() === "" || EMAIL_RE.test(email.trim()) ? null : "Enter a valid email or leave empty.";
  const urlError = [website, facebook, instagram, menu].some((u) => /\s/.test(u.trim()))
    ? "URLs cannot contain spaces."
    : null;

  function buildDiff(): LeadUpdatePayload {
    const out: LeadUpdatePayload = {};
    const norm = (v: string) => (v.trim() === "" ? null : v.trim());
    const normU = (v: string) => (v.trim() === "" ? null : normalizeUrl(v));
    if (norm(phone) !== (lead.phone ?? null)) out.phone = norm(phone);
    if (norm(email) !== (lead.email ?? null)) out.email = norm(email);
    if (normU(website) !== (lead.website_url ?? null)) out.website_url = normU(website);
    if (normU(facebook) !== (lead.facebook_url ?? null)) out.facebook_url = normU(facebook);
    if (normU(instagram) !== (lead.instagram_url ?? null)) out.instagram_url = normU(instagram);
    if (normU(menu) !== (lead.menu_url ?? null)) out.menu_url = normU(menu);
    return out;
  }

  async function handleSave() {
    const diff = buildDiff();
    if (Object.keys(diff).length === 0) return;
    await patch(diff);
  }

  function handleCancel() {
    setPhone(lead.phone ?? "");
    setEmail(lead.email ?? "");
    setWebsite(lead.website_url ?? "");
    setFacebook(lead.facebook_url ?? "");
    setInstagram(lead.instagram_url ?? "");
    setMenu(lead.menu_url ?? "");
    clearError();
  }

  function handleUrlBlur(setter: (s: string) => void, value: string) {
    if (value.trim() === "") return;
    setter(normalizeUrl(value));
  }

  const readView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-1.5">
      <Row label="Phone" value={lead.phone} />
      <Row label="Email" value={lead.email} />
      <Row label="Website" value={lead.website_url} isLink />
      <Row label="Facebook" value={lead.facebook_url} isLink />
      <Row label="Instagram" value={lead.instagram_url} isLink />
      <Row label="Menu" value={lead.menu_url} isLink />
    </div>
  );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-2">
      <IconInput icon={<Phone className="h-3.5 w-3.5" />} label="Phone" value={phone} onChange={setPhone} />
      <IconInput
        icon={<Mail className="h-3.5 w-3.5" />}
        label="Email"
        value={email}
        onChange={setEmail}
        error={emailError}
      />
      <IconInput
        icon={<Globe className="h-3.5 w-3.5" />}
        label="Website URL"
        value={website}
        onChange={setWebsite}
        onBlur={() => handleUrlBlur(setWebsite, website)}
      />
      <IconInput
        icon={<Facebook className="h-3.5 w-3.5" />}
        label="Facebook URL"
        value={facebook}
        onChange={setFacebook}
        onBlur={() => handleUrlBlur(setFacebook, facebook)}
      />
      <IconInput
        icon={<Instagram className="h-3.5 w-3.5" />}
        label="Instagram URL"
        value={instagram}
        onChange={setInstagram}
        onBlur={() => handleUrlBlur(setInstagram, instagram)}
      />
      <IconInput
        icon={<Menu className="h-3.5 w-3.5" />}
        label="Menu URL"
        value={menu}
        onChange={setMenu}
        onBlur={() => handleUrlBlur(setMenu, menu)}
      />
      {urlError && <p className="text-xs text-red-600 dark:text-red-400">{urlError}</p>}
    </div>
  );

  return (
    <EditableSectionShell
      id="contact"
      title="Contact"
      readView={readView}
      editView={editView}
      onSave={handleSave}
      onCancel={handleCancel}
      saving={saving}
      error={error}
      canSave={emailError === null && urlError === null}
    />
  );
}

function IconInput({
  icon,
  label,
  value,
  onChange,
  onBlur,
  error,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  onChange: (s: string) => void;
  onBlur?: () => void;
  error?: string | null;
}) {
  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="text-zinc-500 dark:text-zinc-400 shrink-0">{icon}</span>
        <input
          type="text"
          aria-label={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          placeholder={label}
          className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
        />
      </div>
      {error && <p className="mt-1 ml-6 text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}

function Row({ label, value, isLink }: { label: string; value: string | null; isLink?: boolean }) {
  return (
    <div className="flex items-baseline gap-3 text-xs">
      <span className="text-zinc-500 dark:text-zinc-400 w-24 shrink-0">{label}</span>
      {value == null || value === "" ? (
        <span className="text-zinc-400 dark:text-zinc-600">—</span>
      ) : isLink ? (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 dark:text-blue-400 hover:underline truncate"
        >
          {value}
        </a>
      ) : (
        <span className="text-zinc-900 dark:text-zinc-100 break-words">{value}</span>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/ContactSection.test.tsx
```

Expected: 2 PASS.

- [ ] **Step 5: Stage**

```bash
git add frontend/src/components/admin/leads/sections/ContactSection.tsx frontend/src/components/admin/leads/sections/__tests__/ContactSection.test.tsx
```

**Suggested commit:** `feat(ui): ContactSection — read + edit with email/URL validation`

---

### Task C3: `DesignPromptSection` (TipTap)

**Files:**
- Create: `frontend/src/components/admin/leads/sections/DesignPromptEditor.tsx` (TipTap, dynamically imported)
- Create: `frontend/src/components/admin/leads/sections/DesignPromptSection.tsx`
- Test: `frontend/src/components/admin/leads/sections/__tests__/DesignPromptSection.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/admin/leads/sections/__tests__/DesignPromptSection.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { DesignPromptSection } from "../DesignPromptSection";
import type { Lead } from "../../types";

// Avoid loading TipTap in tests; it requires a real DOM ContentEditable.
vi.mock("../DesignPromptEditor", () => ({
  DesignPromptEditor: ({
    value,
    onChange,
  }: {
    value: string;
    onChange: (v: string) => void;
  }) => (
    <textarea aria-label="Design prompt editor" value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));

const lead = { id: "lead-1", design_prompt: "<p>brief</p>" } as unknown as Lead;

describe("DesignPromptSection", () => {
  it("renders read view with stored HTML", () => {
    render(
      <EditingSectionProvider>
        <DesignPromptSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    expect(screen.getByText("brief")).toBeTruthy();
  });

  it("reveals the editor on pencil click", () => {
    render(
      <EditingSectionProvider>
        <DesignPromptSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    fireEvent.click(screen.getByLabelText("Edit Design prompt"));
    expect(screen.getByLabelText("Design prompt editor")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/DesignPromptSection.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement the TipTap editor module (dynamically loaded)**

Create `frontend/src/components/admin/leads/sections/DesignPromptEditor.tsx`:

```tsx
"use client";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import {
  Bold,
  Code,
  Heading1,
  Heading2,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Redo2,
  Undo2,
} from "lucide-react";

interface Props {
  value: string;
  onChange: (html: string) => void;
}

export function DesignPromptEditor({ value, onChange }: Props) {
  const editor = useEditor({
    extensions: [StarterKit, Link.configure({ openOnClick: false, autolink: true })],
    content: value,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
    editorProps: {
      attributes: {
        class:
          "prose prose-sm prose-zinc dark:prose-invert max-w-none focus:outline-none min-h-[8rem]",
      },
    },
    immediatelyRender: false,
  });

  if (!editor) return null;

  const Btn = ({
    active,
    onClick,
    title,
    children,
  }: {
    active?: boolean;
    onClick: () => void;
    title: string;
    children: React.ReactNode;
  }) => (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={`h-7 w-7 inline-flex items-center justify-center rounded-md text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer transition-colors ${
        active ? "ring-2 ring-zinc-300 dark:ring-zinc-700 bg-zinc-100 dark:bg-zinc-800" : ""
      }`}
    >
      {children}
    </button>
  );

  function promptLink() {
    const prev = editor!.getAttributes("link").href as string | undefined;
    const url = window.prompt("URL", prev ?? "https://");
    if (url === null) return;
    if (url === "") {
      editor!.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    editor!.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-0.5 sticky top-0 bg-zinc-50 dark:bg-zinc-900 py-1 z-10">
        <Btn title="Bold" active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()}>
          <Bold className="h-3.5 w-3.5" />
        </Btn>
        <Btn title="Italic" active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()}>
          <Italic className="h-3.5 w-3.5" />
        </Btn>
        <Btn title="Heading 1" active={editor.isActive("heading", { level: 1 })} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}>
          <Heading1 className="h-3.5 w-3.5" />
        </Btn>
        <Btn title="Heading 2" active={editor.isActive("heading", { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>
          <Heading2 className="h-3.5 w-3.5" />
        </Btn>
        <Btn title="Bullet list" active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()}>
          <List className="h-3.5 w-3.5" />
        </Btn>
        <Btn title="Numbered list" active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()}>
          <ListOrdered className="h-3.5 w-3.5" />
        </Btn>
        <Btn title="Code block" active={editor.isActive("codeBlock")} onClick={() => editor.chain().focus().toggleCodeBlock().run()}>
          <Code className="h-3.5 w-3.5" />
        </Btn>
        <Btn title="Link" active={editor.isActive("link")} onClick={promptLink}>
          <LinkIcon className="h-3.5 w-3.5" />
        </Btn>
        <div className="mx-1 h-4 w-px bg-zinc-200 dark:bg-zinc-700" />
        <Btn title="Undo" onClick={() => editor.chain().focus().undo().run()}>
          <Undo2 className="h-3.5 w-3.5" />
        </Btn>
        <Btn title="Redo" onClick={() => editor.chain().focus().redo().run()}>
          <Redo2 className="h-3.5 w-3.5" />
        </Btn>
      </div>
      <div className="rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 p-3">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement the section**

Create `frontend/src/components/admin/leads/sections/DesignPromptSection.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch } from "../hooks/useLeadPatch";

const DesignPromptEditor = dynamic(
  () => import("./DesignPromptEditor").then((m) => m.DesignPromptEditor),
  { ssr: false, loading: () => <div className="text-xs text-zinc-500">Loading editor…</div> },
);

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

export function DesignPromptSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);

  const [html, setHtml] = useState(lead.design_prompt ?? "");

  useEffect(() => {
    setHtml(lead.design_prompt ?? "");
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.design_prompt]);

  async function handleSave() {
    const next = html.trim() === "" ? null : html;
    if (next === (lead.design_prompt ?? null)) return;
    await patch({ design_prompt: next });
  }

  function handleCancel() {
    setHtml(lead.design_prompt ?? "");
    clearError();
  }

  const readView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      {lead.design_prompt ? (
        <div
          className="prose prose-sm prose-zinc dark:prose-invert max-w-none"
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: lead.design_prompt }}
        />
      ) : (
        <p className="text-xs text-zinc-500 dark:text-zinc-400 italic">Not set yet.</p>
      )}
    </div>
  );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      <DesignPromptEditor value={html} onChange={setHtml} />
    </div>
  );

  return (
    <EditableSectionShell
      id="design_prompt"
      title="Design prompt"
      readView={readView}
      editView={editView}
      onSave={handleSave}
      onCancel={handleCancel}
      saving={saving}
      error={error}
      canSave={true}
    />
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/DesignPromptSection.test.tsx
```

Expected: 2 PASS.

- [ ] **Step 6: Stage**

```bash
git add frontend/src/components/admin/leads/sections/DesignPromptSection.tsx frontend/src/components/admin/leads/sections/DesignPromptEditor.tsx frontend/src/components/admin/leads/sections/__tests__/DesignPromptSection.test.tsx
```

**Suggested commit:** `feat(ui): DesignPromptSection — TipTap rich text editor for design briefs`

---

### Task C4: `OpeningHoursSection`

**Files:**
- Create: `frontend/src/components/admin/leads/sections/OpeningHoursSection.tsx`
- Test: `frontend/src/components/admin/leads/sections/__tests__/OpeningHoursSection.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/admin/leads/sections/__tests__/OpeningHoursSection.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { OpeningHoursSection } from "../OpeningHoursSection";
import type { Lead } from "../../types";

const lead = {
  id: "lead-1",
  opening_hours: { Monday: "9–17" },
} as unknown as Lead;

describe("OpeningHoursSection", () => {
  it("renders 7 day rows in read mode", () => {
    render(
      <EditingSectionProvider>
        <OpeningHoursSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    expect(screen.getByText("Monday")).toBeTruthy();
    expect(screen.getByText("Sunday")).toBeTruthy();
    expect(screen.getByText("9–17")).toBeTruthy();
  });

  it("Closed quick-button sets the input to 'Closed'", () => {
    render(
      <EditingSectionProvider>
        <OpeningHoursSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    fireEvent.click(screen.getByLabelText("Edit Opening hours"));
    fireEvent.click(screen.getByLabelText("Mark Tuesday closed"));
    const tueInput = screen.getByLabelText("Tuesday hours") as HTMLInputElement;
    expect(tueInput.value).toBe("Closed");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/OpeningHoursSection.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement the section**

Create `frontend/src/components/admin/leads/sections/OpeningHoursSection.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { motion } from "framer-motion";
import { fadeUp, staggerFast } from "@/lib/animations";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch } from "../hooks/useLeadPatch";

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

const DAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

type Day = (typeof DAYS)[number];

function emptyDraft(hours: Record<string, string> | null): Record<Day, string> {
  return Object.fromEntries(DAYS.map((d) => [d, hours?.[d] ?? ""])) as Record<Day, string>;
}

function draftToServerMap(draft: Record<Day, string>): Record<string, string> {
  // Drop empty days; backend stores only days with data.
  const out: Record<string, string> = {};
  for (const d of DAYS) if (draft[d].trim() !== "") out[d] = draft[d].trim();
  return out;
}

function mapsEqual(a: Record<string, string>, b: Record<string, string>): boolean {
  const ak = Object.keys(a).sort();
  const bk = Object.keys(b).sort();
  if (ak.length !== bk.length) return false;
  return ak.every((k, i) => k === bk[i] && a[k] === b[k]);
}

export function OpeningHoursSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);

  const [draft, setDraft] = useState<Record<Day, string>>(() => emptyDraft(lead.opening_hours));

  useEffect(() => {
    setDraft(emptyDraft(lead.opening_hours));
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.opening_hours]);

  async function handleSave() {
    const next = draftToServerMap(draft);
    const curr = (lead.opening_hours ?? {}) as Record<string, string>;
    if (mapsEqual(next, curr)) return;
    await patch({ opening_hours: next });
  }

  function handleCancel() {
    setDraft(emptyDraft(lead.opening_hours));
    clearError();
  }

  const readView = (
    <motion.div
      variants={staggerFast}
      initial="hidden"
      animate="visible"
      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800"
    >
      {DAYS.map((day) => {
        const v = lead.opening_hours?.[day] ?? "___";
        const placeholder = v === "___";
        return (
          <motion.div
            key={day}
            variants={fadeUp}
            className="flex items-center justify-between px-3 py-2 text-sm"
          >
            <span className="text-zinc-600 dark:text-zinc-400 font-medium">{day}</span>
            <span
              className={
                placeholder
                  ? "text-zinc-400 dark:text-zinc-600 font-mono italic"
                  : "text-zinc-900 dark:text-zinc-100 tabular-nums"
              }
            >
              {v}
            </span>
          </motion.div>
        );
      })}
    </motion.div>
  );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800">
      {DAYS.map((day) => (
        <div key={day} className="flex items-center gap-2 px-3 py-1.5">
          <span className="w-20 text-xs text-zinc-600 dark:text-zinc-400 font-medium shrink-0">
            {day}
          </span>
          <input
            type="text"
            aria-label={`${day} hours`}
            value={draft[day]}
            onChange={(e) => setDraft((d) => ({ ...d, [day]: e.target.value }))}
            placeholder="9–17, Closed, Open 24 hours…"
            className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-2 py-1 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
          />
          <button
            type="button"
            aria-label={`Mark ${day} closed`}
            onClick={() => setDraft((d) => ({ ...d, [day]: "Closed" }))}
            className="text-[10px] px-1.5 py-0.5 rounded text-zinc-500 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-800 cursor-pointer transition-colors"
          >
            Closed
          </button>
        </div>
      ))}
    </div>
  );

  return (
    <div className="mt-5">
      <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2 flex items-center gap-1.5">
        <Clock className="h-3.5 w-3.5" />
      </div>
      <EditableSectionShell
        id="opening_hours"
        title="Opening hours"
        readView={readView}
        editView={editView}
        onSave={handleSave}
        onCancel={handleCancel}
        saving={saving}
        error={error}
        canSave
      />
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/OpeningHoursSection.test.tsx
```

Expected: 2 PASS.

- [ ] **Step 5: Stage**

```bash
git add frontend/src/components/admin/leads/sections/OpeningHoursSection.tsx frontend/src/components/admin/leads/sections/__tests__/OpeningHoursSection.test.tsx
```

**Suggested commit:** `feat(ui): OpeningHoursSection — free-text per day with Closed quick button`

---

### Task C5: `AboutSection`

**Files:**
- Create: `frontend/src/components/admin/leads/sections/AboutSection.tsx`
- Test: `frontend/src/components/admin/leads/sections/__tests__/AboutSection.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/admin/leads/sections/__tests__/AboutSection.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { AboutSection } from "../AboutSection";
import type { Lead } from "../../types";

const lead = {
  id: "lead-1",
  extra: {
    attributes: {
      "Service options": { "Dine-in": true, Takeout: false },
    },
  },
} as unknown as Lead;

describe("AboutSection", () => {
  it("renders existing attributes in read view", () => {
    render(
      <EditingSectionProvider>
        <AboutSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    expect(screen.getByText("Service options")).toBeTruthy();
    expect(screen.getByText("Dine-in")).toBeTruthy();
  });

  it("toggles an attribute in edit mode", () => {
    render(
      <EditingSectionProvider>
        <AboutSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    fireEvent.click(screen.getByLabelText("Edit About this business"));
    const toggle = screen.getByLabelText("Toggle Dine-in") as HTMLButtonElement;
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-pressed")).toBe("false");
  });

  it("adds a new attribute when the user types and submits", () => {
    render(
      <EditingSectionProvider>
        <AboutSection lead={lead} onPatched={vi.fn()} />
      </EditingSectionProvider>,
    );
    fireEvent.click(screen.getByLabelText("Edit About this business"));
    const addInput = screen.getByPlaceholderText(/new attribute in Service options/i) as HTMLInputElement;
    fireEvent.change(addInput, { target: { value: "Delivery" } });
    fireEvent.keyDown(addInput, { key: "Enter" });
    expect(screen.getByText("Delivery")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/AboutSection.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement the section**

Create `frontend/src/components/admin/leads/sections/AboutSection.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Plus, Trash2, X } from "lucide-react";
import { fadeUp, rowAdd, staggerFast } from "@/lib/animations";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch } from "../hooks/useLeadPatch";

type Attrs = Record<string, Record<string, boolean>>;

function readAttrs(lead: Lead): Attrs {
  const e = lead.extra;
  if (e && typeof e === "object" && "attributes" in e) {
    return (e.attributes as Attrs) ?? {};
  }
  return {};
}

function attrsEqual(a: Attrs, b: Attrs): boolean {
  const ak = Object.keys(a).sort();
  const bk = Object.keys(b).sort();
  if (ak.length !== bk.length) return false;
  for (let i = 0; i < ak.length; i++) {
    if (ak[i] !== bk[i]) return false;
    const sa = a[ak[i]];
    const sb = b[bk[i]];
    const aak = Object.keys(sa).sort();
    const bbk = Object.keys(sb).sort();
    if (aak.length !== bbk.length) return false;
    for (let j = 0; j < aak.length; j++) {
      if (aak[j] !== bbk[j]) return false;
      if (sa[aak[j]] !== sb[bbk[j]]) return false;
    }
  }
  return true;
}

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

export function AboutSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);
  const [draft, setDraft] = useState<Attrs>(() => structuredClone(readAttrs(lead)));
  const [newSection, setNewSection] = useState("");
  const [newAttrPerSection, setNewAttrPerSection] = useState<Record<string, string>>({});

  useEffect(() => {
    setDraft(structuredClone(readAttrs(lead)));
    setNewSection("");
    setNewAttrPerSection({});
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.extra]);

  async function handleSave() {
    const current = readAttrs(lead);
    if (attrsEqual(draft, current)) return;
    await patch({ about_attributes: draft });
  }

  function handleCancel() {
    setDraft(structuredClone(readAttrs(lead)));
    setNewSection("");
    setNewAttrPerSection({});
    clearError();
  }

  function toggle(section: string, attr: string) {
    setDraft((d) => ({
      ...d,
      [section]: { ...d[section], [attr]: !d[section][attr] },
    }));
  }

  function removeAttr(section: string, attr: string) {
    setDraft((d) => {
      const next = { ...d, [section]: { ...d[section] } };
      delete next[section][attr];
      return next;
    });
  }

  function removeSection(section: string) {
    setDraft((d) => {
      const next = { ...d };
      delete next[section];
      return next;
    });
  }

  function addAttr(section: string) {
    const label = (newAttrPerSection[section] ?? "").trim();
    if (label === "") return;
    setDraft((d) => ({ ...d, [section]: { ...d[section], [label]: false } }));
    setNewAttrPerSection((s) => ({ ...s, [section]: "" }));
  }

  function addSection() {
    const name = newSection.trim();
    if (name === "" || draft[name] !== undefined) return;
    setDraft((d) => ({ ...d, [name]: {} }));
    setNewSection("");
  }

  const readView =
    Object.keys(readAttrs(lead)).length === 0 ? (
      <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 text-xs text-zinc-500 dark:text-zinc-400 italic">
        No &quot;About&quot; data on Google Maps for this place.
      </div>
    ) : (
      <motion.div
        variants={staggerFast}
        initial="hidden"
        animate="visible"
        className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-3"
      >
        {Object.entries(readAttrs(lead)).map(([section, items]) => (
          <motion.div key={section} variants={fadeUp}>
            <div className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
              {section}
            </div>
            <ul className="space-y-0.5">
              {Object.entries(items).map(([attr, v]) => (
                <li key={attr} className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                  {v ? (
                    <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  ) : (
                    <X className="h-3.5 w-3.5 text-zinc-400 dark:text-zinc-600 shrink-0" />
                  )}
                  <span className={v ? "" : "text-zinc-500 dark:text-zinc-500 line-through"}>{attr}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        ))}
      </motion.div>
    );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-4">
      <AnimatePresence initial={false}>
        {Object.entries(draft).map(([section, items]) => (
          <motion.div
            key={section}
            variants={rowAdd}
            initial="hidden"
            animate="visible"
            exit={{ height: 0, opacity: 0 }}
            className="group/section"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">{section}</span>
              <button
                type="button"
                aria-label={`Remove section ${section}`}
                onClick={() => removeSection(section)}
                className="opacity-0 group-hover/section:opacity-100 transition-opacity text-zinc-400 hover:text-red-500 cursor-pointer"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
            <ul className="space-y-1">
              <AnimatePresence initial={false}>
                {Object.entries(items).map(([attr, v]) => (
                  <motion.li
                    key={attr}
                    variants={rowAdd}
                    initial="hidden"
                    animate="visible"
                    exit={{ height: 0, opacity: 0 }}
                    className="flex items-center gap-2 group/row"
                  >
                    <button
                      type="button"
                      role="switch"
                      aria-pressed={v}
                      aria-label={`Toggle ${attr}`}
                      onClick={() => toggle(section, attr)}
                      className={`relative h-4 w-7 rounded-full transition-colors ${
                        v ? "bg-emerald-500" : "bg-zinc-300 dark:bg-zinc-700"
                      }`}
                    >
                      <motion.span
                        layout
                        className="absolute top-0.5 h-3 w-3 rounded-full bg-white shadow"
                        style={{ left: v ? "calc(100% - 0.875rem)" : "0.125rem" }}
                        transition={{ type: "spring", stiffness: 500, damping: 30 }}
                      />
                    </button>
                    <span className="text-sm text-zinc-700 dark:text-zinc-300 flex-1">{attr}</span>
                    <button
                      type="button"
                      aria-label={`Remove ${attr}`}
                      onClick={() => removeAttr(section, attr)}
                      className="opacity-0 group-hover/row:opacity-100 transition-opacity text-zinc-400 hover:text-red-500 cursor-pointer"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
            <div className="mt-1.5 flex items-center gap-1.5">
              <input
                type="text"
                value={newAttrPerSection[section] ?? ""}
                placeholder={`new attribute in ${section}`}
                onChange={(e) =>
                  setNewAttrPerSection((s) => ({ ...s, [section]: e.target.value }))
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addAttr(section);
                  }
                }}
                className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-2 py-1 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
              />
              <button
                type="button"
                onClick={() => addAttr(section)}
                className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 cursor-pointer"
                aria-label={`Add attribute to ${section}`}
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>

      <div className="flex items-center gap-1.5 pt-2 border-t border-zinc-200 dark:border-zinc-800">
        <input
          type="text"
          value={newSection}
          placeholder="new section"
          onChange={(e) => setNewSection(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addSection();
            }
          }}
          className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-2 py-1 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
        />
        <button
          type="button"
          onClick={addSection}
          aria-label="Add section"
          className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );

  return (
    <EditableSectionShell
      id="about"
      title="About this business"
      readView={readView}
      editView={editView}
      onSave={handleSave}
      onCancel={handleCancel}
      saving={saving}
      error={error}
      canSave
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/AboutSection.test.tsx
```

Expected: 3 PASS.

- [ ] **Step 5: Stage**

```bash
git add frontend/src/components/admin/leads/sections/AboutSection.tsx frontend/src/components/admin/leads/sections/__tests__/AboutSection.test.tsx
```

**Suggested commit:** `feat(ui): AboutSection — toggle attributes + add/remove sections & attributes`

---

## Phase D — Wire-up + smoke

### Task D1: Mount new sections in `LeadDetailDrawer`

**Files:**
- Modify: `frontend/src/components/admin/leads/LeadDetailDrawer.tsx`

- [ ] **Step 1: Wrap the drawer body in `EditingSectionProvider`**

In `LeadDetailDrawer.tsx`, change the `DrawerBody` return to wrap its outer `<div className="p-5">` inside `<EditingSectionProvider>`:

```tsx
import { EditingSectionProvider } from "./context/EditingSectionContext";
import { LocationSection } from "./sections/LocationSection";
import { ContactSection } from "./sections/ContactSection";
import { DesignPromptSection } from "./sections/DesignPromptSection";
import { OpeningHoursSection } from "./sections/OpeningHoursSection";
import { AboutSection } from "./sections/AboutSection";
```

Replace the existing Location, Contact, Design prompt, Opening hours, and About JSX blocks in `DrawerBody`'s return with:

```tsx
<LocationSection lead={lead} onPatched={onPatched} />
<ContactSection lead={lead} onPatched={onPatched} />
<DesignPromptSection lead={lead} onPatched={onPatched} />
<OpeningHoursSection lead={lead} onPatched={onPatched} />
<AboutSection lead={lead} onPatched={onPatched} />
```

Then wrap the entire `<div className="p-5">...</div>` return in `<EditingSectionProvider>...</EditingSectionProvider>`.

**Remove** the now-unused imports: `OpeningHoursTable`, `ReviewsList` (keep if still used elsewhere — check), `AboutAttributesPanel`. **Note:** `ReviewsList` is unrelated, leave it. `OpeningHoursTable` and `AboutAttributesPanel` are no longer imported by the drawer; leave the component files alone — they may still be useful as standalone components.

**Remove** the local helpers `Row`, `DetailCard` and the `closed_amount` block? **No** — `DetailCard`/`Row` are still used by the AI scoring block, and `closed_amount` is unrelated. Only remove the Location and Contact `DetailCard` usages.

- [ ] **Step 2: Type-check + lint**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

Expected: no new errors.

- [ ] **Step 3: Run all frontend tests**

```bash
cd frontend && npx vitest run
```

Expected: all PASS (existing tests + the new section tests).

- [ ] **Step 4: Stage**

```bash
git add frontend/src/components/admin/leads/LeadDetailDrawer.tsx
```

**Suggested commit:** `feat(ui): mount editable sections inside LeadDetailDrawer`

---

### Task D2: Manual E2E smoke

This task is manual; no code changes. Run through the §6 checklist from the spec:

- [ ] **Step 1: Restart dev servers**

```bash
# Kill old server on 8002
netstat -ano | grep ":8002 " | grep LISTENING | awk '{print $5}' | xargs -I{} taskkill //F //PID {}
cd backend && source venv/Scripts/activate && uvicorn auth_service.main:app --reload --port 8002 --host 127.0.0.1 &
cd frontend && FASTAPI_URL=http://localhost:8002 npm run dev &
```

- [ ] **Step 2: E2E checklist**

Open http://localhost:3000/dashboard/admin/leads, log in, open any lead. For each row below, verify the expected outcome and report any issue:

| # | Action | Expected |
|---|---|---|
| 1 | Hover Location header | Pencil icon fades in. |
| 2 | Click pencil; change Address; Save | Section returns to read view; address updated; reopen lead — persisted. |
| 3 | Enter invalid email; observe Save button | Save disabled; "Enter a valid email" under field. |
| 4 | Edit Contact, type `example.com` in Facebook, blur | Becomes `https://example.com`. |
| 5 | Edit Design prompt; format with bold/italic/list; Save | Read view re-renders with formatting preserved. |
| 6 | Edit Opening hours; click `Closed` on Tuesday; Save | Tuesday now shows `Closed` in read view. |
| 7 | Edit About; add a new section "Parking" with attribute "Free"; Save | Section appears in read view. |
| 8 | Edit About; toggle an existing attribute; Save; verify in Supabase | `extra.attributes.<section>.<attr>` flipped; other `extra` keys unchanged. |
| 9 | Open Location edit; while dirty, click Contact pencil | Location edits discarded silently; Contact opens. |
| 10 | Submit `<script>` in Design prompt via HTML paste; Save; reopen | Script tag stripped; safe HTML retained. |

- [ ] **Step 3: ui-ux-pro-max review**

Per the spec, invoke the `ui-ux-pro-max` skill to review each edit-mode view. Apply any spacing/affordance feedback to the section components. Stage and commit those polish changes separately:

```bash
git add frontend/src/components/admin/leads/sections/
```

**Suggested commit:** `polish(ui): apply ui-ux-pro-max review feedback to lead sections`

---

## Self-review (post-write)

- **Spec coverage:**
  - §3.1 edit pattern → Task B5 (shell) + sections.
  - §3.2 component breakdown → Tasks B3, B4, B5, C1–C5, D1.
  - §3.3 per-section UX → Tasks C1–C5.
  - §3.4 save flow → Tasks B4 (hook) + each section's `handleSave`.
  - §3.5.1 LeadUpdate expansion → Task A2.
  - §3.5.2 router (sanitization + merge) → Tasks A3 + A4.
  - §3.5.3 backend tests → Tasks A2, A3, A4.
  - §3.6 validation rules → embedded in C1 (lat/lng), C2 (email/URL); free-text everywhere else by design.
  - §3.7 animations → Task B2.
  - §3.8 dependencies → Tasks A1 (bleach), B1 (TipTap, typography).
  - §3.9 ui-ux-pro-max → Task D2 Step 3.
- **Placeholders:** none — every step has runnable commands or complete code.
- **Type consistency:** `LeadUpdatePayload` defined in Task B4 and used by every section in C1–C5; `EditableSectionShellProps` defined in B5 used by all sections.

**Plan complete and saved to `docs/superpowers/plans/2026-05-21-lead-editing.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — executed in this session via executing-plans, batch with checkpoints.

Which approach?
