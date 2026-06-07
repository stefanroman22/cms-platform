# CMS Multi-Language Support — Design

**Date:** 2026-06-05
**Status:** Approved (design), pending implementation plan
**Area:** `backend/auth_service/` (DB schema, content/workspace/publish routers, new `translation/` service) · `frontend/src/components/dashboard/` + `frontend/src/app/dashboard/` · `agents/CMS Connector - Website/` · `.claude/skills/i18n-setup/`

## Goal

Let a CMS-connected client website be published in **1, 2, 3, or more languages**. The client authors content **once** in a per-project **default language**; the CMS **automatically translates** it into the other languages; and the client can **manually override** any single translated string when the machine output isn't good enough — with that override **protected** from being silently overwritten later.

The platform's defining feature is preserved: **publishing stays a database flip** (no redeploy). A freshly translated, multilingual site goes live within the existing ~60s ISR window.

## Background: why this is net-new

The platform currently has two *separate, never-combined* content models (confirmed by a full scan of the connector agent, dashboard, backend/DB, the `i18n-setup` skill, and the Samir reference site):

| | **CMS-connected sites** (e.g. `it-global-services`) | **next-intl sites** (e.g. `samir-kapsalon`) |
|---|---|---|
| Content store | Supabase `content_entries` (`draft_content`/`published_content` JSONB) | `messages/<locale>.json` files in the repo |
| Delivery | Runtime fetch `GET /content/{slug}` (60s ISR) | Baked in at build time |
| Publish | DB flip, **no redeploy** | Git commit → Vercel rebuild |
| Multilingual? | **No — single-locale by construction** | **Yes — one file per locale** |
| Uses the CMS? | Yes | No |

So today a site can be CMS-driven *or* multilingual, never both. There is **zero locale dimension** anywhere in the CMS content model (DB, API, dashboard), and the connector agent actively **excludes** translatable chrome as "config, not content." The only language data in the system is sales metadata: `leads.languages text[]` (canonical English names like `"Romanian"`, `"Dutch"`, per `backend/migrations/2026_06_03_lead_languages.sql`).

The i18n library is **`next-intl`** (Samir uses `^4.12.0`; the `i18n-setup` skill and Website Builder agent standardize on it and forbid `react-i18next`/`next-i18next`). `next-intl` does **routing + message lookup + formatting + SEO**, but it does **not** translate — it expects pre-translated strings per locale. This design makes the **CMS the translation source** that feeds next-intl.

## Key decisions (settled during brainstorming)

1. **Delivery model — CMS DB + runtime fetch.** The CMS is the multilingual source of truth. Client sites keep next-intl for routing/SEO but their `i18n/request.ts` fetches the per-locale message bundle from the CMS at runtime. Publish = DB flip, no redeploy.
2. **Translation engine — DeepL Free API**, behind a **pluggable provider interface** (DeepL Free tier: 500k chars/month ≈ $0 at SMB scale; best-in-class for EU languages). Swappable for Claude or Google without touching callers.
3. **Trigger — on save *and* on publish.** On save, changed (non-overridden) default-locale fields are translated into every locale and written to **draft**, so the preview site is fully multilingual immediately. Publish flips all locales live. Only fields whose source actually changed are re-translated.
4. **Override policy — keep + flag.** A manual override is never silently overwritten. When its source changes it is marked **"needs review."**
5. **Content scope — both.** The CMS owns dynamic content **and** a curated set of UI chrome strings (nav/buttons/banners), served as one per-locale bundle. The connector agent starts capturing chrome (reversing its current exclusion).
6. **Rollout — all CMS-connected sites.** New sites are born multilingual; existing single-locale sites keep working as default-only until a locale is added.

## Architecture overview

```
        ┌─────────────────────── CMS dashboard (Next.js) ───────────────────────┐
        │  Locale switcher (?locale=)  →  per-locale editor (auto/manual/stale)  │
        └───────────────┬───────────────────────────────────────────────────────┘
                        │ PUT …/services/{key}?locale=…           (authenticated)
                        ▼
   ┌───────────────────────────── FastAPI backend ─────────────────────────────┐
   │  workspace.save_service ──► writes default draft, then for each other      │
   │                              locale: auto leaves re-translated,            │
   │                              manual leaves kept + flagged stale            │
   │                                   │                                        │
   │  translation/  (provider iface) ──┘   DeepLProvider (default)              │
   │                                                                            │
   │  publish.publish_project ──► copy draft→published per (service, locale)    │
   └───────────────┬────────────────────────────────────────────────────────────┘
                   │  Supabase: content_entries  (1 row per service × locale)
                   ▼
   GET /content/{slug}/{locale}        ◄── client next-intl i18n/request.ts (60s ISR)
   GET /content/{slug}/{locale}/draft  ◄── preview deployment (token-gated)
   GET /content/{slug}                  ◄── UNCHANGED: returns default locale (legacy)
                   │
                   ▼
            Live client site   /ro   /en   /nl   (next-intl routing + hreflang)
```

