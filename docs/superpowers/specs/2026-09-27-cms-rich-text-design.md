# CMS Rich Text — Design Spec

Date: 2026-09-27 · Status: approved-by-autonomy (Stefan asked for plan → self-review → subagent implementation without sign-off stops) · Branch: `feat/rich-text`

## 1. Goal

Every human-prose text field in the CMS is edited with a rich-text editor (bold, italic, underline, strikethrough, links, bullet and numbered lists, headings, quotes, dividers, line breaks and blank lines). No colours, fonts or sizes in the editor: **each client website's theme decides how formatting looks** (e.g. the colour of bold text on a dark hero vs a light card). This works for all four live sites (it-global-services, samir-kapsalon, laurian-duma-portfolio, akris) and for every future site produced by the Website Builder and CMS Connector agents.

### Success criteria

1. A client can format any prose field in the dashboard, save, publish, and see it rendered with their site's theme on every live site, in every locale.
2. Nothing breaks on any live site at any point in the rollout (no literal `<strong>`/`**`/`&amp;` visible, no broken meta tags, links, `tel:`/`mailto:` hrefs, React keys, animations or hydration).
3. Formatting survives DeepL translation into every enabled locale.
4. Stored content is always sanitized server-side; no XSS path exists from dashboard input to any site.
5. Future sites built by the agents render rich text and define the theme contract by default.

### What Stefan said vs what I assumed

Said: every text field becomes a rich text box; bullets, bold, italic, underline, spacing; no colours; site theme decides formatted-text colour per background; system for all current and future sites; update the connector and website-builder agents; plan, self-review, subagent implementation; handle all edge cases.

Assumed (recorded decisions):
- **A1** "Every text field" means every *human-prose* field. Machine values — URLs, emails, phone numbers, prices-as-numbers, slugs, hours, alt text, file names, anything feeding `href`/`tel:`/`mailto:`/`Number()`/regex detection — stay **plain** single-line inputs. Formatting there is meaningless and would break links, accessibility and SEO. The dashboard still shows every prose field as a rich box.
- **A2** Titles/headings get **inline** formatting (bold, italic, underline, strike, link, line break) but not lists/headings (a title with a bullet list is not a title). Bodies/descriptions get the full **rich** toolbar.
- **A3** Deploying includes committing, pushing, promoting the CMS (dev → main via the manual workflow) and pushing each client site to its preview and production branches after verification — the same flow Stefan used for it-global-services today.

## 2. Current state (facts that constrain the design)

