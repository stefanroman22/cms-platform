# Category Playbook: Salons

For: hair salons, barbershops, beauty salons, nail studios, spas, brow bars, lash studios. Wedding venues use `category-venues.md`.

## Required pages

1. **Home** — hero + services overview + team teaser + gallery teaser + booking CTA + footer
2. **Services** — full list with descriptions, durations, prices (or price ranges); grouped by category (cut/color/treatment, or facial/massage/wax)
3. **Team** — stylist/specialist bios with photo, role, specialties, Instagram link
4. **Gallery** — before/after if appropriate, editorial work, room shots
5. **Book** — embedded booking widget (Treatwell, Salonized, Salon Iris, Fresha, Booksy) in a styled wrapper
6. **Contact** — address, phone, hours, map

Optional: **Products** (if they retail), **Memberships** (if subscription model), **Bridal/Special occasion** (if relevant)

## Aesthetic archetypes (pick ONE)

### `editorial-fashion` — high-end salon, color specialist, fashion-forward
- Type: fashion-magazine serif (Playfair Display, Fraunces, Saol Display, Canela) + clean grotesque body
- Color: high-contrast B&W + single brand accent (deep red, gold, burgundy, oxblood, electric blue)
- Layout: editorial, large photography, generous whitespace, fashion-shoot energy
- Examples: Bleach London, Hairrari, Tru Salon, Daniel Hersheson

### `monochrome-luxury` — refined, mature clientele, premium pricing
- Type: refined serif (Cormorant, GT Sectra, Tiempos) + minimal sans (Söhne, GT America)
- Color: warm white, cream, charcoal, single metallic accent (brushed brass, rose gold)
- Layout: museum-quiet, lots of whitespace, restrained
- Examples: Sally Hershberger, The Lane, Frédéric Fekkai

### `neon-expressive` — young, edgy, creative, urban
- Type: bold display (Druk, GT America Condensed, Tusker Grotesk) + clean sans
- Color: black + 1-2 saturated neon accents (acid green, hot pink, electric yellow)
- Layout: confident, asymmetric, big type as architecture
- Examples: Bleach London (their bolder side), Hare & Bone, Edward James

### `warm-boutique` — neighborhood salon, friendly luxury
- Type: humanist serif (Lora, Source Serif) + warm sans (Switzer, Manrope)
- Color: blush, oat, terracotta, deep wine, soft gold
- Layout: friendly, warm photography, hand-drawn accent touches
- Examples: Davines salons, Aveda concept stores, Hello Sunday

### `industrial-utilitarian` — barbershop, men's grooming, urban
- Type: condensed display (Druk Wide, GT America Condensed) + neutral sans
- Color: charcoal, concrete grey, oxblood, deep navy
- Layout: tight, masculine, no-nonsense
- Examples: Hawleywood's, Murdock London, Ruffians

## Color guidance — what NOT to use

- ❌ Generic salon pastel (lavender, baby pink, mint) — that's the AI-slop salon default
- ❌ Purple/indigo gradients (a specific subtype of salon slop)
- ❌ Glittery gold-on-pink (this is wedding-invite energy, not salon energy)
- ✅ Confident, restrained palettes with one strong brand color

## Typography — banned

Inter, Roboto, Arial, Open Sans, Lato, Space Grotesk, system-ui, Poppins, Montserrat (especially Montserrat — every generic salon site uses it).

## Reference brands

Bleach London, Hairrari, Tru Salon, Davines, The Lane, Daniel Hersheson, Aveda, Ruffians, Murdock London.

## 21st.dev component hooks

- Hero: `/ui salon hero with full-bleed editorial portrait and booking CTA`
- Services pricing table: `/ui pricing table with service categories, durations, prices`
- Team grid: `/ui team grid with portrait, name, role, specialty tags`
- Before/after gallery: `/ui before-after slider with category filter`
- Booking embed: `/ui booking widget wrapper with service selector and date picker`
- Footer: `/ui salon footer with address, hours, social, booking CTA`

## Required components

- **Sticky "Book Now" CTA** in the header on every page (the #1 conversion driver)
- **Service list with PRICES** (or price ranges — never hide pricing; if they refuse to publish prices, use "from €X")
- **Stylist/specialist team page** with portraits (faces sell salons)
- **Before/after gallery** if hair/beauty (skip for nails, spas without visual transformation)
- **Direct booking** integration, not just a phone number

## Booking experience (required pattern)

Model the booking flow on Fresha/Treatwell — a multi-step wizard, not one long form:

- **Steps:** Services → Professional (stylist/barber, include a **"No preference / first available"** option) → Time → Confirm.
- **Layout:** desktop = two columns — left scrolls through the active step, right is a **sticky summary/action card** whose Continue/Confirm button stays visible without scrolling. Mobile = one step at a time + a **sticky bottom action bar** with the running selection, total, and a Back control.
- **Day picker — week-paginated, NOT a long horizontal date strip.** Show a fixed 7-day week; the "Pick a day" header carries prev/next arrows on the right of the same line. Back is disabled on the current week (week 0 = today, no past days); forward jumps +7 days, enabled to ~6 months out. Sold-out days render but are greyed/disabled. The 7 cells are equal-width (`grid repeat(7,1fr)`) so they always fit with **no horizontal scroll** at any width (shrink type on small screens; drop the month label only on the tiniest phones). Week changes animate as a **directional slide** (outgoing slides out, incoming slides in, clipped by overflow-hidden; reduced-motion → fade).
- **Selectable-card cross-fade:** service and stylist cards select via a smooth cross-fade — render both a "+" and a "check" stacked in one cell and fade/scale between them while the card colour/border transitions, so selection animates in instead of popping. Reduced-motion disables it.
- **Confirmation / success screen:** must fit fully **without scrolling on every viewport** (320→1440) — compact centred layout, `@media (max-height)` tiers that shrink type/spacing on short screens, and on tiny legacy phones drop only the least-important secondary line. The "manage your booking" link is its **own** themed, hover-able accent link (`cursor:pointer`) — distinct from the "Date & time" detail label. Animate the success checkmark in, don't pop it.

## SEO and structured data

- `@type: HairSalon` | `BeautySalon` | `NailSalon` | `DaySpa` (sub-classes of `LocalBusiness`)
- `priceRange: "€€" | "€€€"`
- `openingHoursSpecification`
- `aggregateRating`
- For each major service, a sub-page or schema with `OfferCatalog`

## Mobile considerations

- ~75% mobile traffic
- Booking button must be sticky-bottom on mobile
- Service prices must be readable without pinch-zoom
- Phone tap-to-call in header

## Category-specific anti-patterns

- ❌ Auto-playing background video of hair being cut (it's nauseating)
- ❌ "Trusted by celebrities" without names
- ❌ Generic "self-care" stock photography (woman in robe with cucumber slices)
- ❌ Glassmorphism on every card
- ❌ Pastel rainbow gradients as the brand identity
- ❌ Service descriptions that hide prices ("Contact us for pricing")
- ❌ Booking that requires creating an account before showing availability
- ❌ A fixed-width Select/Selected pill on a barber/service card that crushes or overlaps the card text on phones (collapse the pill to an icon-only badge on mobile)
- ❌ A booking step or success screen that needs scrolling to reach the action/Continue button
- ❌ A sudden select-state "pop" instead of a cross-fade when a card is chosen
