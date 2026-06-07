# Booking Email Template Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A dashboard "Emails" tab where the owner uploads a logo, picks a brand color, and edits the wording of the 4 client-facing booking emails (confirmation, reschedule, cancellation, reminder) with a live, server-rendered preview.

**Architecture:** Per-tenant copy overrides in a new `booking_settings.email_copy` JSONB column; a `tt(overrides, locale, key)` helper makes the existing renderers override-aware (default = `booking_i18n`); a preview endpoint renders the draft with the real renderers + sample data; the editor is a split view (controls + debounced live iframe).

**Tech Stack:** FastAPI + supabase-py (service-role + Storage `cms-files`); Next.js dashboard (`useQuery`, `lib/styles.ts`, `motion/react`); pytest + Vitest.

## Spec
Implements `docs/superpowers/specs/2026-06-06-booking-email-template-editor-design.md`. Read it first.

---

# PART A — Backend

## Task A1: `email_copy` column + TenantConfig

**Files:** Create `backend/migrations/2026_06_06_booking_email_copy.sql`; Modify `backend/auth_service/services/booking_tenant.py`

- [ ] **Step 1: Migration file** (applied via MCP in Task A7):
```sql
-- Additive: per-tenant email copy overrides (key -> custom text). Defaults live
-- in booking_i18n; only overridden keys are stored here.
alter table public.booking_settings
  add column if not exists email_copy jsonb not null default '{}'::jsonb;
```

- [ ] **Step 2: `TenantConfig`** — add `email_copy: dict` to the dataclass (at the END, default `field(default_factory=dict)` — import `field`), add `email_copy` to `_FIELDS`, and map in `_to_config` via `row.get("email_copy") or {}`. Existing constructions keep working (default `{}`).

- [ ] **Step 3: Verify** `cd backend && source venv/Scripts/activate && python -c "from auth_service.services.booking_tenant import TenantConfig; print(TenantConfig(tenant_id='t', public_slug='s', timezone='UTC', locale='en', business_name=None, owner_notification_email='o@x.com', email_from_name=None, meeting_url='', slot_granularity_min=15, reminders_enabled=True, reminder_offsets_min=[], calendar_provider='none', is_active=True).email_copy)"` → `{}`.

## Task A2: `tt` override helper + editable field schema

**Files:** Modify `backend/auth_service/services/booking_i18n.py`; Test `backend/auth_service/tests/test_booking_i18n.py`

- [ ] **Step 1: Failing test** (append):
```python
from auth_service.services.booking_i18n import tt, EDITABLE_EMAIL_FIELDS

def test_tt_uses_override():
    assert tt({"join_cta": "Join now"}, "en", "join_cta") == "Join now"

def test_tt_falls_back_to_default():
    assert tt({}, "en", "join_cta") == "Join the call"
    assert tt(None, "en", "confirm_subject") == "Your call with Stefan is booked"

def test_tt_formats_override():
    assert tt({"confirmed_heading": "Booked, {name}!"}, "en", "confirmed_heading", name="Sam") == "Booked, Sam!"

def test_editable_fields_have_known_keys():
    keys = {f["key"] for f in EDITABLE_EMAIL_FIELDS}
    assert "join_cta" in keys and "confirm_subject" in keys
    assert all(f["key"] in STRINGS["en"] for f in EDITABLE_EMAIL_FIELDS)
```

- [ ] **Step 2: Run → fails** (`ImportError`). `pytest auth_service/tests/test_booking_i18n.py -v`

