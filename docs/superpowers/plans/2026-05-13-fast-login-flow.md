# Fast Login Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/` → `/log-in` → `/dashboard` paint within ~500ms perceived on production, by splitting public pages into Server Components + small client islands and trimming hydration weight.

**Architecture:** Route-group restructure (`(marketing)`) lets the marketing layout become a Server Component. Header is split into a server shell + small client island (mobile drawer + auth badge). Login page becomes a Server Component that mounts a `<LoginForm />` client island. `LoadingScreen` is dynamic-imported. `AuthProvider` is scoped to `(marketing)` and skips the `/auth/me` network call when no auth cookie is present. Dashboard gets a `loading.tsx` skeleton plus chunk-prefetch on hover from the login success view.

**Tech Stack:** Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind CSS v4, framer-motion (kept but island-only), Vitest + Testing Library, Supabase backend.

**Branch:** `feat/fast-login-flow` (already created off `dev`).

**Commit policy:** Per Stefan's standing rule, **never run `git commit` without explicit go-ahead from Stefan**. Each task ends with a "request commit approval" step. Do not commit autonomously.

**Spec:** [docs/superpowers/specs/2026-05-13-fast-login-flow-design.md](../specs/2026-05-13-fast-login-flow-design.md)

---

## File Plan

### To create
| Path | Responsibility |
|---|---|
| `frontend/src/app/(marketing)/layout.tsx` | Server Component. Wraps marketing routes with `<MarketingProviders>` + `<Header />` + `<main>` + `<Footer />`. |
| `frontend/src/app/(marketing)/providers.tsx` | Client. Mounts `<LoadingProvider>` + `<AuthProvider>` scoped to marketing routes. |
| `frontend/src/app/(marketing)/page.tsx` | Server Component. Root `/` page. Same JSX, no `"use client"`. |
| `frontend/src/app/(marketing)/log-in/page.tsx` | Server Component. Renders static card chrome + heading + `<LoginForm />` island. |
| `frontend/src/app/(marketing)/log-in/LoginForm.tsx` | Client island. Form state, submit, framer slide-in, success view. |
| `frontend/src/app/(marketing)/log-in/__tests__/LoginForm.test.tsx` | Vitest tests for LoginForm behavior. |
| `frontend/src/components/HeaderRightCluster.tsx` | Client island. Mobile drawer state, auth badge (`useAuth`), hamburger, drawer overlay. |
| `frontend/src/components/__tests__/HeaderRightCluster.test.tsx` | Vitest tests for cluster. |
| `frontend/src/context/__tests__/auth.test.tsx` | Vitest tests for cookie-sniff early return. |
| `frontend/src/app/dashboard/loading.tsx` | Server Component skeleton (sidebar block + topbar + content placeholders). |

### To modify
| Path | Change |
|---|---|
| `frontend/src/app/layout.tsx` | Drop `<Providers>` + `<SiteShell>` wrap. Body now just renders `{children}`. Theme script unchanged. |
| `frontend/src/components/Header.tsx` | Strip `"use client"`. Static markup only. Renders nav links as plain `<a>` + slot `<HeaderRightCluster />` at right. |
| `frontend/src/context/auth.tsx` | `useEffect` early-returns when no auth cookie present. |
| `frontend/src/app/globals.css` | Add `@keyframes fadeDown` + `.animate-fade-down` utility for Header bar entrance. |

### To delete
| Path | Reason |
|---|---|
| `frontend/src/app/page.tsx` | Replaced by `(marketing)/page.tsx`. |
| `frontend/src/app/log-in/page.tsx` | Replaced by `(marketing)/log-in/page.tsx`. |
| `frontend/src/app/log-in/` | Empty dir after move. |
| `frontend/src/components/SiteShell.tsx` | Route groups handle the dashboard-vs-marketing branch. |
| `frontend/src/components/Providers.tsx` | Replaced by per-group providers. |

---

## Task 1: CSS keyframe for Header entrance

**Files:**
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Open `frontend/src/app/globals.css` and append the keyframe + utility class at the end of the file**

Add:

```css
@keyframes fadeDown {
  from {
    opacity: 0;
    transform: translateY(-16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-down {
  animation: fadeDown 0.4s ease-out both;
}
```

- [ ] **Step 2: Verify CSS still compiles**

Run: `cd frontend && npm run build`
Expected: build completes, no PostCSS error.

(If build is too slow at this stage, run `npm run lint` instead — Tailwind v4 CSS errors surface there too. Build is the authoritative check.)

- [ ] **Step 3: Request commit approval from Stefan**

Proposed message:
```
feat(fe): add fadeDown keyframe for static Header entrance
```

---

## Task 2: Dashboard `loading.tsx` skeleton

**Files:**
- Create: `frontend/src/app/dashboard/loading.tsx`

- [ ] **Step 1: Create `frontend/src/app/dashboard/loading.tsx`**

