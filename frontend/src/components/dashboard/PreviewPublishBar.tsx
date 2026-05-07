"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, CheckCircle2, Check } from "lucide-react";
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

async function postPublish(
  slug: string
): Promise<{ published_count: number; last_published_at: string }> {
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

export function PreviewPublishBar({
  projectSlug,
  projectName = "Project",
}: PreviewPublishBarProps) {
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
      setToast({
        kind: "ok",
        text: `Published ${result.published_count} change${result.published_count === 1 ? "" : "s"} — live within 60 seconds.`,
      });
      await refresh();
    } catch (err) {
      setToast({ kind: "err", text: err instanceof Error ? err.message : "Publish failed." });
    } finally {
      setPublishing(false);
    }
  }

  const count = status?.unpublished_count ?? 0;
  // Strict: only the dedicated `preview_url` (Vercel preview branch
  // with `CMS_PREVIEW_TOKEN` so unpublished changes render). Never
  // fall back to production — opening the live site under a "See
  // Preview" label would mislead the operator into thinking they
  // were viewing unpublished drafts when they weren't.
  const previewTarget = status?.preview_url ?? null;
  const hasPreview = !!previewTarget;
  const isClean = !loading && count === 0;

  // Count-tag popover ("You have X unpublished changes"). Hover opens it
  // on desktop; tap toggles it on mobile; outside click closes it.
  const [countPopoverOpen, setCountPopoverOpen] = useState(false);
  const countWrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!countPopoverOpen) return;
    const onDocClick = (e: MouseEvent) => {
      if (!countWrapperRef.current?.contains(e.target as Node)) {
        setCountPopoverOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [countPopoverOpen]);

  return (
    <>
      {/* Sticky bar — h-16 matches the Sidebar brand height so the
                buttons inside (vertically centered via items-center) sit at
                the same Y as the "Roman Technologies / Client Portal" logo
                in the sidebar. The negative top margin cancels the parent
                page padding so the bar starts at the scroll-container top
                at rest, keeping its bottom border on the same Y as the
                sidebar divider regardless of scroll.

                "Last published" is rendered just below the bar (outside
                this h-16 container) so it doesn't push the buttons off-
                center vs. the logo. */}
      <div className="sticky top-0 z-30 -mx-4 -mt-4 md:-mx-8 md:-mt-8 mb-6 flex h-16 items-center justify-between gap-3 border-b border-zinc-200 bg-white/90 px-4 md:px-8 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
        {hasPreview && previewTarget ? (
          <a
            href={previewTarget}
            target="_blank"
            rel="noopener noreferrer"
            title="Open preview in a new tab"
            className="cursor-pointer inline-flex shrink-0 items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
          >
            <ExternalLink className="h-4 w-4" />
            <span className="hidden sm:inline">See Preview</span>
            <span className="sm:hidden">Preview</span>
          </a>
        ) : (
          <button
            type="button"
            disabled
            title={loading ? "Loading…" : "Preview not set up — contact admin"}
            className="cursor-not-allowed inline-flex shrink-0 items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
          >
            <ExternalLink className="h-4 w-4" />
            <span className="hidden sm:inline">See Preview</span>
            <span className="sm:hidden">Preview</span>
          </button>
        )}

        <div className="flex items-center gap-2">
          {!loading && (
            <div
              ref={countWrapperRef}
              className="relative"
              onMouseEnter={() => setCountPopoverOpen(true)}
              onMouseLeave={() => setCountPopoverOpen(false)}
            >
              <button
                type="button"
                onClick={() => setCountPopoverOpen((s) => !s)}
                aria-label={
                  isClean
                    ? "All changes are published"
                    : `${count} unpublished change${count === 1 ? "" : "s"}`
                }
                className={`cursor-pointer inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full px-1.5 text-[11px] font-bold tabular-nums transition-colors ${
                  isClean
                    ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-300 dark:hover:bg-emerald-900/60"
                    : "bg-amber-100 text-amber-800 hover:bg-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:hover:bg-amber-900/60"
                }`}
              >
                {isClean ? <Check className="h-3 w-3" strokeWidth={3} /> : count}
              </button>
              <AnimatePresence>
                {countPopoverOpen && (
                  /* Wrapper has pt-2 (no margin) so its
                                       bounding box bridges the visual gap
                                       between the badge and the popover —
                                       prevents mouseLeave from firing while
                                       the cursor crosses into the popover. */
                  <motion.div
                    initial={{ opacity: 0, y: -4, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -4, scale: 0.96 }}
                    transition={{ duration: 0.15, ease: "easeOut" }}
                    className="absolute top-full left-1/2 z-40 -translate-x-1/2 pt-2"
                  >
                    <div
                      role="status"
                      className={`relative whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium shadow-lg ${
                        isClean
                          ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/60 dark:text-emerald-100"
                          : "bg-amber-100 text-amber-900 dark:bg-amber-900/60 dark:text-amber-100"
                      }`}
                    >
                      {isClean
                        ? "All changes are published."
                        : `You have ${count} unpublished change${count === 1 ? "" : "s"}`}
                      {/* Up-pointing tail, color matched to popover bg */}
                      <span
                        className={`absolute bottom-full left-1/2 -translate-x-1/2 border-x-4 border-b-4 border-x-transparent ${
                          isClean
                            ? "border-b-emerald-100 dark:border-b-emerald-900/60"
                            : "border-b-amber-100 dark:border-b-amber-900/60"
                        }`}
                      />
                    </div>
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
            (toast.kind === "ok" ? "bg-emerald-600 text-white" : "bg-red-600 text-white")
          }
        >
          {toast.text}
        </div>
      )}
    </>
  );
}
