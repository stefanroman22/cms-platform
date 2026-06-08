"use client";

import { motion } from "framer-motion";
import { Check, X } from "lucide-react";
import { fadeUp, staggerFast } from "@/lib/animations";

interface Props {
  attributes: Record<string, Record<string, boolean>> | null | undefined;
}

export function AboutAttributesPanel({ attributes }: Props) {
  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
        About this business
      </h3>
      {!attributes || Object.keys(attributes).length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 text-xs text-zinc-500 dark:text-zinc-400 italic">
          No &quot;About&quot; data on Google Maps for this place.
        </div>
      ) : (
        <motion.div
          variants={staggerFast}
          initial="hidden"
          animate="visible"
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-3"
        >
          {Object.entries(attributes).map(([section, items]) => (
            <motion.div key={section} variants={fadeUp}>
              <div className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                {section}
              </div>
              <ul className="space-y-0.5">
                {Object.entries(items).map(([attr, value]) => (
                  <li
                    key={attr}
                    className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300"
                  >
                    {value ? (
                      <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    ) : (
                      <X className="h-3.5 w-3.5 text-zinc-400 dark:text-zinc-600 shrink-0" />
                    )}
                    <span className={value ? "" : "text-zinc-500 dark:text-zinc-500 line-through"}>
                      {attr}
                    </span>
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </motion.div>
      )}
    </section>
  );
}
