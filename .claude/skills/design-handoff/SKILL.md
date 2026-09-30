---
name: design-handoff
description: Parse a Claude Design export (URL or local folder) and produce a structured _design-manifest.json that downstream phases consume. Use this skill at the very start of any website build to translate the design package into a machine-readable plan. Triggers when the user references a Claude Design URL, a design folder, or asks to "implement this design".
---

# Design Handoff

Translates a Claude Design export into a `_design-manifest.json` that all downstream phases consume.

## Inputs

Either:
- A URL like `https://api.anthropic.com/v1/design/h/<hash>` (with optional `?open_file=<file>`)
- A local folder path containing `index.html`, usually `README.md`, and assets

## Steps

### 1. Locate the content

**If URL:** Use WebFetch to retrieve the URL. The response is HTML. Extract `<link>`, `<script src>`, and `<img src>` references. Construct full URLs by combining the base (strip `?open_file=...`) with each asset path. WebFetch each one. Save fetched assets to `_design-cache/` in the new project. Many Claude Design URLs serve a single self-contained HTML file with inline CSS and base64 images — if so, you only need one fetch.

**If local folder:** Use Glob to list all files recursively. Read `README.md` first if present, then `index.html`, then other HTML files, then CSS, then a sample of asset names (don't open every image).

### 2. Read the README

The design's `README.md` is your highest-priority source. It typically contains:
- The business / brand name
- The intent of the design (e.g. "marketing site for a coffee subscription")
- Page list and what each page is for
- Notes on intended interactions, animations, hover states
- Color palette and typography choices
- Caveats from Claude Design (e.g. "responsiveness was not the focus")

If there's no README, derive intent from the HTML structure and visible copy. **Flag this** in the manifest's `notes` array so downstream phases know context is thin.

### 3. Extract design tokens

From the CSS (inline or external):
- **Colors** — every distinct color. Name by purpose if inferrable (primary, accent, surface, text, muted). Convert to OKLCH where helpful, but keep the original hex too.
- **Typography** — font families used, type scale (h1 → body sizes), weights, line heights.
- **Spacing** — common spacing values (margin/padding patterns).
- **Border radii** — what radius values appear.
- **Shadows** — extract box-shadow definitions verbatim.

### 4. Identify pages and sections

For each HTML file in the design:
- Is it a full page or an embeddable section?
- What are the major sections (hero, features, pricing, footer, etc.)?
- What components repeat?

Use `<section>` tags, distinct `id`s, semantic landmarks (`<header>`, `<main>`, `<footer>`), and major layout breaks as section boundaries.

### 5. Identify assets

Catalog every image, font, and SVG. For each:
- Source path in the design
- Intended destination: `public/images/<section>/<name>.<ext>` (or `public/fonts/`, `public/svg/`)
- Kind: logo, hero image, content image, icon, decorative

**Do not modify or replace assets.** Just plan their placement.

### 6. Identify locale hints

Look for signs that the design implies a specific market or multilingual scope:
- Copy language (is it written in English, Dutch, French, multiple?).
- Country/market references in the README ("for Dutch SMBs", "EU-focused").
- Currency symbols (€ vs $ vs £).
- Address formats, phone number formats.
- Legal links (GDPR/AVG = EU; CCPA = California; etc.).
- Existing language switcher in the design markup.

Output a `locales` field in the manifest: `["en"]` if monolingual, `["en", "nl"]` if EN/NL bilingual is implied, etc. If genuinely ambiguous, leave as `null` so Phase 2 asks the user.

### 7. Identify interactions

Look for:
- Hover states (`:hover` CSS, JS event handlers)
- Animations (`@keyframes`, CSS transitions, JS animation libs)
- Scroll-triggered behavior (classes named `reveal`, `fade-in`, IntersectionObserver code)
- Form behavior (submit handlers, validation)
- Modal/dialog/dropdown patterns

Each one becomes a Motion implementation in Phase 4.

### 8. Flag responsive gaps

This is critical. Walk through the design's CSS and HTML and list places that will break on mobile:
- Fixed-width elements (`width: 800px`, `min-width: 1024px`)
- Missing `@media` rules
- Multi-column grids without mobile collapse
- Text sized in `vw` units without `clamp()` floor
- Horizontal navigation that won't fit narrow screens

These go into `responsive_gaps` so the responsive-audit skill knows where to focus.

### 9. Write the manifest

Write `_design-manifest.json` in the new project root:

```json
{
  "source": { "type": "url|folder", "ref": "..." },
  "business": {
    "name": "...",
    "description": "...",
    "domain": null
  },
  "intent": "marketing|product|portfolio|landing|service|...",
  "locales": ["en", "nl"],
  "default_locale": "en",
  "tokens": {
    "colors": {
      "primary": "#...",
      "accent": "#...",
      "surface": "#...",
      "text": "#...",
      "muted": "#..."
    },
    "fonts": {
      "display": "Font Name",
      "body": "Font Name"
    },
    "spacing": ["0.5rem", "1rem", "2rem", "..."],
    "richText": {
      "light":    { "strong": "#...", "em": "#...", "link": "#...", "linkHover": "#...", "marker": "#...", "heading": "#...", "quoteBorder": "#...", "rule": "#..." },
      "dark":     { "strong": "#...", "em": "#...", "link": "#...", "linkHover": "#...", "marker": "#...", "heading": "#...", "quoteBorder": "#...", "rule": "#..." },
      "inverted": { "strong": "#...", "em": "#...", "link": "#...", "linkHover": "#...", "marker": "#...", "heading": "#...", "quoteBorder": "#...", "rule": "#..." }
    },
    "radii": ["0.25rem", "0.5rem", "1rem"],
    "shadows": ["0 1px 3px rgba(0,0,0,0.1)", "..."]
  },
  "pages": [
    {
      "slug": "/",
      "title": "Home",
      "sections": [
        {
          "name": "hero",
          "intent": "Convert visitor with headline + primary CTA",
          "interactions": ["fade-in on load", "CTA hover scale"],
          "assets": ["public/images/hero/photo.jpg"]
        }
      ]
    }
  ],
  "assets": [
    { "src": "...", "dest": "public/images/hero/photo.jpg", "kind": "image" }
  ],
  "responsive_gaps": [
    "Pricing comparison table uses fixed widths; needs horizontal scroll wrapper on mobile",
    "Hero text uses 96px; needs clamp() for fluid scaling"
  ],
  "notes": [
    "No README provided; intent inferred from copy",
    "Design uses 5 colors but no semantic naming"
  ]
}
```

### `tokens.richText`

Per-surface colours for CMS rich text (`light`, `dark`, `inverted`; omit a surface the design lacks), mapped to the `--cms-rich-*` variables in phase 3. Contrast rule: an accent may be used for a slot only if it reaches WCAG AA (4.5:1) against that surface's background; otherwise set the slot to the surface's text colour and let font weight carry emphasis. If the design gives no values, leave `richText` out and phase 3 derives them from `tokens.colors` by this rule.

## When done

- The manifest exists at `<new-project>/_design-manifest.json`.
- Mock assets are either copied (local case) or downloaded to `_design-cache/` (URL case).
- If anything was genuinely ambiguous, you've asked the user one clarifying question.
- Hand back to the parent agent for Phase 2 (Clarify) and Phase 3 (Scaffold).
