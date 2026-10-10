# Design Tokens Cheatsheet

A complete website design system in 2026 needs **eight token families**. Emit them in shadcn/ui's CSS-variable shape using OKLCH color values — this is what claude.ai/design and Claude Code with `frontend-design` produce under the hood, so this format gives a clean handoff.

The W3C Design Tokens Community Group's stable 2025.10 spec defines what a "token" is; shadcn/ui defines the wire format that LLMs handle best.

---

## 1. Color — semantic pairs (mandatory shape)

shadcn's convention: every `--name` pairs with `--name-foreground` so text-on-background contrast is guaranteed.

```css
:root {
  /* Base surfaces */
  --background:         oklch(L C H);
  --foreground:         oklch(L C H);

  /* Cards (slightly elevated surface) */
  --card:               oklch(L C H);
  --card-foreground:    oklch(L C H);

  /* Popovers / menus */
  --popover:            oklch(L C H);
  --popover-foreground: oklch(L C H);

  /* Primary action color */
  --primary:            oklch(L C H);
  --primary-foreground: oklch(L C H);

  /* Secondary surfaces / less-emphasis actions */
  --secondary:          oklch(L C H);
  --secondary-foreground: oklch(L C H);

  /* Muted backgrounds + muted text */
  --muted:              oklch(L C H);
  --muted-foreground:   oklch(L C H);

  /* Accent (third color, used sparingly) */
  --accent:             oklch(L C H);
  --accent-foreground:  oklch(L C H);

  /* Destructive / error */
  --destructive:        oklch(L C H);
  --destructive-foreground: oklch(L C H);

  /* Borders, inputs, focus rings */
  --border:             oklch(L C H);
  --input:              oklch(L C H);
  --ring:               oklch(L C H);
}

.dark {
  /* Override the same names with dark-mode values */
}
```

### Why OKLCH (not HEX or HSL)

- Perceptually uniform: equal numeric distance = equal perceived distance
- Wide-gamut native (Display P3, Rec2020)
- Easier to generate accessible variants programmatically
- Endorsed by W3C DTCG 2025.10 spec

### Bind color to mood (not the other way around)

| Mood | Hue family (OKLCH H value) | Example |
|---|---|---|
| Warm earth (restaurant, cafe, venue) | 30–80 (orange-yellow), 0–30 (red-burgundy) | terracotta, oat, deep wine |
| Refined neutral (luxury salon, premium service) | 270–360 (greys with cool bias) or 60–90 (warm bias) | warm white + charcoal |
| Botanical (cafe organic, restaurant farm-to-table) | 130–170 (green) | sage, forest, moss |
| Coastal (venue, cafe coastal) | 200–250 (cyan-blue) — but muted, never saturated | sea-foam, deep navy |
| Bold accent (agency, neon salon) | Single saturated hue + neutral support | electric blue, oxblood, mustard |

### Forbidden color directions

- `--primary: oklch(... 270)` (indigo/violet) on a light background unless the lead's `design_prompt` explicitly requests it
- Pure white (`oklch(100% 0 0)`) on pure black — use `oklch(97% 0.005 60)` cream and `oklch(15% 0.005 60)` ink instead
- All-neutral palettes with no accent at all (the design dies; pick ONE accent)

---

## 2. Typography

### Mandatory pairing

Always specify TWO families minimum:

- **Display** (headlines, hero, large copy)
- **Body** (paragraph, UI, labels)

Optionally a third:
- **Mono** (only if needed for prices, codes, addresses with structured emphasis)

### Type scale

Use a documented scale. Two acceptable approaches:

**Pixel scale (more predictable):**
```
12, 14, 16, 18, 20, 24, 30, 36, 48, 60, 72, 96
```

**Modular scale (more elegant, harder to maintain):**
```
Base 16px, ratio 1.250 (Major Third): 16, 20, 25, 31, 39, 49, 61, 76, 95, 119
```

