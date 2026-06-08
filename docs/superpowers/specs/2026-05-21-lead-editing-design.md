# Lead Editing — Design Spec

**Date:** 2026-05-21
**Branch:** `feat/lead-scraper-system`
**Author:** Stefan + Claude (Opus 4.7)
**Status:** Design — pending review

---

## 1. Problem

The admin Lead Detail drawer ([frontend/src/components/admin/leads/LeadDetailDrawer.tsx](../../../frontend/src/components/admin/leads/LeadDetailDrawer.tsx)) renders five sections that are currently **read-only**:

- **Location** — address, city, country, postal code, lat/lng.
- **Contact** — phone, email, website, Facebook, Instagram, menu.
- **Design prompt** — long-form text written by an external AI agent.
- **Opening hours** — 7-day map of free-text strings.
- **About this business** — nested Google Maps attribute structure (`extra.attributes`).

Stefan needs to correct scraped data (typos, wrong phone numbers, missing socials) and curate the Design prompt by hand before handing the lead to the website-build pipeline. Today the only way to fix anything is to edit Postgres directly.

The drawer already has an editable Pipeline + Notes + Closed-deal block, so the patterns and the `PATCH /admin/leads/{id}` endpoint exist — but the [`LeadUpdate` Pydantic schema](../../../backend/auth_service/models/schemas.py) is whitelisted to pipeline-status fields only, and `LeadDetailDrawer.tsx` is already ~450 lines and would grow past 1000 if edit logic for five more sections were inlined.

## 2. Goal

Make the five sections editable from the drawer with a calm, focused UX that scales beyond five sections without turning into a wall of inputs:

- One section in edit mode at a time, smooth framer-motion reveal between read and edit.
- Light client-side validation; defense-in-depth validation on the server (`EmailStr` / `HttpUrl`).
- Rich-text editing for Design prompt (TipTap), plain inputs everywhere else.
- Same `PATCH /admin/leads/{id}` endpoint, expanded whitelist.
- Drawer file shrinks: it becomes a layout shell that mounts section components.

**Non-goals (locked YAGNI):**
- Real-time collaborative editing.
- Cross-section undo.
- Image uploads in the rich-text editor.
- Edit audit log / versioning.
- Structured time pickers for opening hours (free text matches the scraped shape).
- E.164 phone validation.
- Making Pipeline / AI scoring / Notes use the new pattern — they keep current behavior.

## 3. Approach

### 3.1 Edit pattern (decided: B — per-section pencil toggle)

Each editable section displays its read view by default. Hovering the section header reveals a `Pencil` icon button. Clicking it:

1. Notifies the drawer-level `EditingSectionContext` that this section is taking the edit slot.
2. Any section currently in edit mode exits (its body collapses, its drafts are discarded after a brief grace period — see §3.4).
3. The clicked section's body crossfades to its edit form with `{ height: 0, opacity: 0 } → { height: "auto", opacity: 1 }`, `duration: 0.22`, `ease: "easeOut"` — the project's standard motion baseline (matches [AnimatedSelect](../../../frontend/src/components/dashboard/AnimatedSelect.tsx) and the drawer entrance).
4. Inside edit mode, the section header shows **Save** + **Cancel** buttons in place of the pencil. `Save` shows a `Loader2` spinner while the PATCH is in flight and is disabled while validation errors are present.
5. **Keyboard:** `Esc` while editing = Cancel; `Cmd/Ctrl+S` while editing = Save.

Only the five sections in scope get this treatment. Pipeline keeps its always-on pickers and the drawer-level Save button (unchanged). AI scoring stays read-only.

### 3.2 Component breakdown

New folder: `frontend/src/components/admin/leads/sections/`.

