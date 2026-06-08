"use client";

import { motion, useReducedMotion } from "motion/react";
import {
  CalendarCheck2,
  CalendarClock,
  CalendarDays,
  Clock,
  TrendingDown,
  XCircle,
} from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import { dashboardSectionCardCn } from "@/lib/styles";
import { getStats } from "./api";
import {
  BookingsOverTimeChart,
  ByServiceChart,
  ByStatusChart,
  PeakTimesHeatmap,
} from "./OverviewCharts";

interface Props {
  projectSlug: string;
}

// ── KPI card ──────────────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  accent?: boolean;
}

function KpiCard({ label, value, icon, accent }: KpiCardProps) {
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
          accent
            ? "bg-red-50 text-red-600 dark:bg-red-950 dark:text-red-400"
            : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"
        }`}
      >
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-xl font-bold text-zinc-900 dark:text-zinc-50 tabular-nums">{value}</p>
        <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">{label}</p>
      </div>
    </motion.div>
  );
}

// ── OverviewPanel ─────────────────────────────────────────────────────────────

export function OverviewPanel({ projectSlug }: Props) {
  const { data, loading, error } = useQuery(
    `booking-stats:${projectSlug}`,
    () => getStats(projectSlug),
    { ttl: 2 * 60 * 1000 }
  );

  if (loading) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
        <ArcSpinner size={20} />
        Loading overview…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400">
        Failed to load stats: {error}
      </div>
    );
  }

  if (!data) return null;

  const { kpis, cancellation_rate, no_show_rate, by_day, by_service, by_status, heatmap } = data;

  // Empty state
  if (kpis.total === 0) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-zinc-200 bg-white px-6 py-16 text-center dark:border-zinc-800 dark:bg-zinc-900">
        <CalendarCheck2 className="h-8 w-8 text-zinc-300 dark:text-zinc-600" aria-hidden="true" />
        <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">No bookings yet</p>
        <p className="max-w-xs text-xs text-zinc-400 dark:text-zinc-500">
          Once bookings come in, you&apos;ll see stats, trends, and peak-time charts right here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <KpiCard label="Total" value={kpis.total} icon={<CalendarDays className="h-4 w-4" />} />
        <KpiCard
          label="Upcoming"
          value={kpis.upcoming}
          icon={<CalendarClock className="h-4 w-4" />}
        />
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
          accent={cancellation_rate > 20}
        />
      </div>

      {/* No-show rate — separate card so the grid isn't too wide on small screens */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <KpiCard
          label="No-show"
          value={`${no_show_rate}%`}
          icon={<TrendingDown className="h-4 w-4" />}
          accent={no_show_rate > 15}
        />
      </div>

      {/* Charts row 1 */}
      <BookingsOverTimeChart data={by_day} />

      {/* Charts row 2: by service + by status side-by-side on wider screens */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ByServiceChart data={by_service} />
        <ByStatusChart data={by_status} />
      </div>

      {/* Peak times heatmap */}
      <PeakTimesHeatmap data={heatmap} />
    </div>
  );
}
