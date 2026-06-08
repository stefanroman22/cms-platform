# Marketing nav restructure + Team, About, Clients pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Commit policy (Stefan's workflow):** Do NOT run the `git commit` steps unless Stefan explicitly says to commit. Until then, leave changes staged/unstaged and continue. Commit steps are written out so they're ready when he gives the go-ahead.

**Goal:** Restructure the marketing nav (remove Projects; add Clients + Team) and redistribute content: a new Team page (team + values), an About page rebuilt around the "What do we do" block, and a new filterable Clients page.

**Architecture:** Reuse by extraction — the home "What do we do" block becomes a shared `WhatWeDo` component with a `layout` prop so home stays pixel-identical while About gets a full-width variant. The new Clients grid and the home carousel both read the same `content/projects.ts`. Theme (dark + gold accent, `Reveal`/`REVEAL_EASE` motion, `MotionConfig reducedMotion="user"`) is preserved throughout.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, Tailwind v4, Motion (`motion/react`), lucide-react, Vitest + Testing Library (jsdom).

**Spec:** `docs/superpowers/specs/2026-06-08-marketing-nav-team-clients-restructure-design.md`

**Working directory note:** all `npx`/`npm` commands run from `frontend/` (e.g. `cd frontend && npx vitest run ...`). The repo root is `CMS - websites`.

---

## File map

**Create**
- `frontend/src/components/work/WhatWeDo.tsx` — shared "What do we do" block (`layout: "split" | "full"`), owns `SERVICES`.
- `frontend/src/components/work/__tests__/WhatWeDo.test.tsx`
- `frontend/src/components/team/ValuesSection.tsx` — framer-animated values block (4 local values).
- `frontend/src/components/team/__tests__/ValuesSection.test.tsx`
- `frontend/src/components/work/ProjectsGrid.tsx` — filterable detailed project card grid.
- `frontend/src/components/work/__tests__/ProjectsGrid.test.tsx`
- `frontend/src/app/(marketing)/team/page.tsx` — `/team` route.
- `frontend/src/app/(marketing)/clients/page.tsx` — `/clients` route.
- `frontend/src/lib/__tests__/nav-links.test.ts`
- `frontend/src/components/about/__tests__/AboutStory.test.tsx`

**Modify**
- `frontend/src/components/work/WorkSection.tsx` — use `<WhatWeDo layout="split" />` (home unchanged).
- `frontend/src/components/about/AboutStory.tsx` — drop `values` prop + grid (story only).
- `frontend/src/content/about.ts` — remove `Value` interface + `values` field from `AboutContent`.
- `frontend/src/content/about.json` — remove the `values` array.
- `frontend/src/app/(marketing)/about/page.tsx` — compose `AboutStory` + `WhatWeDo` (full).
- `frontend/src/lib/nav-links.ts` — new `NAV_LINKS`.

---

## Task 1: Extract `WhatWeDo` component; refactor `WorkSection`

**Files:**
- Create: `frontend/src/components/work/WhatWeDo.tsx`
- Test: `frontend/src/components/work/__tests__/WhatWeDo.test.tsx`
- Modify: `frontend/src/components/work/WorkSection.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/work/__tests__/WhatWeDo.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LazyMotion, domAnimation } from "motion/react";
import { WhatWeDo } from "../WhatWeDo";

describe("WhatWeDo", () => {
  it("renders all four services in the split layout", () => {
    // split layout has no own LazyMotion; provide one (WorkSection does in prod).
    render(
      <LazyMotion features={domAnimation}>
        <WhatWeDo layout="split" />
      </LazyMotion>
    );
    expect(screen.getByRole("heading", { name: /what do we do/i })).toBeInTheDocument();
    expect(screen.getByText("We build AI agents")).toBeInTheDocument();
    expect(screen.getByText("We develop websites")).toBeInTheDocument();
    expect(screen.getByText("We build software applications")).toBeInTheDocument();
    expect(screen.getByText("We create automation workflows with AI")).toBeInTheDocument();
  });

  it("renders the heading and all four services in the full layout", () => {
    render(<WhatWeDo layout="full" />);
    expect(screen.getByRole("heading", { name: /what do we do/i })).toBeInTheDocument();
    expect(screen.getByText("We build AI agents")).toBeInTheDocument();
    expect(screen.getByText("We create automation workflows with AI")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/work/__tests__/WhatWeDo.test.tsx`
