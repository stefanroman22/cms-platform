// PlanTab.tsx
import { useQuery } from "@/hooks/useQuery";
import { getPlan } from "./api";

export function PlanTab({ projectSlug }: { projectSlug: string }) {
  const { data, loading } = useQuery(`seo-plan:${projectSlug}`, () => getPlan(projectSlug), {
    ttl: 60 * 1000,
  });
  if (loading) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (!data || data.length === 0)
    return <p className="text-sm text-zinc-500">No plan items yet. Run the agent.</p>;
  return (
    <ul className="space-y-2">
      {data.map((it) => (
        <li key={it.id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="flex items-center gap-2">
            <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs uppercase dark:bg-zinc-800">
              {it.track}
            </span>
            <span className="font-medium">{it.title}</span>
            <span className="ml-auto text-xs text-zinc-500">{it.status}</span>
          </div>
          {it.description && (
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{it.description}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
