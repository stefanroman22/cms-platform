# Category Playbook: Wedding Venues

For: wedding venues, event spaces, banquet halls, ceremony locations, country estates, vineyards with events, restored barns, boutique hotels with weddings. For non-wedding event spaces (conference centres), use `category-services.md`.

## Required pages

1. **Home** — cinematic hero (often video) + venue overview + signature spaces + testimonial + packages teaser + RFP CTA + footer
2. **The Venue** — spaces tour (ceremony, reception, getting-ready rooms, outdoor), capacity, layout options
3. **Galleries** — multiple galleries, organized by season or style (e.g., "Summer weddings", "Intimate ceremonies", "Black-tie receptions")
4. **Packages / Pricing** — what's included, capacity tiers, seasonal pricing notes (don't hide all pricing; at least show "starting from")
5. **Testimonials** — real couples, real photos, full names with permission, dates
6. **FAQ** — capacity, catering, alcohol, parking, accessibility, accommodation nearby
7. **Plan Your Wedding / RFP** — inquiry form (kept SHORT — every required field reduces conversion 5-10%)

Optional: **Vendors we recommend**, **Virtual tour** (3D walkthrough or video), **Blog** (real weddings; only if they maintain it)

## Aesthetic archetypes (pick ONE)

### `cinematic-editorial` — luxury, destination, high-end
- Type: refined serif (Canela, Cormorant Garamond, GT Sectra, Saol Display) + a quiet sans (Söhne, GT America)
- Color: warm white, cream, deep ink, soft blush or moss, single metallic accent (gold/champagne)
- Layout: full-bleed photography, cinematic ratios, large quiet typography
- Examples: Aman properties, Borgo Pignano, Castello di Casole, La Foce

### `rustic-warm` — barn, vineyard, farm, countryside
- Type: a humanist serif (Lora, Source Serif, Frank Ruhl) + warm sans
- Color: warm white, cream, sage, terracotta, deep wine, golden hour tones
- Layout: photography-led, hand-drawn details, generous spacing
- Examples: Blackberry Farm, Mountain House Estate, Houchins

### `classic-elegant` — historic estate, ballroom, traditional
- Type: classic serif (Caslon, Garamond, Cormorant) + serif body (yes, two serifs)
- Color: cream, ivory, navy, deep green, antique gold
- Layout: symmetric, formal, framed photography
- Examples: The Plaza, Cliveden House, Hotel Bel-Air

### `destination-modern` — contemporary architecture, modern art, urban
- Type: clean serif (Tiempos Headline) or characterful sans (Söhne Breit) + minimal body
- Color: high-contrast neutrals + one strong accent (oxblood, ochre, deep teal)
- Layout: architectural, large white space, confident type
- Examples: The Standard High Line, ACE Hotel weddings, Casa Bonay

### `coastal-airy` — seaside, beachfront, bright Mediterranean
- Type: refined serif + airy sans
- Color: warm white, sand, sea-foam, soft terracotta, navy
- Layout: bright photography, lots of negative space, soft motion
- Examples: Cap Rocat, Borgo Egnazia, Hotel du Cap

## Color guidance — what NOT to use

- ❌ Pastel rainbow (this is the AI-slop wedding default)
- ❌ Glittery gold-on-purple (the cliché wedding-invite palette)
- ❌ Purple/indigo gradients
- ❌ Pure white + pure black (too tech for weddings)
- ✅ Warm neutrals + one restrained accent
- ✅ Photography does the color work; the design is the frame

## Typography — banned

Inter, Roboto, Arial, Open Sans, Lato, Space Grotesk, system-ui, Poppins, Montserrat, Great Vibes (every generic wedding template uses Great Vibes), Allura, Pinyon Script.

## Reference brands

Aman, Borgo Pignano, Castello di Casole, Mountain House Estate, Houchins, Cliveden House, The Standard. For Dutch context: Kasteel De Vanenburg, Landgoed De Olmenhorst, Wieuwerd.

## 21st.dev component hooks

- Hero: `/ui wedding venue hero with full-bleed video or cinematic photography and small bottom-right RFP CTA`
- Spaces tour: `/ui venue spaces grid with category filter and large photography`
- Gallery: `/ui masonry gallery with lightbox and seasonal filter`
- Testimonial: `/ui testimonial card with couple photo, names, date, full quote`
- RFP form: `/ui short RFP form with date, guest count, name, email, phone, optional message`
- Footer: `/ui elegant footer with address, contact, social, RFP CTA`

## Required components

- **Cinematic hero** (video acceptable, still photo always acceptable)
- **At least 3 galleries** (couples expect lots of photos — this is the #1 conversion driver)
- **Pricing transparency** — "starting from €X" or capacity-based packages; couples reject venues that hide all pricing
- **RFP form, kept short** — name, email, phone, date, guest count, optional message. Every additional required field drops conversion ~5-10%.
- **Testimonials with REAL couple photos and names** (this is a high-stakes purchase; faceless quotes are weak)
- **Capacity, catering policy, alcohol policy, accessibility** visible in FAQ
- **Accommodation map** if rural (couples and guests need lodging info)

## SEO and structured data

- `@type: EventVenue` (sub-class of `Place`) — pair with `LocalBusiness`
- `maximumAttendeeCapacity` per space
- `aggregateRating` if reviews are aggregated
- `Photo` array referencing gallery images
- `priceRange: "€€€" | "€€€€"`

## Mobile considerations

- ~70% mobile traffic (lower than restaurants — couples often browse on laptops too)
- Hero video must have a still poster fallback
- RFP form must work flawlessly on mobile (the #1 conversion event)
- Gallery must be swipeable

## Category-specific anti-patterns

- ❌ Auto-playing hero video with sound
- ❌ Hidden pricing ("Contact us for our brochure") — this is the most common reason couples bounce
- ❌ RFP form with 15+ required fields
- ❌ Stock photography of weddings that didn't happen at the venue
- ❌ Photography of only one demographic of couple — show diversity
- ❌ "Award-winning" claims without naming the award
- ❌ Cursive-script-only headlines (unreadable, dated)
- ❌ Music auto-playing on page load
- ❌ Excessive parallax (motion sickness, especially on mobile)