Expected: FAIL — `Failed to resolve import "../WhatWeDo"`.

- [ ] **Step 3: Create `WhatWeDo.tsx`**

Create `frontend/src/components/work/WhatWeDo.tsx`. The `split` branch reproduces the exact current left column of `WorkSection` (so home is unchanged); the `full` branch is a self-contained full-width section.

```tsx
"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Bot, Globe, AppWindow, Workflow, type LucideIcon } from "lucide-react";
import { Reveal } from "@/components/motion/Reveal";

interface Service {
  icon: LucideIcon;
  title: string;
  desc: string;
}

/** What Roman Technologies does — AI agents first, as requested. */
export const SERVICES: Service[] = [
  {
    icon: Bot,
    title: "We build AI agents",
    desc: "Autonomous agents that handle real work end-to-end — not just chatbots.",
  },
  {
    icon: Globe,
    title: "We develop websites",
    desc: "Fast, beautiful, SEO-ready sites that turn visitors into customers.",
  },
  {
    icon: AppWindow,
    title: "We build software applications",
    desc: "Web, mobile and desktop apps engineered to scale with you.",
  },
  {
    icon: Workflow,
    title: "We create automation workflows with AI",
    desc: "AI-driven workflows that run your busywork around the clock.",
  },
];

/** The intro copy (eyebrow + heading + lead) shared by both layouts. */
function Intro({ centered }: { centered: boolean }) {
  return (
    <Reveal inView amount={0.4} direction="up" distance={24}>
      <p className="mb-4 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
        What we build
      </p>
      <h2 className="font-display text-[clamp(2rem,5vw,3.25rem)] font-bold leading-[1.05] tracking-[-0.02em] text-text-primary">
        What do we do?
      </h2>
      <p
        className={`mt-5 text-[1.0625rem] leading-relaxed text-text-secondary ${
          centered ? "mx-auto max-w-xl" : "max-w-md"
        }`}
      >
        From a single landing page to full AI platforms — here&apos;s how we help
        ambitious companies ship.
      </p>
    </Reveal>
  );
}

/**
 * "What do we do" — reused on the home page (`layout="split"`, the left column
 * beside the projects carousel) and the About page (`layout="full"`, a
 * full-width section). `split` renders only the column content and relies on an
 * ancestor `LazyMotion`/`MotionConfig` (WorkSection provides them); `full` is a
 * self-contained section.
 */
export function WhatWeDo({ layout }: { layout: "split" | "full" }) {
  if (layout === "split") {
    return (
      <div>
        <Intro centered={false} />
        <ul className="mt-8 space-y-5">
          {SERVICES.map((s, i) => (
            <Reveal
              as="li"
              key={s.title}
              inView
              amount={0.6}
              direction="up"
              distance={16}
              delay={i * 0.06}
              className="flex gap-4"
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-accent/25 bg-accent/10 text-accent">
                <s.icon className="h-5 w-5" strokeWidth={2} aria-hidden="true" />
              </span>
              <div>
                <h3 className="font-display text-base font-semibold text-text-primary">
                  {s.title}
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-text-secondary">{s.desc}</p>
              </div>
            </Reveal>
          ))}
        </ul>
      </div>
    );
  }

  // layout === "full"
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="relative overflow-hidden bg-black px-6 py-16 lg:py-24">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-24 h-[460px] w-[760px] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
            style={{
              background:
                "radial-gradient(circle, rgba(201,169,97,0.10), rgba(201,169,97,0) 70%)",
            }}
          />
          <div className="relative z-10 mx-auto max-w-6xl">
            <div className="mx-auto max-w-3xl text-center">
              <Intro centered />
            </div>
            <div className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {SERVICES.map((s, i) => (
                <Reveal key={s.title} inView amount={0.3} direction="up" distance={20} delay={i * 0.08}>
                  <div className="group h-full rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm transition-colors hover:border-accent/40">
                    <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-accent/25 bg-accent/10 text-accent transition-transform duration-300 group-hover:scale-110">
                      <s.icon className="h-6 w-6" strokeWidth={2} aria-hidden="true" />
                    </span>
                    <h3 className="mt-5 font-display text-lg font-semibold text-text-primary">
                      {s.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-text-secondary">{s.desc}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/work/__tests__/WhatWeDo.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Refactor `WorkSection` to use the split layout**

Replace the entire contents of `frontend/src/components/work/WorkSection.tsx` with:

```tsx
"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Reveal } from "@/components/motion/Reveal";
import { WhatWeDo } from "@/components/work/WhatWeDo";
import { ProjectsCarousel } from "@/components/work/ProjectsCarousel";

