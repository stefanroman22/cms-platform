---
name: seo-pro
description: Implement production-grade SEO for a Vite + React 19 SSG site — React 19 head hoisting, lib/head.ts, prebuild sitemap/robots/OG (satori), JSON-LD structured data, and Core Web Vitals targets. Use when finalizing any page or when the build plan has SEO items pending. Triggers on phrases like "add SEO", "metadata", "sitemap", "structured data", "OG image".
---

# SEO Pro

## The SEO checklist for every page

1. **Title** — unique, 50–60 chars, includes primary keyword + brand.
2. **Description** — unique, 140–160 chars, action-oriented.
3. **Canonical URL** — `<link rel="canonical" href="...">` via `lib/head.ts`.
4. **OG image** — 1200×630, descriptive `alt`.
5. **Twitter card** — `summary_large_image`.
6. **JSON-LD** appropriate to the page type.
7. **Indexable** — no `<meta name="robots" content="noindex">` unless intentional.
8. **Internal links** — at least one link to/from other site pages.

## How head tags work in Vite + React 19 SSG

React 19 hoists `<title>`, `<meta>`, and `<link>` elements rendered anywhere inside a component
straight to `<head>`. `vite-react-ssg` bakes those hoisted tags into the pre-rendered HTML, so
crawlers see them in raw markup without JavaScript.

The pattern: call `buildHead(route, locale)` from `src/lib/head.ts` inside each page component
and render its return value as JSX tags. No `generateMetadata`, no separate viewport export.

```tsx
// src/pages/HomePage.tsx
import { buildHead } from "@/lib/head";

export default function HomePage({ locale }: { locale: string }) {
  const head = buildHead("home", locale);
  return (
    <>
      <title>{head.title}</title>
      <meta name="description" content={head.description} />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <link rel="canonical" href={head.canonical} />
      {head.hreflang.map(({ locale: l, href }) => (
        <link key={l} rel="alternate" hrefLang={l} href={href} />
      ))}
      <meta property="og:title" content={head.title} />
      <meta property="og:description" content={head.description} />
      <meta property="og:url" content={head.canonical} />
      <meta property="og:locale" content={locale.replace("-", "_")} />{/* og:locale must be underscore-separated BCP-47 (e.g. en_US, nl_NL) — map from locale code via locale.replace("-", "_") or a locale→og_locale map */}
      <meta property="og:image" content={head.ogImage} />
      <meta name="twitter:card" content="summary_large_image" />
      {/* JSON-LD injected here too — see below */}
      {/* page content */}
    </>
  );
}
```

## `src/lib/head.ts` — per-route × locale head builder

`buildHead(route, locale)` returns the full tag set for a given route and locale. It is called at
pre-render time (inside the page component rendered by `vite-react-ssg`) so the tags are baked
into raw HTML.

```ts
// src/lib/head.ts
import { SITE_URL, SUPPORTED_LOCALES } from "@/lib/config";
import { getStoredMeta } from "@/lib/seo-meta";

export interface HeadData {
  title: string;
  description: string;
  canonical: string;
  ogImage: string;
  hreflang: { locale: string; href: string }[];
}

export function buildHead(route: string, locale: string): HeadData {
  const stored = getStoredMeta(route, locale); // build-time fetch result (never throws)
  const path = route === "home" ? "" : `/${route}`;
  return {
    title: stored?.title ?? `<Business> — ${route}`,
    description: stored?.description ?? "",
    canonical: `${SITE_URL}/${locale}${path}`,
    ogImage: `${SITE_URL}/og/${locale}/${route}.png`,
    // Coded tags are generated LOCALLY — not fetched
    hreflang: SUPPORTED_LOCALES.map((l) => ({
      locale: l,
      href: `${SITE_URL}/${l}${path}`,
    })),
  };
}
```

Key rules:
- `SITE_URL` is a constant in `src/lib/config.ts` — ask for the real domain; **never leave
  `https://example.com`**.
