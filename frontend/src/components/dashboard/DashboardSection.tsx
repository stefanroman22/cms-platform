"use client";

import { AnimatePresence, motion } from "motion/react";
import {
  BarChart3,
  ArrowRight,
  Globe,
  ExternalLink,
  Users,
  Eye,
  Clock,
  FileText,
  type LucideIcon,
} from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import { dashboardSectionCardCn, dashboardPrimaryBtnCn } from "@/lib/styles";

interface ProjectInfo {
  name: string;
  slug: string;
  website_url?: string | null;
}

function fetchProjects(): Promise<ProjectInfo[]> {
  return fetch(`/api/projects`, { credentials: "include", cache: "no-store" }).then((r) =>
    r.json()
  );
}

type SettingsFromApi = { website_url: string | null; allowed_origins: string[] | null };

/** The stat slots real analytics will fill in later. Keeping them visible as
 *  ghosts now means the layout doesn't change when the data arrives — each
 *  tile just swaps its "—" for a number. */
const KPI_SLOTS: { label: string; icon: LucideIcon }[] = [
  { label: "Visitors", icon: Users },
  { label: "Page views", icon: Eye },
  { label: "Avg. visit", icon: Clock },
  { label: "Top page", icon: FileText },
];

// Static ghost sparkline for the chart placeholder (heights in %).
const GHOST_BARS = [35, 55, 30, 70, 45, 85, 60, 40, 75, 50, 90, 65];

interface DashboardSectionProps {
  projectSlug: string;
  isAdmin: boolean;
  onGoToCms: () => void;
}

/**
 * Default landing section: the live-website card up top (the project's most
 * useful link), then the analytics frame — ghost KPI tiles and a placeholder
 * chart — that Vercel data will fill in later without a layout change.
 */
export function DashboardSection({ projectSlug, isAdmin, onGoToCms }: DashboardSectionProps) {
  // Shared cache keys with the sidebar ("projects") and the Settings section
  // (`settings:<slug>`), so both queries are usually instant cache hits.
  const { data: projectsList, loading: projectsLoading } = useQuery<ProjectInfo[]>(
    "projects",
    fetchProjects,
    { ttl: 5 * 60 * 1000 }
  );
  const project = Array.isArray(projectsList)
    ? projectsList.find((p) => p.slug === projectSlug)
    : undefined;

  // Admin fallback: admins can open projects that aren't in their own
  // /projects list, so the live URL comes from the settings endpoint instead.
  const { data: settingsRaw } = useQuery<SettingsFromApi>(
    `settings:${projectSlug}`,
    () =>
      fetch(`/api/projects/${projectSlug}/settings`, { credentials: "include" }).then((r) =>
        r.json()
      ),
    { ttl: 5 * 60 * 1000, enabled: isAdmin }
  );

  const projectInList = project !== undefined;
  const liveUrl = project?.website_url || settingsRaw?.website_url || null;
  const adminFallbackPending = isAdmin && !projectInList && settingsRaw === null;
  const liveUrlLoading = (projectsLoading && !projectInList) || adminFallbackPending;

  return (
    <div className="space-y-4">
      {/* ── Live website ─────────────────────────────────────────────────── */}
      <AnimatePresence mode="wait" initial={false}>
        {liveUrlLoading ? (
          <motion.div
            key="live-url-loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            role="status"
            aria-busy="true"
            aria-label="Loading live website URL"
            className={`${dashboardSectionCardCn} flex items-center gap-3 px-5 py-4`}
          >
            <ArcSpinner size={22} />
            <p className="text-xs font-medium tracking-wide text-zinc-500 dark:text-zinc-400">
              Loading live website…
            </p>
          </motion.div>
        ) : liveUrl ? (
          <motion.a
            key="live-url-card"
            href={liveUrl}
            target="_blank"
            rel="noopener noreferrer"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }}
            className={`${dashboardSectionCardCn} group flex items-center gap-4 px-5 py-4 transition-colors hover:border-emerald-300 hover:bg-emerald-50/40 dark:hover:border-emerald-800 dark:hover:bg-emerald-950/30`}
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300">
              <Globe aria-hidden="true" className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                <span
                  aria-hidden="true"
                  className="h-1.5 w-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400"
                />
                Live website
              </p>
              <p className="mt-0.5 truncate font-mono text-sm text-zinc-900 dark:text-zinc-100">
                {liveUrl.replace(/^https?:\/\//, "")}
              </p>
              <p className="mt-0.5 text-xs leading-snug text-zinc-500 dark:text-zinc-400">
                This is the public website your visitors see.
              </p>
            </div>
            <span className="flex shrink-0 items-center gap-1.5 text-xs font-medium text-zinc-400 transition-colors group-hover:text-emerald-700 dark:text-zinc-500 dark:group-hover:text-emerald-400">
              <span className="hidden sm:inline">Open site</span>
              <ExternalLink aria-hidden="true" className="h-3.5 w-3.5" />
            </span>
          </motion.a>
        ) : (
          <motion.div
            key="live-url-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="flex items-center gap-4 rounded-xl border border-dashed border-zinc-300 px-5 py-4 dark:border-zinc-700"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-500">
              <Globe aria-hidden="true" className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-zinc-600 dark:text-zinc-300">
                No live website connected yet.
              </p>
              <p className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">
                {isAdmin
                  ? "Set the website URL in this project's Settings."
                  : "It will appear here once your website goes live."}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── KPI slots (ghosts until analytics ship) ──────────────────────── */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {KPI_SLOTS.map(({ label, icon: Icon }) => (
          <div key={label} className={`${dashboardSectionCardCn} p-4`}>
            <div className="flex items-center gap-2 text-zinc-400 dark:text-zinc-500">
              <Icon aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
              <span className="text-[11px] font-semibold uppercase tracking-wider">{label}</span>
            </div>
            <p
              aria-label={`${label}: no data yet`}
              className="mt-2 text-2xl font-semibold tabular-nums text-zinc-300 dark:text-zinc-600"
            >
              —
            </p>
          </div>
        ))}
      </div>

      {/* ── Analytics placeholder ────────────────────────────────────────── */}
      <div className={`${dashboardSectionCardCn} relative`}>
        {/* Ghost chart hinting at what fills this card later. */}
        <div
          aria-hidden="true"
          className="absolute inset-x-8 bottom-0 flex h-24 items-end gap-2 opacity-70"
        >
          {GHOST_BARS.map((h, i) => (
            <div
              key={i}
              style={{ height: `${h}%` }}
              className={`w-full rounded-t-md ${
                h === 90 ? "bg-accent/25 dark:bg-accent/20" : "bg-zinc-100 dark:bg-zinc-800"
              }`}
            />
          ))}
        </div>
        <div className="relative mx-auto flex max-w-md flex-col items-center px-6 pb-24 pt-12 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
            <BarChart3 aria-hidden="true" className="h-6 w-6" />
          </span>
          <span className="mt-4 inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-[11px] font-medium text-indigo-700 dark:border-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-300">
            Coming soon
          </span>
          <h2 className="mt-3 text-base font-semibold text-zinc-900 dark:text-zinc-50">
            Website analytics
          </h2>
          <p className="mt-1.5 text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
            Visitor traffic, page views, and performance metrics from Vercel will appear here. For
            now, jump into your content to make changes.
          </p>
          <button type="button" onClick={onGoToCms} className={`${dashboardPrimaryBtnCn} mt-6`}>
            Go to CMS
            <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