## Data model

### Schema changes (Supabase, `public` schema)

```sql
-- projects: per-project locale configuration
ALTER TABLE projects
  ADD COLUMN default_locale text NOT NULL DEFAULT 'en',
  ADD COLUMN locales        text[] NOT NULL DEFAULT '{}';   -- default locale listed first
-- backfill: see Migration section (per-project correct default + locales = [default])

-- content_entries: one row per (service × locale)
ALTER TABLE content_entries
  ADD COLUMN locale           text,                    -- backfilled to project default, then NOT NULL
  ADD COLUMN translation_meta jsonb NOT NULL DEFAULT '{}';

-- replace the one-to-one uniqueness with per-locale uniqueness
ALTER TABLE content_entries DROP CONSTRAINT content_entries_project_service_id_key;
ALTER TABLE content_entries
  ADD CONSTRAINT content_entries_service_locale_key UNIQUE (project_service_id, locale);

-- keep the "needs publish" partial-index behavior, now per-locale row
-- (recreate idx_content_entries_needs_publish over the new shape)
```

**Each locale's `draft_content`/`published_content` keeps the *exact same shape* it has today** — the per-type payload (`{title, body}`, `{url, alt}`, `{entries}`, `{_schema, items}`, etc.). Only the values differ per locale. This keeps the public read path almost unchanged (filter by locale).

**`translation_meta` tracks only manual overrides:**

```jsonc
{
  "body":               { "src_hash": "a1b2c3…" },   // this leaf was manually edited
  "items.<itemId>.short_description": { "src_hash": "d4e5f6…" }
}
```

- A leaf **not** in `translation_meta` → **auto** (machine-managed; refreshed on every relevant save).
- A leaf **in** `translation_meta` → **manual** (protected; never auto-translated).
- A manual leaf is **stale / "needs review"** when its stored `src_hash` ≠ the hash of the *current* default-locale source string for that leaf path.

The **default-locale row is the source of truth** for structure and source text; its `translation_meta` is always `{}`.

### Translatable-segment model

A pure function `segments_of(service_type, content)` flattens a service's content into a flat map of **leaf paths → strings**, used by both translation and override tracking. Translatability is driven by field type:

| Service type | Translatable leaf paths | Non-translatable (copied verbatim) |
|---|---|---|
| `text_block` | `title`, `body` | — |
| `image` / `floor_plan` | `alt` | `url` |
| `gallery` | — | `items[]` (URLs) |
| `video` | — | `url`, `poster` |
| `file_download` | `filename` | `url` |
| `key_value` | each `entries.<key>` value | the keys themselves |
| `repeater` | per item, each field whose `_schema` `type` ∈ {`string`,`richtext`,`tags`} → `items.<itemId>.<field>` | fields of type `url`; numbers |
| `email_config` | — (private; never public) | `destination_email` |

**Repeater item identity (refinement):** repeater items gain a stable `_id` (generated on create), so leaf paths survive reorder/add/delete. Leaf paths use `items.<_id>.<field>`, **not** array index. This touches `RepeaterEditor.tsx` (assign `_id` to new items) and the provisioning seed.

`richtext`/`body` is Markdown and `metadata.footer.rights`-style strings carry ICU placeholders (`{year}`) — both are preserved (see Translation engine).

## Translation engine

A new backend package `backend/auth_service/translation/`:

```python
class TranslationProvider(Protocol):
    def translate(self, texts: list[str], *, source: str, target: str,
                  fmt: Literal["text", "markdown", "html"]) -> list[str]: ...

# Implementations:
#   DeepLProvider  (default)   — DeepL Free API; tag_handling for markup
#   ClaudeProvider (premium)   — Anthropic API; best brand-voice/placeholder fidelity
#   NullProvider   (manual)    — echoes source; for "manual only" projects
# Selected via env TRANSLATION_PROVIDER (default "deepl"); DEEPL_API_KEY in backend env.
```