- [ ] **Step 3: Implement** — append to `booking_i18n.py`:
```python
def tt(overrides: dict | None, locale: str | None, key: str, **fmt: object) -> str:
    """Tenant override → else the locale default (t). Formats {placeholders}
    best-effort; never raises on a missing placeholder."""
    if overrides and key in overrides and overrides[key]:
        raw = str(overrides[key])
        if fmt:
            try:
                return raw.format(**fmt)
            except (KeyError, IndexError, ValueError):
                return raw
        return raw
    return t(locale, key, **fmt)


# Editable client-facing fields, grouped for the dashboard editor. Host-facing
# keys are intentionally excluded. `group` drives the editor's case selector;
# "shared" fields render once.
EDITABLE_EMAIL_FIELDS: list[dict[str, str]] = [
    {"key": "manage_cta", "label": "Manage-booking button", "group": "shared"},
    {"key": "join_cta", "label": "Join-call button", "group": "shared"},
    {"key": "add_cal_cta", "label": "Add-to-calendar button", "group": "shared"},
    {"key": "manage_prompt", "label": "Manage prompt", "group": "shared"},
    {"key": "confirm_subject", "label": "Subject", "group": "confirmation"},
    {"key": "header_confirmed", "label": "Header subtitle", "group": "confirmation"},
    {"key": "confirmed_heading", "label": "Heading", "group": "confirmation"},
    {"key": "confirmed_subtext", "label": "Subtext", "group": "confirmation"},
    {"key": "reschedule_subject", "label": "Subject", "group": "reschedule"},
    {"key": "header_moved", "label": "Header subtitle", "group": "reschedule"},
    {"key": "reschedule_client_heading", "label": "Heading", "group": "reschedule"},
    {"key": "cancel_subject", "label": "Subject", "group": "cancellation"},
    {"key": "header_cancelled", "label": "Header subtitle", "group": "cancellation"},
    {"key": "cancel_client_heading", "label": "Heading", "group": "cancellation"},
    {"key": "reminder_subject", "label": "Subject", "group": "reminder"},
    {"key": "header_reminder", "label": "Header subtitle", "group": "reminder"},
    {"key": "reminder_heading", "label": "Heading", "group": "reminder"},
]
```

- [ ] **Step 4: Run → pass.** **Step 5:** commit checkpoint (no auto-commit — leave in tree).

## Task A3: Override-aware renderers + accent on buttons

**Files:** Modify `backend/auth_service/services/booking_email.py`, `booking_manage_email.py`, `booking_reminder_email.py`; Test: extend `test_booking_email.py`, `test_booking_manage_email.py`

The transformation (apply consistently):
1. **Thread `copy`:** add `copy: dict | None = None` to the **client-facing** render + send functions: `render_visitor_html`, `send_visitor_confirmation` (booking_email); `render_cancel_client`, `render_reschedule_client`, `send_cancellation`, `send_reschedule` (booking_manage_email); `render_html`, `send` (booking_reminder_email). Inside each, replace every `t(locale, KEY, ...)` with `tt(copy, locale, KEY, ...)` (import `tt` from `.booking_i18n`). The send functions pass `copy=copy` into their render call AND use `tt(copy, locale, "..._subject", ...)` for the subject. (Leave host-facing functions — `render_host_html`, `send_host_notification`, `render_cancel_host`, `render_reschedule_host` — on plain `t`.)
2. **Accent on buttons:** give the primary-CTA helpers an `accent: str = "#18181b"` param — `_cta_block` (booking_email), `_button` (booking_manage_email), and the inline CTA in `booking_reminder_email.render_html`. Replace the PRIMARY button `background:#18181b` with `background:{accent}` (leave secondary/outline buttons as-is). The render functions pass `accent=_brand.accent` (the `_brand` they already resolve). Default `#18181b` keeps unbranded output identical.

- [ ] **Step 1: Failing tests** — add:
```python
# test_booking_email.py
def test_visitor_email_copy_override():
    html = render_visitor_html(booking=BOOKING, meeting_url="https://m/x",
                               copy={"confirmed_heading": "All set, {name}!"})
    assert "All set, Jane" in html  # BOOKING["name"] == "Jane <b>Doe</b>" -> escaped; assert the override text
    assert "You&#39;re booked" not in html

def test_visitor_email_accent_on_button():
    html = render_visitor_html(booking=BOOKING, meeting_url="https://m/x",
                               brand=Brand(business_name="Acme", logo_url="https://a/l.png",
                                           accent="#ff0000", canonical_url="https://a"))
    assert "#ff0000" in html  # header AND join button
```
(Use `from auth_service.services.email_layout import Brand`.)

