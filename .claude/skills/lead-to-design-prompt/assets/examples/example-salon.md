# Example: Salon Output (abbreviated)

This example highlights the **category-specific differences** from `example-restaurant.md`. Full output structure is the same; only differences are shown.

## Sample input

```json
{
  "business_name": "STUDIO NORTH",
  "category": "Hair salon",
  "description": "Editorial color specialists and precision cutting in a converted warehouse in Rotterdam Noord.",
  "design_prompt": "We're a color salon — think Bleach London or Hairrari. Bold but refined. Most clients book through Treatwell. We want our stylists' Instagram work to be central.",
  "country": "NL",
  "city": "Rotterdam",
  "address": "Zaagmolenstraat 134",
  "phone": "+31 10 244 5566",
  "instagram_url": "https://instagram.com/studionorth.rdam",
  "rating": 4.9,
  "review_count": 187,
  "opening_hours": {
    "Mon": "Closed", "Tue": "10:00–19:00", "Wed": "10:00–19:00",
    "Thu": "10:00–21:00", "Fri": "10:00–21:00", "Sat": "09:00–18:00", "Sun": "Closed"
  },
  "notes": "Stylists are Mira (color), Tomas (cuts), Anouk (color + extensions). They all want individual booking links."
}
```

## Key differences from a restaurant prompt

### `<aesthetic_direction>`

```xml
<aesthetic_direction>
  <archetype>editorial-fashion</archetype>
  <one_line_description>Fashion-magazine editorial: bold Druk-condensed display, high-contrast B&W + single oxblood accent, large editorial portraits.</one_line_description>
  <reference_brands>
    Bleach London — editorial color specialist energy
    Hairrari NYC — queer-owned editorial high-contrast
    Daniel Hersheson — UK refined editorial
  </reference_brands>
  <tone>confident, bold, restrained, professional</tone>
  <mood_keywords>editorial, monochrome, oxblood, precision, fashion, magazine</mood_keywords>
  <anti_references>
    NOT a generic "salon template" with lavender + pink + script font
    NOT a wellness spa (this is a color salon, not a relaxation spa)
    NOT a 2018 startup site
  </anti_references>
</aesthetic_direction>
```

### `<design_system>` — color and type

```xml
<design_system>
  <color>
    <philosophy>High-contrast black + warm ivory + single oxblood accent. The salon is the canvas; the clients' hair is the color. UI palette must not compete with portfolio photography.</philosophy>
    <semantic_pairs>
      --background:         oklch(96% 0.005 60);    /* warm ivory */
      --foreground:         oklch(15% 0.005 30);    /* near-black */
      --card:               oklch(94% 0.005 60);
      --card-foreground:    oklch(15% 0.005 30);
      --primary:            oklch(15% 0.005 30);    /* black, used for primary buttons */
      --primary-foreground: oklch(96% 0.005 60);
      --secondary:          oklch(88% 0.005 60);    /* warm stone */
      --secondary-foreground: oklch(15% 0.005 30);
      --muted:              oklch(92% 0.005 60);
      --muted-foreground:   oklch(45% 0.005 30);
      --accent:             oklch(38% 0.14 20);     /* oxblood */
      --accent-foreground:  oklch(96% 0.005 60);
      --destructive:        oklch(50% 0.18 25);
      --destructive-foreground: oklch(96% 0.005 60);
      --border:             oklch(85% 0.005 60);
      --input:              oklch(92% 0.005 60);
      --ring:               oklch(38% 0.14 20);
    </semantic_pairs>
    <dark_mode>required — toggle in footer, defaults to system preference; the editorial-fashion archetype works in both modes</dark_mode>
  </color>

  <typography>
    <display_font>
      family: "Druk Condensed" (Commercial Type) — fallback "GT America Condensed Bold"
      weights: 700, 900
      use: hero headlines, page titles, large display
    </display_font>
    <body_font>
      family: "Söhne"
      weights: 400, 500, 600
    </body_font>
  </typography>

  <radius>--radius: 0 (sharp); inputs 2px; chips 9999px — radius differentiation is part of the editorial language</radius>
</design_system>
```

