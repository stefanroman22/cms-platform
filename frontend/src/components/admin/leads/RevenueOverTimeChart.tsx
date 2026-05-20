"use client";

import { motion } from "framer-motion";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ConversionTimePoint } from "./types";

interface Props {
  data: ConversionTimePoint[];
}

function formatEur(n: number): string {
  return new Intl.NumberFormat("nl-NL", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(n);
}

export function RevenueOverTimeChart({ data }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4"
    >
      <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
        Revenue over time
      </h3>
      {data.length === 0 ? (
        <div className="py-12 text-center text-sm text-zinc-400 dark:text-zinc-500">
          No accepted deals yet. Close a lead with a deal amount to start tracking revenue.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
            <XAxis
              dataKey="month"
              tick={{ fontSize: 12 }}
              stroke="currentColor"
              className="text-zinc-500"
            />
            <YAxis
              tickFormatter={formatEur}
              tick={{ fontSize: 12 }}
              stroke="currentColor"
              className="text-zinc-500"
            />
            <Tooltip
              formatter={(value: number) => formatEur(value)}
              contentStyle={{
                backgroundColor: "rgb(24 24 27)",
                border: "1px solid rgb(63 63 70)",
                borderRadius: 8,
              }}
              labelStyle={{ color: "rgb(212 212 216)" }}
            />
            <Line
              type="monotone"
              dataKey="revenue"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
              animationDuration={800}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </motion.div>
  );
}
