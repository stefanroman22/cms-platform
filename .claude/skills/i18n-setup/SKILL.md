---
name: i18n-setup
description: Set up multilingual support in a Vite + React 19 SPA using react-i18next — locale URL routing, messages files, language switcher, LocaleGuard. Use during scaffolding whenever the build target supports more than one locale, or whenever the design's intended market is multilingual. Triggers on phrases like "make it multilingual", "add locales", "i18n", "translate", or any explicit locale list in the prompt. Messages come from the CMS per-locale once connected; local messages files are the pre-connection seed.
---

# i18n Setup

This skill wires up multilingual support with **react-i18next** — the standard i18n library for React SPAs. NEVER use `next-intl`, `next-i18next` (Next.js-specific), or `react-intl`.

## Default locales

If the user hasn't specified, default to: **`en` (default), `nl`**. The agent's user (Stefan) is Netherlands-based with EU clients, so EN + NL covers most cases. Common additions: `fr`, `de`, `es`, `it`.

## Install

These packages are already part of the `vite-react-scaffolding` install sequence, listed here for reference:

```powershell
npm install react-i18next i18next i18next-browser-languagedetector
```

`i18next-browser-languagedetector` is used only during development to auto-detect the browser's language preference; in production the URL segment (`/:locale`) is authoritative.

## File structure

```
<project>/
  src/
    i18n/
      config.ts                  ← react-i18next init (resources, fallbackLng, supportedLngs)
      messages/
        en.json                  ← default; full English copy (namespaced t() shape)
        nl.json                  ← Dutch seed (pre-connection fallback)
        fr.json                  ← optional
    components/
      LocaleGuard.tsx            ← validates /:locale segment; calls i18n.changeLanguage
      LanguageSwitcher.tsx       ← navigate to other locale prefix + i18n.changeLanguage + persist
    lib/
      store.ts                   ← useLocaleStore (Zustand persist) — persists chosen locale
      cms-content.ts             ← build-time + client merge of CMS payload over messages
```

The `/:locale` segment lives in **React Router** (`routes.tsx`), not in a Next.js middleware. The locale URL is the canonical locale source; `useLocaleStore` only persists the user's last choice for redirect-on-load.

## `src/i18n/config.ts`

```ts
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { SUPPORTED_LOCALES, DEFAULT_LOCALE } from "@/lib/config";

// Import message files directly — bundled at build time; CMS merges over them at runtime.
import en from "./messages/en.json";
import nl from "./messages/nl.json";

export type Locale = (typeof SUPPORTED_LOCALES)[number];

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      nl: { translation: nl },
    },
    fallbackLng: DEFAULT_LOCALE,
    supportedLngs: [...SUPPORTED_LOCALES],
    interpolation: { escapeValue: false },   // React already escapes
    defaultNS: "translation",
  });

export default i18n;
```

Import `src/i18n/config.ts` once at the top of `src/main.tsx` (side-effect import) so i18next is initialized before any component renders.

## `src/main.tsx` integration

```tsx
// src/main.tsx
import "./i18n/config";                // init i18next (side effect)
import { ViteReactSSG } from "vite-react-ssg";
import { routes } from "./routes";

// ViteReactSSG (NOT ViteSSG) consumes { routes } as an object — NOT a bare array.
// Do NOT wrap it in <RouterProvider>; that component does not exist here.
export const createRoot = ViteReactSSG({ routes });
```

App-level providers (`I18nextProvider`, `QueryClientProvider`, etc.) belong in the **root layout route element** that wraps `<Outlet />`, not around a router. Wire them in `src/routes.tsx`:

```tsx
// src/routes.tsx (root layout wraps every page; providers live here, NOT around a router)
import { Outlet } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import i18n from "./i18n/config";

function RootLayout() {
  return (
    <I18nextProvider i18n={i18n}>
      <LocaleGuard>
        <Outlet />
      </LocaleGuard>
    </I18nextProvider>
  );
}
export const routes = [
  { path: "/:locale", element: <RootLayout />, children: [ /* pages */ ] },
  // redirect "/" → default locale
];
```

See the `src/routes.tsx` section below for the full locale-prefix route tree.

## `src/components/LocaleGuard.tsx`

The locale segment is validated and applied here — this replaces `next-intl`'s middleware and `setRequestLocale`.

