---
name: lead-to-design-prompt
description: Transforms a structured small-business lead record into one comprehensive XML-tagged website design prompt for Claude Design or Claude Code with the frontend-design skill. Use whenever a user provides lead data (business_name, category, location, contact, ratings, hours, design_prompt) for an SMB and asks to generate a website, design prompt, design brief, design system, or page designs — even if they don't explicitly say "use the skill". Covers restaurants, cafes, hair/beauty salons, wedding venues, retail boutiques, and professional services. Output is one self-contained, category-matched, anti-AI-slop prompt per lead, including a complete design system (color/typography/spacing/motion/radius/shadow tokens), page architecture, component inventory (with 21st.dev hooks), copy seeds, and imagery direction. Trigger on phrases like "create a design prompt", "generate a website for this lead", "design system for [business]", or any time a JSON of lead fields is pasted.
license: MIT
---

# Lead → Design Prompt

This skill turns a structured lead record (the kind produced by a Google Maps / KvK scraping pipeline) into **one comprehensive design prompt** ready to paste into Claude Design (claude.ai/design) or into Claude Code with the `frontend-design` and `web-artifacts-builder` skills loaded.

The output is a single XML-tagged Markdown prompt covering: brand identity, aesthetic direction, complete design tokens (shadcn/OKLCH semantic pairs), page architecture, component inventory, copy seeds, imagery direction, deliverables, anti-patterns, and the lead's hand-written brief as a top-priority override.

**Critical goal:** the resulting website must NOT look AI-generated. It must look modern, distinctive, category-appropriate, and humanly authored.

---

## Inputs

The user provides a lead record. Any field may be `null` or missing. The skill must handle gracefully.

| Field | Required | Use |
|---|---|---|
| `business_name` | yes | Brand identity, hero, footer |
| `category` | yes | Drives the entire aesthetic archetype, page list, component choices |
| `description` | no | Hero subtitle, meta description (strip placeholders like "Not found") |
| `about` | no | About section seed copy |
| `design_prompt` | no | **Owner-written brief — highest priority, goes in `<user_override>` verbatim** |
| `country`, `region`, `city`, `address`, `postal_code` | partial | Location section, footer, schema.org LocalBusiness markup, locale fallback when `languages` is empty |
| `languages` | no | **Target website locales** (`text[]`, canonical English names e.g. Dutch, English). Drives `<languages>` and the language-switcher requirement. Empty = single-language site (locale primary), no switcher |
| `lat`, `lng` | no | Map widget (only embed if BOTH non-null) |
| `phone`, `email` | no | Header CTA, contact section; wrap as `tel:` / `mailto:` |
| `website_url` | no | If present and `web_presence=has_website`, flag to scrape for legacy tone |
| `facebook_url`, `instagram_url` | no | Footer social icons; Instagram embed if present |
| `social_links` | no | `{facebook,instagram,tiktok,linkedin,youtube,x,pinterest,whatsapp}` → url. Source of truth for footer social icons; `facebook_url`/`instagram_url` are mirrors of two keys |
| `business_status` | no | `CLOSED_TEMPORARILY`/`CLOSED_PERMANENTLY` → add a status banner requirement; `FUTURE_OPENING` → "opening soon" hero framing |
| `primary_type`, `types` | no | Google place types (`barber_shop`, `hair_salon`…); use alongside `category` for bucket classification (step 2) |
| `price_level` | no | `free`…`very_expensive` → price-positioning copy ("affordable", "premium"); never print the raw enum |
| `extra.google.photos[]` | no | `{url, owner_photo, attributions[{name,uri}], google_maps_uri}`. **`owner_photo=true` → usable site imagery (list in `<imagery>` as real assets). `owner_photo=false` → visual reference for art direction only; never instruct the site to embed them** |
| `extra.google.generative_summary` | no | `{overview, disclosure}` — Google's AI summary. Research input for tone/positioning only; **never quote it as the business's own words** and never include `disclosure` in site copy |
| `extra.google.review_summary`, `extra.google.editorial_summary` | no | Same rule as above; `editorial_summary` already feeds `about` |
| `extra.google.price_range`, `extra.google.opening_hours.secondary` | no | Price range for menu/pricing section hints; secondary hours (e.g. delivery) → optional hours sub-widget |
| `menu_url` | no | "View menu" button — food businesses only |
| `web_presence` | no | `none`/`social_only`/`has_website`/`unknown` — sets framing (`has_website` = the old "ok/outdated" case) |
| `source_url` | no | Google Maps URL for additional photo sourcing |
| `rating`, `review_count` | no | Trust band (`"5.0 ★ · 629 reviews"`); only include if `review_count >= 5` |
| `reviews` | no | Array of `{author, text, relative_date, rating}` — pick top 3–5 by rating × length, trim names ("Maria K."), strip emoji-only |
| `opening_hours` | no | Hours widget + schema.org `OpeningHours`; format Mon→Sun explicitly |
| `extra.attributes` | no | Google Maps "About" — `{section: {attribute: bool}}`; `true` becomes checkmark line, `false` dropped |
| `notes` | no | **Owner/admin special request.** If non-empty, honor it (ranks below `design_prompt`, above playbook/defaults) and place in `<internal_notes>`. If empty, add nothing extra |

