"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BookingStatsByDay, BookingStatsByService, BookingStatsByStatus } from "./api";

// ── Shared tooltip style ──────────────────────────────────────────────────────

const TOOLTIP_STYLE = {
  backgroundColor: "rgb(24 24 27)",
  border: "1px solid rgb(63 63 70)",
  borderRadius: 8,
} as const;

/**
 * Custom tooltip — recharts colours each Pie item's text with the slice fill
 * (dark-on-dark for e.g. "cancelled"), and `itemStyle` doesn't override it. A
 * custom content guarantees the label + values stay light on the dark popover.
 */
interface TooltipEntry {
  name?: string | number;
  value?: string | number;
  color?: string;
}
function DarkTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div style={TOOLTIP_STYLE} className="px-2.5 py-1.5 text-xs">
      {label !== undefined && label !== "" && (
        <p className="mb-0.5 capitalize text-zinc-400">{label}</p>
      )}
      {payload.map((p, i) => (
        <p key={i} className="flex items-center gap-1.5 capitalize text-zinc-100">
          {p.color && (
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: p.color }}
              aria-hidden="true"
            />
          )}
          <span>{p.name}</span>
          <span className="ml-1 tabular-nums">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

// ── Motion card wrapper ───────────────────────────────────────────────────────

function ChartCard({
  title,
  headerRight,
  children,
}: {
  title: string;
  headerRight?: ReactNode;
  children: React.ReactNode;
}) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
          {title}
        </h3>
        {headerRight}
      </div>
      {children}
    </motion.div>
  );
}

function EmptyState({ label = "No data yet." }: { label?: string }) {
  return <div className="py-12 text-center text-sm text-zinc-400 dark:text-zinc-500">{label}</div>;
}

// ── Bookings over time (AreaChart) — the "Trend" view ─────────────────────────

interface BookingsOverTimeProps {
  data: BookingStatsByDay[];
}

export function BookingsOverTimeChart({ data }: BookingsOverTimeProps) {
  return (
    <ChartCard title="Bookings over time">
      {data.length === 0 ? (
        <EmptyState label="No bookings in this period yet." />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="bookingGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              stroke="currentColor"
              className="text-zinc-500"
              tickFormatter={(v: string) => {
                const d = new Date(v);
                return `${d.getMonth() + 1}/${d.getDate()}`;
              }}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fontSize: 11 }}
              stroke="currentColor"
              className="text-zinc-500"
            />
            <Tooltip content={<DarkTooltip />} />
            <Area
              type="monotone"
              dataKey="count"
              name="Bookings"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#bookingGradient)"
              dot={false}
              activeDot={{ r: 5 }}
              animationDuration={800}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
}

// ── Shared palettes ───────────────────────────────────────────────────────────

const SERVICE_PALETTE = [
  "#10b981",
  "#3b82f6",
  "#8b5cf6",
  "#f59e0b",
  "#ef4444",
  "#06b6d4",
  "#84cc16",
];

const STATUS_COLOR: Record<string, string> = {
  confirmed: "#10b981", // emerald
  pending: "#f59e0b", // amber
  cancelled: "#71717a", // zinc
  completed: "#3b82f6", // blue
  no_show: "#ef4444", // red
};

function statusColor(s: string): string {
  return STATUS_COLOR[s] ?? "#a1a1aa";
}

// ── Breakdown: service + status in ONE container, colour-coded labels ─────────
//
// Both halves use the same visual language — a coloured dot + label text tinted to
// match its data colour — so "Consultation" (service) and its statuses read as one
// system. Replaces the two separate service/status cards.

function ServiceBreakdown({ data }: { data: BookingStatsByService[] }) {
  const reduced = useReducedMotion();
  const top = data.slice(0, 7);
  const max = Math.max(1, ...top.map((d) => d.count));
  return (
    <ul className="space-y-2.5">
      {top.map((row, i) => {
        const color = SERVICE_PALETTE[i % SERVICE_PALETTE.length];
        const pct = (row.count / max) * 100;
        return (
          <li key={row.service}>
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="flex min-w-0 items-center gap-1.5 font-medium" style={{ color }}>
                <span
                  className="inline-block h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: color }}
                  aria-hidden="true"
                />
                <span className="truncate">{row.service}</span>
              </span>
              <span className="shrink-0 tabular-nums text-zinc-500 dark:text-zinc-400">
                {row.count}
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: color }}
                initial={reduced ? false : { width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{
                  duration: reduced ? 0 : 0.55,
                  delay: reduced ? 0 : i * 0.05,
                  ease: [0.16, 1, 0.3, 1],
                }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function StatusBreakdown({ data }: { data: BookingStatsByStatus[] }) {
  return (
    <div>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="status"
            cx="50%"
            cy="50%"
            innerRadius="58%"
            outerRadius="80%"
            paddingAngle={3}
            animationDuration={800}
          >
            {data.map((row, i) => (
              <Cell key={i} fill={statusColor(row.status)} />
            ))}
          </Pie>
          <Tooltip content={<DarkTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      <ul className="mt-3 space-y-1.5">
        {data.map((row) => {
          const color = statusColor(row.status);
          return (
            <li
              key={row.status}
              className="flex items-center justify-between gap-2 text-xs font-medium"
            >
              {/* Dot carries the colour; the label stays high-contrast (readable
                  on the dark surface) rather than tinted to the status colour. */}
              <span className="flex items-center gap-1.5 capitalize text-zinc-700 dark:text-zinc-200">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: color }}
                  aria-hidden="true"
                />
                {row.status.replace("_", " ")}
              </span>
              <span className="tabular-nums text-zinc-500 dark:text-zinc-400">{row.count}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface BreakdownProps {
  byService: BookingStatsByService[];
  byStatus: BookingStatsByStatus[];
  /** Optional control rendered in the card header (e.g. a time-range filter). */
  headerRight?: ReactNode;
  /** When provided, the body crossfades whenever this key changes (range switch). */
  animateKey?: string | number;
}

export function BookingBreakdown({ byService, byStatus, headerRight, animateKey }: BreakdownProps) {
  const reduced = useReducedMotion();
  const hasService = byService.length > 0;
  const hasStatus = byStatus.length > 0;
  return (
    <ChartCard title="Breakdown" headerRight={headerRight}>
      {!hasService && !hasStatus ? (
        <EmptyState />
      ) : (
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={animateKey ?? "static"}
            initial={reduced ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? undefined : { opacity: 0, y: -6 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="grid gap-x-8 gap-y-6 sm:grid-cols-2"
          >
            <section>
              <h4 className="mb-3 text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                By service
              </h4>
              {hasService ? <ServiceBreakdown data={byService} /> : <EmptyState />}
            </section>
            <section>
              <h4 className="mb-3 text-xs font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                By status
              </h4>
              {hasStatus ? <StatusBreakdown data={byStatus} /> : <EmptyState />}
            </section>
          </motion.div>
        </AnimatePresence>
      )}
    </ChartCard>
  );
}