```tsx
/**
 * Streams instantly while the dashboard route segment compiles and
 * the page's data fetches. No client JS — pure server-rendered HTML
 * + Tailwind utility classes. Pulse via Tailwind's `animate-pulse`.
 */
export default function DashboardLoading() {
  return (
    <div className="flex min-h-screen bg-zinc-950" aria-busy="true" aria-label="Loading dashboard">
      {/* Sidebar placeholder */}
      <aside className="hidden w-64 border-r border-white/[0.08] p-4 md:block">
        <div className="h-10 w-32 animate-pulse rounded bg-white/[0.06]" />
        <div className="mt-8 space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-8 w-full animate-pulse rounded bg-white/[0.04]" />
          ))}
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        {/* Topbar placeholder */}
        <div className="flex h-16 items-center justify-between border-b border-white/[0.08] px-6">
          <div className="h-6 w-48 animate-pulse rounded bg-white/[0.06]" />
          <div className="h-8 w-8 animate-pulse rounded-full bg-white/[0.06]" />
        </div>

        {/* Content placeholders */}
        <div className="grid flex-1 gap-4 p-6 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-40 animate-pulse rounded-xl border border-white/[0.06] bg-white/[0.02]"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Manual sanity check**

Run: `cd frontend && npm run dev`
Visit `http://localhost:3000/dashboard` while signed out (route renders skeleton briefly before redirect or content). Confirm skeleton appears.

(If middleware redirects too fast to see it, hit a deep dashboard route that exists — e.g. `/dashboard/account` — and observe in DevTools the `loading.tsx` HTML payload precedes the page payload.)

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: clean.

- [ ] **Step 4: Request commit approval**

Proposed message:
```
feat(fe): dashboard skeleton loading.tsx for streamed first paint
```

---

## Task 3: ~~Auth context — cookie-sniff early return~~ DROPPED 2026-05-13

**Decision:** Skipped. Backend `sid` cookie is `HttpOnly`, so `document.cookie` cannot read it from JS. The `getMe()` call stays as-is — async, non-blocking, no first-paint regression. Avoiding a backend change (non-HttpOnly companion cookie) keeps the auth surface minimal.

Skip directly to Task 4.

---

<details>
<summary>Original Task 3 (kept for reference)</summary>

**Files:**
- Modify: `frontend/src/context/auth.tsx`
- Create: `frontend/src/context/__tests__/auth.test.tsx`

**Note on cookie name:** The backend's session cookie name and `HttpOnly` flag must be confirmed before writing test/impl. Inspect `backend/auth_service/routers/auth.py` for the `Set-Cookie` value used on login. The spec uses `auth_session` as placeholder.

- [ ] **Step 1: Identify the actual session cookie**

Run: `cd backend && grep -nE "set_cookie|Set-Cookie" auth_service/routers/auth.py`
Read the result. Note: (a) the cookie key name, (b) whether `httponly=True`.

**Decision:**
- If the cookie is **NOT** `HttpOnly` → use `document.cookie.includes("<key>=")` as the gate.
- If the cookie **IS** `HttpOnly` → the JS cookie sniff is impossible. Stop. Tell Stefan: "Session cookie is HttpOnly, can't sniff from JS. Two options: (a) backend also sets a non-HttpOnly `auth_present=1` companion cookie, or (b) skip Task 3 and accept the `getMe()` call on every marketing page mount. Which?"

The rest of this task assumes a non-HttpOnly cookie key, referred to as `<COOKIE_KEY>` below. Substitute the actual name when writing code.

- [ ] **Step 2: Write the failing test**

Create `frontend/src/context/__tests__/auth.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "../auth";

function Probe() {
  const { isLoggedIn } = useAuth();
  return <div data-testid="state">{isLoggedIn ? "in" : "out"}</div>;
}

beforeEach(() => {
  global.fetch = vi.fn();
  Object.defineProperty(document, "cookie", { writable: true, configurable: true, value: "" });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AuthProvider", () => {
  it("does NOT call /auth/me when no session cookie is present", async () => {
    document.cookie = "";
    const { getByTestId } = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId("state").textContent).toBe("out");
    });

    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("DOES call /auth/me when a session cookie is present", async () => {
    document.cookie = "<COOKIE_KEY>=abc123";
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ id: "u_1", email: "a@b.c" }),
    });

    const { getByTestId } = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId("state").textContent).toBe("in");
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/auth/me",
      expect.objectContaining({ credentials: "include" })
    );
  });
});
```

Replace `<COOKIE_KEY>` literal with the actual cookie name from Step 1 before saving.

- [ ] **Step 3: Run test, verify failure**

Run: `cd frontend && npx vitest run src/context/__tests__/auth.test.tsx`
Expected: the "does NOT call" test FAILS — current code calls `getMe()` unconditionally.

- [ ] **Step 4: Implement cookie-sniff in `frontend/src/context/auth.tsx`**

Replace the existing mount effect:

```tsx
  // Check auth state once on mount
  useEffect(() => {
    getMe().then((user) => setIsLoggedIn(!!user));
  }, []);
```

With:

