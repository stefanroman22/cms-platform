"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { X, Loader2, Save } from "lucide-react";
import { dashboardInputCn, dashboardFieldLabelCn } from "@/lib/styles";
import { createAppointment, getAvailability } from "./api";
import type { BookingService, AvailabilitySlot } from "./api";

interface Props {
  projectSlug: string;
  services: BookingService[];
  timezone: string | null;
  onClose: () => void;
  onCreated: () => void;
}

const DRAWER_VARIANTS = {
  hidden: { x: "100%" },
  visible: { x: 0 },
};

const BACKDROP_VARIANTS = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

export function NewAppointmentDrawer({
  projectSlug,
  services,
  timezone,
  onClose,
  onCreated,
}: Props) {
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
            services={services}
            timezone={timezone}
            onClose={onClose}
            onCreated={onCreated}
          />
        </motion.aside>
      </>
    </AnimatePresence>
  );
}

type Step = "service" | "slot" | "customer";

interface Draft {
  serviceId: string;
  date: string;
  selectedSlot: string;
  customerName: string;
  customerEmail: string;
  customerPhone: string;
  note: string;
}

const emptyDraft: Draft = {
  serviceId: "",
  date: "",
  selectedSlot: "",
  customerName: "",
  customerEmail: "",
  customerPhone: "",
  note: "",
};

