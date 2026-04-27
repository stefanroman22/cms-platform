"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
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

    // Count-tag popover ("You have X unpublished changes"). Tapping the tag
    // toggles it; auto-dismisses after 2.5s and closes on outside click.
    const [countPopoverOpen, setCountPopoverOpen] = useState(false);
    const countWrapperRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (!countPopoverOpen) return;
        const dismiss = setTimeout(() => setCountPopoverOpen(false), 2500);
        const onDocClick = (e: MouseEvent) => {
            if (!countWrapperRef.current?.contains(e.target as Node)) {
                setCountPopoverOpen(false);
            }
        };
        document.addEventListener("mousedown", onDocClick);
        return () => {
            clearTimeout(dismiss);
            document.removeEventListener("mousedown", onDocClick);
        };
    }, [countPopoverOpen]);

    return (
        <>
            {/* Sticky bar — h-16 matches Sidebar brand height. The negative
                top margin (-mt-4 md:-mt-8) cancels the parent page padding so
                the bar sits flush with the scroll-container top at rest, not
                only after scrolling. As a result the bottom border stays on
                the same Y as the sidebar divider regardless of scroll.

                Internally arranged as two stacked rows so the See Preview and
                Publish Changes buttons share the same baseline (Y) on every
                screen size. "Last published" lives in row 2, right-aligned. */}
            <div className="sticky top-0 z-30 -mx-4 -mt-4 md:-mx-8 md:-mt-8 mb-6 flex h-16 flex-col justify-center gap-2 border-b border-zinc-200 bg-white/90 px-4 md:px-8 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
                <div className="flex items-center justify-between gap-3">
                    <button
                        type="button"
                        disabled={!hasPreview || loading}
                        onClick={() => status?.preview_url && window.open(status.preview_url, "_blank", "noopener,noreferrer")}
                        title={hasPreview ? "Open preview in a new tab" : "Preview not set up — contact admin"}
                        className="cursor-pointer inline-flex shrink-0 items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
                    >
                        <ExternalLink className="h-4 w-4" />
                        <span className="hidden sm:inline">See Preview</span>
                        <span className="sm:hidden">Preview</span>
                    </button>

                    <div className="flex items-center gap-2">
                        {count > 0 && (
                            <div ref={countWrapperRef} className="relative">
                                <button
                                    type="button"
                                    onClick={() => setCountPopoverOpen((s) => !s)}
                                    aria-label={`${count} unpublished change${count === 1 ? "" : "s"}`}
                                    className="cursor-pointer inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-amber-100 px-1.5 text-[11px] font-bold tabular-nums text-amber-800 transition-colors hover:bg-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:hover:bg-amber-900/60"
                                >
                                    {count}
                                </button>
                                <AnimatePresence>
                                    {countPopoverOpen && (
                                        <motion.div
                                            initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                            animate={{ opacity: 1, y: 0, scale: 1 }}
                                            exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                            transition={{ duration: 0.15, ease: "easeOut" }}
                                            role="status"
                                            className="absolute bottom-full left-1/2 z-40 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white shadow-lg dark:bg-zinc-100 dark:text-zinc-900"
                                        >
                                            You have {count} unpublished change{count === 1 ? "" : "s"}
                                            <span className="absolute left-1/2 top-full -translate-x-1/2 border-x-4 border-t-4 border-x-transparent border-t-zinc-900 dark:border-t-zinc-100" />
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        )}
                        <button
                            type="button"
                            disabled={count === 0 || publishing || loading}
                            onClick={() => setModalOpen(true)}
                            className="cursor-pointer inline-flex shrink-0 items-center gap-2 rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
                        >
                            <CheckCircle2 className="h-4 w-4" />
                            <span className="hidden sm:inline">Publish Changes</span>
                            <span className="sm:hidden">Publish</span>
                        </button>
                    </div>
                </div>

                {lastPublished && (
                    <p className="text-right text-xs leading-none text-zinc-500 dark:text-zinc-400">
                        Last published {lastPublished}
                    </p>
                )}
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
