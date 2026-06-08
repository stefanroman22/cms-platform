"use client";

import { motion, useReducedMotion } from "motion/react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BookingStatsByStaff } from "../api";

const TOOLTIP_STYLE = {
  backgroundColor: "rgb(24 24 27)",
  border: "1px solid rgb(63 63 70)",
  borderRadius: 8,
} as const;

const TOOLTIP_LABEL_STYLE = { color: "rgb(212 212 216)" } as const;

const STAFF_PALETTE = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#84cc16"];

interface Props {
  data: BookingStatsByStaff[];
}

/**
 * Appointments-per-staff bar chart + compact per-staff count list. Only meaningful
 * with two or more staff; the registry/panel hides it otherwise.
 */
export function ByStaffWidgets({ data }: Props) {
  const reduced = useReducedMotion();
  const rows = data.slice(0, 7);

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
    >
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
        By staff
      </h3>

      {rows.length === 0 ? (
        <div className="py-12 text-center text-sm text-zinc-400 dark:text-zinc-500">
          No data yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* Bar chart */}
          <div className="lg:col-span-2">
            <ResponsiveContainer width="100%" height={Math.max(180, rows.length * 38)}>
              <BarChart
                data={rows}
                layout="vertical"
                margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  className="stroke-zinc-200 dark:stroke-zinc-800"
                />
                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{ fontSize: 11 }}
                  stroke="currentColor"
                  className="text-zinc-500"
                />
                <YAxis
                  type="category"
                  dataKey="resource_name"
                  tick={{ fontSize: 11 }}
                  width={110}
                  stroke="currentColor"
                  className="text-zinc-500"
                />
                <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} />
                <Bar dataKey="count" name="Bookings" animationDuration={800}>
                  {rows.map((_, i) => (
                    <Cell key={i} fill={STAFF_PALETTE[i % STAFF_PALETTE.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Compact per-staff count list */}
          <ul className="space-y-1.5">
            {rows.map((s, i) => (
              <li
                key={s.resource_id}
                className="flex items-center justify-between gap-2 rounded-lg border border-zinc-100 px-3 py-2 dark:border-zinc-800/60"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: STAFF_PALETTE[i % STAFF_PALETTE.length] }}
                    aria-hidden="true"
                  />
                  <span className="truncate text-sm text-zinc-700 dark:text-zinc-300">
                    {s.resource_name}
                  </span>
                </span>
                <span className="text-sm font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">
                  {s.count}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </motion.div>
  );
}