- [ ] **Step 2: Run → fail.** **Step 3: Implement** the transformation above. **Step 4: Run → pass** (plus all existing email tests stay green — default output unchanged). **Step 5:** checkpoint.

## Task A4: Wire `copy=cfg.email_copy` at the send sites

**Files:** Modify `backend/auth_service/routers/booking.py`, `booking_admin.py`

- [ ] **Step 1:** At each place the routers call the threaded send/render functions (`_create_core` visitor confirmation; the public manage cancel/reschedule; the cron reminder send; the owner `_notify_client_cancelled`/`_notify_client_rescheduled` in booking_admin), add `copy=cfg.email_copy` to the call. `cfg` is the resolved `TenantConfig` (now carries `email_copy`). For the reminder cron, `cfg` is loaded per booking already.
- [ ] **Step 2:** Run the full booking suite → green: `pytest auth_service/tests/ -q -k booking`. (Existing tests pass; `email_copy` defaults to `{}` so behavior is unchanged.)

## Task A5: `SettingsPatch.email_copy` + email-template schema endpoint

**Files:** Modify `backend/auth_service/models/booking_admin_schemas.py`, `backend/auth_service/routers/booking_admin.py`; Test `backend/auth_service/tests/test_booking_email_editor.py`

- [ ] **Step 1:** `SettingsPatch` — add `email_copy: dict | None = None`.
- [ ] **Step 2:** Append to `booking_admin.py`:
```python
from ..services import booking_i18n  # add to imports

@router.get("/projects/{project_slug}/bookings/email-template")
async def get_email_template(project_slug: str, request: Request) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    row = booking_admin_repo.get_settings(tenant_id) or {}
    overrides = row.get("email_copy") or {}
    fields = [
        {**f, "default": booking_i18n.STRINGS["en"][f["key"]],
         "value": overrides.get(f["key"], "")}
        for f in booking_i18n.EDITABLE_EMAIL_FIELDS
    ]
    return JSONResponse(content={
        "brand": {"logo_url": row.get("logo_url"), "accent_color": row.get("accent_color"),
                  "business_name": row.get("business_name")},
        "fields": fields,
    })
```

- [ ] **Step 3: Failing test** (`test_booking_email_editor.py`): patch `require_user`/`require_project_access` + `booking_admin_repo.get_settings` → a row with `email_copy={"join_cta":"Join"}`; GET email-template → assert `fields` includes a `join_cta` entry with `value=="Join"` and `default=="Join the call"`, and `brand` keys present. **Step 4:** run → pass.

## Task A6: Preview + logo endpoints

**Files:** Modify `backend/auth_service/routers/booking_admin.py`; Test `test_booking_email_editor.py`

