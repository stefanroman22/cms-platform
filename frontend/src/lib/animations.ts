import type { Variants } from "framer-motion";

// ── Primitives ────────────────────────────────────────────────────────────────

/** Header entrance — bar drops in from above */
export const fadeDown: Variants = {
  hidden: { opacity: 0, y: -16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: "easeOut" } },
};

/** Section entrance — content rises into view (footer, cards, etc.) */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: "easeOut" } },
};

/** Generic child fade-in — used inside any stagger container */
export const fadeIn: Variants = {
  hidden: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

// ── Stagger containers ────────────────────────────────────────────────────────

/** Standard stagger — desktop nav, footer sections */
export const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.09, delayChildren: 0.3 } },
};

/** Fast stagger — compact lists such as the mobile drawer */
export const staggerFast: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06, delayChildren: 0.12 } },
};

// ── Overlay / Drawer ──────────────────────────────────────────────────────────

/** Right-edge drawer — slides in from off-screen right */
export const drawerRight: Variants = {
  hidden: { x: "100%" },
  visible: { x: 0, transition: { duration: 0.35, ease: "circOut" } },
  exit: { x: "100%", transition: { duration: 0.25, ease: "easeIn" } },
};

/** Translucent backdrop that dims the content behind a drawer */
export const backdrop: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.2 } },
  exit: { opacity: 0, transition: { duration: 0.2 } },
};

// ── Slide-in factory ──────────────────────────────────────────────────────────

export type SlideDirection = "left" | "right" | "top" | "bottom";

export interface SlideInOptions {
  /** Direction the element slides in from. @default "bottom" */
  direction?: SlideDirection;
  /** How far (px) the element starts from its resting position. @default 40 */
  offset?: number;
  /** Seconds before the animation begins. @default 0 */
  delay?: number;
  /** Animation duration in seconds. @default 0.45 */
  duration?: number;
}

/**
 * Factory that returns a `Variants` object animating a div into view
 * from any edge, with configurable offset, delay, and duration.
 *
 * @example
 * // Slide in from the left after 0.2 s
 * const variants = createSlideIn({ direction: "left", delay: 0.2 });
 *
 * <motion.div variants={variants} initial="hidden" animate="visible" />
 */
export function createSlideIn({
  direction = "bottom",
  offset = 40,
  delay = 0,
  duration = 0.45,
}: SlideInOptions = {}): Variants {
  const axis = direction === "left" || direction === "right" ? "x" : "y";
  const sign = direction === "right" || direction === "bottom" ? 1 : -1;

  const hiddenTranslate = { [axis]: sign * offset };
  const visibleTranslate = { [axis]: 0 };

  return {
    hidden: {
      opacity: 0,
      ...hiddenTranslate,
    },
    visible: {
      opacity: 1,
      ...visibleTranslate,
      transition: {
        duration,
        delay,
        ease: "easeOut",
      },
    },
    exit: {
      opacity: 0,
      ...hiddenTranslate,
      transition: {
        duration: duration * 0.6,
        ease: "easeIn",
      },
    },
  };
}