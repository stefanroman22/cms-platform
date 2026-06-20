# Marketing Site Multilingual Language Switcher — Design

**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan
**Scope:** Public marketing frontend only (`frontend/src/app/(marketing)`). **Dashboard and booking widget are explicitly out of scope and physically untouched.**

## 1. Goal

Let visitors of the public marketing site (roman-technologies.dev) read it in **English, Dutch, or Romanian** and switch freely. The site should default to the visitor's language based on the country they connect from (via Vercel geo), falling back to English. The switcher must be present, on-brand, and responsive on **every screen size**, reachable from the **desktop nav, the mobile drawer, and the footer**.

## 2. Decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Translation scope | **Whole marketing site** — every marketing page localizes; no half-English pages |
| URL model | **Locale-prefixed, `as-needed`** — `/` `/about` (en, unprefixed), `/nl/...`, `/ro/...` |
| Switcher placements | **Desktop nav dropdown + mobile drawer + footer** (not a floating control) |
| Translation production | **DeepL auto-translate → human review** before commit |
| Library | **`next-intl`** (org standard; powers `i18n-setup` skill + client sites) |
| Dashboard/widget | **Untouched** — no file behavior change, no locale prefix |

## 3. Non-goals

- No changes to `/dashboard/*` or `(widget)/*` behavior or URLs.
- No change to the booking widget's internal `tw()` dictionary i18n.
- No backend changes. DeepL is invoked from a **local dev script**, never at Vercel build/runtime.
- No new locales beyond `en`, `nl`, `ro`.

## 4. Architecture

### 4.1 Locale routing

Install `next-intl` (v4, Next 16 compatible — verify exact version at implementation). Configure:

```
locales:       ["en", "nl", "ro"]
defaultLocale: "en"
localePrefix:  "as-needed"   // en is clean, nl/ro are prefixed
```

`frontend/src/i18n/routing.ts` — `defineRouting(...)` + typed `Link`, `redirect`, `usePathname`, `useRouter` re-exports (next-intl navigation APIs).
`frontend/src/i18n/request.ts` — `getRequestConfig` that resolves the active locale and loads `messages/{locale}.json`.

### 4.2 File moves (marketing only)

Marketing pages move under a new `app/[locale]/` segment. **Only the `(marketing)` route group moves**; everything else stays put.

```
app/
  layout.tsx                 # root <html lang="en"> + theme boot script + fonts (unchanged shell)
  [locale]/
    layout.tsx               # NEW: validates locale, setRequestLocale, generateStaticParams, NextIntlClientProvider
    (marketing)/
      layout.tsx             # MOVED: Header / Footer / MarketingProviders (unchanged internals)
      providers.tsx          # MOVED
      page.tsx               # MOVED: home
      about/ clients/ team/ contact/ log-in/ manage/[token]/   # MOVED
  dashboard/                 # UNTOUCHED
  (widget)/                  # UNTOUCHED
  globals.css                # UNTOUCHED
```

- `@/`-aliased imports mean moved pages need **no import edits**.
- `app/[locale]/layout.tsx` calls `setRequestLocale(locale)` so marketing pages stay **statically rendered**; it `notFound()`s on an unknown locale and provides `generateStaticParams` for the three locales.
- Static route segments (`dashboard`) and route groups (`(widget)`) take routing precedence over `[locale]`, so `/dashboard` and `/w/[slug]` never resolve through the locale segment. The i18n middleware matcher also excludes them (belt and suspenders).

### 4.3 `<html lang>` strategy

The single root `app/layout.tsx` renders a **static `<html lang="en">`** (preserves static rendering + zero dashboard risk). On localized pages, correctness is delivered by:
- **`hreflang` alternates** in metadata (next-intl `alternates`) — the primary SEO language signal.
- A small client effect in `MarketingProviders` that syncs `document.documentElement.lang` to the active locale for screen readers.

*Alternative considered and rejected for now:* multiple root layouts via route groups give a perfectly static per-locale `lang`, but require relocating dashboard + widget folders. Not worth the extra surface against the "don't touch the dashboard" constraint. Documented here in case it's wanted later.

### 4.4 Middleware composition (geo default + persistence + existing auth)

`frontend/src/middleware.ts` gains an i18n layer composed with the current logic. Order:

1. **Legacy-host redirect** — unchanged, runs first.
2. **Geo default (first visit only):** if there is **no `NEXT_LOCALE` cookie** and the path is unprefixed, read `request.headers.get("x-vercel-ip-country")`:
   - `NL → nl`, `RO → ro`, anything else / missing → `en` (true fallback).
   - If the resolved locale ≠ `en`, redirect once to the prefixed equivalent of the current path and set the `NEXT_LOCALE` cookie. If `en`, set the cookie and continue.
   - This runs **only while the user hasn't expressed a choice.** A `NEXT_LOCALE` cookie or an explicit prefixed URL always wins — no repeated redirects, shared `/nl/...` links stay Dutch.
3. **next-intl middleware** — handles prefix normalization, cookie read, and locale negotiation for marketing paths.
4. **Auth gating** — existing `/dashboard` protection + `/log-in` redirect, made locale-aware with a `stripLocale(pathname)` helper (so `/nl/log-in` still gates). Legacy/auth behavior otherwise identical.

Matcher: continues to match all non-static paths; **excludes** `/dashboard`, `/api`, `/w` (widget), and static assets from i18n rewriting. Localhost/dev has no geo header → English.

## 5. Translation pipeline

### 5.1 Message catalogs

