# ADR-0011: Project theme, styled rich text, and CMS-editable images and icons

Status: Accepted
Date: 2026-10-11
Amends: ADR-0010 (colour, font and size marks are now allowed, in one restricted form)

## Context

Clients want to change what their site looks like without a developer: swap every image and
illustration, swap icons (including their own SVGs, recoloured to fit the site), pick the site
font from any web font, and colour/resize/re-font parts of a title or paragraph. ADR-0010 forbade
colour, font and size in stored text, so every site had to hard-code its illustrations, icons and
fonts. A free-for-all (arbitrary `style`, arbitrary SVG) would reopen the XSS and "content breaks
the design" problems ADR-0010 closed, so the new freedom has to be narrow and validated in one
place, the same way rich text is.

## Decision

- **Styled spans.** `span` joins the mark tags of both formats (`inline` and `rich`). It carries
  exactly one attribute, `style`, whose only allowed declarations are, in this canonical order:
  `color` (`#rrggbb`, lowercase; `#rgb` and `rgb(r, g, b)` input is converted), `font-family`
  (one family name of letters, digits, spaces and hyphens, max 64 chars, serialised single-quoted
  with no fallback list) and `font-size` (an `em` value from 0.5 to 4, at most 3 decimals,
  trailing zeros stripped). Canonical form: `<span style="color:#1e5aa8;font-family:'Open Sans';font-size:1.25em">`.
  Anything else in `style` is dropped; a span left with no valid declaration is unwrapped. Spans
  count toward `MAX_MARK_DEPTH`. `services/rich_text.py` and the client kit stay 1:1 ports, pinned
  by the shared fixtures. `a[href]` and `span[style]` are the only stored attributes.
- **Old sites degrade gracefully.** Kit `1.0.x` unwraps unknown tags and keeps their text, so a
  site that has not re-synced the kit (`1.1.0`+) shows styled text in its normal style. No
  `rich_text_version` bump is needed. The dashboard only shows the font/colour/size controls for a
  project that has a theme service (its site is wired for this ADR).
- **Theme service.** A project's look lives in at most one service of the new `theme` type
  (key `general_theme` by convention, page "General"), so it goes through draft/publish and
  preview like all content (ADR-0005) and reaches sites in the existing public manifest
  (additive, ADR-0006). Shape:
  `{colors: [{name, value}], surfaces: [{name, value}], fonts: [Font], body_font, heading_font}`
  where `Font` is `{family, source: "google", weights: int[], italic: bool}`,
  `{family, source: "upload", files: [{url, weight, style}]}` or `{family, source: "system"}`.
  `services/theme.py` validates it on every save (hex colours, family charset, https URLs under
  our storage bucket for uploads, weight 100–900, style normal/italic, size caps) and returns 422
  on anything else. A theme is never translated. Theme colours are recommendations (rich-text
  swatches, icon tints checked for ≥ 3:1 contrast against the theme's surfaces); they do not
  recolour the site's design. Theme fonts are live: sites load them and use `body_font` /
  `heading_font` through `--cms-font-body` / `--cms-font-heading`.
- **Fonts on sites.** The kit's `<ThemeStyles>` builds the Google Fonts `css2` URL from
  family/weights/italic, `@font-face` rules for uploaded files, and the font CSS variables. Sites
  keep a bundled default font as the fallback when the theme is missing.
- **Media field types.** Repeater `_schema` gains `image` (value: a URL string, `""` for none) and
  `icon` (value: `{src, mode: "tint" | "original", color: "" | "#rrggbb", name}` or `null`).
  Schema fields may carry `hint: {width, height}` (recommended pixel size) and, for icons,
  `surface` (the theme surface name the icon sits on, used for colour recommendations). A
  standalone `image` service may carry the same hint as `_hint`. `hint`, `surface` and `_hint` are
  structural metadata: admin/agent-set, preserved on a client save (like `_schema`/`_formats`).
  Neither field type is translated.
- **SVG uploads.** SVG is accepted wherever images are, but only after
  `services/svg_sanitize.py` rewrites it from an allow-list of shape elements and presentation
  attributes (no scripts, event handlers, `foreignObject`, external references, DOCTYPE/entities).
  Icons render through the kit's `<CmsIcon>`: `tint` mode draws the SVG as a CSS mask filled with
  the chosen colour (or `currentColor`), so uploaded SVG markup is never inlined into a page;
  `original` mode renders it as an `<img>`. Icons picked from the dashboard's icon set are
  rendered to SVG and uploaded the same way, so sites need no icon library.
- **Every image is a CMS field.** Generated sites read every image and illustration (including
  per-item images such as a service banner) from an image field with a size hint; the design's
  artwork is the seed/fallback, not a hard-coded asset.

## Consequences

- Clients can restyle text, swap images/icons and change fonts themselves; the theme keeps their
  choices aligned with the site.
- Styled text can clash with a dark surface; the theme's surfaces and contrast hints mitigate it
  but cannot prevent it. A site that wants to forbid styling can ignore spans by not re-syncing
  the kit.
- Existing sites keep working unchanged; each one adopts the features by re-syncing the kit and
  wiring the theme, image and icon fields.
- Do NOT: allow any other `style` property, any other attribute, or a font-family list; inline
  uploaded SVG markup into a page; serve an unsanitised SVG; store a second theme service in a
  project; translate theme, image or icon values; let a client save change `hint`, `surface` or
  `_hint`.