- `canonical`, `hreflang`, `og:locale`, and JSON-LD `inLanguage` are **generated locally per
  locale** in `lib/head.ts`, not fetched from the backend.
- The viewport is a plain `<meta name="viewport">` — no framework export, no special API.

## `src/lib/seo-meta.ts` — build-time stored-meta fetch

Fetches `GET {backend}/projects/{slug}/seo/public/meta?route=<route>&locale=<locale>` at **build
time only** (no ISR, no request-time fetch for crawlers). The endpoint applies the
**per-field default-locale fallback** server-side, so the site never merges locales itself.

```ts
// src/lib/seo-meta.ts
const META_CACHE = new Map<string, StoredMeta | null>();

export function getStoredMeta(route: string, locale: string): StoredMeta | null {
  const key = `${route}:${locale}`;
  if (META_CACHE.has(key)) return META_CACHE.get(key)!;
  // Populated by preFetchAllMeta() called once at build entry
  return null;
}

// Call preFetchAllMeta once at build entry — it MUST run INSIDE the SSG build process
// (call it from the vite-react-ssg entry/setup in `src/main.tsx` so `lib/head.ts` reads
// the same in-process cache during pre-render). Running it from a separate `tsx` prebuild
// process would populate an isolated in-process Map that the SSG renderer never sees (empty
// cache → all getStoredMeta() calls return null). Alternative: persist the prefetched meta
// to a JSON file that `lib/seo-meta.ts` imports at build time instead of using the Map.
export async function preFetchAllMeta(slug: string, locales: string[], routes: string[]) {
  await Promise.all(
    locales.flatMap((locale) =>
      routes.map(async (route) => {
        try {
          const res = await fetch(
            `${process.env.VITE_CMS_ENDPOINT}/projects/${slug}/seo/public/meta?route=${route}&locale=${locale}`
          );
          if (!res.ok) return;
          META_CACHE.set(`${route}:${locale}`, await res.json());
        } catch {
          // never throw — fall back to build-time output
        }
      })
    )
  );
}
```

## `src/seo/sitemap.gen.ts` — prebuild → `public/sitemap.xml`

Runs as part of the `prebuild` npm script (`tsx src/seo/sitemap.gen.ts`). Writes
`public/sitemap.xml` containing every locale × page combination with `<xhtml:link>` hreflang
alternates.

```ts
// src/seo/sitemap.gen.ts
import { writeFileSync } from "node:fs";
import { SITE_URL, SUPPORTED_LOCALES } from "../lib/config";

const pages = [
  { path: "", priority: "1.0", changefreq: "monthly" },
  { path: "/about", priority: "0.7", changefreq: "monthly" },
  { path: "/contact", priority: "0.6", changefreq: "monthly" },
];

const urls = SUPPORTED_LOCALES.flatMap((locale) =>
  pages.map(({ path, priority, changefreq }) => {
    const loc = `${SITE_URL}/${locale}${path}`;
    const alternates = SUPPORTED_LOCALES.map(
      (l) => `    <xhtml:link rel="alternate" hreflang="${l}" href="${SITE_URL}/${l}${path}"/>`
    ).join("\n");
    return `  <url>\n    <loc>${loc}</loc>\n    <changefreq>${changefreq}</changefreq>\n    <priority>${priority}</priority>\n${alternates}\n  </url>`;
  })
);

const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n${urls.join("\n")}\n</urlset>`;
writeFileSync("public/sitemap.xml", xml);
console.log("sitemap.xml written");
```

For dynamic routes (blog, products), fetch the slugs inside the same script and append entries.

## `src/seo/robots.gen.ts` — prebuild → `public/robots.txt`

```ts
// src/seo/robots.gen.ts
import { writeFileSync } from "node:fs";
import { SITE_URL } from "../lib/config";

