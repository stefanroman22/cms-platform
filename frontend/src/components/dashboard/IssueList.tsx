"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Pencil, Trash2, X, Save } from "lucide-react";
import {
    dashboardSectionCardCn,
    dashboardInputCn,
    dashboardFieldLabelCn,
    dashboardErrorBannerCn,
} from "@/lib/styles";

type Priority = "High" | "Medium" | "Low";
type IssueStatus = "pending" | "in_progress" | "done";
type SortMode = "priority" | "date";

interface Issue {
    id: string;
    project_id: string;
    title: string;
    description: string;
    priority: Priority;
    status: IssueStatus;
    created_by: string | null;
    created_by_email: string | null;
    created_at: string;
}

export interface IssueListProps {
    projectSlug: string;
    refreshTrigger: number;
    isAdmin: boolean;
    currentUserId: string | null;
}

const PRIORITY_ORDER: Record<Priority, number> = { High: 0, Medium: 1, Low: 2 };

const priorityBadgeCn: Record<Priority, string> = {
    High:   "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400",
    Medium: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
    Low:    "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400",
};

const prioritySelectedCn: Record<Priority, string> = {
    High:   "bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-400",
    Medium: "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-400",
    Low:    "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-400",
};

const priorityUnselectedCn =
    "bg-white dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800";

const SECTIONS: { status: IssueStatus; label: string; color: string }[] = [
    { status: "pending",     label: "Open",        color: "text-zinc-600 dark:text-zinc-400" },
    { status: "in_progress", label: "In Progress", color: "text-amber-600 dark:text-amber-400" },
    { status: "done",        label: "Done",        color: "text-emerald-600 dark:text-emerald-400" },
];

const STATUS_TRANSITIONS: Record<IssueStatus, { label: string; next: IssueStatus }[]> = {
    pending:     [{ label: "Start",   next: "in_progress" }, { label: "Resolve", next: "done" }],
    in_progress: [{ label: "Resolve", next: "done" },        { label: "Reopen",  next: "pending" }],
    done:        [{ label: "Reopen",  next: "pending" }],
};

function sortIssues(issues: Issue[], mode: SortMode): Issue[] {
    return [...issues].sort((a, b) => {
        if (mode === "priority") {
            const pd = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
            if (pd !== 0) return pd;
            const dd = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
            if (dd !== 0) return dd;
            return a.title.localeCompare(b.title);
        } else {
            const dd = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
            if (dd !== 0) return dd;
            const pd = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
            if (pd !== 0) return pd;
            return a.title.localeCompare(b.title);
        }
    });
}

function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString([], {
        day: "numeric", month: "short", year: "numeric",
    });
}

