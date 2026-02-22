/**
 * Shared Tailwind class strings.
 * Import these constants instead of copying class lists across components.
 */

/** Nav link — interaction styles only; add layout padding (px-*, py-*) per context */
export const navLinkCn =
  "text-sm font-medium text-zinc-400 transition-colors duration-200 hover:text-white";

/** CTA button — inverted white pill; intrinsic size, never stretches */
export const ctaButtonCn =
  "inline-flex shrink-0 items-center justify-center rounded-full bg-white px-4 py-1.5 text-sm font-medium text-black transition-colors duration-200 hover:bg-zinc-200";

/** Small uppercase section label (e.g., "Contact") */
export const sectionLabelCn =
  "text-xs font-semibold uppercase tracking-widest text-zinc-600";

/** Hairline horizontal rule */
export const dividerCn = "h-px bg-white/[0.08]";
