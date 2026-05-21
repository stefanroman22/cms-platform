"use client";

import { useEffect, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Pencil, Save, X } from "lucide-react";
import { editReveal, errorBlip } from "@/lib/animations";
import { useEditingSection } from "../context/EditingSectionContext";

export interface EditableSectionShellProps {
  /** Stable id, used as the EditingSectionContext slot key. */
  id: string;
  title: string;
  readView: ReactNode;
  editView: ReactNode;
  onSave: () => Promise<void> | void;
  onCancel: () => void;
  saving: boolean;
  error: string | null;
  canSave: boolean;
}

export function EditableSectionShell({
  id,
  title,
  readView,
  editView,
  onSave,
  onCancel,
  saving,
  error,
  canSave,
}: EditableSectionShellProps) {
  const { isEditing, requestEdit, release } = useEditingSection(id);

  function handleStartEdit() {
    requestEdit();
  }

  function handleCancel() {
    onCancel();
    release();
  }

  async function handleSave() {
    try {
      await onSave();
      release();
    } catch {
      // error is surfaced via the `error` prop; stay in edit mode.
    }
  }

  // ESC closes edit mode; Cmd/Ctrl+S saves.
  useEffect(() => {
    if (!isEditing) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        handleCancel();
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (canSave && !saving) void handleSave();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditing, canSave, saving]);

  return (
    <section className="mt-5 group">
      <div className="flex items-center justify-between mb-2 min-h-[1.25rem]">
        <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold">
          {title}
        </h3>
        {isEditing ? (
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleCancel}
              disabled={saving}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-md text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <X className="h-3 w-3" />
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={!canSave || saving}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-md bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
            >
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
              Save
            </button>
          </div>
        ) : (
          <button
            type="button"
            aria-label={`Edit ${title}`}
            onClick={handleStartEdit}
            className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity inline-flex items-center justify-center h-6 w-6 rounded-md text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <AnimatePresence initial={false}>
        {error && (
          <motion.div
            key="err"
            variants={errorBlip}
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="mb-2 rounded-md bg-red-50 dark:bg-red-950 px-3 py-1.5 text-xs text-red-700 dark:text-red-300"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="sync" initial={false}>
        {isEditing ? (
          <motion.div
            key="edit"
            variants={editReveal}
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="overflow-hidden"
          >
            {editView}
          </motion.div>
        ) : (
          <motion.div
            key="read"
            variants={editReveal}
            initial="hidden"
            animate="visible"
            exit="hidden"
            className="overflow-hidden"
          >
            {readView}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
