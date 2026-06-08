# Website Builder — LEARNINGS

Append-only cross-build meta-lessons for the website-builder agent. Phase 8 adds at least one
generalizable lesson per build. The subagent reads this file at startup only if it exceeds 25
lines (the empty scaffold is skipped to save tokens).

## Format

```
## YYYY-MM-DD — <one-line lesson>

**Build:** <which site / design>
**Lesson:** <the generalizable takeaway>
**Apply:** <how future builds should change>
```

## Entries

<!-- Append below. Newest at the top. -->

## 2026-05-22 — Point Playwright's webServer at a production build in sandboxed runs

**Build:** samir-kapsalon
**Lesson:** The default `playwright-user-stories` config runs `npm run dev` as the webServer.
In this sandbox that fails (dev HMR stalls hydration — see the earlier entry), so client-
interaction tests never pass. Setting `webServer.command` to `npx next start -p <port>` (after
a build) gave a clean run: 42/42 passed including the booking-flow interaction.
**Apply:** For Phase 7, when the environment can't run dev HMR, configure Playwright's webServer
to serve a production build. Also: Pixel-family devices are Chromium (only `chromium` is usually
installed); iPhone descriptors pull WebKit and fail to launch unless `playwright install webkit`.

## 2026-05-22 — getByRole name match is substring + case-insensitive — use exact for short labels

**Build:** samir-kapsalon
**Lesson:** A language-switch test for the "EN" button also matched the "Open m**en**u" hamburger
(visible only at mobile widths), causing a strict-mode violation on the mobile project only.
**Apply:** For 2-letter / short accessible names (EN, NL, OK), use
`getByRole(role, { name, exact: true })` to avoid accidental substring matches.

## 2026-05-22 — Verify hydration on a production server, not the dev server, in sandboxed/headless browsers

**Build:** samir-kapsalon (Claude Design barbershop)
**Lesson:** In this environment the Playwright/MCP browser cannot complete Next.js dev's HMR
WebSocket handshake (`ws://.../_next/webpack-hmr` → ERR_INVALID_HTTP_RESPONSE). That stalls
client hydration in `next dev`, so client effects (scroll-state header, IntersectionObserver
reveals) never run — looking like a real bug when it isn't. `npm run build` + `next start`
(no HMR) hydrates correctly and is the source of truth for client-behavior checks.
**Apply:** During Phase 6/7, when client interactivity "doesn't work" under Playwright, first
rule out the dev HMR artifact by testing against a production server before changing code.

## 2026-05-22 — Gate scroll-reveal hidden state behind an `html.js` class

**Build:** samir-kapsalon
**Lesson:** Designs that default `.reveal { opacity: 0 }` and rely on JS to add `.is-visible`
leave content invisible for no-JS users/crawlers and look broken in full-page screenshots.
**Apply:** Make the hidden state `html.js .reveal { opacity: 0; ... }` and set
`document.documentElement.classList.add('js')` in an inline script before paint. Content is
visible by default; the reveal is a pure progressive enhancement.

## 2026-05-22 — Self-host fonts the brief names even when they're not on Google Fonts

**Build:** samir-kapsalon (Anton display + Switzer body)
**Lesson:** Switzer (the brief's body font) is on Fontshare, not Google Fonts. Fetched the 4
weight woff2 files from the Fontshare CDN (protocol-relative `//cdn.fontshare.com/...` URLs)
and wired them via `next/font/local`. Anton came from `next/font/google`.
**Apply:** Don't substitute a Google "close enough" font when the brief names a specific one —
download the woff2s and self-host with next/font/local to stay faithful and avoid the AI-default
font ban.
