# Phase 2 — Scan website & generate CMS integration report

**Orchestration:** per the skill's *Orchestration policy (ultracode)*, fan out via the Workflow tool for non-trivial sites (large source, multiple page types, multi-locale content model, or booking detection) — adversarially verify the proposed manifest before writing the report; be exhaustive.

**Goal:** Produce `cms-integration-report.md` listing every recommended CMS service, grouped into sections, written for human review.

**Inputs:** `<folder_name>`, output of Phase 1, Anthropic Claude.

## Steps

1. Read source files via `file_reader.read_website_files`. Cap by size + count, skip excluded dirs.
2. Detect logo: scan `<folder_name>/public/` for `.svg`, `.png`, `.jpg`, `.jpeg`, `.webp`. Prefer filenames containing `logo`, `brand`, or `mark`. Record relative path. Also record every other image, illustration and content icon the pages render (each becomes an image/icon field, ADR-0011; UI-control icons stay in code) and the design's palette, surfaces and fonts (they seed `general_theme`).
3. Call Claude with `prompts.py` SYSTEM_PROMPT. **Model: `claude-opus-4-8`** with effort `xhigh` — scan accuracy drives every downstream phase, so use the strongest model. Mark the system block with `cache_control: {"type": "ephemeral"}` for prompt caching on retries.
4. Compose the report (structure below).
5. Write the report to `agents/CMS Connector - Website/cms-integration-report.md`. **Temporary** — deleted at end of Phase 6.
6. Halt and ask user to review. Do not proceed until explicit approval.

## Output

`cms-integration-report.md` written to disk.

## Required report structure

```markdown
# CMS Integration Report — <project_slug>

Generated: <UTC timestamp>
Source: <folder_name>
Repo: <github_repo>
Locales: <detected locales from i18n/routing.ts> | Default: <default_locale> | Per-locale translations found: <yes/no — messages/<locale>.json present>

## Section 1 — General

- Display name (header / business name / person name): "<value>"  → text_block service `general_brand_name`
- Logo (if found in /public): "<relative path>" → image service `general_logo`
  - If no logo: "No logo detected in /public/. Confirm whether site uses a logo."
- Theme → theme service `general_theme` (`translatable: false`): palette colours (named, `#rrggbb`), surfaces (page light/dark, card, header, footer), fonts (Google by default, weights actually used, italic only if used), `body_font`, `heading_font`
  - A non-Google font the site self-hosts is seeded as `{"family", "source": "system"}` (never `"upload"`: the backend rejects an upload font without files in project storage). The site's own bundled `@font-face` of that family still resolves it. List its font files here (path, weight, style); Phase 4 step 3e uploads them and switches the font to `source: "upload"`.
  - Theme colours are recommendations (rich-text swatches, icon tints); they do not drive the site palette.

## Section 2 — Contact (only if contact info detected)