- **Placeholder & markup safety.** Before sending, ICU tokens (`{var}`, `{count, plural, …}`) are masked to inert sentinels (and Markdown/HTML protected via DeepL `tag_handling`), then restored after — so interpolation and formatting never break. A unit-tested `protect()`/`restore()` pair guards this.
- **Batching.** All changed leaves for one target locale go in a single provider call (DeepL accepts arrays).
- **Cost control (no new table).** Re-translation is skipped by comparing each leaf's current default-locale `src_hash` against what produced the existing translation: a leaf is re-translated only when its source actually changed (and it isn't manual). This "only changed leaves re-translate" rule lives in the save flow and needs no separate cache table. (A `translation_cache` table keyed by `src_hash+source+target+provider` is a possible future optimization for cross-project string reuse, explicitly out of scope now.)
- **Locale codes.** Providers receive ISO-639-1 (`ro`, `nl`, `en`); a `language_name → iso` map converts `leads.languages` ("Romanian") at provisioning. Lives next to / mirrors `frontend/src/lib/languages.ts`.

## Save & publish flow

### Save — `PUT /projects/{slug}/services/{key}?locale={locale}` (`workspace.save_service`)

- **Editing the default locale (authoring):**
  1. Write the default-locale `draft_content`.
  2. Compute changed translatable leaves vs the previous default draft.
  3. For each other project locale, for each changed leaf:
     - if the leaf is **auto** → translate and write into that locale's draft;
     - if the leaf is **manual** → leave its value, mark **stale** (its `src_hash` now mismatches).
  4. Persist updated draft rows. Untouched leaves and unaffected locales are not rewritten.
- **Editing a non-default locale (override):**
  1. Write that locale's leaf value into its `draft_content`.
  2. Record the leaf in that row's `translation_meta` with `src_hash = hash(current default source)` → status becomes **manual**, **stale** cleared.

`ContentSaveRequest` gains an optional `locale` (defaults to project default). The `?locale=` query param drives it. `_flatten_service` / `GET …/services/{key}` gain a `locale` param (default-locale fallback when a locale row is missing).

### Publish — `POST /projects/{slug}/publish` (`publish.publish_project`)

For every `content_entries` row (all services × all locales) where `draft_content != published_content`, copy draft → published; bump `last_published_at`. Identical DB-flip semantics, iterated per locale. `project_status.unpublished_count` and the per-locale review counts aggregate across locales. **No redeploy.**

## Public read API + client-site wiring

### Endpoints (`backend/auth_service/routers/content.py`)

```
GET /content/{slug}/{locale}        → published_content for {locale}; fallback to default
GET /content/{slug}/{locale}/draft  → draft_content for {locale} (X-CMS-Preview-Token)
GET /content/{slug}/{locale}/types  → per-locale TS .d.ts (optional; shape is locale-invariant)
GET /content/{slug}                  → UNCHANGED — returns the default locale (legacy/back-compat)
```

Response envelope is the existing `{ project_slug, project_name, last_updated, content: { <service_key>: { _type, _label, …fields } } }`, now for the requested locale. `email_config` stays filtered; ETag/304 and `_normalise_published` behavior preserved. Missing-locale leaves fall back to the default locale so a half-translated site never renders blanks.

### Client site (next-intl)

The only client wire that changes is `i18n/request.ts`, which sources messages from the CMS instead of a local file:

```ts
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale;
  const res = await fetch(`${CMS_ENDPOINT}/${SLUG}/${locale}`, { next: { revalidate: 60 } });
  return { locale, messages: toMessages(await res.json()) };  // CMS content → next-intl namespace tree
});
```

`toMessages()` maps the service-keyed content map into a next-intl namespace tree (chrome services under a reserved `page_name`/namespace, e.g. `ui.*`). `routing.locales`/`routing.defaultLocale` stay the single source of truth for routing, and **must mirror** `projects.locales`/`default_locale` (the connector/Website-Builder keep them in sync). hreflang, sitemap, and the language switcher derive from `routing.locales` and are unaffected. Preview deployments point at `/{locale}/draft` with the preview token (Next.js sites use `NEXT_PUBLIC_CMS_ENDPOINT`/`NEXT_PUBLIC_CMS_PREVIEW_TOKEN`).

## Dashboard UX

Reuses the existing URL-param navigation pattern (`?view=` via `useProjectView`, `?tab=` via `ServiceGrid`) by adding a **third param `?locale=`**.

- **Locale switcher** in the CMS section header. Lists `projects.locales`; default locale badged. Default = authoring view; non-default = review/override view. Each locale shows a status chip (e.g. `EN · 2 need review`).
- **Per-locale editor view (non-default):** each translatable field renders its auto-translation with:
  - **⚡ Auto · DeepL** badge (machine-managed) + an **Override** action;
  - **✎ Manual** badge once edited (protected);
  - **⚠ Needs review** when a manual field's source changed, with one-click **Re-translate** (drop override) / **Keep mine** (re-anchor `src_hash` to the new source);
  - the **default-locale source string** shown beneath for reference.