- `frontend/messages/en.json` — **source of truth**, hand-authored by extracting all current marketing copy.
- `frontend/messages/nl.json`, `frontend/messages/ro.json` — DeepL-generated, human-reviewed, committed.
- Namespacing by surface: `nav`, `header`, `footer`, `hero`, `laptop`, `contact`, `work`, `pricing`, `about`, `team`, `clients`, `login`, `manage`, `common`.

### 5.2 Content vs. copy split

Structured, locale-independent data stays in content files; only human-readable text moves to messages:
- **Stays in content** (`src/content/*`): team member `name`, `image`, `email`, `linkedin`; project `image`/links; any URL or proper noun.
- **Moves to messages**: team member `role` + `description` (keyed by a stable member id), project titles/descriptions, all section headings/leads/CTAs, nav labels, footer text, login labels.

### 5.3 DeepL script

`frontend/scripts/translate-i18n.mjs` (run locally by Stefan; **not** in CI/build):
- Reads `messages/en.json`; for each target locale, translates **only new/changed keys** (incremental, via a committed source-hash snapshot `messages/.translation-cache.json`) so prior **human edits are preserved**.
- **Placeholder protection:** ICU placeholders (`{name}`, `{count}`) are swapped to inert XML tags before sending and restored after (`tag_handling=xml`, ignored), so DeepL never mangles them.
- **Glossary / do-not-translate:** "Roman Technologies" (and any other brand proper nouns) are protected so they stay verbatim across locales.
- Auth: `DEEPL_API_KEY` from env. **Verify the key exists / is the Free or Pro endpoint at implementation start** (backend already integrates DeepL; reuse the same key). Script fails loudly with a clear message if the key is missing.
- Output is written, **Stefan reviews**, then commits.

## 6. The language switcher (UI/UX + brand)

Brand context: dark (`zinc-950`/`black`), gold accent `text-accent` (#C9A961), Geist + display font, glass-blur header, `motion/react` motion vocabulary, cursor-pointer on buttons (global rule).

Single shared `LanguageSwitcher` component, three presentational variants:

- **Desktop nav (`variant="nav"`):** ghost button = `Globe` icon + active code ("EN") + chevron, in the header right cluster. Click → `motion` popover (fade + scale from top-right) listing the three by **native name** (`English · Nederlands · Română`), active in gold with a check. Closes on Esc / outside-click / route change. Full ARIA (`aria-haspopup`, `aria-expanded`, roving focus), visible focus ring.
- **Mobile drawer (`variant="drawer"`):** a labeled **"Language"** section inside the existing hamburger drawer — three segmented pills, active in gold. Reachable on every small screen.
- **Footer (`variant="footer"`):** a globe control with an **upward** popover (the "settings"-style home), styled to footer tone.

**Smooth switch:** selecting a language calls next-intl's router to swap the locale on the **current** path inside `startTransition`, preserving scroll; the existing branded `RouteLoader` covers the transition. The choice persists via the `NEXT_LOCALE` cookie (next-intl writes it).

Final visual polish (exact spacing, popover motion curve, flag-vs-code treatment) is refined during implementation using the frontend-design / ui-ux-pro-max / impeccable skills, within these brand tokens.

## 7. SEO

- `hreflang` alternates for all three locales + `x-default` via next-intl metadata `alternates`, on every localized page.
- Per-locale `<title>`/`<description>` sourced from messages.
- Sitemap (if present) extended to emit per-locale URLs; otherwise noted as a follow-up.

## 8. Testing & verification

- **Vitest unit:** `country → locale` mapping (incl. unknown/missing → en); `stripLocale()`; `LanguageSwitcher` render, active-state, keyboard nav, close-on-route-change.
- **Playwright user-stories** (mobile + laptop + desktop viewports):
  - Switch EN→NL→RO from nav, drawer, and footer; assert URL prefix **and** visible copy change.
  - Geo default: mocked `x-vercel-ip-country` (NL, RO, US) → correct landing locale; no cookie → geo applies, cookie present → geo ignored.
  - Persistence across navigation; shared `/nl/...` link renders Dutch directly.
  - Dashboard + widget render unaffected (English, no prefix).
- **Gates:** `npm run build`, `npm run typecheck`, full existing vitest suite stay green.

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Middleware regression (auth/legacy host) | `stripLocale()` keeps checks correct; auth tests + Playwright assert `/dashboard` + `/nl/log-in`; legacy-host redirect stays first and unchanged |
| `[locale]` colliding with `/dashboard` or `/w` | Static-segment precedence + explicit matcher exclusions; Playwright asserts both |
| DeepL mangles placeholders / brand | XML tag-protection for ICU vars + glossary for proper nouns; review step |
| Marketing pages deopt to dynamic | `setRequestLocale` in `[locale]` layout + pages keeps them static; root layout stays static |
| DeepL key missing/wrong tier | Verify at implementation start; script fails loudly; reuse backend's key |
| Large copy-extraction surface (regressions in wording) | Extract per-surface with the live components open; Playwright copy assertions per locale |

## 10. Dependencies / env to verify at implementation start

- `next-intl` version compatible with Next 16.2.5.
- `DEEPL_API_KEY` available locally (same key the backend uses) and which endpoint (Free vs Pro).
- `x-vercel-ip-country` populated in production middleware (Vercel default; confirm).

## 11. Out-of-scope follow-ups (noted, not built)

- Localizing the dashboard or booking widget.
- Per-locale OG images.
- Wiring marketing copy to the CMS per-locale (currently file-based).