```tsx
  // Check auth state once on mount.
  //
  // Optimization: if no session cookie is present, skip the /auth/me
  // roundtrip entirely. The user can't be logged in without it, so the
  // network call would always return 401 — wasteful on cold marketing
  // page loads (the case we care most about).
  useEffect(() => {
    if (typeof document === "undefined") return;
    if (!document.cookie.includes("<COOKIE_KEY>=")) {
      setIsLoggedIn(false);
      return;
    }
    getMe().then((user) => setIsLoggedIn(!!user));
  }, []);
```

Substitute `<COOKIE_KEY>` with the real cookie name.

- [ ] **Step 5: Run test, verify pass**

Run: `cd frontend && npx vitest run src/context/__tests__/auth.test.tsx`
Expected: both tests pass.

- [ ] **Step 6: Typecheck + lint**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: clean.

- [ ] **Step 7: Request commit approval**

Proposed message:
```
perf(fe-auth): skip /auth/me on marketing routes when no session cookie
```

</details>

---

## Task 4: Split Header into Server shell + `HeaderRightCluster` client island

**Files:**
- Create: `frontend/src/components/HeaderRightCluster.tsx`
- Create: `frontend/src/components/__tests__/HeaderRightCluster.test.tsx`
- Modify: `frontend/src/components/Header.tsx`

- [ ] **Step 1: Write failing test for HeaderRightCluster**

Create `frontend/src/components/__tests__/HeaderRightCluster.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HeaderRightCluster } from "../HeaderRightCluster";
import { AuthProvider } from "@/context/auth";

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({ ok: false });
  Object.defineProperty(document, "cookie", { writable: true, configurable: true, value: "" });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HeaderRightCluster", () => {
  it("renders 'Log In' link when logged out", () => {
    render(
      <AuthProvider>
        <HeaderRightCluster />
      </AuthProvider>
    );
    expect(screen.getByRole("link", { name: /log in/i })).toBeInTheDocument();
  });

  it("opens mobile drawer when hamburger clicked", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <HeaderRightCluster />
      </AuthProvider>
    );
    await user.click(screen.getByRole("button", { name: /open menu/i }));
    expect(screen.getByRole("button", { name: /close menu/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `cd frontend && npx vitest run src/components/__tests__/HeaderRightCluster.test.tsx`
Expected: FAIL — `HeaderRightCluster` not defined.

- [ ] **Step 3: Implement `HeaderRightCluster.tsx`**

Create `frontend/src/components/HeaderRightCluster.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, User } from "lucide-react";
import { Logo } from "@/components/ui/Logo";
import { backdrop, drawerRight, fadeIn, staggerFast } from "@/lib/animations";
import { ctaButtonCn, navLinkCn } from "@/lib/styles";
import { useAuth } from "@/context/auth";

const NAV_LINKS = [
  { label: "Home", href: "/" },
  { label: "About", href: "/about" },
  { label: "Contact", href: "/contact" },
];

export function HeaderRightCluster() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { isLoggedIn } = useAuth();
  const close = () => setMobileOpen(false);

  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  return (
    <>
      {/* Desktop auth slot — fades in once auth state resolves */}
      <div className="relative ml-2 hidden h-8 w-8 md:block">
        <AnimatePresence mode="wait">
          {isLoggedIn ? (
            <motion.div
              key="user-icon"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.2 }}
              className="absolute inset-0"
            >
              <button
                onClick={() => window.open("/dashboard", "cms-dashboard")}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/20"
                aria-label="Open dashboard"
              >
                <User className="h-4 w-4 cursor-pointer" />
              </button>
            </motion.div>
          ) : (
            <motion.div
              key="login-btn"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.2 }}
              className="absolute inset-0 flex items-center"
            >
              <Link href="/log-in" className={ctaButtonCn}>
                Log In
              </Link>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Mobile hamburger */}
      <button
        onClick={() => setMobileOpen(true)}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-zinc-400 transition-colors duration-200 hover:bg-white/5 hover:text-white md:hidden"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              key="backdrop"
              variants={backdrop}
              initial="hidden"
              animate="visible"
              exit="exit"
              onClick={close}
              className="fixed inset-0 z-50 bg-black/60 md:hidden"
              aria-hidden="true"
            />
            <motion.div
              key="drawer"
              variants={drawerRight}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed right-0 top-0 z-[51] flex h-dvh w-4/5 max-w-sm flex-col border-l border-white/[0.08] bg-zinc-950 sm:w-3/5 md:hidden"
            >
              <div className="flex h-14 shrink-0 items-center justify-between border-b border-white/[0.06] px-4 sm:h-16">
                <Logo />
                <button
                  onClick={close}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-zinc-400 transition-colors duration-200 hover:bg-white/5 hover:text-white"
                  aria-label="Close menu"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <motion.nav
                variants={staggerFast}
                initial="hidden"
                animate="visible"
                className="flex flex-col gap-1 p-4"
                aria-label="Mobile navigation"
              >
                {NAV_LINKS.map((link) => (
                  <motion.div key={link.label} variants={fadeIn}>
                    <Link
                      href={link.href}
                      onClick={close}
                      className={`block rounded-lg px-4 py-3 text-base ${navLinkCn}`}
                    >
                      {link.label}
                    </Link>
                  </motion.div>
                ))}

                <motion.div variants={fadeIn} className="pt-4">
                  {isLoggedIn ? (
                    <button
                      type="button"
                      onClick={() => {
                        close();
                        window.open("/dashboard", "cms-dashboard");
                      }}
                      className={ctaButtonCn}
                    >
                      Open Dashboard
                    </button>
                  ) : (
                    <Link href="/log-in" onClick={close} className={ctaButtonCn}>
                      Log In
                    </Link>
                  )}
                </motion.div>

                <motion.div variants={fadeIn} className="pt-2">
                  <Link href="/contact" onClick={close} className={ctaButtonCn}>
                    Get in touch
                  </Link>
                </motion.div>
              </motion.nav>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `cd frontend && npx vitest run src/components/__tests__/HeaderRightCluster.test.tsx`
