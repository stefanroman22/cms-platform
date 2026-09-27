# ADR-0008: Each language is its own content row, machine-translated on save

Status: Accepted
Date: 2026-09-27

## Context

Client sites are multilingual (e.g. EN/NL/RO). Clients write content in one language and rarely
translate by hand, but when they do fix a translation, that fix must survive later edits to the
source text. Client sites also need a complete response in every language even if some fields
were never translated.

## Decision

- Projects declare `default_locale` and `locales`. `content_entries` has one row per
  (service, locale). The one-row-per-service uniqueness was replaced by per-(service, locale)
  uniqueness in `migrations/2026_06_05_content_locale.sql`.
- Saving in the default locale machine-translates the translatable leaves into the other locales.
  `services/segments.py` decides which leaves are translatable: URLs, emails, numbers and image
  sources are never translated. The translation provider is DeepL when
  `TRANSLATION_PROVIDER=deepl`, else a no-op (`translation/`).
- A human edit in a non-default locale becomes a manual override, anchored to a hash of its source
  text. The dashboard shows each leaf as `auto`, `manual`, or `stale` when the source has changed
  since the override (`routers/workspace.py`, `_translation_status`).
- Reads fall back to the default-locale row (`services/content_locale.py`, `pick_locale_entry`)
  and fill missing leaves from the default locale.

## Consequences

- Clients maintain one language, the others follow automatically, and manual fixes are not
  overwritten.
- The content model is more complex: every content read or write must be locale-aware, and seed
  or import code must write per-locale rows.
- Without DeepL configured, non-default locales just echo the source text.
- Do NOT: collapse locales back into one row or one JSON blob, translate URLs, emails or other
  non-text leaves, or let an auto-translate run overwrite leaves marked `manual`. A repeater's
  `_schema` inside its content must never be overwritten by seeding.
