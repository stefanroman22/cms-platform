import {
  LayoutDashboard,
  FileText,
  Newspaper,
  UtensilsCrossed,
  CalendarCheck,
  Images,
  Settings,
  Search,
  TrendingUp,
  Bot,
  Check,
  Plus,
} from "lucide-react";

/* Café Nordlys — a fictional Berlin café chain. All data below is the
   sample client used throughout the hero so the projected UI reads as a
   real product, never a marketing mockup. Rendered at a fixed logical
   size and scaled onto the laptop screen by drei <Html transform>. */

const NAV = [
  { label: "Dashboard", icon: LayoutDashboard, active: true },
  { label: "Pages", icon: FileText, active: false },
  { label: "Blog", icon: Newspaper, active: false },
  { label: "Menu", icon: UtensilsCrossed, active: false },
  { label: "Bookings", icon: CalendarCheck, active: false },
  { label: "Media", icon: Images, active: false },
  { label: "Settings", icon: Settings, active: false },
] as const;

const STATS = [
  { label: "Bookings today", value: "23", trend: "+12%" },
  { label: "Page views", value: "1,847", trend: "+8%" },
  { label: "Menu items live", value: "42", trend: "+3" },
  { label: "Avg. response time", value: "1.2s", trend: "−0.3s" },
] as const;

const LANGS = [
  { flag: "🇩🇪", code: "DE" },
  { flag: "🇬🇧", code: "EN" },
  { flag: "🇳🇱", code: "NL" },
] as const;

export function CMSPreview() {
  return (
    <div
      style={{ width: 1280, height: 800 }}
      className="flex select-none overflow-hidden bg-[#0E0E10] font-body text-text-primary antialiased"
    >
      {/* ── Sidebar ──────────────────────────────────────────────── */}
      <aside className="flex w-[220px] shrink-0 flex-col border-r border-white/[0.06] bg-[#0B0B0D] px-4 py-6">
        <div className="mb-9 flex items-center gap-2.5 px-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-[15px] font-bold text-bg">
            N
          </span>
          <span className="text-[15px] font-semibold tracking-tight">Café Nordlys</span>
        </div>

        <nav className="flex flex-col gap-1">
          {NAV.map(({ label, icon: Icon, active }) => (
            <div
              key={label}
              className={
                active
                  ? "relative flex items-center gap-3 rounded-md bg-white/[0.04] px-3 py-2.5 text-[14px] font-medium text-text-primary"
                  : "flex items-center gap-3 rounded-md px-3 py-2.5 text-[14px] text-text-secondary"
              }
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r bg-accent" />
              )}
              <Icon className={active ? "h-4 w-4 text-accent" : "h-4 w-4"} strokeWidth={1.75} />
              {label}
            </div>
          ))}
        </nav>

        <div className="mt-auto flex items-center gap-3 rounded-md border border-white/[0.06] px-3 py-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/10 text-[12px] font-semibold">
            LK
          </span>
          <div className="leading-tight">
            <p className="text-[12.5px] font-medium">Lukas Brandt</p>
            <p className="text-[11px] text-text-tertiary">Owner</p>
          </div>
        </div>
      </aside>

      {/* ── Main column ──────────────────────────────────────────── */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex h-[60px] shrink-0 items-center gap-4 border-b border-white/[0.06] px-7">
          <div className="flex h-9 max-w-[320px] flex-1 items-center gap-2.5 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3">
            <Search className="h-3.5 w-3.5 text-text-tertiary" strokeWidth={2} />
            <span className="text-[13px] text-text-tertiary">Search pages, bookings…</span>
          </div>
          <div className="ml-auto flex items-center gap-4">
            <button className="flex h-9 items-center gap-2 rounded-lg bg-accent px-4 text-[13px] font-semibold text-bg">
              Publish
            </button>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-[12px] font-semibold">
              LK
            </span>
          </div>
        </header>

        {/* Dashboard body */}
        <div className="flex-1 overflow-hidden px-7 py-7">
          <h2 className="text-[24px] font-semibold tracking-tight">Good morning, Lukas</h2>
          <p className="mt-1 text-[14px] text-text-secondary">
            Here&rsquo;s what&rsquo;s happening at Café Nordlys today.
          </p>

          {/* Stat row */}
          <div className="mt-6 grid grid-cols-4 gap-4">
            {STATS.map(({ label, value, trend }) => (
              <div
                key={label}
                className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4"
              >
                <p className="text-[12.5px] text-text-secondary">{label}</p>
                <div className="mt-2 flex items-end justify-between">
                  <span className="text-[26px] font-semibold leading-none tracking-tight">
                    {value}
                  </span>
                  <span className="flex items-center gap-1 text-[12px] font-medium text-accent">
                    <TrendingUp className="h-3.5 w-3.5" strokeWidth={2.25} />
                    {trend}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Recent activity */}
          <div className="mt-7 rounded-xl border border-white/[0.06] bg-white/[0.02]">
            <div className="border-b border-white/[0.06] px-5 py-3.5">
              <h3 className="text-[14px] font-semibold">Recent activity</h3>
            </div>
            <ul className="divide-y divide-white/[0.04]">
              <li className="flex items-center gap-3 px-5 py-3.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent">
                  <Bot className="h-3.5 w-3.5" strokeWidth={2} />
                </span>
                <p className="text-[13.5px] text-text-secondary">
                  AI agent resolved a booking conflict (auto-confirmed)
                </p>
                <span className="ml-2 rounded-full bg-accent/15 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-accent">
                  Auto
                </span>
                <span className="ml-auto whitespace-nowrap text-[12px] text-text-tertiary">
                  2m ago
                </span>
              </li>
              <li className="flex items-center gap-3 px-5 py-3.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-text-secondary">
                  <Newspaper className="h-3.5 w-3.5" strokeWidth={2} />
                </span>
                <p className="text-[13.5px] text-text-secondary">
                  New blog post published in DE / EN / NL
                </p>
                <span className="ml-auto whitespace-nowrap text-[12px] text-text-tertiary">
                  14m ago
                </span>
              </li>
              <li className="flex items-center gap-3 px-5 py-3.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-text-secondary">
                  <UtensilsCrossed className="h-3.5 w-3.5" strokeWidth={2} />
                </span>
                <p className="text-[13.5px] text-text-secondary">
                  Senior review approved menu update
                </p>
                <span className="ml-2 inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 text-[10.5px] font-medium text-text-secondary">
                  <Check className="h-3 w-3 text-accent" strokeWidth={3} />
                  Reviewed
                </span>
                <span className="ml-auto whitespace-nowrap text-[12px] text-text-tertiary">
                  1h ago
                </span>
              </li>
            </ul>
          </div>

          {/* Languages live */}
          <div className="mt-6 flex items-center gap-3">
            <span className="text-[12.5px] font-medium text-text-tertiary">Languages live</span>
            <div className="flex items-center gap-2">
              {LANGS.map(({ flag, code }) => (
                <span
                  key={code}
                  className="flex items-center gap-1.5 rounded-full border border-white/[0.06] bg-white/[0.02] px-2.5 py-1 text-[12px] font-medium"
                >
                  <span className="text-[13px] leading-none">{flag}</span>
                  {code}
                </span>
              ))}
              <button className="flex items-center gap-1 rounded-full border border-dashed border-white/15 px-2.5 py-1 text-[12px] text-text-tertiary">
                <Plus className="h-3 w-3" strokeWidth={2.5} />
                Add language
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
