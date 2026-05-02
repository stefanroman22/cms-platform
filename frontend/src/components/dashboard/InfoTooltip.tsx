"use client";

import { Info } from "lucide-react";

interface InfoTooltipProps {
  hint: string;
  className?: string;
  /**
   * Horizontal alignment of the tooltip relative to the icon.
   * - "center" (default) — centered on the icon
   * - "start"  — left-aligns with the icon; use when icon is near the left edge
   * - "end"    — right-aligns with the icon; use when icon is near the right edge
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
   */
  wide?: boolean;
}

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
 */
export function InfoTooltip({
  hint,
  className = "",
  align = "center",
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
                    ${wide ? "w-72" : "w-56"}
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
