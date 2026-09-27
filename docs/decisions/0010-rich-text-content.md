# ADR-0010: Rich text is canonical HTML, gated per project

Status: Accepted
Date: 2026-09-27

## Context

`text_block.body` and repeater `richtext` fields have been Markdown by convention only — 27
repeater fields and several `text_block` bodies already use `**bold**`/`##`/etc, with no schema
enforcing it. DeepL translates that Markdown as plain text (`formats_of` sends `"markdown"`, no
tag handling), so `*`/`_`/`#` markers get mangled or split across sentences. `ContentSaveRequest.content`
is an unvalidated dict and nothing sanitises it server-side, even though ADR-0002 makes the backend
the only writer and therefore the security boundary. None of the four live client sites renders
HTML or has a sanitizer — they read plain/Markdown strings via next-intl, `useCMSContent()` or
`react-markdown`. ADR-0006 treats the public `/content` payload as a contract with repos we don't
see, so any change to what a text leaf contains must be additive and versioned, not a silent
format flip.

## Decision

- Every text leaf has one of three formats: `plain` (raw string, no HTML semantics), `inline`
  (an HTML fragment restricted to `strong em u s a br`, no block tags — used for titles/headings),
  or `rich` (a block-level HTML document restricted to `p br strong em u s a ul ol li h2 h3 h4
  blockquote hr` — used for bodies/descriptions). The only attribute ever stored is `a[href]`; no
  `class`, `style`, `id`, `target` or `rel`. Colour, font and size cannot be represented, by
  construction — each site's theme decides how formatting looks.
- `services/rich_text.py` is the single source of truth for canonical HTML: it resolves the format
  of every leaf (`format_of`), converts legacy plain/Markdown values once (`legacy_to_html`), and
  produces the allow-listed, synonym-mapped, length-limited canonical form (`canonicalize`). No
  other backend code parses, sanitises or serialises rich content.
- **`projects.rich_text_version`** gates the whole behaviour per project: `0` is today's
  behaviour everywhere (no normalisation, no sanitisation, legacy `markdown`/`text` translation
  formats); `1` turns on canonical HTML, sanitisation and `fmt="html"` translation. Existing
  projects start at `0`; the column's default flips to `1` immediately after, so every project
  created afterwards is rich-text-enabled from the start. A project only moves from `0` to `1`
  through the one-time migration script (`backend/scripts/migrate_rich_text.py`), after its site
  ships the client kit.
- `_schema` (repeater) and `_formats` (key_value) are structural metadata, not content: they
  declare each field's format and are set by admins or agents, not by an ordinary save.
- The `client-kit/rich-text/` package (parser, canonical-transform port, legacy-converter port,
  `<RichText>`, `plainText()`, `splitRichWords()`) is vendored into every site and is the only
  approved way to render or flatten stored HTML. Its `cms-rich.css` exposes the formatting purely
  through the `--cms-rich-*` CSS custom properties (bold/italic/underline/link/heading/list-marker/
  quote/divider colours and weights); a site defines those per surface (light, dark, inverted) and
  the kit itself sets no colour, font or size.
- Translation calls the provider with `fmt="html"` (DeepL `tag_handling=html`) once
  `rich_text_version ≥ 1`, and every translated inline/rich leaf is re-canonicalised afterwards,
  because DeepL can emit markup outside the allow-list.
- Migrating a project's existing data is one atomic, all-or-nothing SQL block
  (`migrate_rich_text.py --emit-sql`) that converts every stored leaf and flips
  `rich_text_version` to `1` in the same transaction; a concurrent edit aborts the whole block
  instead of leaving a project half-migrated.

## Consequences

- Formatting round-trips through save, publish, translation and every site's render without a
  client site ever seeing Markdown, literal tags or unescaped entities.
- The rollout is incremental and reversible per project: a project stuck at version 0 behaves
  exactly as before, and the migration script can restore a project to version 0 from its backup.
- Every future prose field must declare a format up front (`inline` or `rich`) instead of being
  free-form Markdown by convention.
- Do NOT: store any attribute other than `a[href]`; add colour, font or size marks to the allow-list
  or the editor; render CMS-produced HTML on a client site with `dangerouslySetInnerHTML` — always
  go through the client kit's `<RichText>`; run the legacy plain/Markdown-to-HTML conversion
  anywhere outside the one-time migration; flip a project's `rich_text_version` to `1` before its
  site has shipped the client kit; or let a non-admin save change `_schema`/`_formats` — those are
  structural metadata, always preserved on a non-admin save.
