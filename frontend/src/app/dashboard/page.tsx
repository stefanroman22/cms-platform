"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, FolderOpen, ExternalLink, ArrowRight } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { PageHeader } from "@/components/dashboard/PageHeader";

interface Project {
    id: string;
    name: string;
    description: string | null;
    slug: string;
    is_active: boolean;
    created_at: string;
    website_url?: string | null;
}

function fetchProjects(): Promise<Project[]> {
    return fetch("/api/projects", { credentials: "include", cache: "no-store" }).then((r) => {
        if (!r.ok) throw new Error("Failed to load projects.");
        return r.json();
    });
}

export default function ProjectsOverviewPage() {
    const { data: projects, loading, error } = useQuery<Project[]>(
        "projects",
        fetchProjects,
        { ttl: 2 * 60 * 1000, refetchInterval: 2 * 60 * 1000 }
    );

    const [search, setSearch] = useState("");

    const filtered = (projects ?? []).filter((p) =>
        p.name.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="p-8">
            <PageHeader title="Projects" description="All active projects associated with your account." />

            {/* Search */}
            <div className="relative mb-6 max-w-sm">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400 dark:text-zinc-500" />
                <input
                    type="text"
                    placeholder="Search by name…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full rounded-lg border border-zinc-200 bg-white py-2 pl-9 pr-4 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-400 focus:outline-none focus:ring-0 transition-colors dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500 dark:focus:border-zinc-500"
                />
            </div>

            {error && (
                <p className="mb-6 text-sm text-red-600 dark:text-red-400">{error}</p>
            )}

            {/* Loading skeleton — only shown on first load (no cache) */}
            {loading && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {[...Array(3)].map((_, i) => (
                        <div key={i} className="h-36 rounded-xl border border-zinc-200 bg-white animate-pulse dark:border-zinc-800 dark:bg-zinc-900" />
                    ))}
                </div>
            )}

            {/* Empty state */}
            {!loading && filtered.length === 0 && (
                <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white py-16 text-center dark:border-zinc-700 dark:bg-zinc-900">
                    <FolderOpen className="h-8 w-8 text-zinc-300 mb-3 dark:text-zinc-600" />
                    <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                        {search ? "No projects match your search." : "No projects yet."}
                    </p>
                    {!search && (
                        <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">Projects will appear here once active.</p>
                    )}
                </div>
            )}

            {/* Grid */}
            {!loading && filtered.length > 0 && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {filtered.map((project) => (
                        <Link
                            key={project.id}
                            href={`/dashboard/${project.slug}`}
                            className="group rounded-xl border border-zinc-200 bg-white p-5 shadow-sm transition-all hover:shadow-md hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:shadow-none dark:hover:border-zinc-700 flex flex-col"
                        >
                            <div className="flex items-start justify-between gap-2">
                                <h3 className="font-medium text-zinc-900 leading-snug group-hover:text-zinc-700 dark:text-zinc-100 dark:group-hover:text-zinc-200">
                                    {project.name}
                                </h3>
                                <span className="shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400">
                                    Active
                                </span>
                            </div>
                            {project.description && (
                                <p className="mt-2 text-sm text-zinc-500 leading-relaxed line-clamp-2 dark:text-zinc-400">
                                    {project.description}
                                </p>
                            )}
                            <div className="mt-4 flex items-center justify-between">
                                <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs text-zinc-500 font-mono dark:bg-zinc-800 dark:text-zinc-400">
                                    /{project.slug}
                                </span>
                                <div className="flex items-center gap-2">
                                    {project.website_url && (
                                        <a
                                            href={project.website_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            onClick={(e) => e.stopPropagation()}
                                            className="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-700 dark:text-zinc-500 dark:hover:text-zinc-300 transition-colors"
                                            title="Open website"
                                        >
                                            <ExternalLink className="h-3.5 w-3.5" />
                                        </a>
                                    )}
                                    <ArrowRight className="h-3.5 w-3.5 text-zinc-300 group-hover:text-zinc-500 transition-colors dark:text-zinc-600 dark:group-hover:text-zinc-400" />
                                </div>
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
}
