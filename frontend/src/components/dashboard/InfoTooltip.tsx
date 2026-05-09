"use client";

import { Info } from "lucide-react";

interface InfoTooltipProps {
  hint: string;
  className?: string;
  /**
   * Horizontal alignment of the tooltip relative to the icon.
   * - "start"  (default) — left edge of tooltip aligns with the icon, extends RIGHT.
   *   Best when the icon sits near the left edge of the viewport / parent (the
   *   common "label + ⓘ" layout); won't clip on small screens.
   * - "center" — centred on the icon. Risky on narrow viewports — half the
   *   tooltip can overflow the parent or the window.
   * - "end"    — right edge of tooltip aligns with the icon, extends LEFT.
   *   Use when the icon is at the far right of a row.
   */
  align?: "center" | "start" | "end";
  /**
   * Which direction the tooltip opens.
   * - "up" (default) — opens above the icon
   * - "down" — opens below the icon; use inside cards with overflow-hidden where upward is clipped
   */
  direction?: "up" | "down";
  /**
   * Wider tooltip (w-72 instead of w-56) so longer hints don't wrap as much.
   * Width is also clamped to the viewport so phones never see overflow.
   */
  wide?: boolean;
}

// Width is `min(target, calc(100vw - 1.5rem))` so on a 320 px screen the
// tooltip becomes ~ 296 px instead of overflowing at its declared 288 px.
// `1.5rem` accounts for ~12 px of breathing room on each edge.
const widthClasses = {
  default: "w-[min(theme(spacing.56),calc(100vw-1.5rem))]",
  wide: "w-[min(theme(spacing.72),calc(100vw-1.5rem))]",
} as const;

const alignClasses = {
  center: "left-1/2 -translate-x-1/2",
  start: "left-0 translate-x-0",
  end: "right-0 translate-x-0",
} as const;

const arrowAlignClasses = {
  center: "left-1/2 -translate-x-1/2",
  start: "left-3",
  end: "right-3",
} as const;

/**
 * A small ⓘ icon that shows a tooltip on hover.
 * Place inline next to a field label for formatting hints.
 *
 * Default alignment is `"start"` (left-anchored) because most uses sit
 * next to a left-aligned label; centring would clip the tooltip on
 * narrow viewports. Pass `align="end"` if the icon is on the far
 * right of its row.
 */
export function InfoTooltip({
  hint,
  className = "",
  align = "start",
  direction = "up",
  wide = false,
}: InfoTooltipProps) {
  const isUp = direction === "up";

  return (
    <span className={`relative inline-flex items-center group ${className}`}>
      <Info className="h-3.5 w-3.5 text-zinc-400 dark:text-zinc-500 cursor-help" />
      {/* Tooltip panel */}
      <span
        role="tooltip"
        className={`
                    pointer-events-none absolute z-50
                    ${isUp ? "bottom-full mb-1.5" : "top-full mt-1.5"}
                    ${wide ? widthClasses.wide : widthClasses.default}
                    max-w-[calc(100vw-1.5rem)]
                    rounded-lg border border-zinc-200
                    bg-white px-3 py-2 text-xs leading-relaxed text-zinc-600
                    shadow-md
                    opacity-0 scale-95
                    transition-all duration-150
                    group-hover:opacity-100 group-hover:scale-100
                    dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300
                    ${alignClasses[align]}
                `}
      >
        {hint}
        {/* Arrow — points toward the icon */}
        {isUp ? (
          <span
            className={`absolute top-full border-4 border-transparent border-t-white dark:border-t-zinc-900 ${arrowAlignClasses[align]}`}
          />
        ) : (
          <span
            className={`absolute bottom-full border-4 border-transparent border-b-white dark:border-b-zinc-900 ${arrowAlignClasses[align]}`}
          />
        )}
      </span>
    </span>
  );
}
