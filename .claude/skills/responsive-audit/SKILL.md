---
name: responsive-audit
description: Audit a Tailwind site for responsive design failures across mobile, tablet, and desktop breakpoints, and apply fixes. Use after initial implementation or whenever the design's source had known responsiveness gaps (often flagged in the design manifest's responsive_gaps array). Triggers on phrases like "make it responsive", "fix mobile", "test breakpoints", "responsive audit".
---

# Responsive Audit

Claude Design outputs often have responsiveness gaps. This skill systematically catches and fixes them.

## The breakpoint sweep

Walk through these viewports in order. At each, screenshot the page (via Playwright MCP if available, otherwise inspect in `npm run dev` with browser devtools).

| Breakpoint | Width | Represents |
|---|---|---|
| Mobile S | 375px | iPhone SE, small Android |
| Mobile L | 414px | iPhone Pro Max, large Android |
| Tablet | 768px | iPad portrait |
| Laptop | 1024px | iPad landscape, small laptops |
| Desktop | 1440px | Standard desktop |
| Wide | 1920px | Large monitors |

The 375 and 768 breakpoints catch 95% of issues. Don't skip them.

## What to check at each breakpoint

For every page and every section:

1. **No horizontal overflow.** `document.documentElement.scrollWidth === window.innerWidth`. Common causes: fixed-width elements, `min-width` without overflow handling, oversized images, very long unbreakable text (URLs, hashes), grids that don't reflow.
2. **All text readable.** Body text ≥ 16px on mobile (Tailwind `text-base`). Headlines fluid via `clamp()` or breakpoint-stepped.
3. **Tap targets ≥ 44×44px.** All clickable elements on mobile. Inspect every `<button>`, `<a>`, icon-button.
4. **No content cut off.** Especially form fields, navigation menus, cards in grids, pricing tables.
5. **Images scale correctly.** `<img>` with `srcset` and `sizes` props. No fixed-pixel widths on hero images.
6. **Spacing scales.** Padding/margin should reduce on mobile (`py-12 md:py-24 lg:py-32`, not just `py-32`).
7. **Hover-only interactions have a non-hover fallback.** Mobile has no hover state — tap or visible state must exist.
8. **Navigation collapses.** Horizontal nav with > 4 items must become a hamburger or stack on mobile.
9. **Modals/dialogs fit.** Full-screen on mobile, centered on desktop.

## Tailwind patterns to enforce

### Mobile-first sizing

```tsx
// WRONG — desktop-first, breaks the mental model
<div className="text-4xl md:text-2xl">...</div>

// RIGHT — start small, scale up
<div className="text-2xl md:text-4xl lg:text-5xl">...</div>
```

### Fluid type with `clamp()`

For hero headlines that should scale continuously rather than jumping at breakpoints:

```css
/* In globals.css */
.text-display {
  font-size: clamp(2rem, 5vw + 1rem, 5rem);
  line-height: 1.05;
  letter-spacing: -0.02em;
}
```

Or inline with Tailwind arbitrary values:

```tsx
<h1 className="text-[clamp(2rem,5vw+1rem,5rem)] leading-[1.05] tracking-tight">
```

### Responsive padding

```tsx
<section className="px-4 py-12 md:px-8 md:py-20 lg:px-12 lg:py-28">
```

### Container queries for component-internal layout

Use when a component's layout depends on ITS OWN width (e.g., a card in a sidebar vs. a full-width grid):

```tsx
<div className="@container">
  <div className="grid grid-cols-1 @md:grid-cols-2 @lg:grid-cols-3 gap-4">
    {/* cards */}
  </div>
</div>
```

This is Tailwind v4's preferred pattern for component-level responsiveness, distinct from viewport-level `md:` / `lg:`.

### Image `sizes` and `srcset` props

```tsx
<img
  src="/images/hero/photo.jpg"
  alt="..."
  srcset="/images/hero/photo-480.jpg 480w, /images/hero/photo-1024.jpg 1024w, /images/hero/photo-1920.jpg 1920w"
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
/>
```

Or use an `<Image>` wrapper component. Without `sizes` and `srcset`, the browser serves the largest image to every viewport — kills mobile performance.

## The fix workflow

For each issue found:

1. Identify the offending element and its current classes.
2. Determine root cause (fixed width? wrong order? missing breakpoint?).
3. Apply the smallest fix that resolves it.
4. Re-screenshot to verify.
5. If the fix is non-obvious or counterintuitive, log it to `.learnings/conventions.md` so the next site doesn't repeat the mistake.

## Accessibility cross-check (do during responsive pass)

While auditing responsive, also catch:

- Missing `alt` on `<Image>`.
- `<button>` without accessible text (icon-only without `aria-label`).
- Color contrast < 4.5:1 for body text, < 3:1 for large text. Tailwind default colors against default backgrounds usually pass; danger zones are accent text on accent backgrounds.
- Focus visible on all interactive elements. If `focus:outline-none` is used without a replacement `focus-visible:ring-2`, fix it.
- Form inputs have associated `<label>` (visible or `sr-only`).
- Heading hierarchy doesn't skip levels (no `<h1>` directly to `<h3>`).
- `lang` attribute on `<html>`.

Run an automated pass:

```powershell
# In one terminal
npm run dev

# In another
npx @axe-core/cli http://localhost:3000
npx @axe-core/cli http://localhost:3000/about
# ... for each page
```

Fix every reported violation. If a violation is intentional (rare), comment in code with justification.

## Outputs when done

1. All breakpoints show no overflow, no cut-off content.
2. axe-core reports 0 violations on every page.
3. `.learnings/conventions.md` has at least one entry from this audit (a non-obvious fix or pattern).
4. The `responsive_gaps` array in `_design-manifest.json` is empty or every item has a matching `.learnings/` entry explaining how it was resolved.