### `<page_architecture>` — different page list from a restaurant

```xml
<page_architecture>
  <page name="Home" route="/">
    <sections>
      1. Sticky nav with right-aligned BOOK NOW oxblood button
      2. Hero — full-bleed editorial portrait (model with bold color work)
      3. Services teaser — 4 service categories with photography
      4. Stylist team — grid of 3 (Mira, Tomas, Anouk)
      5. Instagram feed — 6-up grid pulled from @studionorth.rdam
      6. Booking strip — Treatwell quick-launch
      7. Footer
    </sections>
  </page>

  <page name="Services" route="/services">
    <sections>
      1. Nav
      2. Page title
      3. Color services — list with descriptions, durations, "from €X" prices, dietary-equivalent note (e.g., "balayage", "bleach + tone")
      4. Cuts — list with descriptions, durations, prices
      5. Treatments — list
      6. Add-ons — list
      7. Booking strip
      8. Footer
    </sections>
  </page>

  <page name="Team" route="/team">
    <sections>
      1. Nav
      2. Three featured stylists — large editorial portraits, name, role, specialty, Instagram handle, individual Treatwell booking link
      3. Footer
    </sections>
  </page>

  <page name="Work" route="/work">
    <sections>
      1. Nav
      2. Editorial gallery — before/after sliders + standalone portraits, filterable by stylist
      3. Footer
    </sections>
  </page>

  <page name="Book" route="/book">
    <sections>
      1. Nav
      2. Treatwell embed (styled wrapper)
      3. Service-not-on-Treatwell phone fallback
      4. Footer
    </sections>
  </page>

  <page name="Contact" route="/contact">
    <sections>
      1. Nav
      2. Address + map (Zaagmolenstraat 134, Rotterdam)
      3. Hours table
      4. Public transit (metro to Noorderkanaal, tram lines)
      5. Footer
    </sections>
  </page>
</page_architecture>
```

### `<component_inventory>` — salon-specific

```xml
<component_inventory>
  - Sticky nav with BOOK NOW oxblood button (all pages, including mobile sticky-bottom) — **custom**
  - Hero (Home): full-bleed editorial portrait, Druk Condensed headline overlaid — **custom**
  - Services pricing table (Services): editorial pricing table with categories, durations, from-prices — 21st.dev `/ui pricing table with service categories, durations, prices in editorial style`
  - Stylist team grid (Home, Team): 3-up editorial portrait grid with name, role, specialty, individual booking link — 21st.dev `/ui editorial team grid with portrait, name, role, specialty tag, instagram link, individual booking CTA`
  - Instagram feed (Home): 6-up grid pulled from @studionorth.rdam — 21st.dev `/ui instagram feed embed grid showing latest 6 posts in editorial style`
  - Before/after slider (Work): stylist-filtered before/after slider — 21st.dev `/ui before-after image slider with stylist filter and lightbox`
  - Treatwell embed wrapper (Book, all pages footer): styled iframe wrapper — **custom**
  - Footer: address + hours + social + BOOK NOW CTA — 21st.dev `/ui salon footer with address, hours, social icons, booking CTA`
</component_inventory>
```

### Key category-specific bans (added to `<anti_patterns>`)

```
Banned (salon-specific):
- Generic "salon template" pastel palette (lavender, baby pink, mint)
- Glittery gold-on-pink (wedding invite energy, not salon energy)
- "Self-care" stock photography (woman in robe with cucumber slices)
- Auto-playing background video of hair being cut (nauseating)
- Service descriptions that hide prices ("Contact us for pricing")
- Booking that requires creating an account before showing availability
- Trust claims like "Trusted by celebrities" without names
```

### What's the same as the restaurant example

- The `<role>` block (identical)
- The `<business>` block structure
- The `<design_system>` shape (tokens, just different values)
- The `<deliverables>` block (just `@type: HairSalon` instead of `Restaurant`)
- The `<instructions>` block
- The `<user_override>` placement

The skill produces the same XML structure for every category — only the values change.