Expected: both tests pass.

- [ ] **Step 5: Rewrite `Header.tsx` as Server Component**

Overwrite `frontend/src/components/Header.tsx`:

```tsx
import Link from "next/link";
import { Logo } from "@/components/ui/Logo";
import { navLinkCn } from "@/lib/styles";
import { HeaderRightCluster } from "@/components/HeaderRightCluster";

const NAV_LINKS = [
  { label: "Home", href: "/" },
  { label: "About", href: "/about" },
  { label: "Contact", href: "/contact" },
];

/**
 * Server Component. Static markup ships as HTML, no JS needed to render
 * the bar or nav links. The right-hand cluster (mobile drawer + auth
 * badge) is a small client island. Entrance animation is pure CSS
 * (`.animate-fade-down` from globals.css), so there is no framer
 * runtime cost on first paint.
 */
export default function Header() {
  return (
    <header className="fixed left-0 right-0 top-0 z-40 animate-fade-down border-b border-white/[0.1] bg-black">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:h-16 sm:px-6 lg:px-8">
        <Logo />

        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary navigation">
          {NAV_LINKS.map((link) => (
            <Link key={link.label} href={link.href} className={`px-4 py-2 ${navLinkCn}`}>
              {link.label}
            </Link>
          ))}
          <HeaderRightCluster />
        </nav>

        {/* Mobile: cluster owns the hamburger; nav links live in its drawer */}
        <div className="md:hidden">
          <HeaderRightCluster />
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 6: Confirm `Logo` is safe as a Server Component child**

Run: `grep -n "use client" frontend/src/components/ui/Logo.tsx`
- If `Logo` has `"use client"`, it stays a client island under the server `Header` — fine.
- If `Logo` is server-safe (no hooks, no event handlers), no change needed.
- Action: only stop if `Logo` uses `next/link` with handlers it depends on at module scope — unlikely. Note any concern and continue.

- [ ] **Step 7: Run all component tests**

Run: `cd frontend && npm test`
Expected: all green. Pay attention to any preexisting test that mounted `<Header />` directly — it now needs `AuthProvider` because `HeaderRightCluster` uses `useAuth`.

If a Header-related test fails because of the missing provider, wrap the render with `<AuthProvider>`.

- [ ] **Step 8: Typecheck + lint**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: clean.

- [ ] **Step 9: Request commit approval**

Proposed message:
```
refactor(fe-header): split into server shell + client right-cluster island

Header now renders as plain HTML; only the mobile drawer + auth badge
ship JS. Entrance animation moves to pure CSS keyframe.
```

---

## Task 5: Create `(marketing)` route group — layout, providers, root page

**Files:**
- Create: `frontend/src/app/(marketing)/layout.tsx`
- Create: `frontend/src/app/(marketing)/providers.tsx`
- Create: `frontend/src/app/(marketing)/page.tsx`
- Delete: `frontend/src/app/page.tsx`

- [ ] **Step 1: Create `(marketing)/providers.tsx`**

```tsx
"use client";

import { LoadingProvider } from "@/context/loading";
import { AuthProvider } from "@/context/auth";

export function MarketingProviders({ children }: { children: React.ReactNode }) {
  return (
    <LoadingProvider>
      <AuthProvider>{children}</AuthProvider>
    </LoadingProvider>
  );
}
```

- [ ] **Step 2: Create `(marketing)/layout.tsx`**

```tsx
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { MarketingProviders } from "./providers";

