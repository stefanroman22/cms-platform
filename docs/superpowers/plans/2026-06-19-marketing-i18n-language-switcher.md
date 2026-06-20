# Marketing Site Multilingual Language Switcher — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let visitors read the public marketing site in English, Dutch, or Romanian — auto-defaulting to their country, switchable from the desktop nav, mobile drawer, and footer, on every screen size, with DeepL-generated translations.

**Architecture:** Add `next-intl` with `as-needed` locale-prefixed routing (`/`, `/nl`, `/ro`). Marketing pages move under `app/[locale]/`; the dashboard + booking widget stay physically untouched and locale-free. `middleware.ts` gains a geo-default step (Vercel `x-vercel-ip-country`) composed with the existing auth/legacy logic. All marketing copy is extracted into `messages/{en,nl,ro}.json`; a local DeepL script generates NL/RO for human review. A shared `LanguageSwitcher` renders three brand-matched variants.

**Tech Stack:** Next.js 16.2.5 (App Router), React 19, TypeScript, Tailwind v4, `motion/react`, `next-intl` v4, vitest + @testing-library/react (jsdom), Playwright MCP (live verification), DeepL REST API.

## Global Constraints

- **Library:** `next-intl` v4 (verify exact version compatible with Next 16.2.5 at Task 1). Import path for client hooks is `next-intl`; navigation APIs come from `@/i18n/navigation`.
- **Locales:** exactly `["en","nl","ro"]`; `defaultLocale` = `"en"`; `localePrefix: "as-needed"` (English unprefixed).
- **Locale cookie:** `NEXT_LOCALE` (next-intl's default cookie name). 1-year maxAge, `path:"/"`, `sameSite:"lax"`.
- **Untouched:** no behavior/URL change to `app/dashboard/**` or `app/(widget)/**`. No backend changes. DeepL runs only from a local dev script — never at Vercel build or runtime.
- **Brand tokens:** dark surfaces (`zinc-950`/`#0e0e10`/`black`), gold accent class `text-accent` (#C9A961), Geist font, `motion/react` for animation, **all buttons get `cursor-pointer`** (global rule). Reuse `navLinkCn`, `ctaButtonCn`, `sectionLabelCn` from `@/lib/styles`.
- **No commits unless the user says so** (Stefan's standing rule). The "Commit" steps below are written for completeness; when executing, **stage but do not commit** unless explicitly told to.
- **Surgical edits:** every changed line traces to this feature. Don't refactor adjacent code.

---

## File Structure

**Create**
- `frontend/src/lib/locale.ts` — locale constants, country→locale map, `stripLocale`, `hasLocalePrefix`, native names. Pure, unit-tested.
- `frontend/src/i18n/routing.ts` — next-intl routing definition.
- `frontend/src/i18n/navigation.ts` — typed `Link`/`useRouter`/`usePathname`/`redirect`.
- `frontend/src/i18n/request.ts` — `getRequestConfig` with English deep-merge fallback.
- `frontend/src/i18n/alternates.ts` — `buildAlternates(path, locale)` for hreflang.
- `frontend/src/app/[locale]/layout.tsx` — locale validation, `setRequestLocale`, `NextIntlClientProvider`, `generateStaticParams`.
- `frontend/messages/en.json`, `nl.json`, `ro.json` — message catalogs.
- `frontend/messages/.translation-cache.json` — DeepL source-hash snapshot (committed for incremental runs).
- `frontend/scripts/translate-i18n.mjs` — DeepL generation script.
- `frontend/src/components/i18n/LanguageSwitcher.tsx` — the switcher (nav/drawer/footer variants).
- Tests: `frontend/src/lib/__tests__/locale.test.ts`, `frontend/src/components/i18n/__tests__/LanguageSwitcher.test.tsx`.

**Move (mechanical `git mv`; `@/` imports unaffected)**
- `frontend/src/app/(marketing)/**` → `frontend/src/app/[locale]/(marketing)/**`

**Modify**
- `frontend/next.config.ts` — wrap with `createNextIntlPlugin`.
- `frontend/src/app/layout.tsx` — unchanged `<html lang="en">` (documented why).
- `frontend/src/app/[locale]/(marketing)/providers.tsx` — client `lang` sync effect.
- `frontend/src/middleware.ts` — compose geo + intl + auth.
- `frontend/src/lib/nav-links.ts` and all marketing components/pages listed in Tasks 8–13 — swap literals for `t()`.
- `frontend/src/content/about.json`, `projects.ts` — add stable `id`s; move human copy to messages.

---

## Task 1: next-intl scaffolding + config

**Files:**
- Create: `frontend/src/i18n/routing.ts`, `frontend/src/i18n/navigation.ts`, `frontend/src/i18n/request.ts`, `frontend/src/i18n/alternates.ts`
- Create (seed): `frontend/messages/en.json`, `frontend/messages/nl.json`, `frontend/messages/ro.json`
- Modify: `frontend/next.config.ts`
- Depends on: Task 2's `@/lib/locale` exports — **do Task 2 first** (it's pure + fast), then this task imports from it.

**Interfaces:**
- Produces: `routing` (next-intl routing object, `routing.locales`, `routing.defaultLocale`); `Link, redirect, usePathname, useRouter, getPathname` from `@/i18n/navigation`; `buildAlternates(path: string, locale: Locale)` returning `{ canonical: string, languages: Record<string,string> }`.

- [ ] **Step 1: Install next-intl**

Run from `frontend/`: `npm install next-intl@latest`
Then verify it resolves a version that supports Next 16: `npm ls next-intl` (expect `next-intl@4.x`). If 4.x is incompatible with Next 16.2.5 at install time, pin the latest 4.x that lists Next 16 in its peer range and note it here.

- [ ] **Step 2: Create `src/i18n/routing.ts`**

```ts
import { defineRouting } from "next-intl/routing";
import { LOCALES, DEFAULT_LOCALE } from "@/lib/locale";

export const routing = defineRouting({
  locales: LOCALES,
  defaultLocale: DEFAULT_LOCALE,
  localePrefix: "as-needed",
});
```

- [ ] **Step 3: Create `src/i18n/navigation.ts`**

```ts
import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
```

- [ ] **Step 4: Create `src/i18n/request.ts`** (English deep-merge fallback so a missing NL/RO key never crashes — it shows English)

```ts
import { getRequestConfig } from "next-intl/server";
import { hasLocale } from "next-intl";
import { routing } from "./routing";

async function load(locale: string): Promise<Record<string, unknown>> {
  return (await import(`../../messages/${locale}.json`)).default;
}

// Deep-merge `override` over `base`; arrays and primitives in override win wholesale.
function mergeDeep(
  base: Record<string, unknown>,
  override: Record<string, unknown>
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...base };
  for (const key of Object.keys(override ?? {})) {
    const b = base?.[key];
    const o = override[key];
    out[key] =
      b && o && typeof b === "object" && typeof o === "object" && !Array.isArray(o)
        ? mergeDeep(b as Record<string, unknown>, o as Record<string, unknown>)
        : o;
  }
  return out;
}

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale;
  const en = await load(routing.defaultLocale);
  const messages = locale === routing.defaultLocale ? en : mergeDeep(en, await load(locale));
  return { locale, messages };
});
```

- [ ] **Step 5: Create `src/i18n/alternates.ts`**

```ts
import { routing } from "./routing";
import type { Locale } from "@/lib/locale";

const BASE = "https://roman-technologies.dev";

/** `path` is the locale-less canonical path, e.g. "/" or "/about". */
export function buildAlternates(path: string, locale: Locale) {
  const url = (l: string) =>
    l === routing.defaultLocale
      ? `${BASE}${path}`
      : `${BASE}/${l}${path === "/" ? "" : path}`;

  const languages: Record<string, string> = {};
  for (const l of routing.locales) languages[l] = url(l);
  languages["x-default"] = url(routing.defaultLocale);

  return { canonical: url(locale), languages };
}
```

- [ ] **Step 6: Seed message files** so the app boots before extraction. Write identical minimal content to `messages/en.json`, `messages/nl.json`, `messages/ro.json`:

```json
{
  "common": { "brand": "Roman Technologies" }
}
```

- [ ] **Step 7: Wrap `next.config.ts` with the plugin.** At the top of the file add:

```ts
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");
```

Change the final line from `export default nextConfig;` to:

```ts
export default withNextIntl(nextConfig);
```

Leave all `securityHeaders` / `embeddableHeaders` logic exactly as-is.

- [ ] **Step 8: Verify build compiles**

Run: `cd frontend && npm run typecheck`
Expected: no errors (the config is inert until Task 3 mounts the provider).

- [ ] **Step 9: Stage** (do not commit unless told)

```bash
git add frontend/src/i18n frontend/messages frontend/next.config.ts frontend/package.json frontend/package-lock.json
```

---

## Task 2: Pure locale helpers (TDD)

**Files:**
- Create: `frontend/src/lib/locale.ts`
- Test: `frontend/src/lib/__tests__/locale.test.ts`

**Interfaces:**
- Produces: `LOCALES` (`readonly ["en","nl","ro"]`), `type Locale`, `DEFAULT_LOCALE`, `LOCALE_NAMES: Record<Locale,string>`, `resolveLocaleFromCountry(country: string|null|undefined): Locale`, `isLocale(v): v is Locale`, `stripLocale(pathname: string): string`, `hasLocalePrefix(pathname: string): boolean`.

- [ ] **Step 1: Write the failing test** at `src/lib/__tests__/locale.test.ts`

```ts
import { describe, it, expect } from "vitest";
import {
  resolveLocaleFromCountry,
  stripLocale,
  hasLocalePrefix,
  isLocale,
  DEFAULT_LOCALE,
} from "@/lib/locale";

describe("resolveLocaleFromCountry", () => {
  it("maps NL→nl, RO→ro", () => {
    expect(resolveLocaleFromCountry("NL")).toBe("nl");
    expect(resolveLocaleFromCountry("RO")).toBe("ro");
  });
  it("maps Dutch/Romanian-adjacent countries", () => {
    expect(resolveLocaleFromCountry("BE")).toBe("nl");
    expect(resolveLocaleFromCountry("MD")).toBe("ro");
  });
  it("is case-insensitive", () => {
    expect(resolveLocaleFromCountry("nl")).toBe("nl");
  });
  it("falls back to English for unknown/empty", () => {
    expect(resolveLocaleFromCountry("US")).toBe(DEFAULT_LOCALE);
    expect(resolveLocaleFromCountry(null)).toBe("en");
    expect(resolveLocaleFromCountry(undefined)).toBe("en");
    expect(resolveLocaleFromCountry("")).toBe("en");
  });
});

describe("stripLocale", () => {
  it("removes a leading locale segment", () => {
    expect(stripLocale("/nl/about")).toBe("/about");
    expect(stripLocale("/ro/team")).toBe("/team");
  });
  it("returns / for a bare locale root", () => {
    expect(stripLocale("/nl")).toBe("/");
  });
  it("leaves unprefixed paths untouched", () => {
    expect(stripLocale("/about")).toBe("/about");
    expect(stripLocale("/")).toBe("/");
  });
});

describe("hasLocalePrefix / isLocale", () => {
  it("detects a locale prefix", () => {
    expect(hasLocalePrefix("/nl/about")).toBe(true);
    expect(hasLocalePrefix("/about")).toBe(false);
    expect(hasLocalePrefix("/")).toBe(false);
  });
  it("isLocale guards membership", () => {
    expect(isLocale("ro")).toBe(true);
    expect(isLocale("de")).toBe(false);
    expect(isLocale(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Run it, verify it fails**

Run: `cd frontend && npx vitest run src/lib/__tests__/locale.test.ts`
Expected: FAIL — cannot resolve `@/lib/locale`.

- [ ] **Step 3: Implement `src/lib/locale.ts`**

```ts
export const LOCALES = ["en", "nl", "ro"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

/** Native language names, in display order. */
export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  nl: "Nederlands",
  ro: "Română",
};

// ISO-3166-1 alpha-2 country → preferred locale. Everything else → English.
// BE (Flanders) and MD (Moldova) included as sensible linguistic defaults; edit freely.
const COUNTRY_TO_LOCALE: Record<string, Locale> = {
  NL: "nl",
  BE: "nl",
  RO: "ro",
  MD: "ro",
};

export function resolveLocaleFromCountry(country: string | null | undefined): Locale {
  if (!country) return DEFAULT_LOCALE;
  return COUNTRY_TO_LOCALE[country.toUpperCase()] ?? DEFAULT_LOCALE;
}

export function isLocale(value: string | null | undefined): value is Locale {
  return !!value && (LOCALES as readonly string[]).includes(value);
}

/** "/nl/about" → "/about"; "/nl" → "/"; "/about" → "/about". */
export function stripLocale(pathname: string): string {
  const segments = pathname.split("/"); // ["", "nl", "about"]
  if (isLocale(segments[1])) {
    const rest = "/" + segments.slice(2).join("/");
    return rest === "/" ? "/" : rest.replace(/\/+$/, "");
  }
  return pathname;
}

export function hasLocalePrefix(pathname: string): boolean {
  return isLocale(pathname.split("/")[1]);
}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `cd frontend && npx vitest run src/lib/__tests__/locale.test.ts`
Expected: PASS (all assertions).

- [ ] **Step 5: Stage**

```bash
git add frontend/src/lib/locale.ts frontend/src/lib/__tests__/locale.test.ts
```

---

## Task 3: Restructure marketing routes under `[locale]`

**Files:**
- Move: `frontend/src/app/(marketing)/` → `frontend/src/app/[locale]/(marketing)/`
- Create: `frontend/src/app/[locale]/layout.tsx`
- Modify: `frontend/src/app/[locale]/(marketing)/providers.tsx`
- Leave unchanged: `frontend/src/app/layout.tsx` (document why)

**Interfaces:**
- Consumes: `routing` (Task 1).
- Produces: live routes `/`, `/nl`, `/ro`, `/about`, `/nl/about`, … all rendering current English copy (extraction happens later). `NextIntlClientProvider` mounted for all marketing pages.

- [ ] **Step 1: Move the route group**

```bash
cd frontend
git mv "src/app/(marketing)" "src/app/[locale]/(marketing)"
```
(If not tracked yet, use a plain move; the folder must end at `src/app/[locale]/(marketing)/`.)

- [ ] **Step 2: Create `src/app/[locale]/layout.tsx`**

```tsx
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { routing } from "@/i18n/routing";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  // Enables static rendering of marketing pages under this segment.
  setRequestLocale(locale);
  return <NextIntlClientProvider>{children}</NextIntlClientProvider>;
}
```

- [ ] **Step 3: Add the client `lang` sync to `providers.tsx`.** The root `<html lang="en">` stays static (keeps marketing pages statically renderable + zero dashboard risk); we correct the language for assistive tech on the client. Edit `src/app/[locale]/(marketing)/providers.tsx`:

Change the imports line:
```tsx
import { useEffect } from "react";
import { useLocale } from "next-intl";
```
Inside `MarketingProviders`, before the `return`, add:
```tsx
  const locale = useLocale();
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
```

- [ ] **Step 4: Document the root layout decision.** In `src/app/layout.tsx`, replace the comment above `<html lang="en"` with a note (no behavior change):
```tsx
      {/* lang stays "en" statically: marketing pages set the active language on the
          client (see MarketingProviders) and emit hreflang alternates for SEO; the
          dashboard/widget are English. Keeps every page statically renderable. */}
```

- [ ] **Step 5: Verify routes resolve**

Run: `cd frontend && npm run build`
Expected: build succeeds; output lists `/[locale]` routes. (`npm run dev` then load `/`, `/nl`, `/ro/about` — all render current English copy. Do not run `npm run build` while a dev server is on :3000 — it kills it.)

- [ ] **Step 6: Verify dashboard + widget untouched**

`npm run dev`, then load `/dashboard` (redirects to `/log-in` when logged out) and `/w/<any-slug>` — both must render exactly as before (no locale prefix, no crash).

- [ ] **Step 7: Stage**

```bash
git add frontend/src/app
```

---

## Task 4: Middleware — geo default + intl + auth composition

**Files:**
- Modify: `frontend/src/middleware.ts`

**Interfaces:**
- Consumes: `routing` (Task 1); `resolveLocaleFromCountry`, `hasLocalePrefix`, `stripLocale`, `DEFAULT_LOCALE` (Task 2).
- Produces: first-visit geo redirect to `/nl|/ro`; `NEXT_LOCALE` cookie pinning; locale-aware `/log-in`→`/dashboard` redirect; unchanged `/dashboard` protection + legacy-host redirect.

- [ ] **Step 1: Rewrite `src/middleware.ts`** to the composed form (preserve legacy-host + verified-cookie behavior exactly):

```ts
import { NextRequest, NextResponse } from "next/server";
import createIntlMiddleware from "next-intl/middleware";
import { routing } from "@/i18n/routing";
import {
  resolveLocaleFromCountry,
  hasLocalePrefix,
  stripLocale,
  DEFAULT_LOCALE,
} from "@/lib/locale";

const intlMiddleware = createIntlMiddleware(routing);

const AUTH_SERVICE_URL = process.env.FASTAPI_URL ?? "http://localhost:8001";
const CANONICAL_HOST = "roman-technologies.dev";
const VERIFIED_COOKIE = "auth_verified";
const VERIFIED_TTL_SECONDS = 60;
const LOCALE_COOKIE = "NEXT_LOCALE";
const LOCALE_TTL_SECONDS = 60 * 60 * 24 * 365;

function markVerified(response: NextResponse): void {
  response.cookies.set(VERIFIED_COOKIE, "1", {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: VERIFIED_TTL_SECONDS,
    secure: process.env.NODE_ENV === "production",
  });
}

function clearVerified(response: NextResponse): void {
  response.cookies.set(VERIFIED_COOKIE, "", { maxAge: 0, path: "/" });
}

async function isAuthenticated(request: NextRequest): Promise<boolean> {
  const cookieHeader = request.headers.get("cookie") ?? "";
  try {
    const res = await fetch(`${AUTH_SERVICE_URL}/auth/me`, {
      headers: { Cookie: cookieHeader },
      cache: "no-store",
    });
    return res.ok;
  } catch {
    return false;
  }
}

// Authed users hitting any /log-in (en or prefixed) bounce to the dashboard.
async function maybeRedirectLoggedIn(
  request: NextRequest,
  intlResponse: NextResponse
): Promise<NextResponse> {
  if (!stripLocale(request.nextUrl.pathname).startsWith("/log-in")) return intlResponse;
  if (request.cookies.get("sid") && request.cookies.get(VERIFIED_COOKIE)) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  if (await isAuthenticated(request)) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return intlResponse;
}

export async function middleware(request: NextRequest) {
  // ── Legacy host redirect (unchanged) ────────────────────────────────────
  const host = request.headers.get("host") ?? "";
  if (host.startsWith("cms-frontend-roman.") && host.endsWith(".vercel.app")) {
    const url = request.nextUrl.clone();
    url.host = CANONICAL_HOST;
    url.protocol = "https:";
    return NextResponse.redirect(url, 308);
  }

  const { pathname } = request.nextUrl;

  // ── API + widget: never localized, no auth ──────────────────────────────
  if (pathname.startsWith("/api") || pathname.startsWith("/w")) {
    return NextResponse.next();
  }

  // ── Dashboard: locale-free, auth-protected (unchanged semantics) ─────────
  if (pathname.startsWith("/dashboard")) {
    if (request.cookies.get("sid") && request.cookies.get(VERIFIED_COOKIE)) {
      return NextResponse.next();
    }
    if (!(await isAuthenticated(request))) {
      const response = NextResponse.redirect(new URL("/log-in", request.url));
      clearVerified(response);
      return response;
    }
    const response = NextResponse.next();
    markVerified(response);
    return response;
  }

  // ── Marketing area (intl) ────────────────────────────────────────────────
  const firstVisit = !request.cookies.get(LOCALE_COOKIE) && !hasLocalePrefix(pathname);

  if (firstVisit) {
    const locale = resolveLocaleFromCountry(request.headers.get("x-vercel-ip-country"));
    if (locale !== DEFAULT_LOCALE) {
      const url = request.nextUrl.clone();
      url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
      const response = NextResponse.redirect(url);
      response.cookies.set(LOCALE_COOKIE, locale, {
        path: "/",
        maxAge: LOCALE_TTL_SECONDS,
        sameSite: "lax",
      });
      return response;
    }
  }

  const intlResponse = intlMiddleware(request);
  if (firstVisit) {
    // English (or unknown country): pin the cookie so Accept-Language can't override.
    intlResponse.cookies.set(LOCALE_COOKIE, DEFAULT_LOCALE, {
      path: "/",
      maxAge: LOCALE_TTL_SECONDS,
      sameSite: "lax",
    });
  }
  return maybeRedirectLoggedIn(request, intlResponse);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|svg|gif|webp|ico|css|js|woff2?)).*)",
  ],
};
```

- [ ] **Step 2: Verify geo default (Romanian)**

`cd frontend && npm run dev`, then:
Run: `curl -sI -H "x-vercel-ip-country: RO" http://localhost:3000/ | grep -i location`
Expected: `location: /ro`

- [ ] **Step 3: Verify geo default (Dutch, deep path)**

Run: `curl -sI -H "x-vercel-ip-country: NL" http://localhost:3000/about | grep -i location`
Expected: `location: /nl/about`

- [ ] **Step 4: Verify fallback + cookie wins**

Run: `curl -sI -H "x-vercel-ip-country: US" http://localhost:3000/ | grep -i -E "location|set-cookie"`
Expected: NO redirect to a locale; `set-cookie: NEXT_LOCALE=en`.
Run: `curl -sI -H "x-vercel-ip-country: RO" --cookie "NEXT_LOCALE=en" http://localhost:3000/ | grep -i location`
Expected: no `/ro` redirect (cookie wins).

- [ ] **Step 5: Verify dashboard still gates**

Run: `curl -sI http://localhost:3000/dashboard | grep -i location`
Expected: `location: /log-in` (logged out).

- [ ] **Step 6: Stage**

```bash
git add frontend/src/middleware.ts
```

---

## Task 5: LanguageSwitcher component (TDD)

**Files:**
- Create: `frontend/src/components/i18n/LanguageSwitcher.tsx`
- Test: `frontend/src/components/i18n/__tests__/LanguageSwitcher.test.tsx`

**Interfaces:**
- Consumes: `LOCALES`, `LOCALE_NAMES`, `Locale` (Task 2); `usePathname`, `useRouter` (`@/i18n/navigation`); `useLocale`, `useTranslations` (`next-intl`).
- Produces: `<LanguageSwitcher variant="nav" | "drawer" | "footer" />`. On select, calls `router.replace(pathname, { locale })` inside `startTransition`.
- Requires message namespace `languageSwitcher` (added in Task 7): keys `ariaLabel`, `label`.

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanguageSwitcher } from "../LanguageSwitcher";

const replace = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  usePathname: () => "/about",
  useRouter: () => ({ replace }),
}));
vi.mock("next-intl", () => ({
  useLocale: () => "en",
  useTranslations: () => (key: string) => key,
}));