- `text_block.body` and repeater `richtext` fields are already **Markdown by convention** (27 repeater richtext fields live; George's `about_main_body` uses `**bold**`/`##`; Akris renders news/OATK via `react-markdown`). DeepL translates them as plain text (`formats_of` → `"markdown"`, no tag handling), so markup can be mangled today.
- Everything else is plain text: `text_block.title`, repeater `string`, `key_value` values, `image.alt`, `file_download.filename`.
- No server-side sanitisation of CMS content; `ContentSaveRequest.content` is an unvalidated dict (ADR-0002 says the backend is the security boundary).
- `bleach` is a backend dependency (`services/html_sanitizer.py` for lead design prompts). The dashboard already ships TipTap v3 (StarterKit 3.23.5 bundles Underline and Link), `isomorphic-dompurify`, `@tailwindcss/typography`.
- DeepL provider already supports `fmt="html"` → `tag_handling=html`; placeholder masking (`protect.py`) handles `{…}` only.
- Client sites (ADR-0006: public payload is a contract with repos we don't see):
  - **it-global-services** — Next 16 + next-intl, Tailwind v4, CSS vars, `data-theme` dark mode, reads CMS via `src/lib/cms.ts`; word-splits the hero tagline and brand wordmark; hand-rolled Markdown `RichBody`.
  - **samir-kapsalon** — Next 16 + next-intl, merges CMS into ICU messages; plain `t()` throws on tags; `t.raw()` bypasses ICU.
  - **laurian-duma-portfolio** — Vite 8 SPA, Tailwind v3, always dark, client-side `useCMSContent()`.
  - **akris** — Vite 6 SPA, Tailwind v3 via CDN (typography plugin not loaded), `react-markdown`; `FadeInText` word-splits hero text.
  - None renders HTML; none has a sanitizer.

## 3. Architecture overview

```
Dashboard (TipTap editor per field format)
   │  PUT content (HTML for inline/rich leaves)
   ▼
Backend save  ── resolve format per leaf ── normalize (legacy→HTML) ── sanitize (bleach allow-list) ── limit
   │                                                           │
   │                                                           └─ DeepL fmt="html" → re-sanitize → locale drafts
   ▼
content_entries (draft/published, per locale)  ── publish (unchanged)
   │
   ▼  GET /content/{slug}[/{locale}]  (+ top-level "rich_text_version")
Client site  ── client-kit: <RichText> / plainText() / splitRichWords()  ── theme via --cms-rich-* CSS variables
```

Gate: **`projects.rich_text_version`** (0 = legacy behaviour everywhere, 1 = rich text on). Existing projects start at 0 and flip to 1 only after their site ships the client kit and their data is migrated. New projects default to 1.

## 4. Content model

### 4.1 Field formats

| Format | Stored value | Allowed markup | Editor |
|---|---|---|---|
| `plain` | raw string, no HTML semantics | none | single-line input (typed validation for url/email/tel) |
| `inline` | HTML fragment, no block wrapper | `strong em u s a[href] br` | inline rich editor (no lists/headings); Enter = line break |
| `rich` | HTML document of blocks | `p br strong em u s a[href] ul ol li h2 h3 h4 blockquote hr` | full rich editor |

No `class`, `style`, `id`, `target`, `rel` or any attribute other than `a[href]` is ever stored. Colour, font and size cannot be represented, by construction.

### 4.2 Format resolution (single source of truth: `services/rich_text.py::format_of`)

| Service type | Leaf | Format |
|---|---|---|
| `text_block` | `title` | `inline` |
| `text_block` | `body` | `rich` |
| `image`, `floor_plan` | `alt` | `plain` |
| `file_download` | `filename` | `plain` |
| `key_value` | `entries.<k>` | `content._formats[k]` ∈ {plain, inline, rich}; default `plain` |
| `repeater` | `items.<id>.<key>` | by `_schema` field type: `string`→plain, **`inline`→inline (new)**, `richtext`→rich, `url`→plain (never translated), `tags`→plain per tag |
| `gallery`, `video`, `email_config` | — | no text leaves |

`_formats` (key_value) and `_schema` (repeater) are **structural metadata**. They are set by admins/agents (connector seed, migration script, admin dashboard save) and preserved server-side on every non-admin save: a client save cannot change a field's format.

When `rich_text_version = 0`, `format_of` still resolves, but the save path skips normalisation/sanitisation and translation uses the legacy formats (`markdown`/`text`) — i.e. today's behaviour exactly.

### 4.3 Canonical HTML

The backend is the only writer (ADR-0002), so it defines canonical form:
- Allow-list sanitisation via `bleach` (`strip=True`, comments stripped). Disallowed tags are removed but their text is kept; `script`/`style`/`iframe`/`object`/`svg`/`math` are removed **with** content.
- Synonym mapping before sanitising: `b→strong`, `i→em`, `strike|del→s`, `ins→u`, `h1→h2`, `h5|h6→h4`, `div→p` (rich) / unwrap (inline).
- `a[href]` kept only when, after stripping whitespace and ASCII control characters and decoding entities, the scheme is `http`, `https`, `mailto` or `tel`, or the href starts with `/` (not `//`) or `#`. Otherwise the `<a>` is unwrapped (text kept). Bare domains typed in the editor are prefixed with `https://` by the dashboard, not the backend.
- Inline: any block tags are unwrapped; block boundaries become `<br>`; leading/trailing `<br>`s trimmed.
- Rich: loose top-level text/inline nodes are wrapped in `<p>`; nested lists allowed (depth ≤ 4, deeper flattened); a document consisting only of empty paragraphs normalises to `""`. **Interior empty paragraphs are preserved** — they are the "add spaces" feature.
- Whitespace: trimmed at the ends; `&nbsp;` preserved.
- Idempotent: `canonical(canonical(x)) == canonical(x)` (tested).
- Limits (serialized length after canonicalisation): inline ≤ 2 000 chars, rich ≤ 50 000 chars. Exceeding returns **422** `{"detail": "Field <path> is too long (N > max)"}`.

### 4.4 Legacy conversion (plain / Markdown → HTML)

Detection: a value "is HTML" iff it matches `<(p|br|strong|em|u|s|a|ul|ol|li|h[1-6]|blockquote|hr|b|i|div|span)\b[^>]*>` (case-insensitive).

**Critical rule (prevents double-escaping):** a canonical `inline` value often contains no tags at all (`Tom &amp; Jerry`), so it is indistinguishable from legacy plain text. Therefore:
- `inline` values are **always parsed as HTML fragments** — in the save path, the dashboard and the client kit. Legacy inline conversion runs **only inside the one-time migration** of a version-0 project (the version gate makes it run exactly once per project).
- `rich` values without any tag are legacy (canonical rich always starts with a block tag), so the save path, dashboard and kit convert them.

Legacy conversion:
- **Rich** (Markdown-lite, exactly the existing convention): HTML-escape `& < >` (and ` `→`&nbsp;`); `**x**`/`__x__`→strong, `*x*`/`_x_`→em (word-boundary aware with an explicit `[0-9A-Za-zÀ-ɏ]` word class so Python and JS agree), `~~x~~`→s, `[text](url)`→a (href rules of 4.3); `#`/`##`→h2, `###`→h3, `####`+→h4 at line start; `- `/`* `/`+ ` and `1. `/`1) ` line runs → ul/ol (flat); a non-marker line right after a list item continues that item with `<br>`; `> ` line runs → one blockquote paragraph; `---`/`***`/`___` → hr. Blank line(s) separate blocks; a single `\n` inside a paragraph → `<br>` (matches the `remark-breaks` behaviour sites use today). Lines are trimmed and internal whitespace runs collapsed.
- **Inline** (migration only): no Markdown (inline sources were plain strings, where `*` is literal); trim leading/trailing blank lines, escape each line, join lines with `<br>`.
- The converter emits canonical HTML directly (`canonicalize(legacy_to_html(x)) == legacy_to_html(x)`, tested).

A shared JSON file of test vectors (`client-kit/rich-text/fixtures/legacy-vectors.json`) is asserted by **both** the Python converter and the TypeScript client-kit fallback, so the two stay identical.

## 5. Backend changes

1. **`services/rich_text.py`** (new): `Format` literal; `format_of(service_type, leaf_path, content)`; `is_html(v)`; `legacy_to_html(v, fmt)`; `canonicalize(v, fmt)`; `normalize_content(service_type, content) -> content` (walks every text leaf via `segments_of`, applies legacy conversion + canonicalisation to inline/rich leaves, enforces limits); `plain_text(html)`.
2. **`services/segments.py`**: `_TRANSLATABLE_FIELD_TYPES` adds `inline`; `formats_of(service_type, content, rich_text_version)` returns `"html"` for inline/rich leaves when version ≥ 1, legacy `markdown`/`text` otherwise; key_value reads `_formats`.
3. **`routers/workspace.py` `save_service`**:
   - Load project `rich_text_version` (added to the project select in `deps.py`).
   - Structural protection: for non-admin users, replace incoming `_schema` (repeater) and `_formats` (key_value) with the stored default-locale values (draft → published fallback), extending the existing `_grafted_repeater_content` pattern. Admins/seed may change them; validate `_formats` values ⊂ {plain, inline, rich} and `_schema` types ⊂ {string, inline, richtext, url, tags} (422 otherwise).
   - When version ≥ 1: `normalize_content` **before** the default-locale upsert, translation fan-out and the non-default manual-override diff (so hashes are computed over canonical HTML).
   - Response re-fetch unchanged.
4. **Translation (`translation/sync.py`, `translation/deepl.py`)**: pass `rich_text_version` to `formats_of`; after `provider.translate(fmt="html")`, re-canonicalise every translated inline/rich leaf with its format (DeepL may emit odd markup). DeepL `html` mode already sets `tag_handling=html`. **The DeepL provider chunks each batch so no request body exceeds 100 KiB** (DeepL's limit is 128 KiB; rich leaves up to 50 000 chars make one-request batches unsafe), preserving input order and the count check across chunks. Null provider echoes (already canonical).
5. **`add_service`** allowed repeater types: add `inline`; accept optional `formats` (key_value) on create.
6. **Public content (`routers/content.py`)**: add top-level `"rich_text_version": <int>` to all four content endpoints (additive; ADR-0006-compatible). `_formats` already rides along inside key_value content. The `/types` `.d.ts` endpoint documents `RichHtml`/`InlineHtml` string aliases per leaf.
7. **Service detail (`GET /projects/{slug}/services/{key}`)**: add `rich_text_version`, `can_edit_structure` (caller is admin) and a computed `field_formats` map so the dashboard never re-implements resolution. Shape is **per field, not per item**: `text_block` → `{"title": "inline", "body": "rich"}`; `repeater` → `{"<field_key>": <format>}` for every `_schema` field (`url`/`tags` → `"plain"`); `key_value` → `{"<entry_key>": <format>}` for every stored entry plus `"*": "plain"` as the default for new entries; `image`/`floor_plan` → `{"alt": "plain"}`; `file_download` → `{"filename": "plain"}`.
8. **Project admin**: `PATCH /admin/projects/{slug}` accepts `rich_text_version` (admin only) for the rollout.
9. **DB migration `backend/migrations/2026_09_27_rich_text.sql`**:
   ```sql
   alter table projects add column if not exists rich_text_version smallint not null default 0;
   alter table projects alter column rich_text_version set default 1;
   update service_types set schema = jsonb_set(schema, '{fields,title,type}', '"inline"') where slug = 'text_block';
   ```
   Existing rows get 0 at add time; projects created afterwards get 1. Applied **before** the backend deploy (additive; old code ignores the column).
10. **ADR `docs/decisions/0010-rich-text-content.md`**: stored format, formats taxonomy, per-project gate, client-kit contract, theme variables, do-nots.
11. **Other backend readers**: any backend code that reads CMS text leaves for non-display purposes (transactional email bodies/subjects, form notifications, booking emails, `.d.ts` generation, logs) must call `plain_text()` (or `html.escape` on it for email HTML) — never inject stored HTML into emails. The implementation greps every reader of `content_entries` content and fixes each.

## 6. Dashboard changes (`frontend/`)

New folder `src/components/dashboard/rich-text/`:
- `extensions.ts` — TipTap extension sets per mode. Rich: StarterKit (heading levels 2–4; `code`, `codeBlock` disabled; Link `openOnClick:false, autolink:true, linkOnPaste:true, protocols` restricted; Underline on). Inline: custom `Document` with `content: 'paragraph'` + Bold/Italic/Underline/Strike/Link/HardBreak/History; Enter → `setHardBreak()`.
- `serialize.ts` — `toStored(editor, mode)`: rich → `getHTML()` with all-empty doc → `""`; inline → unwrap the single `<p>`, `""` when empty. `fromStored(value, mode)`: legacy (non-HTML) values go through the same legacy conversion as the backend (TS port shared with the client kit, tested with the same vectors) so an unmigrated value opens correctly.
- `RichTextEditor.tsx` — props `{ value, onChange, mode: 'inline'|'rich', label, placeholder?, maxLength, disabled?, id }`. Controlled-on-mount; `onChange` called once per transaction. Character counter measures the **stored HTML length** (what the backend limits), shown at ≥80 % of the limit and turning red above 100 % with the text "Too long — the save will be rejected".
- `Toolbar.tsx` — `role="toolbar"`, roving tabindex, `aria-pressed`, tooltips with shortcuts. Rich: Undo, Redo │ Block style select (Paragraph, Heading 2/3/4) │ Bold, Italic, Underline, Strike │ Bullet list, Numbered list, Quote, Divider │ Link, Remove link │ Clear formatting. Inline: Bold, Italic, Underline, Strike │ Link, Remove link │ Clear formatting. Sticky inside long fields.
- `LinkPopover.tsx` — anchored popover (no `window.prompt`): URL input, validation (http/https/mailto/tel/`/path`/`#anchor`; bare `example.com` → `https://example.com`; bare email → `mailto:`; phone → `tel:`), Enter applies, Esc cancels, edit/remove existing link. With an empty selection outside a link it inserts the URL itself as linked text.
- Paste (rich): rely on the TipTap schema. No Color/TextStyle/FontFamily/Highlight extensions are loaded, so colours, fonts, sizes and highlights from Word/Google Docs vanish, while style-based bold/italic (Google Docs `<span style="font-weight:700">`) is still recognised by the Bold/Italic parse rules. Paste (inline): `transformPastedHTML` converts the clipboard HTML to canonical inline HTML via the vendored kit (blocks become `<br>`), because an inline document can hold only one paragraph. Plain-text paste keeps line breaks.
- Styling: `prose prose-sm prose-zinc dark:prose-invert` content area, zinc dashboard tokens, visible focus ring, min heights (inline 1 line, rich 8 lines), resize by content.
- `ContentField.tsx` — dispatcher `{ format, value, onChange, … }` → `PlainInput` (existing input styling, `type` from repeater `url`) or `RichTextEditor`.

Editor integrations (only when `rich_text_version ≥ 1`; version 0 keeps today's inputs untouched):
- `TextBlockEditor` → title `inline`, body `rich`.
- `RepeaterEditor` → `FieldInput` routes `string`→plain, `inline`→inline, `richtext`→rich, `url`, `tags` unchanged. Items get **stable React keys that travel with the item** (the item's `_id`, else a client-generated key held in state next to the item — never the array index), because TipTap editors own their state: with index keys, "move up/down" or "remove" would leave the formatted text in place while the data moves.
- `KeyValueEditor` → value field uses `_formats[key]`; admins see a small format select per entry (Plain / Inline / Rich) that writes `_formats`; renaming a key moves its `_formats` entry; deleting drops it.
- `ImageEditor`, `FileDownloadEditor` unchanged (plain).
- Remove the "Markdown supported" hints when version ≥ 1.

`ServiceEditor` hardening (edge cases that hurt more once people write long formatted text):
- `beforeunload` guard while dirty.
- Locale switch and Re-translate ask for confirmation when dirty (today they discard silently).
- Save errors (422 too long / invalid structure) surface the backend `detail` in the error banner.

## 7. Client kit (`client-kit/rich-text/`, vendored into every site)

Zero runtime dependencies beyond React ≥18; framework-agnostic (Next App Router server + client components, Vite SPA, vite-react-ssg); deterministic output on server and client (no hydration mismatch).

- `src/parse.ts` — small tokenizer for the allow-list. Recognises only allow-listed tags (plus synonyms of 4.3); every other `<…>` sequence is text. Decodes `&amp; &lt; &gt; &quot; &#39; &apos; &nbsp;` and numeric entities; leaves unknown entities literal. Produces a node tree `{ type: 'text' | tag, children, href? }`. Enforces href rules of 4.3 (defence in depth even though the backend already sanitised). Never uses `dangerouslySetInnerHTML`, `DOMParser` or `innerHTML`.
- `src/normalize.ts` + `src/serialize.ts` — a TS port of the backend canonical transform (§4.3), so the kit renders exactly the structure the backend would store (no `<p>` inside `<p>` → no hydration errors, even for legacy or tampered data). Pinned to the backend by a second shared fixture, `fixtures/canonical-vectors.json`, asserted by both the Python `canonicalize` tests and the kit tests.
- `src/legacy.ts` — TS port of the legacy converter (same vectors as Python). Applied only to `rich` values without tags (§4.4 critical rule); `inline` values are always parsed as HTML fragments.
- `src/RichText.tsx` — `<RichText value format="rich"|"inline" as? className? headingOffset? linkTarget?: 'auto'|'self'|'blank' renderLink? />`. Renders semantic elements inside a wrapper with class `cms-rich` (+ `cms-rich--inline`, default `as` = `div` for rich, `span` for inline). `headingOffset` shifts h2..h4 (e.g. +1 inside cards) clamped to h6. Links: `auto` → external http(s) opens in a new tab with `rel="noopener noreferrer"`; internal paths render via `renderLink` when provided (Next `Link`, React Router `Link`). Empty value → renders nothing (`null`).
- `src/plainText.ts` — `plainText(value)`: tags stripped, entities decoded, `<br>`/block boundaries → single spaces (or `\n` with `{ keepLineBreaks: true }`), whitespace collapsed. For meta tags, JSON-LD, alt/aria, React keys, search, `tel:`/`mailto:` building, `Number()`.
- `src/splitRichWords.ts` — `splitRichWords(value)` → array of word tokens `{ key, node }` preserving marks (a bold word stays bold), for per-word animations (George's hero, Akris `FadeInText`). `RichWords` helper component with a render prop.
- `src/cms-rich.css` — base styles driven entirely by CSS custom properties with safe fallbacks (inherit/currentColor), so a site that sets nothing still looks correct:

  | Variable | Controls | Fallback |
  |---|---|---|
  | `--cms-rich-strong` / `--cms-rich-strong-weight` | bold colour / weight | `inherit` / `700` |
  | `--cms-rich-em` | italic colour | `inherit` |
  | `--cms-rich-underline` | underline colour | `currentColor` |
  | `--cms-rich-link` / `--cms-rich-link-hover` / `--cms-rich-link-decoration` | link colours, underline style | `currentColor` / `inherit` / `underline` |
  | `--cms-rich-heading` / `--cms-rich-heading-font` / `--cms-rich-heading-weight` | heading colour, font, weight | `inherit` / `inherit` / `700` |
  | `--cms-rich-marker` | bullet / number colour | `currentColor` |
  | `--cms-rich-quote-border` / `--cms-rich-quote-text` | blockquote | `currentColor` / `inherit` |
  | `--cms-rich-rule` | divider colour | `currentColor` (40 % opacity) |
  | `--cms-rich-gap` / `--cms-rich-list-indent` | block spacing, list indent | `0.75em` / `1.4em` |

  Empty paragraphs keep one line of height. Selectors are `.cms-rich <element>` (specificity 0,1,1), unlayered: this beats Tailwind preflight in v3 (unlayered, 0,0,1) and v4 (`@layer base`), which would otherwise strip list bullets and margins. The kit sets **no properties on the wrapper element itself**, so utility classes a site puts on `<RichText className=…>` always apply. Inner-element styling is changed through the variables (the contract), not by competing selectors.
- **Theme contract.** Each site defines the variables in its theme: on `:root` (light), on its dark-theme selector, and on every inverted/coloured surface (`.section-dark`, hero, footer…). Because they are CSS custom properties, the nearest surface wins automatically — this is the "colour handler": bold on a dark hero can be the accent colour while bold in a light card is the ink colour. Rule for choosing values: accent colours are used only when they reach WCAG AA (4.5:1) against that surface; otherwise the variable stays text-coloured and weight carries the emphasis.
- `scripts/sync-rich-text-kit.mjs <target-dir>` — copies `src/` into a site (e.g. `src/lib/cms-rich-text/`) with a header comment `// Vendored from CMS client-kit/rich-text vX.Y.Z — do not edit; re-sync instead.` and writes `VERSION`.
- `README.md` — install for Next (server/client), Vite, Tailwind v3/v4/plain CSS, samir-style next-intl (`t.raw` rule), theme recipe, field-usage rules (display → `<RichText>`, non-display → `plainText()`, per-word animation → `splitRichWords`).
- Tests (vitest + jsdom + Testing Library, `client-kit/rich-text/package.json`; `make install` runs its `npm ci`, and `make ci` runs it as `make test-kit`): parser allow-list, XSS vectors (event handlers, `javascript:`/`data:`/entity-obfuscated/whitespace-prefixed schemes, `<svg>`/`<img>`/`<script>`/`<style>`, nested and unclosed tags, attribute injection), entity decoding, legacy vectors, `plainText`, `splitRichWords`, SSR string equality (`renderToString` twice, identical), heading offset, link targets.

## 8. Migration of existing data (`backend/scripts/migrate_rich_text.py`)

`python scripts/migrate_rich_text.py --project <slug> --formats <config.json> [--apply]`

- `config.json` (per project, written during that site's migration after auditing its render sites): `{ "repeaters": { "<service_key>": { "<field_key>": "inline"|"richtext"|"string" } }, "key_values": { "<service_key>": { "<entry_key>": "plain"|"inline"|"rich" } } }`. Unlisted fields keep their current type/format (`string`/`plain`).
- For every service and **every locale row**: update `_schema` / `_formats` per config; convert all inline/rich leaves in `draft_content` **and** `published_content` (legacy → canonical HTML); leave plain leaves byte-identical.
- Recompute `translation_meta[path].src_hash` for manual overrides in non-default locales from the converted default-locale source, so manual translations don't all turn "stale".
- **Atomic.** The pure planner lives in `auth_service/services/rich_text_migration.py`; the CLI reads via the backend Supabase client and, with `--emit-sql`, writes **one `DO $$ … $$` block** that updates every row (`… where id = X and updated_at = Y; if not found then raise exception …`) and flips `projects.rich_text_version = 1` in the same transaction. It is applied with the Supabase MCP `execute_sql` (or `scripts/apply_supabase_migration.py`). Any concurrent edit aborts the whole block and nothing changes; re-run the planner and apply again. This matters because re-converting an already-migrated inline value would double-escape it — so a project is never left half-migrated.
- Dry run (default) prints a per-leaf before/after diff and counts. `--emit-sql` also writes a full JSON backup of every touched row. Both files go to `backend/scripts/.rich-text-work/` (gitignored — they contain client content).
- `--restore <backup.json> --emit-sql` writes an atomic block restoring those rows and setting the version back to 0.
- Idempotent: the planner refuses to plan a project whose `rich_text_version` is already 1 (prints "already migrated", exit 0).

## 9. Client-site rollout (per site, strictly in this order)

1. Vendor the kit (`sync-rich-text-kit.mjs`), import `cms-rich.css`, define the `--cms-rich-*` variables for light, dark and every inverted surface from the site's existing palette (contrast-checked).
2. Audit every CMS render site (list from the exploration report) and wire: display prose → `<RichText>`; non-display uses → `plainText()`; per-word animations → `splitRichWords`; titles used as keys → `plainText()`.
3. Write the project's `formats` config: which repeater `string` fields and key_value entries are prose (→ inline/rich) vs machine values (stay plain).
4. Build + lint; Playwright check locally against **legacy** data (version 0) — the site must render identically to production before the data changes.
5. Push to the site's preview branch (`cms-preview`), verify the preview deploy; then push the same commit to the production branch (`main`; `master` for Laurian) and verify production still renders identically. Safe because the kit renders legacy values exactly as before — production never runs code that can't render the data.
6. Run the migration dry run, review the diff, emit the atomic SQL and apply it (flips the project to version 1).
7. Verify local, preview and production with migrated data: formatted text renders with theme colours in light/dark, all locales, meta/JSON-LD plain, links/tel/mailto intact, no console/hydration errors, per-word animations intact. Then make a real formatted edit through the backend (bold + link + list), publish, verify, and restore.

Site-specific notes:
- **it-global-services**: replace `RichBody`; hero tagline accent split and Header/Footer/MobileMenu brand wordmark via `splitRichWords`/`plainText`; metadata via `plainText`; `contactFields.ts` keeps plain values.
- **samir-kapsalon**: CMS prose that flows through next-intl must be read with `t.raw()` and rendered with `<RichText>`; never `t()` on a rich/inline value (throws). Metadata via `plainText(t.raw(...))`. `cms-content.ts` passes rich values through untouched.
- **laurian-duma-portfolio**: Tailwind v3 always-dark palette → variables on `:root` only; bullets repeater may stay `tags`.
- **akris**: replace `react-markdown` usage with `<RichText>` (legacy Markdown still renders via the kit fallback until migrated); `FadeInText` via `splitRichWords`; remove the now-unused `react-markdown`/`remark-breaks` deps.
- **e2e-test-project**: migrate so the dashboard E2E specs exercise the rich editor; update `e2e/` selectors from `textarea` to the editor's `role="textbox"`.

## 10. Agent and skill updates

- **CMS Connector** (`agents/CMS Connector - Website/`): `prompts.py` + `phases/2-scan.md` + `AGENTS.md` glossary — field formats, repeater `inline` type, key_value `_formats`, classification rules (prose vs machine value), text_block title inline/body rich, Markdown/Portable Text sources convert to HTML; `scan.py` sends `_formats` on key_value seeds and preserves them like `_schema`; `phases/4-integration.md` §4.1.6 — vendor the kit, render rules, theme variables, samir-style `t.raw` rule; `phases/5-testing.md` 5i — probe with a bold+link+list value and assert `<strong>`/`<a>`/`<li>` render and no literal tags; `LEARNINGS.md` append (supersede the 2026-06-17 Markdown rule).
- **Website Builder** (`agents/Website Builder/`): `phases/3-scaffold.md` vendors the kit and defines the theme variables in `src/index.css` from design tokens; `phases/4-implement.md` render rules; `phases/8-verify.md` REQUIRE grep gates (`cms-rich`, `--cms-rich-strong`) and FAIL gates (`dangerouslySetInnerHTML` fed by CMS data, `react-markdown`); `learnings-template/frontend-patterns.md` §4 TextReveal uses `splitRichWords`; `learnings-template/conventions.md` + `LEARNINGS.md` entries.
- **Skills**: `vite-react-scaffolding` (tree + `lib/cms-rich-text/` + css import), `i18n-setup` (CMS rich values bypass interpolation; render with `<RichText>`), `design-handoff` (manifest `tokens.richText` slot: strong/em/link/marker/heading/quote per surface), `cms-connector-website` SKILL.md reference. Untracked skills are committed with `git add -f`.

## 11. Rollout order (whole system)

1. ADR + DB migration applied (additive).
2. Backend + dashboard + client kit on `feat/rich-text`, `make ci` green, merged to `dev`, preview verified with the e2e-test-project migrated.
3. Promote dev → main (manual workflow), production smoke.
4. Sites one at a time (§9): it-global-services → laurian-duma-portfolio → akris → samir-kapsalon (most complex last).
5. Agents + skills updated and committed.
6. Delete this spec and the plan once everything is live and stable (CLAUDE.md rule).

## 12. Error handling and edge cases (checklist)

- Unmigrated project (version 0): dashboard + backend behave exactly as today.
- Mixed legacy/HTML values during rollout: kit and dashboard detect and convert legacy text.
- Values containing `&`, `<`, `>`, quotes, emoji, RTL, `{placeholders}`, very long words: escaped correctly, round-trip stable, DeepL placeholder masking still applies inside HTML.
- Pasted Word/Google Docs/web content: styles, colours, fonts, spans, images, tables stripped; structure kept.
- Empty field / whitespace-only / only empty paragraphs → `""`; site renders nothing.
- Interior blank lines preserved (empty paragraphs) and rendered with height.
- Links: invalid or dangerous hrefs unwrapped; `mailto:`/`tel:` allowed; external links open in new tab on sites.
- Too long → 422 with field path; counter warns in the editor before that.
- Client cannot change `_schema`/`_formats`; admin can; invalid values → 422.
- Translation: tags preserved; output re-sanitised; manual overrides keep their hashes through migration; re-translate works per locale.
- Locale switch / navigation / tab close with unsaved rich edits → confirmation.
- Heading levels in cards (`headingOffset`) for accessibility; toolbar keyboard accessible.
- Hydration: kit output identical on server and client.
- Rollback: per-project `--restore` backup + version 0; kit keeps rendering either form.

## 13. Testing

- Backend pytest: canonicalisation (allow-list, synonyms, hrefs, idempotence, limits), legacy vectors, `format_of`, `normalize_content` per type, save path (version 0 untouched, version 1 normalised, structural protection admin vs client, 422s), `formats_of` html, sync re-sanitisation, content endpoints `rich_text_version`, migration script (dry run, apply, meta hash recompute, idempotence, restore, concurrency conflict).
- Frontend vitest: `serialize` (inline unwrap, empty docs, legacy load), `RichTextEditor` (toolbar toggles marks, Enter vs Shift+Enter per mode, link popover validation, paste stripping, counter), editor integrations per type at version 0 vs 1, ServiceEditor dirty guards.
- Client kit vitest as §7.
- Manual/Playwright: dashboard on dev preview (e2e-test-project) and each site's preview + production per §9.
- `make ci` green before every merge.
