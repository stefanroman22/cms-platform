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
