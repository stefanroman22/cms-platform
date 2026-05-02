/**
 * Shared Tailwind class strings.
 * Import these constants instead of copying class lists across components.
 */

// ── Public site ───────────────────────────────────────────────────────────────

/** Nav link — interaction styles only; add layout padding (px-*, py-*) per context */
export const navLinkCn =
  "text-sm font-medium text-zinc-400 transition-colors duration-200 hover:text-white";

/** CTA button — inverted white pill; intrinsic size, never stretches */
export const ctaButtonCn =
  "inline-flex shrink-0 items-center justify-center rounded-full bg-white px-4 py-1.5 text-sm font-medium text-black transition-colors duration-200 hover:bg-zinc-200 cursor-pointer";

/** Small uppercase section label (e.g., "Contact") */
export const sectionLabelCn = "text-xs font-semibold uppercase tracking-widest text-zinc-600";

/** Hairline horizontal rule */
export const dividerCn = "h-px bg-white/[0.08]";

// ── Dashboard ─────────────────────────────────────────────────────────────────

/** Primary action button — dark fill, disabled state included */
export const dashboardPrimaryBtnCn =
  "flex items-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer dark:bg-zinc-700 dark:hover:bg-zinc-600";

/** Text input / select / textarea — standard (py-2) */
export const dashboardInputCn =
  "w-full rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-400 focus:bg-white focus:outline-none transition-colors dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:placeholder:text-zinc-500 dark:focus:border-zinc-500 dark:focus:bg-zinc-800";

/** Text input / select / textarea — tall variant (py-2.5) used in new-project form */
export const dashboardInputLgCn =
  "w-full rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-400 focus:bg-white focus:outline-none transition-colors dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:placeholder:text-zinc-500 dark:focus:border-zinc-500 dark:focus:bg-zinc-800";

/** Form field label */
export const dashboardFieldLabelCn =
  "block text-xs font-medium text-zinc-500 mb-1.5 dark:text-zinc-400";

/** Section card — white rounded card with border */
export const dashboardSectionCardCn =
  "rounded-xl border border-zinc-200 bg-white overflow-hidden dark:border-zinc-800 dark:bg-zinc-900";

/** Error feedback banner */
export const dashboardErrorBannerCn =
  "rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-400";

/** Success feedback banner */
export const dashboardSuccessBannerCn =
  "flex items-center gap-2 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400";
