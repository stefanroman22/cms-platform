# Category Playbook: Professional Services (Fallback)

For: consultants, accountants, lawyers, agencies (marketing/design/dev), tradespeople (plumbers, electricians, contractors), fitness studios/yoga/personal training, dentists/clinics, photographers, real-estate, financial advisors, anything that doesn't fit the more specific categories.

This is the **fallback** bucket. If a more specific category fits (restaurant, cafe, salon, venue, retail), use that one.

## Required pages

The exact list depends on the sub-type. Pick from:

1. **Home** — hero + value prop + services overview + social proof + CTA + footer (always)
2. **Services** — what they do, in detail, grouped if multi-service
3. **About / Team** — bios with photos, credentials, philosophy
4. **Work / Case studies / Portfolio** — for agencies/photographers/contractors/architects
5. **Contact** — form + phone + email + address + hours (always)
6. **Pricing** (optional) — for transparent service businesses; some sub-types intentionally hide pricing
7. **FAQ** — if they get the same questions repeatedly
8. **Blog / Insights** — ONLY if they actually publish (don't add empty blog scaffolding)

### Sub-type specific page additions

- **Consultants / Agencies**: Case studies, Portfolio, Process
- **Trades**: Service areas (geographic), Emergency contact, Reviews
- **Fitness studios**: Class schedule, Trainer team, Membership/pricing, Booking
- **Clinics**: Services, Practitioners, Insurance accepted, Book appointment
- **Photographers**: Portfolio by category (wedding/portrait/commercial), Investment/Pricing, Inquiry form
- **Real estate**: Listings, Agents, Sold portfolio, Contact

## Aesthetic archetypes (pick ONE)

### `expressive-minimalism` — agency, consultant, modern service
- Type: characterful sans display (Söhne Breit, GT America, PP Mori, Switzer) + clean body
- Color: confident high-contrast palette — off-black + warm white + one bold accent (oxblood, electric blue, mustard, deep green)
- Layout: large typography as architecture, generous whitespace, bold but restrained
- Examples: Linear, Vercel, Pentagram, Stripe (B2B), Basecamp

### `editorial-confident` — law firm, financial advisor, premium consultant
- Type: refined serif (Tiempos Headline, Saol Display, GT Sectra) + clean grotesque body
- Color: warm white, deep ink, navy, single restrained accent (burgundy, brass)
- Layout: editorial, classical proportions, photography-led for team
- Examples: Hogan Lovells, Brunswick Group, McKinsey

### `technical-utilitarian` — engineering, tradespeople, technical services
- Type: clean grotesque (Söhne, GT America, Aktiv) + monoweight body
- Color: neutral palette + single bright accent (safety orange, electric yellow, deep red)
- Layout: tight, no-nonsense, function-led
- Examples: Linear (for SaaS feel), local trade websites done right

### `warm-human` — coach, therapist, yoga studio, wellness
- Type: humanist serif (Lora, Source Serif, Tiempos Text) + warm sans (Switzer, Manrope)
- Color: cream, terracotta, sage, deep wine, soft naturals
- Layout: photography-led, generous whitespace, soft motion
- Examples: Headspace, Calm, local independent therapy/yoga sites

### `studio-portfolio` — photographer, designer, architect, creative
- Type: minimal serif or characterful sans + body
- Color: warm white or off-black + single accent
- Layout: portfolio-first, photography or work is the design
- Examples: Studio Joost Grootens, Mr Porter, Pentagram

## Color guidance — what NOT to use

- ❌ Stock corporate blue (LinkedIn-blue is the single most generic service-business default)
- ❌ Purple/indigo gradients
- ❌ Three-icon feature row with stock icons
- ✅ Confident palette appropriate to the sub-type

## Typography — banned

Inter, Roboto, Arial, Open Sans, Lato, Space Grotesk, system-ui, Poppins, Montserrat, Raleway (every consultant uses Raleway, please don't).

## Reference brands

By sub-type:
- Agencies/consultants: Linear, Vercel, Pentagram, Stripe, Basecamp, Wieden+Kennedy
- Law/finance: Brunswick, Hogan Lovells, Bain
- Trades: avoid most trade websites; reference instead Linear/Stripe for clarity
- Fitness/wellness: Equinox, Y7 Studio, Modo Yoga
- Photographers: Mr Porter, Studio Joost Grootens (for editorial discipline)

## 21st.dev component hooks

- Hero: `/ui service business hero with large headline, subhead, and inquiry CTA`
- Services grid: `/ui editorial services grid with icon or photo, headline, description`
- Case studies: `/ui case study card with project image, client name, outcome metric`
- Team grid: `/ui team grid with portrait, name, role, short bio`
- Inquiry form: `/ui contact inquiry form with name, email, phone, service interest, message`
- Footer: `/ui professional footer with services list, contact, social, newsletter`

## Required components

- **Clear value proposition in the hero** (this sub-type lives on the hero copy)
- **Real team photos** with names + roles (not faceless silhouettes)
- **Contact form** with phone fallback
- **Social proof** — testimonials, case studies, OR named clients (but only with permission)

## SEO and structured data

- `@type: ProfessionalService` (sub-class of `LocalBusiness`)
- Sub-types where applicable: `LegalService`, `AccountingService`, `MedicalBusiness`, `HealthAndBeautyBusiness`, `Photograph`, `RealEstateAgent`, `HomeAndConstructionBusiness`
- `serviceArea` if geographically constrained
- `priceRange` if relevant
- `aggregateRating` if available

## Mobile considerations

- ~60–70% mobile traffic (lower for B2B agencies, higher for trades)
- Contact CTA must be sticky on mobile for trades (someone needs a plumber NOW)
- For agencies, hover-driven interactions must have mobile equivalents

## Category-specific anti-patterns

- ❌ Stock photography of "diverse team in meeting room" (it's transparently fake)
- ❌ "Trusted by" logos without permission
- ❌ Vague taglines ("We help businesses grow")
- ❌ Three-icon feature row ("Strategy / Execution / Results")
- ❌ Faceless silhouette avatars for team members
- ❌ Massive footer with 8 columns of useless links
- ❌ Cookie banner that takes 30% of the viewport on mobile
- ❌ AI-generated abstract gradient blobs as decoration
