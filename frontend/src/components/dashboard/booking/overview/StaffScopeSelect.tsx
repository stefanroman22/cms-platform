"use client";

import { Users } from "lucide-react";
import { dashAccent } from "@/lib/dashboardTheme";
import type { BookingResource } from "../api";

interface Props {
  /** Active staff-type resources to scope by. */
  staff: BookingResource[];
  /** "all" or a resource_id. */
  value: string;
  onChange: (scope: string) => void;
}

/**
 * "All staff | <person>" scope switcher rendered as a segmented pill row so the
 * whole Overview (calendar + every stat) can be retargeted to one person in a single
 * tap. Horizontally scrollable (scrollbar hidden) so it stays usable on mobile and
 * with many staff. The selection is persisted by the panel. Hidden by the panel when
 * fewer than two staff exist.
 */
export function StaffScopeSelect({ staff, value, onChange }: Props) {
  const options = [
    { id: "all", name: "All staff" },
    ...staff.map((s) => ({ id: s.id, name: s.name })),
  ];

  return (
    <div
      role="group"
      aria-label="Staff scope"
      className="no-scrollbar flex max-w-full items-center gap-1 overflow-x-auto rounded-xl border border-zinc-200 bg-zinc-50 p-1 dark:border-zinc-700 dark:bg-zinc-800/50"
    >
      <Users
        className="ml-1 mr-0.5 h-4 w-4 shrink-0 text-zinc-400 dark:text-zinc-500"
        aria-hidden="true"
      />
      {options.map((opt) => {
        const active = value === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(opt.id)}
            className={`shrink-0 cursor-pointer whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${dashAccent.focusRing} ${
              active
                ? "bg-white text-accent shadow-sm dark:bg-zinc-700"
                : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            {opt.name}
          </button>
        );
      })}
    </div>
  );
}
