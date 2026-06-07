# Lead Languages Field Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an editable, searchable multi-select **languages** field (target website locales) to each lead, shown in the lead detail drawer, supporting 0-to-many values with add/remove.

**Architecture:** A real `text[]` column on `public.leads` carries the data. The Pydantic `LeadOut`/`LeadUpdate` models expose it with full-replacement PATCH semantics. The frontend stores canonical English language names; a static ISO 639-1 list in `frontend/src/lib/languages.ts` powers a custom Tailwind + framer-motion combobox (`LanguageMultiSelect`) rendered inside a new `LanguagesSection` wrapped in the existing `EditableSectionShell`.

**Tech Stack:** FastAPI + Pydantic v2, Supabase (Postgres), Next.js 16 + React + TypeScript, Tailwind, framer-motion, Vitest + Testing Library, pytest.

---

## ⚠️ Refinement to the approved spec (please confirm or veto before execution)

The spec called for backend validation against a **full ISO 639 name allow-list**, kept in sync between TS and Python. Maintaining 184 language names duplicated in two languages is a real drift/maintenance hazard. This plan instead uses **structural backend validation** — trim, drop empties, de-duplicate, reject non-strings, cap each name at 60 chars and the list at 50 items — while the **frontend autocomplete remains the real constraint** (users can only pick from the ISO list). This keeps a single source of truth (the TS list) and still prevents junk/abuse. If you require a hard server-side name allow-list instead, say so and Task 2 will carry the full Python name set.

---

## File Structure

**New files**
- `backend/migrations/2026_06_03_lead_languages.sql` — adds the `languages` column + GIN index.
- `frontend/src/lib/languages.ts` — canonical ISO 639-1 language list + helpers (frontend source of truth).
- `frontend/src/components/admin/leads/sections/LanguageMultiSelect.tsx` — the searchable add/remove combobox widget.
- `frontend/src/components/admin/leads/sections/LanguagesSection.tsx` — drawer section wrapping the widget in `EditableSectionShell`.
- `frontend/src/components/admin/leads/sections/__tests__/LanguagesSection.test.tsx` — section tests.

**Modified files**
- `backend/auth_service/models/schemas.py` — `LeadOut.languages`, `LeadUpdate.languages` + field validator.
- `backend/auth_service/tests/test_admin_leads_router.py` — PATCH languages tests.
- `frontend/src/components/admin/leads/types.ts` — `Lead.languages`.
- `frontend/src/components/admin/leads/hooks/useLeadPatch.ts` — `LeadUpdatePayload.languages`.
- `frontend/src/components/admin/leads/LeadDetailDrawer.tsx` — mount `<LanguagesSection />` after `<ContactSection />`.

---

## Task 1: Database migration

**Files:**
- Create: `backend/migrations/2026_06_03_lead_languages.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- Lead target-website locales. Stored as canonical English language names
-- (e.g. 'Romanian', 'Dutch'). Edited from the admin leads drawer.
ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS languages text[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN leads.languages IS
'Target website locales for this lead, stored as canonical English language names (e.g. "Romanian", "Dutch"). Edited from the admin leads drawer.';

CREATE INDEX IF NOT EXISTS leads_languages_gin_idx ON leads USING gin (languages);
```

- [ ] **Step 2: Apply the migration via Supabase MCP**

Use the `mcp__supabase__apply_migration` tool with name `lead_languages_2026_06_03` and the SQL above. (Per project convention, the controller applies migrations via MCP — do not ask the user to run it manually.)

- [ ] **Step 3: Verify the column exists**

