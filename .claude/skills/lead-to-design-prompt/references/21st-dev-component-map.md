# 21st.dev Component Map

21st.dev is an AI-curated marketplace of shadcn/Tailwind-compatible React components. The **Magic MCP** server gives Claude Code a `/ui` slash command that generates 1+ variations of any component from a natural-language description.

When generating the `<component_inventory>` block of a design prompt, use the table below to choose between:
- **custom** — build from scratch (use when the component is brand-defining, e.g., the hero)
- **21st.dev `/ui ...`** — defer to a 21st.dev component (use when the component is utilitarian, e.g., footer, testimonial carousel)

## Why mix both

21st.dev components are well-built but recognizable. Use them for the **utility** sections so you save effort; build **brand-defining** sections custom. This is the same principle agencies follow: don't reinvent the footer, but never use a stock hero.

## Magic MCP setup (one-time, for the user)

```bash
npx @21st-dev/magic@latest API_KEY="your-key-here"
```

This adds Magic MCP to `~/.claude/mcp_config.json`. Inside Claude Code, the user then types `/ui` followed by a natural-language description, and Magic returns multiple variations.

In the generated design prompt, write component references in this exact format so the downstream user knows what to invoke:

```
Testimonials (Home): 21st.dev `/ui editorial testimonial carousel with large pull-quote, small author name, no avatar`
```

## Component mapping by section type

### Heroes — usually CUSTOM

| Section need | Recommendation |
|---|---|
| Restaurant hero, photography-led | **custom** (brand-defining) |
| Salon hero, editorial portrait | **custom** |
| Venue hero, cinematic video | **custom** |
| Cafe hero, lifestyle | **custom** |
| Service business hero, type-driven | 21st.dev `/ui editorial service hero with large headline, subhead, inquiry CTA` |
| Retail hero, product-forward | **custom** |

### Navigation

| Need | Recommendation |
|---|---|
| Sticky transparent-over-hero nav | 21st.dev `/ui sticky transparent navigation that becomes solid on scroll` |
| Editorial top nav with centered logo | 21st.dev `/ui editorial centered-logo navigation with menu items left and right` |
| Mobile menu drawer | 21st.dev `/ui mobile menu drawer with full-height overlay` |

### Menu / services / pricing tables

| Need | Recommendation |
|---|---|
| Restaurant menu, editorial card grid with photo | **custom** (each business's menu is unique) |
| Restaurant menu, list with categories | 21st.dev `/ui editorial menu list with category headers, item name dot leaders to price` |
| Salon services pricing | 21st.dev `/ui pricing table with service categories, durations, prices in editorial style` |
| Venue packages | 21st.dev `/ui package comparison card grid with included items and starting price` |
| Service pricing tiers | 21st.dev `/ui pricing tier cards with feature list, highlighted middle tier` |

### Galleries

| Need | Recommendation |
|---|---|
| Masonry photo gallery with lightbox | 21st.dev `/ui masonry image gallery with lightbox and category filter` |
| Before/after slider | 21st.dev `/ui before-after image slider with handle and category filter` |
| Editorial product grid | 21st.dev `/ui editorial product grid with image, name, price, no hover animations` |
| Carousel | 21st.dev `/ui photo carousel with subtle navigation arrows and dot indicators` |

### Testimonials

| Need | Recommendation |
|---|---|
| Editorial single quote | 21st.dev `/ui editorial testimonial with large pull-quote, small author name, no avatar` |
| Multi-quote carousel | 21st.dev `/ui testimonial carousel with three visible cards and gentle auto-advance` |
| With real photos (venue, fitness, agency) | 21st.dev `/ui testimonial card with portrait, name, role or date, full quote` |

### Team / staff

| Need | Recommendation |
|---|---|
| Editorial team grid | 21st.dev `/ui editorial team grid with portrait, name, role, specialty tags, social link` |
| Single-feature team member | 21st.dev `/ui featured team member card with portrait, biography paragraph, contact` |

### Forms

| Need | Recommendation |
|---|---|
| Reservation form | 21st.dev `/ui restaurant reservation form with date, time, party size, name, email, phone, special requests` |
| Booking widget wrapper | 21st.dev `/ui booking widget wrapper with styled container around iframe` |
| Venue RFP / inquiry | 21st.dev `/ui short RFP form with date, guest count, name, email, phone, optional message — exactly six fields` |
| Service contact form | 21st.dev `/ui contact form with name, email, phone, service select, message, no captcha visible` |
| Newsletter signup | 21st.dev `/ui inline newsletter signup with email input and submit button, no checkbox barrier` |

### Hours / location

| Need | Recommendation |
|---|---|
| Hours table | 21st.dev `/ui hours table Mon-Sun with current-day highlight` |
| Location card with map | 21st.dev `/ui location card with embedded map, address, get-directions button, public transit notes` |
| Multi-location selector | 21st.dev `/ui location selector with dropdown and current selection details` |

### Footers — usually 21st.dev

| Need | Recommendation |
|---|---|
| Editorial footer | 21st.dev `/ui editorial footer with address block, hours table, social icons, newsletter signup` |
| Minimal footer | 21st.dev `/ui minimal footer with copyright, social links, hours` |
| Service footer with sitemap | 21st.dev `/ui service footer with three-column sitemap, contact block, social, newsletter` |

### Specialty

| Need | Recommendation |
|---|---|
| Instagram embed | 21st.dev `/ui instagram feed embed grid showing latest 6 posts` |
| Reservation widget iframe | **custom** (wrap third-party iframe: OpenTable, Resengo, Formitable) |
| Booking widget iframe | **custom** (wrap Treatwell, Salonized, Fresha) |
| Schema.org JSON-LD | **custom** (no UI; data only) |
| Cookie banner | 21st.dev `/ui minimal cookie banner with accept and reject buttons, GDPR-compliant, dismissible` |

## When 21st.dev is the wrong choice

- **Brand-defining sections** — heroes, logo treatment, signature visual moments. These need to feel bespoke.
- **Highly category-specific UX** — a wine list with food pairings, a tasting menu walkthrough, a salon's allergen consultation form. 21st.dev components are generic; this UX needs custom.
- **When you need multi-variation output anyway** — Magic MCP returns multiple variations; useful for exploration but for production you'll pick one and customize it.

## Output convention

Always wrap 21st.dev references in backticks and prefix with `21st.dev`:

✅ `21st.dev /ui editorial footer with address, hours, social, newsletter`
❌ "use a 21st dev component for the footer"
❌ "21st"

This makes it copy-pasteable in Claude Code.