/**
 * Home "Projects" section: what we do (left) beside a live projects carousel
 * (right). Anchored as #projects for the nav + deep links. Each block fades in
 * on scroll, echoing the contact and pricing sections.
 */
export function WorkSection() {
  return (
    <section id="projects" className="relative overflow-hidden bg-black px-6 py-16 lg:py-24">
      {/* Subtle gold ambient glow, matching the surrounding sections. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-24 h-[460px] w-[760px] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
        style={{
          background: "radial-gradient(circle, rgba(201,169,97,0.10), rgba(201,169,97,0) 70%)",
        }}
      />

      <LazyMotion features={domAnimation}>
        <MotionConfig reducedMotion="user">
          <div className="relative z-10 mx-auto max-w-6xl">
            <div className="grid grid-cols-1 items-start gap-12 lg:grid-cols-2 lg:gap-16">
              {/* Left — features */}
              <WhatWeDo layout="split" />

              {/* Right — projects carousel */}
              <Reveal inView amount={0.15} direction="up" distance={28} delay={0.1}>
                <ProjectsCarousel />
              </Reveal>
            </div>
          </div>
        </MotionConfig>
      </LazyMotion>
    </section>
  );
}
```

- [ ] **Step 6: Verify the WhatWeDo tests + typecheck still pass**

Run: `cd frontend && npx vitest run src/components/work/__tests__/WhatWeDo.test.tsx && npx tsc --noEmit`
Expected: tests PASS; tsc reports no errors.

- [ ] **Step 7: Commit** *(only on Stefan's go-ahead)*

```bash
git add frontend/src/components/work/WhatWeDo.tsx frontend/src/components/work/__tests__/WhatWeDo.test.tsx frontend/src/components/work/WorkSection.tsx
git commit -m "refactor(marketing): extract WhatWeDo from WorkSection (split + full layouts)"
```

---

## Task 2: Strip values from About; rebuild About page around `WhatWeDo`

**Files:**
- Modify: `frontend/src/components/about/AboutStory.tsx`
- Modify: `frontend/src/content/about.ts`
- Modify: `frontend/src/content/about.json`
- Modify: `frontend/src/app/(marketing)/about/page.tsx`
- Test: `frontend/src/components/about/__tests__/AboutStory.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/about/__tests__/AboutStory.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AboutStory } from "../AboutStory";

