---
name: motion-animations
description: Implement animations and micro-interactions using Motion (formerly Framer Motion) in a React 19 project. Use whenever a design specifies animations, scroll effects, hover states, page transitions, or layout transitions. The library is "motion" with import path "motion/react" — NEVER framer-motion.
---

# Motion Animations

The library is **Motion**. It was renamed from Framer Motion in mid-2025. Package: `motion`. React entry: `motion/react`.

## Imports — ALWAYS use these

```ts
// React components and hooks
import {
  motion,
  AnimatePresence,
  useScroll,
  useTransform,
  useReducedMotion,
  useInView,
} from "motion/react";

// Lightweight animate function (rare — imperative animation outside React)
import { animate } from "motion";
```

**NEVER** `import { motion } from "framer-motion"`. That's the legacy name. The package is now `motion`.

## Client component requirement

Vite SPA components are all client-side; no directive needed. There is no `"use client"` in a Vite SPA — every component is already client-rendered. Do not add `"use client"` directives.

## Patterns by use case

### Fade-in on mount

```tsx
import { motion } from "motion/react";

<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
>
  ...
</motion.div>
```

### Staggered children (e.g. features grid)

```tsx
const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.2 },
  },
};
const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

<motion.ul variants={container} initial="hidden" animate="show">
  {items.map((i) => (
    <motion.li key={i.id} variants={item}>{i.text}</motion.li>
  ))}
</motion.ul>
```

### Scroll-triggered reveal (once-only)

```tsx
<motion.section
  initial={{ opacity: 0, y: 40 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true, margin: "-100px" }}
  transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
>
  ...
</motion.section>
```

The `margin: "-100px"` triggers slightly before the element fully enters the viewport, which feels more responsive.

### Parallax on scroll

```tsx
import { useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";

function ParallaxImage() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], [-50, 50]);

  return (
    <div ref={ref} className="relative overflow-hidden">
      <motion.div style={{ y }}>{/* image */}</motion.div>
    </div>
  );
}
```

### Hover micro-interaction

```tsx
<motion.button
  whileHover={{ scale: 1.03 }}
  whileTap={{ scale: 0.97 }}
  transition={{ type: "spring", stiffness: 400, damping: 25 }}
  className="..."
>
  Click me
</motion.button>
```

Don't apply `whileHover` to large surface areas (whole cards) — it can feel jittery. Keep it on buttons and small interactive elements.

### Layout animation (e.g. expanding card)

```tsx
<motion.div layout transition={{ type: "spring", duration: 0.4 }}>
  {expanded && <motion.div layout>{/* extra content */}</motion.div>}
</motion.div>
```

### AnimatePresence (mount/unmount)

```tsx
<AnimatePresence mode="wait">
  {isOpen && (
    <motion.div
      key="modal"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      ...
    </motion.div>
  )}
</AnimatePresence>
```

The `key` prop is REQUIRED on children of AnimatePresence — without it, exit animations don't fire.

### Submit → success morph (forms, booking, checkout)

The confirm/submit action must NOT be a blocky disabled button. On submit, show an in-tone loading
spinner; on success, morph it into a green check, then fade the confirmation in.

```tsx
// phase: "idle" | "submitting" | "success"
<AnimatePresence mode="wait">
  {phase === "submitting" && (
    <motion.span key="spin" className="spinner" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
  )}
  {phase === "success" && (
    <motion.svg key="check" viewBox="0 0 24 24" initial={{ scale: 0.6, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", stiffness: 380, damping: 22 }}>
      <motion.path d="M5 13l4 4L19 7" fill="none" stroke="currentColor" strokeWidth={2}
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.35, delay: 0.05 }} />
    </motion.svg>
  )}
</AnimatePresence>
```

Reduced motion → skip the choreography, jump straight to the success state.

### Mobile multi-step flow (one section at a time)

Booking/checkout/wizards on mobile show ONE step at a time with a fade/slide between steps + a Back
control; the primary action lives in a sticky bottom bar (always visible — never scroll to act).

```tsx
<AnimatePresence mode="wait" initial={false}>
  <motion.div
    key={step}
    initial={reduce ? { opacity: 0 } : { opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    exit={reduce ? { opacity: 0 } : { opacity: 0, y: -12 }}
    transition={{ duration: reduce ? 0.12 : 0.26, ease: [0.2, 0, 0, 1] }}
  >
    {stepBodies[step]}
  </motion.div>
</AnimatePresence>
```

On desktop, the same flow keeps a fixed summary/action column and only the content column scrolls.

Both viewports use the SAME height-bounded model: clear any fixed site header with top padding so
it never overlaps the flow's top bar, bound the shell to `calc(100svh − top − bottom)`, and let only
the inner region scroll — the page itself must not scroll. Animate the live summary/side-panel updates
too (selected item, date/time, total fade/slide in as they change; step content cross-fades on advance).
On mobile, surface the RUNNING SELECTION (all picks so far + total) persistently in the fixed bottom bar
so it's visible at all times — including the final step — and fills in (animated) as each choice is made.

## Accessibility — REQUIRED

Wrap any non-essential motion with `useReducedMotion()`:

```tsx
import { motion, useReducedMotion } from "motion/react";

function HeroReveal({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 20 }}
      animate={reduce ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
    >
      {children}
    </motion.div>
  );
}
```

When `prefers-reduced-motion: reduce` is set in the OS, the user sees content immediately with no animation. This is not optional — required for WCAG 2.3.3.

## Performance rules

1. **Animate `transform` and `opacity` only** when possible. Avoid animating `width`, `height`, `top`, `left` — they trigger layout reflows.
2. **`viewport={{ once: true }}`** on scroll reveals so they don't re-trigger on scroll back up.
3. **Use `layoutId` sparingly** — powerful but expensive at scale.
4. **Keep animation durations < 1 second.** Anything longer feels sluggish.
5. **Stagger delays < 0.15s.** Beyond that, the sequence feels labored.

## Reusable wrappers — `components/motion/`

Build small reusable wrappers rather than reimplementing the same motion in every section.

### `components/motion/FadeIn.tsx`

```tsx
import { motion, useReducedMotion } from "motion/react";
import { type ReactNode } from "react";

export function FadeIn({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 20 }}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
```

### `components/motion/StaggerContainer.tsx`

```tsx
import { motion } from "motion/react";
import { type ReactNode } from "react";

export function StaggerContainer({
  children,
  className,
  stagger = 0.1,
}: {
  children: ReactNode;
  className?: string;
  stagger?: number;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-50px" }}
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: stagger } },
      }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 20 },
        show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
      }}
    >
      {children}
    </motion.div>
  );
}
```

Section components then import these wrappers and stay clean of motion logic.

## Hard constraint reminder

If you find yourself typing `framer-motion`, STOP. The correct import is `motion/react`. Run this grep before declaring done:

```powershell
Select-String -Path .\**\*.ts,.\**\*.tsx -Pattern "framer-motion" -SimpleMatch
```

Must return zero matches.
