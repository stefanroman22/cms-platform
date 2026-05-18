"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@/hooks/useQuery";
import { LeadStatsCards } from "./LeadStatsCards";
import { LeadFilters } from "./LeadFilters";
import { LeadsTable } from "./LeadsTable";
import { EMPTY_FILTERS } from "./types";
import type { Lead, LeadFiltersState, LeadsListResponse } from "./types";

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

  const qs = useMemo(() => buildQuery(filters, page), [filters, page]);

  const { data, loading } = useQuery<LeadsListResponse>(
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
    // C9 wires the LeadDetailDrawer; for now log so the row click is testable.
    console.log("selected lead:", lead.id, lead.business_name);
  }

  const leads = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <LeadStatsCards leads={leads} total={total} />
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
        <LeadFilters value={filters} onChange={handleFiltersChange} />
      </div>
      <LeadsTable
        leads={leads}
        total={total}
        loading={loading}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        onSelect={handleSelect}
      />
    </div>
  );
}
