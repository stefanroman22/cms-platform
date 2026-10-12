# Prompt Skeleton

This is the XML template the skill fills in to produce the final design prompt. Every block is mandatory unless marked optional. Order is fixed — Claude was trained on XML structure, and ordering affects generation quality (per Anthropic's prompt-engineering docs, queries-at-the-end improve quality up to 30%; that's why `<user_override>` is last).

Replace `{{double-curly}}` placeholders with values resolved from the lead and the category playbook. Drop any block whose source field is null *except* for the mandatory ones (`<role>`, `<business>`, `<aesthetic_direction>`, `<design_system>`, `<universal_ux_requirements>`, `<commerce_and_forms>`, `<page_architecture>`, `<component_inventory>`, `<deliverables>`, `<anti_patterns>`, `<instructions>`).

The `<commerce_and_forms>` block is category-agnostic and **literal** (like `<universal_ux_requirements>`) — emit it byte-for-byte on every build that has services/a catalogue or any booking/contact form. It encodes shipped-client defaults: a price on every service, email-required/phone-optional forms, desktop steps that never scroll to reach the primary action, a smooth Motion submit→success morph, and mobile multi-step flows that show one section at a time. Never tailor its body to the lead.

The `<universal_ux_requirements>` block is category-agnostic and **literal** — emit it byte-for-byte as written below on every build. It encodes baseline UX behaviours every site must ship: an intro loader, a themed scrollbar, and inter-page fade transitions. Never tailor its body to the lead; only the surrounding design tokens it references (`--accent`, `--background`, `--muted`, `--motion-page`, etc.) are interpreted by the downstream designer.

