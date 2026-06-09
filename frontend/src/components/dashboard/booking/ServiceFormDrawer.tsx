"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { X, Save, Trash2, Loader2 } from "lucide-react";
import { dashboardInputCn, dashboardFieldLabelCn } from "@/lib/styles";
import { createService, patchService, deleteService } from "./api";
import type { BookingService, BookingResource } from "./api";

interface Props {
  projectSlug: string;
  service: BookingService | null; // null = "add new"
  resources: BookingResource[];
  onClose: () => void;
  onSaved: () => void;
}

type Draft = {
  name: string;
  description: string;
  color: string;
  duration_min: string;
  price: string;
  buffer_before_min: string;
  buffer_after_min: string;
  lead_time_min: string;
  max_advance_days: string;
  is_active: boolean;
  sort_order: string;
  resource_ids: string[];
};

function serviceToDraft(s: BookingService): Draft {
  return {
    name: s.name,
    description: s.description ?? "",
    color: s.color ?? "",
    duration_min: String(s.duration_min),
    price: s.price != null ? String(s.price) : "",
    buffer_before_min: String(s.buffer_before_min ?? 0),
    buffer_after_min: String(s.buffer_after_min ?? 0),
    lead_time_min: String(s.lead_time_min ?? 0),
    max_advance_days: String(s.max_advance_days ?? 60),
    is_active: s.is_active ?? true,
    sort_order: String(s.sort_order ?? 0),
    resource_ids: s.resource_ids ?? [],
  };
}

const emptyDraft: Draft = {
  name: "",
  description: "",
  color: "",
  duration_min: "30",
  price: "",
  buffer_before_min: "0",
  buffer_after_min: "0",
  lead_time_min: "0",
  max_advance_days: "60",
  is_active: true,
  sort_order: "0",
  resource_ids: [],
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
 * Add/edit service drawer — mirrors LeadDetailDrawer pattern.
 * `service === null` means "add new".
 */
export function ServiceFormDrawer({ projectSlug, service, resources, onClose, onSaved }: Props) {
  return (
    <AnimatePresence>
      {(service !== null || service === null) && (
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
              service={service}
              resources={resources}
              onClose={onClose}
              onSaved={onSaved}
            />
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function DrawerBody({ projectSlug, service, resources, onClose, onSaved }: Props) {
  const isNew = service === null;
  const [draft, setDraft] = useState<Draft>(service ? serviceToDraft(service) : emptyDraft);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const prefersReduced = useReducedMotion();
  const press = prefersReduced ? {} : { whileTap: { scale: 0.97 } };

  useEffect(() => {
    setDraft(service ? serviceToDraft(service) : emptyDraft);
    setError(null);
    setConfirmDelete(false);
  }, [service?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function setField<K extends keyof Draft>(k: K, v: Draft[K]) {
    setDraft((d) => ({ ...d, [k]: v }));
    setError(null);
  }

  function toggleResource(id: string) {
    setDraft((d) => ({
      ...d,
      resource_ids: d.resource_ids.includes(id)
        ? d.resource_ids.filter((r) => r !== id)
        : [...d.resource_ids, id],
    }));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const body = {
        name: draft.name.trim(),
        description: draft.description.trim(),
        color: draft.color.trim(),
        duration_min: parseInt(draft.duration_min, 10) || 30,
        price: draft.price.trim() === "" ? null : parseFloat(draft.price),
        buffer_before_min: parseInt(draft.buffer_before_min, 10) || 0,
        buffer_after_min: parseInt(draft.buffer_after_min, 10) || 0,
        lead_time_min: parseInt(draft.lead_time_min, 10) || 0,
        max_advance_days: parseInt(draft.max_advance_days, 10) || 60,
        is_active: draft.is_active,
        sort_order: parseInt(draft.sort_order, 10) || 0,
        resource_ids: draft.resource_ids,
      };
      if (isNew) {
        await createService(projectSlug, body);
      } else {
        await patchService(projectSlug, service!.id, body);
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
    if (!service) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteService(projectSlug, service.id);
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
          {isNew ? "Add service" : "Edit service"}
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
              aria-label="Delete service"
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
                Delete <span className="font-semibold">{service?.name}</span> permanently? If the
                service has bookings, deactivate it instead.
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
            placeholder="Consultation"
            className={dashboardInputCn}
          />
        </div>

        <div>
          <label className={dashboardFieldLabelCn}>Description</label>
          <textarea
            rows={2}
            value={draft.description}
            onChange={(e) => setField("description", e.target.value)}
            className={`${dashboardInputCn} resize-none`}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={dashboardFieldLabelCn}>Duration (min)</label>
            <input
              type="number"
              min={5}
              step={5}
              value={draft.duration_min}
              onChange={(e) => setField("duration_min", e.target.value)}
              className={dashboardInputCn}
            />
          </div>
          <div>
            <label className={dashboardFieldLabelCn}>Price (€)</label>
            <input
              type="number"
              min={0}
              step="0.01"
              value={draft.price}
              onChange={(e) => setField("price", e.target.value)}
              placeholder="e.g. 25 — shown to customers"
              className={dashboardInputCn}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={dashboardFieldLabelCn}>Color</label>
            <input
              type="text"
              value={draft.color}
              onChange={(e) => setField("color", e.target.value)}
              placeholder="#4f46e5"
              className={dashboardInputCn}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={dashboardFieldLabelCn}>Buffer before (min)</label>
            <input
              type="number"
              min={0}
              value={draft.buffer_before_min}
              onChange={(e) => setField("buffer_before_min", e.target.value)}
              className={dashboardInputCn}
            />
          </div>
          <div>
            <label className={dashboardFieldLabelCn}>Buffer after (min)</label>
            <input
              type="number"
              min={0}
              value={draft.buffer_after_min}
              onChange={(e) => setField("buffer_after_min", e.target.value)}
              className={dashboardInputCn}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={dashboardFieldLabelCn}>Lead time (min)</label>
            <input
              type="number"
              min={0}
              value={draft.lead_time_min}
              onChange={(e) => setField("lead_time_min", e.target.value)}
              className={dashboardInputCn}
            />
          </div>
          <div>
            <label className={dashboardFieldLabelCn}>Max advance (days)</label>
            <input
              type="number"
              min={1}
              value={draft.max_advance_days}
              onChange={(e) => setField("max_advance_days", e.target.value)}
              className={dashboardInputCn}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
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
          <div className="flex items-center justify-between pt-5">
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

        {resources.length > 0 && (
          <div>
            <label className={dashboardFieldLabelCn}>Which staff can perform this service</label>
            <div className="space-y-1.5">
              {resources.map((r) => (
                <label
                  key={r.id}
                  className="flex cursor-pointer items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300"
                >
                  <input
                    type="checkbox"
                    checked={draft.resource_ids.includes(r.id)}
                    onChange={() => toggleResource(r.id)}
                    className="h-4 w-4 rounded border-zinc-300 accent-zinc-900 dark:border-zinc-600"
                  />
                  {r.name}
                  {r.type && (
                    <span className="text-xs text-zinc-400 dark:text-zinc-500">({r.type})</span>
                  )}
                </label>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