describe("AboutStory", () => {
  it("renders the story heading and paragraphs (no values grid)", () => {
    render(
      <AboutStory story={{ heading: "Who we are", paragraphs: ["First para", "Second para"] }} />
    );
    expect(screen.getByRole("heading", { name: "Who we are" })).toBeInTheDocument();
    expect(screen.getByText("First para")).toBeInTheDocument();
    expect(screen.getByText("Second para")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/about/__tests__/AboutStory.test.tsx`
Expected: FAIL — TypeScript/runtime error because `AboutStory` still requires a `values` prop (type error on the render call / `values.map` is undefined at runtime).

- [ ] **Step 3: Update `AboutStory.tsx` (drop values)**

Replace the entire contents of `frontend/src/components/about/AboutStory.tsx` with:

```tsx
"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Reveal } from "@/components/motion/Reveal";
import type { AboutContent } from "@/content/about";

export function AboutStory({ story }: { story: AboutContent["story"] }) {
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="px-6 py-14 sm:py-20">
          <div className="mx-auto max-w-5xl">
            <div className="mx-auto max-w-3xl text-center">
              <Reveal inView amount={0.4}>
                <h2 className="font-display text-[clamp(1.8rem,4vw,2.75rem)] font-bold leading-[1.1] tracking-[-0.02em] text-text-primary">
                  {story.heading}
                </h2>
              </Reveal>

              {story.paragraphs.map((paragraph, i) => (
                <Reveal key={i} inView amount={0.3} delay={0.08 + i * 0.08}>
                  <p className="mt-5 text-[1rem] leading-relaxed text-text-secondary sm:text-[1.0625rem]">
                    {paragraph}
                  </p>
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
```

- [ ] **Step 4: Remove `Value`/`values` from `about.ts`**

In `frontend/src/content/about.ts`, delete the `Value` interface (lines defining `export interface Value { title; description; }`) and remove the `values: Value[];` line from `AboutContent`. The interface block becomes:

```ts
export interface TeamMember {
  name: string;
  role: string;
  /** Shown as the overlay that fades in when hovering the photo. */
  description: string;
  /** Path under /public, e.g. "/team/stefan-roman.svg". */
  image: string;
  email: string;
  linkedin: string;
}

export interface AboutContent {
  hero: { eyebrow: string; title: string; lead: string };
  story: { heading: string; paragraphs: string[] };
  team: { heading: string; subheading: string; members: TeamMember[] };
}
```

(Leave the file header comment and `export const about = data as AboutContent;` line intact.)

- [ ] **Step 5: Remove the `values` array from `about.json`**

In `frontend/src/content/about.json`, delete the entire `"values": [ ... ]` array (the four objects: Human-reviewed, EU-based & GDPR-first, Managed end-to-end, Fair & transparent), including its trailing comma, so the object goes directly from `"story"` to `"team"`.

- [ ] **Step 6: Update the About page**

Replace the entire contents of `frontend/src/app/(marketing)/about/page.tsx` with:

```tsx
import type { Metadata } from "next";
import { about } from "@/content/about";
import { AboutStory } from "@/components/about/AboutStory";
import { WhatWeDo } from "@/components/work/WhatWeDo";

export const metadata: Metadata = {
  title: "About — Roman Technologies",
  description: about.hero.lead,
};

/**
 * About page. Copy lives in `src/content/about.json`. The page composes the
 * "Who we are" story with the full-width "What do we do" block (shared with the
 * home page). The team now lives on `/team`.
 */
export default function AboutPage() {
  return (
    <div className="bg-black">
      <AboutStory story={about.story} />
      <WhatWeDo layout="full" />
    </div>
  );
}
```

- [ ] **Step 7: Run tests + typecheck to verify pass**

Run: `cd frontend && npx vitest run src/components/about/__tests__/AboutStory.test.tsx && npx tsc --noEmit`
Expected: test PASS; tsc reports no errors (confirms no other consumer of the removed `values`).

- [ ] **Step 8: Commit** *(only on Stefan's go-ahead)*

```bash
git add frontend/src/components/about/AboutStory.tsx frontend/src/content/about.ts frontend/src/content/about.json frontend/src/app/(marketing)/about/page.tsx frontend/src/components/about/__tests__/AboutStory.test.tsx
git commit -m "feat(about): replace team + values with full-width WhatWeDo block"
```

---

## Task 3: Create `ValuesSection` (Team page values)

**Files:**
- Create: `frontend/src/components/team/ValuesSection.tsx`
- Test: `frontend/src/components/team/__tests__/ValuesSection.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/team/__tests__/ValuesSection.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ValuesSection } from "../ValuesSection";

describe("ValuesSection", () => {
  it("renders all four values with their descriptions", () => {
    render(<ValuesSection />);
    expect(screen.getByText("Client comes first")).toBeInTheDocument();
    expect(screen.getByText("Teamwork")).toBeInTheDocument();
    expect(screen.getByText("Ownership")).toBeInTheDocument();
    expect(screen.getByText("Transparency")).toBeInTheDocument();
    expect(screen.getByText(/start from your goals/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/team/__tests__/ValuesSection.test.tsx`
Expected: FAIL — `Failed to resolve import "../ValuesSection"`.

- [ ] **Step 3: Create `ValuesSection.tsx`**

Create `frontend/src/components/team/ValuesSection.tsx`:

```tsx
"use client";

import { LazyMotion, domAnimation, MotionConfig, m } from "motion/react";
import { HeartHandshake, Users, KeyRound, Eye, type LucideIcon } from "lucide-react";
import { Reveal, REVEAL_EASE } from "@/components/motion/Reveal";

interface Value {
  icon: LucideIcon;
  title: string;
  description: string;
}

/** Culture values shown on the Team page. Local const mirrors WorkSection's SERVICES. */
const VALUES: Value[] = [
  {
    icon: HeartHandshake,
    title: "Client comes first",
    description:
      "We start from your goals, not our stack. Every decision is measured by what moves your business forward.",
  },
  {
    icon: Users,
    title: "Teamwork",
    description:
      "Engineering, security and strategy work as one team, so nothing falls between the cracks.",
  },
  {
    icon: KeyRound,
    title: "Ownership",
    description:
      "You own everything we build — code, data and roadmap. No lock-in, no black boxes.",
  },
  {
    icon: Eye,
    title: "Transparency",
    description:
      "Clear quotes, honest timelines, and a human who answers. You always know where things stand.",
  },
];

export function ValuesSection() {
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="relative overflow-hidden px-6 pb-24 pt-8 sm:pb-32">
          {/* Brass ambient glow, echoing the other sections. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-10 h-[420px] w-[720px] -translate-x-1/2 rounded-full opacity-50 blur-3xl"
            style={{
              background: "radial-gradient(circle, rgba(201,169,97,0.10), rgba(201,169,97,0) 70%)",
            }}
          />

          <div className="relative z-10 mx-auto max-w-6xl">
            <div className="mx-auto max-w-2xl text-center">
              <Reveal inView amount={0.4}>
                <p className="mb-4 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
                  What we stand for
                </p>
                <h2 className="font-display text-[clamp(1.8rem,4vw,2.75rem)] font-bold leading-[1.1] tracking-[-0.02em] text-text-primary">
                  Our values
                </h2>
              </Reveal>
            </div>

            <div className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {VALUES.map((value, i) => (
                <Reveal key={value.title} inView amount={0.3} direction="up" distance={24} delay={i * 0.1}>
                  <m.div
                    whileHover={{ y: -6 }}
                    transition={{ duration: 0.3, ease: REVEAL_EASE }}
                    className="group h-full rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm transition-colors hover:border-accent/40"
                  >
                    <m.span
                      initial={{ scale: 0.6, opacity: 0 }}
                      whileInView={{ scale: 1, opacity: 1 }}
                      viewport={{ once: true, amount: 0.5 }}
                      transition={{ duration: 0.5, ease: REVEAL_EASE, delay: i * 0.1 + 0.15 }}
                      className="flex h-12 w-12 items-center justify-center rounded-xl border border-accent/25 bg-accent/10 text-accent"
                    >
                      <value.icon className="h-6 w-6" strokeWidth={2} aria-hidden="true" />
                    </m.span>
                    <h3 className="mt-5 font-display text-lg font-semibold text-text-primary">
                      {value.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                      {value.description}
                    </p>
                  </m.div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/team/__tests__/ValuesSection.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit** *(only on Stefan's go-ahead)*

```bash
git add frontend/src/components/team/ValuesSection.tsx frontend/src/components/team/__tests__/ValuesSection.test.tsx
git commit -m "feat(team): add animated ValuesSection (client-first, teamwork, ownership, transparency)"
```

---

## Task 4: Create the `/team` page

**Files:**
- Create: `frontend/src/app/(marketing)/team/page.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/app/(marketing)/team/page.tsx`:

```tsx
import type { Metadata } from "next";
import { about } from "@/content/about";
import { TeamSection } from "@/components/about/TeamSection";
import { ValuesSection } from "@/components/team/ValuesSection";

export const metadata: Metadata = {
  title: "Team — Roman Technologies",
  description: about.team.subheading,
};

/**
 * Team page: a short hero, the team grid (moved off the About page), and the
 * culture values. Team copy + members live in `src/content/about.json`.
 */
export default function TeamPage() {
  return (
    <div className="bg-black">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-8 pt-14 sm:pb-12 sm:pt-24">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-0 h-[400px] w-[660px] -translate-x-1/2 rounded-full opacity-50 blur-3xl"
          style={{
            background: "radial-gradient(circle, rgba(201,169,97,0.12), rgba(201,169,97,0) 70%)",
          }}
        />
        <div className="animate-fade-down relative z-10 mx-auto max-w-2xl text-center">
          <p className="mb-5 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
            Our team
          </p>
          <h1 className="text-balance font-display text-[clamp(2.25rem,6vw,4rem)] font-bold leading-[1.04] tracking-[-0.02em] text-text-primary">
            A small, senior team that ships.
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-[1.0625rem] leading-relaxed text-text-secondary sm:text-[1.15rem]">
            The people behind every build — engineering, security and strategy under one roof, and
            the principles that guide how we work.
          </p>
        </div>
      </section>

      <TeamSection team={about.team} />
      <ValuesSection />
    </div>
  );
}
```

- [ ] **Step 2: Verify the route compiles (typecheck)**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit** *(only on Stefan's go-ahead)*

```bash
git add "frontend/src/app/(marketing)/team/page.tsx"
git commit -m "feat(team): add /team page (hero + team grid + values)"
```

---

## Task 5: Create `ProjectsGrid` (filterable detailed grid)

**Files:**
- Create: `frontend/src/components/work/ProjectsGrid.tsx`
- Test: `frontend/src/components/work/__tests__/ProjectsGrid.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/work/__tests__/ProjectsGrid.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProjectsGrid } from "../ProjectsGrid";

describe("ProjectsGrid", () => {
  it("renders all projects with their key info by default", () => {
    render(<ProjectsGrid />);
    expect(screen.getByText("Akris Website")).toBeInTheDocument();
    expect(screen.getByText("Pluxbox Website")).toBeInTheDocument();
    expect(screen.getByText("Roman Mariana - Business Website")).toBeInTheDocument();
    // keyInfo labels render (each card has a "Type" row).
    expect(screen.getAllByText("Type").length).toBeGreaterThan(0);
  });

  it("filters projects by name", async () => {
    const user = userEvent.setup();
    render(<ProjectsGrid />);
    await user.type(screen.getByLabelText(/search projects/i), "akris");
    expect(screen.getByText("Akris Website")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByText("Pluxbox Website")).not.toBeInTheDocument()
    );
  });

  it("shows an empty state when nothing matches", async () => {
    const user = userEvent.setup();
    render(<ProjectsGrid />);
    await user.type(screen.getByLabelText(/search projects/i), "zzzzz");
    expect(screen.getByText(/no projects match/i)).toBeInTheDocument();
    expect(screen.queryByText("Akris Website")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/work/__tests__/ProjectsGrid.test.tsx`
Expected: FAIL — `Failed to resolve import "../ProjectsGrid"`.

- [ ] **Step 3: Create `ProjectsGrid.tsx`**

Create `frontend/src/components/work/ProjectsGrid.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";
import { LazyMotion, domAnimation, m, AnimatePresence, MotionConfig } from "motion/react";
import { ArrowUpRight, Search } from "lucide-react";
import { projects } from "@/content/projects";
import { REVEAL_EASE } from "@/components/motion/Reveal";

/**
 * Clients page grid: detailed project cards (image, name, tagline, key info,
 * live link) with a name filter. Reads the same `content/projects.ts` as the
 * home carousel. Cards animate in and re-flow as the filter narrows results.
 */
export function ProjectsGrid() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter(
      (p) => p.name.toLowerCase().includes(q) || p.short.toLowerCase().includes(q)
    );
  }, [query]);

  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <section className="px-6 pb-24 sm:pb-32">
          <div className="mx-auto max-w-6xl">
            {/* Search */}
            <div className="mx-auto mb-10 max-w-md">
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary"
                  aria-hidden="true"
                />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search projects…"
                  aria-label="Search projects by name"
                  className="w-full rounded-xl border border-border bg-surface/40 py-3 pl-10 pr-4 text-sm text-text-primary placeholder:text-text-tertiary outline-none transition-colors focus:border-accent/50 focus-visible:ring-2 focus-visible:ring-accent"
                />
              </div>
            </div>

            {filtered.length === 0 ? (
              <p className="text-center text-sm text-text-secondary">
                No projects match “{query}”.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                <AnimatePresence>
                  {filtered.map((p, i) => (
                    <m.article
                      key={p.id}
                      layout
                      initial={{ opacity: 0, y: 24 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -12 }}
                      transition={{ duration: 0.4, ease: REVEAL_EASE, delay: i * 0.05 }}
                      className="group flex flex-col overflow-hidden rounded-2xl border border-border bg-surface/30 transition-colors hover:border-accent/40"
                    >
                      <div className="relative aspect-[16/10] w-full overflow-hidden">
                        <img
                          src={p.image}
                          alt={`${p.name} preview`}
                          loading="lazy"
                          draggable={false}
                          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                        />
                        {p.url && (
                          <a
                            href={p.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`Open ${p.name} in a new tab`}
                            className="group/btn absolute right-3 top-3 flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-black/40 text-white backdrop-blur-sm transition-all duration-300 hover:scale-105 hover:border-accent hover:bg-accent hover:text-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-pointer"
                          >
                            <ArrowUpRight className="h-5 w-5 transition-transform duration-300 group-hover/btn:rotate-45" />
                          </a>
                        )}
                      </div>
                      <div className="flex flex-1 flex-col p-6">
                        <h3 className="font-display text-lg font-semibold text-text-primary">
                          {p.name}
                        </h3>
                        <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                          {p.tagline}
                        </p>
                        <dl className="mt-5 space-y-2 border-t border-border pt-4">
                          {p.keyInfo.map((info) => (
                            <div key={info.label} className="flex items-baseline gap-3 text-sm">
                              <dt className="w-16 shrink-0 text-text-tertiary">{info.label}</dt>
                              <dd className="text-text-secondary">{info.value}</dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                    </m.article>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </div>
        </section>
      </MotionConfig>
    </LazyMotion>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/work/__tests__/ProjectsGrid.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit** *(only on Stefan's go-ahead)*

```bash
git add frontend/src/components/work/ProjectsGrid.tsx frontend/src/components/work/__tests__/ProjectsGrid.test.tsx
git commit -m "feat(clients): add filterable ProjectsGrid with detailed cards"
```

---

## Task 6: Create the `/clients` page

**Files:**
- Create: `frontend/src/app/(marketing)/clients/page.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/src/app/(marketing)/clients/page.tsx`:

```tsx
import type { Metadata } from "next";
import { ProjectsGrid } from "@/components/work/ProjectsGrid";

export const metadata: Metadata = {
  title: "Clients — Roman Technologies",
  description:
    "A selection of websites, applications, AI agents & workflows built and now keep running for clients across the EU.",
};

/**
 * Clients page: a short hero + the filterable projects grid. Project data lives
 * in `src/content/projects.ts`.
 */
export default function ClientsPage() {
  return (
    <div className="bg-black">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-10 pt-14 sm:pb-12 sm:pt-24">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-0 h-[400px] w-[660px] -translate-x-1/2 rounded-full opacity-50 blur-3xl"
          style={{
            background: "radial-gradient(circle, rgba(201,169,97,0.12), rgba(201,169,97,0) 70%)",
          }}
        />
        <div className="animate-fade-down relative z-10 mx-auto max-w-2xl text-center">
          <p className="mb-5 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
            Our work
          </p>
          <h1 className="text-balance font-display text-[clamp(2.25rem,6vw,4rem)] font-bold leading-[1.04] tracking-[-0.02em] text-text-primary">
            Built for ambitious companies.
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-[1.0625rem] leading-relaxed text-text-secondary sm:text-[1.15rem]">
            A selection of websites, applications and AI workflows we&apos;ve designed, built and now
            keep running for clients across the EU.
          </p>
        </div>
      </section>

      <ProjectsGrid />
    </div>
  );
}
```

- [ ] **Step 2: Verify the route compiles (typecheck)**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit** *(only on Stefan's go-ahead)*

```bash
git add "frontend/src/app/(marketing)/clients/page.tsx"
git commit -m "feat(clients): add /clients page (hero + projects grid)"
```

---

## Task 7: Update the navigation

**Files:**
- Modify: `frontend/src/lib/nav-links.ts`
- Test: `frontend/src/lib/__tests__/nav-links.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/__tests__/nav-links.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { NAV_LINKS } from "@/lib/nav-links";

describe("NAV_LINKS", () => {
  it("lists About, Clients, Team, Contact in order with no Projects", () => {
    expect(NAV_LINKS.map((l) => l.label)).toEqual(["About", "Clients", "Team", "Contact"]);
    expect(NAV_LINKS.map((l) => l.href)).toEqual(["/about", "/clients", "/team", "/contact"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/__tests__/nav-links.test.ts`
Expected: FAIL — current array is `[Projects, About, Contact]`, so both assertions fail.

- [ ] **Step 3: Update `nav-links.ts`**

Replace the array in `frontend/src/lib/nav-links.ts` (keep the file's leading comment):

```ts
export const NAV_LINKS = [
  { label: "About", href: "/about" },
  { label: "Clients", href: "/clients" },
  { label: "Team", href: "/team" },
  { label: "Contact", href: "/contact" },
] as const;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/__tests__/nav-links.test.ts`
Expected: PASS (1 test). Both desktop `Header` and mobile `HeaderRightCluster` consume this single source, so both update.

- [ ] **Step 5: Commit** *(only on Stefan's go-ahead)*

```bash
git add frontend/src/lib/nav-links.ts frontend/src/lib/__tests__/nav-links.test.ts
git commit -m "feat(nav): swap Projects for Clients + Team (About · Clients · Team · Contact)"
```

---

## Task 8: Styling polish + full verification

**Files:** (touch-ups only, as ui-ux-pro-max recommends) `WhatWeDo.tsx`, `ValuesSection.tsx`, `ProjectsGrid.tsx`, `team/page.tsx`, `clients/page.tsx`.

- [ ] **Step 1: Run the ui-ux-pro-max skill for theme-consistent polish**

Invoke the `ui-ux-pro-max` skill. Scope it to: the full-layout `WhatWeDo` grid, `ValuesSection`, `ProjectsGrid` cards + search field, and the two new page heroes. Goal: spacing rhythm, typography scale, hover/motion polish, and consistency with the existing dark + gold (`#c9a961`) theme and the Contact/About sections. Apply only the tweaks that keep the components on-theme; do not change copy or structure.

- [ ] **Step 2: Run the full test suite**

Run: `cd frontend && npx vitest run`
Expected: all suites PASS (including the new WhatWeDo, AboutStory, ValuesSection, ProjectsGrid, nav-links tests and all pre-existing tests).

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Lint**

Run: `cd frontend && npm run lint`
Expected: no errors (warnings acceptable if pre-existing).

- [ ] **Step 5: Production build (milestone)**

Run: `cd frontend && npm run build`
Expected: build succeeds; `/about`, `/team`, and `/clients` appear in the route output.

- [ ] **Step 6: Manual smoke check (dev server)**

Run `cd frontend && npm run dev`, then verify in the browser:
- Top nav (desktop) shows **About · Clients · Team · Contact**, no Projects; mobile drawer shows the same four.
- `/` (home) looks identical to before (WhatWeDo split + carousel).
- `/about` shows the "Who we are" story + full-width "What do we do" (no team, no values grid).
- `/team` shows hero + team grid + animated values.
- `/clients` shows hero + filterable grid; typing a name filters; clearing restores; non-match shows the empty state; the live-site links open.

- [ ] **Step 7: Commit** *(only on Stefan's go-ahead)*

```bash
git add -A
git commit -m "style(marketing): ui-ux-pro-max polish for team/clients/about sections"
```

---

## Self-review notes

- **Spec coverage:** nav swap → Task 7; Team page (team + values) → Tasks 3, 4; About rebuilt around WhatWeDo, values removed → Tasks 1, 2; Clients filterable grid → Tasks 5, 6; home unchanged via extraction → Task 1; styling via ui-ux-pro-max → Task 8; tests for each new unit → Tasks 1–3, 5, 7. All spec sections map to a task.
- **Type consistency:** `WhatWeDo` prop `layout: "split" | "full"` is used identically in `WorkSection` (split), the About page (full), and tests. `SERVICES` exported from `WhatWeDo`. `ValuesSection` and `ProjectsGrid` take no props. `AboutStory` now takes only `story: AboutContent["story"]`, matching the About page call and its test.
- **No placeholders:** every code step contains complete, runnable code; every run step has an exact command + expected result.
- **jsdom/motion note:** tests query by text/role/label (visible regardless of scroll-reveal state); `whileInView` triggers immediately when `IntersectionObserver` is absent, so no polyfill is needed. The `ProjectsGrid` filter test uses `waitFor` to allow the card exit animation to complete.
