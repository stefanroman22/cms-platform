# ADR-0013: Display options (toggle, select and colour fields, and the options service)

Status: Accepted
Date: 2026-11-11

## Context

Clients ask for changes that are about how a page is laid out, not what it says: a different page
background, wider text, an image above the text instead of beside it, a title switched off, another
arrangement of the contact page. Until now each of these was a code change in one client's site, so
no other client got the same choice and the client could not change their mind without a developer.
A free-form "custom CSS" field would let content break the design, which ADR-0010 and ADR-0011
avoided. The choice has to stay narrow: the site declares which knobs exist and which values each
one takes, and the client only picks among them.

## Decision

- **Three option field types.** Field definitions (`_schema` entries) gain `toggle`, `select` and
  `color`:
  - `toggle`: value `true` / `false`. Definition may carry `default: boolean`.
  - `select`: value is one of the definition's `options: [{value, label}]` (2 to 24 options, `value`
    matching `^[a-z0-9][a-z0-9_-]{0,39}$` and unique, `label` 1 to 80 characters), or `""` for
    "not chosen". Definition may carry `default` (one of the option values).
  - `color`: value `""` (none) or `#rrggbb` lowercase (`#rgb` and uppercase input is converted).
    Definition may carry `default` (`""` or a hex colour).
  `options` and `default` are structural metadata like `hint` and `surface` (ADR-0011): admin/agent
  set, preserved on a client save, allowed only on these three types. Option values are never
  translated.
- **In repeaters.** The three types are valid repeater field types, so one item can carry its own
  switch or choice (for example "show the title on this service's page"). Values are validated on
  every save; an item that lacks the key is left alone and the site uses its default.
- **Options service.** A new service type `options` (dashboard name "Display Options") holds one
  set of values for a page or section: `{_schema: [field definitions], values: {key: value}}`. Its
  `_schema` may only use the three option types (1 to 40 fields, keys `^[a-z0-9_]{1,40}$`, unique).
  `services/content_structure.py` rebuilds `values` on every save from the schema keys only: a valid
  value is kept, a missing one becomes the field's `default` (else `false` / `""`), an invalid one
  is a 422, unknown keys are dropped. Like the theme, an options service is never translated: every
  save goes through the default locale. It goes through draft/publish and preview like all content
  (ADR-0005) and reaches sites in the existing public manifest (additive, ADR-0006). A project may
  have any number of options services; the convention is one per page, keyed `<page>_page_options`.
- **Sites decide what an option means.** The kit's `readOptions(raw, defaults)` returns a value only
  when the service's `_schema` declares the key with the matching type and the stored value is valid
  for it; otherwise the site's own default. Sites map each value to their own classes and CSS
  variables. A stored colour is the only client-chosen value that reaches CSS, and it is always a
  validated `#rrggbb`.
- **Conventions for generated sites.** Every page gets a `<page>_page_options` service with at
  least `background` (colour) and `content_width` (select). A layout the design can show in more
  than one arrangement is a `select`; a part that can be left out is a `toggle`. The site's default
  for every option is the designed look, so a site with no options service renders as designed. A
  custom colour applies to the light theme only when the site has a derived dark theme, and text on
  it must stay readable (the kit's `inkOn` picks a readable text colour).

## Consequences

- Clients change layout, widths, backgrounds and optional parts themselves, with preview and
  publish, and every client site can offer the same kinds of choice.
- Each option is a branch the site must design and test; keep the set per page small.
- Existing sites keep working unchanged; a site adopts the feature by re-syncing the kit (`1.3.0`+)
  and reading the options it declares.
- Do NOT: add a free-text, number or CSS field type to options; let a client save change
  `options` or `default`; translate option values; put content (text, images) in an options
  service; apply a stored value to CSS without the kit's readers.