```xml
<role>
You are an expert frontend designer building a complete, production-grade website for a specific small business. Your job is to produce (1) a complete design system file and (2) every page listed in <page_architecture>, as a single self-contained set of artifacts.

You have strong knowledge of design principles, typography, and color theory. You default to safe, generic choices unless explicitly encouraged otherwise. The constraints below exist to push you out of that default. Honor them.

Match implementation complexity to the aesthetic vision. Minimalist designs require restraint and meticulous spacing — not "minimal but with five gradients". Bold designs require committed execution — not timid pastels with one accent color.

Treat <user_override> as the highest-priority signal. When <user_override> conflicts with anything else in this prompt — except <anti_patterns>, which is structural — <user_override> wins.
</role>

<business>
  <name>{{business_name}}</name>
  <category>{{normalized_category}} ({{raw_category}})</category>
  <description>{{description_or_omit}}</description>
  <about>{{about_or_omit}}</about>
  <location>
    <city>{{city}}</city>
    <region>{{region_or_omit}}</region>
    <country>{{country_expanded}}</country>
    <address>{{address_or_omit}}</address>
    <postal_code>{{postal_code_or_omit}}</postal_code>
    <coordinates>{{lat_lng_pair_or_omit}}</coordinates>
  </location>
  <contact>
    <phone>{{phone_or_omit}}</phone>
    <email>{{email_or_omit}}</email>
    <website>{{website_url_or_omit}}</website>
  </contact>
  <social>
    <facebook>{{facebook_url_or_omit}}</facebook>
    <instagram>{{instagram_url_or_omit}}</instagram>
    <menu>{{menu_url_or_omit}}</menu>
  </social>
  <web_presence>{{web_presence_signal}}</web_presence>
  <trust_signals>
    <rating>{{rating_formatted_or_omit}}</rating>
    <!-- Review COUNT must be ROUNDED to "N+" (round down to a clean number: 105 → "100+",
         240 → "200+"), NEVER the exact number — there is no live Google Maps sync, so an
         exact count goes stale and forces the owner to keep editing it. Render every visible
         count ("N reviews", "rated by N", "read all N reviews") as the rounded "N+" form, and
         keep it CMS-editable. The exact integer is used ONLY inside Schema.org aggregateRating
         (which requires a number). Use an exact visible count solely if a real reviews API
         feeds it live. -->
    <review_count>{{review_count_rounded_Nplus_or_omit}}</review_count>
    <selected_reviews>{{top_3_to_5_reviews_or_omit}}</selected_reviews>
  </trust_signals>
  <hours>{{opening_hours_formatted_or_omit}}</hours>
  <google_attributes>{{maps_about_attributes_or_omit}}</google_attributes>
  <languages primary="{{primary_locale}}" switcher="{{yes if >=2 resolved locales, else no}}">{{resolved locales, comma-separated, primary first}}</languages>
</business>

<aesthetic_direction>
  <archetype>{{ONE archetype chosen from the category playbook}}</archetype>
  <one_line_description>{{e.g. "Editorial-magazine warmth: serif display, generous whitespace, photography-led."}}</one_line_description>
  <reference_brands>
    {{2-3 named real-world brands the downstream Claude can interpolate toward — pulled from references/reference-brands-by-category.md}}
  </reference_brands>
  <tone>{{warm | restrained | playful | austere | confident | intimate | bold}}</tone>
  <mood_keywords>{{5-7 evocative single words, comma-separated}}</mood_keywords>
  <anti_references>{{2-3 things this site MUST NOT look like — e.g. "a SaaS landing page", "a generic Squarespace template", "a 2018 startup site"}}</anti_references>
</aesthetic_direction>

<design_system>
  <color>
    <philosophy>{{2-3 sentence color rationale tied to the archetype and category}}</philosophy>
    <semantic_pairs format="shadcn-compatible CSS variables, OKLCH values">
      --background: {{oklch value}};
      --foreground: {{oklch value}};
      --card: {{oklch value}};
      --card-foreground: {{oklch value}};
      --popover: {{oklch value}};
      --popover-foreground: {{oklch value}};
      --primary: {{oklch value}};
      --primary-foreground: {{oklch value}};
      --secondary: {{oklch value}};
      --secondary-foreground: {{oklch value}};
      --muted: {{oklch value}};
      --muted-foreground: {{oklch value}};
      --accent: {{oklch value}};
      --accent-foreground: {{oklch value}};
      --destructive: {{oklch value}};
      --destructive-foreground: {{oklch value}};
      --border: {{oklch value}};
      --input: {{oklch value}};
      --ring: {{oklch value}};
    </semantic_pairs>
    <dark_mode>{{required | optional | not-applicable, with rationale}}</dark_mode>
    <cms_theme_palette>
      Colours: {{named palette in hex, e.g. "Primary #1e5aa8, Accent #c2410c, Ink #1c1917"}}
      Surfaces: {{named backgrounds in hex: Page light, Page dark (if dark mode), Card, Header, Footer}}
      These seed the client's CMS theme (rich-text colour swatches, icon tints); keep them identical
      to the tokens above. Text and icon colours must reach WCAG AA against each surface they sit on.
    </cms_theme_palette>
  </color>

  <typography>
    <philosophy>{{2-3 sentence type rationale tied to the archetype}}</philosophy>
    <display_font>
      family: {{e.g. "Fraunces", "Cormorant Garamond", "GT Sectra", "Söhne Breit"}}
      source: {{Google Fonts (default) | self-hosted woff2 (only when the brief names a non-Google font)}}
      weights: {{only the weights actually used, e.g. 400, 600, 800}}
      italic: {{yes | no — yes only if the design uses italics}}
      use: headlines, large display copy (the CMS theme's heading_font)
    </display_font>
    <body_font>
      family: {{e.g. "Söhne", "GT America", "Inter Tight", "Switzer", "Manrope"}}
      source: {{...}}
      weights: {{only the weights actually used, e.g. 400, 500, 600}}
      italic: {{yes | no}}
      use: body, UI, labels (the CMS theme's body_font)
    </body_font>
    <cms_fonts>The client can switch either font later from their CMS theme; the chosen families are the seed and the bundled fallback, so use Google Fonts families wherever the archetype allows.</cms_fonts>
    <mono_font_optional>{{e.g. "JetBrains Mono" — only if needed for prices/codes}}</mono_font_optional>
    <scale>
      12 / 14 / 16 / 18 / 20 / 24 / 30 / 36 / 48 / 60 / 72 / 96
      OR a modular scale at 1.25 (Major Third) from 16px base
    </scale>
    <line_heights>
      tight (headings): 1.0–1.2
      base (body): 1.5–1.7
      relaxed (longform): 1.6–1.8
    </line_heights>
    <letter_spacing>
      display: -0.02em to -0.03em (tightened)
      body: 0
      labels/eyebrow: 0.05em to 0.15em (tracked, uppercase)
    </letter_spacing>
  </typography>

  <spacing>
    Base: 4px / 8px grid.
    Scale: 0, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192px
    Section padding: 96–128px vertical on desktop; 48–64px on mobile.
    Container max-width: {{e.g. 1280px or 1440px}}.
  </spacing>

  <radius>
    --radius: {{e.g. 0px sharp | 4px subtle | 8px default | 16px soft | 24px rounded}};
    Derived: sm = calc(--radius * 0.5); md = --radius; lg = calc(--radius * 1.5); xl = calc(--radius * 2);
    Rule: do NOT apply the same radius to every component. Differentiate cards from buttons from inputs.
  </radius>

  <shadow>
    Elevation 0: none
    Elevation 1: 0 1px 2px 0 oklch(0% 0 0 / 0.05) — subtle resting
    Elevation 2: 0 2px 4px -1px oklch(0% 0 0 / 0.08), 0 1px 2px -1px oklch(0% 0 0 / 0.04) — cards
    Elevation 3: 0 8px 16px -4px oklch(0% 0 0 / 0.1), 0 4px 8px -2px oklch(0% 0 0 / 0.06) — modals, popovers
    Elevation 4: 0 24px 48px -12px oklch(0% 0 0 / 0.18) — hero / featured
  </shadow>

  <motion>
    Durations:
      --motion-fast: 120ms
      --motion-base: 200ms
      --motion-slow: 400ms
      --motion-page: 700ms
    Easings:
      --ease-standard: cubic-bezier(0.2, 0, 0, 1)
      --ease-emphasized: cubic-bezier(0.3, 0, 0, 1.2)
      --ease-decelerate: cubic-bezier(0, 0, 0.2, 1)
    Use motion for: page transitions, focus rings, hover affordances, scroll-triggered reveals (subtle, ≤ 8px translate), and animated mobile nav open/close (slide or fade — never an instant appear).
    Hover rule (mandatory): hover states animate ONLY transform / color / opacity / box-shadow. NEVER animate font-size, font-weight, padding, or width on hover — anything that reflows text to a new line or shifts neighbours reads as glitchy. Hover transitions are ≥ 200ms ease-out (reserve the 120ms fast tier for focus rings only).
    Avoid: spring-bouncy entrances on every element; parallax on hero; auto-playing carousels.
    Respect prefers-reduced-motion.
  </motion>

  <breakpoints>
    sm: 640px (≥ phones landscape)
    md: 768px (≥ tablets)
    lg: 1024px (≥ small laptops)
    xl: 1280px (≥ desktops)
    2xl: 1536px (≥ large desktops)
    Mobile-first: design for 375px first, then enhance.
  </breakpoints>
</design_system>

<universal_ux_requirements>
  These three behaviours apply to EVERY page on EVERY build, regardless of category. They are
  the brand's UX baseline. Honour them without exception. They use only the design tokens
  defined above, so they recolour automatically per palette.

  <intro_loader>
    Full-screen first-visit splash that plays a single, branded workflow:
    spinner spinning while the site loads → status text + spinner BOTH transition together
    to a "ready" state (text crossfades copy + colour to the brand accent; spinner stops,
    fills with the accent, a checkmark scales in inside it) → the whole field dissolves
    smoothly away → page is revealed. It must look like part of the brand, never trap the
    user, never flash, and never replay needlessly within a session.

    <visual_requirements>
      - Cover the entire viewport, above every other layer (`z-index: 1000`, beats site chrome).
      - Opaque from first paint — the background is the brand's darkest neutral so the page
        underneath is never visible behind a fading overlay. The CONTENTS (wordmark, spinner,
        text) animate in, NOT the background.
      - Three visual elements, vertically stacked, centred, with ~28px gap:
        1. Wordmark / brand mark in the display typeface (uppercase, letter-spaced).
        2. Spinner — thin ring 40–48px diameter, neutral track at α≈0.16, single arc in
           `var(--accent)`, rotating at ~0.85s/turn linear.
        3. Status line — small uppercase (12px, 0.18em tracking), muted on-dark text.
      - DONE state (after page loaded):
          * Status text CROSSFADES from the loading copy to a short welcome line AND shifts
            colour from muted-on-dark to `var(--accent)`.
          * Spinner stops rotating and FILLS with the accent (ring → solid disc) in ~280ms.
          * A checkmark strokes in inside the disc, scaling 0.4 → 1 with opacity 0 → 1 over
            ~380ms, with ~120ms delay so it lands AFTER the fill, not during.
          * The disc may pop very slightly (scale 1.06) to reinforce the success beat.
      - EXIT: the whole splash fades opacity 1 → 0 with a gentle scale 1 → 1.04 over ~600ms
        (revealing the page behind), then is removed from layout.
      - Brand vocabulary: ALL colours come from existing design tokens. NEVER introduce
        ad-hoc hex values. The success moment (filled accent + on-accent foreground check)
        MUST match any other "success" surface the design system already uses.
    </visual_requirements>

    <timing_constants_default>
      Defaults — tune per brand personality (faster for utilitarian/SaaS, slower for
      editorial/luxury). Floors are hard:
        MIN_VISIBLE = 1400ms  (since navigation start; spinner is always appreciated, even on
                               instant loads). Floor: ≥ 800ms.
        Done climax  ≈ 380–500ms total (text swap + spinner fill + check pop)
        DONE_HOLD   = 1300ms  (user reads "welcome" + sees the filled check)
        EXIT        = 600ms   (gradual dissolve into the page)
        MAX_WAIT    = 4500ms  (safety cap — never trap if window.load is slow). Ceiling: ≤ 6000ms.
      Total visible ≈ 3.3s on first visit.
    </timing_constants_default>

    <architecture_locked>
      Implement as THREE coordinating pieces so the framework never owns the DOM the
      controller mutates — this is what prevents hydration flashes.

      1) **Server-rendered markup.** The splash HTML is part of the initial server response,
         with `data-state="loading"` AND both the loading and (initially-aria-hidden) ready
         text spans present. Server-rendered ⇒ visible from first paint, no client-JS
         dependency for APPEARING. In Next.js App Router: a server component imported by the
         locale layout, rendered ABOVE `NextIntlClientProvider` so its strings come from a
         server `getTranslations({ locale, namespace: "loader" })` call.

      2) **Pre-paint inline `<script>`** placed immediately after the splash element in the
         HTML. Synchronously checks `sessionStorage["site:loader-shown"]`; if present, sets
         `data-state="off"` on the splash element BEFORE first paint, so repeat-visit-this-
         session reloads never see it (no flash). Wrap in `try/catch` for private-mode browsers.

      3) **Client-only controller** component that returns `null` (renders no markup) and
         drives the state machine IMPERATIVELY via `document.querySelector` + `setAttribute`.
         Mount it inside the client provider tree. It:
           - Reads `sessionStorage` and short-circuits if `data-state === "off"`.
           - Writes the session flag at start.
           - Listens for `window.load` OR `document.readyState === "complete"`, with a
             `MAX_WAIT` safety timeout.
           - Sequences: enforce `MIN_VISIBLE` since navigationStart → set `data-state="done"`
             (toggle `aria-hidden` on the two text spans so screen readers announce the
             welcome line) → after `DONE_HOLD` set `data-state="hide"` → after `EXIT` set
             `data-state="off"`.
           - Cleans up timers on unmount.

      Because the controller mutates the DOM and the markup is NOT part of any client
      component's render tree, React/Vue/Svelte will not reconcile `data-state`. The
      pre-paint script and the controller never fight each other.
    </architecture_locked>

    <state_model_locked>
      Drive EVERYTHING from a single attribute on the root splash element. Use CSS
      `[data-state="..."]` selectors for every visual change. DO NOT animate via JS.

        data-state="loading" → initial: spinner spinning, loading text visible, ready text aria-hidden
        data-state="done"    → spinner stops + fills with accent, check pops in, text crossfades to welcome
        data-state="hide"    → whole splash fades opacity → 0 with subtle scale 1.04, pointer-events: none
        data-state="off"     → display: none, scroll lock released
    </state_model_locked>

    <theme_integration>
      Map roles → tokens (all defined above in `<design_system>`):

        Splash background                          → `var(--primary)` (darkest brand neutral).
          If `--primary` is too light, invert to the brand's darkest available surface —
          a splash needs clear figure/ground contrast the body content doesn't always have.
        Wordmark + loading text colour             → `var(--primary-foreground)` (on-dark fg).
        Spinner track                              → on-dark fg at α ≈ 0.16.
        Spinner arc + ready text + spinner fill    → `var(--accent)`.
        Checkmark stroke                           → `var(--accent-foreground)` (on-accent fg).
        Wordmark typography                        → `var(--font-display)`, uppercase, letter-spaced;
                                                     fall back to body font at heavy weight.
        Motion easing                              → `var(--ease-standard)` and `var(--ease-emphasized)`.
    </theme_integration>

    <css_skeleton_locked>
      Use this verbatim. Only swap token names if the project spells them differently.

      ```css
      /* Scroll lock while the splash is on. */
      html:has(.page-loader:not([data-state="off"])) { overflow: hidden; }

      .page-loader {
        position: fixed; inset: 0; z-index: 1000;
        display: flex; align-items: center; justify-content: center;
        background: var(--primary);
        color: var(--primary-foreground);
        transition: opacity 600ms var(--ease-standard),
                    transform 600ms var(--ease-standard);
      }
      .page-loader[data-state="off"] { display: none; }

      .loader-inner {
        display: flex; flex-direction: column; align-items: center;
        gap: 28px; padding: 0 24px; text-align: center;
        animation: loader-rise 400ms var(--ease-decelerate) both;
      }
      @keyframes loader-rise {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
      }

      .loader-wordmark { /* var(--font-display), uppercase, ~24–32px, tracking 0.04em */ }

      .loader-spinner {
        position: relative;
        width: 44px; height: 44px;
        border-radius: 50%;
        border: 2px solid /* on-dark fg at α 0.16 — compute via oklch() / rgb()/a */;
        border-top-color: var(--accent);
        animation: loader-spin 0.85s linear infinite;
        transition: background 280ms var(--ease-standard),
                    border-color 280ms var(--ease-standard),
                    transform 320ms var(--ease-emphasized);
      }
      @keyframes loader-spin { to { transform: rotate(360deg); } }

      .loader-check {
        position: absolute; top: 50%; left: 50%;
        width: 22px; height: 22px;
        color: var(--accent-foreground);
        opacity: 0;
        transform: translate(-50%, -50%) scale(0.4);
        transition: opacity 220ms var(--ease-standard) 120ms,
                    transform 380ms var(--ease-emphasized) 120ms;
      }

      .loader-status {
        position: relative; margin: 0; min-height: 1.2em;
        font-size: 12px; font-weight: 600;
        letter-spacing: 0.18em; text-transform: uppercase;
      }
      .loader-text { display: block; transition: opacity 200ms var(--ease-standard); }
      .loader-text--loading { color: /* on-dark fg at α 0.72 */; }
      .loader-text--done    { position: absolute; inset: 0; color: var(--accent); opacity: 0; }

      .page-loader[data-state="done"] .loader-text--loading { opacity: 0; }
      .page-loader[data-state="done"] .loader-text--done    { opacity: 1; }
      .page-loader[data-state="done"] .loader-spinner {
        background: var(--accent);
        border-color: var(--accent);
        animation: none;
        transform: scale(1.06);
      }
      .page-loader[data-state="done"] .loader-check {
        opacity: 1;
        transform: translate(-50%, -50%) scale(1);
      }

      .page-loader[data-state="hide"] {
        opacity: 0;
        transform: scale(1.04);
        pointer-events: none;
      }

      @media (prefers-reduced-motion: reduce) {
        .loader-inner   { animation: none; }
        .loader-spinner { animation: none; }
        .loader-check   { transition-duration: 120ms; }
      }
      ```
    </css_skeleton_locked>

    <markup_skeleton_locked>
      ```html
      <div class="page-loader" data-state="loading" role="status" aria-live="polite">
        <div class="loader-inner">
          <span class="loader-wordmark" aria-hidden="true">{{ BRAND }}</span>
          <span class="loader-spinner" aria-hidden="true">
            <svg class="loader-check" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2.6"
                 stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12.5 L10 17.5 L19 7" />
            </svg>
          </span>
          <p class="loader-status">
            <span class="loader-text loader-text--loading">{{ LOADING_COPY }}</span>
            <span class="loader-text loader-text--done" aria-hidden="true">{{ READY_COPY }}</span>
          </p>
        </div>
      </div>

      <!-- pre-paint short-circuit for repeat visits this session -->
      <script>
        try {
          if (sessionStorage.getItem('site:loader-shown')) {
            var l = document.currentScript.previousElementSibling;
            if (l && l.classList && l.classList.contains('page-loader'))
              l.setAttribute('data-state','off');
          }
        } catch(e) {}
      </script>
      ```

      `{{ BRAND }}` = the wordmark string. `{{ LOADING_COPY }}` and `{{ READY_COPY }}` =
      the two locale-aware status phrases from the i18n catalogue (see `<copy_guidance>`).
    </markup_skeleton_locked>

    <controller_skeleton_locked>
      Imperative state machine — adapt to the framework's lifecycle (e.g. `useEffect` in React,
      `onMount` in Svelte/Vue).

      ```js
      const KEY = 'site:loader-shown';
      const MIN_VISIBLE = 1400, DONE_HOLD = 1300, EXIT = 600, MAX_WAIT = 4500;

      function runLoader() {
        const el = document.querySelector('.page-loader');
        if (!el || el.getAttribute('data-state') === 'off') return;
        try { sessionStorage.setItem(KEY, '1'); } catch {}

        const after = (ms, fn) => setTimeout(fn, ms);
        const finish = () => {
          el.querySelector('.loader-text--loading')?.setAttribute('aria-hidden', 'true');
          el.querySelector('.loader-text--done')?.removeAttribute('aria-hidden');
          el.setAttribute('data-state', 'done');
          after(DONE_HOLD, () => {
            el.setAttribute('data-state', 'hide');
            after(EXIT, () => el.setAttribute('data-state', 'off'));
          });
        };
        const ready = () => after(Math.max(0, MIN_VISIBLE - performance.now()), finish);

        if (document.readyState === 'complete') ready();
        else {
          window.addEventListener('load', ready, { once: true });
          after(MAX_WAIT, ready);
        }
      }
      ```
    </controller_skeleton_locked>

    <copy_guidance>
      Both lines locale-aware, stored in i18n under `loader.loading` and `loader.ready`,
      one entry per locale.

      Loading line (12px, uppercase, letter-spaced, muted on-dark): catchy + on-brand,
      ending in "…". Imply PREPARATION, not literal "loading bar 47%". NEVER use literal
      "Loading…". Suggested seeds by category bucket (pick one and translate per locale):
        restaurants  → "Setting the table…"        / "Tafel dekken…"
        cafes        → "Pulling the first shot…"   / "Eerste shot zetten…"
        salons       → "Setting up the chair…"     / "Even de stoel klaarzetten…"
        retail       → "Unboxing the floor…"       / "Etalage inrichten…"
        venues       → "Polishing the floor…"      / "Vloer poetsen…"
        services     → "Polishing the dashboard…"  / "Dashboard polijsten…"

      Ready line (same style, accent colour): short, warm, brand-voiced welcome, ≤ 25 chars.
      Examples: "Welcome to {{Brand}}.", "Step inside.", "Ready when you are.",
                "Welkom.", "Kom binnen.", "Klaar voor je."

      Route-loader line — a SEPARATE i18n key `loader.routeLoading` (NOT the intro `loading`
      line), shown by the inter-page route loader (see `<companion_behaviours>`). Same
      catchy + on-brand style ending in "…", but framed as work IN PROGRESS during navigation.
      Seeds by category bucket (pick one, translate per locale):
        salons       → "Cutting in progress…"      / "Bezig met knippen…"
        restaurants  → "Plating up…"               / "Aan het opdienen…"
        cafes        → "Brewing your page…"        / "Pagina aan het zetten…"
        retail       → "Restocking the shelf…"     / "Schap aan het vullen…"
        venues       → "Setting the stage…"        / "Het podium klaarzetten…"
        services     → "Crunching the numbers…"    / "Cijfers aan het kraken…"
    </copy_guidance>

    <companion_behaviours>
      - **Scroll lock while up**: handled by the CSS rule
        `html:has(.page-loader:not([data-state="off"])) { overflow: hidden; }`. Falls back
        gracefully where `:has()` isn't supported.
      - **No-JS fallback**: include `<noscript><style>.page-loader{display:none}</style></noscript>`
        so users with JS disabled aren't trapped behind a splash that will never dismiss.
      - **Locale awareness**: render the splash inside the i18n provider so the loading + ready
        copy resolve to the user's saved/active language automatically. Don't reinvent locale
        detection — the URL/cookie the routing layer already resolves IS the saved language.
      - **Bonus — inter-page route loaders**: ship a FIRST-CLASS, FULL-SCREEN-CAPABLE themed
        route loader in the route-segment loading file (`app/[locale]/loading.tsx` in Next.js
        App Router) — NOT a small in-content spinner. It pairs the brand wordmark + a spinner
        (reuse the `loader-spin` keyframe) with a SHORT, business-flavoured status line from a
        DEDICATED i18n key `loader.routeLoading` (NOT the intro loader's `loading` copy).
        Theme to the palette (light theme → light bg + accent spinner; the inverted track is
        for light backgrounds); z-index ABOVE the header & mobile menu so it covers the whole
        navigation; respect `prefers-reduced-motion`. Gives inter-page navigations a branded
        splash without re-mounting the full intro loader.
    </companion_behaviours>

    <accessibility_locked>
      - `role="status"` + `aria-live="polite"` on the splash container.
      - Spinner: `aria-hidden="true"` (decorative).
      - Two text spans, ONLY ONE announced at a time: initial `aria-hidden="true"` on the
        ready span; the controller toggles aria-hidden on `done` so screen readers announce
        the welcome line.
      - Respect `prefers-reduced-motion: reduce`: disable the spin and the rise-in entrance;
        clamp transition durations so the state changes still happen, just instantly.
      - Wordmark inside the splash: `aria-hidden="true"` (decorative — the brand name is
        already in the page chrome).
    </accessibility_locked>

    <adaptation_hooks_allowed>
      The agent IS free to tune per brand:
        - Timing constants (MIN_VISIBLE, DONE_HOLD, EXIT) — within the floor/ceiling above.
        - Spinner size 40–56px; ring thickness 2–3px; arc speed 0.7–1.0s/turn.
        - Entrance animation of `.loader-inner` — default is rise-in; alternatives:
          fade-only, scale-from-95, blur-in (pick what matches the brand's motion language).
        - Exit animation — default is opacity + slight scale 1.04; alternatives: curtain-up
          translateY(-100%), radial mask, blur-out.
        - Wordmark vs. logomark vs. monogram in the centre.
        - The success beat — default is a checkmark; alternatives: a small brand glyph that
          strokes in, or a colour-only fill if the brand avoids icons.

      The agent MUST NOT change:
        - The three-piece architecture (server markup + pre-paint script + imperative client controller).
        - The single `data-state` source of truth.
        - The session-flag short-circuit.
        - The `MAX_WAIT` safety net.
        - The `role="status"` + `aria-live` semantics.
        - The reduced-motion handling.
        - The brand-token mapping (always use existing tokens; never introduce hard-coded colours).
    </adaptation_hooks_allowed>
  </intro_loader>

  <themed_scrollbar>
    The vertical scrollbar must be themed to the site palette on every container that scrolls.
    NEVER rely on the OS/browser default. Specs:
      - WebKit/Chromium (`::-webkit-scrollbar`):
          width: 10px (12px on `lg` and up);
          `::-webkit-scrollbar-track` → `var(--background)` (or `var(--card)` if higher contrast
            is needed against the page);
          `::-webkit-scrollbar-thumb` → `var(--muted)` with `border-radius: var(--radius-sm)`
            and a 2px transparent inset border so the thumb visually inset from the track;
          `::-webkit-scrollbar-thumb:hover` → `var(--accent)`;
          `::-webkit-scrollbar-corner` → transparent.
      - Firefox / standards (on `html` and any inner scroll container):
          `scrollbar-width: thin;`
          `scrollbar-color: var(--muted) var(--background);`
          On hover: bump thumb to `var(--accent)` via a `:hover` override.
      - Apply globally to `html`, AND explicitly on any internal scroll containers (modals,
        side-drawers, long tables, mobile menu, code blocks). Do NOT leave any inner overflow
        container with browser-default scrollbar.
      - Dark mode (if enabled in `<design_system>`): recompute the same token mapping under
        `.dark` so the scrollbar inherits the dark palette automatically.
    Net effect: the scrollbar reads as part of the brand chrome, not as the OS, and tinted
    toward `--accent` on interaction.
  </themed_scrollbar>

  <page_transitions>
    Navigation between pages MUST be a smooth fade-out → fade-in, never a jarring full-document
    swap. Specs:
      - Implementation (Next.js App Router): wrap the locale layout's `{children}` in a small
        client component (`<PageTransition>`) that keys on `usePathname()` and uses
        `motion/react` `<AnimatePresence mode="wait">` with one `<motion.div key={pathname}>`
        applying `initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}`
        and `transition={{ duration: 0.35, ease: [0.2, 0, 0, 1] }}` (uses `--motion-page`).
      - Duration: 300–400ms total — NEVER more than 500ms (feels sluggish on real navigation).
      - Scroll behaviour: scroll-to-top happens AFTER the exit animation completes and BEFORE
        the entering page mounts, so the new page enters at `y=0` already faded out.
      - Gate on pathname equality, NOT full URL equality — same-route hash or search-param
        changes (`?barber=samir`, `#hours`) MUST NOT fade the page; they're in-page state.
      - `prefers-reduced-motion: reduce` → drop the opacity animation, keep the scroll-to-top.
      - Initial visit: the intro loader (see `<intro_loader>`) covers the first reveal — the
        page-transition wrapper itself does NOT animate the initial mount (set `initial={false}`
        on the first render, or guard with a `mounted` flag).
      - No layout shift during the fade: `mode="wait"` ensures the exiting and entering pages
        are never both in the DOM simultaneously. Do NOT use `mode="popLayout"` (causes
        overlapping flashes on slow devices).
  </page_transitions>
