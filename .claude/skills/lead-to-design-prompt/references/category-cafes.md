# Category Playbook: Cafes

For: cafes, coffee shops, bakeries, patisseries, tea houses, juice bars, brunch spots, specialty coffee. Full-service restaurants use `category-restaurants.md`.

## Required pages

1. **Home** — hero + featured items + atmosphere + hours/location + footer
2. **Menu** — drinks + food, simple list (cafes can use a flat menu — no need for course grouping)
3. **About / Story** — owner story, sourcing (especially for specialty coffee)
4. **Visit** (instead of Contact) — address, hours, photos of the space, parking/transit, wifi notes
5. **Shop** (optional) — only if they sell beans/merch online

Optional: **Events** (if they host workshops/cuppings), **Wholesale** (if specialty coffee with B2B sales)

## Aesthetic archetypes (pick ONE)

### `organic-natural` — specialty coffee, third-wave, ethical sourcing
- Type: humanist serif (Source Serif, Tiempos Text) + monoweight sans (Söhne, Inter Tight as fallback only)
- Color: oat cream, espresso brown, sage, terracotta, deep forest
- Layout: editorial, ingredient/origin-focused
- Examples: Blue Bottle, Drop Coffee, Lot Sixty One (Amsterdam), Onyx Coffee

### `hand-crafted-cozy` — neighborhood cafe, bakery, brunch
- Type: hand-lettered display (Caslon Italic, Marcellus, or custom hand-script) + warm sans
- Color: butter cream, blush, sage, warm browns, soft terracotta
- Layout: scrapbook-style, slightly imperfect, hand-drawn icons
- Examples: Sqirl, Tartine, Bourke Street Bakery

### `scandinavian-clean` — Nordic minimalism, light wood + white
- Type: clean grotesque (Söhne, GT America, Aktiv) + minimal serif accent
- Color: warm white, pale grey, blonde wood, single muted accent
- Layout: lots of whitespace, large photography, tight grids
- Examples: Coffee Collective Copenhagen, Tim Wendelboe Oslo

### `retro-diner` — American diner, breakfast spot, classic patisserie
- Type: vintage signage display (Cooper Black, Recoleta, Pistilli) + tight grotesque
- Color: cream, tomato red, mustard, kelph green, navy
- Layout: framed photography, retro signage references
- Examples: Big Mama's & Papa's, Cafe Mogador, Le Diplomate

### `tea-house-elegant` — tea, matcha, refined morning
- Type: refined serif (Marcellus, Cormorant, Lora) + airy sans
- Color: pale jade, oat, blush, deep navy
- Layout: ceremony-influenced, quiet rhythm
- Examples: Bellocq, Postcard Teas, Cha-an

## Color guidance — what NOT to use

- ❌ Pure white + black (too tech; cafes need warmth)
- ❌ Cool corporate blue
- ❌ Purple/indigo gradients
- ✅ Warm neutrals (cream, oat, butter, blush)
- ✅ One earth-tone accent (terracotta, sage, espresso, kelph)

## Typography — banned

Inter, Roboto, Arial, Open Sans, Lato, Space Grotesk, system-ui, Poppins.

## Reference brands

Blue Bottle, Stumptown, Drop Coffee, Onyx, Lot Sixty One, Sqirl, Tartine, Bellocq, Tim Wendelboe.

## 21st.dev component hooks

- Hero: `/ui cafe hero with full-bleed lifestyle photography, hours and address below`
- Menu list: `/ui simple cafe menu list with categories, items, prices`
- Origin/story card: `/ui editorial card with large image, headline, paragraph`
- Hours/visit: `/ui hours and location card with map and address`
- Footer: `/ui cozy footer with hours, address, social, newsletter signup`

## Required components

- **Hours prominently visible** (cafes live or die on hours clarity)
- **Address + walking transit notes** on Visit page
- **Instagram embed** on Home if `instagram_url` present (cafes are visual-first)
- **Menu** as flat browsable list, not PDF

## SEO and structured data

- `@type: CafeOrCoffeeShop` or `Bakery` (sub-class of `LocalBusiness` / `FoodEstablishment`)
- `servesCuisine` if relevant
- `openingHoursSpecification` from `opening_hours` (critical — cafes get searched for "open now")
- `aggregateRating` if available
- `hasMenu` link to the menu page

## Mobile considerations

- ~85% mobile traffic
- "Open now?" must be answerable in 1 second from any page
- Map and "Get directions" must be one tap from any page

## Category-specific anti-patterns

- ❌ Cluttered homepage with 10 menu categories (keep it tight; let the menu page do the work)
- ❌ Auto-playing video
- ❌ "Order ahead" CTAs without an actual order-ahead integration
- ❌ Stock photography of latte art that isn't theirs
- ❌ Long-form blog about "our journey" on the homepage
