"use client";

import { motion } from "framer-motion";
import { staggerFast, fadeUp } from "@/lib/animations";
import type { Lead } from "./types";

interface Props {
  leads: Lead[];
  total: number; // total across all pages, from API
}

export function LeadStatsCards({ leads, total }: Props) {
  const noWebsite = leads.filter((l) => l.web_presence === "none").length;
  const sent = leads.filter((l) => l.lead_status === "sent").length;
  const aiScored = leads.filter((l) => l.ai_score !== null).length;
  const stats = [
    { label: "Total (filtered)", value: total },
    { label: "No website (page)", value: noWebsite },
    { label: "Sent (page)", value: sent },
    { label: "AI scored (page)", value: aiScored },
  ];

  return (
    <motion.div
      variants={staggerFast}
      initial="hidden"
      animate="visible"
      className="grid grid-cols-2 md:grid-cols-4 gap-3"
    >
      {stats.map((s) => (
        <motion.div
          key={s.label}
          variants={fadeUp}
          className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4"
        >
          <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
            {s.label}
          </div>
          <div className="mt-1 text-2xl font-semibold text-zinc-900 dark:text-zinc-100 tabular-nums">
            {s.value}
          </div>
        </motion.div>
      ))}
    </motion.div>
  );
}
