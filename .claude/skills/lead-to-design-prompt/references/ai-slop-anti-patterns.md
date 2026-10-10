# Anti-AI-Slop Anti-Patterns

This file is embedded **verbatim** in the `<anti_patterns>` block of every generated prompt. It encodes the specific defaults Claude collapses to when asked to "make a website", and gives the downstream model a literal list to avoid.

The "AI slop" phenomenon is real and documented. The causal chain: Tailwind's original `bg-indigo-500` demo → templates copied that → LLM training data over-represented it → models default to purple-blue gradients, Inter font, centered hero, three-card grid. Adam Wathan (Tailwind creator) publicly apologized in August 2025. Anthropic's own `web-artifacts-builder` skill warns: *"VERY IMPORTANT: To avoid what is often referred to as 'AI slop', avoid using excessive centered layouts, purple gradients, uniform rounded corners, and Inter font."*

---

## Banned typography

**Hard ban as primary font:**
- Inter
- Roboto
- Arial
- Open Sans
- Lato
- Space Grotesk (Anthropic's frontend-design skill specifically warns about this — Claude over-converges on it as the "non-Inter" default)
- system-ui (the CSS fallback as primary type)
- `sans-serif` (the literal CSS keyword as primary)

**Soft ban (only with specific category justification):**
- Poppins (every generic startup site uses it)
- Montserrat (every generic salon site uses it)
- Raleway (every consultant site uses it)
- Nunito
- Source Sans Pro
- Work Sans
- Great Vibes, Allura, Pinyon Script (every generic wedding site uses these scripts)

---

## Banned color patterns

- Purple-to-indigo gradients on any background
- Indigo-to-blue gradients
- Violet-to-magenta gradients
- Tailwind's default `bg-indigo-500` or `bg-violet-500` as a primary action color
- Pastel-on-pastel glassmorphism (frosted glass cards floating over pastel gradient backgrounds)
- Pure `#FFFFFF` background + pure `#000000` text (too tech; use a warmer pair like `oklch(98% 0.005 80)` cream + `oklch(20% 0.01 30)` ink)
- "Cyber" neon-on-black with electric purple glow

---

## Banned layouts

- Centered hero with a vague subtitle + an "above-the-fold" CTA button
- Three identical icon-card grid below the hero ("Easy / Fast / Reliable", "Strategy / Execution / Results")
- "Trusted by [greyscale logo bar]" without real logos and permission
- Faceless 3D character illustrations holding floating UI elements (the "Notion duck" aesthetic everywhere)
- Identical card grids for every section (cards for testimonials, cards for services, cards for team — same shape, same spacing, same shadow)
- Uniform border-radius (typically 8px) applied to every component
- Long-scroll homepage with 12+ sections (most SMBs need 6–7 max)
- Hero "split layout" with abstract gradient blob on one side and a heading on the other
- Floating dashboard mockups in the hero (this is a B2B SaaS cliché, not an SMB pattern)

---

## Banned components

- Bento grid when content doesn't have ≥ 4 genuinely distinct categories (bento for bento's sake)
- Glassmorphism on every surface — use selectively if at all
- Identical icon style across all components from a single icon library (Lucide/Heroicons everywhere) — mix sources or use bespoke
- Rotating logo carousels (`<marquee>` energy)
- "Sign up for our newsletter" modals on first visit
- Cookie banner that takes >25% of the viewport on mobile
- Sticky banners stacked on top of each other (cookie + promo + newsletter)
- Auto-playing video with sound

---

## Banned copy patterns

- "Revolutionary [thing] for the modern [audience]"
- "We help [audience] [vague verb] their [vague noun]"
- "The future of [industry]"
- "Experience the difference"
- "Elevate your [thing]"
- "Trusted by thousands" (without specifics)
- Gradient text headlines
- Headlines that promise transformation without saying what the business actually does
- Empty hype words: "Innovative", "Cutting-edge", "Seamless", "Game-changing"

---

## Banned imagery

