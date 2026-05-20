"use client";

import { motion } from "framer-motion";
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
import type { ConversionBreakdownRow } from "./types";

interface Props {
  title: string;
  data: ConversionBreakdownRow[];
  metric: "accepted" | "revenue";
}

const PALETTE = ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#84cc16"];

function formatValue(v: number, metric: "accepted" | "revenue"): string {
  if (metric === "revenue") {
    return new Intl.NumberFormat("nl-NL", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(v);
  }
  return v.toString();
}

export function BreakdownChart({ title, data, metric }: Props) {
  const top = data.slice(0, 7);
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4"
    >
      <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
        {title}
      </h3>
      {top.length === 0 ? (
        <div className="py-12 text-center text-sm text-zinc-400 dark:text-zinc-500">
          No data yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={top} layout="vertical" margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-800" />
            <XAxis
              type="number"
              tickFormatter={(v) => formatValue(v, metric)}
              tick={{ fontSize: 12 }}
              stroke="currentColor"
              className="text-zinc-500"
            />
            <YAxis
              type="category"
              dataKey="key"
              tick={{ fontSize: 12 }}
              width={100}
              stroke="currentColor"
              className="text-zinc-500"
            />
            <Tooltip
              formatter={(value: number) => formatValue(value, metric)}
              contentStyle={{
                backgroundColor: "rgb(24 24 27)",
                border: "1px solid rgb(63 63 70)",
                borderRadius: 8,
              }}
              labelStyle={{ color: "rgb(212 212 216)" }}
            />
            <Bar dataKey={metric} animationDuration={800}>
              {top.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </motion.div>
  );
}