Single `key_value` service named `contact_info`. Add ONE entry per
contact channel detected — pick keys that match the operator's mental
model (their language, their convention), not ours. The website's
contact resolver is heuristic-driven (see "Generated client website
contracts" in [`AGENTS.md`](../AGENTS.md)) — it picks an icon/label/
href automatically based on:

- **Value shape**: anything containing `@` renders as Email; anything
  matching a phone-number pattern renders as Phone — regardless of
  the key the operator chose.
- **Key family**: keys containing stems like `address` / `location`,
  `hour` / `schedule` / `program` / `time`, `website` / `site` /
  `url` resolve to address / business-hours / website cards.
- **Fallback**: any unrecognised key still renders, with the key
  itself humanised as the label.

Examples (any of these work):
- Email → entry `email`, `mail`, `correo`, `email_office`, …
- Phone → entry `phone`, `mobile`, `telefon`, `phone_secondary`, …
- Address → entry `address`, `location`, `office_address`, `adresa`, …
- Hours → entry `hours`, `schedule`, `program`, `working_hours`, `orar`, …
- Custom → e.g. `whatsapp`, `linkedin`, `vat_number` — render as
  generic info cards.

**Do not** invent a fixed schema or normalise the operator's keys.
Capture them verbatim from the source (or as the operator dictates
during review). The website handles every case.

For multi-day opening hours that need granular structure, prefer a
separate `repeater` service `schedule_hours` with `item_schema`
`[day, open, close]` instead of stuffing them into key_value.

## Section 3+ — Domain-specific (one per detected category)

For each:
- Section name (About / Hobbies / Projects / Experience / Menu / Services / About Us / etc.)
- Each piece of content with:
  - Suggested `service_key` (snake_case)
  - Suggested `service_type_slug`
  - Source location (`file_path:line` or component name)
  - For repeaters: full `item_schema` (key, label, type; `hint` on image/icon fields, `surface` on icon fields)
  - For every image/icon field: the source asset (path, or the icon component / Lucide name) that Phase 4 uploads as the seed, and the hint `{width, height}`
  - `initial_content`: extracted current values

## Field formats (rich text, ADR-0010)

The report MUST list each field's format. Classify like this:

- Prose the client should be able to format -> `inline` (titles, labels, short lines) or `richtext` (bodies, descriptions, bios, anything that could hold a list).
- Machine values stay `string`/`url`/plain: URLs, emails, phone numbers, addresses parsed by code, hours, prices used as numbers, slugs, alt text, anything feeding `href`/`tel:`/`mailto:`/`Number()`/regex.
- Repeater `item_schema` types: `string` (plain), `inline`, `richtext`, `url`, `tags`, plus the media types `image` and `icon` (see below).
- `key_value` entries get a per-entry `formats` map (`plain`/`inline`/`rich`, default `plain`).
- `text_block` title/body need no config (always inline/rich).
- Source rich text (Markdown, Portable Text, HTML in the old site) is emitted in `initial_content` as **canonical HTML** (allowed tags only), never Markdown.
- Rich text may contain styled spans (ADR-0011): a source span's colour/font/size is kept in the canonical form `<span style="color:#1e5aa8;font-family:'Open Sans';font-size:1.25em">`.

See [ADR-0010](../../../docs/decisions/0010-rich-text-content.md) and the [kit README](../../../client-kit/rich-text/README.md).

## Images, icons and theme (ADR-0011)

The report MUST list every image, illustration and icon as a field, following the [contract in AGENTS.md](../AGENTS.md#theme-images-and-icons-contract-adr-0011):

- **Every image and illustration is a CMS image field** (standalone `image` service or a repeater `image` field) with a `hint: {width, height}` matching the slot's rendered aspect at 2× density (e.g. full-width banner 1600×600, card 800×600, avatar 400×400). A standalone image service carries it as `_hint` in `initial_content`. Per-item images (service banner, team portrait) are repeater `image` fields, never `url`. Only the favicon/OG generator assets stay in code.
- **Every content icon is a CMS icon field** (icons on services, features, items, contact methods and the like; `icon` repeater field) with `surface` set to the theme surface it sits on. UI-control icons (menu, close, chevrons, arrows, spinners, form affordances) stay in code. Contact-method icons stay heuristic only where the contact service is `key_value`.
- Seeds: a repeater `image` field seeds `""` and an `icon` field `null` (stored values must be https URLs); the report names the source asset so Phase 4 uploads it. An animated SVG component stays the in-code fallback.
- **Every project gets a `general_theme` service** (Section 1 above). Themes, images and icons are never translated.

## Booking Service (only if `booking.detected` is true in the manifest)

```markdown
## Booking Service

- **Public slug:** `<public_slug>`
- **Business name:** `<business_name>`
- **Brand colors:** accent `<accent_color>` | primary `<primary_color>`
- **Locale / timezone:** `<locale>` / `<timezone>`
- **Calendar provider:** none (headless — no calendar sync)
- **Reminder offsets (hours before):** `<reminder_offsets list>`

### Services

| Name | Duration |
|------|----------|
| <service_name> | <duration_minutes> min |

### Resources / Staff

- `<resource_name>` (repeat per resource)

### Weekly Hours

| Day (0=Sun … 6=Sat) | Open | Close |
|---------------------|------|-------|
| <weekday>           | <open_time> | <close_time> |

### Destination email

`<destination_email>` — **Edit this to the client's actual email before Phase 4 runs.** If left blank it defaults to `stefanromanpers@gmail.com`.

### Client UI wiring

Components from design that will be wired to `lib/booking.ts`: `<ui_wiring.components list, or "iframe fallback">`.

Public API contract the wired UI will use:
- `GET /booking/{slug}/services` — service picker
- `GET /booking/{slug}/availability?service_id=&from=&to=` — date/time slots
- `POST /booking/{slug}` — submit booking → returns `booking_id` + `manage_url`
- Reschedule / cancel → centralized CMS-hosted `/manage/{token}` page (no client-side manage UI needed)
```

> **Narrowed detection rule:** a plain contact form (name + email + message → sends an email) stays `email_config`. The `booking` block is generated **only** when the site has genuine scheduling intent — service selection, date/time picking, appointment slots.
>
> Stefan reviews and edits this section — especially the destination email — before Phase 4 provisions anything.

## Section: Excluded items

List items the agent considered but rejected, with reason. Examples:
- Navigation menu links — excluded (structural)
- Button labels ("Submit", "Send", "Learn more") — excluded (UI affordance)
- Page titles in `<title>` — excluded (route metadata)
- CSS class names, Tailwind utilities — excluded
- Animation timings, breakpoints, spacing/radius/shadow tokens — excluded (palette and fonts go into `general_theme`)
- Favicon, OG generator assets — excluded (stay in code)
- Test fixtures, mock data — excluded

## Section: Open questions for review

Anything uncertain. Examples:
- "Detected `<h1>` 'Welcome to MyShop' on Home — editable, or permanent tagline?"
- "Two image grids: gallery on About, project thumbnails on Projects. Both gallery, or Projects as repeater(title, image)?"

## Approval

User must reply "approved" before Phase 3.
```

## Hard rules (also in `prompts.py` SYSTEM_PROMPT — keep in sync)

**Always include:**
- General section every site, even if minimal, including the `general_theme` service.
- One service per editable string, image, or list of items the client realistically maintains.
- For services lists / menus: examine each item's structure carefully; ensure every per-item field has a corresponding repeater field. Missing a field is the most common Phase 2 bug.
- Every image, illustration and content icon as an image/icon field with a hint (icons also a `surface`); UI-control icons stay in code.

**Never include:**
- Button / CTA labels
- Navigation items
- Page-level routes / page metadata
- Hard-coded UI affordance copy
- Class names, design tokens, animation config, breakpoints (the palette and fonts go only into `general_theme`)
- The favicon and OG generator assets
- Test fixtures, mock data

**Decision rule when ambiguous:** "would a non-developer client reasonably ask 'can I change this myself?'" → include. Else exclude.

## Failure feedback

| Cause | Message |
|-------|---------|
| Source folder unreadable | "Cannot read source files in `<folder_name>`. Check permissions." |
| Claude returned non-JSON | "LLM returned malformed output. Raw response written to `agents/CMS Connector - Website/.last-llm-output.txt`." |
| Source appears binary | "Source files appear binary/corrupted. Verify the directory contains text source." |

## Self-improvement hook

When the user reviews the report and says X should have been caught (or shouldn't have been included), append to `LEARNINGS.md` under `## Phase 2 — Scan rules`. Format: `- <date>: <one-line rule>. Triggered by: <short context>.` Next run, the agent reads LEARNINGS.md and includes those rules in the SYSTEM_PROMPT for Claude.

Example learned rules:
- `- 2026-06-06: The language-SWITCHER control/labels stay excluded (chrome); DETECT the locale set from i18n/routing.ts + messages/<locale>.json and import per-locale CONTENT as first-class CMS data. Supersedes 2026-04-29 rule. Triggered by: multilingual sites have real per-locale content that must be imported.`
- `- 2026-05-12: For e-commerce sites, always recommend a top-level shipping_policy rich-text. Triggered by: missed shipping-policy text on three runs.`
