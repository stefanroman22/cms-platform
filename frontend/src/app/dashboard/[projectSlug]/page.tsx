"use client";

import { use, useEffect, useRef, useCallback } from "react";
import { useQuery } from "@/hooks/useQuery";
import { useUser } from "@/context/user";
import { PreviewPublishBar } from "@/components/dashboard/PreviewPublishBar";
import { SectionRail } from "@/components/dashboard/SectionRail";
import { SectionPanel } from "@/components/dashboard/SectionPanel";
import { DashboardSection } from "@/components/dashboard/DashboardSection";
import { CmsSection } from "@/components/dashboard/CmsSection";
import { AutoFixSection } from "@/components/dashboard/AutoFixSection";
import { ProjectSettingsSection } from "@/components/dashboard/ProjectSettingsSection";
import { BookingsSection } from "@/components/dashboard/booking/BookingsSection";
import { SeoSection } from "@/components/dashboard/seo/SeoSection";
import { visibleSections, type SectionKey } from "@/components/dashboard/sectionConfig";
import { useProjectView } from "@/components/dashboard/hooks/useProjectView";
import { setLastProjectSlug } from "@/lib/lastProject";
import { getSettings as getBookingSettings } from "@/components/dashboard/booking/api";
import { getOverview as getSeoOverview } from "@/components/dashboard/seo/api";

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

export default function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ projectSlug: string }>;
}) {
  const { projectSlug } = use(params);
  const { user } = useUser();
  const isAdmin = user?.is_admin ?? false;

  // Shared cache key with the sidebar's projects list: both read the same
  // array; this page derives its single project locally.
  const { data: projectsList } = useQuery<ProjectInfo[]>("projects", fetchProjects, {
    ttl: 5 * 60 * 1000,
  });

  const project = Array.isArray(projectsList)
    ? projectsList.find((p) => p.slug === projectSlug)
    : undefined;
  const projectName = project?.name ?? projectSlug;

  // Remember this project so /dashboard reopens it next visit.
  useEffect(() => {
    setLastProjectSlug(projectSlug);
  }, [projectSlug]);

  const { data: bookingSettings } = useQuery(
    `booking-settings:${projectSlug}`,
    () => getBookingSettings(projectSlug),
    { ttl: 60 * 1000 }
  );
  const { data: seoOverview } = useQuery(
    `seo-overview:${projectSlug}`,
    () => getSeoOverview(projectSlug),
    { ttl: 60 * 1000 }
  );
  const caps = {
    bookingEnabled: !!bookingSettings?.enabled,
    seoEnabled: !!seoOverview?.enabled,
  };

  const { activeView, setView } = useProjectView(isAdmin, caps);
  const sections = visibleSections(isAdmin, caps);

  // Section tabs sit directly above the inline CMS editor, so a single click
  // (or rail arrow key) would silently discard an unsaved draft. The editor
  // reports its dirty state up; switching away from CMS confirms first.
  const cmsEditorDirtyRef = useRef(false);
  const handleEditorDirtyChange = useCallback((dirty: boolean) => {
    cmsEditorDirtyRef.current = dirty;
  }, []);
  const handleSelectView = useCallback(
    (view: SectionKey) => {
      if (
        view !== "cms" &&
        cmsEditorDirtyRef.current &&
        !confirm("You have unsaved changes. Leave the editor without saving?")
      ) {
        return;
      }
      setView(view);
    },
    [setView]
  );

  return (
    <div className="p-4 md:p-8">
      <PreviewPublishBar projectSlug={projectSlug} projectName={project?.name ?? projectSlug} />

      {/* Project header — the name is the page's anchor, written big. */}
      <div className="mb-6 md:mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-zinc-900 md:text-3xl dark:text-zinc-50">
          {projectName}
        </h1>
        <p className="mt-1.5 text-sm text-zinc-500 dark:text-zinc-400">
          Manage content and settings for this project.
        </p>
      </div>

      {/* ── Horizontal section tabs + animated panel below ──────────────── */}
      <SectionRail sections={sections} activeView={activeView} onSelect={handleSelectView} />

      <div className="mt-6">
        <SectionPanel activeView={activeView}>
          {activeView === "dashboard" && (
            <DashboardSection
              projectSlug={projectSlug}
              isAdmin={isAdmin}
              onGoToCms={() => setView("cms")}
            />
          )}
          {activeView === "cms" && (
            <CmsSection
              projectSlug={projectSlug}
              isAdmin={isAdmin}
              onEditorDirtyChange={handleEditorDirtyChange}
            />
          )}
          {activeView === "autofix" && (
            <AutoFixSection
              projectSlug={projectSlug}
              isAdmin={isAdmin}
              currentUserId={user?.id ?? null}
            />
          )}
          {activeView === "bookings" && (
            <BookingsSection projectSlug={projectSlug} isAdmin={isAdmin} />
          )}
          {activeView === "seo" && <SeoSection projectSlug={projectSlug} isAdmin={isAdmin} />}
          {activeView === "settings" && isAdmin && (
            <ProjectSettingsSection projectSlug={projectSlug} />
          )}
        </SectionPanel>
      </div>
    </div>
  );
}
