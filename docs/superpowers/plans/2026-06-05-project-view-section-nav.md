# Project View — Section Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single long-scroll project view with a sidebar-rail shell that switches between four sections (Dashboard · CMS · Auto-Fix · Settings) using the existing fade-in/out animation, and slim `page.tsx` from a 419-line god component into focused section components.

**Architecture:** A new `SectionRail` (vertical sidebar, horizontal on mobile) drives a URL-persisted `?view=` state via a `useProjectView` hook. A `SectionPanel` wraps the active section in the project's existing `AnimatePresence mode="wait"` fade+lift. Each section's content lives in its own component (`DashboardSection`, `CmsSection`, `AutoFixSection`, `ProjectSettingsSection`); existing `ServiceGrid`/`PageTabs`/`IssueForm`/`IssueList`/`ServiceCard`/`PreviewPublishBar` are relocated/wrapped, never rewritten. `page.tsx` becomes a thin orchestrator.

**Tech Stack:** Next.js 16 (App Router, client components), React 19, TypeScript, Tailwind v4, framer-motion (project convention — NOT `motion/react`), lucide-react icons. Tests: Vitest + React Testing Library + jsdom (`npx vitest run` from `frontend/`).

**Spec:** `docs/superpowers/specs/2026-06-05-project-view-section-nav-design.md`

**Commit policy:** This repo follows a **no-auto-commit** rule — commits happen only when Stefan explicitly says so. Each task ends with a **Checkpoint** step (verify + pause for review). A suggested commit command is given for when Stefan approves; do NOT run it automatically.

**Conventions to follow (verified in the codebase):**
- Tests mock `next/navigation` per file. For varying search params use `vi.hoisted`:
  ```ts
  const { mockParams, replace } = vi.hoisted(() => ({
    mockParams: { current: new URLSearchParams() },
    replace: vi.fn(),
  }));
  vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace }),
    usePathname: () => "/dashboard/demo",
    useSearchParams: () => mockParams.current,
  }));
  ```
- Shared Tailwind class constants live in `@/lib/styles` (`dashboardPrimaryBtnCn`, `dashboardSectionCardCn`, `dashboardInputCn`, `dashboardFieldLabelCn`, `dashboardErrorBannerCn`).
- `no-scrollbar` utility class already exists in `globals.css` (used by `PageTabs`).
- Run tests from the `frontend/` directory.

---

## File Structure

**New files (all under `frontend/src/components/dashboard/`):**
- `sectionConfig.ts` — `SectionKey` type, `SectionDef` interface, `PROJECT_SECTIONS`, `DEFAULT_VIEW`, `visibleSections()`, `isAccessibleView()`.
- `hooks/useProjectView.ts` — URL `?view=` state + admin gating.
- `SectionRail.tsx` — sidebar/horizontal nav with animated active pill + keyboard nav.
- `SectionPanel.tsx` — animated wrapper around the active section.
- `DashboardSection.tsx` — "coming soon" analytics empty state.
- `CmsSection.tsx` — owns services fetch + skeleton + error + `ServiceGrid` + removal (extracted from `page.tsx`).
- `AutoFixSection.tsx` — header + `IssueForm` + `IssueList`, owns issue-refresh state.
- `ProjectSettingsSection.tsx` — admin settings form (extracted from `page.tsx`).
- `__tests__/` test files for `sectionConfig`, `useProjectView`, `SectionRail`, `SectionPanel`, `DashboardSection`, `ProjectSettingsSection`.

**Modified:**
- `app/dashboard/[projectSlug]/page.tsx` — slimmed to orchestrator.

---

## Task 1: Section configuration + helpers

**Files:**
- Create: `frontend/src/components/dashboard/sectionConfig.ts`
- Test: `frontend/src/components/dashboard/__tests__/sectionConfig.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/components/dashboard/__tests__/sectionConfig.test.ts
import { describe, it, expect } from "vitest";
import {
  PROJECT_SECTIONS,
  DEFAULT_VIEW,
  visibleSections,
  isAccessibleView,
} from "../sectionConfig";

describe("sectionConfig", () => {
  it("defines the four sections in order", () => {
    expect(PROJECT_SECTIONS.map((s) => s.key)).toEqual([
      "dashboard",
      "cms",
      "autofix",
      "settings",
    ]);
  });

  it("default view is dashboard", () => {
    expect(DEFAULT_VIEW).toBe("dashboard");
  });

  it("hides admin-only sections from non-admins", () => {
    expect(visibleSections(false).map((s) => s.key)).toEqual([
      "dashboard",
      "cms",
      "autofix",
    ]);
    expect(visibleSections(true).map((s) => s.key)).toContain("settings");
  });

  it("validates views against admin visibility", () => {
    expect(isAccessibleView("cms", false)).toBe(true);
    expect(isAccessibleView("settings", false)).toBe(false);
    expect(isAccessibleView("settings", true)).toBe(true);
    expect(isAccessibleView("bogus", true)).toBe(false);
    expect(isAccessibleView(null, true)).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/dashboard/__tests__/sectionConfig.test.ts`
Expected: FAIL — cannot find module `../sectionConfig`.

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/src/components/dashboard/sectionConfig.ts
import { LayoutDashboard, FileText, Sparkles, Settings, type LucideIcon } from "lucide-react";

export type SectionKey = "dashboard" | "cms" | "autofix" | "settings";

