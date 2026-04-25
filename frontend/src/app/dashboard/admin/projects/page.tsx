"use client";

import Link from "next/link";
import { use } from "react";
import { FolderKanban, ArrowRight } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { dashboardSectionCardCn } from "@/lib/styles";

interface AdminProject {
    id: string;
    name: string;
    slug: string;
    is_active: boolean;
    created_at: string;
    user_id: string;
    user_email: string | null;
    user_full_name: string | null;
}

function fetchAdminProjects(): Promise<AdminProject[]> {
    return fetch("/api/admin/projects", { credentials: "include", cache: "no-store" }).then((r) => {
        if (!r.ok) throw new Error("Failed to load projects.");
        return r.json();
    });
}

export default function AdminProjectsPage({
    searchParams,
}: {
    searchParams: Promise<{ user?: string }>;
}) {
    const { user: filterUserId } = use(searchParams);

    const { data: projects, loading, error } = useQuery<AdminProject[]>(
        "admin:projects",
        fetchAdminProjects,
        { ttl: 60 * 1000 }
    );

    const filtered = filterUserId
        ? (projects ?? []).filter((p) => p.user_id === filterUserId)
        : (projects ?? []);

    const filterClient = filterUserId
        ? (projects ?? []).find((p) => p.user_id === filterUserId)
        : null;

    return (
        <div className="p-4 md:p-8">
            <PageHeader
                title="All Projects"
                description={
                    filterClient
                        ? `Showing projects for ${filterClient.user_email ?? filterUserId}`
                        : "Every project across all clients."
                }
            />

            {filterUserId && (
                <div className="mb-6">
                    <Link
                        href="/dashboard/admin/projects"
                        className="text-xs text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
                    >
                        ← Show all projects
                    </Link>
                </div>
            )}

            {error && <p className="mb-6 text-sm text-red-600 dark:text-red-400">{error}</p>}

            {loading && (
                <div className="h-48 rounded-xl border border-zinc-200 bg-white animate-pulse dark:border-zinc-800 dark:bg-zinc-900" />
            )}

            {!loading && filtered.length === 0 && (
                <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white py-16 text-center dark:border-zinc-700 dark:bg-zinc-900">
                    <FolderKanban className="h-8 w-8 text-zinc-300 mb-3 dark:text-zinc-600" />
                    <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">No projects found.</p>
                </div>
            )}

            {!loading && filtered.length > 0 && (
                <div className={dashboardSectionCardCn}>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-zinc-100 dark:border-zinc-800">
                                <th className="px-5 py-3 text-left text-xs font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">Project</th>
                                <th className="px-5 py-3 text-left text-xs font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">Client</th>
                                <th className="px-5 py-3 text-left text-xs font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">Slug</th>
                                <th className="px-5 py-3 text-left text-xs font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">Created</th>
                                <th className="px-5 py-3" />
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                            {filtered.map((project) => (
                                <tr key={project.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
                                    <td className="px-5 py-3.5">
                                        <span className="font-medium text-zinc-900 dark:text-zinc-100">{project.name}</span>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <p className="text-zinc-700 dark:text-zinc-300">{project.user_full_name ?? "—"}</p>
                                        <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-0.5">{project.user_email}</p>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <span className="font-mono text-xs rounded-md bg-zinc-100 px-2 py-0.5 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                                            /{project.slug}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3.5 text-zinc-500 dark:text-zinc-400">
                                        {new Date(project.created_at).toLocaleDateString("en-GB", {
                                            day: "numeric", month: "short", year: "numeric",
                                        })}
                                    </td>
                                    <td className="px-5 py-3.5 text-right">
                                        <Link
                                            href={`/dashboard/${project.slug}`}
                                            className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
                                        >
                                            Open <ArrowRight className="h-3.5 w-3.5" />
                                        </Link>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
