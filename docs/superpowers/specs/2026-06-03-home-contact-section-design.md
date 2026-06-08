# Home-page Contact Section — Design Spec

**Date:** 2026-06-03
**Author:** Stefan Roman (via Claude)
**Status:** Approved (design); pending spec review

## Goal

Add a contact section to the marketing home page (`app/(marketing)/page.tsx`),
placed **before** the pricing section. It contains:

1. A **Calendly calendar** to book a 30-minute appointment with Stefan Roman.
2. A **contact form** (name, email, company *optional*, message) that **actually
   sends** the message to `stefanromanpers@gmail.com`.

Along the way, build reusable pieces (confirmation animation, Calendly widget),
unify the contact form across the Contact page and the home page, and enforce a
global `cursor: pointer` rule for buttons.

## Requirements (from the request)

- New contact section on the home page, **before** `<PricingSection />`.
- Calendly calendar = **reusable** component, themed to the site (gold-on-black),
  using `react-calendly`'s `InlineWidget`. Source URL:
  `https://calendly.com/stefanromanpers/30min`.
- Contact form fields: **name, email, company (optional), message** — same
  styling as the existing Contact page form.
- **One** form component, reused on both the Contact page and the home page.
- All buttons get **`cursor: pointer`**, enforced as a standing project rule.
- On "Send message": a smooth `motion/react` animation — a loading **spinner**
  fades in with text below; when the send actually completes, the text smoothly
  changes **color + content**, and the spinner smoothly **morphs into a
  checkmark**. Spinner and checkmark are **gold** (the `accent` token).
- The confirmation animation is a **reusable** component; the **Contact page
  form uses it too**.
- The form **auto-sends** to `stefanromanpers@gmail.com` when the button is
  clicked (real send, server-side).
- Calendar + form are **side by side on desktop**, stacked on mobile/tablet.
- Components **fade in on scroll into view**.

## Out of scope

- No redesign of the existing Contact page hero or `ContactInfo`.
- No CMS-tenant wiring for this form — it is Roman Technologies' own form, not a
  client project form. (The existing multi-tenant `/forms/{slug}/{form_key}`
  endpoint is left untouched.)
- No changes to pricing, hero, laptop showcase, or about sections.

## Architecture & components

### 1. `components/ui/SubmitFeedback.tsx` — NEW, reusable confirmation animation

Pure presentation; the parent owns the async work and passes state in.

**Props**

```ts
interface SubmitFeedbackProps {
  status: "loading" | "success" | "error";
  loadingText?: string;   // default "Sending your message…"
  successText?: string;   // default "Message sent — talk soon!"
  errorText?: ReactNode;  // default falls back to "email me directly" line
}
```

**Visual / motion (built with `motion/react`)**

- An inline SVG **spinner** (reuse the `ArcSpinner` comet look: dim track ring +
  bright gold arc). While `status === "loading"`, the arc rotates
  (CSS `animate-spin`, immune to React re-renders — same approach as
  `ArcSpinner`).
- On `status === "success"`:
  - rotation stops; the bright arc settles into a **full gold ring**, and a
    **checkmark `<path>` draws in** using motion's `pathLength` (0 → 1) with the
    site easing (`[0.16, 1, 0.3, 1]`). This is the "spinner becomes a checkmark
    smoothly" behavior.
  - the text below **crossfades** (AnimatePresence) from `loadingText`
    (`text-secondary`) to `successText`, animating color to **`accent`** (gold).
- On `status === "error"`: text crossfades to a red message with a mailto
  fallback; spinner stops (no checkmark).
- The whole block fades in (opacity 0 → 1, slight `y`) when it mounts.
- Respects `MotionConfig reducedMotion="user"` (provided by the parent): motion
  keeps fades, drops movement; the rotating spinner is acceptable under reduced
  motion as a busy indicator, but the checkmark still simply fades in.

The spinner→check visual lives inside this file (a small internal `SpinnerCheck`
sub-component). `SubmitFeedback` is the unit reused by both forms.

### 2. `components/contact/ContactForm.tsx` — MODIFIED (one shared component)

Already used on the Contact page and already has the exact field set. Changes:

- Add submit lifecycle state: `phase: "idle" | "sending" | "sent" | "error"`.
- Replace the `mailto:` flow with a real **async POST** to `/api/forms/contact`
  (the Next proxy forwards it to the backend). Body: `{ name, email, company,
  message }`.
- On submit (after the existing client-side `validate()`):
  - set `phase = "sending"`; `AnimatePresence mode="wait"` swaps the `<form>` out
    and a `<SubmitFeedback status="loading" />` in (crossfade).
  - on a successful response → `phase = "sent"`, flip
    `<SubmitFeedback status="success" />` (same mounted block transitions
    loading→success per §1, so the spinner morphs to the gold checkmark and the
    text recolors — one continuous animation).
  - on failure → `phase = "error"`, `<SubmitFeedback status="error" />`.
