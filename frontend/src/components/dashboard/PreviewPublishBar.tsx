"use client";

import { useCallback, useEffect, useState } from "react";
import { ExternalLink, CheckCircle2 } from "lucide-react";
import { PublishConfirmModal } from "./PublishConfirmModal";

interface ProjectStatus {
    unpublished_count: number;
    last_published_at: string | null;
    preview_url: string | null;
    production_url: string | null;
}

interface PreviewPublishBarProps {
    projectSlug: string;
    projectName?: string;
}

const POLL_MS = 30_000;

async function fetchStatus(slug: string): Promise<ProjectStatus> {
    const r = await fetch(`/api/projects/${slug}/status`, {
        credentials: "include",
        cache: "no-store",
    });
    if (!r.ok) throw new Error(`status fetch failed: ${r.status}`);
    return r.json();
}

async function postPublish(slug: string): Promise<{ published_count: number; last_published_at: string }> {
    const r = await fetch(`/api/projects/${slug}/publish`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
    });
    if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail ?? "Publish failed.");
    }
    return r.json();
}

function timeAgo(iso: string | null): string | null {
    if (!iso) return null;
    const delta = (Date.now() - new Date(iso).getTime()) / 1000;
    if (delta < 60) return "just now";
    if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
    if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
    return `${Math.floor(delta / 86400)}d ago`;
}

export function PreviewPublishBar({ projectSlug, projectName = "Project" }: PreviewPublishBarProps) {
    const [status, setStatus] = useState<ProjectStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [modalOpen, setModalOpen] = useState(false);
    const [publishing, setPublishing] = useState(false);
    const [toast, setToast] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

    const refresh = useCallback(async () => {
        try {
            const s = await fetchStatus(projectSlug);
            setStatus(s);
        } catch {
            // Leave old status; visible via console
        } finally {
            setLoading(false);
        }
    }, [projectSlug]);

    useEffect(() => {
        refresh();
        const id = setInterval(refresh, POLL_MS);
        return () => clearInterval(id);
    }, [refresh]);

    useEffect(() => {
        if (!toast) return;
        const id = setTimeout(() => setToast(null), 4000);
        return () => clearTimeout(id);
    }, [toast]);

    async function handleConfirm() {
        setPublishing(true);
        try {
            const result = await postPublish(projectSlug);
            setModalOpen(false);
            setToast({ kind: "ok", text: `Published ${result.published_count} change${result.published_count === 1 ? "" : "s"} — live within 60 seconds.` });
            await refresh();
        } catch (err) {
            setToast({ kind: "err", text: err instanceof Error ? err.message : "Publish failed." });
        } finally {
            setPublishing(false);
        }
    }

    const count = status?.unpublished_count ?? 0;
    const hasPreview = !!status?.preview_url;
    const lastPublished = timeAgo(status?.last_published_at ?? null);

    return (
        <>
            <div className="sticky top-0 z-30 -mx-8 mb-6 flex items-center justify-between gap-4 border-b border-zinc-200 bg-white/90 px-8 py-3 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
                <button
                    type="button"
                    disabled={!hasPreview || loading}
                    onClick={() => status?.preview_url && window.open(status.preview_url, "_blank", "noopener,noreferrer")}
                    title={hasPreview ? "Open preview in a new tab" : "Preview not set up — contact admin"}
                    className="cursor-pointer inline-flex items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
                >
                    <ExternalLink className="h-4 w-4" />
                    See Preview
                </button>

                <div className="flex items-center gap-3">
                    {count > 0 && (
                        <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                            {count} unpublished {count === 1 ? "change" : "changes"}
                        </span>
                    )}
                    <div className="flex flex-col items-end">
                        <button
                            type="button"
                            disabled={count === 0 || publishing || loading}
                            onClick={() => setModalOpen(true)}
                            className="cursor-pointer inline-flex items-center gap-2 rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
                        >
                            <CheckCircle2 className="h-4 w-4" />
                            Publish Changes
                        </button>
                        {lastPublished && (
                            <span className="mt-0.5 text-[10px] text-zinc-400 dark:text-zinc-500">
                                Last published {lastPublished}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            <PublishConfirmModal
                open={modalOpen}
                count={count}
                projectName={projectName}
                busy={publishing}
                onCancel={() => setModalOpen(false)}
                onConfirm={handleConfirm}
            />

            {toast && (
                <div
                    className={
                        "fixed bottom-4 right-4 z-50 rounded-md px-4 py-2 text-sm font-medium shadow-lg " +
                        (toast.kind === "ok"
                            ? "bg-emerald-600 text-white"
                            : "bg-red-600 text-white")
                    }
                >
                    {toast.text}
                </div>
            )}
        </>
    );
}
