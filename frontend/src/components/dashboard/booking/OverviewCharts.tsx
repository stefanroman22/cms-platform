"use client";

import { motion, useReducedMotion } from "motion/react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  BookingStatsByDay,
  BookingStatsByService,
  BookingStatsByStatus,
  BookingStatsHeatmapCell,
} from "./api";

// ── Shared tooltip style ──────────────────────────────────────────────────────

const TOOLTIP_STYLE = {
  backgroundColor: "rgb(24 24 27)",
  border: "1px solid rgb(63 63 70)",
  borderRadius: 8,
} as const;

const TOOLTIP_LABEL_STYLE = { color: "rgb(212 212 216)" } as const;

// ── Motion card wrapper ───────────────────────────────────────────────────────

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
    >
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
        {title}
      </h3>
      {children}
    </motion.div>
  );
}

// ── Bookings over time (AreaChart) ────────────────────────────────────────────

interface BookingsOverTimeProps {
  data: BookingStatsByDay[];
}

export function BookingsOverTimeChart({ data }: BookingsOverTimeProps) {
  return (
    <ChartCard title="Bookings over time">
      {data.length === 0 ? (
        <div className="py-12 text-center text-sm text-zinc-400 dark:text-zinc-500">
          No bookings in this period yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
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
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} />
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

// ── By service (BarChart, horizontal) ────────────────────────────────────────

const SERVICE_PALETTE = [
  "#10b981",
  "#3b82f6",
  "#8b5cf6",
  "#f59e0b",
  "#ef4444",
  "#06b6d4",
  "#84cc16",
];

interface ByServiceProps {
  data: BookingStatsByService[];
}

export function ByServiceChart({ data }: ByServiceProps) {
  const top = data.slice(0, 7);
  return (
    <ChartCard title="By service">
      {top.length === 0 ? (
        <div className="py-12 text-center text-sm text-zinc-400 dark:text-zinc-500">
          No data yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(180, top.length * 38)}>
          <BarChart data={top} layout="vertical" margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fontSize: 11 }}
              stroke="currentColor"
              className="text-zinc-500"
            />
            <YAxis
              type="category"
              dataKey="service"
              tick={{ fontSize: 11 }}
              width={110}
              stroke="currentColor"
              className="text-zinc-500"
            />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} />
            <Bar dataKey="count" name="Bookings" animationDuration={800}>
              {top.map((_, i) => (
                <Cell key={i} fill={SERVICE_PALETTE[i % SERVICE_PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
}

// ── By status (PieChart / donut) ──────────────────────────────────────────────

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

interface ByStatusProps {
  data: BookingStatsByStatus[];
}

export function ByStatusChart({ data }: ByStatusProps) {
  return (
    <ChartCard title="By status">
      {data.length === 0 ? (
        <div className="py-12 text-center text-sm text-zinc-400 dark:text-zinc-500">
          No data yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie
              data={data}
              dataKey="count"
              nameKey="status"
              cx="50%"
              cy="50%"
              innerRadius="55%"
              outerRadius="75%"
              paddingAngle={3}
              animationDuration={800}
            >
              {data.map((row, i) => (
                <Cell key={i} fill={statusColor(row.status)} />
              ))}
            </Pie>
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} />
          </PieChart>
        </ResponsiveContainer>
      )}
      {/* Legend */}
      <div className="mt-2 flex flex-wrap gap-3 justify-center">
        {data.map((row) => (
          <span
            key={row.status}
            className="flex items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-400"
          >
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: statusColor(row.status) }}
            />
            <span className="capitalize">{row.status.replace("_", " ")}</span>
            <span className="font-medium">{row.count}</span>
          </span>
        ))}
      </div>
    </ChartCard>
  );
}

// ── Peak times heatmap (7×24 CSS grid) ───────────────────────────────────────

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface HeatmapProps {
  data: BookingStatsHeatmapCell[];
}

export function PeakTimesHeatmap({ data }: HeatmapProps) {
  const reduced = useReducedMotion();

  const maxCount = data.reduce((m, c) => Math.max(m, c.count), 0);

  // Build a lookup map: `${weekday}-${hour}` → count
  const lookup = new Map<string, number>();
  for (const cell of data) {
    lookup.set(`${cell.weekday}-${cell.hour}`, cell.count);
  }

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
    >
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
        Peak times
      </h3>

      {data.length === 0 ? (
        <div className="py-12 text-center text-sm text-zinc-400 dark:text-zinc-500">
          No data yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          {/* Hour header row */}
          <div className="flex items-center">
            <div className="w-9 shrink-0" />
            <div
              className="grid flex-1 gap-px"
              style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}
            >
              {Array.from({ length: 24 }, (_, h) => (
                <div key={h} className="text-center text-[9px] text-zinc-400 dark:text-zinc-600">
                  {h % 6 === 0 ? `${h}h` : ""}
                </div>
              ))}
            </div>
          </div>

          {/* Rows per weekday */}
          {WEEKDAY_LABELS.map((label, wd) => (
            <div key={wd} className="flex items-center gap-0.5">
              <div className="w-9 shrink-0 pr-1 text-right text-[10px] text-zinc-500 dark:text-zinc-400">
                {label}
              </div>
              <div
                className="grid flex-1 gap-px"
                style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}
              >
                {Array.from({ length: 24 }, (_, h) => {
                  const count = lookup.get(`${wd}-${h}`) ?? 0;
                  const opacity = maxCount > 0 ? count / maxCount : 0;
                  return (
                    <div
                      key={h}
                      title={
                        count > 0
                          ? `${label} ${h}:00 — ${count} booking${count !== 1 ? "s" : ""}`
                          : undefined
                      }
                      className="h-4 rounded-sm"
                      style={{
                        backgroundColor: `rgba(16, 185, 129, ${opacity})`,
                        border: "1px solid rgba(16,185,129,0.15)",
                      }}
                    />
                  );
                })}
              </div>
            </div>
          ))}

          {/* Legend */}
          <div className="mt-3 flex items-center justify-end gap-2">
            <span className="text-[10px] text-zinc-400 dark:text-zinc-600">Less</span>
            {[0.1, 0.3, 0.5, 0.7, 1].map((o) => (
              <div
                key={o}
                className="h-3 w-3 rounded-sm"
                style={{ backgroundColor: `rgba(16, 185, 129, ${o})` }}
              />
            ))}
            <span className="text-[10px] text-zinc-400 dark:text-zinc-600">More</span>
          </div>
        </div>
      )}
    </motion.div>
  );
}