export function IssueList({
    projectSlug,
    refreshTrigger,
    isAdmin,
    currentUserId,
}: IssueListProps) {
    const [issues, setIssues] = useState<Issue[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [sortMode, setSortMode] = useState<SortMode>("priority");

    // Inline edit state
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editTitle, setEditTitle] = useState("");
    const [editDescription, setEditDescription] = useState("");
    const [editPriority, setEditPriority] = useState<Priority>("Medium");
    const [editSaving, setEditSaving] = useState(false);
    const [editError, setEditError] = useState<string | null>(null);

    // Action states
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [updatingStatusId, setUpdatingStatusId] = useState<string | null>(null);

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
                if (!res.ok) throw new Error(`Failed to load issues (${res.status})`);
                const data: Issue[] = await res.json();
                if (!cancelled) setIssues(data);
            } catch (err) {
                if (!cancelled)
                    setError(err instanceof Error ? err.message : "Failed to load issues.");
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        fetchIssues();
        return () => {
            cancelled = true;
        };
    }, [projectSlug, refreshTrigger]);

    function startEdit(issue: Issue) {
        setEditingId(issue.id);
        setEditTitle(issue.title);
        setEditDescription(issue.description);
        setEditPriority(issue.priority);
        setEditError(null);
    }

    function cancelEdit() {
        setEditingId(null);
        setEditError(null);
    }

    async function saveEdit(issueId: string) {
        setEditSaving(true);
        setEditError(null);
        try {
            const res = await fetch(`/api/projects/${projectSlug}/issues/${issueId}`, {
                method: "PATCH",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: editTitle.trim(),
                    description: editDescription.trim(),
                    priority: editPriority,
                }),
            });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.detail ?? `Save failed (${res.status})`);
            }
            const updated: Issue = await res.json();
            setIssues((prev) => prev.map((i) => (i.id === issueId ? updated : i)));
            setEditingId(null);
        } catch (err) {
            setEditError(err instanceof Error ? err.message : "Save failed.");
        } finally {
            setEditSaving(false);
        }
    }

    async function deleteIssue(issueId: string) {
        if (!confirm("Delete this issue? This cannot be undone.")) return;
        setDeletingId(issueId);
        try {
            await fetch(`/api/projects/${projectSlug}/issues/${issueId}`, {
                method: "DELETE",
                credentials: "include",
            });
            setIssues((prev) => prev.filter((i) => i.id !== issueId));
        } finally {
            setDeletingId(null);
        }
    }

    async function updateStatus(issueId: string, newStatus: IssueStatus) {
        setUpdatingStatusId(issueId);
        try {
            const res = await fetch(
                `/api/projects/${projectSlug}/issues/${issueId}/status`,
                {
                    method: "PATCH",
                    credentials: "include",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ status: newStatus }),
                }
            );
            if (!res.ok) return;
            const updated: Issue = await res.json();
            setIssues((prev) => prev.map((i) => (i.id === issueId ? updated : i)));
        } finally {
            setUpdatingStatusId(null);
        }
    }

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
        return <div className={`mt-4 ${dashboardErrorBannerCn}`}>{error}</div>;
    }

    const sorted = sortIssues(issues, sortMode);

    return (
        <div className="mt-4">
            {/* Header: count + sort toggle */}
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                    {issues.length} {issues.length === 1 ? "Issue" : "Issues"}
                </h3>
                <div className="flex gap-1">
                    {(["priority", "date"] as SortMode[]).map((mode) => (
                        <button
                            key={mode}
                            type="button"
                            onClick={() => setSortMode(mode)}
                            className={[
                                "px-2.5 py-1 text-xs rounded-md font-medium transition-colors cursor-pointer",
                                sortMode === mode
                                    ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                                    : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700",
                            ].join(" ")}
                        >
                            {mode === "priority" ? "By Priority" : "By Date"}
                        </button>
                    ))}
                </div>
            </div>

            {issues.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                    <CheckCircle2 className="h-8 w-8 text-zinc-300 dark:text-zinc-600 mb-2" />
                    <p className="text-sm text-zinc-400 dark:text-zinc-500">
                        No issues reported. All good!
                    </p>
                </div>
            ) : (
                <div className="space-y-6">
                    {SECTIONS.map(({ status, label, color }) => {
                        const sectionIssues = sorted.filter((i) => i.status === status);
                        return (
                            <div key={status}>
                                <p
                                    className={`text-xs font-semibold uppercase tracking-wider mb-2 ${color}`}
                                >
                                    {label} ({sectionIssues.length})
                                </p>
                                {sectionIssues.length === 0 ? (
                                    <p className="text-xs text-zinc-400 dark:text-zinc-500 pl-1">
                                        No issues here.
                                    </p>
                                ) : (
                                    <div
                                        className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}
                                    >
                                        {sectionIssues.map((issue) => {
                                            const canEdit =
                                                isAdmin || issue.created_by === currentUserId;
                                            const isEditing = editingId === issue.id;
                                            const isDeleting = deletingId === issue.id;
                                            const isUpdatingStatus =
                                                updatingStatusId === issue.id;

                                            if (isEditing) {
                                                return (
                                                    <div
                                                        key={issue.id}
                                                        className="px-5 py-4 space-y-3"
                                                    >
                                                        {editError && (
                                                            <p className={dashboardErrorBannerCn}>
                                                                {editError}
                                                            </p>
                                                        )}
                                                        <div>
                                                            <label
                                                                className={dashboardFieldLabelCn}
                                                            >
                                                                Title
                                                            </label>
                                                            <input
                                                                type="text"
                                                                value={editTitle}
                                                                onChange={(e) =>
                                                                    setEditTitle(e.target.value)
                                                                }
                                                                className={dashboardInputCn}
                                                                autoFocus
                                                            />
                                                        </div>
                                                        <div>
                                                            <label
                                                                className={dashboardFieldLabelCn}
                                                            >
                                                                Description
                                                            </label>
                                                            <textarea
                                                                rows={4}
                                                                value={editDescription}
                                                                onChange={(e) =>
                                                                    setEditDescription(
                                                                        e.target.value
                                                                    )
                                                                }
                                                                className={`${dashboardInputCn} resize-none`}
                                                            />
                                                        </div>
                                                        <div>
                                                            <label
                                                                className={dashboardFieldLabelCn}
                                                            >
                                                                Priority
                                                            </label>
                                                            <div className="flex gap-0 rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden">
                                                                {(
                                                                    [
                                                                        "High",
                                                                        "Medium",
                                                                        "Low",
                                                                    ] as Priority[]
                                                                ).map((p) => (
                                                                    <button
                                                                        key={p}
                                                                        type="button"
                                                                        onClick={() =>
                                                                            setEditPriority(p)
                                                                        }
                                                                        className={`flex-1 py-1.5 text-sm font-medium transition-colors cursor-pointer ${
                                                                            editPriority === p
                                                                                ? prioritySelectedCn[p]
                                                                                : priorityUnselectedCn
                                                                        }`}
                                                                    >
                                                                        {p}
                                                                    </button>
                                                                ))}
                                                            </div>
                                                        </div>
                                                        <div className="flex gap-2 justify-end">
                                                            <button
                                                                type="button"
                                                                onClick={cancelEdit}
                                                                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors cursor-pointer"
                                                            >
                                                                <X className="h-3.5 w-3.5" />
                                                                Cancel
                                                            </button>
                                                            <button
                                                                type="button"
                                                                onClick={() => saveEdit(issue.id)}
                                                                disabled={
                                                                    editSaving ||
                                                                    !editTitle.trim()
                                                                }
                                                                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-zinc-900 text-white hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                                                            >
                                                                <Save className="h-3.5 w-3.5" />
                                                                {editSaving ? "Saving…" : "Save"}
                                                            </button>
                                                        </div>
                                                    </div>
                                                );
                                            }

                                            return (
                                                <div
                                                    key={issue.id}
                                                    className="px-5 py-4 flex items-start gap-4"
                                                >
                                                    {/* Priority badge */}
                                                    <span
                                                        className={`mt-0.5 shrink-0 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${priorityBadgeCn[issue.priority]}`}
                                                    >
                                                        {issue.priority}
                                                    </span>

                                                    {/* Content + admin status buttons */}
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50 truncate">
                                                            {issue.title}
                                                        </p>
                                                        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400 line-clamp-2 whitespace-pre-wrap">
                                                            {issue.description}
                                                        </p>
                                                        {isAdmin && (
                                                            <div className="mt-2 flex gap-1.5 flex-wrap">
                                                                {STATUS_TRANSITIONS[
                                                                    issue.status
                                                                ].map(
                                                                    ({ label: btnLabel, next }) => (
                                                                        <button
                                                                            key={next}
                                                                            type="button"
                                                                            disabled={
                                                                                isUpdatingStatus
                                                                            }
                                                                            onClick={() =>
                                                                                updateStatus(
                                                                                    issue.id,
                                                                                    next
                                                                                )
                                                                            }
                                                                            className="px-2.5 py-0.5 text-xs rounded-full border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                                                                        >
                                                                            {btnLabel}
                                                                        </button>
                                                                    )
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>

                                                    {/* Meta + edit/delete actions */}
                                                    <div className="shrink-0 text-right space-y-1">
                                                        <p className="text-xs text-zinc-400 dark:text-zinc-500">
                                                            {issue.created_by_email ?? "Unknown"}
                                                        </p>
                                                        <p className="text-xs text-zinc-400 dark:text-zinc-500">
                                                            {formatDate(issue.created_at)}
                                                        </p>
                                                        {canEdit && (
                                                            <div className="flex gap-1 justify-end mt-1">
                                                                <button
                                                                    type="button"
                                                                    onClick={() => startEdit(issue)}
                                                                    className="flex items-center justify-center h-7 w-7 rounded-md text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                                                                    aria-label="Edit issue"
                                                                >
                                                                    <Pencil className="h-3.5 w-3.5" />
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    disabled={isDeleting}
                                                                    onClick={() =>
                                                                        deleteIssue(issue.id)
                                                                    }
                                                                    className="flex items-center justify-center h-7 w-7 rounded-md text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                                                                    aria-label="Delete issue"
                                                                >
                                                                    <Trash2 className="h-3.5 w-3.5" />
                                                                </button>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