### Line heights

```
tight   — 1.0–1.2 (headings, display)
base    — 1.5–1.7 (body)
relaxed — 1.6–1.8 (longform editorial)
```

### Letter spacing

```
display  — -0.02em to -0.03em (tightened, optical correction at large sizes)
body     — 0 (default)
eyebrow  — 0.05em to 0.15em (tracked, often uppercase, for category labels)
```

### Banned fonts (anywhere as primary)

**Hard ban**: Inter, Roboto, Arial, Open Sans, Lato, Space Grotesk, system-ui, sans-serif, serif (the literal CSS keyword).

**Soft ban (use only if specifically warranted)**: Poppins, Montserrat, Raleway, Nunito, Source Sans Pro, Work Sans, Great Vibes, Allura, Pinyon Script.

### Recommended display fonts by mood

| Mood | Display options |
|---|---|
| Editorial serif | Fraunces, Cormorant Garamond, GT Sectra, Saol Display, Canela, Tiempos Headline, Recoleta |
| Modern serif | Söhne Schmal, IBM Plex Serif, Source Serif, Lora |
| Characterful sans | Söhne Breit, GT America, PP Mori, Switzer, Manrope, Aktiv Grotesk, Mona Sans |
| Bold display | Druk, Druk Wide, Reckless, GT America Condensed, Tusker Grotesk |
| Hand-set / unique | Marcellus, Cooper Black, Pistilli, Caslon Italic, Hatton |

### Recommended body fonts

Söhne, GT America, Switzer, Manrope, Inter Tight (note: Inter Tight is acceptable as body; original Inter is banned), Aktiv Grotesk, Mona Sans, IBM Plex Sans, Söhne Mono (if mono).

### Source

Always specify the font source: Google Fonts, Adobe Fonts, self-hosted via `@font-face`, or paid subscription (Klim Type Foundry, Pangram Pangram). For commercial use, Google Fonts is safest.

---

## 3. Spacing

Base 4px/8px grid.

```
0   = 0px
1   = 4px
2   = 8px
3   = 12px
4   = 16px
6   = 24px
8   = 32px
12  = 48px
16  = 64px
24  = 96px
32  = 128px
48  = 192px
```

**Section padding (vertical):**
- Desktop: 96–128px
- Tablet: 64–96px
- Mobile: 48–64px

**Container max-width:**
- Standard: 1280px
- Editorial: 1440px or full-bleed with inner container at 1280px
- Reading: 640–720px for longform body copy

---

## 4. Radius

```css
--radius: 0.5rem; /* base */
```

Derived:
```
sm: calc(var(--radius) * 0.5)   /* small UI elements: chips, badges */
md: var(--radius)                /* default buttons, inputs */
lg: calc(var(--radius) * 1.5)    /* cards */
xl: calc(var(--radius) * 2)      /* hero, large panels */
```

### Recommended base by mood

| Mood | --radius |
|---|---|
| Sharp / brutalist / editorial | 0px |
| Subtle / refined | 4px |
| Default / friendly | 8px |
| Soft / cozy | 16px |
| Rounded / playful | 24px |
| Full / pill (only for tags/badges, never globally) | 9999px |

**Rule:** Don't apply the same radius to every component. Cards, buttons, inputs, and images should differentiate. Uniform border-radius is an AI-slop tell.

---

## 5. Shadow

Five elevation levels. Use OKLCH alpha for cleaner gradients.

```css
--shadow-0: none;
--shadow-1: 0 1px 2px 0 oklch(0% 0 0 / 0.05);                                                    /* subtle resting */
--shadow-2: 0 2px 4px -1px oklch(0% 0 0 / 0.08), 0 1px 2px -1px oklch(0% 0 0 / 0.04);             /* cards */
--shadow-3: 0 8px 16px -4px oklch(0% 0 0 / 0.10), 0 4px 8px -2px oklch(0% 0 0 / 0.06);            /* modals, popovers */
--shadow-4: 0 24px 48px -12px oklch(0% 0 0 / 0.18);                                              /* hero, featured */
```

