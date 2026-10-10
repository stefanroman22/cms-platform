# Example: Wedding Venue Output (abbreviated)

Shows the **category-specific differences** for a venue. Full output structure matches the restaurant example.

## Sample input

```json
{
  "business_name": "De Olmenhorst",
  "category": "Wedding venue",
  "description": "A restored 18th-century country estate set in 4 hectares of orchard and gardens, hosting intimate weddings for up to 120 guests.",
  "design_prompt": "Cinematic and editorial — we want couples to feel they've discovered something private. Photography is everything. Pricing transparency is important: show 'from €' for our three packages but the full pricing only after an inquiry. We do not want a blog.",
  "country": "NL",
  "region": "Zuid-Holland",
  "city": "Lisse",
  "address": "Lisserweg 481",
  "postal_code": "2165 AS",
  "lat": 52.2691,
  "lng": 4.5577,
  "phone": "+31 252 411 234",
  "email": "info@deolmenhorst.nl",
  "instagram_url": "https://instagram.com/deolmenhorst",
  "rating": 4.9,
  "review_count": 64,
  "opening_hours": {"By appointment only": true},
  "extra": {"attributes": {"Outdoor space": true, "Ceremony license": true, "On-site catering": true, "Accommodation": true}}
}
```

## Key differences

### `<aesthetic_direction>`

```xml
<aesthetic_direction>
  <archetype>cinematic-editorial</archetype>
  <one_line_description>Cinematic-editorial luxury venue: serif display, generous full-bleed photography, warm neutral palette, restrained motion.</one_line_description>
  <reference_brands>
    Aman properties (aman.com) — restrained luxury, photography-first
    Borgo Pignano — Tuscan estate refined warmth
    Castello di Casole — editorial cinematic
  </reference_brands>
  <tone>restrained, intimate, confident, quiet</tone>
  <mood_keywords>cinematic, orchard, golden-hour, private, restored, hand-written</mood_keywords>
  <anti_references>
    NOT a generic wedding-template site with cursive script + gold-on-pink
    NOT a corporate event-space site
    NOT a Pinterest-board pastel rainbow
  </anti_references>
</aesthetic_direction>
```

### `<design_system>` — venue-specific color and type

```xml
<design_system>
  <color>
    <philosophy>Warm neutrals as the canvas, with deep ink type and a single soft sage accent. Photography (orchard, estate, golden-hour) carries the saturation. The UI is the museum frame around the work.</philosophy>
    <semantic_pairs>
      --background:         oklch(97% 0.008 80);    /* warm ivory */
      --foreground:         oklch(22% 0.012 40);    /* warm ink */
      --primary:            oklch(22% 0.012 40);
      --primary-foreground: oklch(97% 0.008 80);
      --secondary:          oklch(85% 0.02 100);    /* warm stone */
      --secondary-foreground: oklch(22% 0.012 40);
      --accent:             oklch(55% 0.06 130);    /* soft sage */
      --accent-foreground:  oklch(97% 0.008 80);
      --muted:              oklch(93% 0.008 80);
      --muted-foreground:   oklch(45% 0.012 40);
      --border:             oklch(88% 0.01 80);
      --input:              oklch(93% 0.008 80);
      --ring:               oklch(55% 0.06 130);
    </semantic_pairs>
    <dark_mode>optional — implement for nighttime browsers but default to light (golden-hour palette doesn't translate to dark mode cleanly)</dark_mode>
  </color>

  <typography>
    <display_font>
      family: "Canela" (Commercial Type) — fallback "Cormorant Garamond" (Google Fonts)
      weights: 300, 400, 500
      use: hero headlines, section titles
    </display_font>
    <body_font>
      family: "Söhne" — fallback "GT America"
      weights: 400, 500
    </body_font>
  </typography>

  <radius>--radius: 0 (sharp); image frames 0; buttons 2px subtle — sharp radii reinforce editorial discipline</radius>

  <motion>700ms page transitions with quiet fade + 8px translate. Gallery lightbox crossfades at 400ms. NO parallax on hero (motion-sickness on mobile).</motion>
</design_system>
```

### `<page_architecture>` — venues have more pages than restaurants

