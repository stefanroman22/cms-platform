# Example: Restaurant Output

**Sample input lead:**

```json
{
  "business_name": "Osteria Lucia",
  "category": "Italian restaurant",
  "description": "Family-run Northern Italian kitchen serving fresh handmade pasta and seasonal antipasti in a candle-lit dining room.",
  "about": "Founded in 2014 by chef Marco Bellini, born in Bologna. We make all our pasta in-house every morning. Wine list focuses on small biodynamic Italian producers.",
  "design_prompt": "Make it feel warm and Italian but not cliché — no checkered tablecloths, no Italian flag colors. Think Carbone NYC meets a Tuscan farmhouse. We want online reservations through Resengo. Bilingual NL/EN.",
  "country": "NL",
  "region": "Noord-Holland",
  "city": "Amsterdam",
  "address": "Reguliersgracht 24",
  "postal_code": "1017 LK",
  "lat": 52.3654,
  "lng": 4.8965,
  "phone": "+31 20 123 4567",
  "email": "ciao@osterialucia.nl",
  "website_url": null,
  "facebook_url": "https://facebook.com/osterialucia",
  "instagram_url": "https://instagram.com/osterialucia",
  "menu_url": null,
  "web_presence": "social_only",
  "source_url": "https://maps.google.com/...",
  "rating": 4.7,
  "review_count": 412,
  "reviews": [
    {"author": "Sandra K.", "text": "The cacio e pepe is the best I've had outside of Rome. The dining room feels like a private dinner party.", "relative_date": "2 weeks ago", "rating": 5},
    {"author": "Tom V.", "text": "Marco came out to chat about the wine. Felt like family.", "relative_date": "1 month ago", "rating": 5},
    {"author": "Lina F.", "text": "Pasta is clearly hand-made. Pricing is fair for the quality. Highly recommend the tagliatelle.", "relative_date": "3 weeks ago", "rating": 5}
  ],
  "opening_hours": {
    "Mon": "Closed", "Tue": "18:00–22:30", "Wed": "18:00–22:30",
    "Thu": "18:00–23:00", "Fri": "18:00–23:30", "Sat": "12:00–15:00, 18:00–23:30", "Sun": "12:00–22:00"
  },
  "extra": {
    "attributes": {
      "Service options": {"Dine-in": true, "Takeout": false, "Delivery": false, "Outdoor seating": true},
      "Highlights": {"Cozy atmosphere": true, "Romantic": true, "Wine list": true, "Vegetarian options": true},
      "Accessibility": {"Wheelchair accessible entrance": true, "Wheelchair accessible seating": false}
    }
  },
  "notes": "Marco is camera-shy — keep team photos optional. Prefer photography of food and the room, not people."
}
```

---

## Generated output

Design prompt for **Osteria Lucia** — paste the XML block below into claude.ai/design, or into Claude Code with the `frontend-design` and `web-artifacts-builder` skills loaded. The `<user_override>` block at the end captures Marco's brief and supersedes the skill's defaults.

