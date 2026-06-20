"use client";

import { useMemo, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { dashAccent } from "@/lib/dashboardTheme";
import { dateKey, MONTH_LABELS } from "@/lib/bookingDates";
import { getStats } from "../api";
import type { BookingStats } from "../api";
import { BookingBreakdown } from "../OverviewCharts";

type Range = "day" | "week" | "month" | "year" | "all";

const RANGES: { id: Range; label: string }[] = [
  { id: "day", label: "Day" },
  { id: "week", label: "Week" },
  { id: "month", label: "Month" },
  { id: "year", label: "Year" },
  { id: "all", label: "All time" },
];

/** Mon-first start of the week containing `d`. */
function startOfWeek(d: Date): Date {
  const out = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  out.setDate(out.getDate() - ((out.getDay() + 6) % 7));
  return out;
}

interface Period {
  from?: string;
  to?: string;
  label: string;
}

/** Calendar-aligned period for `range`, shifted by `cursor` periods from now. */
function periodFor(range: Range, cursor: number): Period {
  const now = new Date();
  if (range === "all") return { label: "All time" };

  if (range === "day") {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + cursor);
    return {
      from: dateKey(d),
      to: dateKey(d),
      label: new Intl.DateTimeFormat("en-GB", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      }).format(d),
    };
  }
  if (range === "week") {
    const start = startOfWeek(now);
    start.setDate(start.getDate() + cursor * 7);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    const fmt = (x: Date) =>
      new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(x);
    return {
      from: dateKey(start),
      to: dateKey(end),
      label: `${fmt(start)} – ${fmt(end)} ${end.getFullYear()}`,
    };
  }
  if (range === "month") {
    const start = new Date(now.getFullYear(), now.getMonth() + cursor, 1);
    const end = new Date(start.getFullYear(), start.getMonth() + 1, 0);
    return {
      from: dateKey(start),
      to: dateKey(end),
      label: `${MONTH_LABELS[start.getMonth()]} ${start.getFullYear()}`,
    };
  }
  // year
  const y = now.getFullYear() + cursor;
  return { from: `${y}-01-01`, to: `${y}-12-31`, label: String(y) };
}

interface Props {
  projectSlug: string;
  /** undefined = all staff; otherwise a single staff resource_id. */
  resourceId?: string;
  /** All-time stats already loaded by the panel — used for the "All time" range. */
  fallback: BookingStats;
}

/**
 * The "Breakdown" stat view with a time-range filter (day / week / month / year /
 * all time) PLUS period navigation. The range + cursor are ephemeral — by request
 * neither is persisted. Day → step days, Week → weeks, Month → months, Year →
 * years. Switching range re-queries the calendar-aligned period and crossfades.
 */
export function RangedBreakdown({ projectSlug, resourceId, fallback }: Props) {
  const reduced = useReducedMotion();
  const [range, setRange] = useState<Range>("all");
  const [cursor, setCursor] = useState(0);

  const period = useMemo(() => periodFor(range, cursor), [range, cursor]);
  const scopeKey = resourceId ?? "all";

  // "All time" reuses the panel's already-loaded stats (no extra request).
  const { data } = useQuery(
    `booking-stats-range:${projectSlug}:${scopeKey}:${range}:${cursor}`,
    () => getStats(projectSlug, period.from, period.to, resourceId),
    { ttl: 60 * 1000, enabled: range !== "all" }
  );

  const stats = range === "all" ? fallback : (data ?? fallback);

  function changeRange(next: Range) {
    setRange(next);
    setCursor(0); // jump back to the current period when switching granularity
  }

  const filter = (
    <div className="flex flex-col items-end gap-2">
      <div
        role="group"
        aria-label="Breakdown time range"
        className="no-scrollbar inline-flex max-w-full items-center gap-0.5 overflow-x-auto rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 dark:border-zinc-700 dark:bg-zinc-800/50"
      >
        {RANGES.map((r) => {
          const active = r.id === range;
          return (
            <button
              key={r.id}
              type="button"
              aria-pressed={active}
              onClick={() => changeRange(r.id)}
              className={`relative shrink-0 cursor-pointer rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${dashAccent.focusRing} ${
                active
                  ? "text-zinc-900 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
              }`}
            >
              {active && (
                <motion.span
                  layoutId="breakdown-range-pill"
                  className="absolute inset-0 rounded-md bg-white shadow-sm dark:bg-zinc-700"
                  transition={
                    reduced
                      ? { duration: 0 }
                      : { type: "spring", stiffness: 480, damping: 36, mass: 0.6 }
                  }
                />
              )}
              <span className="relative z-10">{r.label}</span>
            </button>
          );
        })}
      </div>

      {/* Period navigator (hidden for "All time") */}
      {range !== "all" && (
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setCursor((c) => c - 1)}
            aria-label="Previous period"
            className={`rounded-md border border-zinc-200 p-1 text-zinc-500 transition-colors hover:border-accent/50 hover:text-accent dark:border-zinc-700 dark:text-zinc-400 ${dashAccent.focusRing}`}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <span className="min-w-[8.5rem] text-center text-xs font-medium tabular-nums text-zinc-600 dark:text-zinc-300">
            {period.label}
          </span>
          <button
            type="button"
            onClick={() => setCursor((c) => c + 1)}
            aria-label="Next period"
            className={`rounded-md border border-zinc-200 p-1 text-zinc-500 transition-colors hover:border-accent/50 hover:text-accent dark:border-zinc-700 dark:text-zinc-400 ${dashAccent.focusRing}`}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
          {cursor !== 0 && (
            <button
              type="button"
              onClick={() => setCursor(0)}
              className="ml-1 cursor-pointer text-xs font-medium text-accent hover:underline"
            >
              Today
            </button>
          )}
        </div>
      )}
    </div>
  );

  return (
    <BookingBreakdown
      byService={stats.by_service}
      byStatus={stats.by_status}
      headerRight={filter}
      animateKey={`${scopeKey}:${range}:${cursor}`}
    />
  );
}
