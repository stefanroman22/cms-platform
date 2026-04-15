"use client";

import { useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { dashboardSectionCardCn } from "@/lib/styles";

interface Issue {
    id: string;
    project_id: string;
    title: string;
    description: string;
    priority: "High" | "Medium" | "Low";
    created_by: string | null;
    created_by_email: string | null;
    created_at: string;
}

interface IssueListProps {
    projectSlug: string;
    refreshTrigger: number;
}

const priorityBadgeCn = {
    High:   "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
    Medium: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
    Low:    "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400",
} as const;

function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString([], {
        day: "numeric", month: "short", year: "numeric",
    });
}

export function IssueList({ projectSlug, refreshTrigger }: IssueListProps) {
    const [issues, setIssues] = useState<Issue[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        async function fetchIssues() {
            setLoading(true);
            setError(null);
            try {
                const res = await fetch(`/api/projects/${projectSlug}/issues`, {
                    credentials: "include",
                    cache: "no-store",
                });
                if (!res.ok) {
                    throw new Error(`Failed to load issues (${res.status})`);
                }
                const data: Issue[] = await res.json();
                if (!cancelled) setIssues(data);
            } catch (err) {
                if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load issues.");
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        fetchIssues();
        return () => { cancelled = true; };
    }, [projectSlug, refreshTrigger]);

    if (loading) {
        return (
            <div className="mt-4 space-y-2">
                {[0, 1, 2].map((i) => (
                    <div
                        key={i}
                        className="h-16 rounded-lg bg-zinc-100 dark:bg-zinc-800 animate-pulse"
                    />
                ))}
            </div>
        );
    }

    if (error) {
        return (
            <div className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-400">
                {error}
            </div>
        );
    }

    return (
        <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500 mb-3">
                {issues.length} {issues.length === 1 ? "Issue" : "Issues"} reported
            </h3>

            {issues.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                    <CheckCircle2 className="h-8 w-8 text-zinc-300 dark:text-zinc-600 mb-2" />
                    <p className="text-sm text-zinc-400 dark:text-zinc-500">No issues reported. All good!</p>
                </div>
            ) : (
                <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
                    {issues.map((issue) => (
                        <div key={issue.id} className="px-5 py-4 flex items-start gap-4">
                            {/* Priority badge — left side */}
                            <span
                                className={`mt-0.5 shrink-0 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${priorityBadgeCn[issue.priority]}`}
                            >
                                {issue.priority}
                            </span>

                            {/* Content — center */}
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50 truncate">
                                    {issue.title}
                                </p>
                                <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400 line-clamp-2 whitespace-pre-wrap">
                                    {issue.description}
                                </p>
                            </div>

                            {/* Meta — right side */}
                            <div className="shrink-0 text-right">
                                <p className="text-xs text-zinc-400 dark:text-zinc-500">
                                    {issue.created_by_email ?? "Unknown"}
                                </p>
                                <p className="text-xs text-zinc-400 dark:text-zinc-500">
                                    {formatDate(issue.created_at)}
                                </p>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