```tsx
import { useEffect } from "react";
import { Outlet, useParams, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LOCALES, DEFAULT_LOCALE } from "@/lib/config";
import type { Locale } from "@/i18n/config";
import { useLocaleStore } from "@/lib/store";

export function LocaleGuard() {
  const { locale } = useParams<{ locale: string }>();
  const { i18n } = useTranslation();
  const setLocale = useLocaleStore((s) => s.setLocale);

  const isValid = SUPPORTED_LOCALES.includes(locale as Locale);

  useEffect(() => {
    if (isValid && locale !== i18n.language) {
      i18n.changeLanguage(locale);
      setLocale(locale as Locale);
    }
  }, [locale, i18n, isValid, setLocale]);

  if (!isValid) {
    return <Navigate to={`/${DEFAULT_LOCALE}`} replace />;
  }

  return <Outlet />;
}
```

This component is the layout-level route for `/:locale` in `routes.tsx`. Every page route nests under it.

## `src/routes.tsx` (locale prefix pattern)

```tsx
import { lazy } from "react";
import type { RouteObject } from "react-router-dom";
import { LocaleGuard } from "@/components/LocaleGuard";
import { RouteLoader } from "@/components/RouteLoader";

const HomePage  = lazy(() => import("@/pages/HomePage"));
const AboutPage = lazy(() => import("@/pages/AboutPage"));

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Navigate to={`/${DEFAULT_LOCALE}`} replace />,
  },
  {
    path: "/:locale",
    element: <LocaleGuard />,
    children: [
      { index: true,  element: <Suspense fallback={<RouteLoader />}><HomePage /></Suspense> },
      { path: "about", element: <Suspense fallback={<RouteLoader />}><AboutPage /></Suspense> },
    ],
  },
];
```

## Using translations in components

### Functional component (all pages are client components in a Vite SPA)

```tsx
import { useTranslation } from "react-i18next";

export function HeroSection() {
  const { t } = useTranslation();
  return (
    <section>
      <h1>{t("hero.headline")}</h1>
      <p>{t("hero.subheadline")}</p>
      <button>{t("hero.cta")}</button>
    </section>
  );
}
```

### Default namespace with dotted key paths (always use this)

```tsx
const { t } = useTranslation();      // default "translation" namespace
t("hero.headline");                  // dotted key path into messages/<locale>.json
```

> **Warning:** Do NOT split translations into multiple react-i18next namespaces (e.g., `useTranslation("hero")`). Doing so would require separate namespace files, which breaks the single-file `messages/<locale>.json` shape that the CMS connector merges over. Always use the default namespace with dotted key paths.

### Raw array/object values (repeaters, key_value)

```tsx
const items = t("services.items", { returnObjects: true }) as ServiceItem[];
```

Equivalent to next-intl's `t.raw("services.items")`.

### Locale-aware internal links

Use React Router's `Link` with the locale prefix:

```tsx
import { Link, useParams } from "react-router-dom";

export function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const { locale } = useParams<{ locale: string }>();
  return <Link to={`/${locale}${to}`}>{children}</Link>;
}
```

NEVER hard-code a locale prefix; always read it from `useParams()`.

## `src/i18n/messages/en.json` — default-locale seed (real copy)

```json
{
  "metadata": {
    "siteName": "<Business Name>",
    "description": "<one-line description>"
  },
  "nav": {
    "home": "Home",
    "about": "About",
    "pricing": "Pricing",
    "contact": "Contact",
    "loader": {
      "routeLoading": "Loading…"
    }
  },
  "hero": {
    "headline": "<from design>",
    "subheadline": "<from design>",
    "cta": "<from design>"
  },
  "footer": {
    "rights": "© {year} <Business>. All rights reserved."
  }
}
```

## `src/i18n/messages/nl.json` — Dutch seed (pre-connection fallback)

```json
{
  "metadata": {
    "siteName": "<Business Name>",
    "description": "<one-line description>"
  },
  "nav": {
    "home": "Home",
    "about": "About",
    "pricing": "Pricing",
    "contact": "Contact",
    "loader": {
      "routeLoading": "Laden…"
    }
  },
  "hero": {
    "headline": "<from design>",
    "subheadline": "<from design>",
    "cta": "<from design>"
  },
  "footer": {
    "rights": "© {year} <Business>. Alle rechten voorbehouden."
  }
}
```

These local files are the **build-time seed** used until the site is CMS-connected. Once connected, the CMS holds the per-locale content and **auto-translates** the default locale into the others (DeepL when configured, else echoes the source). The default-locale file holds the real copy; non-default seed files can mirror the default — the CMS will translate after connection. Do NOT hand-maintain `[XX]` placeholders.

