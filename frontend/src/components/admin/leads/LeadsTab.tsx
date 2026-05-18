"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { LeadsDashboard } from "./LeadsDashboard";
import { ScraperControl } from "./ScraperControl";

type Section = "dashboard" | "scraper";

export function LeadsTab() {
  const [section, setSection] = useState<Section>("dashboard");
  return (
    <div className="p-4 md:p-8">
      <PageHeader
        title="Leads"
        description="Browse scraped businesses without websites and trigger new scrape jobs."
      />
      <div className="mt-6 flex gap-2">
        {(["dashboard", "scraper"] as Section[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSection(s)}
            className={[
              "px-3 py-1.5 rounded-md text-sm font-medium transition-colors cursor-pointer",
              section === s
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700",
            ].join(" ")}
          >
            {s === "dashboard" ? "Dashboard" : "Scraper"}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={section}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
          className="mt-6"
        >
          {section === "dashboard" ? <LeadsDashboard /> : <ScraperControl />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