```xml
<page_architecture>
  <page name="Home" route="/">
    <sections>
      1. Cinematic hero — full-bleed orchard video (with still poster fallback) + minimal nav
      2. Welcome paragraph — 3 sentences on the estate
      3. Signature spaces — 4 spaces shown as large images with names
      4. Testimonial — single large quote with couple's first names + wedding date
      5. Packages teaser — 3 packages with "from €X" and "Inquire" CTA
      6. Plan your wedding CTA strip
      7. Footer
    </sections>
    <primary_cta>Plan your wedding (inquiry form)</primary_cta>
  </page>

  <page name="The Estate" route="/estate">
    <purpose>Spatial tour of every space, capacity, ceremony license, accommodation</purpose>
    <sections>
      1. Nav
      2. Estate overview — orchard map + total capacity + ceremony license
      3. The Orangery — photo + capacity + use cases
      4. The Garden Pavilion — photo + capacity
      5. The Drawing Rooms — photo + capacity
      6. Accommodation — 12 rooms, photo + description
      7. Plan CTA
      8. Footer
    </sections>
  </page>

  <page name="Galleries" route="/galleries">
    <purpose>Multiple galleries — by season and style</purpose>
    <sections>
      1. Nav
      2. Gallery filter — Spring / Summer / Autumn / Winter weddings + Intimate / Classic / Modern styles
      3. Masonry gallery with lightbox
      4. Footer
    </sections>
  </page>

  <page name="Packages" route="/packages">
    <purpose>Three transparent package tiers with "from €" pricing; full details after inquiry</purpose>
    <sections>
      1. Nav
      2. Pricing philosophy — 2-sentence intro on transparency
      3. Three package cards — Intimate (up to 40 guests), Classic (40-80), Grand (80-120)
      4. What's included grid
      5. Plan CTA
      6. Footer
    </sections>
  </page>

  <page name="Real Weddings" route="/real-weddings">
    <purpose>Testimonials from real couples with photography (NOT a blog; just a curated set)</purpose>
    <sections>
      1. Nav
      2. Grid of real-wedding entries — 6-9 entries, each with couple's first names, date, season, link to detail
      3. Detail pages — long-form layout with photography, the couple's words, vendor credits
      4. Plan CTA
      5. Footer
    </sections>
  </page>

  <page name="FAQ" route="/faq">
    <purpose>Capacity, catering, alcohol, parking, accessibility, accommodation, weather plan, music curfew</purpose>
    <sections>
      1. Nav
      2. Accordion of FAQ items, grouped by topic
      3. Plan CTA
      4. Footer
    </sections>
  </page>

  <page name="Plan Your Wedding" route="/inquire">
    <purpose>Short, low-friction RFP form — six fields max</purpose>
    <sections>
      1. Nav
      2. Hero — single line: "Tell us about your wedding."
      3. Inquiry form — date (or 'flexible'), guest count, name, email, phone, optional message
      4. What happens next — 2-sentence explanation
      5. Phone fallback
      6. Footer
    </sections>
    <primary_cta>Send inquiry</primary_cta>
  </page>
</page_architecture>
```

### `<component_inventory>` — venue-specific

```xml
<component_inventory>
  - Cinematic hero (Home): full-bleed orchard video with still-image poster fallback, minimal nav overlaid — **custom**
  - Signature spaces grid (Home): 4 large photographs, name + capacity overlaid — **custom**
  - Package cards (Home, Packages): three editorial cards with from-price, capacity range, included summary — 21st.dev `/ui editorial package comparison cards with included items summary and inquire CTA`
  - Masonry gallery (Galleries, Real Weddings): masonry grid with lightbox + season/style filters — 21st.dev `/ui masonry image gallery with lightbox and category filter`
  - Testimonial (Home, Real Weddings detail pages): single large pull-quote with couple first names + wedding date, no avatar — 21st.dev `/ui editorial testimonial with large pull-quote, couple first names, wedding date, no avatar`
  - Inquiry form (Plan Your Wedding): six-field RFP — 21st.dev `/ui short RFP form with date or 'flexible', guest count, name, email, phone, optional message — exactly six fields, no captcha visible`
  - FAQ accordion: grouped FAQ with accordion expansion — 21st.dev `/ui FAQ accordion grouped by topic with smooth expansion`
  - Footer: address + contact + inquiry CTA, no newsletter (venues don't do newsletters) — 21st.dev `/ui editorial venue footer with address, phone, email, inquiry CTA, no newsletter`
</component_inventory>
```

### Key category-specific bans (added to `<anti_patterns>`)

```
Banned (venue-specific):
- Hidden pricing ("Contact us for our brochure") — show "from €X" at minimum
- RFP form with 15+ required fields — keep to six
- Stock photography of weddings that didn't happen at the venue
- Photography of only one demographic of couple — show diversity in galleries
- "Award-winning" claims without naming the award
- Cursive-script-only headlines (unreadable, dated)
- Auto-playing hero video WITH sound (silent is fine)
- Music auto-playing on page load
- Excessive parallax (motion sickness, especially on mobile)
- A blog (per user_override)
```

### What's the same as restaurant and salon

- The `<role>`, `<business>`, `<deliverables>`, `<instructions>` blocks
- The eight-family design-token structure
- The `<user_override>` placement (the venue's "no blog, transparent from-pricing only" instruction goes here verbatim)

The venue example shows the largest page count (7 pages) of any category — wedding venues legitimately need it. Restaurants typically need 5–6; salons 5–6; cafes 4–5; retail 4–6; services 3–5.