- [ ] **Step 1: Preview endpoint** — append:
```python
from ..services import booking_email, booking_manage_email, booking_reminder_email  # imports
from ..services.email_layout import Brand  # import
from ..models.booking_admin_schemas import EmailPreviewIn  # Task A6 model

_SAMPLE = {
    "name": "Alex Carter", "email": "alex@example.com",
    "when_label": "Mon, 30 Jun 2026 · 14:30 (Europe/Berlin)",
    "note": "Looking forward to it.",
}

@router.post("/projects/{project_slug}/bookings/email-preview")
async def email_preview(project_slug: str, body: EmailPreviewIn, request: Request) -> JSONResponse:
    await _tenant(project_slug, request)
    d = body.draft
    brand = Brand(
        business_name=d.get("business_name") or "Your business",
        logo_url=d.get("logo_url") or "https://roman-technologies.dev/logo_dark.png",
        accent=d.get("accent_color") or "#18181b",
        canonical_url="https://roman-technologies.dev",
    )
    copy = d.get("email_copy") or {}
    start = datetime(2026, 6, 30, 12, 30, tzinfo=UTC)
    end = datetime(2026, 6, 30, 13, 15, tzinfo=UTC)
    booking = {**_SAMPLE, "start_utc": start, "end_utc": end}
    if body.case == "confirmation":
        html = booking_email.render_visitor_html(
            booking=booking, meeting_url="https://meet.example/demo",
            manage_url="https://example/m/sample", brand=brand, copy=copy)
    elif body.case == "reschedule":
        html = booking_manage_email.render_reschedule_client(
            name=_SAMPLE["name"], new_when=_SAMPLE["when_label"],
            meeting_url="https://meet.example/demo", manage_url="https://example/m/sample",
            new_start=start, new_end=end, brand=brand, copy=copy)
    elif body.case == "cancellation":
        html = booking_manage_email.render_cancel_client(
            name=_SAMPLE["name"], when_label=_SAMPLE["when_label"], brand=brand, copy=copy)
    elif body.case == "reminder":
        html = booking_reminder_email.render_html(
            name=_SAMPLE["name"], when_label=_SAMPLE["when_label"], note=_SAMPLE["note"],
            meeting_url="https://meet.example/demo", brand=brand, copy=copy)
    else:
        raise HTTPException(status_code=422, detail="Unknown case")
    return JSONResponse(content={"html": html})
```
Add model to `booking_admin_schemas.py`:
```python
class EmailPreviewIn(BaseModel):
    case: str
    draft: dict = {}
```

- [ ] **Step 2: Logo endpoint** — mirror `workspace.py`'s upload (read it for the exact guards). Append:
```python
import uuid
from fastapi import UploadFile, File

_LOGO_DENY = {"image/svg+xml", "text/html", "application/xhtml+xml"}
_LOGO_MAX = 5 * 1024 * 1024

@router.post("/projects/{project_slug}/bookings/logo")
async def upload_logo(project_slug: str, request: Request, file: UploadFile = File(...)) -> JSONResponse:
    tenant_id = await _tenant(project_slug, request)
    content = await file.read()
    if len(content) > _LOGO_MAX:
        raise HTTPException(status_code=413, detail="Logo too large (max 5MB)")
    mime = file.content_type or ""
    if not mime.startswith("image/") or mime in _LOGO_DENY:
        raise HTTPException(status_code=415, detail="Logo must be a PNG/JPG/WebP image")
    ext = (file.filename or "logo").rsplit(".", 1)[-1].lower()[:8] or "png"
    path = f"{tenant_id}/booking-logo/{uuid.uuid4()}.{ext}"
    sb = get_supabase_admin()  # import from ..services.supabase_client
    sb.storage.from_("cms-files").upload(
        path=path, file=content, file_options={"content-type": mime, "upsert": "false"})
    url = sb.storage.from_("cms-files").get_public_url(path)
    return JSONResponse(content={"url": url})
```
(Add `from ..services.supabase_client import get_supabase_admin` to imports.)

- [ ] **Step 3: Tests** (`test_booking_email_editor.py`): preview for each of the 4 cases returns HTML containing the override text + accent hex (mock auth; no DB needed — preview uses sample data, only `_tenant` is patched). Logo: oversize → 413; non-image mime → 415; valid → mock `get_supabase_admin().storage` and assert `{url}` returned. **Step 4:** run → pass; full suite green; ruff clean.

## Task A7: Apply migration
- [ ] Apply `2026_06_06_booking_email_copy.sql` via Supabase MCP (`apply_migration`). Verify the column exists: `select column_name from information_schema.columns where table_name='booking_settings' and column_name='email_copy'` → 1 row.

---

# PART B — Frontend ("Emails" tab)

## Task B1: API client

**Files:** Modify `frontend/src/components/dashboard/booking/api.ts`

