// OverviewTab.tsx
import { useQuery } from "@/hooks/useQuery";
import { getOverview, enqueueRun } from "./api";
import { useState } from "react";

export function OverviewTab({ projectSlug }: { projectSlug: string }) {
  const { data, loading } = useQuery(
    `seo-overview:${projectSlug}`,
    () => getOverview(projectSlug),
    { ttl: 60 * 1000 }
  );
  const [queued, setQueued] = useState(false);
  if (loading) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (!data) return <p className="text-sm text-zinc-500">No data.</p>;
  const dial = (label: string, v: number | null) => (
    <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-3xl font-semibold">{v ?? "—"}</div>
    </div>
  );
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {dial("SEO", data.seo_score)}
        {dial("GEO (AI readiness)", data.geo_score)}
        {dial("Local", data.local_score)}
      </div>
      <button
        type="button"
        disabled={queued}
        onClick={() => {
          enqueueRun(projectSlug)
            .then(() => setQueued(true))
            .catch(() => {});
        }}
        className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
      >
        {queued ? "Queued ✓" : "Run SEO agent"}
      </button>
    </div>
  );
}