writeFileSync(
  "public/robots.txt",
  `User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: ${SITE_URL}/sitemap.xml\n`
);
console.log("robots.txt written");
```

## `src/seo/og.gen.ts` — prebuild → `public/og/*.png` (satori + sharp)

OG images are generated at build time (1200×630) by `satori` + `@resvg/resvg-js`/`sharp`. No
`next/og` `ImageResponse`. Per-locale variants are generated when locales differ significantly.

```ts
// src/seo/og.gen.ts
import satori from "satori";
import sharp from "sharp";
import { readFileSync, mkdirSync } from "node:fs";
import { SITE_URL, SUPPORTED_LOCALES } from "../lib/config";

const pages = ["home", "about", "contact"];

// Load font for satori — if a custom font breaks satori, fall back to Playwright screenshot:
// const browser = await chromium.launch(); const page = await browser.newPage();
// await page.goto(`${SITE_URL}/og-template/${route}?locale=${locale}`);
// await page.screenshot({ path: `public/og/${locale}/${route}.png`, clip: { x:0,y:0,width:1200,height:630 } });
let fontData: Buffer | undefined;
try {
  fontData = readFileSync("node_modules/@fontsource/inter/files/inter-latin-400-normal.woff");
} catch {
  console.warn("Font not found for satori; use Playwright screenshot fallback if OG images fail.");
}

async function generateOg(route: string, locale: string, title: string) {
  mkdirSync(`public/og/${locale}`, { recursive: true });
  const svg = await satori(
    {
      type: "div",
      props: {
        style: {
          width: 1200, height: 630,
          display: "flex", flexDirection: "column",
          alignItems: "flex-start", justifyContent: "flex-end",
          padding: "80px",
          background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
          color: "#ffffff",
        },
        children: [
          { type: "div", props: { style: { fontSize: 88, fontWeight: 700 }, children: title } },
          { type: "div", props: { style: { fontSize: 36, opacity: 0.7, marginTop: 24 }, children: "<Business tagline>" } },
        ],
      },
    },
    { width: 1200, height: 630, fonts: fontData ? [{ name: "Inter", data: fontData, weight: 400, style: "normal" }] : [] }
  );
  await sharp(Buffer.from(svg)).png().toFile(`public/og/${locale}/${route}.png`);
}

(async () => {
  for (const locale of SUPPORTED_LOCALES) {
    for (const route of pages) {
      await generateOg(route, locale, `<Business> — ${route}`);
    }
  }
  console.log("OG images written");
})();
```

**Playwright-screenshot fallback:** If a font breaks satori (e.g. a variable or non-Latin font),
replace the `satori` call with a Playwright headless screenshot of a pre-rendered OG-template
route, cropped to 1200×630. This is the standard escape hatch — do not fight satori font issues.

## JSON-LD structured data

Create `src/lib/seo/jsonld.tsx`:

```tsx
export function JsonLd<T extends object>({ data }: { data: T }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
```

Use it inside page components (the JSON-LD `<script>` is rendered inside the SSG page component;
`vite-react-ssg` serializes the rendered tree to static HTML so the `<script>` appears in the raw
markup — in-tree, not necessarily in `<head>` — which is fine: structured-data validators and
Google read it from raw HTML and do not require JSON-LD in `<head>`):

```tsx
import { JsonLd } from "@/lib/seo/jsonld";
import { SITE_URL } from "@/lib/config";

export default function HomePage({ locale }: { locale: string }) {
  return (
    <>
      {/* head tags from buildHead() */}
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Organization",
          name: "<Business>",
          url: SITE_URL,
          logo: `${SITE_URL}/logo.png`,
          inLanguage: locale,
          sameAs: [
            "https://twitter.com/...",
            "https://linkedin.com/company/...",
          ],
        }}
      />
      {/* page content */}
    </>
  );
}
```

## Schema.org types by page kind

| Page kind | Schema.org type |
|---|---|
| Home (general business) | `Organization` |
| Home (local business) | `LocalBusiness` (or specific subtype: `Restaurant`, `Store`, etc.) |
| About | `AboutPage` |
| Product | `Product` + nested `Offer` |
| Service | `Service` |
| Article / blog post | `Article` or `BlogPosting` |
| Contact | `ContactPage` + `Organization` reference |
| Pricing | `Service` with multiple `Offer`s, or `OfferCatalog` |
| FAQ section | `FAQPage` — use ONLY where the content is genuinely Q&A. (Google restricted FAQ rich results to authoritative/gov/health sites in 2023; do NOT promise a SERP or AI-Overview boost.) |
| Person bio | `Person` |

Validate every JSON-LD block at https://validator.schema.org/ before declaring done.

### GEO note (schema + stored SEO)

Treat schema as a Google rich-result + structured signal, **NOT** an AI-citation multiplier
(LLMs tokenize JSON-LD as text). When the CMS has stored SEO for a route
(`GET /projects/{slug}/seo/public/meta?route=&locale=`), `lib/seo-meta.ts` **prefers it**
(title / description / OG / JSON-LD), with a build-time fallback (never throw — fall back to
the build-time output on any error). Per-field default-locale fallback is applied by the
**endpoint**, so the site never merges locales itself. The **SEO/GEO Optimizer agent owns that
stored SEO** (it writes `seo_page_meta`); this skill is the build-time technical floor.

**Forbidden claims:** never assert the 11 research-refuted SEO/GEO claims (see
`agents/SEO-GEO Optimizer/prompts.py` `FORBIDDEN_CLAIMS`): no FAQ-3.2×, answer-first-67%,
llms.txt-as-signal, GBP-32%, NAP-74%, review-click-multipliers, etc.

## `SITE_URL` constant

`src/lib/config.ts` must export a `SITE_URL` constant set to the real production domain. **Ask
for the domain if unknown — never leave `https://example.com`.** The prebuild scripts and
`lib/head.ts` all import from this one location.