- [ ] Add types + wrappers (mirror existing style; all `credentials:"include"`, throw `Error(detail)` on non-ok):
  - `EmailTemplateField { key; label; group; default: string; value: string }`
  - `EmailTemplateData { brand: {logo_url, accent_color, business_name}; fields: EmailTemplateField[] }`
  - `getEmailTemplate(slug): Promise<EmailTemplateData>` → `GET .../email-template`
  - `previewEmail(slug, case, draft): Promise<{html:string}>` → `POST .../email-preview`
  - `uploadBookingLogo(slug, file): Promise<{url:string}>` → `POST .../logo` (FormData, no Content-Type header — let the browser set the multipart boundary)
  - Extend the existing `patchSettings` body type to allow `email_copy?: Record<string,string>`.

## Task B2: Live preview frame

**Files:** Create `frontend/src/components/dashboard/booking/EmailPreviewFrame.tsx`

- [ ] A component `{ slug, caseKey, draft }` that: debounces `draft`+`caseKey` changes ~300ms, calls `previewEmail`, stores `html`, and renders `<iframe sandbox="" srcDoc={html} title="Email preview" className="h-full w-full rounded-lg border border-zinc-200 bg-white dark:border-zinc-800" />`. Show a subtle shimmer/spinner while the first preview loads; on subsequent updates keep the old preview until the new HTML arrives, then cross-fade (a short `motion/react` opacity transition, `useReducedMotion` respected). On fetch error, render a neutral "Preview unavailable" panel. Cancel stale requests (track a request id / AbortController).

## Task B3: The editor + tab wiring

**Files:** Create `frontend/src/components/dashboard/booking/EmailTemplateEditor.tsx`; Modify `frontend/src/components/dashboard/booking/BookingsSection.tsx`

- [ ] **Editor** `{ projectSlug }`:
  - `useQuery` `getEmailTemplate`. Draft state: `{ logo_url, accent_color, business_name, email_copy: Record<string,string> }` initialized from the loaded data (email_copy from field `value`s that are non-empty).
  - **Split layout** (`grid lg:grid-cols-2 gap-6`; left scrolls, right is `lg:sticky lg:top-4`):
    - **Left:** a **Brand** card — logo upload (file input → `uploadBookingLogo` → set `draft.logo_url`; show a thumbnail; "Remove" clears it) + an accent color control (`<input type="color">` + a hex text input bound to `draft.accent_color`). Then a **segmented case selector** (Confirmation · Reschedule · Cancellation · Reminder — reuse the segmented-control styling from `AppointmentsManager`). Below it, the fields for `group === activeCase`, then a **"Shared"** card with `group === "shared"` fields. Each field: label, `<input>`/`<textarea>` (textarea for headings/subtext, input for subjects/buttons), `placeholder={field.default}`, value = `draft.email_copy[key] ?? ""`; on change set/delete the key in `email_copy` (delete when emptied → falls back to default); a small "Reset" button per field that deletes the key.
    - **Right:** `<EmailPreviewFrame slug={projectSlug} caseKey={activeCase} draft={draft} />` (full height).
  - **Save** button (primary, one per the UX rule): `patchSettings(slug, { logo_url, accent_color, business_name, email_copy })`; success/error banner (mirror `BookingSettingsForm`); invalidate the `booking-settings:`/`email-template` cache keys.
  - Mobile: stack; show a "Preview" toggle that reveals the frame below the controls.
- [ ] **Tab wiring:** add an **"Emails"** tab to `BookingsSection` (after Settings) → `<EmailTemplateEditor projectSlug={slug} />`.

## Task B4: Verify
- [ ] `cd frontend && npx tsc --noEmit` clean; `npm run lint` (zero new findings); `npm test -- --run` green; milestone `npm run build` succeeds. A Vitest test for `EmailPreviewFrame` (debounce → one `previewEmail` call) and for the field-edit→`email_copy` override/reset round-trip (fetch mocked) if the harness supports it; otherwise typecheck+build suffice.

---

## Done criteria
- `email_copy` column live; renderers honor per-tenant copy with `booking_i18n` fallback; accent color on header + buttons; sending unchanged when no overrides.
- `email-template`, `email-preview`, `logo` endpoints; backend suite + ruff green.
- "Emails" tab: brand controls + per-case + shared copy fields + debounced live preview + Save; typecheck/build/tests green. No auto-commit.
