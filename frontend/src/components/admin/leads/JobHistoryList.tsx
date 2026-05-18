"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { useQuery } from "@/hooks/useQuery";
import { LeadBadge } from "./LeadBadge";
import { SCRAPE_JOB_STATUS_BADGE_CN, SCRAPE_JOB_STATUS_LABEL } from "@/lib/leadEnums";
import { staggerFast, fadeUp } from "@/lib/animations";
import type { ScrapeJob } from "./types";

interface Props {
  refreshTrigger: number;
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function summarizeParams(j: ScrapeJob): string {
  const { params } = j;
  const cities = params.cities.length ? params.cities.join(", ") : params.country;
  return `${params.category} · ${cities} · max ${params.max_results_per_area}`;
}

export function JobHistoryList({ refreshTrigger }: Props) {
  const { data, loading, error, refresh } = useQuery<ScrapeJob[]>(
    "scrape-jobs",
    () =>
      fetch("/api/admin/scrape-jobs?limit=50", { credentials: "include" }).then(async (r) => {
        if (!r.ok) throw new Error(`Failed to load jobs (${r.status})`);
        return r.json();
      }),
    { ttl: 5 * 1000 }
  );

  // Poll every 5s while the list is mounted, so running/pending jobs reveal
  // their state without a manual refresh.
  useEffect(() => {
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  // Refresh on parent's trigger bump (form just submitted a new job).
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  async function cancelJob(id: string) {
    if (!confirm("Cancel this pending job?")) return;
    const res = await fetch(`/api/admin/scrape-jobs/${id}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "cancelled" }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      alert(`Cancel failed: ${body.detail ?? res.status}`);
      return;
    }
    refresh();
  }

  if (loading && !data) {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-14 rounded-lg bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
        ))}
      </div>
    );
  }
  if (error) {
    return <div className="text-sm text-red-600 dark:text-red-400">{error}</div>;
  }
  const jobs = data ?? [];
  if (jobs.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-zinc-500 dark:text-zinc-400">
        No scrape jobs yet.
      </div>
    );
  }

  return (
    <motion.div variants={staggerFast} initial="hidden" animate="visible" className="space-y-2">
      {jobs.map((j) => (
        <motion.div
          key={j.id}
          variants={fadeUp}
          layout
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3 flex items-start justify-between gap-3"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <LeadBadge
                label={SCRAPE_JOB_STATUS_LABEL[j.status]}
                className={SCRAPE_JOB_STATUS_BADGE_CN[j.status]}
              />
              <span className="text-sm text-zinc-900 dark:text-zinc-100 truncate">
                {summarizeParams(j)}
              </span>
            </div>
            <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400 flex flex-wrap gap-3">
              <span>created {formatTimestamp(j.created_at)}</span>
              {j.started_at && <span>started {formatTimestamp(j.started_at)}</span>}
              {j.finished_at && <span>finished {formatTimestamp(j.finished_at)}</span>}
              {j.results_found != null && (
                <span>
                  {j.results_inserted ?? 0}/{j.results_found} inserted
                </span>
              )}
              {j.error && (
                <span className="text-red-600 dark:text-red-400 truncate max-w-md">{j.error}</span>
              )}
            </div>
          </div>
          {j.status === "pending" && (
            <button
              type="button"
              onClick={() => cancelJob(j.id)}
              className="text-xs text-zinc-500 hover:text-red-600 dark:hover:text-red-400 cursor-pointer"
            >
              Cancel
            </button>
          )}
        </motion.div>
      ))}
    </motion.div>
  );
}