For brutalist / editorial archetypes, often skip shadows entirely. For warm/cozy archetypes, lean into them.

---

## 6. Motion

```css
--motion-fast:    120ms;
--motion-base:    200ms;
--motion-slow:    400ms;
--motion-page:    700ms;

--ease-standard:    cubic-bezier(0.2, 0, 0, 1);
--ease-emphasized:  cubic-bezier(0.3, 0, 0, 1.2);
--ease-decelerate:  cubic-bezier(0, 0, 0.2, 1);
```

### Use motion for

- Page transitions (700ms, decelerate)
- Focus rings (120ms)
- Hover affordances (200ms, standard)
- Scroll-triggered reveals (subtle: max 8px translate + opacity)

### Don't use motion for

- Every element entrance (it's exhausting)
- Parallax on hero (motion-sickness on mobile)
- Auto-playing carousels (annoying, accessibility-hostile)
- Spring-bouncy CSS (it screams "I just discovered Framer Motion")

### Always respect `prefers-reduced-motion`

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 7. Breakpoints

Mobile-first.

```
sm:  640px  (phones landscape, small tablets)
md:  768px  (tablets)
lg:  1024px (small laptops)
xl:  1280px (desktops)
2xl: 1536px (large desktops)
```

Design for 375px width first. Then enhance.

---

## 8. Dark mode

| Category | Dark mode |
|---|---|
| Restaurant — fine dining | Optional (often elevates the brand) |
| Restaurant — bistro / family | Default off |
| Cafe | Often required (matches the lighting) |
| Salon — editorial / luxury | Often required |
| Salon — warm boutique | Default off |
| Venue | Optional (cinematic) |
| Retail — fashion | Often required |
| Retail — warm craft | Default off |
| Service — agency / tech | Always required |
| Service — wellness | Default off |

Implement as a `.dark` selector override on `:root`. Detect `prefers-color-scheme`. Provide a toggle in the footer for user override.

---

## Putting it all together — example

For a fine-dining restaurant in Amsterdam, archetype `editorial-magazine`:

```css
:root {
  /* Color — warm editorial */
  --background:         oklch(98% 0.005 80);    /* warm ivory */
  --foreground:         oklch(20% 0.01 30);     /* deep ink with warm cast */
  --card:               oklch(96% 0.008 80);
  --card-foreground:    oklch(20% 0.01 30);
  --primary:            oklch(28% 0.08 25);     /* deep wine */
  --primary-foreground: oklch(98% 0.005 80);
  --secondary:          oklch(82% 0.02 75);     /* warm stone */
  --secondary-foreground: oklch(20% 0.01 30);
  --muted:              oklch(94% 0.005 80);
  --muted-foreground:   oklch(45% 0.01 30);
  --accent:             oklch(65% 0.12 65);     /* warm copper */
  --accent-foreground:  oklch(20% 0.01 30);
  --destructive:        oklch(50% 0.18 25);
  --destructive-foreground: oklch(98% 0.005 80);
  --border:             oklch(88% 0.01 80);
  --input:              oklch(94% 0.005 80);
  --ring:               oklch(65% 0.12 65);

  /* Typography */
  --font-display: "Fraunces", Georgia, serif;
  --font-body:    "Söhne", "Inter Tight", system-ui, sans-serif;

  /* Radius — refined */
  --radius: 4px;

  /* Motion */
  --motion-fast: 120ms;
  --motion-base: 200ms;
  --motion-slow: 400ms;
  --motion-page: 700ms;
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
}
```

In the generated prompt, do NOT dump the full CSS. **Describe** the tokens in shadcn-style variable names + OKLCH values + 1-line rationale per family. The downstream Claude fills in the details consistently.
