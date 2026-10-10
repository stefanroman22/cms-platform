# Category Playbook: Restaurants

For: full-service restaurants, bistros, trattorias, brasseries, gastropubs, steakhouses, pizzerias, sushi/ramen, fine dining. Cafes and coffee shops use `category-cafes.md`.

## Required pages

In this order:

1. **Home** — hero + reservation CTA + featured menu items + atmosphere photography + social proof + location/hours + footer
2. **Menu** — full browsable HTML menu (NEVER embed a PDF), grouped by course; per-item: name, short description, price, dietary icons (vegan/gluten-free/spicy)
3. **About / Story** — chef/owner story, founding date if known, sourcing philosophy if mentioned in reviews
4. **Gallery** — food + room + chef-in-action; mixed grid (not uniform thumbnails)
5. **Reservations** — embedded third-party widget (OpenTable, Resengo, Formitable, TheFork) in a styled wrapper; fallback to a phone CTA
6. **Contact** — address, phone, email, hours, embedded map, parking notes, public-transport notes

Optional: **Events / Private dining**, **Order online** (if `menu_url` or delivery is in `extra.attributes`)

**Do not add a blog page** unless the lead's design_prompt explicitly asks.

## Aesthetic archetypes (pick ONE)

### `editorial-magazine` — fine dining, tasting menu, white tablecloth
- Type: serif display (Fraunces, Cormorant, GT Sectra, Tiempos) + clean grotesque body (Söhne, GT America, Switzer)
- Color: ivory/cream background, deep ink or wine for text, gold or copper accent. NO white-on-pure-white.
- Layout: asymmetric, generous whitespace, large photography one side / type the other
- Examples to lean on: Carbone, The Fat Duck, Noma, De Librije, Aman dining sites

### `warm-photographic` — bistro, trattoria, family-run, neighborhood restaurant
- Type: humanist serif (Source Serif, Lora, Frank Ruhl) + warm sans (Inter Tight ONLY as fallback, prefer Switzer, Söhne, Manrope)
- Color: cream, terracotta, olive, deep wine, warm browns
- Layout: photography-led hero, menu items with photos, hand-drawn or hand-lettered accent touches
- Examples: Sqirl, Lyle's London, Bavette, Toscanini Amsterdam

### `industrial-utilitarian` — modern brasserie, brewpub, neo-bistro
- Type: condensed display (Söhne Breit, GT America Condensed, Druk) + neutral sans body
- Color: high-contrast — concrete grey, off-black, single bright accent (oxblood, mustard, electric blue)
- Layout: bento-grid menu, large type as architecture, exposed structure
- Examples: Mission Chinese, Frenchette, De School Amsterdam (food side)

### `cozy-hand-crafted` — pizzeria, taco joint, ramen shop, casual
- Type: a single characterful sans (GT Walsheim, Mona Sans, Söhne) or hand-set serif
- Color: warm accent palette tied to cuisine (red-orange-cream for Italian, deep navy-cream for Japanese, terracotta-cream-pink for Mexican)
- Layout: friendly, slightly imperfect alignment, hand-drawn icons
- Examples: Roberta's, Tacombi, Ippudo

### `organic-natural` — farm-to-table, vegetarian/vegan, seasonal
- Type: humanist serif + earthy sans
- Color: sage, terracotta, oat, deep forest; muted, never saturated
- Layout: lots of negative space, ingredient-focused photography
- Examples: Dirt Candy, Greens, Restaurant De Kas Amsterdam

## Color guidance — what NOT to use

- ❌ Cool corporate blue (this is a SaaS color, not a restaurant color)
- ❌ Purple/indigo gradients
- ❌ Pure black on pure white (too tech; use deep ink #1a1a1a on cream #fafaf5)
- ❌ Pastel rainbow palettes (this is for cafes/bakeries, not restaurants)
- ✅ Warm neutrals + one or two saturated brand accents
- ✅ Earth tones grounded in the cuisine

## Typography — banned in this category

Inter, Roboto, Arial, Open Sans, Lato, Space Grotesk, system-ui. Also avoid Poppins (too tech) and Montserrat (too 2018 startup).

## Reference brands to name in `<reference_brands>` (always cite 2–3)

See `reference-brands-by-category.md`. Restaurants: Aesop (for editorial tone discipline), Noma, Sqirl, Carbone, Lyle's, The Fat Duck, De Librije.

## 21st.dev component hooks

- Hero: `/ui restaurant hero with full-bleed food photography and reservation button`
- Featured menu: `/ui editorial menu card grid with photo, name, price`
- Testimonials: `/ui editorial testimonial with large pull-quote, small author name, no avatar`
- Hours table: `/ui hours table with current-day highlight`
- Footer: `/ui editorial footer with address, hours, social, newsletter`

## Required components

- **Reservation CTA** in the header on every page (sticky on scroll)
- **Phone number** clickable in the header on mobile
- **Address + hours** in the footer on every page
- **Browsable menu** (HTML, never PDF)
- **Map** in the contact page (only if `lat`/`lng` present)
- **Reviews section** if `review_count >= 5` and `rating >= 4.0`

## SEO and structured data

- `@type: Restaurant` (subclass of `LocalBusiness` and `FoodEstablishment`)
- `servesCuisine` from category context
- `acceptsReservations: true` if reservation widget is included
- `priceRange: "€€" | "€€€"` (infer from category context)
- `openingHoursSpecification` from `opening_hours`
- `aggregateRating` if `rating` + `review_count` present
- `menu` URL pointing to the menu page

## Mobile considerations

- 80% of restaurant traffic is mobile
- Reservation button must be sticky at the bottom on mobile (above the iOS home indicator)
- Menu must be readable without pinch-zoom
- Phone number must be tappable from the header

## Category-specific anti-patterns

- ❌ PDF menu embed (kills SEO, kills mobile UX)
- ❌ Auto-playing background video with sound
- ❌ Hero carousel with multiple slides (one strong photo always wins)
- ❌ "Trusted by" logo bar (irrelevant for restaurants)
- ❌ Three-icon feature grid ("Fresh ingredients / Cozy atmosphere / Friendly staff") — show, don't tell
- ❌ Long-scroll homepage with 12 sections — keep to 6–7
- ❌ Stock photography of "smiling people clinking glasses"