/**
 * Server Component layout for marketing routes (root, log-in, about,
 * contact). Renders the static Header shell + Footer as HTML. Client
 * state (auth + loading) is mounted by <MarketingProviders>, which
 * itself is a thin "use client" boundary.
 */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <MarketingProviders>
      <Header />
      <main className="min-h-screen pt-16">{children}</main>
      <Footer />
    </MarketingProviders>
  );
}
```

- [ ] **Step 3: Move root page into the group**

Move `frontend/src/app/page.tsx` → `frontend/src/app/(marketing)/page.tsx`. Strip nothing — the existing file already has no `"use client"` directive (verify before moving). It is already a Server Component.

Run: `git mv "frontend/src/app/page.tsx" "frontend/src/app/(marketing)/page.tsx"`

Verify the moved file's content begins with `import Image from "next/image";` and **does not** contain `"use client"`. No code changes needed.

- [ ] **Step 4: Build to verify routing still resolves**

Run: `cd frontend && npm run build`
Expected: build succeeds. `/` route appears in the build output as a static page.

If build fails with "missing layout" or "duplicate route", check that `frontend/src/app/(marketing)/layout.tsx` is in place and that the old `app/page.tsx` is gone.

- [ ] **Step 5: Manual smoke**

Run: `cd frontend && npm run dev`
Visit `http://localhost:3000/`. Confirm:
- Header bar shows (logo + nav links + "Log In" button).
- Page content renders.
- No hydration error in console.

- [ ] **Step 6: Request commit approval**

Proposed message:
```
refactor(fe): move root page into (marketing) route group with server layout
```

---

## Task 6: Move log-in page into `(marketing)`; extract `LoginForm` client island

**Files:**
- Create: `frontend/src/app/(marketing)/log-in/page.tsx`
- Create: `frontend/src/app/(marketing)/log-in/LoginForm.tsx`
- Create: `frontend/src/app/(marketing)/log-in/__tests__/LoginForm.test.tsx`
- Delete: `frontend/src/app/log-in/page.tsx`
- Delete: `frontend/src/app/log-in/` (empty)

- [ ] **Step 1: Write failing test for LoginForm**

Create `frontend/src/app/(marketing)/log-in/__tests__/LoginForm.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginForm } from "../LoginForm";
import { AuthProvider } from "@/context/auth";
import { LoadingProvider } from "@/context/loading";

function renderWithProviders(ui: React.ReactNode) {
  return render(
    <LoadingProvider>
      <AuthProvider>{ui}</AuthProvider>
    </LoadingProvider>
  );
}

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({ ok: false });
  Object.defineProperty(document, "cookie", { writable: true, configurable: true, value: "" });
  Object.defineProperty(window, "open", { writable: true, configurable: true, value: vi.fn() });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("LoginForm", () => {
  it("submit button is disabled until both fields are non-empty", async () => {
    renderWithProviders(<LoginForm />);
    const user = userEvent.setup();

    const submit = screen.getByRole("button", { name: /sign in to dashboard/i });
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText(/email/i), "a@b.c");
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText(/^password$/i), "secret");
    expect(submit).not.toBeDisabled();
  });

  it("toggles password visibility", async () => {
    renderWithProviders(<LoginForm />);
    const user = userEvent.setup();

    const pw = screen.getByLabelText(/^password$/i) as HTMLInputElement;
    expect(pw.type).toBe("password");

    await user.click(screen.getByRole("button", { name: /show password/i }));
    expect(pw.type).toBe("text");
  });

  it("renders error on failed login", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Invalid email or password" }),
    });

    renderWithProviders(<LoginForm />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "a@b.c");
    await user.type(screen.getByLabelText(/^password$/i), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in to dashboard/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `cd frontend && npx vitest run "src/app/(marketing)/log-in/__tests__/LoginForm.test.tsx"`
Expected: FAIL — `LoginForm` not defined.

- [ ] **Step 3: Implement `LoginForm.tsx`**

Create `frontend/src/app/(marketing)/log-in/LoginForm.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Eye, EyeOff, CheckCircle, Check } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { login } from "@/lib/auth";
import { useLoading } from "@/context/loading";
import { useAuth } from "@/context/auth";

/**
 * Client island for the log-in page. Static card chrome (heading,
 * subtitle, labels, layout) is rendered by the Server Component
 * parent and shipped as HTML; only the interactive form + success
 * view live here.
 *
 * Entrance animation: pure CSS `.animate-fade-down` (defined in
 * globals.css). The form HTML paints immediately; the fade plays on
 * top, so perceived appearance is instant. Removing framer-motion
 * from this island also keeps ~40KB out of the /log-in chunk.
 */
const DASHBOARD_WINDOW_NAME = "cms-dashboard";

