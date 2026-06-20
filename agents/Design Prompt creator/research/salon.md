# Research — Salon

**Last refreshed:** 2026-05-21

## Reference brands

### Fellow Barber · https://fellowbarber.com
- **Type:** barber
- **Typography:** Modern geometric sans (display) + clean web sans (body)
- **Palette:** White / black / muted gold accent / gray
- **Layout:** Product grid 3–4 col, modular "Featured" curated collections, social-proof strip with press logos mid-page, integrated booking in nav, hero with career messaging + image
- **Notable:** Press credibility shown mid-page (not relegated to footer); "Sold out" product visibility preserved for aspirational signalling; homepage gives equal weight to "Book" and "Shop" (multi-revenue stream); extensive whitespace conveys premium positioning
- **Researched:** 2026-05-21

### Huckle · https://wearehuckle.com/
- **Type:** barber
- **Typography:** Clean geometric sans throughout (display + body, single-family discipline)
- **Palette:** Black/charcoal / off-white / no chromatic accent — imagery drives the visual interest
- **Layout:** Hero image with overlaid text establishing the brand promise, modular card-based locations/news sections, full-width imagery breaking up text blocks, newsletter signup repeated strategically (top and footer)
- **Notable:** Positions as a *cultural destination* ("Where Great Hair Meets Real Culture & Community") — record store mentions, news/events programming. Zero barbershop clichés (no vintage blades, no retro styling). Contemporary cool via restraint + cultural credibility.
- **Researched:** 2026-05-21

### Barber & Co Miami · https://www.barberandco.com
- **Type:** barber
- **Typography:** Serif wordmark (classic heritage feel) + sans for UI elements (likely system fonts)
- **Palette:** Beige/cream / dark grey / white / black
- **Layout:** Minimalist grid; no traditional hero splash — instead a "dual-logo treatment" with beige and dark-grey alternation. Modular product cards. Dual-location structure prominently featured.
- **Notable:** Scandinavian-influenced minimalism, monochromatic discipline. A "Lab" section hints at product transparency (uncommon for the category). Separates "Shops" from "Bars/Gift Shop" — multi-service business differentiated via navigation, not chrome.
- **Researched:** 2026-05-21

### Murdock London · https://www.murdocklondon.com
- **Type:** barber
- **Typography:** Modern sans-serif display (likely custom or premium) + clean sans body. Headers in measured uppercase ("barbering. it's what we do best") for typographic authority.
- **Palette:** Black / white / gold-tan accent / dark gray
- **Layout:** Full-width hero banner rotating product spotlights → 3-column bestseller grid → barbering messaging → trending products → journal → footer. Vertical modular stack with generous whitespace between sections.
- **Notable:** Sticky nav for persistent booking access. Dual imagery per product (product + lifestyle). Journal/content section establishes brand authority beyond retail. Location cards with photographic backgrounds differentiate each shop without changing the chrome. Masculine without resorting to barber-pole graphics or retro hand-lettering.
- **Researched:** 2026-05-21

## Booking UX (barbershop/salon) — field-tested patterns

Field-tested from a deep barbershop booking build (2026-06-17). Bake these into salon design prompts — they refine the generic `<commerce_and_forms>` booking defaults with category specifics.

- **Multi-step flow + always-visible action.** Fresha/Treatwell-style steps: Services → Professional (barber; include a "No preference / first available" option) → Time → Confirm. Desktop = two columns: left is the active step (scrolls), right is a STICKY summary/action card whose Continue/Confirm button is always visible without scrolling. Mobile = one step at a time + a sticky bottom action bar showing the running selection, total, and a Back control.
- **Week-paginated day picker** (replaces a long horizontally-scrolling date strip). Show a FIXED 7-day week in a `repeat(7,1fr)` grid so cells always fit with no horizontal scroll at any width (shrink type on small screens; drop the month label only on the tiniest phones). "Pick a day" header carries prev/next arrows on the RIGHT, same line as the label. BACK disabled on week 0 (starts today, no past days); FORWARD jumps +7 days, enabled to ~6 months out. All 7 cells always render; sold-out / no-free-slot days are greyed and disabled. Fetch availability per VISIBLE week (lazy), refetch on arrow nav, reset to week 0 when service/barber changes. Animate week changes as a DIRECTIONAL slide (AnimatePresence keyed on week offset with a custom direction, clipped by an overflow-hidden wrapper; reduced-motion → fade).
- **Per-card selection cross-fade.** Service and barber cards select with a smooth cross-fade — render BOTH a "+" and a "check" stacked in one grid cell and fade/scale between them (opacity + scale) while the card's colour/border transitions, so the check and colour animate in instead of popping. Distinct from the submit→success morph; this is per-card SELECTION feedback. Reduced-motion disables it.
- **Responsive select pill → icon-only on mobile.** A card laid out "avatar | text | pill" where the Select/Selected pill is `flex:0 0 auto` crushes the text column to one-word-per-line on phones and overlaps the text. The whole card is the tap target, so on phones collapse the pill to a compact ICON-ONLY badge (check/plus), hide its text label, and put `min-width:0` on the text column. Keep the labelled pill on desktop.
- **No-scroll confirmation/success screen.** Must fit FULLY without scrolling on every viewport (verify 320→1440): compact centred layout; `@media (max-height: …)` tiers that progressively shrink type + spacing on short screens; on tiny legacy phones (≤360w AND ≤600h) drop ONLY the least-important secondary line. Optionally render on the page background (no card chrome). The "manage your booking" link must be its OWN themed, hover-able link (accent colour, `cursor:pointer`) — NOT a reused "Date & time" detail label. Animate the success checkmark in; don't pop it.
- **First-class localized route loader.** Elevate the App Router segment loader (`app/[locale]/loading.tsx`) from a small in-content spinner to a first-class, full-screen-capable THEMED splash: brand wordmark + spinner + a short, business-flavoured, LOCALIZED status line via a DEDICATED i18n key (e.g. `loader.routeLoading`) — do NOT reuse the intro loader's copy. Barbershop: NL "Bezig met knippen…" / EN "Cutting in progress…". Theme to the palette (light theme → light bg + accent spinner), z-index ABOVE header & mobile menu, respect reduced-motion. (Inspiration: nsttvakris.nl shows a full-screen brand spinner between pages.)

## Common patterns observed

(regenerated by Phase 4 once ≥5 brands of one archetype exist)
