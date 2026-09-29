# CMS rich-text client kit

Renders CMS-stored `inline`/`rich` HTML on client sites and in the dashboard. See
[`docs/decisions/0010-rich-text-content.md`](../../docs/decisions/0010-rich-text-content.md)
for the full design (stored format, the formats taxonomy, per-project rollout gate).

## 1. What it is

- Zero runtime dependencies beyond React ≥18. Framework-agnostic: Next.js App Router (server
  and client components), Vite SPA, vite-react-ssg.
- **Never uses `dangerouslySetInnerHTML`, `DOMParser` or `innerHTML`.** `parse.ts` is a small
  hand-written tokenizer that recognises only the allow-listed tags (`strong em u s a br` plus
  `p ul ol li h2 h3 h4 blockquote hr`, and a handful of synonyms — `b`→`strong`, `i`→`em`, `div`→`p`,
  etc.) and turns them into a plain node tree (`{ type: 'text' | tag, children, href? }`) that React
  renders as real elements. Everything else — script/style/iframe/svg content, unknown tags, stray
  `<`/`>` — is dropped or kept as literal text. This is defence in depth: the backend already
  sanitises on save, but the kit never trusts stored HTML either.
- `normalize.ts` / `serialize.ts` are a TypeScript port of the backend's canonical transform, so the
  kit renders exactly the structure the backend would have stored — no `<p>` nested in `<p>`, no
  hydration mismatch, even for legacy or hand-crafted data. `legacy.ts` is a matching port of the
  legacy (pre-rich-text) Markdown-lite → HTML converter, applied only to `rich` values that contain
  no tags at all (§4.4 of the spec — this is the one case where a tag-free value is *not* already
  HTML). `inline` values are always parsed as an HTML fragment; they are never run through the
  legacy converter.
- Deterministic on server and client: `RichText` uses no hooks, so the exact same markup comes out
  of `renderToString` on the server and the first client render — no hydration warnings.

## 2. Install into a site

From the CMS repo, vendor the kit's `src/` into the site with the sync script:

```bash
node <cms-repo>/client-kit/rich-text/scripts/sync-rich-text-kit.mjs <site>/src/lib/cms-rich-text
```

This copies every kit source file into `<site>/src/lib/cms-rich-text/`, stamps each one with a
`// Vendored from CMS client-kit/rich-text vX.Y.Z — do not edit; re-sync instead.` header, and writes
a `VERSION` file. **Never hand-edit the vendored copy** — fix the kit source in this repo and re-run
the script. Running it again always overwrites the target in place.

Import the stylesheet once, globally:

- **Next.js (App Router):** in the root `app/layout.tsx`, alongside your other global CSS imports:
  ```ts
  import "@/lib/cms-rich-text/cms-rich.css";
  ```
- **Vite:** in `main.tsx`:
  ```ts
  import "./lib/cms-rich-text/cms-rich.css";
  ```