```ts
// src/lib/config.ts
export const SITE_URL = "https://<real-domain>";  // replace before final build
export const SUPPORTED_LOCALES = ["en", "nl"]; // extend per project
export const DEFAULT_LOCALE = "en";
```

## Verification before declaring SEO complete

1. `npm run build` (which runs `prebuild` first) — exits 0; no OG generation errors.
2. Open `public/sitemap.xml` — all locale × page combinations present with `<xhtml:link>` hreflang.
3. Open `public/robots.txt` — `Sitemap:` line points to the real `SITE_URL`.
4. View source on pre-rendered `dist/<locale>/index.html` — `<title>`, `<meta name="description">`,
   OG tags, hreflang `<link>` elements, and JSON-LD all present in raw HTML (no JS required).
5. Run Lighthouse SEO audit — target 95+.
6. Validate JSON-LD at https://validator.schema.org/.

## Common mistakes to catch

- Leaving `SITE_URL = "https://example.com"` — causes wrong canonical and sitemap URLs.
- Missing `<meta name="viewport">` — it is now a plain tag in the page component; easy to forget.
- Calling `buildHead` inside a `"use client"` component — run it in the SSG page component (no
  `"use client"` directive) so the tags land in the pre-rendered HTML.
- JSON-LD not appearing in raw HTML — same cause: rendered inside a client component. Move to the
  SSG page shell.
- Duplicate titles — use `title.template`-equivalent logic in `buildHead` (`"<page> — <Brand>"`).
- OG image path mismatch between `og.gen.ts` output and `buildHead` `ogImage` URL — keep them in sync.
- `noindex` left on accidentally from dev — `grep -r "noindex" src/` before final build.
- Canonical URL pointing to `localhost` or staging — verify `SITE_URL` before deploy.
- OG image > 8MB — `sharp` PNG output should be well under; check if you have unusually large
  raster sources embedded.
- `alt` missing on `<img>` — both SEO and a11y impact; all images must have `alt`.
