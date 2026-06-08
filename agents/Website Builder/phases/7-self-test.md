# Phase 7 — Self-test

**Apply skill:** `playwright-user-stories`.

**Do:**
- Generate `tests/user-stories.md` from `_design-manifest.json`.
- Convert each story to a spec in `tests/e2e/<page>.spec.ts` (accessibility-first selectors).
- Add per-locale smoke tests: each locale root loads, `/` redirects to default locale,
  `<html lang>` matches URL, language switcher preserves path, hreflang tags present.
- Use `127.0.0.1` (not `localhost`) in `playwright.config.ts` baseURL (Windows IPv6 issue).
- Run `npx playwright test`. Fix the SITE, not the test (unless the test is wrong). Never
  weaken assertions to pass.
- If `superpowers` present and the project is non-trivial, consider its subagent-driven
  two-stage review on the generated suite before running.

**Gate:** `npx playwright test` exits 0. If the same test fails 3× with the same root cause,
STOP and ask the user.