To upgrade a site to a newer kit version later, re-run the same sync command and commit the diff —
the `VERSION` file tells you (and CI's `--check` mode) whether a site is behind.

## 3. Field-usage rules

| Use | How |
|---|---|
| Display prose | `<RichText value={x} format="rich\|inline" />` |
| Meta tags, JSON-LD, `alt`/`aria-label`, React keys, search, `tel:`/`mailto:`, `Number()` | `plainText(x)` |
| Per-word animations | `splitRichWords` / `<RichWords>` |
| Inside a clickable card | `links={false}` |
| Internal links | `renderLink` with the site router |
| Headings inside cards | `headingOffset={1}` |

`<RichText>` props: `value`, `format` (`"inline" \| "rich"`, default `"rich"`), `as` (element/component,
default `div` for rich / `span` for inline), `className`, `id`, `headingOffset` (shifts `h2`–`h4` up by
N levels, clamped to `h1`–`h6` — use `1` for prose rendered inside a card so it doesn't outrank the page's
own `h1`/`h2`), `links` (`false` renders anchors as `<span class="cms-rich-link">` instead of `<a>` —
use this whenever the rich text sits inside an element that is itself a link or button, since nested
`<a>` is invalid HTML), `linkTarget` (`"auto" | "self" | "blank"`, default `"auto"` — external
`http(s)` links open in a new tab with `rel="noopener noreferrer"`; internal paths never do), and
`renderLink` (`({ href, external, children }) => ReactNode` — called for internal links, i.e. those
starting with `/` or `#`, that are not external; wire it to your router's `Link` component so CMS
prose links navigate client-side instead of doing a full page load). An empty/whitespace-only value
renders `null` (nothing), so an empty CMS field never leaves an empty wrapper element in the DOM.

There is **no `components` prop** — the kit renders fixed semantic HTML (`<strong>`, `<a>`, `<h2>`,
`<ul>`, …), themed entirely through the CSS variables in §5. If a site needs different markup for a
tag, style it with the variables or wrap `<RichText>` in your own container; don't reach for a
swappable-renderer API that doesn't exist.

## 4. next-intl sites

CMS values that get merged into `next-intl` messages must be read with `t.raw("key")`, not `t("key")`
— rich/inline values contain `<`/`>` characters that `t()`'s ICU message parser will throw on. Render
the raw string with `<RichText>`:

```tsx
const t = useTranslations("services");
<RichText value={t.raw("description")} format="rich" />
```

For metadata (page `<title>`, `<meta description>`, JSON-LD), strip tags first:

```ts
plainText(t.raw("description"));
```

Never call `t()` directly on an inline/rich value for any purpose, including inside `generateMetadata`
or JSON-LD builders — always go through `t.raw()` first.

## 5. Theme recipe

`cms-rich.css` sets no colours or fonts directly — every visual property is a CSS custom property with
a safe fallback (`inherit`/`currentColor`), so a site that defines nothing still renders correctly
using the surrounding text colour. A site opts into its own look by defining these variables:

| Variable | Controls | Fallback |
|---|---|---|
| `--cms-rich-strong` / `--cms-rich-strong-weight` | bold colour / weight | `inherit` / `700` |
| `--cms-rich-em` | italic colour | `inherit` |
| `--cms-rich-underline` | underline colour | `currentColor` |
| `--cms-rich-link` / `--cms-rich-link-hover` / `--cms-rich-link-decoration` | link colours, underline style | `currentColor` / `inherit` / `underline` |
| `--cms-rich-heading` / `--cms-rich-heading-font` / `--cms-rich-heading-weight` | heading colour, font, weight | `inherit` / `inherit` / `700` |
| `--cms-rich-marker` | bullet / number colour | `currentColor` |
| `--cms-rich-quote-border` / `--cms-rich-quote-text` | blockquote | `currentColor` / `inherit` |
| `--cms-rich-rule` | divider colour | `currentColor` (40% opacity) |
| `--cms-rich-gap` / `--cms-rich-list-indent` | block spacing, list indent | `0.75em` / `1.4em` |

Define the variables on `:root` (light), on your dark-theme selector, and on every inverted or
coloured surface (hero, footer, `.section-dark`, …) — because these are CSS custom properties, the
nearest surface always wins, so bold text can be the accent colour on a dark hero and the ordinary
ink colour in a light card, automatically:

```css
:root { --cms-rich-strong: var(--ink); --cms-rich-link: var(--brand); --cms-rich-marker: var(--brand); }
[data-theme="dark"] { --cms-rich-strong: #fff; --cms-rich-link: var(--accent-cyan); }
.hero, .section-dark { --cms-rich-strong: var(--accent-cyan); }
```

**Contrast rule:** only use an accent colour for a variable when it reaches WCAG AA (4.5:1 contrast)
against the surface it will appear on. If it doesn't, leave the variable text-coloured (inherit) and
let font-weight alone carry the emphasis — don't ship low-contrast accent bold/links.

The kit's own selectors (`.cms-rich <element>`) are unlayered at specificity `(0,1,1)`, which beats
Tailwind preflight in both v3 (unlayered, `(0,0,1)`) and v4 (`@layer base`) — so list bullets and
block margins survive without extra work. The kit puts **no rules on the wrapper element itself**, so
any `className` you pass to `<RichText>` always applies cleanly.

## 6. Formats

- **`plain`** — a bare string, no markup. Machine values: URLs, phone numbers, tags, IDs.
- **`inline`** — HTML fragment restricted to `strong em u s a br` (plus synonyms). Produced by the
  dashboard's inline editor for one-line/short fields (titles, labels, short descriptions).
- **`rich`** — inline tags plus block tags `p ul ol li h2 h3 h4 blockquote hr`. Produced by the
  dashboard's rich editor for multi-paragraph prose (body copy, long descriptions). A `rich` value
  with no tags at all is legacy plain text and is converted with the same Markdown-lite rules as the
  one-time server-side migration (`*bold*`, single/double newlines → paragraphs, `- ` lists).

The only attribute either format ever carries is `a[href]`, restricted to `http://`, `https://`,
`mailto:`, `tel:`, `#…`, and `/…` (not `//…`, not `/\…`) — invalid or dangerous hrefs are dropped
(the link renders as a `<span>`/plain wrapper instead), matching the backend's save-time sanitisation.

## 7. Known limits

- **`RichWords`/`splitRichWords` render one `<a>` per linked word**, not one `<a>` spanning the
  whole link — a multi-word link animated per-word will produce several adjacent anchors instead of
  one. There is no `links`/`renderLink` option on `splitRichWords` (unlike `RichText`). If the
  per-word animation needs to live inside something already clickable, wrap it in a card/link
  yourself and render plain `<RichText links={false}>` for any prose inside that card rather than
  animating linked text per word.
- **`decodeEntities`** handles `&amp; &lt; &gt; &quot; &#39; &apos; &nbsp;` and numeric character
  references (`&#123;`, `&#x7B;`); any other named entity (e.g. `&copy;`, `&mdash;`) is left literal.
  This covers everything the dashboard's editors and the backend's canonicalizer can produce; it is
  not a general HTML-entity decoder.

## 8. Testing a site

After wiring a render site to `<RichText>`/`plainText`/`splitRichWords`, check, in each locale and
each theme (light/dark and every inverted surface the page uses):

- [ ] **Bold** renders with the surface's `--cms-rich-strong` colour/weight, not the browser default.
- [ ] **Link** is styled via `--cms-rich-link`/`--cms-rich-link-hover`, opens in a new tab only when
      external, and (if `renderLink` is wired) navigates client-side for internal paths.
- [ ] **List** (`ul`/`ol`) keeps its bullets/numbers and `--cms-rich-marker` colour under the site's
      CSS framework (Tailwind preflight especially).
- [ ] **Heading** inside a card renders at the offset level (`headingOffset`), not the raw `h2`.
- [ ] **Blank line** (an empty paragraph between two others) keeps its line height instead of
      collapsing.
- [ ] **`&`** and other special characters round-trip correctly — no literal `&amp;` or `&lt;` visible
      anywhere on the page.
- [ ] No literal tags (`<strong>`, `<p>`, …) visible as text anywhere on the page.
- [ ] No console errors and no React hydration-mismatch warnings on load.
