# Category Playbook: Retail Boutiques

For: clothing boutiques, concept stores, gift shops, florists, jewellery, lifestyle, bookshops, record stores, design stores. Cafes/restaurants/salons use their own playbooks.

## Required pages

1. **Home** — hero + featured products or collections + brand story teaser + visit/location + footer
2. **Shop / Catalog** — product grid with filters (or by-collection if curated)
3. **Product detail** — large photography, description, price, sizing/specs, add-to-cart or "available in store"
4. **About / Story** — brand origin, founder, sourcing/values
5. **Visit** — store address, hours, photos, parking/transit (essential for in-store-only retail)
6. **Contact** — email, phone, hours, address

Optional: **Journal / Editorial** (only if they maintain it), **Cart / Checkout** (if e-commerce), **Wholesale** (if B2B side)

If the lead is **in-store only** (no e-commerce), de-emphasize "Shop" and emphasize "Visit" — the website is a discovery / catalogue tool, not a transactional tool.

## Aesthetic archetypes (pick ONE)

### `editorial-fashion` — fashion boutique, design store, concept store
- Type: fashion-magazine serif (Saol Display, Canela, Fraunces) + clean grotesque (Söhne, GT America)
- Color: warm white or off-black + single saturated accent
- Layout: editorial spreads, large photography, generous whitespace, fashion-shoot energy
- Examples: Aesop, Acne Studios, COS, Glossier

### `warm-craft` — handmade, ceramics, plants, florist, gift shop
- Type: humanist serif (Lora, Source Serif) + warm sans
- Color: cream, terracotta, sage, oat, deep wine
- Layout: friendly, photography-led, hand-drawn touches
- Examples: Heath Ceramics, Goldune, Floom

### `brutalist-confident` — design store, contemporary art, streetwear
- Type: bold display (Druk, Reckless, GT America Condensed) + neutral body
- Color: high-contrast monochrome + single strong accent
- Layout: confident, type-as-architecture, asymmetric
- Examples: SSENSE, Dover Street Market, Goodhood

### `soft-pastel` — kids, beauty, candles, lifestyle gifts
- Type: refined serif + airy sans
- Color: blush, butter, sage, soft terracotta — but RESTRAINED, never rainbow
- Layout: gentle, lots of whitespace, soft photography
- Examples: Goop, Glossier, Beauty Pie

### `vintage-archival` — record shop, vintage clothing, antique
- Type: vintage display (Cooper Black, Recoleta, Pistilli, Druk) + clean body
- Color: warm cream, tobacco, deep wine, mustard
- Layout: catalogue-style, framed photography
- Examples: Rough Trade, Stüssy archive

## Color guidance — what NOT to use

- ❌ Generic e-commerce blue (Amazon-blue, eBay-yellow)
- ❌ Purple/indigo gradients
- ❌ Pastel rainbow (only for kid-focused if intentional)
- ✅ Confident palette tied to the merchandise

## Typography — banned

Inter, Roboto, Arial, Open Sans, Lato, Space Grotesk, system-ui, Poppins, Montserrat.

## Reference brands

Aesop, Acne Studios, COS, Glossier, Heath Ceramics, SSENSE, Dover Street Market, Goodhood, Rough Trade.

## 21st.dev component hooks

- Hero: `/ui editorial boutique hero with full-bleed product photography and small CTA`
- Product grid: `/ui editorial product grid with image, name, price, no add-to-cart hover (let users click in)`
- Product detail: `/ui product detail page with large image gallery, description, specs, add-to-cart`
- Collection nav: `/ui collection filter sidebar with categories`
- Footer: `/ui editorial footer with newsletter, store address, social, hours`

## Required components

- **Visit / Store hours** prominently visible (even for e-commerce retail, the physical store matters)
- **Newsletter signup** in footer (boutique retail thrives on email)
- **Instagram embed** on home if `instagram_url` present
- **Real product photography** — never use the manufacturer's stock images

## SEO and structured data

- `@type: Store` (sub-class of `LocalBusiness`)
- `@type: Product` on product pages, with `Offer`, `priceRange`, `availability`
- `openingHoursSpecification`
- `aggregateRating` if applicable

## Mobile considerations

- ~80% mobile traffic
- Product images must zoom on tap (not on hover)
- Filters must collapse cleanly on mobile

## Category-specific anti-patterns

- ❌ "Add to cart" hover animations on every product card (it's noisy on a catalogue page)
- ❌ Stock product photography
- ❌ Glassmorphism on product cards
- ❌ Excessive countdown timers ("Sale ends in 14:32:18") — boutique vibe is killed
- ❌ Auto-rotating hero carousel
- ❌ Six concurrent promotional banners stacked
