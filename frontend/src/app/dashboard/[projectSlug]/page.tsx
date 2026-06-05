"use client";

import Link from "next/link";
import { use } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ChevronRight, Globe, ExternalLink } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { useUser } from "@/context/user";
import { PreviewPublishBar } from "@/components/dashboard/PreviewPublishBar";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import { SectionRail } from "@/components/dashboard/SectionRail";
import { SectionPanel } from "@/components/dashboard/SectionPanel";
import { DashboardSection } from "@/components/dashboard/DashboardSection";
import { CmsSection } from "@/components/dashboard/CmsSection";
import { AutoFixSection } from "@/components/dashboard/AutoFixSection";
import { ProjectSettingsSection } from "@/components/dashboard/ProjectSettingsSection";
import { visibleSections } from "@/components/dashboard/sectionConfig";
import { useProjectView } from "@/components/dashboard/hooks/useProjectView";

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

export default function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ projectSlug: string }>;
}) {
  const { projectSlug } = use(params);
  const { user } = useUser();
  const isAdmin = user?.is_admin ?? false;

  // Shared cache key with the projects-overview page: both read the same
  // array; this page derives its single project locally.
  const { data: projectsList, loading: projectsLoading } = useQuery<ProjectInfo[]>(
    "projects",
    fetchProjects,
    { ttl: 5 * 60 * 1000 }
  );

  const project = Array.isArray(projectsList)
    ? projectsList.find((p) => p.slug === projectSlug)
    : undefined;
  const projectName = project?.name ?? projectSlug;

  // Live-website card fallback for admins viewing another owner's project
  // (where `project` is absent from /projects). Shares the `settings:<slug>`
  // cache key with ProjectSettingsSection. Read-only here.
  const { data: settingsRaw } = useQuery<SettingsFromApi>(
    `settings:${projectSlug}`,
    () =>
      fetch(`/api/projects/${projectSlug}/settings`, { credentials: "include" }).then((r) =>
        r.json()
      ),
    { ttl: 5 * 60 * 1000, enabled: isAdmin }
  );

  const { activeView, setView } = useProjectView(isAdmin);
  const sections = visibleSections(isAdmin);

  return (
    <div className="p-4 md:p-8">
      <PreviewPublishBar projectSlug={projectSlug} projectName={project?.name ?? projectSlug} />

      {/* Breadcrumb */}
      <div className="mb-6 flex items-center gap-1.5 text-sm text-zinc-400 dark:text-zinc-500">
        <Link
          href="/dashboard"
          className="flex items-center gap-1 transition-colors hover:text-zinc-700 dark:hover:text-zinc-300"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Projects
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="font-medium text-zinc-700 dark:text-zinc-200">{projectName}</span>
      </div>

      <div className="mb-8">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{projectName}</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Manage content and settings for this project.
        </p>

        {/* Live website card (unchanged behavior). */}
        {(() => {
          const projectInList = project !== undefined;
          const liveUrl = project?.website_url || settingsRaw?.website_url || null;
          const adminFallbackPending = isAdmin && !projectInList && settingsRaw === undefined;
          const liveUrlLoading = (projectsLoading && !projectInList) || adminFallbackPending;
          if (!liveUrlLoading && !liveUrl) return null;

          return (
            <div className="mt-4 w-full max-w-xl">
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
                    className="flex items-center gap-3 rounded-lg border border-zinc-200 bg-white/40 px-4 py-3 text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-200"
                  >
                    <ArcSpinner size={22} />
                    <p className="text-xs font-medium tracking-wide text-zinc-500 dark:text-zinc-400">
                      Loading live website…
                    </p>
                  </motion.div>
                ) : (
                  liveUrl && (
                    <motion.a
                      key="live-url-card"
                      href={liveUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }}
                      className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-white px-4 py-3 transition-colors hover:border-emerald-300 hover:bg-emerald-50/40 dark:border-zinc-800 dark:bg-zinc-900/40 dark:hover:border-emerald-800 dark:hover:bg-emerald-950/30"
                    >
                      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300">
                        <Globe className="h-3.5 w-3.5" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                          Live website
                        </p>
                        <p className="mt-0.5 truncate font-mono text-sm text-zinc-900 dark:text-zinc-100">
                          {liveUrl.replace(/^https?:\/\//, "")}
                        </p>
                        <p className="mt-1 text-xs leading-snug text-zinc-500 dark:text-zinc-400">
                          This is the public website your visitors see.
                        </p>
                      </div>
                      <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-zinc-400 dark:text-zinc-500" />
                    </motion.a>
                  )
                )}
              </AnimatePresence>
            </div>
          );
        })()}
      </div>

      {/* ── Section shell: rail + animated panel ───────────────────────── */}
      <div className="flex flex-col gap-6 md:flex-row md:gap-8">
        <div className="md:w-56 md:shrink-0">
          <div className="md:sticky md:top-24">
            <SectionRail sections={sections} activeView={activeView} onSelect={setView} />
          </div>
        </div>

        <SectionPanel activeView={activeView}>
          {activeView === "dashboard" && <DashboardSection onGoToCms={() => setView("cms")} />}
          {activeView === "cms" && <CmsSection projectSlug={projectSlug} isAdmin={isAdmin} />}
          {activeView === "autofix" && (
            <AutoFixSection
              projectSlug={projectSlug}
              isAdmin={isAdmin}
              currentUserId={user?.id ?? null}
            />
          )}
          {activeView === "settings" && isAdmin && (
            <ProjectSettingsSection projectSlug={projectSlug} />
          )}
        </SectionPanel>
      </div>
    </div>
  );
}