export function LoginForm() {
  const { show, hide } = useLoading();
  const { isLoggedIn, setLoggedIn } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const isFormValid = email.trim() !== "" && password.trim() !== "";

  // Warm the /dashboard chunk so the post-login window.open is instant.
  useEffect(() => {
    router.prefetch("/dashboard");
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isFormValid) return;

    show();
    setIsLoading(true);
    setError("");

    try {
      await login({ email, password, remember_me: rememberMe });
      setLoggedIn(true);
      window.name = "cms-login";
      window.open("/dashboard", DASHBOARD_WINDOW_NAME);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      hide();
      setIsLoading(false);
    }
  };

  if (isLoggedIn) {
    return (
      <div className="animate-fade-down w-full max-w-md space-y-8 rounded-2xl border border-white/[0.08] bg-zinc-950 p-8 shadow-[0_8px_30px_rgb(0,0,0,0.12)]">
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-950/60">
            <CheckCircle className="h-7 w-7 text-emerald-400" />
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-white">
            Successfully Logged In
          </h2>
          <p className="text-sm text-zinc-400">
            You&apos;re all set. Head over to your dashboard to manage your projects.
          </p>
        </div>

        <div>
          <Button
            type="button"
            variant="primary"
            size="lg"
            className="w-full text-base"
            onClick={() => window.open("/dashboard", DASHBOARD_WINDOW_NAME)}
          >
            Go to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-down w-full max-w-md space-y-8 rounded-2xl border border-white/[0.08] bg-zinc-950 p-8 shadow-[0_8px_30px_rgb(0,0,0,0.12)]">
      <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
        {error && (
          <div className="rounded-md bg-red-950/50 p-4 text-sm font-medium text-red-400">
            {error}
          </div>
        )}

        <div className="space-y-4 rounded-md shadow-sm">
          <div>
            <label htmlFor="email" className="block text-sm font-medium leading-6 text-zinc-300">
              Email address or Username
            </label>
            <div className="mt-2 text-white">
              <input
                id="email"
                name="email"
                type="text"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="block w-full rounded-md border-0 bg-transparent py-2.5 px-3 text-white shadow-sm ring-1 ring-inset ring-white/[0.12] placeholder:text-zinc-500 focus:ring-1 focus:ring-inset focus:ring-white/30 sm:text-sm sm:leading-6 transition-colors"
                placeholder="admin@example.com"
              />
            </div>
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium leading-6 text-zinc-300">
              Password
            </label>
            <div className="relative mt-2 text-white">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="block w-full rounded-md border-0 bg-transparent py-2.5 pl-3 pr-10 text-white shadow-sm ring-1 ring-inset ring-white/[0.12] placeholder:text-zinc-500 focus:ring-1 focus:ring-inset focus:ring-white/30 sm:text-sm sm:leading-6 transition-colors"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-zinc-400 hover:text-zinc-300 transition-colors"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <EyeOff className="h-5 w-5" aria-hidden="true" />
                ) : (
                  <Eye className="h-5 w-5" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>
        </div>

        <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <input
              id="remember-me"
              name="remember-me"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="sr-only"
            />
            <button
              type="button"
              role="checkbox"
              aria-checked={rememberMe}
              aria-labelledby="remember-me-label"
              onClick={() => setRememberMe((v) => !v)}
              className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors focus:outline-none focus:ring-1 focus:ring-white/30 ${
                rememberMe
                  ? "border-white bg-white"
                  : "border-white/30 bg-zinc-950 hover:border-white/50"
              }`}
            >
              {rememberMe && <Check className="h-3 w-3 text-black" strokeWidth={3} />}
            </button>
            <label
              id="remember-me-label"
              onClick={() => setRememberMe((v) => !v)}
              className="cursor-pointer text-sm text-zinc-400 select-none"
            >
              Remember me
            </label>
          </div>

          <div className="text-sm">
            <a href="#" className="font-medium text-white transition-colors hover:text-zinc-300">
              Forgot your password?
            </a>
          </div>
        </div>

        <div>
          <Button
            type="submit"
            variant="primary"
            size="lg"
            className="w-full text-base"
            disabled={!isFormValid || isLoading}
            isLoading={isLoading}
          >
            Sign in to dashboard
          </Button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 4: Create the Server Component log-in page**

Create `frontend/src/app/(marketing)/log-in/page.tsx`:

```tsx
import { LoginForm } from "./LoginForm";

/**
 * Server Component. Static card heading/subtitle ship as HTML before
 * any JS arrives. Interactive form is the <LoginForm /> client island.
 */
export default function LogInPage() {
  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-black px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md">
        <div className="mb-8">
          <h2 className="mt-2 text-center text-3xl font-semibold tracking-tight text-white">
            Access CMS
          </h2>
          <p className="mt-2 text-center text-sm text-zinc-400">
            Please sign in to your administrative account.
          </p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
```

Note: heading + subtitle moved OUT of the animated card so they ship as static HTML and appear instantly. The card (form) keeps its slide-in.

- [ ] **Step 5: Delete the old log-in page**

Run:
```
rm "frontend/src/app/log-in/page.tsx"
rmdir "frontend/src/app/log-in"
```

(If `rmdir` complains, the directory has other files — list them and decide.)

- [ ] **Step 6: Run LoginForm tests, verify pass**

Run: `cd frontend && npx vitest run "src/app/(marketing)/log-in/__tests__/LoginForm.test.tsx"`
Expected: 3/3 pass.

- [ ] **Step 7: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds. `/log-in` route appears in build output.

Check the build output: note the **First Load JS** size for `/log-in`. Record it for the verification task.

- [ ] **Step 8: Manual smoke**

Run: `cd frontend && npm run dev`
Visit `http://localhost:3000/log-in`:
- Heading "Access CMS" appears immediately (server-rendered).
- Card slides in within ~200ms.
- Submit credentials — flow lands on dashboard.

- [ ] **Step 9: Typecheck + lint + full test suite**

Run: `cd frontend && npm run typecheck && npm run lint && npm test`
Expected: clean across the board.

- [ ] **Step 10: Request commit approval**

Proposed message:
```
refactor(fe-login): server-render card chrome, isolate form as client island

Heading + subtitle ship as static HTML. LoginForm island carries the
form state + framer slide-in (delay reduced 500ms → 0). Dashboard CTA
uses next/link prefetch to prime the chunk on hover.
```

---

## Task 7: Slim root `app/layout.tsx`; delete `SiteShell` and `Providers`

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Delete: `frontend/src/components/SiteShell.tsx`
- Delete: `frontend/src/components/Providers.tsx`

- [ ] **Step 1: Confirm no stragglers import `SiteShell` or `Providers`**

Run: `grep -rn "SiteShell\|from \"@/components/Providers\"" frontend/src`
Expected: only `frontend/src/app/layout.tsx` references them. If anything else turns up, address before deleting.

- [ ] **Step 2: Rewrite `frontend/src/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Roman Technologies",
  description: "Premium software solutions for modern businesses.",
};

/**
 * Theme boot script — placed RAW in <head> so the browser executes it
 * synchronously before parsing <body>. Reads `dashboard-theme` from
 * localStorage; defaults to "dark". Sets `class="dark"` on <html> and
 * `data-theme="dark|light"` for `context/theme.tsx` to pick up on mount.
 */
const themeBootScript = `(function(){try{var t=localStorage.getItem('dashboard-theme');if(t!=='light'&&t!=='dark')t='dark';document.documentElement.dataset.theme=t;document.documentElement.classList.toggle('dark',t==='dark');}catch(e){document.documentElement.dataset.theme='dark';document.documentElement.classList.add('dark');}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script suppressHydrationWarning dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>{children}</body>
    </html>
  );
}
```

- [ ] **Step 3: Delete `SiteShell` + `Providers`**

Run:
```
rm "frontend/src/components/SiteShell.tsx"
rm "frontend/src/components/Providers.tsx"
```

- [ ] **Step 4: Build + manual smoke**

Run: `cd frontend && npm run build`
Expected: build succeeds. Both `/` and `/log-in` appear in the route table.

Run: `cd frontend && npm run dev` and visit:
- `/` — header + content render. No console errors.
- `/log-in` — same.
- `/dashboard` — header is **absent** (dashboard has its own layout). Skeleton flashes, then content.

- [ ] **Step 5: Typecheck + lint + test**

Run: `cd frontend && npm run typecheck && npm run lint && npm test`
Expected: clean.

- [ ] **Step 6: Request commit approval**

Proposed message:
```
refactor(fe): drop SiteShell + global Providers; root layout server-only

Marketing routes own their providers via the (marketing) layout.
Dashboard owns its own. Root <body> renders {children} directly.
```

---

## Task 8: Dynamic-import `LoadingScreen`

**Files:**
- Modify: `frontend/src/context/loading.tsx`

- [ ] **Step 1: Rewrite `frontend/src/context/loading.tsx`**

```tsx
"use client";

import { createContext, useContext, useState, useCallback } from "react";
import dynamic from "next/dynamic";

/**
 * LoadingScreen is dynamic-imported with `ssr: false`. Two reasons:
 *   1. It's never visible on cold load — the overlay only shows when
 *      a transition explicitly calls `show()`. Loading its module +
 *      framer-motion + arc CSS upfront wastes bandwidth.
 *   2. The overlay's framer animation has no business running during
 *      SSR HTML generation.
 */
const LoadingScreen = dynamic(
  () => import("@/components/ui/LoadingScreen").then((m) => ({ default: m.LoadingScreen })),
  { ssr: false }
);

interface LoadingContextValue {
  show: () => void;
  hide: () => void;
}

const LoadingContext = createContext<LoadingContextValue>({
  show: () => {},
  hide: () => {},
});

export function LoadingProvider({ children }: { children: React.ReactNode }) {
  const [isVisible, setIsVisible] = useState(false);

  const show = useCallback(() => setIsVisible(true), []);
  const hide = useCallback(() => setIsVisible(false), []);

  return (
    <LoadingContext.Provider value={{ show, hide }}>
      {/* Only render the overlay once we actually want it visible — keeps
          the dynamic chunk out of the network waterfall on cold load. */}
      {isVisible && <LoadingScreen isVisible={isVisible} />}
      {children}
    </LoadingContext.Provider>
  );
}

export function useLoading() {
  return useContext(LoadingContext);
}
```

- [ ] **Step 2: Build + check bundle**

Run: `cd frontend && npm run build`
Look for a separate chunk named with `LoadingScreen` in the route summary or in `.next/server/chunks`. Confirm `/log-in` first-load JS dropped vs Task 6's recorded number.

- [ ] **Step 3: Manual smoke**

Run: `cd frontend && npm run dev`
- Visit `/log-in`. Submit credentials with bad password. Confirm the loading overlay appears during the request and disappears after the error renders. (This proves the dynamic import resolves and `<LoadingScreen>` mounts correctly when triggered.)

- [ ] **Step 4: Tests + typecheck + lint**

Run: `cd frontend && npm run typecheck && npm run lint && npm test`
Expected: clean.

- [ ] **Step 5: Request commit approval**

Proposed message:
```
perf(fe-loading): dynamic-import LoadingScreen overlay

Overlay JS only fetched once `show()` is called. Removes framer +
arc-spinner CSS from initial /log-in chunk.
```

---

## Task 9: Verification — bundle size, Lighthouse, E2E

**Files:** none

- [ ] **Step 1: Capture bundle size baseline diff**

Run: `cd frontend && npm run build > /tmp/build-after.txt 2>&1`

Open `/tmp/build-after.txt` and find the route table. Record the **First Load JS** for `/` and `/log-in`.

Acceptance: `/log-in` First Load JS < 100 KB.

If it's not, identify the largest remaining chunk via `npx next-bundle-analyzer` or by inspecting `.next/static/chunks/`, and report to Stefan.

- [ ] **Step 2: Run full test suite + typecheck + lint**

Run: `cd frontend && npm run typecheck && npm run lint && npm test`
Expected: clean.

- [ ] **Step 3: Push to remote, wait for CI/E2E**

Run: `git push -u origin feat/fast-login-flow`
Open the resulting CI run on GitHub. Wait for: lint, unit tests, E2E, Lighthouse-CI (if configured), CodeQL.

Expected: all green. If E2E fails on the login flow, the form's DOM structure or selectors changed — fix and re-test locally before re-pushing.

- [ ] **Step 4: Open Vercel preview, run Lighthouse mobile**

Find the Vercel preview URL in the PR / GitHub commit checks.

In Chrome DevTools → Lighthouse → Mobile → Performance: run on `/` and `/log-in` against the preview URL.

Acceptance:
- LCP < 1s on `/log-in`.
- TBT < 100ms.
- Performance score >= 90.

Record results in a comment on the PR.

- [ ] **Step 5: Manual flow smoke on preview**

On preview URL:
1. Cold-load `/` — header + hero appear without visible delay.
2. Click Log In — `/log-in` loads, heading appears instantly, form card slides in within ~200ms.
3. Submit valid credentials — overlay shows briefly, dashboard tab opens with skeleton, then content.
4. Submit invalid credentials — overlay shows, error message appears, no broken state.

- [ ] **Step 6: Open PR `feat/fast-login-flow` → `dev`**

Run (only after Stefan confirms):
```
gh pr create --base dev --title "perf(fe): fast login flow — server islands + dynamic loading" --body "$(cat <<'EOF'
## Summary
- Marketing routes moved to `(marketing)` route group with a Server Component layout.
- Header split into server shell + small client island (mobile drawer + auth badge).
- Log-in page server-renders card chrome; `<LoginForm />` is a client island with 0-delay slide-in.
- `LoadingScreen` is dynamic-imported.
- `AuthProvider` skips `/auth/me` when no session cookie is present.
- Dashboard gains `loading.tsx` skeleton + chunk prefetch from login success view.

## Test plan
- [ ] CI green (lint, unit, E2E, CodeQL).
- [ ] Lighthouse mobile on `/log-in`: LCP < 1s, TBT < 100ms, score >= 90.
- [ ] Manual: `/` → `/log-in` → submit → dashboard. Each hop paints visibly fast.

Spec: docs/superpowers/specs/2026-05-13-fast-login-flow-design.md
Plan: docs/superpowers/plans/2026-05-13-fast-login-flow.md
EOF
)"
```

- [ ] **Step 7: Post-merge prod verification**

After `dev` → `master` auto-merge promotes to prod:
- Re-run Lighthouse on `https://roman-technologies.dev/log-in`.
- WebPageTest from US-East, throttled 4G — capture filmstrip. Attach to PR comment.
- If real-world numbers miss the B-target (<500ms perceived), open a follow-up task; do not auto-revert.

---

## Self-Review Notes

- **Spec coverage:**
  - §3.1 route-group restructure → Tasks 5, 6, 7.
  - §3.2 Server Component conversions → Tasks 4, 5, 6, 7.
  - §3.3 Header split → Task 4.
  - §3.4 LoginForm island → Task 6.
  - §3.5 auth context scoping + cookie sniff → Tasks 3, 5 (provider scope via `(marketing)/providers.tsx`).
  - §3.6 bundle/runtime cuts → Tasks 1 (CSS), 8 (dynamic LoadingScreen), 6 (login card delay → 0).
  - §3.7 dashboard skeleton + prefetch → Tasks 2, 6.
  - §5 verification → Task 9.
- **Risks** (spec §6) — all surfaced inline in their relevant tasks (cookie name in Task 3, `<Link target>` in Task 6, `useAuth` consumers in Task 4).
- **Commit policy:** every task ends with "request commit approval" rather than auto-committing, per Stefan's standing rule.
