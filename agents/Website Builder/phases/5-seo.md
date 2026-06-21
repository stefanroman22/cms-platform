# Phase 5 — SEO

**Apply skill:** `seo-pro`.

**Do:**
- Per-page head via `lib/head.ts`: call `buildHead(route, locale)` inside each page component
  and render the returned tags as React 19 hoisted `<title>/<meta>/<link>` elements (React lifts
  them to `<head>`; `vite-react-ssg` bakes them into the pre-rendered HTML). Viewport is a plain
  `<meta name="viewport" content="width=device-width, initial-scale=1">` — no framework export,
  no special API.
- hreflang `<link rel="alternate">` for every locale on every page — generated locally per
  locale inside `lib/head.ts` (not fetched from the backend).
- `src/seo/sitemap.gen.ts` → `public/sitemap.xml` (every locale × page, with `<xhtml:link>`
  hreflang alternates); `src/seo/robots.gen.ts` → `public/robots.txt`. Both run as prebuild
  scripts (`tsx src/seo/sitemap.gen.ts && tsx src/seo/robots.gen.ts` in the `prebuild` npm
  script, before `vite-react-ssg build`).
- JSON-LD per page type (Organization/LocalBusiness on home; appropriate type elsewhere),
  honoring the locale's name/description. Validate at validator.schema.org.
- `src/seo/og.gen.ts` → `public/og/*.png` using `satori` + `sharp` (1200×630). Generate
  per-locale variants if locales differ significantly. Run as part of `prebuild`. If a font
  breaks satori, use the Playwright-screenshot fallback (headless screenshot of an OG-template
  route, cropped to 1200×630).
- Set real `SITE_URL` in `src/lib/config.ts` — ask for the domain if unknown; **never leave
  `https://example.com`**.
- Stored-meta: `lib/seo-meta.ts` fetches `GET {backend}/projects/{slug}/seo/public/meta?route=&locale=<locale>`
  at **build time** (no ISR, no request-time fetch). Prefers stored prose (title/description/OG),
  falls back to build-time output on any error, **never throws**. Coded tags (`canonical`,
  `hreflang`, `og:locale`, JSON-LD `inLanguage`) are generated **locally per locale** in
  `lib/head.ts` — not fetched.
- Pre-render every locale (raw-HTML content per locale): `vite-react-ssg` iterates every locale
  × route entry and emits a static HTML file with localized content + head tags in the raw
  markup. This is the SEO guarantee — crawlers see content without JavaScript.

**Gate:** `npm run build` exits 0 (prebuild scripts succeed first); `public/sitemap.xml` lists
all locale × page combinations with hreflang alternates; `public/robots.txt` has `Sitemap:` line
pointing to the real `SITE_URL`; view-source on `dist/<locale>/index.html` shows `<title>`,
`<meta name="description">`, OG tags, hreflang `<link>` elements, and JSON-LD in raw HTML;
JSON-LD validates at validator.schema.org.