## `src/lib/store.ts` — locale persistence (Zustand)

`useLocaleStore` (already in `src/lib/store.ts` from `vite-react-scaffolding`) persists the user's chosen locale to `localStorage`. On first load, `LocaleGuard` reads the URL segment; the store is only used for redirect-on-load in `src/main.tsx`.

```ts
// Relevant slice from store.ts — see vite-react-scaffolding for the full file.
interface LocaleState {
  locale: Locale;
  setLocale: (l: Locale) => void;
}

export const useLocaleStore = create<LocaleState>()(
  persist(
    (set) => ({
      locale: DEFAULT_LOCALE,
      setLocale: (locale) => set({ locale }),
    }),
    { name: "locale-store" }
  )
);
```

## `src/components/LanguageSwitcher.tsx`

```tsx
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LOCALES } from "@/lib/config";
import type { Locale } from "@/i18n/config";
import { useLocaleStore } from "@/lib/store";

export function LanguageSwitcher() {
  const { locale: current } = useParams<{ locale: string }>();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const setLocale = useLocaleStore((s) => s.setLocale);

  function switchLocale(next: Locale) {
    if (next === current) return;
    // Replace the locale prefix in the current path, keeping the rest of the route.
    const newPath = pathname.replace(`/${current}`, `/${next}`);
    i18n.changeLanguage(next);
    setLocale(next);
    navigate(newPath, { replace: true });
  }

  return (
    <select
      value={current}
      onChange={(e) => switchLocale(e.target.value as Locale)}
      className="bg-transparent border rounded px-2 py-1 cursor-pointer"
      aria-label="Language"
    >
      {SUPPORTED_LOCALES.map((l) => (
        <option key={l} value={l}>{l.toUpperCase()}</option>
      ))}
    </select>
  );
}
```

Place it in the header. Style to match the design.

## CMS content wiring

`src/lib/cms-content.ts` fetches `GET {VITE_CMS_ENDPOINT}/<locale>` at build time (and on the client for freshness) and merges the response over the local `messages/<locale>.json` seed. The `toMessages` transform maps CMS service keys into the same nested namespace shape — `t("home_hero.title")`, `t.raw`-equivalent via `{ returnObjects: true }`.

```ts
// VITE_ prefix required for Vite client bundles
const CMS = import.meta.env.VITE_CMS_ENDPOINT as string | undefined;

export async function loadMessages(locale: string) {
  if (CMS) {
    try {
      const res = await fetch(`${CMS}/${locale}`);
      if (res.ok) return toMessages(await res.json());
    } catch {
      // CMS unreachable → fall through to seed
    }
  }
  // Pre-connection (or CMS unreachable): seed is already bundled via config.ts resources.
  return null; // i18next falls back to bundled resources automatically
}
```

## hreflang and sitemap

hreflang `<link>` tags and `public/sitemap.xml` are the responsibility of the **`seo-pro`** skill (a sibling skill). See that skill for the `src/seo/sitemap.gen.ts` prebuild script. Do NOT duplicate that logic here.

## Static params (pre-render)

`generateStaticParams()` is a Next.js concept. In the Vite SSG model, the locale × route pre-render list is declared in `src/main.tsx` as an explicit array passed to `vite-react-ssg`. See `vite-react-scaffolding` for the `main.tsx` pattern.

## When done — verification checklist

1. Visit `http://127.0.0.1:5173/` — React Router redirects to `/en` (or persisted locale from localStorage).
2. Visit `http://127.0.0.1:5173/nl/` — renders Dutch seed (no `[XX]` placeholders); after CMS connection it shows live CMS content for `nl`.
3. Inspect the DOM: `<html lang="en">` on `/en/`, `<html lang="nl">` on `/nl/`.
4. hreflang `<link rel="alternate">` tags are present in each pre-rendered HTML (added by `seo-pro`, baked by vite-react-ssg).
5. Language switcher swaps between locales without losing the sub-path.
6. `npm run build` exits 0 — no missing translation keys, no TypeScript errors.
7. `/sitemap.xml` includes every locale × every path (generated by `src/seo/sitemap.gen.ts`).
8. With `VITE_CMS_ENDPOINT` set, `cms-content.ts` fetches `{endpoint}/{locale}` and `toMessages` maps service keys into namespaces (verify a known `t("<service_key>.<field>")` resolves).
