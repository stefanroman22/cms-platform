"use client";

import { motion, useReducedMotion } from "motion/react";
import { dashAccent } from "@/lib/dashboardTheme";

export interface StatViewOption {
  id: string;
  title: string;
}

interface Props {
  views: StatViewOption[];
  value: string;
  onChange: (id: string) => void;
}

/**
 * Single-select segmented filter for the statistics panel. Replaces the old
 * checkbox "Customize" drawer: instead of toggling many cards on at once, the owner
 * picks ONE statistic to look at, keeping the Overview calm and uncrowded. The active
 * pill is marked with a shared gold underline (spring) for a clear, on-brand state.
 */
export function StatViewFilter({ views, value, onChange }: Props) {
  const reduced = useReducedMotion();
  return (
    <div
      role="group"
      aria-label="Statistics view"
      className="no-scrollbar flex items-center gap-1 overflow-x-auto"
    >
      {views.map((v) => {
        const active = v.id === value;
        return (
          <button
            key={v.id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(v.id)}
            className={`relative shrink-0 cursor-pointer whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${dashAccent.focusRing} ${
              active
                ? "text-accent"
                : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            {v.title}
            {active && (
              <motion.span
                layoutId="stat-view-underline"
                className={`absolute inset-x-2 -bottom-px h-[2px] rounded-full ${dashAccent.tabUnderline}`}
                transition={
                  reduced
                    ? { duration: 0 }
                    : { type: "spring", stiffness: 480, damping: 36, mass: 0.6 }
                }
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
