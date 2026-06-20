// CompetitorsTab.tsx
import { useQuery } from "@/hooks/useQuery";
import { getCompetitors } from "./api";

export function CompetitorsTab({ projectSlug }: { projectSlug: string }) {
  const { data, loading } = useQuery(
    `seo-competitors:${projectSlug}`,
    () => getCompetitors(projectSlug),
    { ttl: 60 * 1000 }
  );
  if (loading) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (!data || data.length === 0)
    return <p className="text-sm text-zinc-500">No competitor analysis yet.</p>;
  return (
    <ul className="space-y-2">
      {data.map((c) => (
        <li key={c.id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="font-medium">{c.name}</div>
          {c.analysis && (
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{c.analysis}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
