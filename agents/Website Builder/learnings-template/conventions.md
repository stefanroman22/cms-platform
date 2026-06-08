# Project-specific conventions

Rules and patterns established for this project (or, when promoted, for all future builds). The agent reads this at the start of every phase and applies the rules.

## Format

```
## <category> — <rule name>

<the rule, stated as a directive — "Always X" / "Never Y" / "When A then B">

**Rationale:** <why>
**Established:** YYYY-MM-DD
**Source:** correction from user | self-observed failure | initial setup
```

## Active conventions

<!-- Append entries below this line. Group by category if it helps (Typography, Layout, Motion, SEO, A11y, Testing). -->

## Starter rules (apply to all builds)

### Imports — Motion library naming

Always import Motion from `motion/react`, never from `framer-motion`. The package was renamed in mid-2025.

**Rationale:** The legacy `framer-motion` package still works but receives no updates. The new `motion` package is actively maintained.
**Established:** initial setup
**Source:** initial setup

### Imports — i18n library

Always use `next-intl` for internationalization, never `next-i18next` or `react-i18next`.

**Rationale:** `next-intl` is the de facto i18n library for Next.js App Router with full RSC support. The others either don't work with App Router (`next-i18next`) or don't integrate with Next's routing system (`react-i18next`).
**Established:** initial setup
**Source:** initial setup

### Routing — locale prefix

Every page lives under `app/[locale]/`. Even single-locale projects use the locale prefix — it makes adding new locales later trivial.

**Rationale:** Avoids painful migrations later when the user decides to add another market.
**Established:** initial setup
**Source:** initial setup

### Translation — CMS-sourced, seed files as pre-connection fallback

Non-default locale `messages/<locale>.json` files are **build-time seeds / pre-connection fallbacks**. The default-locale file holds real copy; non-default seed files mirror it (same values — no `[XX]`/`[NL]` placeholders to hand-maintain).

Once the site is connected to the CMS (CMS Connector agent sets `NEXT_PUBLIC_CMS_ENDPOINT`), `i18n/request.ts` loads messages live from the CMS per locale. The CMS auto-translates the default locale into the others (DeepL when configured, else echoes the source). No separate translation pipeline is needed.

**Rationale:** Placeholders caused visible garbage text in QA and required a manual translation step. The CMS handles translation automatically post-connection; seeds keep the site functional before that point.
**Established:** 2026-06-06
**Source:** user instruction

### Metadata — viewport export separation

In `app/layout.tsx`, `themeColor`, `width`, and `initialScale` go in the `viewport` export, NOT in the `metadata` export.

**Rationale:** Breaking change since Next.js 15. Putting them in `metadata` produces a warning and is silently ignored.
**Established:** initial setup
**Source:** initial setup

### Images — never raw img tags

Use `next/image` for every image except inside `next/og` ImageResponse. Always include `alt`, `width`, `height` (or `fill` with sized parent), and `sizes` for non-priority images.

**Rationale:** Performance (CLS, LCP) and a11y.
**Established:** initial setup
**Source:** initial setup

### Output location

The agent generates new sites as siblings to "CMS - websites" at `C:\Users\stefa\.gemini\antigravity\scratch\<business-name>\`, never nested inside the CMS repo.

**Rationale:** Keeps each generated site independently versionable and deployable.
**Established:** initial setup
**Source:** user instruction
