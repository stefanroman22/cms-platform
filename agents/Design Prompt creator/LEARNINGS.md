# Learnings — Design Prompt Creator

> Distilled lessons from feedback Stefan left after reviewing generated
> prompts. Auto-updated by Phase 2 of the agent. Each entry: short,
> sourced (date), generalisable. Per-lead specifics are dropped.

## General

### Universal UX baseline (category-agnostic — every prompt must ship this verbatim)
- (2026-05-23) **First-visit splash loader with filled-check success transition.** Full-screen splash on `var(--primary)`: wordmark in display font + thin ring spinner (40–48px, accent arc, 0.85s/turn) + muted on-dark status line. On page-ready: status text crossfades to accent colour with a short welcome phrase, spinner stops + fills with `var(--accent)` (ring→disc, ~280ms), a checkmark strokes in with scale 0.4→1 + opacity 0→1 (~380ms, +120ms delay so it lands after the fill), disc pops to scale 1.06. Exit fades opacity 1→0 + scale 1→1.04 over ~600ms. Timing constants (defaults): MIN_VISIBLE 1400ms, DONE_HOLD 1300ms, EXIT 600ms, MAX_WAIT 4500ms. **Architecture is LOCKED — three coordinating pieces** so the framework never owns the DOM the controller mutates (prevents hydration flashes): (a) server-rendered markup with `data-state="loading"` in the first HTML response; (b) inline pre-paint `<script>` immediately after the markup that short-circuits via `sessionStorage["site:loader-shown"]` BEFORE first paint; (c) client-only controller returning `null`, mutating the splash imperatively via `document.querySelector` + `setAttribute`. **State model LOCKED** — a single `data-state` attribute drives everything via `[data-state="..."]` CSS selectors: `loading` → `done` → `hide` → `off`. Session-scoped, reduced-motion-safe (disable spin + entrance, clamp transitions), no-JS-safe (`<noscript>` rule hides the splash), `role="status" aria-live="polite"`, two text spans with only one announced at a time. Strings in i18n `loader.{wordmark,loading,ready}`. Loading copy implies preparation, NEVER literal "Loading…" (e.g. salons "Setting up the chair…", restaurants "Setting the table…", cafes "Pulling the first shot…").
- (2026-05-23) **Themed vertical scrollbar.** Match the site palette via `::-webkit-scrollbar` (track = `--background`/`--card`, thumb = `--muted`, thumb-hover = `--accent`, 10–12px width, `--radius-sm` corners) AND Firefox `scrollbar-width: thin; scrollbar-color: ...`. Applied to `html` AND every inner scroll container (modals, drawers, tables, mobile menu). Recomputes under `.dark` if dark mode is enabled. Never the OS/browser default.
- (2026-05-23) **Page-fade transitions on every route change.** Wrap the locale layout's `{children}` in a client `<PageTransition>` using `motion/react` `<AnimatePresence mode="wait">` keyed on `usePathname()`, 300–400ms opacity fade with `var(--motion-page)` / `--ease-standard`. Gate on pathname equality only (hash/search-param changes do NOT fade). Reduced-motion drops the opacity animation, keeps scroll-to-top. Initial mount does NOT fade (the intro loader covers that).
- (2026-05-23) **Where this lives.** Encoded as the literal `<universal_ux_requirements>` block in `references/prompt-skeleton.xml.md` (between `<design_system>` and `<page_architecture>`). The skill's SKILL.md step 11b and the agent's Phase 5 step 6 sanity-check enforce that every emitted XML contains it. The block references only design tokens, so it auto-themes per palette — never tailor its body to the lead.

### Responsiveness (hard requirements — the prompt must mandate these every time)
- (2026-05-22) **Zero horizontal scroll at any width from 320px up.** Never acceptable, no matter the layout. Triggered by: Samir site scrolled horizontally on small screens.
- (2026-05-22) **Every primary CTA fully visible + ≥44px tappable at 375px.** Booking/action buttons were clipped on iPhone SE and ≤768px. Require all CTAs to stay within viewport at the smallest breakpoint.
- (2026-05-22) **Footers and data tables (hours, prices) must reflow/stack below `sm`.** The footer timetable was cut off at 375px.
- (2026-05-22) **Ship a dev-only responsive-preview harness** (viewport toggle 375 / 768 / 1024 / full) in the built page so the owner can sanity-check responsiveness fast. Stefan explicitly asked for this and it surfaced the overflow bugs immediately.

### Motion / hover (the prompt's <motion> block must say this)
- (2026-05-22) **Hover effects must never cause layout shift.** Animate only transform / color / opacity / shadow on hover — NEVER font-size, weight, padding, or width that reflows text to a new line. Text jumping on hover reads as glitchy.
- (2026-05-22) **Hover transitions ≥ 200ms with an ease-out curve.** The default fast (120ms) felt abrupt on service rows. Reserve 120ms for focus rings only.
- (2026-05-22) **Animated mobile nav.** The mobile header/menu must expand/collapse with a smooth transition, not snap into existence.

### Layout alignment & card parity
- (2026-05-22) **Sibling items in a row must be equal-height with aligned internal structure regardless of content length.** Reviews, team cards, and service rows looked misaligned when one had more text than its neighbour. Require CSS grid/flex with `align-items: stretch` + consistent internal slots so the Nth sub-element of every card sits on the same baseline (dynamic spacing keyed to the tallest item in the row). The "Boek" button column already did this correctly — make it the rule for ALL repeated items.
- (2026-05-22) **Proximity grouping for compound list items.** When a list item has multiple parts (service: name + description + duration + price), group them tightly with clear separation between items. The prompt must call out internal grouping AND inter-item separation so the price doesn't float far from its service. Decorative numbering (01, 02…) must sit clear of dividers/images, never overlapping them.
- (2026-05-22) **Center rating/review summary lines with inline parts vertically aligned.** "4.8 / 5 · 105 reviews" type lines need their segments centred and middle-aligned, not left-drifting.

