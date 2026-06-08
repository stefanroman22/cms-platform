"use client";

import {
  CalendarCheck2,
  CalendarClock,
  CalendarDays,
  Clock,
  TrendingDown,
  XCircle,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { dashboardSectionCardCn } from "@/lib/styles";
import { dashAccent } from "@/lib/dashboardTheme";
import type { BookingAppointment, BookingResource, BookingService, BookingStats } from "../api";
import { BookingsOverTimeChart, BookingBreakdown } from "../OverviewCharts";
import { ByStaffWidgets } from "./ByStaffWidgets";

// ── Public types ──────────────────────────────────────────────────────────────

export interface OverviewWidgetCtx {
  stats: BookingStats;
  /** Already scope-filtered by the panel. */
  appointments: BookingAppointment[];
  services: BookingService[];
  /** Active staff-type resources. */
  staff: BookingResource[];
  /** "all" | resource_id */
  scope: string;
  timezone: string | null;
  onSelectAppointment: (a: BookingAppointment) => void;
}

/**
 * A single selectable statistics view. The calendar is NOT a stat view — it is
 * always rendered above the filter. Add a view by appending one entry; no changes
 * to the panel shell. `available` hides a view when its data isn't meaningful
 * (e.g. by-staff with a single staff member).
 */
export interface StatView {
  id: string;
  title: string;
  available?: (ctx: OverviewWidgetCtx) => boolean;
  render: (ctx: OverviewWidgetCtx) => React.ReactNode;
}

// ── KPI group (the "overview" view) ────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  /** danger highlight (e.g. high cancellation) */
  danger?: boolean;
  /** gold highlight for the single key metric */
  highlight?: boolean;
}

function KpiCard({ label, value, icon, danger, highlight }: KpiCardProps) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={`${dashboardSectionCardCn} flex items-center gap-3 px-4 py-4`}
    >
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
          danger
            ? "bg-red-50 text-red-600 dark:bg-red-950 dark:text-red-400"
            : highlight
              ? "bg-accent/15 text-accent"
              : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"
        }`}
      >
        {icon}
      </span>
      <div className="min-w-0">
        <p
          className={`text-xl font-bold tabular-nums ${
            highlight ? dashAccent.kpiHighlight : "text-zinc-900 dark:text-zinc-50"
          }`}
        >
          {value}
        </p>
        <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">{label}</p>
      </div>
    </motion.div>
  );
}

export function KpiGroup({ stats }: { stats: BookingStats }) {
  const { kpis, cancellation_rate, no_show_rate } = stats;
  // One responsive grid — Upcoming is the single gold-highlighted metric an owner
  // glances at most; the rest stay neutral zinc, danger states go red.
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
      <KpiCard
        label="Upcoming"
        value={kpis.upcoming}
        icon={<CalendarClock className="h-4 w-4" />}
        highlight
      />
      <KpiCard label="Total" value={kpis.total} icon={<CalendarDays className="h-4 w-4" />} />
      <KpiCard label="Today" value={kpis.today} icon={<CalendarCheck2 className="h-4 w-4" />} />
      <KpiCard
        label="This week"
        value={kpis.this_week}
        icon={<CalendarDays className="h-4 w-4" />}
      />
      <KpiCard label="Avg / day" value={kpis.avg_per_day} icon={<Clock className="h-4 w-4" />} />
      <KpiCard
        label="Cancellation"
        value={`${cancellation_rate}%`}
        icon={<XCircle className="h-4 w-4" />}
        danger={cancellation_rate > 20}
      />
      <KpiCard
        label="No-show"
        value={`${no_show_rate}%`}
        icon={<TrendingDown className="h-4 w-4" />}
        danger={no_show_rate > 15}
      />
    </div>
  );
}

// ── Stat-view registry ─────────────────────────────────────────────────────────
//
// Append one entry to add a view. The first entry is the default-on view (kept in
// sync with DEFAULT_STAT_VIEW in prefsStore.ts; the registry test pins this).

export const STAT_VIEWS: StatView[] = [
  {
    id: "overview",
    title: "Overview",
    render: (ctx) => <KpiGroup stats={ctx.stats} />,
  },
  {
    id: "breakdown",
    title: "Breakdown",
    render: (ctx) => (
      <BookingBreakdown byService={ctx.stats.by_service} byStatus={ctx.stats.by_status} />
    ),
  },
  {
    id: "trend",
    title: "Trend",
    render: (ctx) => <BookingsOverTimeChart data={ctx.stats.by_day} />,
  },
  {
    id: "byStaff",
    title: "By staff",
    // Only meaningful with 2+ staff.
    available: (ctx) => ctx.staff.length > 1,
    render: (ctx) => <ByStaffWidgets data={ctx.stats.by_staff} />,
  },
];

export const STAT_VIEWS_BY_ID: Record<string, StatView> = Object.fromEntries(
  STAT_VIEWS.map((v) => [v.id, v])
);
