---
name: playwright-user-stories
description: Generate user-story-driven Playwright E2E tests for a website. Use to verify the site behaves correctly after implementation — every CTA reaches its destination, every form submits, every page renders. Triggers after a site build is functionally complete, on phrases like "test the site", "user stories", "E2E tests", "verify everything works".
---

# Playwright User Stories

The goal: act as a real user, click everything that should be clickable, fill every form, verify every page renders, produce Playwright spec files the user can re-run.

## Two-step process

1. **Generate `tests/user-stories.md`** — plain-English user stories derived from the design manifest.
2. **Convert each story to a Playwright spec** in `tests/e2e/<page>.spec.ts`.

## Step 1 — User stories

For each page in `_design-manifest.json`, write one story per major user intent. Format:

```markdown
## Home page

### Story: Visitor navigates to pricing from primary CTA
As a visitor on the home page,
When I click the primary CTA in the hero,
Then I should land on /pricing with the pricing table visible.

### Story: Visitor sees all hero content without overflow
As a visitor on the home page at 375px width,
When the page loads,
Then headline, subheadline, primary CTA, and hero image are visible with no horizontal scroll.

## Contact page

### Story: Visitor submits the contact form
As a visitor on /contact,
When I fill name, email, and message and click Send,
Then I see a success state.

### Story: Form rejects invalid email
As a visitor on /contact,
When I enter "not-an-email" and submit,
Then I see an inline error and the form does not submit.
```

Write ONE story per concrete user goal. Don't pad with stories that test the same thing in different ways.

## Step 2 — Playwright specs

For each story, write a spec in `tests/e2e/<page>.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test.describe("Home page", () => {
  test("primary CTA navigates to pricing", async ({ page }) => {
    await page.goto("/");
    await page
      .getByRole("link", { name: /get started|see pricing|view plans/i })
      .first()
      .click();
    await expect(page).toHaveURL(/\/pricing/);
    await expect(page.getByRole("heading", { name: /pricing/i })).toBeVisible();
  });

  test("hero renders without horizontal overflow at 375px", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/");
    const scrollWidth = await page.evaluate(
      () => document.documentElement.scrollWidth
    );
    const innerWidth = await page.evaluate(() => window.innerWidth);
    expect(scrollWidth).toBeLessThanOrEqual(innerWidth);
  });

  test("no console errors during home page load", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(errors).toEqual([]);
  });
});
```

## Selector strategy — accessibility-first

Use Playwright's accessibility-tree selectors. They're stable AND they double as a11y checks (a working selector means the element has an accessible name).

| Preferred | Avoid |
|---|---|
| `page.getByRole("button", { name: /submit/i })` | `page.locator(".btn-primary")` |
| `page.getByRole("link", { name: /pricing/i })` | `page.locator("a.nav-link:nth-child(2)")` |
| `page.getByLabel("Email")` | `page.locator("#email-input")` |
| `page.getByPlaceholder("you@example.com")` | `page.locator("input[type=email]")` |
| `page.getByText(/start free trial/i)` | `page.locator(".cta span")` |
| `page.getByTestId("hero-cta")` | (last resort if no a11y handle) |

CSS selectors break on every Tailwind class change. Accessibility selectors survive refactors.

## `playwright.config.ts`

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:5173",  // 127.0.0.1 over localhost on Windows; Vite dev runs on 5173
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 13"] } },
  ],
});
```

The `127.0.0.1` over `localhost` matters on Windows — Windows can resolve `localhost` to an IPv6 address that Vite doesn't bind to, causing flaky test starts.

## What to test on EVERY build (minimum coverage)

1. **Every page returns 200 and renders the expected H1** — for every locale.
2. **Every nav link reaches the correct destination** — within the current locale (no accidental locale loss).
3. **Every primary CTA reaches its target.**
4. **Every form: happy path + one invalid-input case.**
5. **No horizontal overflow at 375px** on every page.
6. **No console errors** during navigation.
7. **Page title and meta description present** (verifies SEO didn't get skipped).
8. **`/` redirects to `/<default-locale>`** (via react-i18next + URL-segment locale).
9. **`<html lang="...">` matches the URL locale** on every page.
10. **Language switcher preserves the path** — switching `/en/pricing` to NL lands on `/nl/pricing`, not `/nl/`.
11. **hreflang `<link>` tags exist in the document head** on every page, with one entry per locale.

Skeleton for the "every page renders for every locale" test:

```ts
import { test, expect } from "@playwright/test";

const locales = ["en", "nl"];  // EDIT to match src/i18n/config.ts SUPPORTED_LOCALES
const pages = [
  { path: "", h1Patterns: { en: /welcome|hello/i, nl: /welkom|hallo/i } },
  { path: "/about", h1Patterns: { en: /about/i, nl: /over/i } },
  { path: "/pricing", h1Patterns: { en: /pricing|plans/i, nl: /prijzen|tarieven/i } },
  { path: "/contact", h1Patterns: { en: /contact/i, nl: /contact/i } },
];

for (const locale of locales) {
  for (const { path, h1Patterns } of pages) {
    test(`/${locale}${path} renders correctly`, async ({ page }) => {
      const response = await page.goto(`/${locale}${path}`);
      expect(response?.status()).toBe(200);
      // Non-default seed files mirror the default locale; no [XX] placeholders.
      // After CMS connection the CMS auto-translates; before connection, seeds show real copy.
      const pattern = h1Patterns[locale as keyof typeof h1Patterns];
      const h1 = page.getByRole("heading", { level: 1 });
      await expect(h1).toBeVisible();
      const text = await h1.textContent();
      expect(text).toMatch(pattern);
    });
  }
}

test("root redirects to default locale", async ({ page }) => {
  // Via client-side React Router redirect + pre-rendered redirect stub
  await page.goto("/");
  expect(page.url()).toMatch(/\/(en|nl)\/?$/);
});

test("html lang matches locale", async ({ page }) => {
  for (const locale of locales) {
    await page.goto(`/${locale}`);
    const lang = await page.locator("html").getAttribute("lang");
    expect(lang).toBe(locale);
  }
});

test("language switcher preserves path", async ({ page }) => {
  await page.goto("/en/pricing");
  await page.getByLabel(/language/i).selectOption("nl");
  await expect(page).toHaveURL(/\/nl\/pricing/);
});

test("hreflang tags present in head", async ({ page }) => {
  await page.goto("/en");
  for (const locale of locales) {
    const link = page.locator(`link[hreflang="${locale}"]`);
    await expect(link).toHaveCount(1);
  }
});
```

## Run & fix loop

```powershell
npx playwright test
```

If failures:
1. Read the trace: `npx playwright show-trace test-results/<test-name>/trace.zip`.
2. Decide: is the test wrong, or is the SITE wrong?
3. Fix the right thing. **Don't make tests pass by weakening them** (e.g. removing assertions).
4. Re-run.
5. Log non-obvious fixes to `.learnings/failure-modes.md`.

If the same test fails 3 times in a row with the same root cause, STOP and ask the user — something deeper is wrong (test environment, dependency issue, etc).

## Adding `package.json` scripts

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "test:e2e:report": "playwright show-report"
  }
}
```

## When done

1. `npx playwright test` exits with code 0.
2. `tests/user-stories.md` has a summary section at the bottom showing which stories are covered by which spec file.
3. At least one new convention or failure-mode is logged in `.learnings/` from running tests.