### Copy density
- (2026-05-22) **Concise hero + section copy.** Output came out too verbose. Cap: hero headline ≤ 8 words, hero subhead ≤ 16 words, section intros ≤ 2 short sentences. State these ceilings in copy_seeds so downstream Claude doesn't pad.

### Buttons / contrast
- (2026-05-22) **Secondary buttons over photographic heroes need explicit contrast treatment.** The hero secondary button ("Diensten") was invisible against the photo. Require secondary CTAs on image heroes to use a legible treatment (ghost + backdrop blur, or a muted solid) that is distinct from — but not identical to — the primary button.

### Social proof
- (2026-05-22) **Always link rating/review blocks to the source.** When showing a Google rating + review count, include a "Read all N reviews on Google" link to the lead's `source_url`. Clients want to verify; the prompt should mandate the link whenever reviews are surfaced.

### Motion / structure (the prompt must NAME these required elements — every build)
- (2026-06-18) **Page-change loading transition is a NAMED required element, separate from the intro loader.** The universal `<intro_loader>` covers first visit only. Briefs must ALSO require a branded transition shown on internal route navigation — themed, min-display ~450ms so it never flashes, safety force-hide if a nav never commits, reduced-motion respected. State it explicitly or builds skip it on subsequent navigations. Distinct from `app/[locale]/loading.tsx` (RSC fetch waits) — a brief may name both. Triggered by: CMS frontend motion/perf pass.
- (2026-06-18) **Header entrance + per-word hero headline + scroll-triggered DIRECTIONAL section reveals, all from ONE shared token set.** Require: header logo+nav cascade via a single stagger (the auth/locale/menu cluster does NOT animate); a per-word/per-token hero headline reveal (overlapping beats: eyebrow → headline → subtext → actions); section reveals = fade + 16–40px directional travel, ease-out, fire ONCE on viewport entry; 0.3–0.6s throughout, one easing curve. **Grid/list reveals MUST be one container stagger, never per-card index*delay** (per-card delays leave already-on-screen cards invisible, then popping). 1–2 key elements per view; spend boldness on the hero signature only. Triggered by: CMS frontend motion/perf pass.
- (2026-06-18) **Briefs should set structure expectations, not just visuals.** Require a thin `'use client'` boundary (server-first HTML), one app-level motion provider, and heavy/below-the-fold media (galleries, video, any 3D) lazy-loaded with a space-reserving skeleton + mobile fallback. These complement — never repeat — the `<universal_ux_requirements>` block. Triggered by: CMS frontend motion/perf pass.

## Category: restaurant

(none yet)

## Category: cafe

(none yet)

## Category: salon

- (2026-05-22) Barber/salon service lists read best as grouped editorial rows (name + short description + duration/price tight together), NOT a dense spreadsheet-style table. Triggered by: Samir diensten section felt like a spreadsheet with prices floating away from descriptions.
- (2026-06-17) **Booking briefs must specify these five mechanics (Fresha/Treatwell-grade).** Triggered by: deep iteration on the Samir booking flow. (a) **Week-paginated day picker** — a FIXED 7-day week (CSS grid `repeat(7,1fr)` so it always fits with no horizontal scroll), prev/next arrows on the right of the "Pick a day" header; BACK disabled on the current week (week 0 = today), FORWARD jumps +7 days enabled up to ~6 months out then disabled; sold-out days render but are greyed/disabled; availability fetched per visible week (lazy, refetched on nav, reset to week 0 when service/barber changes); week changes animate as a directional slide (`motion/react` `AnimatePresence` keyed on the week offset, clipped by `overflow-hidden`, reduced-motion → fade). Replaces any long horizontally-scrolling date strip. (b) **Per-card selection cross-fade** — service/professional cards stack a "+" and a "check" icon in one grid cell and fade/scale between them while colour/border transitions, so the check animates in instead of popping (reduced-motion disables). Distinct from the submit→success morph. (c) **Responsive icon-only select control** — a fixed `flex:0 0 auto` Select/Selected pill crushes the text column on phones; the whole card is the tap target, so below `sm` collapse the pill to a compact icon-only badge (hide its label) and put `min-width:0` on the text column; keep the labelled pill on desktop. (d) **Confirmation/success screen that fits every viewport with no scroll** (verified 320→1440) — compact centred layout, `@media (max-height)` tiers that shrink type + spacing on short screens, and on tiny legacy phones (≤360w AND ≤600h) drop only the least-important secondary line; animate (don't pop) the success check. The "manage your booking" link must be its OWN themed, hover-able accent link (`cursor:pointer`), DISTINCT from the "Date & time" detail label — never reuse a detail label as the action link. (e) **First-class localized inter-page route loader** — elevate the App Router route-segment loader (`app/[locale]/loading.tsx`) from an in-content spinner to a full-screen-capable themed splash (brand wordmark + spinner + a short, business-flavoured status line) using a DEDICATED i18n key (e.g. `loader.routeLoading`), NOT the intro loader's copy; theme to the palette, z-index above header + mobile menu, respect reduced-motion. Salon copy: NL "Bezig met knippen…" / EN "Cutting in progress…".

## Category: venue

(none yet)

## Category: retail

(none yet)

## Category: service

(none yet)