function DrawerBody({ projectSlug, services, timezone, onClose, onCreated }: Props) {
  const prefersReduced = useReducedMotion();
  const press = prefersReduced ? {} : { whileTap: { scale: 0.97 } };

  const [step, setStep] = useState<Step>("service");
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [slots, setSlots] = useState<AvailabilitySlot[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function setField<K extends keyof Draft>(k: K, v: Draft[K]) {
    setDraft((d) => ({ ...d, [k]: v }));
    setError(null);
  }

  // Fetch slots when service + date change (on the slot step)
  useEffect(() => {
    if (step !== "slot" || !draft.serviceId || !draft.date) {
      setSlots([]);
      setDraft((d) => ({ ...d, selectedSlot: "" }));
      return;
    }

    let cancelled = false;
    setSlotsLoading(true);
    setSlots([]);
    setDraft((d) => ({ ...d, selectedSlot: "" }));
    setError(null);

    getAvailability(projectSlug, draft.serviceId, draft.date, draft.date)
      .then((res) => {
        if (cancelled) return;
        const daySlots = res.slots ?? res.days?.find((d) => d.date === draft.date)?.slots ?? [];
        setSlots(daySlots);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load slots.");
      })
      .finally(() => {
        if (!cancelled) setSlotsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [step, draft.serviceId, draft.date, projectSlug]);

  function goToSlotStep() {
    if (!draft.serviceId) {
      setError("Please select a service.");
      return;
    }
    setError(null);
    setStep("slot");
  }

  function goToCustomerStep() {
    if (!draft.selectedSlot) {
      setError("Please select a slot.");
      return;
    }
    setError(null);
    setStep("customer");
  }

  async function handleCreate() {
    if (!draft.customerName.trim()) {
      setError("Customer name is required.");
      return;
    }
    if (!draft.customerEmail.trim()) {
      setError("Customer email is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createAppointment(projectSlug, {
        service_id: draft.serviceId,
        start_utc: draft.selectedSlot,
        customer: {
          name: draft.customerName.trim(),
          email: draft.customerEmail.trim(),
          phone: draft.customerPhone.trim() || undefined,
        },
        note: draft.note.trim() || undefined,
      });
      onCreated();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create appointment.");
    } finally {
      setSaving(false);
    }
  }

  const selectedService = services.find((s) => s.id === draft.serviceId);

  return (
    <div className="p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">New appointment</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Step indicator */}
      <div className="mt-4 flex items-center gap-2 text-xs text-zinc-400 dark:text-zinc-500">
        <StepDot active={step === "service"} done={step !== "service"} label="Service" />
        <span>›</span>
        <StepDot active={step === "slot"} done={step === "customer"} label="Date & slot" />
        <span>›</span>
        <StepDot active={step === "customer"} done={false} label="Customer" />
      </div>

      {/* Error banner */}
      <AnimatePresence initial={false}>
        {error && (
          <motion.div
            key="error"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: prefersReduced ? 0 : 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950 dark:text-red-300">
              {error}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Step: service */}
      {step === "service" && (
        <div className="mt-5 space-y-4">
          <div>
            <label className={dashboardFieldLabelCn}>Service</label>
            <select
              value={draft.serviceId}
              onChange={(e) => setField("serviceId", e.target.value)}
              className={dashboardInputCn}
            >
              <option value="">Select a service…</option>
              {services.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.duration_min} min)
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end">
            <motion.button
              {...press}
              type="button"
              onClick={goToSlotStep}
              className="cursor-pointer rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-700 dark:hover:bg-zinc-600"
            >
              Next: pick a slot →
            </motion.button>
          </div>
        </div>
      )}

      {/* Step: date + slot */}
      {step === "slot" && (
        <div className="mt-5 space-y-4">
          {selectedService && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Service:{" "}
              <span className="font-medium text-zinc-700 dark:text-zinc-300">
                {selectedService.name}
              </span>{" "}
              ({selectedService.duration_min} min)
            </p>
          )}
          <div>
            <label className={dashboardFieldLabelCn}>Date</label>
            <input
              type="date"
              value={draft.date}
              onChange={(e) => setField("date", e.target.value)}
              className={`${dashboardInputCn} max-w-xs`}
            />
          </div>
          {slotsLoading && (
            <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading slots…
            </div>
          )}
          {!slotsLoading && draft.date && slots.length === 0 && (
            <p className="text-xs text-zinc-400 dark:text-zinc-500">
              No available slots on this date.
            </p>
          )}
          {!slotsLoading && slots.length > 0 && (
            <div>
              <label className={dashboardFieldLabelCn}>Available slots</label>
              <div className="flex flex-wrap gap-1.5">
                {slots.map((slot) => {
                  const label = new Intl.DateTimeFormat("en-GB", {
                    timeZone: timezone ?? "UTC",
                    timeStyle: "short",
                  }).format(new Date(slot.start_utc));
                  return (
                    <button
                      key={slot.start_utc}
                      type="button"
                      onClick={() => setField("selectedSlot", slot.start_utc)}
                      className={`cursor-pointer rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                        draft.selectedSlot === slot.start_utc
                          ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                          : "border-zinc-200 text-zinc-600 hover:border-zinc-400 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-zinc-500"
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => {
                setStep("service");
                setError(null);
              }}
              className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              ← Back
            </button>
            <motion.button
              {...press}
              type="button"
              onClick={goToCustomerStep}
              className="cursor-pointer rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-700 dark:hover:bg-zinc-600"
            >
              Next: customer info →
            </motion.button>
          </div>
        </div>
      )}

      {/* Step: customer */}
      {step === "customer" && (
        <div className="mt-5 space-y-4">
          {selectedService && draft.selectedSlot && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Booking{" "}
              <span className="font-medium text-zinc-700 dark:text-zinc-300">
                {selectedService.name}
              </span>{" "}
              at{" "}
              <span className="font-medium text-zinc-700 dark:text-zinc-300">
                {new Intl.DateTimeFormat("en-GB", {
                  timeZone: timezone ?? "UTC",
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(draft.selectedSlot))}
              </span>
            </p>
          )}
          <div>
            <label className={dashboardFieldLabelCn}>Customer name *</label>
            <input
              type="text"
              value={draft.customerName}
              onChange={(e) => setField("customerName", e.target.value)}
              placeholder="Jane Smith"
              className={dashboardInputCn}
            />
          </div>
          <div>
            <label className={dashboardFieldLabelCn}>Email *</label>
            <input
              type="email"
              value={draft.customerEmail}
              onChange={(e) => setField("customerEmail", e.target.value)}
              placeholder="jane@example.com"
              className={dashboardInputCn}
            />
          </div>
          <div>
            <label className={dashboardFieldLabelCn}>Phone (optional)</label>
            <input
              type="tel"
              value={draft.customerPhone}
              onChange={(e) => setField("customerPhone", e.target.value)}
              placeholder="+40 700 000 000"
              className={dashboardInputCn}
            />
          </div>
          <div>
            <label className={dashboardFieldLabelCn}>Note (optional)</label>
            <textarea
              rows={2}
              value={draft.note}
              onChange={(e) => setField("note", e.target.value)}
              className={`${dashboardInputCn} resize-none`}
            />
          </div>
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => {
                setStep("slot");
                setError(null);
              }}
              className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              ← Back
            </button>
            <motion.button
              {...press}
              type="button"
              onClick={() => {
                handleCreate().catch(() => {});
              }}
              disabled={saving}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
            >
              {saving ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              {saving ? "Creating…" : "Create appointment"}
            </motion.button>
          </div>
        </div>
      )}
    </div>
  );
}

function StepDot({ active, done, label }: { active: boolean; done: boolean; label: string }) {
  return (
    <span
      className={`text-xs font-medium ${
        active
          ? "text-zinc-900 dark:text-zinc-100"
          : done
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-zinc-400 dark:text-zinc-500"
      }`}
    >
      {label}
    </span>
  );
}