beforeEach(() => replace.mockClear());

describe("LanguageSwitcher (nav)", () => {
  it("opens the menu and lists the three native names", async () => {
    const user = userEvent.setup();
    render(<LanguageSwitcher variant="nav" />);
    await user.click(screen.getByRole("button", { name: /ariaLabel/i }));
    expect(screen.getByText("English")).toBeInTheDocument();
    expect(screen.getByText("Nederlands")).toBeInTheDocument();
    expect(screen.getByText("Română")).toBeInTheDocument();
  });

  it("switches locale on the current path, preserving it", async () => {
    const user = userEvent.setup();
    render(<LanguageSwitcher variant="nav" />);
    await user.click(screen.getByRole("button", { name: /ariaLabel/i }));
    await user.click(screen.getByText("Română"));
    expect(replace).toHaveBeenCalledWith("/about", { locale: "ro" });
  });

  it("does not navigate when re-selecting the active locale", async () => {
    const user = userEvent.setup();
    render(<LanguageSwitcher variant="nav" />);
    await user.click(screen.getByRole("button", { name: /ariaLabel/i }));
    await user.click(screen.getByText("English"));
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("LanguageSwitcher (drawer)", () => {
  it("renders the three options inline without a trigger button", () => {
    render(<LanguageSwitcher variant="drawer" />);
    expect(screen.getByText("English")).toBeInTheDocument();
    expect(screen.getByText("Nederlands")).toBeInTheDocument();
    expect(screen.getByText("Română")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it, verify it fails**

Run: `cd frontend && npx vitest run src/components/i18n/__tests__/LanguageSwitcher.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/components/i18n/LanguageSwitcher.tsx`**

```tsx
"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { AnimatePresence, m } from "motion/react";
import { Globe, Check, ChevronDown } from "lucide-react";
import { usePathname, useRouter } from "@/i18n/navigation";
import { LOCALES, LOCALE_NAMES, type Locale } from "@/lib/locale";

type Variant = "nav" | "drawer" | "footer";

export function LanguageSwitcher({ variant = "nav" }: { variant?: Variant }) {
  const active = useLocale() as Locale;
  const t = useTranslations("languageSwitcher");
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [, startTransition] = useTransition();
  const ref = useRef<HTMLDivElement>(null);

  function select(next: Locale) {
    setOpen(false);
    if (next === active) return;
    startTransition(() => router.replace(pathname, { locale: next }));
  }

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => setOpen(false), [pathname]);

  // ── Drawer: inline segmented pills (always visible inside the menu) ───────
  if (variant === "drawer") {
    return (
      <div className="flex flex-col gap-2">
        <p className="px-1 text-xs font-semibold uppercase tracking-widest text-zinc-600">
          {t("label")}
        </p>
        <div className="flex gap-1.5">
          {LOCALES.map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => select(l)}
              aria-current={l === active}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors cursor-pointer ${
                l === active
                  ? "border-accent/40 bg-accent/10 text-accent"
                  : "border-white/[0.08] text-zinc-400 hover:text-white"
              }`}
            >
              {LOCALE_NAMES[l]}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // ── Nav + footer: trigger button + popover ───────────────────────────────
  const upward = variant === "footer";
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("ariaLabel")}
        className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-zinc-400 transition-colors hover:text-white cursor-pointer"
      >
        <Globe className="h-4 w-4" />
        <span className="uppercase">{active}</span>
        <ChevronDown
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <m.ul
            role="menu"
            initial={{ opacity: 0, scale: 0.96, y: upward ? 6 : -6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: upward ? 6 : -6 }}
            transition={{ duration: 0.16, ease: "easeOut" }}
            className={`absolute right-0 z-50 min-w-[10rem] overflow-hidden rounded-xl border border-white/[0.08] bg-zinc-950/95 p-1 shadow-xl backdrop-blur ${
              upward ? "bottom-full mb-2" : "top-full mt-2"
            }`}
          >
            {LOCALES.map((l) => (
              <li key={l} role="none">
                <button
                  type="button"
                  role="menuitemradio"
                  aria-checked={l === active}
                  onClick={() => select(l)}
                  className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm transition-colors cursor-pointer ${
                    l === active
                      ? "text-accent"
                      : "text-zinc-300 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  {LOCALE_NAMES[l]}
                  {l === active && <Check className="h-4 w-4" />}
                </button>
              </li>
            ))}
          </m.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `cd frontend && npx vitest run src/components/i18n/__tests__/LanguageSwitcher.test.tsx`
Expected: PASS. (The `m`/`AnimatePresence` from `motion/react` render fine under jsdom; the menu mounts synchronously on click.)

- [ ] **Step 5: Stage**

```bash
git add frontend/src/components/i18n
```

---

## Task 6: Mount the switcher in all three placements

**Files:**
- Modify: `frontend/src/components/Header.tsx` (desktop nav)
- Modify: `frontend/src/components/HeaderRightCluster.tsx` (mobile drawer)
- Modify: `frontend/src/components/Footer.tsx` (footer)

**Interfaces:**
- Consumes: `<LanguageSwitcher>` (Task 5).

- [ ] **Step 1: Desktop nav.** In `Header.tsx`, import and render the switcher beside the nav links. Add import:
```tsx
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
```
Inside the right group `<div className="flex items-center gap-1 md:gap-2">`, immediately after the closing `</nav>` and before `<HeaderRightCluster />`, add (hidden on mobile — the drawer covers small screens):
```tsx
          <div className="hidden md:block">
            <LanguageSwitcher variant="nav" />
          </div>
```

- [ ] **Step 2: Mobile drawer.** In `HeaderRightCluster.tsx`, add import:
```tsx
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
```
Inside the mobile `<motion.nav>`, after the `Get in touch` block's closing `</motion.div>`, add:
```tsx
                <motion.div variants={fadeIn} className="mt-2 border-t border-white/[0.06] pt-4">
                  <LanguageSwitcher variant="drawer" />
                </motion.div>
```

- [ ] **Step 3: Footer.** In `Footer.tsx`, add import:
```tsx
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
```
In the "Contact" column `<motion.div variants={fadeUp} className="flex flex-col gap-4">`, after the `CONTACT_ITEMS.map(...)` block, add the switcher:
```tsx
            <LanguageSwitcher variant="footer" />
```

- [ ] **Step 4: Verify across viewports (Playwright MCP)**

`npm run dev`. With the Playwright MCP: resize to 1280×800 → confirm the nav globe shows and the popover opens/lists 3 languages; resize to 375×812 → open the hamburger and confirm the drawer "Language" pills show; scroll to the footer at both sizes → confirm the footer switcher shows and opens upward. Switch to `Română` from each and confirm the URL gains `/ro`.

- [ ] **Step 5: Stage**

```bash
git add frontend/src/components/Header.tsx frontend/src/components/HeaderRightCluster.tsx frontend/src/components/Footer.tsx
```

---

## Task 7: Author the full English message catalog

**Files:**
- Modify: `frontend/messages/en.json` (replace the Task 1 seed with the full catalog below)

**Interfaces:**
- Produces: the complete `en.json` consumed by Tasks 5, 6, 8–13, plus the DeepL script (Task 14). This is the single source of truth for marketing copy.

- [ ] **Step 1: Replace `messages/en.json`** with the full catalog (verbatim current copy, extracted from the live components/content files):

```json
{
  "common": { "brand": "Roman Technologies" },
  "languageSwitcher": {
    "label": "Language",
    "ariaLabel": "Change language"
  },
  "nav": { "about": "About", "clients": "Clients", "team": "Team", "contact": "Contact" },
  "header": {
    "logIn": "Log In",
    "openDashboard": "Open dashboard",
    "openMenu": "Open menu",
    "closeMenu": "Close menu",
    "openDashboardButton": "Open Dashboard",
    "getInTouch": "Get in touch"
  },
  "footer": {
    "tagline": "Premium software solutions for modern businesses.",
    "contact": "Contact",
    "rights": "© {year} Roman Technologies SRL. All rights reserved."
  },
  "login": {
    "heading": "Access CMS",
    "subheading": "Please sign in to your administrative account.",
    "emailLabel": "Email address or Username",
    "emailPlaceholder": "admin@example.com",
    "passwordLabel": "Password",
    "showPassword": "Show password",
    "hidePassword": "Hide password",
    "rememberMe": "Remember me",
    "forgotPassword": "Forgot your password?",
    "signIn": "Sign in to dashboard",
    "successHeading": "Successfully Logged In",
    "successBody": "You're all set. Head over to your dashboard to manage your projects.",
    "goToDashboard": "Go to Dashboard"
  },
  "hero": {
    "eyebrow": "Roman Technologies",
    "title": "We make your idea or need come alive",
    "subtitle": "Custom websites, apps, AI Agents and workflows for ambitious companies, at a price that respects your budget.",
    "getPreview": "Get a free preview",
    "seePricing": "See pricing",
    "noCall": "No call required to get pricing.",
    "trust": {
      "humanReviewed": "Human-reviewed code",
      "euBased": "EU-based",
      "gdpr": "GDPR compliant",
      "hosting": "Managed hosting included"
    }
  },
  "laptop": {
    "srDescription": "Decorative animation of a laptop opening to reveal the Roman Technologies content management system in use by Café Nordlys, a sample client.",
    "captions": {
      "manage": "Manage your projects in one place",
      "adjust": "Change content and adjust your project yourself 24/7 using our agentic software",
      "hosted": "Hosted, secured, monitored — by us.",
      "reviewed": "Every major release is human-reviewed to ensure correctness"
    }
  },
  "contactSection": {
    "eyebrow": "Let's talk",
    "heading": "Book a call or send a message",
    "subheading": "Grab a 45-minute slot with me, Stefan — or leave your details below and I'll reply within one business day.",
    "bookingHeading": "Book a call with Stefan",
    "bookingSubheading": "45-minute call"
  },
  "contactInfo": {
    "heading": "Reach us directly",
    "subheading": "Prefer email or a quick call? Here is where to find us.",
    "email": "Email",
    "phone": "Phone",
    "location": "Location",
    "hours": "Hours"
  },
  "contactForm": {
    "name": "Name",
    "email": "Email",
    "company": "Company",
    "message": "Message",
    "optional": "(optional)",
    "namePlaceholder": "Jane Doe",
    "emailPlaceholder": "jane@company.com",
    "companyPlaceholder": "Acme Inc.",
    "messagePlaceholder": "A few lines about your project, timeline and budget.",
    "errName": "Please add your name.",
    "errEmailEmpty": "Please add your email.",
    "errEmailInvalid": "That email does not look right.",
    "errMessage": "Tell us a little more (at least 10 characters).",
    "send": "Send message",
    "success": "Message sent — talk soon!",
    "error": "Something went wrong. Email me directly at {recipient}.",
    "sendAnother": "Send another message",
    "tryAgain": "Try again",
    "orEmail": "Or email us directly at {recipient}."
  },
  "contactChannel": { "email": "Email", "bookCall": "Book a call" },
  "whatWeDo": {
    "eyebrow": "What we build",
    "heading": "What do we do?",
    "lead": "From a single landing page to full AI platforms — here's how we help ambitious companies ship.",
    "aiAgents": { "title": "We build AI agents", "description": "Autonomous agents that handle real work end-to-end — not just chatbots." },
    "websites": { "title": "We develop websites", "description": "Fast, beautiful, SEO-ready sites that turn visitors into customers." },
    "apps": { "title": "We build software applications", "description": "Web, mobile and desktop apps engineered to scale with you." },
    "automation": { "title": "We create automation workflows with AI", "description": "AI-driven workflows that run your busywork around the clock." }
  },
  "values": {
    "eyebrow": "What we stand for",
    "heading": "Our values",
    "clientFirst": { "title": "Client comes first", "description": "We start from your goals, not our stack. Every decision is measured by what moves your business forward." },
    "teamwork": { "title": "Teamwork", "description": "Engineering, security and strategy work as one team, so nothing falls between the cracks." },
    "ownership": { "title": "Ownership", "description": "You own everything we build — code, data and roadmap. No lock-in, no black boxes." },
    "transparency": { "title": "Transparency", "description": "Clear quotes, honest timelines, and a human who answers. You always know where things stand." }
  },
  "work": {
    "searchPlaceholder": "Search projects…",
    "searchAria": "Search projects by name",
    "empty": "No projects match \"{query}\".",
    "previewAlt": "{name} preview",
    "openAria": "Open {name} in a new tab",
    "prevProject": "Previous project",
    "nextProject": "Next project"
  },
  "projects": {
    "akris": {
      "tagline": "A presentation site with a custom scraper that pulls official statistics into a sleek, modern dashboard.",
      "keyInfo": [
        { "label": "Type", "value": "Sports club website" },
        { "label": "Stack", "value": "Next.js · Web scraper" },
        { "label": "Focus", "value": "Live stats dashboard" }
      ]
    },
    "pluxbox": {
      "tagline": "A crisp product site for a software company",
      "keyInfo": [
        { "label": "Type", "value": "SaaS / product website" },
        { "label": "Stack", "value": "Next.js · Tailwind · Motion" },
        { "label": "Focus", "value": "Clarity, conversion" }
      ]
    },
    "roman-mariana": {
      "tagline": "A polished business site with custom email integrations that automate customer-business communication.",
      "keyInfo": [
        { "label": "Type", "value": "Business website" },
        { "label": "Stack", "value": "Next.js · Email automation" },
        { "label": "Focus", "value": "Email automation, lead gen" }
      ]
    }
  },
  "clientsPage": {
    "metaTitle": "Clients — Roman Technologies",
    "metaDescription": "A selection of websites, applications and AI workflows we've built and now keep running for clients across the EU.",
    "eyebrow": "Our work",
    "title": "Built for ambitious companies.",
    "subheading": "A selection of websites, applications and AI workflows we've designed, built and now keep running for clients across the EU."
  },
  "pricing": {
    "heading": "Simple, honest pricing",
    "toggleProject": "Project-based",
    "toggleSubscription": "Subscription",
    "monthly": "Monthly",
    "yearly": "Yearly",
    "mostPopular": "Most popular",
    "save": "Save {discount}%",
    "disclaimerProject": "Prices adjust with complexity — you always get a clear quote before anything starts.",
    "shared": {
      "managedHosting": "Managed hosting and security",
      "managedHostingTip": "Hosted, secured and monitored by us — no separate hosting bill.",
      "seo": "SEO & GEO optimization",
      "seoTip": "Optimized for search engines and AI answer engines so you get found.",
      "humanReview": "Personal human review",
      "humanReviewTip": "Every major release is reviewed by a human, not just shipped by a machine.",
      "cms": "CMS connector & agentic issue solver",
      "cmsTip": "Change content across your app anytime, and an AI agent auto-detects and fixes issues."
    },
    "project": {
      "presentation": {
        "name": "Presentation website",
        "info": "Marketing & presentation sites that launch fast.",
        "price": "from €250",
        "priceNote": "from €400 with complex backend integration",
        "feature": "Custom, responsive design",
        "cta": "Get a free preview"
      },
      "application": {
        "name": "Software application",
        "info": "Mobile and / or desktop apps, built to scale.",
        "price": "from €500",
        "feature": "Priority development meetings",
        "featureTip": "Higher priority for human meetings with the development team.",
        "cta": "Start your app"
      },
      "automation": {
        "name": "AI automation software",
        "info": "Custom AI workflows that run your busywork.",
        "price": "from €200",
        "feature": "24/7 maintenance",
        "featureTip": "We keep your automations running around the clock.",
        "cta": "Automate something"
      }
    },
    "subscription": {
      "care": {
        "name": "Care",
        "info": "Keep an existing site healthy.",
        "priceMonthly": "€49/month",
        "priceYearly": "€490/year",
        "features": ["Managed hosting & monitoring", "Monthly content updates", "Email support"],
        "cta": "Choose Care"
      },
      "growth": {
        "name": "Growth",
        "info": "Ongoing improvements & support.",
        "priceMonthly": "€99/month",
        "priceYearly": "€990/year",
        "features": ["Everything in Care", "Agentic issue solver", "Priority support", "Quarterly strategy meeting"],
        "cta": "Choose Growth"
      },
      "scale": {
        "name": "Scale",
        "info": "A dedicated partner for fast-moving teams.",
        "priceMonthly": "€199/month",
        "priceYearly": "€1990/year",
        "features": ["Everything in Growth", "Dedicated developer hours", "24/7 support agent", "Monthly roadmap reviews"],
        "cta": "Choose Scale"
      }
    }
  },
  "teamPage": {
    "metaTitle": "Team — Roman Technologies",
    "eyebrow": "Our team",
    "title": "A team that ships.",
    "subheading": "The people behind every build — engineering, security and strategy under one roof, and the principles that guide how we work."
  },
  "aboutPage": { "metaTitle": "About — Roman Technologies" },
  "about": {
    "hero": {
      "eyebrow": "About us",
      "title": "Software that respects your time, your budget, and your data.",
      "lead": "Roman Technologies is an EU-based software studio. We design and build custom websites, applications and AI workflows for ambitious companies — then host, secure and maintain them, so you can focus on your business instead of your stack."
    },
    "story": {
      "heading": "Who we are",
      "paragraphs": [
        "We started Roman Technologies on a simple conviction: small and growing businesses deserve the same quality of software as enterprises — without the enterprise price tag or the agency runaround.",
        "Every project is built to be owned by you, reviewed by a human before it ships, and backed by managed hosting and monitoring. No lock-in, no surprises — just software that works, and a team that actually answers."
      ]
    },
    "team": {
      "heading": "Meet the team",
      "subheading": "A small, senior team that ships — engineering, security and strategy under one roof.",
      "members": {
        "stefan-roman": {
          "role": "CEO & Founder",
          "description": "Leads strategy and client relationships, oversees delivery end-to-end, and makes sure every release ships correct, on time, and aligned with what the business actually needs."
        },
        "alexandru-aioanei": {
          "role": "Full Stack (AI) Developer",
          "description": "Builds features end-to-end across frontend and backend, and integrates AI workflows and agents into client products — turning ideas into working, maintainable software."
        },
        "laurian-duma": {
          "role": "GDPR & Security Compliance Engineer",
          "description": "Owns data protection and security: runs reviews and threat modelling, keeps every product GDPR-compliant, and makes sure client data stays locked down and EU-resident."
        }
      }
    }
  },
  "contactPage": {
    "metaTitle": "Contact — Roman Technologies",
    "hero": {
      "eyebrow": "Contact",
      "title": "Tell us what you're building.",
      "lead": "Send a message or reach us directly. We usually reply within one business day, and you never need a call to get a quote."
    }
  },
  "manage": {
    "loading": "Loading…",
    "linkNotFoundTitle": "Link not found",
    "linkNotFoundBody": "This management link is invalid or expired.",
    "cancelledTitle": "Booking cancelled",
    "cancelledBody": "This booking has been cancelled.",
    "bookingTitle": "Your booking",
    "reschedule": "Reschedule",
    "rescheduleTooltipAllowed": "This business allows rescheduling up to {max} {max, plural, one {time} other {times}}.",
    "rescheduleClosedTooltip": "Rescheduling is closed for this booking — it's too close to the appointment.",
    "cancelBooking": "Cancel this booking",
    "cancelling": "Cancelling…",
    "cancelSuccess": "Your booking is cancelled.",
    "cancelError": "Could not cancel. Please try again or contact support.",
    "confirmCancel": "Cancel this booking? This cannot be undone.",
    "keepIt": "Keep it",
    "yesCancel": "Yes, cancel",
    "cancellationClosed": "Cancellation is closed — it's too close to the appointment."
  }
}
```

- [ ] **Step 2: Mirror the new keys into `nl.json` and `ro.json`** as copies of `en.json` for now (DeepL overwrites them in Task 14; the deep-merge fallback means untranslated keys already show English). Quickest: `cp messages/en.json messages/nl.json && cp messages/en.json messages/ro.json` (from `frontend/`).

- [ ] **Step 3: Verify JSON validity + build**

Run: `cd frontend && node -e "require('./messages/en.json');require('./messages/nl.json');require('./messages/ro.json');console.log('ok')"`
Expected: `ok`. Then `npm run typecheck` → no errors.

- [ ] **Step 4: Stage**

```bash
git add frontend/messages
```

---

## Wiring tasks (8–13): pattern

Each wiring task swaps English literals for `t("…")`. Two mechanical patterns:

- **Client component** (`"use client"`): `import { useTranslations } from "next-intl";` then `const t = useTranslations("<namespace>");` inside the component; replace `"Literal"` → `{t("key")}`, attributes → `aria-label={t("key")}`. Interpolations: `t("error", { recipient })`. Arrays: `t.raw("paragraphs") as string[]`.
- **Server component** (no `"use client"`): `import { getTranslations } from "next-intl/server";` then `const t = await getTranslations("<namespace>");` (make the component `async`). Metadata: `export async function generateMetadata({ params }): Promise<Metadata>` using `await getTranslations(...)`.

The string for every key is already in `messages/en.json` (Task 7). Each task below gives the file→namespace→keys map and one fully-worked example; apply the same pattern to the rest of that task's files. After each task: `npm run typecheck` clean, and spot-check the affected page in `npm run dev` at `/` and `/ro` (Romanian shows English until Task 14 — that's expected).

---

## Task 8: Wire the site chrome

**Files & namespaces:**
- Modify: `frontend/src/lib/nav-links.ts` → needs locale-aware labels (see Step 1) using `nav.*`
- Modify: `frontend/src/components/Header.tsx`, `HeaderRightCluster.tsx` → `nav.*`, `header.*`
- Modify: `frontend/src/components/Footer.tsx` → `footer.*`
- Modify: `frontend/src/app/[locale]/(marketing)/log-in/page.tsx` → `login.heading`, `login.subheading`
- Modify: `frontend/src/app/[locale]/(marketing)/log-in/LoginForm.tsx` → `login.*`
- Also: replace `next/link` / `useRouter`/`usePathname` from `next/navigation` with the locale-aware versions from `@/i18n/navigation` in nav components and links so internal links keep the active locale.

**Interfaces:**
- Consumes: `nav`, `header`, `footer`, `login` namespaces (Task 7).

- [ ] **Step 1: Make nav labels translatable.** `nav-links.ts` currently hard-codes labels. Change it to keys + a hook. Replace the file with:

```ts
/**
 * Primary site navigation. `key` indexes the `nav` message namespace;
 * `href` is locale-less (the locale-aware Link adds the prefix).
 */
export const NAV_LINKS = [
  { key: "about", href: "/about" },
  { key: "clients", href: "/clients" },
  { key: "team", href: "/team" },
  { key: "contact", href: "/contact" },
] as const;
```

- [ ] **Step 2: Header desktop nav.** In `Header.tsx` add `import { useTranslations } from "next-intl";`, add `const t = useTranslations("nav");` in the component, and change the link render to:
```tsx
                <NavLink href={link.href} className={`px-4 py-2 ${navLinkCn}`}>
                  {t(link.key)}
                </NavLink>
```
Ensure `NavLink` uses the locale-aware `Link`. In `src/components/nav/NavLink.tsx`, change `import Link from "next/link"` → `import { Link } from "@/i18n/navigation";` (keep the rest).

- [ ] **Step 3: HeaderRightCluster.** Add `import { useTranslations } from "next-intl";`. Add `const tn = useTranslations("nav");` and `const th = useTranslations("header");`. Replace literals: mobile nav `{link.label}` → `{tn(link.key)}`; aria-labels and button text via `th("openDashboard")`, `th("openMenu")`, `th("closeMenu")`, `th("logIn")`, `th("openDashboardButton")`, `th("getInTouch")`. Switch the `next/link` import to `import { Link } from "@/i18n/navigation";`.

- [ ] **Step 4: Footer.** In `Footer.tsx` add `import { useTranslations } from "next-intl";` and `const t = useTranslations("footer");`. Replace:
  - tagline paragraph → `{t("tagline")}`
  - `<p className={sectionLabelCn}>Contact</p>` → `{t("contact")}`
  - copyright → `{t("rights", { year: new Date().getFullYear() })}` (keep the dynamic year as the interpolation value; the literal `new Date().getFullYear()` stays in code).

- [ ] **Step 5: Login page (server).** `log-in/page.tsx` — make it `async`, add `import { getTranslations } from "next-intl/server";`, `const t = await getTranslations("login");`, replace `"Access CMS"` → `{t("heading")}` and the subheading → `{t("subheading")}`.

- [ ] **Step 6: LoginForm (client).** Add `const t = useTranslations("login");` and replace all labels/placeholders/aria/buttons/success copy per the `login.*` keys (emailLabel, emailPlaceholder, passwordLabel, showPassword, hidePassword, rememberMe, forgotPassword, signIn, successHeading, successBody, goToDashboard). The dynamic `{error}` from the API stays as-is.

- [ ] **Step 7: Update the LoginForm test** for the now-rendered strings — they're unchanged English text, so existing queries (`/sign in to dashboard/i`, `/show password/i`) still match. Run: `cd frontend && npx vitest run src/app/[locale]/\(marketing\)/log-in/__tests__/LoginForm.test.tsx`. If the test path moved with the folder, it runs from the new location. Expected: PASS. (The component now needs `NextIntlClientProvider` in the test — wrap `renderWithProviders` with `<NextIntlClientProvider locale="en" messages={messages}>` importing `messages from "@/../messages/en.json"`.)

- [ ] **Step 8: Verify + stage**

Run: `cd frontend && npm run typecheck && npx vitest run` → green.
```bash
git add frontend/src/lib/nav-links.ts frontend/src/components/Header.tsx frontend/src/components/HeaderRightCluster.tsx frontend/src/components/Footer.tsx frontend/src/components/nav/NavLink.tsx "frontend/src/app/[locale]/(marketing)/log-in"
```

---

## Task 9: Wire the home-page sections

**Files & namespaces:**
- `components/hero/HeroSection.tsx` → `hero.*` (incl. `hero.trust.*`)
- `components/hero/LaptopShowcase.tsx` → `laptop.*` (`srDescription`, `captions.*`)
- `components/contact/ContactSection.tsx` → `contactSection.*`
- `components/contact/ContactInfo.tsx` → `contactInfo.*`
- `components/contact/ContactForm.tsx` → `contactForm.*` (interpolate `{recipient}`)
- `components/contact/ContactChannel.tsx` → `contactChannel.*` + `contactSection.bookingHeading/bookingSubheading`
- `components/work/WhatWeDo.tsx` → `whatWeDo.*`
- `components/team/ValuesSection.tsx` → `values.*`

All are client components → `useTranslations`.

**Interfaces:** Consumes `hero`, `laptop`, `contactSection`, `contactInfo`, `contactForm`, `contactChannel`, `whatWeDo`, `values` (Task 7).

- [ ] **Step 1: Worked example — HeroSection.** Add `import { useTranslations } from "next-intl";`, `const t = useTranslations("hero");`. Replace the eyebrow/title/subtitle/buttons/noCall literals with `t("eyebrow")`, `t("title")`, `t("subtitle")`, `t("getPreview")`, `t("seePricing")`, `t("noCall")`. For the `TRUST` array, change it from holding strings to holding keys and resolve at render: change each item's label to `t(\`trust.${item.key}\`)` where keys are `humanReviewed|euBased|gdpr|hosting`.

- [ ] **Step 2: Apply the same pattern** to the remaining files in this task using their namespace + the keys in `en.json`. Notes:
  - `LaptopShowcase` `CAPTIONS` array → keys `manage|adjust|hosted|reviewed`; the sr-only text → `t("srDescription")`.
  - `ContactForm` validation errors map to `errName|errEmailEmpty|errEmailInvalid|errMessage`; feedback to `success|error|sendAnother|tryAgain|orEmail`; `error`/`orEmail` take `{ recipient }`. The recipient email value stays sourced from props.
  - `WhatWeDo`/`ValuesSection` `SERVICES`/`VALUES` arrays → convert each item to `{ key, ... }` and resolve `t(\`${key}.title\`)`/`t(\`${key}.description\`)`.

- [ ] **Step 3: Verify + stage**

Run: `cd frontend && npm run typecheck` → clean. `npm run dev`, load `/` — copy unchanged; load `/ro` — same English (until Task 14).
```bash
git add frontend/src/components/hero frontend/src/components/contact frontend/src/components/work/WhatWeDo.tsx frontend/src/components/team/ValuesSection.tsx
```

---

## Task 10: Wire Work section + project content split

**Files & namespaces:**
- `frontend/src/content/projects.ts` — keep `id`, `name`, `short`, `image`, `url`; **remove** `tagline` + `keyInfo` (now in `messages.projects.<id>`).
- `components/work/ProjectsGrid.tsx`, `components/work/ProjectsCarousel.tsx` → `work.*` + `projects.<id>.*`

**Interfaces:** Consumes `work`, `projects` (Task 7). `projects.<id>.keyInfo` is an array → read via `t.raw()`.

- [ ] **Step 1: Trim `projects.ts`.** Update the `Project` interface to drop `tagline` and `keyInfo`, and remove those fields from each entry (keep `id`, `name`, `short`, `image`, `url`). The `id` values (`akris`, `pluxbox`, `roman-mariana`) must match the `messages.projects` keys.

- [ ] **Step 2: ProjectsCarousel.** Add `const t = useTranslations("work");` and `const tp = useTranslations("projects");`. Replace: arrows aria → `t("prevProject")`/`t("nextProject")`; image alt → `t("previewAlt", { name: project.name })`; open aria → `t("openAria", { name: project.name })`; tagline render → `tp(\`${project.id}.tagline\`)`; keyInfo render → `(tp.raw(\`${project.id}.keyInfo\`) as {label:string;value:string}[]).map(...)`.

- [ ] **Step 3: ProjectsGrid.** Same two hooks. Replace: `searchPlaceholder`, `searchAria`, empty state `t("empty", { query })`, image alt + open aria as above, and tagline/keyInfo via `tp`.

- [ ] **Step 4: Verify + stage**

Run: `cd frontend && npm run typecheck` → clean; `npm run dev` → home Projects + `/clients` grid render with the same copy.
```bash
git add frontend/src/content/projects.ts frontend/src/components/work
```

---

## Task 11: Wire the Pricing section

**Files & namespaces:**
- `components/pricing/PricingSection.tsx` → `pricing.*`

**Interfaces:** Consumes `pricing` (Task 7). Feature lists for subscription plans are arrays → `t.raw("subscription.<plan>.features") as string[]`.

- [ ] **Step 1:** Add `const t = useTranslations("pricing");`. Replace the heading, both toggles (`toggleProject`, `toggleSubscription`), frequency toggles (`monthly`, `yearly`), `mostPopular` badge, `save` (with `{ discount }`), and `disclaimerProject`.

- [ ] **Step 2:** Replace the shared feature labels + tooltips with `t("shared.*")` keys. For each project plan card use `t("project.<plan>.name|info|price|priceNote|feature|featureTip|cta")`; for each subscription card use `t("subscription.<plan>.name|info|priceMonthly|priceYearly|cta")` and `t.raw("subscription.<plan>.features") as string[]` for the bullet list. Keep all pricing logic (toggles, discount %) intact — only the display strings change; pass the computed `discount` number into `t("save", { discount })`.

- [ ] **Step 3: Verify + stage**

Run: `cd frontend && npm run typecheck` → clean; `npm run dev` → `/` pricing renders identically; toggle project/subscription + monthly/yearly still works.
```bash
git add frontend/src/components/pricing/PricingSection.tsx
```

---

## Task 12: Wire content pages + metadata + content split

**Files & namespaces:**
- `frontend/src/content/about.json` — add an `id` to each member (`stefan-roman`, `alexandru-aioanei`, `laurian-duma`); **remove** `role` + `description` (now in `messages.about.team.members.<id>`). Keep `name`, `image`, `email`, `linkedin`. Hero/story/team headings move to messages too (delete `hero`, `story`, `team.heading`, `team.subheading` text — or leave the file holding only `members` data; see Step 1).
- `frontend/src/content/about.ts` — update `TeamMember`/`AboutContent` types to match the trimmed JSON.
- `components/about/AboutHero.tsx`, `AboutStory.tsx`, `TeamSection.tsx`, `TeamMemberCard.tsx` → `about.*`
- `components/team/ValuesSection.tsx` already done (Task 9).
- Pages (server): `about/page.tsx`, `team/page.tsx`, `clients/page.tsx`, `contact/page.tsx` → translated `generateMetadata` + page eyebrows/titles via `getTranslations`.

**Interfaces:** Consumes `about`, `aboutPage`, `teamPage`, `clientsPage`, `contactPage`, `contactInfo` (Task 7); `buildAlternates` (Task 1).

- [ ] **Step 1: Restructure `about.json`** to data-only members:
```json
{
  "members": [
    { "id": "stefan-roman", "name": "Stefan Roman", "image": "/team/stefan-roman.jpg", "email": "stefan@roman-technologies.dev", "linkedin": "https://www.linkedin.com/in/stefan-roman-1911a9211/" },
    { "id": "alexandru-aioanei", "name": "Alexandru Aioanei", "image": "/team/alexandru-aioanei.jpg", "email": "alex03aioanei@gmail.com", "linkedin": "https://www.linkedin.com/in/alexandru-aioanei-7a8370255/" },
    { "id": "laurian-duma", "name": "Laurian Duma", "image": "/team/laurian-duma.jpeg", "email": "d_laurian@yahoo.com", "linkedin": "https://www.linkedin.com/in/laurian-duma/" }
  ]
}
```
Update `about.ts` types accordingly: `TeamMember = { id, name, image, email, linkedin }`, `AboutContent = { members: TeamMember[] }`.

- [ ] **Step 2: TeamMemberCard / TeamSection / AboutHero / AboutStory.** These become message-driven:
  - `TeamSection`: heading → `t("about.team.heading")`/keys; iterate `members`, pass `member` + the member's `role`/`description` resolved via `useTranslations("about.team.members")` → `tm(\`${member.id}.role\`)`, `tm(\`${member.id}.description\`)`.
  - `TeamMemberCard`: take `role`/`description` as props (now strings passed in), keep `name`/`image`/`email`/`linkedin` from the member object; aria-labels `Email {name}` / `{name} on LinkedIn` → add `work`-style keys or inline `useTranslations`. Add keys `about.team.emailAria` = `"Email {name}"` and `about.team.linkedinAria` = `"{name} on LinkedIn"` to `en.json` (and nl/ro copies) and use them.
  - `AboutStory`: `t("about.story.heading")` and `t.raw("about.story.paragraphs") as string[]`.
  - `AboutHero`: `about.hero.eyebrow|title|lead`.

- [ ] **Step 3: about/page.tsx (server).** Replace the static `metadata` with:
```tsx
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { buildAlternates } from "@/i18n/alternates";
import type { Locale } from "@/lib/locale";

export async function generateMetadata({
  params,
}: { params: Promise<{ locale: Locale }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "aboutPage" });
  const ta = await getTranslations({ locale, namespace: "about" });
  return {
    title: t("metaTitle"),
    description: ta("hero.lead"),
    alternates: buildAlternates("/about", locale),
  };
}
```
The page body keeps rendering `AboutStory`/`WhatWeDo` (no inline strings of its own).

- [ ] **Step 4: team/page.tsx, clients/page.tsx, contact/page.tsx.** Apply the same `generateMetadata` pattern with the right namespace (`teamPage`/`clientsPage`/`contactPage`) and `buildAlternates("/team"|"/clients"|"/contact", locale)`. For the inline page hero strings (e.g. team page `"Our team"`, `"A team that ships."`, subheading; clients page `"Our work"`, title, subheading; contact page hero from `contactPage.hero.*`), make each page `async` and use `await getTranslations(namespace)` to render them. ContactInfo labels come from the `contactInfo` namespace (already keyed); the contact details values (email/phone/etc.) stay sourced from `content/contact.ts`.

- [ ] **Step 5: Verify + stage**

Run: `cd frontend && npm run typecheck` → clean; `npm run dev` → `/about`, `/team`, `/clients`, `/contact` render identical English; view-source shows the translated `<title>` and `<link rel="alternate" hreflang>` tags.
```bash
git add frontend/src/content/about.json frontend/src/content/about.ts frontend/src/components/about "frontend/src/app/[locale]/(marketing)/about" "frontend/src/app/[locale]/(marketing)/team" "frontend/src/app/[locale]/(marketing)/clients" "frontend/src/app/[locale]/(marketing)/contact" frontend/messages
```

---

## Task 13: Wire the booking-manage page

**Files & namespaces:**
- `frontend/src/app/[locale]/(marketing)/manage/[token]/page.tsx` (client) → `manage.*`

**Interfaces:** Consumes `manage` (Task 7). `rescheduleTooltipAllowed` uses ICU plural `{max, plural, one {time} other {times}}`.

- [ ] **Step 1:** Add `const t = useTranslations("manage");`. Replace every literal per the `manage.*` keys: `loading`, `linkNotFoundTitle/Body`, `cancelledTitle/Body`, `bookingTitle`, `reschedule`, the reschedule tooltips (`rescheduleTooltipAllowed` with `{ max: max_reschedules }`, `rescheduleClosedTooltip`), `cancelBooking`, the SubmitFeedback `cancelling`/`cancelSuccess`/`cancelError`, `confirmCancel`, `keepIt`, `yesCancel`, `cancellationClosed`. The dynamic `{whenLabel}` (formatted date) stays computed in code.

- [ ] **Step 2: Verify + stage**

Run: `cd frontend && npm run typecheck` → clean.
```bash
git add "frontend/src/app/[locale]/(marketing)/manage"
```

---

## Task 14: DeepL translation script + generate NL/RO

**Files:**
- Create: `frontend/scripts/translate-i18n.mjs`
- Create/commit: `frontend/messages/.translation-cache.json`
- Generate: `frontend/messages/nl.json`, `frontend/messages/ro.json`

**Interfaces:** Reads `messages/en.json`, writes `nl.json`/`ro.json`, preserving prior human edits for unchanged source keys.

- [ ] **Step 1: Pre-flight — verify the DeepL key.** Confirm `DEEPL_API_KEY` is available locally (the backend already uses DeepL — reuse the same key). Determine the endpoint: keys ending `:fx` → Free (`https://api-free.deepl.com`), otherwise Pro (`https://api.deepl.com`). If absent, stop and ask Stefan for the key before proceeding.

- [ ] **Step 2: Create `frontend/scripts/translate-i18n.mjs`**

```js
#!/usr/bin/env node
/**
 * Translate messages/en.json → nl.json + ro.json with DeepL.
 * - Incremental: only (re)translates leaf strings whose English source changed
 *   since the last run (tracked in messages/.translation-cache.json), so manual
 *   edits to nl/ro are preserved.
 * - Protects ICU placeholders ({name}) and the brand "Roman Technologies" from
 *   translation via DeepL XML tag handling.
 *
 * Usage:  DEEPL_API_KEY=xxxx node scripts/translate-i18n.mjs
 */
import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MESSAGES = path.join(__dirname, "..", "messages");
const TARGETS = { nl: "NL", ro: "RO" };
const KEY = process.env.DEEPL_API_KEY;
if (!KEY) {
  console.error("DEEPL_API_KEY is not set. Aborting.");
  process.exit(1);
}
const ENDPOINT = KEY.endsWith(":fx")
  ? "https://api-free.deepl.com/v2/translate"
  : "https://api.deepl.com/v2/translate";

const DO_NOT_TRANSLATE = ["Roman Technologies"];

const hash = (s) => createHash("sha1").update(s).digest("hex");
const isObj = (v) => v && typeof v === "object" && !Array.isArray(v);

// Flatten nested object/array into { "a.b.0": "leaf string" } (strings only).
function flatten(node, prefix = "", out = {}) {
  if (typeof node === "string") {
    out[prefix] = node;
  } else if (Array.isArray(node)) {
    node.forEach((v, i) => flatten(v, prefix ? `${prefix}.${i}` : `${i}`, out));
  } else if (isObj(node)) {
    for (const k of Object.keys(node)) flatten(node[k], prefix ? `${prefix}.${k}` : k, out);
  }
  return out;
}

function setPath(root, dottedKey, value) {
  const parts = dottedKey.split(".");
  let cur = root;
  for (let i = 0; i < parts.length - 1; i++) {
    const k = parts[i];
    const nextIsIndex = /^\d+$/.test(parts[i + 1]);
    if (cur[k] === undefined) cur[k] = nextIsIndex ? [] : {};
    cur = cur[k];
  }
  cur[parts[parts.length - 1]] = value;
}

// Wrap ICU placeholders + brand terms so DeepL leaves them verbatim.
function protect(text) {
  let t = text.replace(/\{[^}]+\}/g, (m) => `<x>${m}</x>`);
  for (const term of DO_NOT_TRANSLATE) {
    t = t.split(term).join(`<x>${term}</x>`);
  }
  return t;
}
function unprotect(text) {
  return text.replace(/<x>(.*?)<\/x>/g, "$1");
}

async function deepl(texts, targetLang) {
  const body = new URLSearchParams();
  for (const t of texts) body.append("text", protect(t));
  body.append("source_lang", "EN");
  body.append("target_lang", targetLang);
  body.append("tag_handling", "xml");
  body.append("ignore_tags", "x");
  body.append("preserve_formatting", "1");

  const res = await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      Authorization: `DeepL-Auth-Key ${KEY}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });
  if (!res.ok) throw new Error(`DeepL ${res.status}: ${await res.text()}`);
  const json = await res.json();
  return json.translations.map((t) => unprotect(t.text));
}

async function main() {
  const en = JSON.parse(await readFile(path.join(MESSAGES, "en.json"), "utf8"));
  const cachePath = path.join(MESSAGES, ".translation-cache.json");
  let cache = {};
  try {
    cache = JSON.parse(await readFile(cachePath, "utf8"));
  } catch {
    cache = {};
  }

  const enFlat = flatten(en);

  for (const [locale, lang] of Object.entries(TARGETS)) {
    const outPath = path.join(MESSAGES, `${locale}.json`);
    let existing = {};
    try {
      existing = JSON.parse(await readFile(outPath, "utf8"));
    } catch {
      existing = {};
    }
    const existingFlat = flatten(existing);
    const result = {};
    cache[locale] = cache[locale] || {};

    // Decide which keys need (re)translation.
    const toTranslate = [];
    for (const [key, source] of Object.entries(enFlat)) {
      const h = hash(source);
      const unchanged = cache[locale][key] === h && existingFlat[key] !== undefined;
      if (unchanged) {
        setPath(result, key, existingFlat[key]); // keep prior (possibly human-edited) value
      } else {
        toTranslate.push({ key, source, h });
      }
    }

    // Translate in batches of 50 (DeepL allows up to 50 text params per call).
    for (let i = 0; i < toTranslate.length; i += 50) {
      const batch = toTranslate.slice(i, i + 50);
      const translated = await deepl(batch.map((b) => b.source), lang);
      batch.forEach((b, j) => {
        setPath(result, b.key, translated[j]);
        cache[locale][b.key] = b.h;
      });
      console.log(`[${locale}] ${Math.min(i + 50, toTranslate.length)}/${toTranslate.length}`);
    }

    await writeFile(outPath, JSON.stringify(result, null, 2) + "\n", "utf8");
    console.log(`[${locale}] wrote ${outPath} (${toTranslate.length} new/changed)`);
  }

  await writeFile(cachePath, JSON.stringify(cache, null, 2) + "\n", "utf8");
  console.log("Done. Review nl.json / ro.json before committing.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
```

- [ ] **Step 3: Add an npm script.** In `frontend/package.json` `scripts`, add: `"i18n:translate": "node scripts/translate-i18n.mjs"`.

- [ ] **Step 4: Run it**

Run: `cd frontend && DEEPL_API_KEY=<key> npm run i18n:translate`
Expected: progress logs; `nl.json` + `ro.json` rewritten with translations; `.translation-cache.json` created.

- [ ] **Step 5: Sanity-check the output.** Confirm: ICU vars like `{recipient}`, `{query}`, `{max}`, `{year}` and the plural block survived verbatim; `Roman Technologies` is untranslated; JSON is valid (`node -e "require('./messages/nl.json');require('./messages/ro.json');console.log('ok')"`).

- [ ] **Step 6: Human review (Stefan).** Stefan reviews `nl.json`/`ro.json` for wording. This is the review gate from the spec — do not auto-commit; surface the files for review.

- [ ] **Step 7: Stage**

```bash
git add frontend/scripts/translate-i18n.mjs frontend/messages/nl.json frontend/messages/ro.json frontend/messages/.translation-cache.json frontend/package.json
```

---

## Task 15: SEO — home alternates + hreflang verification

**Files:**
- Modify: `frontend/src/app/[locale]/(marketing)/page.tsx` (home) — add `generateMetadata` with `buildAlternates("/", locale)`.
- Verify hreflang renders on all localized pages.

- [ ] **Step 1: Home metadata.** `page.tsx` (home) is a server component. Add:
```tsx
import type { Metadata } from "next";
import { buildAlternates } from "@/i18n/alternates";
import type { Locale } from "@/lib/locale";

export async function generateMetadata({
  params,
}: { params: Promise<{ locale: Locale }> }): Promise<Metadata> {
  const { locale } = await params;
  return { alternates: buildAlternates("/", locale) };
}
```

- [ ] **Step 2: Verify hreflang**

`npm run dev`, then:
Run: `curl -s http://localhost:3000/about | grep -i hreflang`
Expected: `<link rel="alternate" hreflang="en" .../about>`, `hreflang="nl" .../nl/about`, `hreflang="ro" .../ro/about`, `hreflang="x-default" .../about`.

- [ ] **Step 3: Stage**

```bash
git add "frontend/src/app/[locale]/(marketing)/page.tsx"
```

---

## Task 16: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Unit + component tests**

Run: `cd frontend && npx vitest run`
Expected: all green, including `locale.test.ts`, `LanguageSwitcher.test.tsx`, the updated `LoginForm.test.tsx`, and any pre-existing suites.

- [ ] **Step 2: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: no errors; build output lists `/[locale]` routes and the unchanged `/dashboard`, `/w/[slug]`.

- [ ] **Step 3: Live cross-viewport behavior (Playwright MCP).** Start `npm run dev`. For viewports 375×812 (mobile), 768×1024 (tablet), 1280×800 (laptop), 1920×1080 (desktop), verify on `/`:
  - The switcher is visible/reachable at every size (nav globe on ≥md, hamburger→drawer pills on <md, footer control at all sizes).
  - Switching EN→NL→RO from **each** placement updates the URL prefix and visibly changes copy to the target language.
  - On a deep page (`/about`), switching keeps you on the same page (`/nl/about`).

- [ ] **Step 4: Geo + persistence**

Run (dev server up):
```bash
curl -sI -H "x-vercel-ip-country: RO" http://localhost:3000/ | grep -i location      # → /ro
curl -sI -H "x-vercel-ip-country: NL" http://localhost:3000/contact | grep -i location # → /nl/contact
curl -sI -H "x-vercel-ip-country: US" http://localhost:3000/ | grep -i -E "location|set-cookie" # no locale redirect; NEXT_LOCALE=en
curl -sI -H "x-vercel-ip-country: RO" --cookie "NEXT_LOCALE=en" http://localhost:3000/ | grep -i location # no /ro (cookie wins)
```
Expected: as annotated.

- [ ] **Step 5: Dashboard + widget unaffected**

Run: `curl -sI http://localhost:3000/dashboard | grep -i location` → `/log-in`.
Load `/w/<slug>` and `/dashboard` (after login) in the browser → render exactly as before, no locale prefix, no console errors.

- [ ] **Step 6: Translation completeness spot-check.** On `/nl` and `/ro`, confirm nav, hero, pricing, footer, and team copy are in the target language (not English) and no raw message keys (e.g. `hero.title`) appear anywhere.

- [ ] **Step 7: Report results.** Summarize: tests passed (counts), build status, viewport matrix, geo matrix, dashboard-unaffected confirmation. Surface `nl.json`/`ro.json` for Stefan's translation review. Do not commit unless told.

---

## Self-Review (against the spec)

**Spec coverage:**
- §2 whole-site scope → Tasks 8–13 cover every marketing surface (chrome, home sections, work, pricing, content pages, manage). ✅
- §2 prefixed `as-needed` URLs → Task 1 routing + Task 3 `[locale]` move. ✅
- §2 three placements → Task 6 (nav/drawer/footer). ✅
- §2 DeepL auto + review → Task 14 (incremental, placeholder/brand protection, human-review gate). ✅
- §4.1/4.2 routing + file moves; dashboard untouched → Tasks 1, 3; verified in Tasks 3, 4, 16. ✅
- §4.3 `<html lang>` strategy (static + client sync + hreflang) → Task 3 Step 3–4 + Tasks 12/15. ✅
- §4.4 middleware geo + persistence + auth + `stripLocale` → Task 4. ✅
- §5 catalogs + content/copy split → Tasks 7, 10, 12. ✅
- §6 switcher UX/brand + smooth `startTransition` switch → Task 5. ✅
- §7 hreflang + per-locale titles → Tasks 12, 15. ✅
- §8 testing (vitest unit/component + Playwright live + geo) → Tasks 2, 5, 16. ✅
- §10 verify next-intl version, DeepL key, geo header → Task 1 Step 1, Task 14 Step 1, Task 4 Steps 2–4. ✅

**Type consistency:** `Locale`, `LOCALES`, `LOCALE_NAMES`, `resolveLocaleFromCountry`, `stripLocale`, `hasLocalePrefix` defined in Task 2 and consumed with the same signatures in Tasks 1/4/5. `buildAlternates(path, locale)` defined in Task 1, used identically in Tasks 12/15. Message namespaces in Task 7 match every `t("ns")` consumer in Tasks 5/6/8–13.

**Placeholder scan:** No "TBD"/"add error handling"-style placeholders; the one human step (DeepL review, Task 14 Step 6) is an explicit gate, and the per-file wiring tasks reference concrete keys that exist verbatim in Task 7's `en.json`.
