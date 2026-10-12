# CMS Connector — Website Agent

Authoritative spec for **this agent only**. Each agent owns its own AGENTS.md.

> Skill entry: [`.claude/skills/cms-connector-website/SKILL.md`](../../.claude/skills/cms-connector-website/SKILL.md)
> Self-improvement log: [`LEARNINGS.md`](./LEARNINGS.md)
> Per-phase detail: [`phases/`](./phases/)

---

## Trigger

> "Run CMS - Connector Website agent for the project within folder `<folder_name>`"

Loaded from SKILL.md. See SKILL.md for first steps and token rules.

## Pipeline (strict order)

| # | Phase | Doc | Goal |
|---|-------|-----|------|
| 1 | GitHub repo | [phases/1-github.md](./phases/1-github.md) | New repo populated from `<folder_name>` |
| 2 | Scan + report | [phases/2-scan.md](./phases/2-scan.md) | Markdown integration report for human review |
| 3 | Review | [phases/3-review.md](./phases/3-review.md) | User approval gate (no disk writes) |
| 4 | Integration | [phases/4-integration.md](./phases/4-integration.md) | Provision CMS services, wire Resend, set up Vercel |
| 5 | Testing | [phases/5-testing.md](./phases/5-testing.md) | End-to-end test matrix passes, incl. **5i per-service content round-trip** (every service drives cms-preview/localhost on save + production on publish; revert restores) |
| 6 | Client onboarding + confirmation | [phases/6-confirmation.md](./phases/6-confirmation.md) | Create client account, transfer project ownership, send branded welcome email via Resend, delete temp files, print summary |

Each phase doc contains: goal, inputs, steps, outputs, failure messages, self-improvement hook.

## Required credentials

The two keys below live in `agents/CMS Connector - Website/.env` (copy
from `.env.example`, gitignored, auto-loaded by `scan.py`). GitHub and
Claude use your logged-in CLIs, so no key is stored for them.

| Tool | Credential | Used in |
|------|------------|---------|
| GitHub | `gh` CLI login (`GITHUB_TOKEN` in `.env` overrides it) | Phase 1, 4 |
| Anthropic Claude | `claude` CLI login (no API key) | Phase 2, 5 |
| Vercel | `VERCEL_TOKEN` | Phase 4 |
| CMS admin | `CMS_ADMIN_API_KEY` (cmsk_…) | Phase 4, 5, 6 |

### Backend-only credentials

These secrets live on the backend's Vercel env, NOT on the agent's
host. The agent reaches them indirectly through admin endpoints.

| Secret | Where | Why |
|--------|-------|-----|
| `RESEND_API_KEY` | backend Vercel env | welcome email send via `POST /admin/clients/{email}/welcome` |
| `SUPABASE_SERVICE_ROLE_KEY` | backend Vercel env | project create + ownership transfer via admin endpoints |

If a credential needed by a phase is missing, halt that phase and
surface a clear remediation. Do not silently skip.

## Failure-mode taxonomy

| Class | Action | Self-improve? |
|-------|--------|---------------|
| Transient (network, 5xx, rate-limit) | Retry up to 3× with backoff. Surface only after exhaustion. | No |
| Credential (401/403, missing env) | Halt, surface remediation. | Only if config drifts repeatedly |
| Logical (wrong service type, missed section) | Surface, ask user, fix, learn. | Always |
| Schema mismatch (CMS service shape changed) | Halt. Re-read backend before extending. | Always |
| User-induced (bad path, malformed input) | Re-prompt. | No |

## Hard rules — what is / isn't a CMS service

**Always include** (Phase 2 surfaces them as candidates):
- General section: display name, logo if `<folder_name>/public/` has one, and the `general_theme` service (palette, surfaces, fonts)
- Contact: email, phone, location, schedule (if business has hours)
- Domain-specific sections: about, hobbies, projects, experience (portfolio); menu (food/drink); about-us text; service catalogue (if business sells services — every per-service field must map to a repeater field)
- Every image, illustration and content icon (as image/icon fields, see "Theme, images and icons contract" below); UI-control icons stay in code

**Never include**:
- Button / CTA labels
- Navigation items
- Page-level routes / page metadata
- Hard-coded UI affordance copy ("Loading…", "Subscribe", form-field placeholders)
- Class names, design tokens, animation config, breakpoints (the palette and fonts go only into `general_theme`)
- The favicon and OG generator assets (they stay in code)
- Test fixtures, mock data
- The language-switcher control and its locale labels (chrome, not content) — but DO detect the locale set and import per-locale CONTENT as first-class CMS data

**Decision rule when ambiguous**: "would a non-developer client reasonably ask 'can I change this myself?'" → include. Else exclude.