export interface SectionDef {
  key: SectionKey;
  label: string;
  icon: LucideIcon;
  /** Renders in the rail only for admins. */
  adminOnly?: boolean;
}

export const PROJECT_SECTIONS: SectionDef[] = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "cms", label: "CMS", icon: FileText },
  { key: "autofix", label: "Auto-Fix", icon: Sparkles },
  { key: "settings", label: "Settings", icon: Settings, adminOnly: true },
];

export const DEFAULT_VIEW: SectionKey = "dashboard";

export function visibleSections(isAdmin: boolean): SectionDef[] {
  return PROJECT_SECTIONS.filter((s) => !s.adminOnly || isAdmin);
}

export function isAccessibleView(view: string | null, isAdmin: boolean): view is SectionKey {
  return view !== null && visibleSections(isAdmin).some((s) => s.key === view);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/dashboard/__tests__/sectionConfig.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Checkpoint** — Run `npm run typecheck`; green. Per repo policy, do NOT commit automatically — pause for review. Suggested commit when Stefan approves:

```bash
git add frontend/src/components/dashboard/sectionConfig.ts frontend/src/components/dashboard/__tests__/sectionConfig.test.ts
git commit -m "feat(dashboard): add project section config + visibility helpers"
```

---

## Task 2: `useProjectView` hook (URL `?view=` state)

**Files:**
- Create: `frontend/src/components/dashboard/hooks/useProjectView.ts`
- Test: `frontend/src/components/dashboard/__tests__/useProjectView.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/dashboard/__tests__/useProjectView.test.tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useProjectView } from "../hooks/useProjectView";

const { mockParams, replace } = vi.hoisted(() => ({
  mockParams: { current: new URLSearchParams() },
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/dashboard/demo",
  useSearchParams: () => mockParams.current,
}));

beforeEach(() => {
  mockParams.current = new URLSearchParams();
  replace.mockClear();
});

describe("useProjectView", () => {
  it("defaults to dashboard when no view param", () => {
    const { result } = renderHook(() => useProjectView(true));
    expect(result.current.activeView).toBe("dashboard");
  });

  it("honors a valid view param", () => {
    mockParams.current = new URLSearchParams("view=cms");
    const { result } = renderHook(() => useProjectView(true));
    expect(result.current.activeView).toBe("cms");
  });

  it("falls back to dashboard when a non-admin requests settings", () => {
    mockParams.current = new URLSearchParams("view=settings");
    const { result } = renderHook(() => useProjectView(false));
    expect(result.current.activeView).toBe("dashboard");
  });

  it("allows settings for admins", () => {
    mockParams.current = new URLSearchParams("view=settings");
    const { result } = renderHook(() => useProjectView(true));
    expect(result.current.activeView).toBe("settings");
  });

  it("setView preserves the existing tab param", () => {
    mockParams.current = new URLSearchParams("tab=Contact");
    const { result } = renderHook(() => useProjectView(true));
    act(() => result.current.setView("cms"));
    expect(replace).toHaveBeenCalledTimes(1);
    const url = replace.mock.calls[0][0] as string;
    expect(url).toContain("view=cms");
    expect(url).toContain("tab=Contact");
    expect(replace.mock.calls[0][1]).toEqual({ scroll: false });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/dashboard/__tests__/useProjectView.test.tsx`
Expected: FAIL — cannot find module `../hooks/useProjectView`.

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/src/components/dashboard/hooks/useProjectView.ts
"use client";

import { useCallback } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { DEFAULT_VIEW, isAccessibleView, type SectionKey } from "@/components/dashboard/sectionConfig";

/**
 * Active project section, persisted in the URL as `?view=`. Mirrors the
 * existing `?tab=` pattern in ServiceGrid so deep links like
 * `?view=cms&tab=Contact` round-trip. Non-admins requesting an admin-only
 * view (e.g. settings) fall back to the default.
 */
export function useProjectView(isAdmin: boolean): {
  activeView: SectionKey;
  setView: (view: SectionKey) => void;
} {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const requested = searchParams.get("view");
  const activeView: SectionKey = isAccessibleView(requested, isAdmin) ? requested : DEFAULT_VIEW;

  const setView = useCallback(
    (view: SectionKey) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("view", view);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [router, pathname, searchParams]
  );

  return { activeView, setView };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/dashboard/__tests__/useProjectView.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 5: Checkpoint** — `npm run typecheck` green. Suggested commit:

```bash
git add frontend/src/components/dashboard/hooks/useProjectView.ts frontend/src/components/dashboard/__tests__/useProjectView.test.tsx
git commit -m "feat(dashboard): add useProjectView URL state hook"
```

---

## Task 3: `SectionRail` (sidebar nav + animated pill + keyboard nav)

**Files:**
- Create: `frontend/src/components/dashboard/SectionRail.tsx`
- Test: `frontend/src/components/dashboard/__tests__/SectionRail.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/dashboard/__tests__/SectionRail.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SectionRail } from "../SectionRail";
import { visibleSections } from "../sectionConfig";

describe("SectionRail", () => {
  it("renders every section it is given as a tab", () => {
    render(
      <SectionRail sections={visibleSections(true)} activeView="dashboard" onSelect={vi.fn()} />
    );
    expect(screen.getByRole("tab", { name: /Dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /CMS/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Auto-Fix/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Settings/i })).toBeInTheDocument();
  });

  it("does not render Settings when given the non-admin section list", () => {
    render(
      <SectionRail sections={visibleSections(false)} activeView="dashboard" onSelect={vi.fn()} />
    );
    expect(screen.queryByRole("tab", { name: /Settings/i })).not.toBeInTheDocument();
  });

  it("marks the active tab with aria-selected", () => {
    render(
      <SectionRail sections={visibleSections(true)} activeView="cms" onSelect={vi.fn()} />
    );
    expect(screen.getByRole("tab", { name: /CMS/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Dashboard/i })).toHaveAttribute(
      "aria-selected",
      "false"
    );
  });

  it("calls onSelect with the section key on click", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <SectionRail sections={visibleSections(true)} activeView="dashboard" onSelect={onSelect} />
    );
    await user.click(screen.getByRole("tab", { name: /Auto-Fix/i }));
    expect(onSelect).toHaveBeenCalledWith("autofix");
  });

  it("moves selection with arrow keys", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <SectionRail sections={visibleSections(true)} activeView="dashboard" onSelect={onSelect} />
    );
    const active = screen.getByRole("tab", { name: /Dashboard/i });
    active.focus();
    await user.keyboard("{ArrowDown}");
    expect(onSelect).toHaveBeenCalledWith("cms");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/dashboard/__tests__/SectionRail.test.tsx`
Expected: FAIL — cannot find module `../SectionRail`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/dashboard/SectionRail.tsx
"use client";

import { useRef } from "react";
import { motion } from "framer-motion";
import type { SectionDef, SectionKey } from "./sectionConfig";

interface SectionRailProps {
  sections: SectionDef[];
  activeView: SectionKey;
  onSelect: (view: SectionKey) => void;
}

/**
 * Project-level section navigation. Vertical rail on md+, a horizontal
 * scrollable strip on mobile. The active item shows a filled pill driven by
 * a shared `layoutId` so it slides between items with the same spring as the
 * CMS underline (PageTabs). tablist semantics + roving tabindex + arrow keys.
 */
export function SectionRail({ sections, activeView, onSelect }: SectionRailProps) {
  const btnRefs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(e: React.KeyboardEvent, index: number) {
    let next: number;
    if (e.key === "ArrowDown" || e.key === "ArrowRight") next = (index + 1) % sections.length;
    else if (e.key === "ArrowUp" || e.key === "ArrowLeft")
      next = (index - 1 + sections.length) % sections.length;
    else return;
    e.preventDefault();
    btnRefs.current[next]?.focus();
    onSelect(sections[next].key);
  }

  return (
    <nav
      role="tablist"
      aria-label="Project sections"
      aria-orientation="vertical"
      className="no-scrollbar flex flex-row gap-1 overflow-x-auto overflow-y-hidden md:flex-col md:overflow-visible"
    >
      {sections.map((section, i) => {
        const isActive = section.key === activeView;
        const Icon = section.icon;
        return (
          <button
            key={section.key}
            ref={(el) => {
              btnRefs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`section-tab-${section.key}`}
            aria-controls={`section-panel-${section.key}`}
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onSelect(section.key)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className="relative flex shrink-0 cursor-pointer items-center rounded-lg px-3 py-2 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-zinc-400/40"
          >
            {isActive && (
              <motion.span
                layoutId="section-rail-active"
                className="absolute inset-0 rounded-lg bg-zinc-100 dark:bg-zinc-800"
                transition={{ type: "spring", stiffness: 480, damping: 36, mass: 0.6 }}
              />
            )}
            <span
              className={
                "relative z-10 flex items-center gap-2.5 " +
                (isActive
                  ? "text-zinc-900 dark:text-zinc-50"
                  : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200")
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {section.label}
              {section.adminOnly && (
                <span className="ml-0.5 rounded-full bg-zinc-200/70 px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-zinc-500 dark:bg-zinc-700/70 dark:text-zinc-400">
                  admin
                </span>
              )}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/dashboard/__tests__/SectionRail.test.tsx`
Expected: PASS (5 tests).

> Note: the accessible name of each tab comes from its text (label). The "admin" badge text is part of the Settings tab name, so `getByRole("tab", { name: /Settings/i })` still matches.

- [ ] **Step 5: Checkpoint** — `npm run typecheck` green. Suggested commit:

```bash
git add frontend/src/components/dashboard/SectionRail.tsx frontend/src/components/dashboard/__tests__/SectionRail.test.tsx
git commit -m "feat(dashboard): add SectionRail navigation with animated active pill"
```

---

## Task 4: `SectionPanel` (animated section wrapper)

**Files:**
- Create: `frontend/src/components/dashboard/SectionPanel.tsx`
- Test: `frontend/src/components/dashboard/__tests__/SectionPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/dashboard/__tests__/SectionPanel.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SectionPanel } from "../SectionPanel";

describe("SectionPanel", () => {
  it("renders its children inside a tabpanel labelled by the active tab", () => {
    render(
      <SectionPanel activeView="cms">
        <p>CMS body</p>
      </SectionPanel>
    );
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveAttribute("aria-labelledby", "section-tab-cms");
    expect(screen.getByText("CMS body")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/dashboard/__tests__/SectionPanel.test.tsx`
Expected: FAIL — cannot find module `../SectionPanel`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/dashboard/SectionPanel.tsx
"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";

interface SectionPanelProps {
  activeView: string;
  children: ReactNode;
}

/**
 * Wraps the active section body in the project's standard content-swap
 * animation (fade + 6px lift, mode="wait" so the old section fully exits
 * before the new one enters) — identical to ServiceGrid's tab swap.
 */
export function SectionPanel({ activeView, children }: SectionPanelProps) {
  return (
    <div
      role="tabpanel"
      id={`section-panel-${activeView}`}
      aria-labelledby={`section-tab-${activeView}`}
      className="min-w-0 flex-1"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={activeView}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.18, ease: [0.32, 0.72, 0, 1] }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/dashboard/__tests__/SectionPanel.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Checkpoint** — `npm run typecheck` green. Suggested commit:

```bash
git add frontend/src/components/dashboard/SectionPanel.tsx frontend/src/components/dashboard/__tests__/SectionPanel.test.tsx
git commit -m "feat(dashboard): add SectionPanel animated section wrapper"
```

---

## Task 5: `DashboardSection` (coming-soon analytics empty state)

**Files:**
- Create: `frontend/src/components/dashboard/DashboardSection.tsx`
- Test: `frontend/src/components/dashboard/__tests__/DashboardSection.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/dashboard/__tests__/DashboardSection.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DashboardSection } from "../DashboardSection";

describe("DashboardSection", () => {
  it("shows the coming-soon analytics empty state", () => {
    render(<DashboardSection onGoToCms={vi.fn()} />);
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
    expect(screen.getByText(/website analytics/i)).toBeInTheDocument();
  });

  it("calls onGoToCms when the shortcut button is clicked", async () => {
    const onGoToCms = vi.fn();
    const user = userEvent.setup();
    render(<DashboardSection onGoToCms={onGoToCms} />);
    await user.click(screen.getByRole("button", { name: /go to cms/i }));
    expect(onGoToCms).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/dashboard/__tests__/DashboardSection.test.tsx`
Expected: FAIL — cannot find module `../DashboardSection`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/dashboard/DashboardSection.tsx
"use client";

import { BarChart3, ArrowRight } from "lucide-react";
import { dashboardSectionCardCn, dashboardPrimaryBtnCn } from "@/lib/styles";

interface DashboardSectionProps {
  onGoToCms: () => void;
}

/**
 * Default landing section. Vercel analytics aren't built yet, so this is a
 * welcoming "coming soon" empty state with a shortcut into the CMS — never a
 * dead end.
 */
export function DashboardSection({ onGoToCms }: DashboardSectionProps) {
  return (
    <div className={`${dashboardSectionCardCn} px-6 py-16`}>
      <div className="mx-auto flex max-w-md flex-col items-center text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
          <BarChart3 className="h-6 w-6" />
        </span>
        <span className="mt-4 inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-[11px] font-medium text-indigo-700 dark:border-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-300">
          Coming soon
        </span>
        <h2 className="mt-3 text-base font-semibold text-zinc-900 dark:text-zinc-50">
          Website analytics
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Visitor traffic, page views, and performance metrics from Vercel will appear here. For
          now, jump into your content to make changes.
        </p>
        <button type="button" onClick={onGoToCms} className={`${dashboardPrimaryBtnCn} mt-6`}>
          Go to CMS
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/dashboard/__tests__/DashboardSection.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Checkpoint** — `npm run typecheck` green. Suggested commit:

```bash
git add frontend/src/components/dashboard/DashboardSection.tsx frontend/src/components/dashboard/__tests__/DashboardSection.test.tsx
git commit -m "feat(dashboard): add Dashboard coming-soon analytics section"
```

---

## Task 6: `CmsSection` (extract services fetch + grid + removal from page.tsx)

**Files:**
- Create: `frontend/src/components/dashboard/CmsSection.tsx`
- Source to copy from: `frontend/src/app/dashboard/[projectSlug]/page.tsx:29-40` (`fetchServices`), `:57-65` (services query), `:186-201` (removal), `:308-329` (skeleton + grid).

This task only **moves** existing logic into a component; behavior is unchanged. No new test is required for the moved logic (covered by existing `ServiceGrid` behavior), but add a light smoke test.

- [ ] **Step 1: Write the failing smoke test**

```tsx
// frontend/src/components/dashboard/__tests__/CmsSection.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard/demo",
  useSearchParams: () => new URLSearchParams(),
}));

import { CmsSection } from "../CmsSection";

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
});
afterEach(() => vi.restoreAllMocks());

describe("CmsSection", () => {
  it("renders the empty-state when there are no services", async () => {
    render(<CmsSection projectSlug="demo" isAdmin={false} />);
    await waitFor(() => {
      expect(screen.getByText(/no services configured yet/i)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/dashboard/__tests__/CmsSection.test.tsx`
Expected: FAIL — cannot find module `../CmsSection`.

- [ ] **Step 3: Write the implementation (move logic out of page.tsx)**

```tsx
// frontend/src/components/dashboard/CmsSection.tsx
"use client";

import { useState } from "react";
import { useQuery } from "@/hooks/useQuery";
import { ServiceGrid } from "@/components/dashboard/ServiceGrid";
import type { ServiceCardService } from "@/components/dashboard/ServiceCard";
import * as cache from "@/lib/cache";

function fetchServices(projectSlug: string): Promise<ServiceCardService[]> {
  return fetch(`/api/projects/${projectSlug}/services`, {
    credentials: "include",
    cache: "no-store",
  }).then(async (r) => {
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail ?? "Failed to load services.");
    }
    return r.json();
  });
}

interface CmsSectionProps {
  projectSlug: string;
  isAdmin: boolean;
}

/**
 * CMS editing area: page tabs + editable service cards. Owns its own services
 * fetch, loading skeleton, error display, and service removal. Extracted from
 * the project page so each section is self-contained.
 */
export function CmsSection({ projectSlug, isAdmin }: CmsSectionProps) {
  const servicesKey = `services:${projectSlug}`;
  const {
    data: services,
    loading,
    error,
    refresh,
  } = useQuery<ServiceCardService[]>(servicesKey, () => fetchServices(projectSlug), {
    ttl: 60 * 1000,
  });

  const [removingKey, setRemovingKey] = useState<string | null>(null);

  async function handleRemoveService(serviceKey: string) {
    if (!confirm(`Remove service "${serviceKey}"? This will also delete its content.`)) return;
    setRemovingKey(serviceKey);
    try {
      await fetch(`/api/projects/${projectSlug}/services/${serviceKey}`, {
        method: "DELETE",
        credentials: "include",
      });
      cache.invalidate(servicesKey);
      refresh();
    } finally {
      setRemovingKey(null);
    }
  }

  return (
    <div>
      {error && <p className="mb-6 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
            />
          ))}
        </div>
      )}

      {!loading && (
        <ServiceGrid
          services={services ?? []}
          projectSlug={projectSlug}
          isAdmin={isAdmin}
          removingKey={removingKey}
          onRemove={handleRemoveService}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/dashboard/__tests__/CmsSection.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Checkpoint** — `npm run typecheck` green. (page.tsx still references the now-duplicated logic; it gets cleaned up in Task 9. Do not delete from page.tsx yet.) Suggested commit:

```bash
git add frontend/src/components/dashboard/CmsSection.tsx frontend/src/components/dashboard/__tests__/CmsSection.test.tsx
git commit -m "feat(dashboard): extract CmsSection (services fetch + grid + removal)"
```

---

## Task 7: `AutoFixSection` (header + IssueForm + IssueList)

**Files:**
- Create: `frontend/src/components/dashboard/AutoFixSection.tsx`
- Source to copy from: `frontend/src/app/dashboard/[projectSlug]/page.tsx:183` (`issueRefreshKey` state), `:331-340` (form + list).

- [ ] **Step 1: Write the failing smoke test**

```tsx
// frontend/src/components/dashboard/__tests__/AutoFixSection.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AutoFixSection } from "../AutoFixSection";

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
});
afterEach(() => vi.restoreAllMocks());

describe("AutoFixSection", () => {
  it("renders the Auto-Fix header explaining the agent", () => {
    render(<AutoFixSection projectSlug="demo" isAdmin={false} currentUserId={null} />);
    expect(screen.getByRole("heading", { name: /auto-fix/i })).toBeInTheDocument();
    expect(screen.getByText(/fix it automatically/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/dashboard/__tests__/AutoFixSection.test.tsx`
Expected: FAIL — cannot find module `../AutoFixSection`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/dashboard/AutoFixSection.tsx
"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { IssueForm } from "@/components/dashboard/IssueForm";
import { IssueList } from "@/components/dashboard/IssueList";

interface AutoFixSectionProps {
  projectSlug: string;
  isAdmin: boolean;
  currentUserId: string | null;
}

/**
 * "Auto-Fix" — the agentic solver area. Describe a problem (IssueForm); an
 * agent resolves it; progress is tracked in IssueList. Owns the refresh key
 * that re-fetches the list after a new issue is filed.
 */
export function AutoFixSection({ projectSlug, isAdmin, currentUserId }: AutoFixSectionProps) {
  const [issueRefreshKey, setIssueRefreshKey] = useState(0);

  return (
    <div>
      <div className="mb-6 flex items-start gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-100 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300">
          <Sparkles className="h-4 w-4" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Auto-Fix</h2>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            Describe a problem with your website and our agent will fix it automatically. Track
            progress below.
          </p>
        </div>
      </div>

      <IssueForm projectSlug={projectSlug} onSubmitted={() => setIssueRefreshKey((k) => k + 1)} />
      <IssueList
        projectSlug={projectSlug}
        refreshTrigger={issueRefreshKey}
        isAdmin={isAdmin}
        currentUserId={currentUserId}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/dashboard/__tests__/AutoFixSection.test.tsx`
Expected: PASS (1 test).

> If `IssueList` requires `next/navigation` at render, add the same `vi.mock("next/navigation", …)` block used in other tests to the top of this file.

- [ ] **Step 5: Checkpoint** — `npm run typecheck` green. Suggested commit:

```bash
git add frontend/src/components/dashboard/AutoFixSection.tsx frontend/src/components/dashboard/__tests__/AutoFixSection.test.tsx
git commit -m "feat(dashboard): add AutoFixSection wrapping issue form + list"
```

---

## Task 8: `ProjectSettingsSection` (extract admin settings form)

**Files:**
- Create: `frontend/src/components/dashboard/ProjectSettingsSection.tsx`
- Source to copy from: `frontend/src/app/dashboard/[projectSlug]/page.tsx:94-181` (settings state + save handler), `:342-416` (form markup). The shared cache key stays `settings:<slug>` so the page's live-website card (which keeps its own read) and this form share cached data.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/dashboard/__tests__/ProjectSettingsSection.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ProjectSettingsSection } from "../ProjectSettingsSection";

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ website_url: "https://example.com", allowed_origins: ["https://example.com"] }),
  });
});
afterEach(() => vi.restoreAllMocks());

describe("ProjectSettingsSection", () => {
  it("loads and displays the website URL in the form", async () => {
    render(<ProjectSettingsSection projectSlug="demo" />);
    await waitFor(() => {
      expect(screen.getByDisplayValue("https://example.com")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /save settings/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/dashboard/__tests__/ProjectSettingsSection.test.tsx`
Expected: FAIL — cannot find module `../ProjectSettingsSection`.

- [ ] **Step 3: Write the implementation (move settings logic out of page.tsx)**

```tsx
// frontend/src/components/dashboard/ProjectSettingsSection.tsx
"use client";

import { useEffect, useState } from "react";
import { Settings } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import {
  dashboardInputCn,
  dashboardFieldLabelCn,
  dashboardSectionCardCn,
  dashboardErrorBannerCn,
} from "@/lib/styles";
import * as cache from "@/lib/cache";

type SettingsFromApi = { website_url: string | null; allowed_origins: string[] | null };

interface ProjectSettingsSectionProps {
  projectSlug: string;
}

/**
 * Admin-only project settings (website URL + allowed origins). Mounted only
 * for admins by the parent. Shares the `settings:<slug>` cache key with the
 * project page's live-website card; saving writes back to the cache and
 * invalidates the projects list (website_url is denormalised there).
 */
export function ProjectSettingsSection({ projectSlug }: ProjectSettingsSectionProps) {
  const settingsKey = `settings:${projectSlug}`;

  const { data: settingsRaw, loading: settingsQueryLoading } = useQuery<SettingsFromApi>(
    settingsKey,
    () =>
      fetch(`/api/projects/${projectSlug}/settings`, { credentials: "include" }).then((r) =>
        r.json()
      ),
    { ttl: 5 * 60 * 1000 }
  );

  const [settingsDraft, setSettingsDraft] = useState<{
    website_url: string;
    allowed_origins: string;
  } | null>(null);

  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (settingsRaw && settingsDraft === null) {
      setSettingsDraft({
        website_url: settingsRaw.website_url ?? "",
        allowed_origins: (settingsRaw.allowed_origins ?? []).join("\n"),
      });
    }
  }, [settingsRaw, settingsDraft]);

  const settingsLoading = settingsQueryLoading && settingsDraft === null;

  async function handleSaveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!settingsDraft) return;
    setSettingsSaving(true);
    setSettingsMsg(null);
    try {
      const r = await fetch(`/api/projects/${projectSlug}/settings`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          website_url: settingsDraft.website_url.trim() || null,
          allowed_origins: settingsDraft.allowed_origins
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail ?? "Failed to save settings.");
      }
      cache.set(settingsKey, {
        website_url: settingsDraft.website_url.trim() || null,
        allowed_origins: settingsDraft.allowed_origins
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      cache.invalidate("projects");
      setSettingsMsg({ type: "ok", text: "Settings saved." });
    } catch (err) {
      setSettingsMsg({ type: "err", text: err instanceof Error ? err.message : "Save failed." });
    } finally {
      setSettingsSaving(false);
    }
  }

  return (
    <div className="max-w-lg">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        <Settings className="h-4 w-4" />
        Project Settings
      </h2>

      {settingsLoading && (
        <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
          <ArcSpinner size={20} />
          Loading project settings…
        </div>
      )}

      {!settingsLoading && settingsDraft !== null && (
        <div className={`${dashboardSectionCardCn} p-6`}>
          <form onSubmit={handleSaveSettings} className="space-y-4">
            {settingsMsg && (
              <div
                className={
                  settingsMsg.type === "ok"
                    ? "rounded-lg border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-300"
                    : dashboardErrorBannerCn
                }
              >
                {settingsMsg.text}
              </div>
            )}

            <div>
              <label className={dashboardFieldLabelCn}>Website URL</label>
              <p className="mb-1.5 text-xs text-zinc-400 dark:text-zinc-500">
                The production URL of the client&apos;s website.
              </p>
              <input
                type="url"
                value={settingsDraft.website_url}
                onChange={(e) => setSettingsDraft((s) => s && { ...s, website_url: e.target.value })}
                placeholder="https://example.com"
                className={dashboardInputCn}
              />
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>Allowed origins</label>
              <p className="mb-1.5 text-xs text-zinc-400 dark:text-zinc-500">
                One origin per line. Form submissions from unlisted origins will be rejected. Leave
                empty to allow any origin.
              </p>
              <textarea
                rows={4}
                value={settingsDraft.allowed_origins}
                onChange={(e) =>
                  setSettingsDraft((s) => s && { ...s, allowed_origins: e.target.value })
                }
                placeholder={"https://example.com\nhttps://www.example.com"}
                className={`${dashboardInputCn} resize-y font-mono text-xs`}
              />
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={settingsSaving}
                className="cursor-pointer rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
              >
                {settingsSaving ? "Saving…" : "Save settings"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/dashboard/__tests__/ProjectSettingsSection.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Checkpoint** — `npm run typecheck` green. Suggested commit:

```bash
git add frontend/src/components/dashboard/ProjectSettingsSection.tsx frontend/src/components/dashboard/__tests__/ProjectSettingsSection.test.tsx
git commit -m "feat(dashboard): extract ProjectSettingsSection admin form"
```

---

## Task 9: Wire `page.tsx` into the section shell + remove extracted code

**Files:**
- Modify: `frontend/src/app/dashboard/[projectSlug]/page.tsx`

This task rewrites `page.tsx` to be a thin orchestrator. It **removes** the code now living in `CmsSection` (services fetch, skeleton, grid, removal), `AutoFixSection` (issue-refresh state, form/list), and `ProjectSettingsSection` (settings draft/save/form markup). It **keeps** the project resolution, the unchanged top (PreviewPublishBar + breadcrumb + name + live-website card), and the page's own `settingsRaw` read used by the live-website card's admin fallback.

- [ ] **Step 1: Replace the file contents**

Replace the entire contents of `frontend/src/app/dashboard/[projectSlug]/page.tsx` with:

```tsx
"use client";

import Link from "next/link";
import { use } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ChevronRight, Globe, ExternalLink } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { useUser } from "@/context/user";
import { PreviewPublishBar } from "@/components/dashboard/PreviewPublishBar";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import { SectionRail } from "@/components/dashboard/SectionRail";
import { SectionPanel } from "@/components/dashboard/SectionPanel";
import { DashboardSection } from "@/components/dashboard/DashboardSection";
import { CmsSection } from "@/components/dashboard/CmsSection";
import { AutoFixSection } from "@/components/dashboard/AutoFixSection";
import { ProjectSettingsSection } from "@/components/dashboard/ProjectSettingsSection";
import { visibleSections } from "@/components/dashboard/sectionConfig";
import { useProjectView } from "@/components/dashboard/hooks/useProjectView";

interface ProjectInfo {
  name: string;
  slug: string;
  website_url?: string | null;
}

function fetchProjects(): Promise<ProjectInfo[]> {
  return fetch(`/api/projects`, { credentials: "include", cache: "no-store" }).then((r) =>
    r.json()
  );
}

type SettingsFromApi = { website_url: string | null; allowed_origins: string[] | null };

export default function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ projectSlug: string }>;
}) {
  const { projectSlug } = use(params);
  const { user } = useUser();
  const isAdmin = user?.is_admin ?? false;

  // Shared cache key with the projects-overview page (see original note): both
  // read the same array; this page derives its single project locally.
  const { data: projectsList, loading: projectsLoading } = useQuery<ProjectInfo[]>(
    "projects",
    fetchProjects,
    { ttl: 5 * 60 * 1000 }
  );

  const project = Array.isArray(projectsList)
    ? projectsList.find((p) => p.slug === projectSlug)
    : undefined;
  const projectName = project?.name ?? projectSlug;

  // Live-website card fallback for admins viewing another owner's project
  // (where `project` is absent from /projects). Shares the `settings:<slug>`
  // cache key with ProjectSettingsSection. Read-only here.
  const { data: settingsRaw } = useQuery<SettingsFromApi>(
    `settings:${projectSlug}`,
    () =>
      fetch(`/api/projects/${projectSlug}/settings`, { credentials: "include" }).then((r) =>
        r.json()
      ),
    { ttl: 5 * 60 * 1000, enabled: isAdmin }
  );

  const { activeView, setView } = useProjectView(isAdmin);
  const sections = visibleSections(isAdmin);

  return (
    <div className="p-4 md:p-8">
      <PreviewPublishBar projectSlug={projectSlug} projectName={project?.name ?? projectSlug} />

      {/* Breadcrumb */}
      <div className="mb-6 flex items-center gap-1.5 text-sm text-zinc-400 dark:text-zinc-500">
        <Link
          href="/dashboard"
          className="flex items-center gap-1 transition-colors hover:text-zinc-700 dark:hover:text-zinc-300"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Projects
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="font-medium text-zinc-700 dark:text-zinc-200">{projectName}</span>
      </div>

      <div className="mb-8">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{projectName}</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Manage content and settings for this project.
        </p>

        {/* Live website card (unchanged behavior). */}
        {(() => {
          const projectInList = project !== undefined;
          const liveUrl = project?.website_url || settingsRaw?.website_url || null;
          const adminFallbackPending = isAdmin && !projectInList && settingsRaw === undefined;
          const liveUrlLoading = (projectsLoading && !projectInList) || adminFallbackPending;
          if (!liveUrlLoading && !liveUrl) return null;

          return (
            <div className="mt-4 w-full max-w-xl">
              <AnimatePresence mode="wait" initial={false}>
                {liveUrlLoading ? (
                  <motion.div
                    key="live-url-loading"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.18, ease: "easeOut" }}
                    role="status"
                    aria-busy="true"
                    aria-label="Loading live website URL"
                    className="flex items-center gap-3 rounded-lg border border-zinc-200 bg-white/40 px-4 py-3 text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-200"
                  >
                    <ArcSpinner size={22} />
                    <p className="text-xs font-medium tracking-wide text-zinc-500 dark:text-zinc-400">
                      Loading live website…
                    </p>
                  </motion.div>
                ) : (
                  liveUrl && (
                    <motion.a
                      key="live-url-card"
                      href={liveUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }}
                      className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-white px-4 py-3 transition-colors hover:border-emerald-300 hover:bg-emerald-50/40 dark:border-zinc-800 dark:bg-zinc-900/40 dark:hover:border-emerald-800 dark:hover:bg-emerald-950/30"
                    >
                      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300">
                        <Globe className="h-3.5 w-3.5" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                          Live website
                        </p>
                        <p className="mt-0.5 truncate font-mono text-sm text-zinc-900 dark:text-zinc-100">
                          {liveUrl.replace(/^https?:\/\//, "")}
                        </p>
                        <p className="mt-1 text-xs leading-snug text-zinc-500 dark:text-zinc-400">
                          This is the public website your visitors see.
                        </p>
                      </div>
                      <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-zinc-400 dark:text-zinc-500" />
                    </motion.a>
                  )
                )}
              </AnimatePresence>
            </div>
          );
        })()}
      </div>

      {/* ── Section shell: rail + animated panel ───────────────────────── */}
      <div className="flex flex-col gap-6 md:flex-row md:gap-8">
        <div className="md:w-56 md:shrink-0">
          <div className="md:sticky md:top-24">
            <SectionRail sections={sections} activeView={activeView} onSelect={setView} />
          </div>
        </div>

        <SectionPanel activeView={activeView}>
          {activeView === "dashboard" && <DashboardSection onGoToCms={() => setView("cms")} />}
          {activeView === "cms" && <CmsSection projectSlug={projectSlug} isAdmin={isAdmin} />}
          {activeView === "autofix" && (
            <AutoFixSection
              projectSlug={projectSlug}
              isAdmin={isAdmin}
              currentUserId={user?.id ?? null}
            />
          )}
          {activeView === "settings" && isAdmin && (
            <ProjectSettingsSection projectSlug={projectSlug} />
          )}
        </SectionPanel>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify no stale references remain**

Run (from `frontend/`): `npm run typecheck`
Expected: PASS. If it reports unused imports or `error`/`refreshServices` references, you missed removing old code — the new file above is the complete replacement, so ensure the whole file was replaced.

Run: `npm run lint`
Expected: no errors for this file (warnings allowed if pre-existing).

> Note: in the original, the live-card used `settings === null`; the page's `useQuery` returns `undefined` before first load, so the rewrite checks `settingsRaw === undefined` for the admin-fallback-pending condition. This preserves the original intent (spinner only while the admin fallback fetch is in flight).

- [ ] **Step 3: Run the full dashboard test suite**

Run: `npx vitest run src/components/dashboard`
Expected: PASS — all new section/rail/panel/hook/config tests plus the existing `PreviewPublishBar` and `PublishConfirmModal` tests stay green.

- [ ] **Step 4: Manual verification (run the app)**

Start the frontend (`cd frontend && npm run dev` → http://localhost:3000) and open a project. Verify:
1. Top bar, project name, and live-website card look identical to before.
2. The rail shows Dashboard / CMS / Auto-Fix, plus Settings only when logged in as admin.
3. Dashboard is the default landing and shows the "coming soon" empty state; "Go to CMS" switches to CMS.
4. Switching sections fades out/in (no overlap) and the active pill slides smoothly.
5. CMS still shows the page tabs + service cards and their own fade animation; no double-tab confusion.
6. Auto-Fix shows the issue form + list; filing an issue refreshes the list.
7. Settings (admin) loads, edits, and saves; the live-website card reflects a saved URL.
8. `?view=cms` in the URL deep-links to CMS; refresh keeps the section; browser back works.
9. Resize to mobile width: the rail becomes a horizontal scrollable strip above the panel.
10. Keyboard: Tab to the rail, arrow keys move between sections, focus ring visible.

- [ ] **Step 5: UI/UX polish pass**

Invoke the **ui-ux-pro-max** skill to review and refine the new shell (spacing, visual hierarchy, rail width/padding, active-pill contrast in light/dark, empty-state polish, focus states, reduced-motion). Apply its suggestions as surgical tweaks to `SectionRail.tsx`, `SectionPanel.tsx`, `DashboardSection.tsx`, and the page shell only. Re-run `npx vitest run src/components/dashboard` and `npm run typecheck` after changes.

- [ ] **Step 6: Checkpoint** — Full suite + typecheck green; manual checks pass. Suggested commit:

```bash
git add frontend/src/app/dashboard/[projectSlug]/page.tsx
git commit -m "feat(dashboard): mount project view in sidebar section shell"
```

---

## Self-Review (completed by plan author)

**Spec coverage:**
- Sidebar rail (sections, order, admin gating) → Tasks 1, 3, 9. ✓
- Default = Dashboard / coming-soon empty state → Tasks 1, 5. ✓
- CMS relocated verbatim → Task 6. ✓
- Auto-Fix (renamed, form+list) → Task 7. ✓
- Settings admin-only extraction → Task 8. ✓
- Section-swap fade+lift animation → Task 4 (SectionPanel) + Task 9 wiring. ✓
- Active-pill shared `layoutId` spring → Task 3. ✓
- URL `?view=` persistence + `tab` preservation + admin fallback → Task 2. ✓
- Responsive collapse → Task 3 (rail classes) + Task 9 (shell flex). ✓
- Accessibility (tablist/tab/tabpanel, roving tabindex, arrow keys, focus rings) → Tasks 3, 4. ✓
- `page.tsx` slimmed to orchestrator → Task 9. ✓
- ui-ux-pro-max polish pass → Task 9 Step 5. ✓
- Out of scope (real Vercel analytics; no edits to PreviewPublishBar/ServiceGrid/PageTabs/IssueForm/IssueList/ServiceCard internals) — honored: those are imported/wrapped, not modified. ✓

**Placeholder scan:** No TBD/TODO; every code step contains full code. ✓

**Type consistency:** `SectionKey`/`SectionDef` from `sectionConfig` used consistently in `useProjectView`, `SectionRail`, and `page.tsx`. `useProjectView` returns `{ activeView, setView }` — matches usage in Task 9. Section component prop names (`projectSlug`, `isAdmin`, `currentUserId`, `onGoToCms`) match their call sites. ✓