```xml
<role>
You are an expert frontend designer building a complete, production-grade website for a specific small business. Your job is to produce (1) a complete design system file and (2) every page listed in <page_architecture>, as a single self-contained set of artifacts.

You have strong knowledge of design principles, typography, and color theory. You default to safe, generic choices unless explicitly encouraged otherwise. The constraints below exist to push you out of that default. Honor them.

Match implementation complexity to the aesthetic vision. Minimalist designs require restraint and meticulous spacing — not "minimal but with five gradients". Bold designs require committed execution — not timid pastels with one accent color.

Treat <user_override> as the highest-priority signal. When <user_override> conflicts with anything else in this prompt — except <anti_patterns>, which is structural — <user_override> wins.
</role>

<business>
  <name>Osteria Lucia</name>
  <category>restaurant (Italian restaurant, family-run Northern Italian)</category>
  <description>Family-run Northern Italian kitchen serving fresh handmade pasta and seasonal antipasti in a candle-lit dining room.</description>
  <about>Founded in 2014 by chef Marco Bellini, born in Bologna. All pasta made in-house every morning. Wine list focused on small biodynamic Italian producers.</about>
  <location>
    <city>Amsterdam</city>
    <region>Noord-Holland</region>
    <country>Netherlands</country>
    <address>Reguliersgracht 24</address>
    <postal_code>1017 LK</postal_code>
    <coordinates>52.3654, 4.8965</coordinates>
  </location>
  <contact>
    <phone>+31 20 123 4567</phone>
    <email>ciao@osterialucia.nl</email>
  </contact>
  <social>
    <facebook>https://facebook.com/osterialucia</facebook>
    <instagram>https://instagram.com/osterialucia</instagram>
  </social>
  <web_presence>social_only — this is their first real website</web_presence>
  <trust_signals>
    <rating>4.7 ★</rating>
    <review_count>412</review_count>
    <selected_reviews>
      "The cacio e pepe is the best I've had outside of Rome. The dining room feels like a private dinner party." — Sandra K.
      "Marco came out to chat about the wine. Felt like family." — Tom V.
      "Pasta is clearly hand-made. Pricing is fair for the quality." — Lina F.
    </selected_reviews>
  </trust_signals>
  <hours>
    Mon: Closed
    Tue–Wed: 18:00–22:30
    Thu: 18:00–23:00
    Fri: 18:00–23:30
    Sat: 12:00–15:00, 18:00–23:30
    Sun: 12:00–22:00
  </hours>
  <google_attributes>
    Service: Dine-in only (no takeout, no delivery), outdoor seating available.
    Highlights: cozy, romantic, biodynamic wine list, vegetarian options available.
    Accessibility: wheelchair-accessible entrance; seating accessibility limited.
  </google_attributes>
  <languages>Dutch (primary) + English (secondary)</languages>
</business>

<aesthetic_direction>
  <archetype>warm-photographic</archetype>
  <one_line_description>Warm-photographic Italian neighborhood restaurant: humanist serif display, ivory/terracotta/deep-wine palette, candle-lit photography weighting every section.</one_line_description>
  <reference_brands>
    Carbone NYC — for editorial Italian confidence
    Sqirl LA — for warm photography-led food sites
    Toscanini Amsterdam — for local Italian neighborhood warmth
  </reference_brands>
  <tone>warm, intimate, confident, unfussy</tone>
  <mood_keywords>candle-lit, hand-made, biodynamic, family, slow, neighborhood</mood_keywords>
  <anti_references>
    NOT a SaaS landing page
    NOT a generic Italian "trattoria template" (no checkered patterns, no Italian flag colors, no Mediterranean stock illustrations)
    NOT a 2018 startup site with Lato + indigo
  </anti_references>
</aesthetic_direction>

<design_system>
  <color>
    <philosophy>Warm ivory ground, deep ink type, with terracotta and a restrained burnt-wine accent. The palette should feel like the candle-lit dining room itself — not Italian-flag, not red-checkered. Photography carries the color saturation; the UI stays restrained.</philosophy>
    <semantic_pairs format="shadcn-compatible CSS variables, OKLCH values">
      --background:         oklch(97% 0.012 75);    /* warm ivory */
      --foreground:         oklch(22% 0.015 30);    /* deep warm ink */
      --card:               oklch(95% 0.015 75);
      --card-foreground:    oklch(22% 0.015 30);
      --popover:            oklch(97% 0.012 75);
      --popover-foreground: oklch(22% 0.015 30);
      --primary:            oklch(32% 0.10 25);     /* deep wine */
      --primary-foreground: oklch(97% 0.012 75);
      --secondary:          oklch(80% 0.05 60);     /* warm terracotta highlight */
      --secondary-foreground: oklch(22% 0.015 30);
      --muted:              oklch(93% 0.01 75);
      --muted-foreground:   oklch(48% 0.015 30);
      --accent:             oklch(62% 0.13 55);     /* burnt copper */
      --accent-foreground:  oklch(22% 0.015 30);
      --destructive:        oklch(50% 0.18 25);
      --destructive-foreground: oklch(97% 0.012 75);
      --border:             oklch(88% 0.012 75);
      --input:              oklch(93% 0.01 75);
      --ring:               oklch(62% 0.13 55);
    </semantic_pairs>
    <dark_mode>optional — implement but default to light; the restaurant's candle-lit room is already evoked in the light palette</dark_mode>
  </color>

  <typography>
    <philosophy>A humanist serif carries the display register (warm, hand-set feel), paired with a clean grotesque for body. The pairing reads as "old-world warmth meets contemporary clarity" — Italian neighborhood, not Italian theme park.</philosophy>
    <display_font>
      family: "Fraunces"
      source: Google Fonts
      weights: 400, 600, 800; optical-size and SOFT axis tuned
      use: hero headlines, page titles, large pull-quotes
    </display_font>
    <body_font>
      family: "Söhne" (preferred) or fallback "Switzer"
      source: Klim Type Foundry / Fontshare
      weights: 400, 500, 600
      use: body, UI, navigation, labels
    </body_font>
    <mono_font_optional>none needed</mono_font_optional>
    <scale>16 / 18 / 20 / 24 / 30 / 36 / 48 / 60 / 72 / 96</scale>
    <line_heights>
      headings: 1.05
      body: 1.6
      menu items: 1.4
    </line_heights>
    <letter_spacing>
      display: -0.025em
      body: 0
      eyebrow labels: 0.12em uppercase
    </letter_spacing>
  </typography>

  <spacing>
    4/8 base. Scale: 0, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192px.
    Section padding: 128px desktop / 64px mobile.
    Container max-width: 1280px with inner reading width 720px for longform.
  </spacing>

  <radius>
    --radius: 4px (subtle, refined).
    Buttons: 4px. Cards: 8px. Inputs: 4px. Image frames: 0 (sharp). Chips/tags: 9999px (pill).
  </radius>

  <shadow>
    Use sparingly. Elevation 1–2 on hover only. No shadows on hero, no shadows on photography (let the image stand).
  </shadow>

  <motion>
    --motion-fast: 120ms; --motion-base: 200ms; --motion-slow: 400ms; --motion-page: 700ms.
    Standard ease: cubic-bezier(0.2, 0, 0, 1).
    Use: page fade-in (700ms), hover on links (200ms), subtle scroll-reveal on hero text (one-time, opacity + 8px translate).
    Respect prefers-reduced-motion.
  </motion>

  <breakpoints>sm 640 / md 768 / lg 1024 / xl 1280 / 2xl 1536. Mobile-first.</breakpoints>
</design_system>

<page_architecture>
  <page name="Home" route="/">
    <purpose>Convey the warmth of the room and the seriousness of the pasta in 7 seconds; drive reservation.</purpose>
    <sections>
      1. Sticky transparent navigation (becomes solid on scroll)
      2. Hero — full-bleed photograph of pasta being plated or the candle-lit room; large Fraunces headline lower-third
      3. Reservation strip — single-line "Tonight at Osteria Lucia" with date selector → Resengo
      4. Featured pasta — 3 dishes, large photography, brief description, no prices
      5. About strip — 2 sentences on Marco + hand-made pasta + biodynamic wine, with one photograph
      6. Trust band — rating + review count + 2 selected pull-quotes
      7. Visit — hours table + address + map
      8. Footer
    </sections>
    <primary_cta>Reserve a table (opens Resengo)</primary_cta>
    <seo_title>Osteria Lucia — Northern Italian in Amsterdam Centrum</seo_title>
    <meta_description>Family-run Northern Italian. Hand-made pasta daily. Biodynamic wine. Reguliersgracht, Amsterdam.</meta_description>
  </page>

  <page name="Menu" route="/menu">
    <purpose>Browsable menu (HTML, never PDF). Highest-traffic page after home.</purpose>
    <sections>
      1. Navigation
      2. Menu header — short note from Marco about seasonal sourcing
      3. Antipasti — list with name, short description, price
      4. Primi (pasta) — list, dietary icons (V for vegetarian)
      5. Secondi — list
      6. Dolci — list
      7. Wine list teaser — "Biodynamic Italian producers. Ask Marco." with link to a PDF if they want one, but the page is HTML
      8. Reserve CTA strip
      9. Footer
    </sections>
    <primary_cta>Reserve a table</primary_cta>
    <seo_title>Menu — Osteria Lucia, Amsterdam</seo_title>
    <meta_description>Hand-made pasta, biodynamic wine, Northern Italian classics. View our seasonal menu.</meta_description>
  </page>

  <page name="About" route="/about">
    <purpose>Marco's story without putting Marco's face on the page (he's camera-shy).</purpose>
    <sections>
      1. Navigation
      2. Headline + 3-paragraph story: from Bologna, opened 2014, pasta-making philosophy
      3. Photography: kitchen detail shots (hands working pasta, flour on a board), NOT portraits
      4. Wine philosophy — short section on biodynamic producers
      5. Reserve CTA
      6. Footer
    </sections>
    <primary_cta>Reserve a table</primary_cta>
    <seo_title>About — Osteria Lucia, Marco Bellini's Northern Italian Kitchen</seo_title>
    <meta_description>Founded 2014. Hand-made pasta. A small Italian kitchen run with care in Amsterdam.</meta_description>
  </page>

  <page name="Gallery" route="/gallery">
    <purpose>Atmosphere proof. Mixed grid of food + room + hands working — no people facing camera.</purpose>
    <sections>
      1. Navigation
      2. Masonry gallery — 18-24 photos, lightbox
      3. Footer
    </sections>
    <primary_cta>Reserve a table</primary_cta>
    <seo_title>Gallery — Osteria Lucia</seo_title>
    <meta_description>Pasta, wine, candle-lit room. Inside Osteria Lucia.</meta_description>
  </page>

  <page name="Reservations" route="/reserveren">
    <purpose>Reservation page with Resengo widget; phone fallback for accessibility.</purpose>
    <sections>
      1. Navigation
      2. Short hero — "Reserveer een tafel" + one line about typical wait times
      3. Resengo embedded widget (styled wrapper)
      4. Phone fallback — large tappable phone number
      5. Hours table
      6. Footer
    </sections>
    <primary_cta>Resengo widget (primary), phone (fallback)</primary_cta>
    <seo_title>Reserveren — Osteria Lucia Amsterdam</seo_title>
    <meta_description>Online reserveren bij Osteria Lucia. Geopend di–zo voor diner; za–zo ook lunch.</meta_description>
  </page>

  <page name="Contact / Visit" route="/contact">
    <purpose>Wayfinding, hours, accessibility info, contact.</purpose>
    <sections>
      1. Navigation
      2. Address block + embedded map (using lat/lng)
      3. Hours table with current-day highlight
      4. Public transit notes (tram 4, 14, 24 to Rembrandtplein)
      5. Accessibility notes (wheelchair entrance accessible; seating limited)
      6. Phone + email
      7. Footer
    </sections>
    <primary_cta>Reserve a table</primary_cta>
    <seo_title>Contact & Visit — Osteria Lucia, Reguliersgracht Amsterdam</seo_title>
    <meta_description>Reguliersgracht 24, Amsterdam. Tram to Rembrandtplein. Hours below.</meta_description>
  </page>
</page_architecture>

<component_inventory>
  - Navigation (all): sticky transparent-over-hero, becomes solid ivory on scroll; logo center, menu items left/right, Reserve CTA right-most — **custom**
  - Hero (Home): full-bleed photograph, Fraunces headline lower-third, single Reserve button — **custom**
  - Reservation strip (Home): single-line date selector linking to Resengo — **custom**
  - Featured pasta grid (Home): 3 dishes, editorial layout, large photography, brief description — **custom**
  - Trust band (Home): rating + review count + 2 quotes, no avatars — 21st.dev `/ui editorial trust band with rating, review count, and two pull-quote testimonials, no avatars`
  - About strip (Home): two sentences + one photograph — **custom**
  - Hours table (multiple): Mon–Sun grid with current-day highlight — 21st.dev `/ui hours table Mon-Sun with current day highlight in editorial style`
  - Menu list (Menu): editorial menu with category headers, item names with dot leaders to prices, dietary icons — 21st.dev `/ui editorial menu list with category headers, item name dot leaders to price, V vegetarian icon`
  - Masonry gallery (Gallery): masonry grid with lightbox, no filters — 21st.dev `/ui masonry image gallery with lightbox and subtle navigation`
  - Resengo wrapper (Reservations): styled iframe wrapper — **custom**
  - Contact map (Contact): embedded Google Map at 52.3654, 4.8965 — **custom** (use Maps Embed API)
  - Footer (all): address + hours + social icons + newsletter signup — 21st.dev `/ui editorial footer with address block, hours summary, social icons, newsletter signup`
</component_inventory>

<copy_seeds>
  <headline>Pasta gemaakt vanochtend. Wijn gekozen met zorg.</headline>
  <subhead>Een kleine Italiaanse keuken op de Reguliersgracht.</subhead>
  <about_paragraph>Osteria Lucia opende in 2014 toen Marco Bellini Bologna inruilde voor Amsterdam. Pasta wordt elke ochtend met de hand gemaakt. De wijnkaart is klein en biodynamisch — bijna allemaal kleine Italiaanse producenten. Er is geen show; alleen het diner.</about_paragraph>
  <primary_cta>Reserveer een tafel</primary_cta>
  <secondary_cta>Bekijk de menukaart</secondary_cta>
  <microcopy_notes>Dutch primary, English in parentheses where needed. Tone: warm, calm, never enthusiastic-marketing-speak. No exclamation marks. Form placeholders in lowercase ("uw naam", "uw email"). Button verbs are concrete ("Reserveer", "Bekijk", "Bel ons") — never "Click here" or "Learn more".</microcopy_notes>
</copy_seeds>

<imagery_direction>
  <photographic_style>Candle-lit interior shots, hands working pasta on flour, plated food at table level (NOT overhead), wine being poured. Warm color grading: shadows lifted, highlights warm. Slight grain acceptable. NO faces of staff, NO overhead "Instagram food" shots.</photographic_style>
  <subject_priority>1. Food close-ups at table level. 2. Hands at work in the kitchen (no faces). 3. Wine and table details. 4. Candle-lit room. 5. Exterior signage on Reguliersgracht.</subject_priority>
  <treatment>Warm white balance, deep shadows, no HDR, no over-saturation. Photography is the only thing in the design that carries saturated color.</treatment>
  <sourcing>Use the business's Google Maps photos at the source_url as seed references. Strongly recommend a commissioned shoot (half day, food + room + hands) before launch — budget ~€800–€1200 in Amsterdam.</sourcing>
  <avoid>AI-generated abstract gradient blobs, decorative pasta illustrations, stock photography of "Italian chef holding pasta with arms raised", Instagram filter looks (no clarendon, no fade).</avoid>
</imagery_direction>

<deliverables>
  1. globals.css with all design tokens as CSS custom properties (and `.dark` overrides), plus base typography reset (font-faces for Fraunces + Söhne).
  2. tailwind.config.ts mapping the tokens to Tailwind theme keys.
  3. Each page from <page_architecture> as a separate route file (Next.js App Router: app/<route>/page.tsx) or self-contained HTML if running in claude.ai/design.
  4. Shared components in components/ — Header, Footer, Nav, Section primitives, HoursTable, ReservationStrip — typed and reusable.
  5. README.md documenting the design system, archetype choice, and how to extend.
  6. Schema.org JSON-LD: @type Restaurant + servesCuisine "Italian" + acceptsReservations true + priceRange "€€€" + openingHoursSpecification + aggregateRating (4.7, 412) + geo (52.3654, 4.8965) + menu URL.
  7. Open Graph + Twitter Card meta with a generated hero image per page.
  8. Hreflang tags for nl-NL primary, en secondary.
  9. WCAG 2.2 AA: contrast verified on all text pairs, focus rings visible, semantic HTML5 landmarks, alt text on every image, keyboard navigation.
  10. Mobile-first: 375px no horizontal scroll, sticky bottom Reserve CTA on mobile, tap-to-call phone in header.
  11. Performance: hero image ≤ 200 KB WebP/AVIF, total page weight ≤ 1 MB, LCP < 2.5s, CLS < 0.1, INP < 200ms.
  12. GDPR cookie banner — minimal accept/reject, dismissible, ≤ 20% mobile viewport.
</deliverables>

<anti_patterns>
Banned typography (anywhere as primary): Inter, Roboto, Arial, Open Sans, Lato, Space Grotesk, system-ui. Soft ban: Poppins, Montserrat, Raleway.

Banned color patterns: purple/indigo/violet gradients on any background; pure white + pure black (use warm ivory + warm ink); cool corporate blue; Italian-flag green/white/red.

Banned layouts: centered hero with vague subtitle + CTA button; three-icon feature grid ("Fresh ingredients / Cozy atmosphere / Friendly staff"); "Trusted by" greyscale logo bar; faceless 3D character illustrations; identical card grids for every section; uniform border-radius on every component; long-scroll homepage with 12+ sections.

Banned components: bento grid (this is a restaurant, not a tech product); glassmorphism cards; rotating logo carousel; auto-playing video with sound; "Sign up for our newsletter" first-visit modal; sticky banners stacked.

Banned copy: "Revolutionary [thing]", "Experience the difference", "The future of [industry]", "Trusted by thousands" (without specifics), gradient text headlines, vague headlines that don't say what the business does.

Banned imagery: AI-generated abstract gradient blobs; stock photography of "smiling diverse team"; stock food photography; faceless silhouette avatars; generic Unsplash "restaurant interior"; decorative SVG illustrations from undraw.co or storyset; Italian-theme-park iconography (Vespa, Colosseum, checkered tablecloth).

Implementation complexity rule: minimalist designs require restraint and meticulous spacing — not "minimal but with five gradients". The warm-photographic archetype here requires commitment to photography quality — placeholder photography will undermine everything else.

Category-specific bans (restaurants): PDF menu embed (use HTML); auto-playing background video with sound; hero carousel with multiple slides (one strong photo wins); three-icon feature grid; stock photography of clinking glasses.
</anti_patterns>

<internal_notes>
Marco is camera-shy. Keep team photos optional. Prefer photography of food and the room, not people. If forced to show people, use hands-at-work only (no faces).
</internal_notes>

<user_override priority="highest">
Make it feel warm and Italian but not cliché — no checkered tablecloths, no Italian flag colors. Think Carbone NYC meets a Tuscan farmhouse. We want online reservations through Resengo. Bilingual NL/EN.
</user_override>

<instructions>
Generate the deliverables listed in <deliverables>. Start with globals.css (tokens + base typography + font-faces), then build the shared components (Header, Footer, Nav, Section, HoursTable, ReservationStrip), then build each page from <page_architecture> in order. After each page, briefly confirm the section list before moving to the next.

Match <aesthetic_direction> exactly: warm-photographic archetype, Fraunces + Söhne typography, warm ivory + deep wine + burnt copper palette. Use the components in <component_inventory> — when a section says "21st.dev `/ui ...`", insert that as a single-line instruction the user will execute manually in Claude Code with Magic MCP loaded; do NOT fabricate the component code yourself.

Honor <user_override> as the highest-priority signal. Do not introduce any pattern listed in <anti_patterns>. Do not add pages not listed in <page_architecture> (no blog).

When you're done, output a short summary of what was built, the key token choices, and any open questions before launch (especially: real photography, real menu items with current prices, Resengo restaurant ID for the embed).
</instructions>
```

## Next steps

- Iterate in claude.ai/design with comment-level changes ("make the hero photo darker", "move the reservation strip above the featured pasta") — don't regenerate the whole prompt.
- Once the design is approved, export and hand off to Claude Code with `web-artifacts-builder` + `frontend-design` skills to ship as a Vite or Next.js project.
- Before launch: commission real photography, confirm menu prices with Marco, get the Resengo restaurant ID for the embed.
