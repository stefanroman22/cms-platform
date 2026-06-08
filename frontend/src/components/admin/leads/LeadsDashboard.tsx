"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useQuery } from "@/hooks/useQuery";
import { LeadStatsCards } from "./LeadStatsCards";
import { LeadFilters } from "./LeadFilters";
import { LeadsTable } from "./LeadsTable";
import { LeadKanban } from "./LeadKanban";
import { LeadDetailDrawer } from "./LeadDetailDrawer";
import { EMPTY_FILTERS } from "./types";
import type { Lead, LeadFiltersState, LeadsListResponse } from "./types";
import type { LeadStatus } from "@/lib/leadEnums";

const PAGE_SIZE = 50;

function buildQuery(filters: LeadFiltersState, page: number): string {
  const p = new URLSearchParams();
  if (filters.country) p.set("country", filters.country);
  if (filters.city) p.set("city", filters.city);
  if (filters.category) p.set("category", filters.category);
  if (filters.lead_type) p.set("lead_type", filters.lead_type);
  for (const wp of filters.web_presence) p.append("web_presence", wp);
  for (const ls of filters.lead_status) p.append("lead_status", ls);
  if (filters.min_rating) p.set("min_rating", filters.min_rating);
  if (filters.max_rating) p.set("max_rating", filters.max_rating);
  if (filters.min_reviews) p.set("min_reviews", filters.min_reviews);
  if (filters.max_reviews) p.set("max_reviews", filters.max_reviews);
  if (filters.search) p.set("search", filters.search);
  p.set("limit", String(PAGE_SIZE));
  p.set("offset", String(page * PAGE_SIZE));
  return p.toString();
}

export function LeadsDashboard() {
  const [filters, setFilters] = useState<LeadFiltersState>(EMPTY_FILTERS);
  const [page, setPage] = useState(0);
  const [view, setView] = useState<"table" | "kanban">("table");
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  const qs = useMemo(() => buildQuery(filters, page), [filters, page]);

  const { data, loading, refresh } = useQuery<LeadsListResponse>(
    `leads:${qs}`,
    () =>
      fetch(`/api/admin/leads?${qs}`, { credentials: "include" }).then(async (r) => {
        if (!r.ok) throw new Error(`Failed to load leads (${r.status})`);
        return r.json();
      }),
    { ttl: 15 * 1000 }
  );

  function handleFiltersChange(next: LeadFiltersState) {
    setFilters(next);
    setPage(0); // reset to first page when filters change
  }

  function handleSelect(lead: Lead) {
    setSelectedLead(lead);
  }

  function handlePatched(updated: Lead) {
    setSelectedLead(updated);
    refresh();
  }

  function handleDeleted() {
    setSelectedLead(null);
    refresh();
  }

  async function handleStatusChange(leadId: string, next: LeadStatus) {
    const res = await fetch(`/api/admin/leads/${leadId}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lead_status: next }),
    });
    if (!res.ok) throw new Error(`Status update failed (${res.status})`);
    await refresh();
  }

  const leads = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <LeadStatsCards leads={leads} total={total} />
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
        <LeadFilters value={filters} onChange={handleFiltersChange} />
      </div>
      <div className="flex items-center gap-2">
        {(["table", "kanban"] as const).map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setView(v)}
            className={[
              "px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
              view === v
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700",
            ].join(" ")}
          >
            {v === "table" ? "Table" : "Kanban"}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={view}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
        >
          {view === "table" ? (
            <LeadsTable
              leads={leads}
              total={total}
              loading={loading}
              page={page}
              pageSize={PAGE_SIZE}
              onPageChange={setPage}
              onSelect={handleSelect}
            />
          ) : (
            <LeadKanban
              leads={leads}
              loading={loading}
              onSelect={handleSelect}
              onStatusChange={handleStatusChange}
            />
          )}
        </motion.div>
      </AnimatePresence>
      <LeadDetailDrawer
        lead={selectedLead}
        onClose={() => setSelectedLead(null)}
        onPatched={handlePatched}
        onDeleted={handleDeleted}
      />
    </div>
  );
}
