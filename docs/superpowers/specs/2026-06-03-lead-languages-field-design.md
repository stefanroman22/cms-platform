# Lead Languages Field — Design Spec

**Date:** 2026-06-03
**Status:** Approved (brainstorming)
**Author:** Stefan + Claude

## Summary

Add a multi-value **languages** field to each lead, representing the **target
website locales** the lead's future site should be built in. Admins edit it in
the lead detail drawer through a searchable, autocomplete multi-select that
supports adding and removing languages, with zero-to-many values allowed.

## Decisions (locked)

- **Meaning:** Target website locales (drives later i18n setup).
- **Storage:** Dedicated `languages text[]` column on `public.leads`.
- **Language source:** Full ISO 639 list (~180 languages) by English name.
  Stored values are the canonical English **name** strings (e.g. `"Romanian"`,
  `"Dutch"`).
- **Visibility:** Lead detail drawer only (no table/kanban/filter changes).
- **Widget:** Custom Tailwind + framer-motion combobox (no new dependency),
  consistent with the existing hand-rolled `AnimatedSelect`.

## Data Layer

### Migration

`backend/migrations/2026_06_03_lead_languages.sql`:

```sql
ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS languages text[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN leads.languages IS
'Target website locales for this lead, stored as canonical English language names (e.g. "Romanian", "Dutch"). Edited from the admin leads drawer.';

CREATE INDEX IF NOT EXISTS leads_languages_gin_idx ON leads USING gin (languages);
```

Applied via Supabase MCP (`apply_migration`) after the file is written.

### Pydantic models (`backend/auth_service/models/schemas.py`)

- `LeadOut`: add `languages: list[str] = Field(default_factory=list)`.
- `LeadUpdate`: add `languages: list[str] | None = None`.
  - Full-replacement semantics (same pattern as `opening_hours`): the client
    sends the complete desired list; `[]` clears all languages.
  - **Validation:** each entry must be a member of the canonical language-name
    allow-list. Reject unknown values with HTTP 422. De-duplicate while
    preserving order. Implemented as a Pydantic field validator on
    `LeadUpdate.languages`.

### Router (`backend/auth_service/routers/admin_leads.py`)

No special handling needed beyond what `model_dump(exclude_unset=True)` already
does — `languages` is a real column, so it flows straight into the Supabase
`update`. (Contrast with `about_attributes`, which needs merge logic.) The
field validator on the schema handles allow-list enforcement.

## Language Source of Truth

`frontend/src/lib/languages.ts` — static export:

```ts
export interface Language { code: string; name: string }
export const LANGUAGES: Language[] = [ /* ISO 639 list, English names */ ];
export const LANGUAGE_NAMES: ReadonlySet<string>; // for O(1) membership
```

Backend gets a matching allow-list. To avoid drift, the Python allow-list is
generated from / kept in sync with the same source (a small `languages.py`
constant under `backend/auth_service/` or `services/`). The set of **names** is
the contract between the two; the `code` is frontend-only convenience for keys.

## UI

### `LanguageMultiSelect` (new)

Location: `frontend/src/components/admin/leads/sections/LanguageMultiSelect.tsx`
(co-located with the section that uses it; promote to `ui/` only if reused).

Props:
- `value: string[]` — selected language names.
- `onChange: (next: string[]) => void`.

Behavior:
- Selected languages render as removable chips (each with an × button).
- A text input below/inline filters the ISO list by name (case-insensitive,
  substring). Already-selected languages are hidden from the dropdown.
- Dropdown of matches; click or Enter adds the highlighted match. Arrow
  Up/Down moves the highlight; Escape closes the dropdown. Backspace on an
  empty input removes the last chip.
- Adding clears the search input and keeps focus for fast multi-add.
- Empty selection is valid and renders nothing in the chip area.
- Dark-mode + focus-visible states, framer-motion enter/exit on dropdown and
  chips, consistent with existing drawer sections.

### `LanguagesSection` (new)

Location: `frontend/src/components/admin/leads/sections/LanguagesSection.tsx`.
Wrapped in `EditableSectionShell` (id `"languages"`, title `"Languages"`),
placed in `LeadDetailDrawer` immediately after `<ContactSection />`.

- **Read view:** chips of `lead.languages`, or an empty state (`—` / "No
  languages") when the array is empty, styled like other read views.
- **Edit view:** `LanguageMultiSelect` bound to local state seeded from
  `lead.languages`.
- **Save:** diff against `lead.languages`; if changed, `patch({ languages })`
  via `useLeadPatch`. Sending `[]` is a valid clear. `canSave` always true
  (any list, including empty, is valid).
- **Cancel:** reset local state to `lead.languages`.
- Reset local state on `lead.id` / `lead.languages` change (mirror
  `ContactSection`'s effect).

### Type wiring

- `frontend/src/components/admin/leads/types.ts`: add
  `languages: string[];` to the `Lead` interface.
- `frontend/src/components/admin/leads/hooks/useLeadPatch.ts`: add
  `languages?: string[];` to `LeadUpdatePayload`.

## Testing

### Backend (`backend/auth_service/tests/test_admin_leads_router.py`)

- PATCH sets languages on a lead → persisted, returned in `LeadOut`.
- PATCH replaces an existing list (full replacement).
- PATCH with `[]` clears all languages.
- PATCH with an unknown language name → 422.
- Duplicate entries are de-duplicated.

### Frontend (`.../sections/__tests__/LanguagesSection.test.tsx`)

Mirror the existing section tests (e.g. `ContactSection.test.tsx`):
- Renders existing languages as chips in read view.
- Empty state when no languages.
- Add a language via search → appears as chip.
- Remove a language via the × button.
- Save sends the correct `{ languages }` diff; no-op when unchanged.

## Out of Scope (YAGNI)

- Table/kanban display of languages.
- Language-based filtering in the leads filter bar.
- Native-name display or per-language flags.
- Wiring languages into the actual i18n build pipeline (separate future work).

## Affected Files

**New**
- `backend/migrations/2026_06_03_lead_languages.sql`
- `backend/auth_service/<languages allow-list>.py`
- `frontend/src/lib/languages.ts`
- `frontend/src/components/admin/leads/sections/LanguageMultiSelect.tsx`
- `frontend/src/components/admin/leads/sections/LanguagesSection.tsx`
- `frontend/src/components/admin/leads/sections/__tests__/LanguagesSection.test.tsx`

**Modified**
- `backend/auth_service/models/schemas.py`
- `backend/auth_service/routers/admin_leads.py` (only if validation lives here vs the schema)
- `backend/auth_service/tests/test_admin_leads_router.py`
- `frontend/src/components/admin/leads/types.ts`
- `frontend/src/components/admin/leads/hooks/useLeadPatch.ts`
- `frontend/src/components/admin/leads/LeadDetailDrawer.tsx`
