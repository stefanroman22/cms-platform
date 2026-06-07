"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { X, Save, Trash2, Loader2 } from "lucide-react";
import { dashboardInputCn, dashboardFieldLabelCn } from "@/lib/styles";
import { createResource, patchResource, deleteResource } from "./api";
import type { BookingResource } from "./api";

interface Props {
  projectSlug: string;
  resource: BookingResource | null; // null = "add new"
  onClose: () => void;
  onSaved: () => void;
}

type Draft = {
  name: string;
  type: string;
  capacity: string;
  is_active: boolean;
  sort_order: string;
};

function resourceToDraft(r: BookingResource): Draft {
  return {
    name: r.name,
    type: r.type ?? "generic",
    capacity: String(r.capacity ?? 1),
    is_active: r.is_active ?? true,
    sort_order: String(r.sort_order ?? 0),
  };
}

const emptyDraft: Draft = {
  name: "",
  type: "generic",
  capacity: "1",
  is_active: true,
  sort_order: "0",
};

const DRAWER_VARIANTS = {
  hidden: { x: "100%" },
  visible: { x: 0 },
};

const BACKDROP_VARIANTS = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

/**
 * Add/edit resource drawer — mirrors LeadDetailDrawer pattern.
 */
export function ResourceFormDrawer({ projectSlug, resource, onClose, onSaved }: Props) {
  return (
    <AnimatePresence>
      <>
        <motion.div
          key="backdrop"
          variants={BACKDROP_VARIANTS}
          initial="hidden"
          animate="visible"
          exit="hidden"
          transition={{ duration: 0.18, ease: "easeOut" }}
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/40"
        />
        <motion.aside
          key="drawer"
          variants={DRAWER_VARIANTS}
          initial="hidden"
          animate="visible"
          exit="hidden"
          transition={{ duration: 0.22, ease: "easeOut" }}
          className="no-scrollbar fixed right-0 top-0 z-50 h-full w-full overflow-y-auto bg-white shadow-2xl dark:bg-zinc-950 md:w-[36rem]"
        >
          <DrawerBody
            projectSlug={projectSlug}
            resource={resource}
            onClose={onClose}
            onSaved={onSaved}
          />
        </motion.aside>
      </>
    </AnimatePresence>
  );
}

function DrawerBody({ projectSlug, resource, onClose, onSaved }: Props) {
  const isNew = resource === null;
  const [draft, setDraft] = useState<Draft>(resource ? resourceToDraft(resource) : emptyDraft);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const prefersReduced = useReducedMotion();
  const press = prefersReduced ? {} : { whileTap: { scale: 0.97 } };

  useEffect(() => {
    setDraft(resource ? resourceToDraft(resource) : emptyDraft);
    setError(null);
    setConfirmDelete(false);
  }, [resource?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function setField<K extends keyof Draft>(k: K, v: Draft[K]) {
    setDraft((d) => ({ ...d, [k]: v }));
    setError(null);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const body = {
        name: draft.name.trim(),
        type: draft.type,
        capacity: parseInt(draft.capacity, 10) || 1,
        is_active: draft.is_active,
        sort_order: parseInt(draft.sort_order, 10) || 0,
      };
      if (isNew) {
        await createResource(projectSlug, body);
      } else {
        await patchResource(projectSlug, resource!.id, body);
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!resource) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteResource(projectSlug, resource.id);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  return (
    <div className="p-5">
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
          {isNew ? "Add resource" : "Edit resource"}
        </h2>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => {
              handleSave().catch(() => {});
            }}
            disabled={saving || deleting}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            <Save className="h-3.5 w-3.5" />
            Save
          </button>
          {!isNew && (
            <motion.button
              {...press}
              type="button"
              onClick={() => setConfirmDelete(true)}
              disabled={saving || deleting}
              aria-label="Delete resource"
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950/40"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </motion.button>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {confirmDelete && (
          <motion.div
            key="confirm-delete"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: prefersReduced ? 0 : 0.24, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-3 dark:border-red-900 dark:bg-red-950/40">
              <p className="text-xs text-red-700 dark:text-red-300">
                Delete <span className="font-semibold">{resource?.name}</span> permanently? If the
                resource has bookings, deactivate it instead.
              </p>
              <div className="mt-2.5 flex items-center gap-2">
                <motion.button
                  {...press}
                  type="button"
                  onClick={() => {
                    handleDelete().catch(() => {});
                  }}
                  disabled={deleting}
                  className="inline-flex cursor-pointer items-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {deleting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                  {deleting ? "Deleting…" : "Delete permanently"}
                </motion.button>
                <motion.button
                  {...press}
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                  disabled={deleting}
                  className="cursor-pointer rounded-md border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  Cancel
                </motion.button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="mt-5 space-y-4">
        <div>
          <label className={dashboardFieldLabelCn}>Name</label>
          <input
            type="text"
            value={draft.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="Staff"
            className={dashboardInputCn}
          />
        </div>

        <div>
          <label className={dashboardFieldLabelCn}>Type</label>
          <select
            value={draft.type}
            onChange={(e) => setField("type", e.target.value)}
            className={dashboardInputCn}
          >
            <option value="staff">Staff</option>
            <option value="room">Room</option>
            <option value="equipment">Equipment</option>
            <option value="generic">Generic</option>
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={dashboardFieldLabelCn}>Capacity</label>
            <input
              type="number"
              min={1}
              value={draft.capacity}
              onChange={(e) => setField("capacity", e.target.value)}
              className={dashboardInputCn}
            />
          </div>
          <div>
            <label className={dashboardFieldLabelCn}>Sort order</label>
            <input
              type="number"
              min={0}
              value={draft.sort_order}
              onChange={(e) => setField("sort_order", e.target.value)}
              className={dashboardInputCn}
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <label className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Active</label>
          <button
            type="button"
            role="switch"
            aria-checked={draft.is_active}
            onClick={() => setField("is_active", !draft.is_active)}
            className={`relative inline-flex h-5 w-9 cursor-pointer items-center rounded-full transition-colors ${
              draft.is_active ? "bg-zinc-900 dark:bg-zinc-100" : "bg-zinc-200 dark:bg-zinc-700"
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform dark:bg-zinc-900 ${
                draft.is_active ? "translate-x-4" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>
      </div>
    </div>
  );
}
