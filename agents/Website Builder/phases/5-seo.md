# Phase 5 — SEO

**Apply skill:** `seo-pro`.

**Do:**
- Root metadata in `app/[locale]/layout.tsx` via `generateMetadata` (locale-specific
  titles/descriptions). `viewport` exported SEPARATELY (Next 15+ breaking change).
- `alternates.languages` hreflang for every locale on every page.
- `app/sitemap.ts` (every locale × every page, with hreflang alternates), `app/robots.ts`.
- JSON-LD per page type (Organization/LocalBusiness on home; appropriate type elsewhere),
  honoring the current locale's name/description.
- `app/opengraph-image.tsx` (+ per-locale variants if locales differ significantly).
- Set real `metadataBase` (ask for the domain if unknown) — never leave `example.com`.

**Gate:** `npm run build` shows no metadata warnings; `/sitemap.xml` and `/robots.txt` render;
JSON-LD validates at validator.schema.org.