| File | Replaces in current drawer | Responsibility |
|---|---|---|
| `sections/EditableSectionShell.tsx` | — (new) | Title, pencil/Save/Cancel chrome, framer-motion reveal, error banner, `EditingSectionContext` interaction. |
| `sections/LocationSection.tsx` | `<DetailCard title="Location">` block | Read view (Rows) + edit form. |
| `sections/ContactSection.tsx` | `<DetailCard title="Contact">` block | Same. |
| `sections/DesignPromptSection.tsx` | inline Design prompt block | Read renders sanitized HTML; edit hosts TipTap. |
| `sections/OpeningHoursSection.tsx` | `<OpeningHoursTable>` import | Read = current 7-day table; edit = 7 free-text rows + per-row `Closed` quick button. |
| `sections/AboutSection.tsx` | `<AboutAttributesPanel>` import | Read = current structured tree; edit = switches + add/remove buttons. |
| `hooks/useLeadPatch.ts` | inline `handleSave` in drawer | `{ patch, saving, error }` — wraps the PATCH fetch and the `onPatched` glue. Single source for the wire format. |
| `context/EditingSectionContext.tsx` | — (new) | Tracks `editingId` at the drawer level; provides `requestEdit(id)` / `release(id)`. |

[LeadDetailDrawer.tsx](../../../frontend/src/components/admin/leads/LeadDetailDrawer.tsx) becomes a layout-only file: keeps the framer drawer chrome and the Pipeline/AI/Notes/Closed-deal blocks; mounts the five new section components below them. The existing `OpeningHoursTable` and `AboutAttributesPanel` components become the read-only renderers used internally by the new section components (no behavior change to those files; they're still rendered, just by the section wrapper).

### 3.3 Per-section edit UX

**LocationSection (edit mode).** Two-column responsive grid (`grid grid-cols-2 gap-3 md:grid-cols-2`):
- Row 1: Address (full-width, `col-span-2`).
- Row 2: City | Country.
- Row 3: Postal code | (empty).
- Row 4: Lat | Lng.

Lat / Lng share a single error line if exactly one is non-empty ("Provide both latitude and longitude, or neither").

**ContactSection (edit mode).** Stacked input rows, each prefixed with a small lucide icon (Phone, Mail, Globe, Facebook, Instagram, Menu). URL fields (`website_url`, `facebook_url`, `instagram_url`, `menu_url`) auto-prepend `https://` on blur if the user typed a bare host. Email validated with the same loose check as a contains-`@`-and-`.` rule.

**DesignPromptSection (edit mode).** TipTap editor with a sparse toolbar:
- `B` bold, `I` italic
- `H1`, `H2`
- `•` bullet list, `1.` numbered list
- `{ }` code block
- `🔗` link (prompts for URL via a small inline popover; rel locked to `noopener nofollow`)
- `↩` undo, `↪` redo

Toolbar buttons highlight via Tailwind `ring-2 ring-zinc-300 dark:ring-zinc-700` when the corresponding mark is active. The editor body shares the same rounded-lg bg-zinc-50 dark:bg-zinc-900 padding as the read view so the visual frame doesn't shift between modes. Read mode renders the stored HTML inside a `prose prose-sm prose-zinc dark:prose-invert` wrapper.

**OpeningHoursSection (edit mode).** Seven rows. Each: day label on the left, free-text input on the right, then a small ghost `Closed` button that sets the input to `"Closed"`. Empty input = day removed from the map (read view falls back to the `___` placeholder).

**AboutSection (edit mode).** Renders sections vertically. Each attribute = a small framer-motion toggle switch + attribute label (label is editable: clicking it swaps to an input). Per section: trailing `+ Add attribute` ghost button. Below all sections: `+ Add section` button that inserts an empty section with an inline rename input that auto-focuses. Per attribute & per section: a trash icon visible on hover; removes with `{ height: 0, opacity: 0 }` exit animation.

### 3.4 Save flow (frontend)

Each section maintains `draft*` local state, initialized from `lead.*` whenever `lead.id` changes (same `useEffect` pattern as the drawer's existing fields). On Save:

1. Validate (light, per §3.6). If invalid, set per-field errors, return without sending.
2. Build a `body: Partial<LeadUpdatePayload>` containing only fields where `draft !== lead.*`.
3. If `body` is empty, exit edit mode quietly (no PATCH, no toast).
4. Call `patch(body)` from `useLeadPatch`. Hook fires `PATCH /api/admin/leads/{leadId}` with `credentials: "include"`, content-type JSON.
5. On 2xx: parent's `onPatched(updated)` runs (`LeadsDashboard.handlePatched` already does `setSelectedLead(updated); refresh();`). Section exits edit mode; drafts reset from new lead.
6. On non-2xx: surface `detail.detail` (or `Update failed (status)`) in the section's inline error banner; inputs re-enable; user can retry or cancel.

When a Save is **in flight** in section A and the user clicks the pencil on section B, the click is **ignored** until A's request settles (the pencil disables while `saving` is true). This avoids a confusing partial-update state.

When the user clicks the pencil on section B while section A is in dirty-but-not-saving edit mode, section A is **cancelled silently** — drafts discarded, read view restored — with a one-second `AnimatePresence` overlap so it feels intentional rather than abrupt.

### 3.5 Backend changes

#### 3.5.1 `LeadUpdate` whitelist expansion ([backend/auth_service/models/schemas.py](../../../backend/auth_service/models/schemas.py))

```python
from pydantic import EmailStr, HttpUrl

class LeadUpdate(BaseModel):
    # --- pipeline (existing) ---
    website_build_status: WebsiteBuildStatus | None = None
    ai_workflow_status: AiWorkflowStatus | None = None
    lead_status: LeadStatus | None = None
    lead_contact_type: LeadContactType | None = None
    payment_status: PaymentStatus | None = None
    notes: str | None = None
    closed_amount: float | None = None
    # --- location (new) ---
    address: str | None = None
    city: str | None = None
    country: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None
    # --- contact (new) ---
    phone: str | None = None
    email: EmailStr | None = None
    website_url: HttpUrl | None = None
    facebook_url: HttpUrl | None = None
    instagram_url: HttpUrl | None = None
    menu_url: HttpUrl | None = None
    # --- design prompt (new, HTML, sanitized server-side) ---
    design_prompt: str | None = None
    # --- opening hours (new, full replacement) ---
    opening_hours: dict[str, str] | None = None
    # --- about attributes (new, virtual — router merges into extra.attributes) ---
    about_attributes: dict[str, dict[str, bool]] | None = None
```

`EmailStr` / `HttpUrl` give us defense-in-depth: even if the FE checks miss something, Pydantic rejects with 422 before the row is touched.

#### 3.5.2 `patch_lead` router ([backend/auth_service/routers/admin_leads.py](../../../backend/auth_service/routers/admin_leads.py))

Three additions:

1. **HTML sanitization.** If `design_prompt` is in `patch` and non-null, run it through `bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)`. Allowed tags: `p, br, strong, em, code, pre, h1, h2, h3, ul, ol, li, a`. Allowed `<a>` attrs: `href`, `title`. Always force `rel="noopener nofollow"` and `target="_blank"` post-sanitization.
2. **`about_attributes` merge.** If `about_attributes` is in `patch`:
   - The existing `closed_amount`-gate branch already fetches the current row; we extend its `select(...)` to include `extra`. If the patch contains `about_attributes` but not `closed_amount`, we still fetch (the read is cheap; admin tab, low traffic).
   - `current_extra = current_row.get("extra") or {}; current_extra["attributes"] = new_attrs; patch["extra"] = current_extra` — preserves every other `extra` key the scraper set.
   - `patch.pop("about_attributes")` so Supabase doesn't receive the virtual key.
3. **URL fields stored as strings.** `HttpUrl` parses to a Pydantic URL type; convert each URL field in `patch` to `str(value)` before sending to Supabase so the column stays a plain TEXT.

The existing `exclude_unset=True` dump semantic stays — keeps "explicit null clears the column" working for `notes`, `closed_amount`, and now `design_prompt`, `address`, etc.

#### 3.5.3 Tests

Extend [test_admin_leads_router.py](../../../backend/auth_service/tests/test_admin_leads_router.py) with:

- One happy-path test per new field group (location, contact, design_prompt, opening_hours, about_attributes).
- One sanitization test: PATCH `design_prompt` with `<script>` content; assert the saved column has no script tag.
- One merge test: PATCH `about_attributes` on a row whose `extra` has other keys; assert those keys survive.
- One validation test: invalid email returns 422 from Pydantic (no DB write).

### 3.6 Validation rules (frontend, light)

| Field | Rule |
|---|---|
| `email` | Must match `/^\S+@\S+\.\S+$/` or be empty. |
| `website_url`, `facebook_url`, `instagram_url`, `menu_url` | Auto-prepend `https://` on blur if missing scheme. Reject if contains whitespace. |
| `lat` | Numeric in `[-90, 90]`, or empty. |
| `lng` | Numeric in `[-180, 180]`, or empty. |
| Lat + Lng together | Both empty OR both filled — never one. |
| `phone` | Any string (no format check). |
| Opening hours rows | Any string, including empty. |
| About attributes | When adding: section name and attribute label must be non-empty. |
| Design prompt | Any HTML the toolbar can produce (sanitized server-side). |

Errors render as `text-xs text-red-600 dark:text-red-400` under the offending field, animated in via a shared `errorBlip` framer-motion variant. The section's Save button stays disabled until all errors clear.

### 3.7 Animations

A single [animations module](../../../frontend/src/lib/animations.ts) already exists and is used by `OpeningHoursTable` and `AboutAttributesPanel`. We add three variants:

```ts
export const editReveal = {
  hidden: { height: 0, opacity: 0 },
  visible: { height: "auto", opacity: 1, transition: { duration: 0.22, ease: "easeOut" } },
};
export const rowAdd = {
  hidden: { x: -8, opacity: 0 },
  visible: { x: 0, opacity: 1, transition: { duration: 0.18, ease: "easeOut" } },
};
export const errorBlip = {
  hidden: { y: -2, opacity: 0 },
  visible: { y: 0, opacity: 1, transition: { duration: 0.16, ease: "easeOut" } },
};
```

All three keep the project's existing motion baseline (`0.22 / easeOut`). No new motion concepts.

### 3.8 Dependencies

Add to `frontend/package.json`:
- `@tiptap/react`
- `@tiptap/starter-kit`
- `@tiptap/extension-link`
- `@tailwindcss/typography` (only if not already pinned — needed for `prose` styling on the read view).

Add to [backend/requirements.txt](../../../backend/requirements.txt):
- `bleach` (with the matching hash in `requirements.lock`).

### 3.9 ui-ux-pro-max consultation

During implementation, the `ui-ux-pro-max` skill is **required** for finalizing the visual layer of:
- TipTap toolbar iconography and active-state styling.
- Switch-toggle visuals for About attributes (modern pill switch, animated thumb).
- Empty-state styling for sections with no data (Location with no address, Contact with no phone/email, etc.).
- Pencil-icon hover-reveal styling (timing + opacity curve).
- Save/Cancel button alignment in section headers.

The implementation plan must include a checkpoint where ui-ux-pro-max reviews each section's edit view before the section is marked complete.

## 4. Out of scope

- Real-time collaborative editing of the same lead from two browsers.
- Optimistic UI; we wait for the PATCH response before swapping the lead state.
- Diff / history of who-edited-what (out of scope for now; the audit log story is a separate spec).
- Image uploads inside the rich-text editor.
- Localization of opening-hours rendering (we render whatever the scraper saved).
- Phone number formatting / E.164 validation.

## 5. Risk register

| Risk | Mitigation |
|---|---|
| TipTap HTML escapes sanitizer | `bleach` allow-list is restrictive (no `<script>`, no `style`, no `on*` attrs). Test the round-trip. |
| Concurrent edits to `extra` (admin in two tabs) | Last write wins; acceptable given low admin concurrency. Add a console warning if `lead.updated_at` from the server is newer than what the drawer opened with — future enhancement, not in this spec. |
| Bundle bloat from TipTap | One editor on one page. Lazy-import (`next/dynamic`) the editor so the lead list page doesn't ship the 60 KB until the drawer opens. |
| URL fields rejected by `HttpUrl` for unusual but valid URLs | Coerce to `str` before storage; if `HttpUrl` proves too strict in practice, swap to a plain string + manual `/^https?:\/\//` check. Defer until we see a real failure. |
| `exclude_unset=True` regression | Already tested in [test_admin_leads_router.py::test_patch_closed_amount_can_be_cleared_to_null](../../../backend/auth_service/tests/test_admin_leads_router.py). Add equivalent tests for the new clearable fields. |

## 6. Testing strategy

- **Backend unit tests** in `test_admin_leads_router.py` (see §3.5.3).
- **Frontend component tests** (lightweight): one render-time test per new section component asserting that (a) edit mode reveals on pencil click, (b) Save with no changes is a no-op, (c) Save with valid changes calls the patch hook. Use the existing testing setup.
- **Manual E2E checklist** (added to the spec PR description):
  1. Open a lead; edit Location; Save; reopen and confirm persistence.
  2. Edit Contact; introduce an invalid email; verify Save disabled + error text.
  3. Edit Design prompt with bold/italic/list; Save; verify formatting survives.
  4. Edit Opening hours; mark Tuesday Closed; Save.
  5. Edit About; add a new section, add an attribute under it, toggle one, delete one; Save; verify other `extra` keys survive (inspect via Supabase).
  6. Switch from editing section A to section B while A is dirty; verify A discards cleanly.
  7. Submit invalid email; backend returns 422; section stays in edit mode with error.

## 7. Files touched

**New:**
- `frontend/src/components/admin/leads/sections/EditableSectionShell.tsx`
- `frontend/src/components/admin/leads/sections/LocationSection.tsx`
- `frontend/src/components/admin/leads/sections/ContactSection.tsx`
- `frontend/src/components/admin/leads/sections/DesignPromptSection.tsx`
- `frontend/src/components/admin/leads/sections/OpeningHoursSection.tsx`
- `frontend/src/components/admin/leads/sections/AboutSection.tsx`
- `frontend/src/components/admin/leads/hooks/useLeadPatch.ts`
- `frontend/src/components/admin/leads/context/EditingSectionContext.tsx`

**Modified:**
- `frontend/src/components/admin/leads/LeadDetailDrawer.tsx` — slimmed to a layout shell.
- `frontend/src/components/admin/leads/types.ts` — no shape change, but a new `LeadUpdatePayload` type for the patch hook (mirrors backend `LeadUpdate`).
- `frontend/src/lib/animations.ts` — add `editReveal`, `rowAdd`, `errorBlip` variants.
- `frontend/package.json` — TipTap packages, typography plugin if needed.
- `backend/auth_service/models/schemas.py` — `LeadUpdate` whitelist expansion.
- `backend/auth_service/routers/admin_leads.py` — sanitization + `about_attributes` merge.
- `backend/requirements.txt` + `requirements.lock` — add `bleach`.
- `backend/auth_service/tests/test_admin_leads_router.py` — new test cases per §3.5.3.

**Unchanged in behavior, used as read-only renderers:**
- `frontend/src/components/admin/leads/OpeningHoursTable.tsx`
- `frontend/src/components/admin/leads/AboutAttributesPanel.tsx`

## 8. Definition of done

- All five sections support read + edit, with one-at-a-time editing enforced by `EditingSectionContext`.
- TipTap editor present in Design prompt; sanitized HTML round-trips through backend.
- Light validation in place per §3.6; backend returns 422 for invalid email/URL.
- About-attributes save preserves unrelated `extra` keys.
- New + existing tests pass (`pytest` + frontend test suite).
- `ui-ux-pro-max` reviewed each section's visual layer.
- Manual E2E checklist (§6) all green.
