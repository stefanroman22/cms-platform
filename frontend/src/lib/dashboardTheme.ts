// Sparing, high-impact gold accent primitives for the dashboard.
// The zinc base stays dominant; accent only on active states / key CTAs / one or two highlights.
export const dashAccent = {
  /** focus-visible ring for interactive controls */
  focusRing: "outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
  /** active tab / nav underline (use as the motion.span bg) */
  tabUnderline: "bg-accent",
  /** primary call-to-action button */
  ctaPrimary: "bg-accent text-bg hover:bg-accent-muted disabled:opacity-50 transition-colors",
  /** emphasise a single key metric */
  kpiHighlight: "text-accent",
  /** calendar 'today' marker ring */
  todayMarker: "ring-1 ring-accent text-accent",
} as const;