- AI-generated abstract gradient blobs
- Stock photography of "smiling diverse team in conference room"
- Stock food photography (especially for restaurants — use the lead's real food photos)
- Faceless silhouette avatars for team members
- Generic Unsplash "modern office" or "restaurant interior"
- Faces stitched from AI generators
- Decorative SVG illustrations from undraw.co or storyset (you'll recognize them immediately)

---

## Banned layout & responsiveness failures

These are not aesthetic preferences — they are correctness bugs that repeatedly slip through. The generated site MUST NOT exhibit any of them:

- **Horizontal scroll at any viewport width from 320px up.** The page must never overflow horizontally, regardless of layout. Use `min-width: 0` on flex children, `max-width: 100%` on media, and wrap/stack instead of letting content push the viewport.
- **Layout shift on hover.** Hover states must animate only `transform` / `color` / `opacity` / `box-shadow` — NEVER `font-size`, `font-weight`, `padding`, `width`, or anything that reflows text to a new line or moves neighbours. Text jumping on hover reads as glitchy.
- **Sibling cards/items in a row with unequal heights or misaligned internal elements.** Repeated items (service rows, team cards, review cards, pricing cards) must be equal-height with their internal sub-elements aligned on shared baselines, regardless of differing text length. Use `align-items: stretch` + consistent internal slots; do not let one card's price/CTA float to a different vertical position than its neighbour's.
- **Primary CTAs clipped, overflowing, or hidden on mobile.** Every primary action button (Book, Reserve, Contact) must remain fully visible and ≥44px tappable at 375px width.
- **Footers and data tables that don't reflow below `sm`.** Hours tables, price tables, multi-column footers must stack/reflow on small screens — never get cut off or force horizontal scroll.
- **Mobile nav that snaps into existence.** The mobile header/menu open+close must be animated (slide/fade), not an instant appear.
- **A fixed-width control crushing the text beside it in a flex row.** A non-shrinking control (a Select/Selected pill, a price chip, a button) set `flex: 0 0 auto` next to a text column squeezes that text to ~one-word-per-line — or overlaps it — on phones. Give the text column `min-width: 0`, and on small screens collapse the control to an icon-only badge (check/plus) with its text label hidden; keep the labelled control on desktop.
- **A wizard step or success screen that requires scrolling to reach its primary action.** Any multi-step / booking-flow step AND its confirmation/success screen must fit the viewport so the primary action (Continue / Confirm / "manage booking") is fully visible without scrolling. Desktop: a sticky summary/action card. Success screen: a compact centred layout plus `@media (max-height: …)` tiers that progressively shrink type + spacing on short screens.
- **A state swap on selection instead of a cross-fade.** A selectable card whose icon/colour pops instantly (the "+" hard-swaps to a check, the border colour jumps) reads as glitchy. Render both icons stacked in one cell and cross-fade (`opacity` + `scale`) between them while the border/colour transitions; reduced-motion disables it.

---

## Required substitutions — give Claude something to do INSTEAD

| Instead of | Use |
|---|---|
| Purple gradient | Category-bound color: terracotta/wine for restaurants; deep forest/cream for venues; high-contrast B&W + brand accent for salons |
| Inter or system-ui | A paired display + body system from the category playbook (e.g., Fraunces + Söhne) |
| Centered hero with subtitle + CTA | Asymmetric editorial layout — photography weighting one side, type the other — OR full-bleed photography with text overlaid lower-third |
| Three-icon feature grid | A real menu list / real services list / real gallery / real story section |
| "Trusted by" logo bar | Specific testimonial quotes with named real people (and real photos for venues) |
| Uniform 8px border-radius | Differentiated radii: sharp on cards, rounded on inputs, full on chips — bound to archetype |
| Bento grid | Editorial sections with varied widths and tighter, more characterful layouts |
| Stock photography | Lead's own photos (from `source_url` Google Maps as a starting point); flag for commissioned replacement before launch |
| Glassmorphism | Solid color blocks with deliberate spacing and typography hierarchy |

---

## Implementation complexity rule

Match implementation complexity to aesthetic vision:

- Minimalist designs require **restraint and meticulous spacing** — not "minimal but with five gradients", not "minimal but every section has a different animation"
- Bold designs require **committed execution** — not "bold typography but timid color", not "brutalist but soft shadows"
- Editorial designs require **photography of the actual subject** — not "editorial but with abstract AI art instead of food/work/people"

---

## When the lead requests an anti-pattern

If the lead's `design_prompt` field asks for something on this list (e.g., "we love purple gradients!", "use Inter, we love it"):

- **Do not silently refuse.**
- **Do not silently comply.**
- **Translate** the request into the closest non-AI-slop alternative: "deep aubergine + warm cream palette" instead of "indigo-to-violet gradient"; "characterful sans like Switzer or Söhne" instead of "Inter".
- **Note the substitution** in a one-line comment within `<user_override>`.

The bans exist for a structural reason: the goal of this entire skill is to escape AI-slop attractors. Keep them intact and offer alternatives consistent with the spirit of the request.