---

## Workflow

Follow these steps in order. Do not skip the quality gate.

### 1. Normalize and validate the lead

- Strip placeholder strings (`"Not found"`, `"N/A"`, `"-"`, empty strings) → treat as `null`.
- Expand `country` ISO codes (`"NL"` → "Netherlands", `"BE"` → "Belgium", `"DE"` → "Germany").
- Resolve the **locale set** (drives `<languages>` and the language switcher):
  - If the lead's `languages` field is non-empty → use it verbatim as the site's locales. Primary = the first entry (list the local/country language first when it's present); the rest are secondary.
  - If `languages` is empty → a **single-language** site in the locale's primary language (`NL` → Dutch; `BE` → Dutch; `DE` → German; else English). No switcher.
  - **Multilingual rule:** if the resolved set has ≥ 2 locales, a language switcher is mandatory (step 7b). With exactly 1 locale, never add one.
- If `lat` or `lng` is null, drop the map embed entirely (no half-map).
- Sanitize HTML in `design_prompt` → plain Markdown.
- If `rating < 4.0` OR `review_count < 5`, **suppress** the trust-band section (don't lead with weak social proof).
- `web_presence` values are `none`, `social_only`, `has_website`, `unknown` (the DB enum). Treat `has_website` as the old "ok/outdated" case: if `website_url` is set, flag it for a legacy-tone scrape.
- Build the imagery input from `extra.google.photos`: `owner_photos = [p.url for p in photos if p.owner_photo]`, `reference_photos = the rest`. Fall back to `photo_urls` as reference-only when `extra.google.photos` is absent (pre-ADR-0012 leads).

### 2. Classify into a category bucket

Map the raw `category` string to exactly ONE of:

- `restaurant` — restaurant, bistro, trattoria, brasserie, gastropub, steakhouse, pizzeria, sushi, ramen, fine dining
- `cafe` — cafe, coffee shop, bakery, patisserie, tea house, juice bar, brunch spot
- `salon` — hair salon, barber, beauty salon, nail studio, spa, brow bar, lash studio
- `venue` — wedding venue, event space, banquet hall, conference centre, ceremony location
- `retail` — boutique, clothing store, gift shop, concept store, florist, jewellery
- `service` — fallback for consultants, accountants, agencies, trades, fitness studios, anything else

If ambiguous, infer from `description` and `extra.attributes` (e.g., "Dine-in: true" → restaurant; "Wheelchair accessible" + "Hair styling: true" → salon).

### 3. Load the category playbook

Read `references/category-<bucket>.md`. Each playbook defines: required pages, allowed aesthetic archetypes, color palette guidance, typography pairings, reference brands, category-specific anti-patterns, and recommended 21st.dev components.

**Do not improvise pages outside the playbook's required list.** A salon site does not get a "blog" section unless the lead's `design_prompt` asks for one.

### 4. Choose ONE aesthetic archetype

Pick exactly one direction from the playbook's allowed list. **Never default to "modern minimal"** — that's the AI-slop attractor.

Override rule: if `design_prompt` specifies a direction ("we want it to feel like a Tokyo izakaya", "make it feel like Aesop"), that supersedes the playbook's default.

Randomization rule: across consecutive runs in the same category, vary the archetype. If the last 2 restaurants both got "editorial-magazine", switch to "warm-photographic" or "industrial-utilitarian" unless the lead clearly demands otherwise.

### 5. Resolve design tokens

Use `references/design-tokens-cheatsheet.md` to build a complete token set in shadcn/OKLCH semantic-pair format. All eight families are mandatory:

1. **Color** — semantic pairs (`--background`/`--foreground`, `--primary`/`--primary-foreground`, etc.) in OKLCH; bound to the archetype's mood
2. **Typography** — display font + body font + optional mono; **never** Inter, Roboto, Arial, Open Sans, Lato, Space Grotesk, or system-ui as the primary type
3. **Spacing** — 4/8 base scale documented as a list
4. **Radius** — base value + derived sm/md/lg/xl
5. **Shadow** — 5 elevation levels in OKLCH alpha
6. **Motion** — fast/base/slow/page durations + standard/emphasized easings
7. **Breakpoints** — sm 640 / md 768 / lg 1024 / xl 1280 / 2xl 1536
8. **Dark mode** — required for cafes, salons, professional services; optional for venues; off by default for traditional restaurants unless the archetype calls for it

These tokens also seed the client's CMS theme (ADR-0011), so fill `<cms_theme_palette>` with the named palette colours and named surfaces (page light/dark, card, header, footer) in hex, and give each font its source (Google Fonts by default), only the weights actually used, and italic only if used. Theme colours are recommendations for the client; they do not replace the site palette.

### 6. Plan page architecture

Use the page list from the category playbook. Order matters. For each page, specify the section sequence (e.g., Home: hero → social-proof → featured-menu → about-strip → testimonials → location → footer).

### 7. Build component inventory

Map every section to either a **custom design** or a **21st.dev component reference**. Use `references/21st-dev-component-map.md` for the mapping. Format inventory lines like:

```
Hero (Home): full-bleed photography, asymmetric typography overlay — custom
Testimonials: 3 cards, large pull-quote, author + role — 21st.dev `/ui testimonial carousel editorial`
Footer: address block, hours table, social, newsletter — 21st.dev `/ui editorial footer with address and hours`
```

### 7b. Language switcher (multilingual only)

If the resolved locale set has ≥ 2 languages, the component inventory MUST include a **language switcher**:

- Sits in the primary navigation and is present + reachable at **every breakpoint** — desktop, laptop, tablet, and mobile (including inside the mobile menu/drawer).
- Styled from the design tokens (typography, `--accent`, `--radius`, `--motion-*`) so it matches the site chrome — never a browser-default `<select>`.
- Switches locale via the `[locale]` route segment, marks the active language, and keeps the user on the same page in the new language.

If the set has exactly 1 language, do NOT add a switcher.

### 8. Seed copy

Write placeholder headlines, subheads, About paragraph, primary CTA — in the brand's voice (extrapolated from `description`/`about`/reviews). **Never invent facts** — no fake chef names, awards, founding dates, or customer counts. Use the lead's reviews to find real adjectives reviewers used.

### 9. Imagery direction

Specify photographic style notes, sourcing guidance, and image-treatment direction (e.g., for restaurants: "dark moody overhead shots on linen, natural-light close-ups of plated dishes, no stock photography, no people in chef coats holding food"). If `source_url` (Google Maps) is present, note it as the seed image source.

Every image and illustration becomes a client-replaceable CMS image field and every content icon (on services, features, items, contact methods and the like) a recolourable CMS icon field (ADR-0011). Fill `<image_slots>` with one line per slot (page/section, subject + art direction, pixel size at 2× the rendered slot, e.g. banner 1600×600, card 800×600, avatar 400×400) and `<icons>` with one consistent icon set and the surface each content icon sits on. Only the favicon, OG images and UI-control icons (menu, close, chevrons, arrows, spinners, form affordances) are fixed.

### 10. Lock the anti-patterns block

Embed the full content of `references/ai-slop-anti-patterns.md` **verbatim** in the prompt's `<anti_patterns>` section. Add any category-specific bans from the playbook.

### 11. Assemble the final prompt

Use `references/prompt-skeleton.xml.md` as the template. Fill in every block. Place the lead's `design_prompt` field **verbatim** inside the final `<user_override priority="highest">` tag. If `notes` is non-empty, append it inside `<internal_notes>` after `<user_override>`.

### 11b. Emit `<universal_ux_requirements>` literally

The `<universal_ux_requirements>` block (intro loader, themed scrollbar, page transitions) is **category-agnostic** and **literal**. Copy it byte-for-byte from `references/prompt-skeleton.xml.md` into the output — do NOT paraphrase, summarize, or tailor it to the lead. The only contextual link is that its body references the design tokens declared in `<design_system>` above (`--accent`, `--background`, `--muted`, `--motion-page`, etc.), so those token names must exist. Every site this skill produces ships these three behaviours; the block is the contract that guarantees it.

### 12. Quality gate (run BEFORE emitting)

Tick every box. If any fails, fix and re-check. Do not emit a partial prompt.

- [ ] Category bucket assigned and matches the playbook
- [ ] Exactly one aesthetic archetype chosen (not a mix)
- [ ] At least 2 reference brands named (from `references/reference-brands-by-category.md`)
- [ ] All 8 design-token families present
- [ ] `<cms_theme_palette>` names the palette and surfaces; each font has source, used weights and italic
- [ ] `<image_slots>` lists every image slot with a pixel size; `<icons>` names one icon set; deliverable 16 is present
- [ ] No banned font (Inter, Roboto, Arial, Open Sans, Lato, Space Grotesk, system-ui as primary)
- [ ] No purple/indigo gradient unless lead explicitly requested it
- [ ] Every required page from the playbook is present
- [ ] Each page has an ordered section list
- [ ] Component inventory covers every section
- [ ] `<user_override>` contains the lead's `design_prompt` verbatim (or is empty if null)
- [ ] `<anti_patterns>` contains the full anti-slop block
- [ ] `<universal_ux_requirements>` is present and emitted literally from the skeleton (contains `<intro_loader>`, `<themed_scrollbar>`, `<page_transitions>`)
- [ ] `<deliverables>` item 13 (global UX chrome: `IntroLoader`, themed scrollbar, `PageTransition`) is present
- [ ] `<instructions>` mentions implementing `<universal_ux_requirements>` exactly as written
- [ ] Schema.org LocalBusiness/Restaurant/HairSalon/EventVenue JSON-LD is in `<deliverables>`
- [ ] WCAG 2.2 AA + mobile-first noted in `<deliverables>`
- [ ] If `lat`/`lng` is null, no map embed referenced
- [ ] `<languages>` reflects the resolved locale set (explicit `languages` field if set, else the locale primary); `switcher` attribute set correctly
- [ ] If ≥ 2 locales: a language switcher is in `<component_inventory>` AND `<deliverables>`, placed in the nav at every breakpoint, theme-matched, and wired to `[locale]` routing
- [ ] If 1 locale: no language switcher anywhere
- [ ] `notes`: if non-empty, reflected in `<internal_notes>` and honored; if empty, nothing extra added

### 13. Emit

Output ONE Markdown response containing:

1. A 2–3 line preamble ("Design prompt for [business] — paste this into claude.ai/design …")
2. The full prompt inside a single fenced code block with language `xml`
3. A 3-line "Next steps" footer telling the user how to iterate (commenting in claude.ai/design vs regenerating)

Do not add commentary inside the prompt. Do not summarize the prompt. The user copies the code block as-is.

---

## Reference files

Read these on demand. Do not load them all upfront.

| File | When to read |
|---|---|
| `references/prompt-skeleton.xml.md` | Always — this is the output template |
| `references/category-restaurants.md` | If category bucket = `restaurant` |
| `references/category-cafes.md` | If category bucket = `cafe` |
| `references/category-salons.md` | If category bucket = `salon` |
| `references/category-venues.md` | If category bucket = `venue` |
| `references/category-retail.md` | If category bucket = `retail` |
| `references/category-services.md` | If category bucket = `service` (fallback) |
| `references/design-tokens-cheatsheet.md` | Always — for the `<design_system>` block |
| `references/ai-slop-anti-patterns.md` | Always — embedded verbatim in every output |
| `references/21st-dev-component-map.md` | Always — for the `<component_inventory>` block |
| `references/reference-brands-by-category.md` | Always — for the `<aesthetic_direction>` block |
| `assets/examples/example-restaurant.md` | If unsure what good output looks like for restaurants |
| `assets/examples/example-salon.md` | If unsure for salons |
| `assets/examples/example-venue.md` | If unsure for venues |

## Optional scripts

| Script | Use |
|---|---|
| `scripts/validate-lead.py` | Run when the user pastes raw JSON to confirm the shape is valid before generating |

---

## Override hierarchy (read carefully)

When the lead's `design_prompt` field conflicts with the category playbook or the design-tokens cheatsheet, **the `design_prompt` wins**. This skill generates a prompt for a downstream Claude; the same priority order must propagate.

1. `design_prompt` (owner-written brief) — highest
2. `notes` (admin special request) — honored when non-empty; never overrides `design_prompt`
3. Category playbook (aesthetic, page list, components)
4. Anti-AI-slop bans (these are *never* overridden — even if the lead says "I love purple gradients", explain in `<user_override>` that the anti-pattern is structural and propose terracotta/burgundy/forest/navy alternatives consistent with the request)
5. Design-tokens cheatsheet defaults — lowest

The exception in step 3 is intentional: the entire point of this skill is to escape AI-slop attractors. Keep the bans intact and explain alternatives.

---

## Common mistakes to avoid

- **Don't summarize the lead in prose before the prompt.** The user already knows their lead — just emit the prompt.
- **Don't ask clarifying questions** if the lead has enough data. Only ask if `business_name` or `category` is missing.
- **Don't mix archetypes** ("editorial-magazine with bento-grid sections" is a mid mix). Pick one.
- **Don't put the user's `design_prompt` field anywhere except `<user_override>`**. Putting it in `<aesthetic_direction>` or `<copy_seeds>` dilutes its priority.
- **Don't generate the website itself.** This skill produces the prompt; another Claude (claude.ai/design or Claude Code) generates the site.
- **Don't omit the schema.org JSON-LD requirement.** SMB sites need LocalBusiness markup or they're invisible to Google Maps re-discovery.
- **Don't add a "blog" page** unless the lead's `design_prompt` requests it. SMB sites rarely maintain blogs.
- **Don't propose more than 7 pages.** Five is the sweet spot for most SMBs; 7 is the ceiling.
