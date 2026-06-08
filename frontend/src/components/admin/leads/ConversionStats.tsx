"use client";

import { motion } from "framer-motion";
import { Banknote, CheckCircle2, Percent, Send, TrendingUp, XCircle } from "lucide-react";
import { staggerFast, fadeUp } from "@/lib/animations";
import type { ConversionSummary } from "./types";

interface Props {
  summary: ConversionSummary;
  loading: boolean;
}

function formatCurrency(n: number): string {
  return new Intl.NumberFormat("nl-NL", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(n);
}

function formatPercent(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

export function ConversionStats({ summary, loading }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-24 rounded-xl bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
        ))}
      </div>
    );
  }

  const stats = [
    {
      label: "Total revenue",
      value: formatCurrency(summary.total_revenue),
      icon: Banknote,
      accent: "text-emerald-600 dark:text-emerald-400",
    },
    {
      label: "Conversion rate",
      value: formatPercent(summary.conversion_rate),
      icon: Percent,
      accent: "text-blue-600 dark:text-blue-400",
    },
    {
      label: "Average deal",
      value: formatCurrency(summary.average_deal_size),
      icon: TrendingUp,
      accent: "text-violet-600 dark:text-violet-400",
    },
    {
      label: "Accepted",
      value: summary.total_accepted.toString(),
      icon: CheckCircle2,
      accent: "text-emerald-600 dark:text-emerald-400",
    },
    {
      label: "Sent",
      value: summary.total_sent.toString(),
      icon: Send,
      accent: "text-zinc-600 dark:text-zinc-400",
    },
    {
      label: "Refused",
      value: summary.total_refused.toString(),
      icon: XCircle,
      accent: "text-red-600 dark:text-red-400",
    },
  ];

  return (
    <motion.div
      variants={staggerFast}
      initial="hidden"
      animate="visible"
      className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3"
    >
      {stats.map((s) => (
        <motion.div
          key={s.label}
          variants={fadeUp}
          className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4"
        >
          <div className="flex items-center justify-between">
            <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              {s.label}
            </div>
            <s.icon className={`h-4 w-4 ${s.accent}`} />
          </div>
          <div className="mt-1 text-2xl font-semibold text-zinc-900 dark:text-zinc-100 tabular-nums">
            {s.value}
          </div>
        </motion.div>
      ))}
    </motion.div>
  );
}