Use `mcp__supabase__list_tables` (or `mcp__supabase__execute_sql` with
`select column_name, data_type, column_default from information_schema.columns where table_name = 'leads' and column_name = 'languages';`).
Expected: one row, `data_type = ARRAY`, `column_default = '{}'::text[]`.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/2026_06_03_lead_languages.sql
git commit -m "feat(leads): add languages column to leads table"
```

---

## Task 2: Backend schema + validation (TDD)

**Files:**
- Modify: `backend/auth_service/models/schemas.py` (LeadOut ~line 486, LeadUpdate ~line 527)
- Test: `backend/auth_service/tests/test_admin_leads_router.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/auth_service/tests/test_admin_leads_router.py`:

```python
def test_patch_languages_sets_list(mock_supabase, client, auth_as, admin_user):
    """languages is a full replacement of the string array."""
    auth_as(admin_user)
    updated = _lead_row(languages=["Romanian", "Dutch"])
    mock_supabase.execute.return_value = MagicMock(data=[updated])
    resp = client.patch(
        "/admin/leads/lead-1", json={"languages": ["Romanian", "Dutch"]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["languages"] == ["Romanian", "Dutch"]


def test_patch_languages_can_be_cleared_to_empty(mock_supabase, client, auth_as, admin_user):
    """Sending an empty list clears all languages."""
    auth_as(admin_user)
    updated = _lead_row(languages=[])
    mock_supabase.execute.return_value = MagicMock(data=[updated])
    resp = client.patch("/admin/leads/lead-1", json={"languages": []})
    assert resp.status_code == 200, resp.text
    assert resp.json()["languages"] == []


def test_patch_languages_dedupes_and_trims(mock_supabase, client, auth_as, admin_user):
    """Duplicate / whitespace-padded / empty entries are normalized before write."""
    auth_as(admin_user)
    captured = {}

    def capture_update(payload):
        captured["payload"] = payload
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(
            data=[_lead_row(languages=payload["languages"])]
        )
        return chain

    mock_supabase.update.side_effect = capture_update
    resp = client.patch(
        "/admin/leads/lead-1",
        json={"languages": [" Romanian ", "Romanian", "", "Dutch"]},
    )
    assert resp.status_code == 200, resp.text
    assert captured["payload"]["languages"] == ["Romanian", "Dutch"]


def test_patch_languages_rejects_overlong_name(client, auth_as, admin_user):
    """A single absurdly long entry is rejected with 422 (junk guard)."""
    auth_as(admin_user)
    resp = client.patch("/admin/leads/lead-1", json={"languages": ["x" * 61]})
    assert resp.status_code == 422
```

Also add `"languages": []` to the `base` dict inside `_lead_row` (after `"photo_urls": []`) so default rows carry the field:

```python
        "photo_urls": [],
        "languages": [],
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && source venv/Scripts/activate && python -m pytest auth_service/tests/test_admin_leads_router.py -k languages -v`
Expected: FAIL — `languages` not yet on the model (422 / KeyError), new tests error.

- [ ] **Step 3: Add `languages` to `LeadOut`**

In `backend/auth_service/models/schemas.py`, inside `class LeadOut`, after the `notes: str | None = None` line (~486):

```python
    notes: str | None = None
    languages: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add `languages` + validator to `LeadUpdate`**

In `class LeadUpdate`, after the `opening_hours` field (~524) and before `about_attributes`:

```python
    # languages — target website locales; full replacement of the list.
    # [] clears all languages. Structural validation only (the frontend
    # autocomplete constrains values to the ISO 639-1 list).
    languages: list[str] | None = None
```

Then add this validator as a method on `LeadUpdate` (place it after the fields, alongside other validators in the file):

```python
    @field_validator("languages", mode="after")
    @classmethod
    def _normalize_languages(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in v:
            if not isinstance(raw, str):
                raise ValueError("each language must be a string")
            name = raw.strip()
            if not name:
                continue
            if len(name) > 60:
                raise ValueError("language name too long (max 60 chars)")
            if name not in seen:
                seen.add(name)
                cleaned.append(name)
        if len(cleaned) > 50:
            raise ValueError("too many languages (max 50)")
        return cleaned
```

(`field_validator` and `Field` are already imported at the top of the file.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && source venv/Scripts/activate && python -m pytest auth_service/tests/test_admin_leads_router.py -k languages -v`
Expected: 4 passed.

- [ ] **Step 6: Run the full leads router suite (no regressions)**

Run: `cd backend && source venv/Scripts/activate && python -m pytest auth_service/tests/test_admin_leads_router.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/auth_service/models/schemas.py backend/auth_service/tests/test_admin_leads_router.py
git commit -m "feat(leads): expose + validate languages in lead schema"
```

---

## Task 3: Frontend language list module

**Files:**
- Create: `frontend/src/lib/languages.ts`

- [ ] **Step 1: Write the language list module**

```ts
// Canonical ISO 639-1 language list (English names). Frontend source of
// truth for the lead "Languages" picker. `code` is a stable React key only;
// the value persisted to the backend is the English `name` string.

export interface Language {
  code: string;
  name: string;
}

export const LANGUAGES: Language[] = [
  { code: "ab", name: "Abkhazian" },
  { code: "aa", name: "Afar" },
  { code: "af", name: "Afrikaans" },
  { code: "ak", name: "Akan" },
  { code: "sq", name: "Albanian" },
  { code: "am", name: "Amharic" },
  { code: "ar", name: "Arabic" },
  { code: "an", name: "Aragonese" },
  { code: "hy", name: "Armenian" },
  { code: "as", name: "Assamese" },
  { code: "av", name: "Avaric" },
  { code: "ae", name: "Avestan" },
  { code: "ay", name: "Aymara" },
  { code: "az", name: "Azerbaijani" },
  { code: "bm", name: "Bambara" },
  { code: "ba", name: "Bashkir" },
  { code: "eu", name: "Basque" },
  { code: "be", name: "Belarusian" },
  { code: "bn", name: "Bengali" },
  { code: "bi", name: "Bislama" },
  { code: "bs", name: "Bosnian" },
  { code: "br", name: "Breton" },
  { code: "bg", name: "Bulgarian" },
  { code: "my", name: "Burmese" },
  { code: "ca", name: "Catalan" },
  { code: "ch", name: "Chamorro" },
  { code: "ce", name: "Chechen" },
  { code: "ny", name: "Chichewa" },
  { code: "zh", name: "Chinese" },
  { code: "cu", name: "Church Slavonic" },
  { code: "cv", name: "Chuvash" },
  { code: "kw", name: "Cornish" },
  { code: "co", name: "Corsican" },
  { code: "cr", name: "Cree" },
  { code: "hr", name: "Croatian" },
  { code: "cs", name: "Czech" },
  { code: "da", name: "Danish" },
  { code: "dv", name: "Divehi" },
  { code: "nl", name: "Dutch" },
  { code: "dz", name: "Dzongkha" },
  { code: "en", name: "English" },
  { code: "eo", name: "Esperanto" },
  { code: "et", name: "Estonian" },
  { code: "ee", name: "Ewe" },
  { code: "fo", name: "Faroese" },
  { code: "fj", name: "Fijian" },
  { code: "fi", name: "Finnish" },
  { code: "fr", name: "French" },
  { code: "fy", name: "Western Frisian" },
  { code: "ff", name: "Fulah" },
  { code: "gd", name: "Gaelic" },
  { code: "gl", name: "Galician" },
  { code: "lg", name: "Ganda" },
  { code: "ka", name: "Georgian" },
  { code: "de", name: "German" },
  { code: "el", name: "Greek" },
  { code: "kl", name: "Kalaallisut" },
  { code: "gn", name: "Guarani" },
  { code: "gu", name: "Gujarati" },
  { code: "ht", name: "Haitian Creole" },
  { code: "ha", name: "Hausa" },
  { code: "he", name: "Hebrew" },
  { code: "hz", name: "Herero" },
  { code: "hi", name: "Hindi" },
  { code: "ho", name: "Hiri Motu" },
  { code: "hu", name: "Hungarian" },
  { code: "is", name: "Icelandic" },
  { code: "io", name: "Ido" },
  { code: "ig", name: "Igbo" },
  { code: "id", name: "Indonesian" },
  { code: "ia", name: "Interlingua" },
  { code: "ie", name: "Interlingue" },
  { code: "iu", name: "Inuktitut" },
  { code: "ik", name: "Inupiaq" },
  { code: "ga", name: "Irish" },
  { code: "it", name: "Italian" },
  { code: "ja", name: "Japanese" },
  { code: "jv", name: "Javanese" },
  { code: "kn", name: "Kannada" },
  { code: "kr", name: "Kanuri" },
  { code: "ks", name: "Kashmiri" },
  { code: "kk", name: "Kazakh" },
  { code: "km", name: "Central Khmer" },
  { code: "ki", name: "Kikuyu" },
  { code: "rw", name: "Kinyarwanda" },
  { code: "ky", name: "Kyrgyz" },
  { code: "kv", name: "Komi" },
  { code: "kg", name: "Kongo" },
  { code: "ko", name: "Korean" },
  { code: "kj", name: "Kuanyama" },
  { code: "ku", name: "Kurdish" },
  { code: "lo", name: "Lao" },
  { code: "la", name: "Latin" },
  { code: "lv", name: "Latvian" },
  { code: "li", name: "Limburgish" },
  { code: "ln", name: "Lingala" },
  { code: "lt", name: "Lithuanian" },
  { code: "lu", name: "Luba-Katanga" },
  { code: "lb", name: "Luxembourgish" },
  { code: "mk", name: "Macedonian" },
  { code: "mg", name: "Malagasy" },
  { code: "ms", name: "Malay" },
  { code: "ml", name: "Malayalam" },
  { code: "mt", name: "Maltese" },
  { code: "gv", name: "Manx" },
  { code: "mi", name: "Maori" },
  { code: "mr", name: "Marathi" },
  { code: "mh", name: "Marshallese" },
  { code: "mn", name: "Mongolian" },
  { code: "na", name: "Nauru" },
  { code: "nv", name: "Navajo" },
  { code: "nd", name: "North Ndebele" },
  { code: "nr", name: "South Ndebele" },
  { code: "ng", name: "Ndonga" },
  { code: "ne", name: "Nepali" },
  { code: "no", name: "Norwegian" },
  { code: "nb", name: "Norwegian Bokmål" },
  { code: "nn", name: "Norwegian Nynorsk" },
  { code: "oc", name: "Occitan" },
  { code: "oj", name: "Ojibwa" },
  { code: "or", name: "Oriya" },
  { code: "om", name: "Oromo" },
  { code: "os", name: "Ossetian" },
  { code: "pi", name: "Pali" },
  { code: "ps", name: "Pashto" },
  { code: "fa", name: "Persian" },
  { code: "pl", name: "Polish" },
  { code: "pt", name: "Portuguese" },
  { code: "pa", name: "Punjabi" },
  { code: "qu", name: "Quechua" },
  { code: "ro", name: "Romanian" },
  { code: "rm", name: "Romansh" },
  { code: "rn", name: "Rundi" },
  { code: "ru", name: "Russian" },
  { code: "se", name: "Northern Sami" },
  { code: "sm", name: "Samoan" },
  { code: "sg", name: "Sango" },
  { code: "sa", name: "Sanskrit" },
  { code: "sc", name: "Sardinian" },
  { code: "sr", name: "Serbian" },
  { code: "sn", name: "Shona" },
  { code: "sd", name: "Sindhi" },
  { code: "si", name: "Sinhala" },
  { code: "sk", name: "Slovak" },
  { code: "sl", name: "Slovenian" },
  { code: "so", name: "Somali" },
  { code: "st", name: "Southern Sotho" },
  { code: "es", name: "Spanish" },
  { code: "su", name: "Sundanese" },
  { code: "sw", name: "Swahili" },
  { code: "ss", name: "Swati" },
  { code: "sv", name: "Swedish" },
  { code: "tl", name: "Tagalog" },
  { code: "ty", name: "Tahitian" },
  { code: "tg", name: "Tajik" },
  { code: "ta", name: "Tamil" },
  { code: "tt", name: "Tatar" },
  { code: "te", name: "Telugu" },
  { code: "th", name: "Thai" },
  { code: "bo", name: "Tibetan" },
  { code: "ti", name: "Tigrinya" },
  { code: "to", name: "Tonga" },
  { code: "ts", name: "Tsonga" },
  { code: "tn", name: "Tswana" },
  { code: "tr", name: "Turkish" },
  { code: "tk", name: "Turkmen" },
  { code: "tw", name: "Twi" },
  { code: "ug", name: "Uyghur" },
  { code: "uk", name: "Ukrainian" },
  { code: "ur", name: "Urdu" },
  { code: "uz", name: "Uzbek" },
  { code: "ve", name: "Venda" },
  { code: "vi", name: "Vietnamese" },
  { code: "vo", name: "Volapük" },
  { code: "wa", name: "Walloon" },
  { code: "cy", name: "Welsh" },
  { code: "wo", name: "Wolof" },
  { code: "xh", name: "Xhosa" },
  { code: "ii", name: "Sichuan Yi" },
  { code: "yi", name: "Yiddish" },
  { code: "yo", name: "Yoruba" },
  { code: "za", name: "Zhuang" },
  { code: "zu", name: "Zulu" },
];

/** All language names, for O(1) membership checks. */
export const LANGUAGE_NAMES: ReadonlySet<string> = new Set(LANGUAGES.map((l) => l.name));

/**
 * Case-insensitive substring search over language names. Already-selected
 * names are excluded. Returns at most `limit` matches, name-sorted.
 */
export function searchLanguages(
  query: string,
  selected: readonly string[],
  limit = 8
): Language[] {
  const q = query.trim().toLowerCase();
  const taken = new Set(selected);
  const matches = LANGUAGES.filter(
    (l) => !taken.has(l.name) && (q === "" || l.name.toLowerCase().includes(q))
  );
  return matches.slice(0, limit);
}
```

- [ ] **Step 2: Type-check the module**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors in `src/lib/languages.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/languages.ts
git commit -m "feat(leads): add ISO 639-1 language list module"
```

---

## Task 4: Frontend type wiring

**Files:**
- Modify: `frontend/src/components/admin/leads/types.ts` (Lead interface, after `notes` ~line 59)
- Modify: `frontend/src/components/admin/leads/hooks/useLeadPatch.ts` (`LeadUpdatePayload`, after `about_attributes` ~line 34)

- [ ] **Step 1: Add `languages` to the `Lead` interface**

In `types.ts`, inside `interface Lead`, after `notes: string | null;`:

```ts
  notes: string | null;
  languages: string[];
```

- [ ] **Step 2: Add `languages` to `LeadUpdatePayload`**

In `useLeadPatch.ts`, inside `interface LeadUpdatePayload`, after the `about_attributes` line:

```ts
  about_attributes?: Record<string, Record<string, boolean>> | null;
  // languages — full replacement of the target-locale list; [] clears all.
  languages?: string[];
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/admin/leads/types.ts frontend/src/components/admin/leads/hooks/useLeadPatch.ts
git commit -m "feat(leads): wire languages into frontend lead types"
```

---

## Task 5: `LanguageMultiSelect` widget

**Files:**
- Create: `frontend/src/components/admin/leads/sections/LanguageMultiSelect.tsx`

- [ ] **Step 1: Write the component**

```tsx
"use client";

import { useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";
import { searchLanguages } from "@/lib/languages";

interface Props {
  value: string[];
  onChange: (next: string[]) => void;
}

/**
 * Searchable add/remove multi-select for language names. Selected languages
 * render as removable chips; typing filters the ISO list; click or Enter adds
 * the highlighted match; Backspace on an empty input removes the last chip.
 */
export function LanguageMultiSelect({ value, onChange }: Props) {
  const prefersReduced = useReducedMotion();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const matches = useMemo(() => searchLanguages(query, value), [query, value]);

  function add(name: string) {
    if (!value.includes(name)) onChange([...value, name]);
    setQuery("");
    setHighlight(0);
    inputRef.current?.focus();
  }

  function remove(name: string) {
    onChange(value.filter((l) => l !== name));
    inputRef.current?.focus();
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => Math.min(h + 1, Math.max(matches.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const pick = matches[highlight];
      if (pick) add(pick.name);
    } else if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "Backspace" && query === "" && value.length > 0) {
      remove(value[value.length - 1]);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      {value.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {value.map((name) => (
            <span
              key={name}
              className="inline-flex items-center gap-1 rounded-full bg-zinc-200 dark:bg-zinc-800 pl-2.5 pr-1 py-0.5 text-xs text-zinc-800 dark:text-zinc-200"
            >
              {name}
              <button
                type="button"
                aria-label={`Remove ${name}`}
                onClick={() => remove(name)}
                className="inline-flex items-center justify-center h-4 w-4 rounded-full text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-300 dark:hover:bg-zinc-700 cursor-pointer"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          aria-label="Search languages"
          value={query}
          placeholder="Search languages…"
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setHighlight(0);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          className="w-full rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
        />

        <AnimatePresence>
          {open && matches.length > 0 && (
            <motion.ul
              initial={{ opacity: 0, y: prefersReduced ? 0 : -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: prefersReduced ? 0 : -4 }}
              transition={{ duration: 0.14, ease: "easeOut" }}
              className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 shadow-lg"
            >
              {matches.map((lang, i) => (
                <li key={lang.code}>
                  <button
                    type="button"
                    // onMouseDown (not onClick) fires before input blur closes the list.
                    onMouseDown={(e) => {
                      e.preventDefault();
                      add(lang.name);
                    }}
                    onMouseEnter={() => setHighlight(i)}
                    className={`w-full text-left px-2.5 py-1.5 text-sm cursor-pointer ${
                      i === highlight
                        ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                        : "text-zinc-700 dark:text-zinc-300"
                    }`}
                  >
                    {lang.name}
                  </button>
                </li>
              ))}
            </motion.ul>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/admin/leads/sections/LanguageMultiSelect.tsx
git commit -m "feat(leads): add LanguageMultiSelect search/add/remove widget"
```

---

## Task 6: `LanguagesSection` + drawer mount (TDD)

**Files:**
- Create: `frontend/src/components/admin/leads/sections/LanguagesSection.tsx`
- Create: `frontend/src/components/admin/leads/sections/__tests__/LanguagesSection.test.tsx`
- Modify: `frontend/src/components/admin/leads/LeadDetailDrawer.tsx` (import + mount after `<ContactSection />` ~line 394)

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/admin/leads/sections/__tests__/LanguagesSection.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EditingSectionProvider } from "../../context/EditingSectionContext";
import { LanguagesSection } from "../LanguagesSection";
import type { Lead } from "../../types";

function makeLead(languages: string[]): Lead {
  return { id: "lead-1", languages } as unknown as Lead;
}

function renderSection(lead: Lead) {
  return render(
    <EditingSectionProvider>
      <LanguagesSection lead={lead} onPatched={vi.fn()} />
    </EditingSectionProvider>
  );
}

describe("LanguagesSection", () => {
  it("renders existing languages as chips in read view", () => {
    renderSection(makeLead(["Romanian", "Dutch"]));
    expect(screen.getByText("Romanian")).toBeTruthy();
    expect(screen.getByText("Dutch")).toBeTruthy();
  });

  it("shows an empty state when there are no languages", () => {
    renderSection(makeLead([]));
    expect(screen.getByText(/no languages/i)).toBeTruthy();
  });

  it("adds a language via search in edit view", () => {
    renderSection(makeLead([]));
    fireEvent.click(screen.getByLabelText("Edit Languages"));
    const input = screen.getByLabelText("Search languages");
    fireEvent.change(input, { target: { value: "roman" } });
    fireEvent.mouseDown(screen.getByText("Romanian"));
    expect(screen.getByLabelText("Remove Romanian")).toBeTruthy();
  });

  it("removes a language via the chip × button in edit view", () => {
    renderSection(makeLead(["Romanian"]));
    fireEvent.click(screen.getByLabelText("Edit Languages"));
    fireEvent.click(screen.getByLabelText("Remove Romanian"));
    expect(screen.queryByLabelText("Remove Romanian")).toBeNull();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/LanguagesSection.test.tsx`
Expected: FAIL — `LanguagesSection` module not found.

- [ ] **Step 3: Write the `LanguagesSection` component**

Create `frontend/src/components/admin/leads/sections/LanguagesSection.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { LanguageMultiSelect } from "./LanguageMultiSelect";
import { useLeadPatch } from "../hooks/useLeadPatch";

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

/** Compares two string lists order-insensitively. */
function sameSet(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false;
  const setB = new Set(b);
  return a.every((x) => setB.has(x));
}

export function LanguagesSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);
  const [languages, setLanguages] = useState<string[]>(lead.languages ?? []);

  useEffect(() => {
    setLanguages(lead.languages ?? []);
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.languages]);

  async function handleSave() {
    if (sameSet(languages, lead.languages ?? [])) return;
    await patch({ languages });
  }

  function handleCancel() {
    setLanguages(lead.languages ?? []);
    clearError();
  }

  const readView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      {(lead.languages ?? []).length === 0 ? (
        <span className="text-xs text-zinc-400 dark:text-zinc-600">No languages</span>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {lead.languages.map((name) => (
            <span
              key={name}
              className="inline-flex items-center rounded-full bg-zinc-200 dark:bg-zinc-800 px-2.5 py-0.5 text-xs text-zinc-800 dark:text-zinc-200"
            >
              {name}
            </span>
          ))}
        </div>
      )}
    </div>
  );

  const editView = <LanguageMultiSelect value={languages} onChange={setLanguages} />;

  return (
    <EditableSectionShell
      id="languages"
      title="Languages"
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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/LanguagesSection.test.tsx`
Expected: 4 passed.

- [ ] **Step 5: Mount the section in the drawer**

In `frontend/src/components/admin/leads/LeadDetailDrawer.tsx`, add the import alongside the other section imports (after the `ContactSection` import, ~line 23):

```tsx
import { ContactSection } from "./sections/ContactSection";
import { LanguagesSection } from "./sections/LanguagesSection";
```

Then mount it right after `<ContactSection />` (~line 394):

```tsx
        <ContactSection lead={lead} onPatched={onPatched} />

        <LanguagesSection lead={lead} onPatched={onPatched} />
```

- [ ] **Step 6: Type-check + commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

```bash
git add frontend/src/components/admin/leads/sections/LanguagesSection.tsx frontend/src/components/admin/leads/sections/__tests__/LanguagesSection.test.tsx frontend/src/components/admin/leads/LeadDetailDrawer.tsx
git commit -m "feat(leads): add Languages drawer section with add/remove"
```

---

## Task 7: UI/UX polish pass (ui-ux-pro-max)

**Files:**
- Modify: `frontend/src/components/admin/leads/sections/LanguageMultiSelect.tsx`
- Modify: `frontend/src/components/admin/leads/sections/LanguagesSection.tsx`

- [ ] **Step 1: Invoke the ui-ux-pro-max skill**

Use the `Skill` tool with `ui-ux-pro-max` to review and refine the Languages section + widget. Scope the review to: chip visual weight and spacing, dropdown elevation/contrast in light & dark mode, focus-visible rings, highlighted-row affordance, empty-state tone, keyboard discoverability, and motion timing consistency with the other drawer sections (`ContactSection`, `OpeningHoursSection`). Apply only styling/interaction refinements — do not change the data contract (`value: string[]` / `onChange`) or the `EditableSectionShell` wiring.

- [ ] **Step 2: Re-run the section tests (no behavioral regressions)**

Run: `cd frontend && npx vitest run src/components/admin/leads/sections/__tests__/LanguagesSection.test.tsx`
Expected: 4 passed. (If a polish change renamed an aria-label used by a test, update the test to match and note it.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/admin/leads/sections/LanguageMultiSelect.tsx frontend/src/components/admin/leads/sections/LanguagesSection.tsx
git commit -m "style(leads): polish Languages section UI/UX"
```

---

## Task 8: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Backend — full lead router suite**

Run: `cd backend && source venv/Scripts/activate && python -m pytest auth_service/tests/test_admin_leads_router.py -v`
Expected: all pass.

- [ ] **Step 2: Frontend — lead section tests + type-check + lint**

Run: `cd frontend && npx vitest run src/components/admin/leads && npx tsc --noEmit && npx eslint src/components/admin/leads src/lib/languages.ts`
Expected: all tests pass, no type errors, no lint errors.

- [ ] **Step 3: Manual smoke (dev servers)**

Start backend (`cd backend && source venv/Scripts/activate && uvicorn auth_service.main:app --reload --port 8001`) and frontend (`cd frontend && npm run dev`). In the admin leads dashboard, open a lead drawer and confirm:
- Languages section shows existing values (or "No languages").
- Edit → search "rom" → Romanian appears → click adds a chip.
- Add a second language; remove one via ×; save with 0 languages; save with multiple.
- Reopen the lead → persisted values match (round-trips through the backend).

- [ ] **Step 4: Final commit (if any verification fixes were made)**

```bash
git add -A
git commit -m "test(leads): verify languages field end-to-end"
```

---

## Self-Review

- **Spec coverage:** Dedicated `text[]` column (Task 1) ✓; `LeadOut`/`LeadUpdate` + validation (Task 2) ✓; ISO 639-1 frontend list (Task 3) ✓; type wiring (Task 4) ✓; searchable add/remove multi-select widget (Task 5) ✓; drawer-only `LanguagesSection` with read/edit/empty-state, 0-to-many, full-replacement save (Task 6) ✓; ui-ux-pro-max polish (Task 7) ✓; backend + frontend tests (Tasks 2, 6, 8) ✓. **Deviation:** backend validation is structural rather than a full name allow-list — flagged at the top for confirmation; out-of-scope items (table/kanban/filter/i18n wiring) intentionally excluded.
- **Placeholders:** none — every code step carries full content.
- **Type consistency:** `Lead.languages: string[]`, `LeadUpdatePayload.languages?: string[]`, `LeadOut.languages: list[str]`, `LeadUpdate.languages: list[str] | None`; widget contract `{ value: string[]; onChange: (next: string[]) => void }` used identically in Tasks 5 and 6; `searchLanguages(query, selected, limit)` defined in Task 3 and consumed in Task 5; `EditableSectionShell` props match Task usage (`canSave` boolean, `id="languages"`).