- Keep the existing "Send another message" reset affordance after success.
- Styling, fields, validation copy, field tokens — **unchanged**.
- Props stay compatible: `{ recipient: string }` (used for the fallback "email
  directly" link). Both call sites already pass `recipient={details.email}`.

This same modified component is what the home section renders — so there is
exactly one form component.

### 3. `components/contact/CalendlyCalendar.tsx` — NEW, reusable

- `"use client"`; follows the pasted scaffold style (imports `cn`, clean props).
- Renders `react-calendly`'s `InlineWidget`.
- **Props**

```ts
interface CalendlyCalendarProps {
  url?: string;        // default "https://calendly.com/stefanromanpers/30min"
  className?: string;
  minHeight?: number;  // default 700
}
```

- **Theme** via `pageSettings` (Calendly hex values, no `#`): dark background
  matched to the surface token, light `textColor`, `primaryColor` = gold
  `c9a961`; `hideEventTypeDetails`/`hideLandingPageDetails` left default.
- SSR-safe: react-calendly is client-only; the component is a client component
  and the widget mounts on the client. (If hydration noise appears, fall back to
  `next/dynamic(..., { ssr: false })`.)
- Wrapper styled to sit inside the section: rounded border + `bg-surface/30`
  card feel consistent with the form card, so the two columns read as a pair.

### 4. `components/contact/ContactSection.tsx` — NEW (home-page section)

- `"use client"` section composing the two reusable pieces.
- Layout: centered eyebrow + heading + subtitle, then a responsive grid:
  - desktop (`lg`): two columns — **Calendly left, ContactForm right**.
  - mobile/tablet: single column, stacked (calendar then form).
- **Scroll-in fade:** wrap the heading block, the calendar, and the form each in
  `Reveal inView` (the existing `components/motion/Reveal`), with small staggered
  delays — matching the pricing section's entrance feel.
- Wrapped in `LazyMotion` + `MotionConfig reducedMotion="user"` like
  `PricingSection`, with the same subtle gold ambient glow on a black background.
- Copy (approved, tweakable):
  - Eyebrow: **Let's talk**
  - Title: **Book a call or send a message**
  - Subtitle: **Grab a 30-minute slot with me, Stefan — or leave your details
    below and I'll reply within one business day.**

### 5. `app/(marketing)/page.tsx` — MODIFIED

Mount `<ContactSection />` **before** `<PricingSection />`:

```tsx
<HeroSection />
<LaptopShowcase />
<ContactSection />
<PricingSection />
```

### 6. `app/globals.css` — MODIFIED (global cursor-pointer rule)

Tailwind v4 preflight sets buttons to `cursor: default`. Add a base layer:

```css
@layer base {
  button:not(:disabled),
  [role="button"]:not([aria-disabled="true"]) {
    cursor: pointer;
  }
}
```

Also saved as a standing **feedback memory** so the rule is applied on all future
work, not just this task.

### 7. Backend — `backend/auth_service/routers/forms.py` — MODIFIED

New endpoint dedicated to the marketing site's own contact form (separate from
the multi-tenant form endpoint):

- Route: `POST /forms/contact` (single path segment — does not collide with the
  two-segment `/{project_slug}/{form_key}`).
- Request model (pydantic): `{ name: str, email: EmailStr, company: str | "",
  message: str, website?: str }` — `website` is a **honeypot** (must be empty).
- Validation: name non-empty, message ≥ 10 chars, valid email. Reject honeypot
  hits with a `200 {success:true}` (silent) to avoid tipping off bots.
- **Rate limiting:** reuse `limiter` keyed by client IP (e.g. `5/10minutes`).
- **Send via Resend:** reuse the existing Resend integration and the
  `_build_email_html` helper (or a small dedicated builder). Recipient is
  `stefanromanpers@gmail.com` (a module constant / settings value);
  `reply_to` = the visitor's email; subject e.g. "New enquiry from {name} —
  romantechnologies.dev".
- **E2E guard:** honor `should_short_circuit` / `short_circuit_response` so
  preview/E2E runs don't actually send (same pattern as `submit_form`).
- **Origin note:** because the browser reaches this through the same-origin Next
  proxy (which forwards only `cookie` + `content-type`, not `Origin`), this
  endpoint does **not** use origin allow-listing. Abuse protection = rate limit +
  honeypot + payload validation. Conscious trade-off for a first-party form.

### 8. `package.json` — add `react-calendly`

Add the dependency (frontend). Lockfile updated via the normal install.

## Data flow (send)

```
[Browser] ContactForm submit
   → fetch POST /api/forms/contact            (same-origin)
   → Next proxy app/api/[...path]/route.ts    (forwards to FASTAPI_URL)
   → FastAPI POST /forms/contact              (validate → Resend)
   → Resend → stefanromanpers@gmail.com
   → {success:true}  ──▶ SubmitFeedback status "loading" → "success"
```

## Error handling

- Client validation runs first (unchanged); only a valid form triggers a send.
- Network/5xx/Resend failure → `phase = "error"` → red message + mailto fallback;
  a "try again" path returns to the form (reuse the reset affordance).
- Backend: 422 on invalid payload, 503 if `RESEND_API_KEY` missing, 502 on Resend
  failure — surfaced to the user as the generic error state.

## Testing

- **Manual / Playwright (frontend):** home page renders the section before
  pricing; Calendly iframe mounts; form validation still blocks empty/invalid;
  on submit the spinner appears, then the gold checkmark + success copy; Contact
  page form shows the same new animation. Use the E2E short-circuit marker so no
  real email is sent.
- **Backend:** unit test the new endpoint — happy path (mocked Resend), honeypot
  silently accepted, validation 422, rate-limit. Reuse existing test patterns for
  `forms.py`.
- Build/lint as a milestone check (not after every change, per project pref).

## Conventions honored

- Animations use `motion/react` (the project standard; same library as Framer
  Motion), not the legacy `framer-motion` import.
- Surgical changes only; existing pricing/hero/about untouched.
- No auto-commit — commit only when Stefan asks.
- Supabase/env-var scoping unaffected (Resend stays on the backend project).
