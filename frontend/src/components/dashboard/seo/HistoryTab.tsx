// HistoryTab.tsx
import { useQuery } from "@/hooks/useQuery";
import { getHistory } from "./api";

export function HistoryTab({ projectSlug }: { projectSlug: string }) {
  const { data, loading } = useQuery(`seo-history:${projectSlug}`, () => getHistory(projectSlug), {
    ttl: 60 * 1000,
  });
  if (loading) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (!data || data.runs.length === 0) return <p className="text-sm text-zinc-500">No runs yet.</p>;
  return (
    <ul className="space-y-2">
      {data.runs.map((r) => (
        <li key={r.id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium">{r.status}</span>
            <span className="text-zinc-500">{new Date(r.started_at).toLocaleString()}</span>
          </div>
          {r.summary && (
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{r.summary}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
