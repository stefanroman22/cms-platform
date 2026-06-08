"use client";

import { m } from "motion/react";
import { cn } from "@/lib/utils";

export type ToggleOption<T extends string> = { value: T; label: string };

/**
 * Pill segmented toggle with a sliding accent indicator (shared `layoutId`).
 * Requires an ancestor `LazyMotion` with `domMax` features for the layout
 * animation. Centre it via a `flex justify-center` parent, or leave it inline
 * for left alignment. Used by the pricing section and the contact channel.
 */
export function SegmentedToggle<T extends string>({
  value,
  onChange,
  options,
  layoutId,
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: ToggleOption<T>[];
  layoutId: string;
  className?: string;
}) {
  return (
    <div
      className={cn("flex w-fit rounded-full border border-border bg-surface/60 p-1", className)}
    >
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className="relative rounded-full px-5 py-1.5 text-sm font-medium"
          >
            <span
              className={cn(
                "relative z-10 transition-colors duration-200",
                active ? "text-bg" : "text-text-secondary hover:text-text-primary"
              )}
            >
              {opt.label}
            </span>
            {active && (
              <m.span
                layoutId={layoutId}
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
                className="absolute inset-0 z-0 rounded-full bg-accent"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
