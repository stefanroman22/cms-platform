// ArticlesTab.tsx
import { useQuery } from "@/hooks/useQuery";
import { getArticles } from "./api";

export function ArticlesTab({ projectSlug }: { projectSlug: string }) {
  const { data, loading } = useQuery(
    `seo-articles:${projectSlug}`,
    () => getArticles(projectSlug),
    { ttl: 60 * 1000 }
  );
  if (loading) return <p className="text-sm text-zinc-500">Loading…</p>;
  if (!data || data.length === 0) return <p className="text-sm text-zinc-500">No articles yet.</p>;
  return (
    <ul className="space-y-2">
      {data.map((a) => (
        <li key={a.id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <span className="font-medium">{a.title}</span>
          <span className="ml-2 text-xs text-zinc-500">
            {a.locale} · {a.status}
          </span>
        </li>
      ))}
    </ul>
  );
}
