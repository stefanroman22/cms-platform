"use client";

import { motion } from "framer-motion";
import { Star } from "lucide-react";
import { fadeUp, staggerFast } from "@/lib/animations";

interface Review {
  author: string | null;
  text: string | null;
  relative_date: string | null;
  rating: number | null;
}

interface Props {
  reviews: Review[] | null;
}

export function ReviewsList({ reviews }: Props) {
  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
        Top reviews
      </h3>
      {!reviews || reviews.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 text-xs text-zinc-500 dark:text-zinc-400 italic">
          No reviews captured.
        </div>
      ) : (
        <motion.div variants={staggerFast} initial="hidden" animate="visible" className="space-y-2">
          {reviews.map((r, i) => (
            <motion.div
              key={`${r.author ?? "anon"}-${i}`}
              variants={fadeUp}
              className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
                  {r.author ?? "Anonymous"}
                </span>
                <span className="inline-flex items-center gap-0.5 text-xs text-amber-600 dark:text-amber-400 tabular-nums">
                  <Star className="h-3 w-3 fill-current" />
                  {r.rating ?? "—"}
                </span>
              </div>
              {r.text && (
                <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">
                  {r.text}
                </p>
              )}
              {r.relative_date && (
                <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  {r.relative_date}
                </div>
              )}
            </motion.div>
          ))}
        </motion.div>
      )}
    </section>
  );
}
