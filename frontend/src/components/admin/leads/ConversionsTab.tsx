"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@/hooks/useQuery";
import { ConversionStats } from "./ConversionStats";
import { RevenueOverTimeChart } from "./RevenueOverTimeChart";
import { BreakdownChart } from "./BreakdownChart";
import { ConversionFilters } from "./ConversionFilters";
import { EMPTY_CONVERSION_FILTERS } from "./types";
import type { ConversionFilters as Filters, ConversionSummary } from "./types";

function buildQuery(f: Filters): string {
  const p = new URLSearchParams();
  if (f.lead_type) p.set("lead_type", f.lead_type);
  if (f.city) p.set("city", f.city);
  if (f.category) p.set("category", f.category);
  if (f.since) p.set("since", f.since);
  return p.toString();
}

export function ConversionsTab() {
  const [filters, setFilters] = useState<Filters>(EMPTY_CONVERSION_FILTERS);
  const qs = useMemo(() => buildQuery(filters), [filters]);

  const { data, loading } = useQuery<ConversionSummary>(
    `conversions:${qs}`,
    () =>
      fetch(`/api/admin/conversions/summary?${qs}`, { credentials: "include" }).then(async (r) => {
        if (!r.ok) throw new Error(`Failed to load conversions (${r.status})`);
        return r.json();
      }),
    { ttl: 30 * 1000 }
  );

  const summary = data ?? {
    total_sent: 0,
    total_accepted: 0,
    total_refused: 0,
    conversion_rate: 0,
    total_revenue: 0,
    average_deal_size: 0,
    timeseries: [],
    by_lead_type: [],
    by_category: [],
    by_city: [],
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
        <ConversionFilters value={filters} onChange={setFilters} />
      </div>

      <ConversionStats summary={summary} loading={loading} />

      <RevenueOverTimeChart data={summary.timeseries} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <BreakdownChart title="By lead type" data={summary.by_lead_type} metric="revenue" />
        <BreakdownChart title="By category" data={summary.by_category} metric="revenue" />
        <BreakdownChart title="By city" data={summary.by_city} metric="revenue" />
      </div>
    </div>
  );
}
