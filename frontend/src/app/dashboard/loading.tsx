/**
 * Streams instantly while the dashboard route segment compiles and
 * the page's data fetches. No client JS — pure server-rendered HTML
 * + Tailwind utility classes. Pulse via Tailwind's `animate-pulse`.
 */
export default function DashboardLoading() {
  return (
    <div className="flex min-h-screen bg-zinc-950" aria-busy="true" aria-label="Loading dashboard">
      {/* Sidebar placeholder */}
      <aside className="hidden w-64 border-r border-white/[0.08] p-4 md:block">
        <div className="h-10 w-32 animate-pulse rounded bg-white/[0.06]" />
        <div className="mt-8 space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-8 w-full animate-pulse rounded bg-white/[0.04]" />
          ))}
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        {/* Topbar placeholder */}
        <div className="flex h-16 items-center justify-between border-b border-white/[0.08] px-6">
          <div className="h-6 w-48 animate-pulse rounded bg-white/[0.06]" />
          <div className="h-8 w-8 animate-pulse rounded-full bg-white/[0.06]" />
        </div>

        {/* Content placeholders */}
        <div className="grid flex-1 gap-4 p-6 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-40 animate-pulse rounded-xl border border-white/[0.06] bg-white/[0.02]"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