These hard rules are **also enforced** in `prompts.py` SYSTEM_PROMPT. Keep both in sync.

## Branch standardization (Option A)

Two branches per client repo:

- **`<production_branch>`** — `main` for new repos (GitHub's default since 2020). Legacy repos with `master` are tolerated; we do not auto-rename. The resolved name is stored in `projects.production_branch`.
- **`cms-preview`** — long-lived preview branch; its Vercel preview (reading drafts) is what the dashboard's "See Preview" opens. Auto-created from `<production_branch>` in Phase 4 (`github.create_branch`) if missing. It is not updated automatically afterwards; refresh it with `git push origin <production_branch>:cms-preview`.

Policy:

- **New repos**: do not override GitHub's `default_branch`. Whatever the user's GitHub account default is (typically `main`), record it as `production_branch`.
- **Legacy repos** (`default_branch == "master"`): accept it. Do not propose renaming inside this agent — branch renames break external PRs, CI badges, and downstream service hooks.
- **Resolution order** in [`scan.py`](./scan.py) `_vercel_setup`: Vercel `productionBranch` first, then GitHub `default_branch`. This lets the operator override per-project via Vercel without changing the GitHub repo itself.

Phase 4 of this agent writes `production_branch` to the `projects` row; promoting `cms-preview` to production is a manual fast-forward to that branch (`git push origin cms-preview:<production_branch>`). If the value is `NULL` after a Connector run, check the Phase 4 PATCH log line `✓ Saved Vercel metadata to CMS project row (prod branch: <branch>)`.

## Generated client website contracts

When the agent stitches the client repo to the CMS (Phase 4 —
integration), the generated TypeScript code MUST treat all
`key_value` services as open records — never hardcode a fixed set of
keys. Concretely:

- The `key_value` selector returns `Record<string, string>` (legacy
  array shape `[{key, value}, ...]` is also tolerated and flattened
  client-side; the backend coalesces both shapes via
  `_normalise_published`).
- The contact section (and any other dynamic key-value renderer)
  iterates EVERY entry. Use a heuristic resolver — value shape
  (`@` → email; digits → phone), then key-family stems
  (`address`/`hour`/`program`/etc.), then a humanised-key fallback —
  to pick an icon, label, and click target per entry. Reference
  implementation: `it-global-services` repo at
  `src/lib/contactFields.ts` (`resolveContactCards`).
- The operator MUST be free to type any key in the CMS and see the
  field render with a sensible icon. No naming convention enforced
  on them.
- These heuristic contact icons are the one exception to "every content
  icon is a CMS icon field" (ADR-0011): a `key_value` service has no icon
  field, so its icons stay picked by the resolver.

This was a real bug: an early generated site (`it-global-services`)
hardcoded `phone | email | address | hours` as the only valid keys.
The operator typed `program` for opening hours; the website silently
dropped it. Future generated sites must follow the heuristic-resolver
pattern above so the same class of bug can't reappear.

### Field formats and rich text contract (ADR-0010)

Every text field has a format: `plain`, `inline` or `rich`. Repeater `item_schema` text types are `string`, `inline`, `richtext`, `url`, `tags` (plus the media types `image` and `icon`, below); `key_value` services carry a per-entry `formats` map (seeded as `_formats`); `text_block` title/body are always inline/rich. Stored values are canonical HTML, never Markdown. Generated sites MUST:

- vendor the kit from `client-kit/rich-text` (sync script) and import `cms-rich.css`;
- render CMS prose with `<RichText>` (never `react-markdown`, never `dangerouslySetInnerHTML`), and never place a rich value inside `<p>`;
- read next-intl-merged rich/inline values with `t.raw`, never `t()`;
- use `plainText()` for metadata, JSON-LD, `alt`/`aria-*`, keys and `href`/`tel:`/`mailto:` building;
- define `--cms-rich-*` on every surface and write `cms-rich-text.formats.json`.

A new site must ship the kit before its project's `rich_text_version` is 1. See [ADR-0010](../../docs/decisions/0010-rich-text-content.md) and the [kit README](../../client-kit/rich-text/README.md).

### Theme, images and icons contract (ADR-0011)

Every generated site is built on these five principles (the Website Builder, the Design Prompt creator and the skills carry the same wording):

1. **Every image and illustration is a CMS image field** (standalone `image` service or a repeater `image` field) with a `hint: {width, height}` matching the slot's rendered aspect at 2× density (e.g. full-width banner 1600×600, card 800×600, avatar 400×400). The design's artwork is uploaded as the seed value (or kept as the in-code fallback when it is an animated SVG component). Only the favicon/OG generator assets stay in code.
2. **Every content icon is a CMS icon field** (icons on services, features, items, contact methods and the like; `icon` repeater field, value `{src, mode, color, name}`) with `surface` set to the theme surface it sits on; rendered via the kit's `<CmsIcon>`; the design's icon (or a matching Lucide icon) is the seed; when empty, sites fall back to their designed icon. UI-control icons (menu, close, chevrons, arrows, spinners, form affordances) stay in code. Contact-method icons stay heuristic only where the contact service is `key_value` (see above).
3. **Every project gets a `general_theme` service** (`theme` type, page General) seeded from the design: palette colours (named), surfaces (page light/dark, card, header, footer), fonts (Google by default, weights actually used, italic only if used), `body_font`, `heading_font`. Sites render `<ThemeStyles theme>` in the root layout/head and use `var(--cms-font-body, <bundled default>)` / `var(--cms-font-heading, …)` for font tokens; the bundled default (`@fontsource` for Vite sites, `next/font` for Next sites) stays as fallback. Theme colours are recommendations; do not drive the site palette from them.
4. **Rich text may contain styled spans** (ADR-0011): sites render through the kit `<RichText>` (kit ≥ 1.1.0), never strip `style` themselves. Content may carry span colours/fonts/sizes chosen by the client; themes keep `--cms-rich-*` for marks; check AA contrast of the theme palette against its surfaces.
5. **Test matrix additions** (Phase 5 5i): swap an image in draft → preview shows the new URL; set an icon (Lucide pick) with a colour → preview shows a `.cms-icon` with that `background-color`; set `body_font` to a different Google font → computed `font-family` of `body` starts with it; save a title with a span colour → rendered span has that colour; empty image/icon → fallback renders, no layout gap.

Read the values with the kit (`readTheme`, `readIcon`; `googleFontsHref`/`fontStack`/`recommendIconColors` when a site needs them; see the kit README section "Theme, fonts and icons"). `hint`, `surface` and `_hint` are admin/agent-set structure: a client save never changes them. Themes, images and icons are never translated. Example pattern for Next sites: it-global-services (`src/app/[locale]/layout.tsx` ThemeStyles + `next/font` fallback, `src/app/globals.css` font tokens, `src/components/ui/ServiceCard.tsx` CmsIcon with an animated-scene fallback, `src/app/[locale]/services/[slug]/ServicePageContent.tsx` banner image, `src/lib/cms.ts` `theme()` accessor). See [ADR-0011](../../docs/decisions/0011-theme-styled-text-and-media-fields.md).

### Booking (headless) contract

When the manifest carries a `booking` block with `"detected": true`, Phase 4 provisions the booking service and generates `lib/booking.ts` in the client repo. The following contract is binding for all generated client websites:

- **API base**: `BOOKING_API_BASE` is set to the **bare backend base** (e.g. `https://cms-backend-roman.vercel.app`). `lib/booking.ts` appends `/booking/{slug}` itself — the env var must NOT include the path.
- **Generated functions** (exported from `lib/booking.ts`):
  - `getServices()` — `GET {BASE}/booking/{slug}/services`
  - `getAvailability(serviceId, from, to)` — `GET {BASE}/booking/{slug}/availability?service_id=&from=&to=`
  - `createBooking(payload)` — `POST {BASE}/booking/{slug}` — always includes `website: ""` honeypot field.
  - `getManage(token)` — `GET {BASE}/booking/manage/{token}`
  - `reschedule(token, slot_start)` — `POST {BASE}/booking/manage/{token}/reschedule`
  - `cancel(token)` — `POST {BASE}/booking/manage/{token}/cancel`
- **Honeypot**: `website: ""` is included in every `createBooking` call. The client UI must pass it silently; the backend rejects non-empty values as spam.
- **Destination email**: booking confirmation and reminder emails go to the address in `destination_email`. If Stefan provides a client email, that address is used; otherwise it defaults to `stefanromanpers@gmail.com`.
- **Manage flow**: reschedule and cancel are centralised on the CMS-hosted `/manage/{token}` page. Client sites link there; they do not implement manage UI themselves.
- **Logo / asset URLs**: locale-invariant — booking emails use the same logo URL regardless of the active locale; do not duplicate per locale.
- **Provisioning order** (Phase 4 sub-steps, strictly): enable → settings → resources → services (each linked to ≥1 resource) → hours. Deviating from this order leaves availability empty.
- **Include/exclude alignment with `prompts.py`**: scheduling intent → `booking` block; plain contact form with no scheduling intent → `email_config` service only. These are mutually exclusive. Keep this rule in sync with the `prompts.py` SYSTEM_PROMPT detection block.

### Multilingual fetch contract

For multilingual sites (manifest `locales` has >1 entry):
- The site fetches **per-locale** content: `GET {base}/content/{slug}/{locale}` where `locale` comes from the active Next.js / next-intl locale context.
- The `key_value` / `Record<string,string>` contract is **unchanged per locale** — each locale's content is its own flat `Record<string,string>` (or array shape coalesced client-side). No nested locale maps at the JS layer.
- Locale-invariant assets (logo, file download URLs) are marked `translatable:false` in the manifest; the site fetches them from the default-locale response regardless of active locale.
- Legacy `GET {base}/content/{slug}` (no locale segment) still returns default-locale content and must remain supported for back-compat (single-locale sites and CMS preview thumbnails).

**Vite + React 19 sites (react-i18next):** the active locale comes from `i18n.language` (react-i18next) and the URL `/:locale` segment — NOT the next-intl server context. The per-locale `GET {base}/content/{slug}/{locale}` fetch + flat `Record<string,string>` contract is otherwise **UNCHANGED**. Supported locales and the default locale are declared in `src/lib/config.ts` (`SUPPORTED_LOCALES`, `DEFAULT_LOCALE`); seed messages live at `src/i18n/messages/<locale>.json`. Keep the Next.js / next-intl wording above for legacy sites.

## Glossary

- **Field format** — `plain` | `inline` | `rich`. Repeater types: `string`=plain, `inline`, `richtext`; `key_value` per-entry via `formats`/`_formats`; seeds carry canonical HTML for inline/rich (ADR-0010).
- **Media field** — repeater `image` (https URL or `""`) and `icon` (`{src, mode: "tint"|"original", color: ""|"#rrggbb", name}` or null) fields; may carry `hint: {width, height}` (ints 16–8000) and, on icons, `surface`. A standalone `image` service carries the same hint as `_hint` (ADR-0011).
- **Service** — CMS content unit. Types the connector emits: `text_block`, `image`, `gallery`, `video`, `file_download`, `key_value`, `email_config`, `repeater`, `theme` (the full catalogue lives in code: `backend/auth_service/services/service_types.py` `SERVICE_TYPES`; there is no service-types admin page or endpoint). For multilingual sites, each translatable service carries per-locale `initial_content` maps; locale-invariant assets (logo, file URLs, the theme) are marked `translatable:false`.
- **Theme service** — `theme` type, key `general_theme`, page General, at most one per project: `{colors:[{name,value}], surfaces:[{name,value}], fonts:[…], body_font, heading_font}`. Created with `POST /projects/{slug}/services` (`service_type_slug: "theme"`, seeds an empty theme), filled with `PUT /projects/{slug}/services/general_theme` (always the default locale).
- **Manifest** — JSON the agent emits. Slim variant `cms.config.json` (in client repo; records each service's `type`/`page`, plus `media` for repeater image/icon fields and `hint` for image services), full variant `cms-provision.json` (admin keeps). For multilingual sites, the manifest carries top-level `locales` (array, e.g. `["en","nl"]`) and `default_locale` (string), plus per-locale `initial_content` maps inside each service. Single-locale manifests stay flat (no per-locale nesting). The manifest may also carry an optional top-level `booking` block (see below).
- **Booking service** — headless booking backend where one tenant equals one CMS project. The tenant is addressed by its `public_slug` (same slug as the CMS project). The booking service owns its own DB tables for resources, services, hours, and bookings; the CMS connector provisions them via admin endpoints during Phase 4.
- **Manifest `booking` block** — optional top-level block in the manifest (parallel to `locales`). When present it signals that the site has scheduling intent and describes how to provision the booking service. Fields: `detected`, `public_slug`, `business_name`, `accent_color`, `primary_color`, `logo_url`, `locale`, `timezone`, `destination_email`, `reminders`, `services` (list with `duration_min`), `resources` (list with `type`), `hours` (list with weekday 0=Sun..6=Sat and local `start_time`/`end_time`), and `ui_wiring` (`components` + `fallback_embed`). A plain contact form with no scheduling intent does NOT get a `booking` block — it stays on the `email_config` path.
- **Preview token** — opaque string in `NEXT_PUBLIC_CMS_PREVIEW_TOKEN` (Next.js) or `VITE_CMS_PREVIEW_TOKEN` (Vite) authenticating draft-content reads via header `X-CMS-Preview-Token`.
- **`folder_name`** — directory containing client website source.
- **`<folder_name>/public/`** — static assets, where the logo lives.

## Modifying this agent

If you change Phase 2 hard rules: update `prompts.py` SYSTEM_PROMPT to match.
If you change Phase 4 sub-steps: update the reference implementations in `scan.py` (`_provision`, `_vercel_setup`).
If you change failure messages: update the corresponding phase doc and any tests in `tests/`.
LEARNINGS.md is append-only; never edit existing rules.
