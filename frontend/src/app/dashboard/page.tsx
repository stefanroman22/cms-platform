"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { FolderOpen } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import { getLastProjectSlug } from "@/lib/lastProject";

interface Project {
  id: string;
  name: string;
  slug: string;
}

function fetchProjects(): Promise<Project[]> {
  return fetch("/api/projects", { credentials: "include", cache: "no-store" }).then((r) => {
    if (!r.ok) throw new Error("Failed to load projects.");
    return r.json();
  });
}

/**
 * The dashboard root no longer renders a "Projects Overview" screen — the
 * sidebar owns project switching now. This page only decides which project
 * workspace to land on: the last one the user opened (localStorage), or the
 * first project as a default.
 */
export default function DashboardIndexPage() {
  const router = useRouter();
  const {
    data: projects,
    loading,
    error,
  } = useQuery<Project[]>("projects", fetchProjects, {
    ttl: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (!Array.isArray(projects) || projects.length === 0) return;
    const stored = getLastProjectSlug();
    const target = projects.find((p) => p.slug === stored) ?? projects[0];
    router.replace(`/dashboard/${target.slug}`);
  }, [projects, router]);

  const hasProjects = Array.isArray(projects) && projects.length > 0;

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4 md:p-8">
      {error && !hasProjects ? (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      ) : !loading && !hasProjects ? (
        <div className="flex flex-col items-center text-center">
          <FolderOpen className="mb-3 h-8 w-8 text-zinc-300 dark:text-zinc-600" />
          <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">No projects yet.</p>
          <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
            Projects will appear here once active.
          </p>
        </div>
      ) : (
        <div
          role="status"
          aria-label="Opening your project"
          className="flex items-center gap-3 text-zinc-500 dark:text-zinc-400"
        >
          <ArcSpinner size={22} />
          <p className="text-xs font-medium tracking-wide">Opening your project…</p>
        </div>
      )}
    </div>
  );
}
