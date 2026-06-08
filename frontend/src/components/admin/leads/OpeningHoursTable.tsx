"use client";

import { motion } from "framer-motion";
import { Clock } from "lucide-react";
import { fadeUp, staggerFast } from "@/lib/animations";

const DAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

interface Props {
  hours: Record<string, string> | null;
}

export function OpeningHoursTable({ hours }: Props) {
  // Merge whatever we have with the 7-day skeleton so every row renders.
  const merged: Record<string, string> = Object.fromEntries(
    DAYS.map((d) => [d, hours?.[d] ?? "___"])
  );

  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2 flex items-center gap-1.5">
        <Clock className="h-3.5 w-3.5" />
        Opening hours
      </h3>
      <motion.div
        variants={staggerFast}
        initial="hidden"
        animate="visible"
        className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800"
      >
        {DAYS.map((day) => {
          const value = merged[day];
          const isPlaceholder = value === "___";
          return (
            <motion.div
              key={day}
              variants={fadeUp}
              className="flex items-center justify-between px-3 py-2 text-sm"
            >
              <span className="text-zinc-600 dark:text-zinc-400 font-medium">{day}</span>
              <span
                className={
                  isPlaceholder
                    ? "text-zinc-400 dark:text-zinc-600 font-mono italic"
                    : "text-zinc-900 dark:text-zinc-100 tabular-nums"
                }
              >
                {value}
              </span>
            </motion.div>
          );
        })}
      </motion.div>
    </section>
  );
}