</universal_ux_requirements>

<commerce_and_forms>
  Category-agnostic, LITERAL block — emit verbatim on every build that has services / a
  catalogue or any booking/contact form. Encodes hard defaults from shipped client feedback;
  the owner can relax them later, but ship them by default.

  <service_prices_by_default>
    Every service / menu item / catalogue entry (and every bookable service) MUST show a PRICE
    by default. Render it in the card and make it CMS-editable. If the lead has no price, use a
    sensible category-typical placeholder rather than omitting it — the owner removes it if
    unwanted.
  </service_prices_by_default>

  <form_field_requirements>
    In every booking / contact / lead form: EMAIL is required, PHONE is optional. The required
    asterisk and the validation must reflect this (block submit on missing/invalid email; never
    block on a missing phone). Never invert this. Any confirmation / fine-print note on the form
    must reference ONLY the channel actually sent — email (the required field). Never promise SMS
    or other channels that aren't implemented.
  </form_field_requirements>

  <desktop_no_scroll_to_act>
    On desktop (≥768px), every step of a multi-step flow (booking, checkout, wizard) AND its
    primary action (Continue / Submit / Confirm) must be fully visible in the viewport WITHOUT
    scrolling. If content is long, scroll the inner list region — never push the primary action
    below the fold. Do NOT auto-scroll-to-top on step change. Prefer a two-column layout where a
    summary / action panel is fixed and only the content column scrolls.
    The flow shell is a SELF-CONTAINED SCREEN: clear any fixed site header with enough top
    padding that the header NEVER overlaps the shell's top bar / back control, and BOUND the
    shell height to the viewport below that header (height ≈ `calc(100svh − top − bottom)`) so
    the inner regions scroll and the PAGE ITSELF does not. The summary/side panel updates should
    ANIMATE (selected item, date/time lines, total fade/slide in as they change), and step
    content cross-fades on Continue (Motion / `motion/react`).
  </desktop_no_scroll_to_act>

  <smooth_submit_confirm_animation>
    Submit / confirmation states use smooth Motion (import from "motion/react" — NEVER
    framer-motion), not a blocky disabled button. Pattern: on submit show an in-tone loading
    state with an animated spinner; on success the spinner MORPHS into a green check, then the
    confirmation fades in (AnimatePresence + opacity/scale, ~200–350ms). Match the site's tone.
    Respect prefers-reduced-motion (skip the choreography; just swap).
  </smooth_submit_confirm_animation>

  <mobile_one_section_at_a_time>
    On mobile (<768px), multi-step flows (especially booking) show ONE section at a time with
    smooth Motion fade/slide transitions between steps (opacity + small translate, ~200–300ms,
    AnimatePresence mode="wait"), a visible Back control at every stage, and the primary action
    always visible (e.g. a fixed bottom bar) — the user stays roughly fixed and advances
    step-by-step. The active section's content scrolls INTERNALLY (inner scroll): bound the shell
    to the viewport below the fixed header, keep the top bar + bottom action bar fixed, and let
    only the content region scroll — the PAGE itself must not scroll, so the user never scrolls
    the whole page to reach later fields (dates/times). Same height-bounded model as desktop.
    The RUNNING SELECTION (every pick made so far — e.g. service · professional · date/time + total)
    must stay visible AT ALL TIMES on mobile (e.g. a persistent summary / ticket in the fixed
    bottom bar) and fill in as the user selects — including on the final step — so the user can
    always see what they've chosen, the same way the desktop summary panel does.
  </mobile_one_section_at_a_time>