- **Editor data flow:** `app/dashboard/[projectSlug]/[serviceKey]/page.tsx` fetches `GET …/services/{key}?locale=` and PUTs with `?locale=`. The 9 editors' `EditorProps` (`initialContent`/`onChange`) are unchanged — they edit a single locale's blob; status badges live in the editor *page* chrome around them, driven by `translation_meta`. Cache keys (`service:{slug}:{key}`, `services:{slug}`) gain a `:{locale}` suffix to avoid cross-locale bleed (`useQuery`/`lib/cache.ts`).
- **Settings → Languages panel** (`ProjectSettingsSection.tsx`): set the default locale and add/remove locales. Adding a locale kicks off a full translation pass (progress indicator); removing one deletes that locale's rows after a confirm.
- **Publish bar** (`PreviewPublishBar.tsx`): `unpublished_count` now spans locales; optional per-locale breakdown.

## Connector agent changes (`agents/CMS Connector - Website/`)

Reverse "exclude i18n" into **detect-and-import**:

- **Phase 2 scan (`prompts.py`, `phases/2-scan.md`):**
  - Detect `i18n/routing.ts` (`locales`, `defaultLocale`) → seed `projects.locales` / `default_locale`.
  - Detect existing `messages/<locale>.json` → seed per-locale `initial_content` (import existing translations, don't discard them).
  - Capture a **curated set of chrome strings** (nav labels, primary CTAs, cookie/consent) as CMS services under a reserved `page_name` (e.g. `UI`).
  - Manifest schema gains `default_locale`, `locales`, and per-locale `initial_content`.
- **Phase 4 integration (`scan.py._provision`, `_vercel_setup`, `output_writer.py`):** write per-locale `content_entries` rows; set project locale config; rewrite the client `i18n/request.ts` to fetch from the CMS; `cms.config.json` gains `locales`/`defaultLocale`.
- **`LEARNINGS.md`:** the append-only rule treating locale strings as config is **superseded** with a dated note (file is append-only; add, don't delete).

## i18n-setup skill / Website Builder changes

- `.claude/skills/i18n-setup/SKILL.md`: `i18n/request.ts` now loads messages from the CMS endpoint; the `[XX]`/"never auto-translate" placeholder convention is **retired** — the CMS is the translation pipeline. `routing.ts` locales must equal the project's CMS locales.
- `agents/Website Builder/` (`AGENTS.md`, `phases/3-scaffold.md`, `learnings-template/conventions.md`, `GOAL_TEMPLATE.md`, `phases/5-seo.md`): new builds wire CMS-sourced messages and chrome-through-CMS; SEO/hreflang derivation from `routing.locales` is unchanged.

## Back-compat & migration

- **Backfill:** set each project's `default_locale` (admin-known; e.g. `it-global-services` → `ro`, since its live content is Romanian) and `locales = [default_locale]`; set `content_entries.locale = <project default_locale>` for every existing row, then make `locale NOT NULL`.
- **One-to-one embed → locale-filtered:** the PostgREST embed in `content.py` / `workspace.py._flatten_service` (`_resolve_content_entry`) changes from a single embedded dict to a locale-filtered select with **fallback to the default locale**.
- `GET /content/{slug}` keeps returning the default locale → **every existing site keeps working untouched**, no client change required until a locale is added.
- **Single → multi dependency (honest):** taking an *existing single-locale* site to multi-locale requires that client site to adopt next-intl `[locale]` routing + the CMS-fetching `i18n/request.ts`. The backend/CMS side is ready the instant the migration runs; the client wiring is a one-time pass the connector (or a small follow-up) applies. Sites already on next-intl (future builds) need no code change to add a locale.

## Security considerations

- The DeepL key lives in backend env only (never shipped to the client); translation calls are server-side in `workspace`/`publish`.
- Per-locale draft remains gated by the existing `X-CMS-Preview-Token` (`hmac.compare_digest`); the public per-locale endpoint exposes only published content and still filters `email_config`.
- Adding `?locale=` does not widen authz — locale is a filter within an already-authorized project scope. Validate `locale ∈ projects.locales` (reject unknown locales) to avoid unbounded row creation.
- Pre-existing finding (out of scope, noted): `public.slack_processed_events` has RLS disabled — unrelated to this work.

## Testing

- **Translation core (unit):** `segments_of` per service type (incl. repeater `_id` paths, key_value, non-translatable URL/number leaves); `protect()/restore()` round-trips ICU `{year}` and Markdown; `DeepLProvider` against a mocked API; `NullProvider` echo.
- **Save flow (integration):** editing default re-translates only changed auto leaves; manual leaf kept + marked stale on source change; editing a non-default locale sets manual + `src_hash`.
- **Publish (integration):** per-(service, locale) draft→published flip; `unpublished_count` spans locales; no redeploy side effects.
- **Public API:** `GET /content/{slug}/{locale}` returns the right locale; missing-locale leaf falls back to default; legacy `GET /content/{slug}` unchanged (regression); ETag/304 per locale.
- **Dashboard:** locale switcher drives `?locale=`; auto/manual/needs-review badges render from `translation_meta`; cache keyed per locale (no cross-locale bleed); Settings add/remove locale.
- **Migration:** existing rows backfilled to default locale; existing sites' content unchanged.
- **Client (E2E, generated site):** `/ro` and `/en` render translated content; switcher preserves path; hreflang present; publish reflects live within ISR.

## Rollout phases (suggested order for the implementation plan)

1. **DB + segment core** — migration, `segments_of`, `translation/` provider interface + `NullProvider` (no external dep yet), per-locale read endpoint with default fallback. Existing sites keep working.
2. **DeepL + save/publish** — `DeepLProvider`, auto-translate-on-save, override/stale tracking, per-locale publish.
3. **Dashboard UX** — locale switcher, per-locale editor badges, Settings Languages panel, per-locale cache keys.
4. **Client wiring + i18n-setup skill** — CMS-sourced `i18n/request.ts`, `toMessages()`, updated skill/Website-Builder.
5. **Connector detect-and-import** — chrome capture, messages/routing detection, per-locale provisioning, LEARNINGS update.

## Out of scope

- **Localized URL slugs** (next-intl `pathnames` map). Sites use shared path segments with only the `/<locale>` prefix (Samir's pattern). Per-locale slugs are a future enhancement.
- **Translation memory / glossary UI.** A per-project glossary is supported by the provider interface but no dashboard UI ships now.
- **Migrating in-repo next-intl sites (e.g. Samir) into the CMS.** Separate effort; not part of this spec.
- **Vercel analytics, booking, solver agent, scraper** — untouched.

## File-level change summary

**Backend — new:**
- `backend/auth_service/translation/__init__.py`, `provider.py` (interface), `deepl.py`, `claude.py`, `null.py`, `segments.py` (segment model + protect/restore), `language_codes.py`.
- `backend/migrations/2026_06_<dd>_content_locale.sql`.
- Tests under `backend/auth_service/tests/`.

**Backend — modified:**
- `routers/content.py` — per-locale endpoints + default fallback; legacy endpoint unchanged.
- `routers/workspace.py` — `save_service` locale-aware + auto-translate hook; `_flatten_service` locale param; repeater seed assigns `_id`.
- `routers/publish.py` — per-(service, locale) flip; per-locale status counts.
- `models/schemas.py` — `ContentSaveRequest.locale`, project locale fields, per-locale status in `ProjectStatusOut`.

**Frontend — new:**
- `components/dashboard/LocaleSwitcher.tsx` (+ `hooks/useProjectLocale.ts`), translation-status badges, Languages panel (in `ProjectSettingsSection.tsx`).

**Frontend — modified:**
- `app/dashboard/[projectSlug]/[serviceKey]/page.tsx` — locale-scoped fetch/save + status chrome.
- `components/dashboard/CmsSection.tsx` / `ServiceGrid.tsx` / `PreviewPublishBar.tsx` — locale switcher, per-locale counts.
- `hooks/useQuery.ts` / `lib/cache.ts` — `:{locale}` cache-key suffix.
- `RepeaterEditor.tsx` — stable `_id` on new items.

**Agents / skills — modified:**
- `agents/CMS Connector - Website/` (`prompts.py`, `scan.py`, `output_writer.py`, `phases/2-scan.md`, `phases/4-integration.md`, `AGENTS.md`, `LEARNINGS.md`).
- `.claude/skills/i18n-setup/SKILL.md`; `agents/Website Builder/` (`AGENTS.md`, `phases/3-scaffold.md`, `phases/5-seo.md`, `learnings-template/conventions.md`, `GOAL_TEMPLATE.md`).

**Unchanged:** auth/session, booking, solver/issues, scraper, forms (except locale is irrelevant there), `email_config` privacy, ETag/preview-token mechanics.
