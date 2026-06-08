"use client";

import { useState } from "react";
import { JobHistoryList } from "./JobHistoryList";
import { ScraperForm } from "./ScraperForm";

export function ScraperControl() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
          New scrape job
        </h2>
        <ScraperForm onJobCreated={() => setRefreshTrigger((n) => n + 1)} />
      </div>
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
          Job history
        </h2>
        <JobHistoryList refreshTrigger={refreshTrigger} />
      </div>
    </div>
  );
}