</commerce_and_forms>

<page_architecture>
  {{For each required page from the category playbook, in order:}}
  <page name="{{Page name}}" route="{{/route}}">
    <purpose>{{1-line purpose}}</purpose>
    <sections>
      1. {{Section 1, e.g. "Hero — full-bleed photo + asymmetric title"}}
      2. {{Section 2}}
      3. {{...}}
    </sections>
    <primary_cta>{{e.g. "Reserve a table"}}</primary_cta>
    <seo_title>{{Title tag, ~60 chars}}</seo_title>
    <meta_description>{{~155 chars}}</meta_description>
  </page>
  {{Repeat for each page}}
</page_architecture>

<component_inventory>
  {{For each unique section/component across all pages, specify whether to build custom or pull from 21st.dev. Format:}}

  - {{Section name}} ({{page(s) where used}}): {{description}} — {{custom | 21st.dev `/ui <prompt>`}}

  {{If `<languages switcher="yes">`, you MUST include a Language switcher component (see the example line below). Omit it entirely when `switcher="no"`.}}

  {{e.g.:
  - Navigation (all): minimal sticky bar, transparent over hero — custom
  - Language switcher (all, if multilingual): compact locale toggle inside the nav, present at every breakpoint incl. the mobile menu; theme-matched (tokens, not a default <select>); switches the `[locale]` route — custom
  - Hero (Home): full-bleed photography, large serif headline lower-third — custom
  - Featured menu (Home, Menu): 3-column editorial grid with photography — custom
  - Testimonial carousel (Home): 3 quotes, large pull-quote, no avatars — 21st.dev `/ui editorial testimonial carousel with large quote and small author name`
  - Hours table (Contact, Footer): Mon–Sun grid with current-day highlight — custom
  - Reservation widget (Reservations): embedded third-party (OpenTable/Resengo/Formitable) — placeholder iframe with styled wrapper
  - Footer (all): address block + hours + social + newsletter — 21st.dev `/ui editorial footer with address block, hours table, social icons, newsletter`
  }}
