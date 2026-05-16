"use client";

import { useEffect } from "react";

interface PublishConfirmModalProps {
  open: boolean;
  count: number;
  projectName: string;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function PublishConfirmModal({
  open,
  count,
  projectName,
  busy = false,
  onCancel,
  onConfirm,
}: PublishConfirmModalProps) {
  useEffect(() => {
    if (!open) return;
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape" && !busy) onCancel();
    }
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="publish-confirm-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={busy ? undefined : onCancel}
    >
      <div
        className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id="publish-confirm-title"
          className="text-lg font-semibold text-zinc-900 dark:text-zinc-100"
        >
          Publish changes?
        </h2>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Publish {count} {count === 1 ? "change" : "changes"} to production?{" "}
          <span className="font-medium text-zinc-900 dark:text-zinc-100">{projectName}</span> will
          update within about 1 minute.
        </p>

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            className="cursor-pointer rounded-md border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className="cursor-pointer rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            {busy ? "Publishing…" : "Publish"}
          </button>
        </div>
      </div>
    </div>
  );
}