</component_inventory>

<copy_seeds>
  <headline>{{primary hero headline — short, distinctive, voice-matched}}</headline>
  <subhead>{{1-line supporting line under hero}}</subhead>
  <about_paragraph>{{2-3 sentences rewriting the lead's about/description in the brand voice; do NOT invent facts}}</about_paragraph>
  <primary_cta>{{e.g. "Reserve a table", "Book your appointment", "Plan your wedding"}}</primary_cta>
  <secondary_cta>{{e.g. "View the menu", "Meet our team", "Take the tour"}}</secondary_cta>
  <microcopy_notes>{{1-2 lines on voice/tone for button labels, form placeholders, error states}}</microcopy_notes>
</copy_seeds>

<imagery_direction>
  <photographic_style>{{e.g. "dark moody overhead shots on linen, natural-light close-ups, no faces in chef coats holding food, no stock photography"}}</photographic_style>
  <subject_priority>{{ordered list of what to photograph — e.g. "1. Food close-ups, 2. Room atmosphere, 3. Hands at work, 4. Exterior signage"}}</subject_priority>
  <treatment>{{color grading, contrast, grain, vignette guidance}}</treatment>
  <sourcing>{{e.g. "Use the business's Google Maps photos at {{source_url}} as seed references. Replace with commissioned photography before launch."}}</sourcing>
  <avoid>{{e.g. "AI-generated abstract gradient blobs, decorative SVG illustrations of food, generic Unsplash 'restaurant interior'"}}</avoid>
  <image_slots>
    Every image and illustration is a client-replaceable CMS image slot. List each slot as:
    {{page / section — subject + art direction — pixel size at 2× the rendered slot (e.g. full-width banner 1600×600, card 800×600, avatar 400×400)}}.
    Design each slot to hold any photo the owner uploads at that aspect (object-fit cover, no text
    baked into the image). Placeholder art is fine as the seed; the owner replaces it. Only the
    favicon and the generated OG images are fixed.
  </image_slots>
  <icons>
    Use ONE consistent icon set (Lucide or a matching line set) as separate single-colour SVG
    elements. Every content icon (on services, features, items, contact methods and the like) is
    a client-replaceable, recolourable CMS icon slot; note the surface (Page light, Card, Header,
    …) each one sits on. UI-control icons (menu, close, chevrons, arrows, spinners, form
    affordances) stay fixed in code. No icons baked into images, no icon fonts.
  </icons>
</imagery_direction>

<deliverables>
  1. **globals.css** containing all design tokens as CSS custom properties (and `.dark` overrides if dark mode is enabled), plus base typography reset.
  2. **tailwind.config.{ts,js}** (if using Tailwind) mapping the tokens to Tailwind theme keys (colors, fontFamily, borderRadius, boxShadow, transitionTimingFunction).
  3. **Each page from <page_architecture>** as either a separate route file (Next.js App Router: `app/<route>/page.tsx`) or a self-contained HTML artifact if running in claude.ai/design.
  4. **Shared components** in `components/` — Header, Footer, Nav, Section primitives, Card variants — typed and reusable.
  5. **README.md** documenting the design system, the archetype choice, the token rationale, and how to extend.
  6. **Schema.org JSON-LD** embedded in `<head>` of every page: appropriate LocalBusiness sub-type ({{Restaurant | HairSalon | EventVenue | CafeOrCoffeeShop | Store | ProfessionalService}}), with name, address, telephone, openingHours, aggregateRating, geo (if coords present). `aggregateRating.reviewCount` is the exact integer (schema requires a number); every VISIBLE review count must instead use the rounded "N+" form (see `<review_count>`) — so split the two: a numeric `reviewCount` for the JSON-LD, a rounded display string for the UI.
  7. **Open Graph + Twitter Card meta** with a generated hero image per page.
  8. **Hreflang tags** if multilingual (e.g., `nl-NL`, `en`).
  9. **Accessibility**: WCAG 2.2 AA contrast on all text, visible focus rings, keyboard navigation across all interactive elements, alt text on every image, semantic HTML5 landmarks (`<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<footer>`).
  10. **Mobile-first (hard requirements, verify at 375px / 768px / 1024px)**:
      - ZERO horizontal scroll at any width from 320px up — no exceptions.
      - Every primary CTA (Book/Reserve/Contact) fully visible and ≥ 44px tappable at 375px.
      - Footers, hours tables, and price tables reflow/stack below `sm` — never clipped.
      - Sibling cards/rows are equal-height with internal elements aligned on shared baselines regardless of text length.
      - Include a dev-only responsive-preview control (viewport toggle: 375 / 768 / 1024 / full) in the build so the owner can verify responsiveness without browser devtools.
  11. **Performance budget**: hero image ≤ 200 KB (WebP/AVIF), total initial page weight ≤ 1 MB, Core Web Vitals green (LCP < 2.5s, CLS < 0.1, INP < 200ms). Every image slot has fixed `width`/`height` at its `<image_slots>` size, so a replaced image never shifts layout.
  12. **GDPR cookie banner** (EU-required) if any analytics/tracking is added — basic accept/reject, not a wall.
  13. **Global UX chrome** implementing `<universal_ux_requirements>` verbatim:
      - **First-visit splash loader** — THREE coordinating pieces (this architecture is locked):
          a. `components/chrome/IntroLoaderMarkup.tsx` — SERVER component that renders the
             splash markup with `data-state="loading"` + both text spans, using strings from
             `getTranslations({ locale, namespace: "loader" })`. Imported by the locale
             layout ABOVE `NextIntlClientProvider` so it's in the first server response.
          b. Inline pre-paint `<script>` rendered immediately after the splash markup
             (inside the same server component). Synchronously reads
             `sessionStorage["site:loader-shown"]` and sets `data-state="off"` before
             first paint on repeat-visit-this-session loads. Wrap in try/catch.
          c. `components/chrome/IntroLoaderController.tsx` — CLIENT component, returns null,
             mounted inside the client provider tree. Drives the state machine imperatively
             via `document.querySelector` + `setAttribute` (no React-owned DOM).
        Strings live under the i18n `loader.*` namespace with `wordmark`, `loading`, `ready`
        keys per locale.
      - **Themed scrollbar styles** in `globals.css` — WebKit `::-webkit-scrollbar`
        pseudo-elements + Firefox `scrollbar-width` / `scrollbar-color`, applied to `html`
        AND every inner scroll container (modals, drawers, tables, mobile menu).
      - **Page-transition wrapper** — `components/chrome/PageTransition.tsx`, a CLIENT
        component using `motion/react` `<AnimatePresence mode="wait">` keyed on
        `usePathname()`, 300–400ms opacity fade. Gated on PATHNAME equality only so
        hash/search-param changes do NOT trigger it. Wraps `{children}` in the locale layout.
      - **Route-segment loader** — `app/[locale]/loading.tsx`, a FIRST-CLASS,
        FULL-SCREEN-CAPABLE themed splash for inter-page navigations: brand wordmark +
        spinner (reuse the `loader-spin` keyframe) + a short business-flavoured status line
        from the dedicated `loader.routeLoading` i18n key (NOT the intro `loading` copy),
        themed to the palette, z-index ABOVE the header & mobile menu, reduced-motion respected.
      - **No-JS fallback**: `<noscript><style>.page-loader{display:none}</style></noscript>`
        in `<head>` so JS-disabled users aren't trapped behind a splash that never dismisses.
      All of the above are mounted/configured in the locale layout ONCE, not per-page.
  14. **Language switcher** — ONLY if `<languages switcher="yes">`. A `LocaleSwitcher` mounted in the primary nav/header, rendered at EVERY breakpoint (desktop / laptop / tablet / mobile — including inside the mobile menu/drawer). Styled entirely from design tokens (display/body font, `--accent`, `--radius`, `--motion-*`) so it reads as site chrome — NEVER a browser-default `<select>`. Switches locale via the `next-intl` `[locale]` route segment, preserves the current path, marks the active locale, and keeps `hreflang` + `<html lang>` in sync. If the site is single-language (`switcher="no"`), OMIT this entirely.
  15. **Commerce & forms defaults** implementing `<commerce_and_forms>` verbatim — ONLY if the site has services/a catalogue or any booking/contact form: a CMS-editable price on every service/menu item; email-required + phone-optional on every form; desktop multi-step flows where the step content scrolls but the primary action stays visible (prefer a sticky summary/action column); a Motion submit→success morph (spinner → green check → fade, `motion/react`); and mobile multi-step flows showing one section at a time with fade/slide transitions, a Back control, and a sticky action bar.
  16. **CMS-ready look** — every image and illustration is a slot from `<image_slots>` at its stated size (only the favicon and OG images are fixed); every content icon a separate single-colour SVG from one set (`<icons>`; UI-control icons stay fixed); fonts load from Google Fonts with only the weights used; README.md lists the `<cms_theme_palette>` colours and surfaces and the display/body fonts so they seed the client's CMS theme. Rich text may later carry client-chosen colours, fonts and sizes, so body and heading styles must not depend on one exact colour or size to stay legible.
</deliverables>

<anti_patterns>
{{Embed the full content of references/ai-slop-anti-patterns.md here verbatim. Plus any category-specific bans from the playbook.}}
</anti_patterns>

<internal_notes>
  {{Stefan's free-text notes field, only if non-empty. These are admin-side hints — incorporate where natural but they do not override <user_override>.}}
</internal_notes>

<user_override priority="highest">
{{The lead's design_prompt field, verbatim. If null, leave this block empty but keep the tag.

This is the business owner's hand-written brief. It supersedes the aesthetic_direction, design_system defaults, copy_seeds, and component_inventory above whenever they conflict — except <anti_patterns>, which is structural and never overridden.

If the user_override appears to request an anti-pattern (e.g., "I love purple gradients"), do not silently refuse — translate the request into a non-AI-slop alternative consistent with the spirit (e.g., a deep aubergine + warm cream palette instead of an indigo-violet gradient) and explain the substitution in a one-line comment within this block.}}
</user_override>

<instructions>
Generate the deliverables listed in <deliverables>. Start with globals.css (tokens + base typography + the themed scrollbar from <universal_ux_requirements>), then the global UX chrome (`IntroLoader`, `PageTransition`) and shared components, then build each page from <page_architecture> in order. After each page, briefly confirm the section list before moving to the next.

Implement <universal_ux_requirements> EXACTLY as written — these are non-negotiable, category-agnostic UX baselines. Do not substitute, simplify, or omit the loader, the themed scrollbar, or the page-transition wrapper.

Match <aesthetic_direction> exactly. Use the components in <component_inventory> — when a section says "21st.dev `/ui ...`", insert that as an instruction the user will execute manually (do NOT fabricate the component code).

Honor <user_override> as the highest-priority signal. Do not introduce any pattern listed in <anti_patterns>. Do not add pages not listed in <page_architecture>.

If `<languages switcher="yes">`, implement the Language switcher (deliverable 14) in the nav at every breakpoint — theme-matched and wired to the `[locale]` routing. If `switcher="no"`, build a single-language site with no switcher.

When you're done, output a short summary of what was built, the token choices, and any open questions the user should answer before launch (e.g., real photography, real menu items, booking provider).
</instructions>
```
