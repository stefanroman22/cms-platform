"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { X, Loader2, CalendarClock } from "lucide-react";
import { dashboardInputCn, dashboardFieldLabelCn } from "@/lib/styles";
import { actOnAppointment, getAvailability } from "./api";
import type { BookingAppointment, BookingService, AvailabilitySlot } from "./api";

interface Props {
  projectSlug: string;
  appointment: BookingAppointment;
  services: BookingService[];
  timezone: string | null;
  onClose: () => void;
  onChanged: () => void;
}

const DRAWER_VARIANTS = {
  hidden: { x: "100%" },
  visible: { x: 0 },
};

const BACKDROP_VARIANTS = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

function formatDateTime(utc: string, tz?: string | null): string {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: tz ?? "UTC",
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(utc));
  } catch {
    return utc;
  }
}

const STATUS_BADGE: Record<string, string> = {
  confirmed: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  cancelled: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
  no_show: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  completed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
};

function statusBadgeCn(status: string) {
  return STATUS_BADGE[status] ?? "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400";
}

/**
 * Returns true if no further actions can be taken on this appointment.
 */
function isTerminal(status: string) {
  return status === "cancelled" || status === "completed";
}

export function AppointmentDetailDrawer({
  projectSlug,
  appointment,
  services,
  timezone,
  onClose,
  onChanged,
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
          className="no-scrollbar fixed right-0 top-0 z-50 h-full w-full overflow-y-auto bg-white shadow-2xl dark:bg-zinc-950 md:w-[38rem]"
        >
          <DrawerBody
            projectSlug={projectSlug}
            appointment={appointment}
            services={services}
            timezone={timezone}
            onClose={onClose}
            onChanged={onChanged}
          />
        </motion.aside>
      </>
    </AnimatePresence>
  );
}

type ActionView = "idle" | "cancel" | "reschedule" | "no_show" | "complete";

function DrawerBody({ projectSlug, appointment, services, timezone, onClose, onChanged }: Props) {
  const prefersReduced = useReducedMotion();
  const press = prefersReduced ? {} : { whileTap: { scale: 0.97 } };

  const [actionView, setActionView] = useState<ActionView>("idle");
  const [reason, setReason] = useState("");
  const [rescheduleDate, setRescheduleDate] = useState("");
  const [slots, setSlots] = useState<AvailabilitySlot[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const terminal = isTerminal(appointment.status);

  // Reset state whenever the appointment changes
  useEffect(() => {
    setActionView("idle");
    setReason("");
    setRescheduleDate("");
    setSlots([]);
    setSelectedSlot("");
    setError(null);
  }, [appointment.id]);

  // Fetch slots when reschedule date changes
  useEffect(() => {
    if (actionView !== "reschedule" || !rescheduleDate) {
      setSlots([]);
      setSelectedSlot("");
      return;
    }

    let cancelled = false;
    setSlotsLoading(true);
    setSlots([]);
    setSelectedSlot("");
    setError(null);

    getAvailability(projectSlug, appointment.service_id, rescheduleDate, rescheduleDate)
      .then((res) => {
        if (cancelled) return;
        // Flatten: either res.slots or first day's slots
        const daySlots = res.slots ?? res.days?.find((d) => d.date === rescheduleDate)?.slots ?? [];
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
  }, [actionView, rescheduleDate, projectSlug, appointment.service_id]);

  async function handleAction() {
    setBusy(true);
    setError(null);
    try {
      if (actionView === "cancel") {
        await actOnAppointment(projectSlug, appointment.id, {
          action: "cancel",
          reason: reason.trim() || undefined,
        });
      } else if (actionView === "reschedule") {
        if (!selectedSlot) {
          setError("Please select a slot.");
          setBusy(false);
          return;
        }
        await actOnAppointment(projectSlug, appointment.id, {
          action: "reschedule",
          start_utc: selectedSlot,
        });
      } else if (actionView === "no_show") {
        await actOnAppointment(projectSlug, appointment.id, {
          action: "no_show",
        });
      } else if (actionView === "complete") {
        await actOnAppointment(projectSlug, appointment.id, {
          action: "complete",
        });
      }
      onChanged();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Action failed.";
      // Surface 409 conflict inline
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  function cancelActionView() {
    setActionView("idle");
    setError(null);
    setReason("");
    setRescheduleDate("");
    setSlots([]);
    setSelectedSlot("");
  }

  const service = services.find((s) => s.id === appointment.service_id);

  return (
    <div className="p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <CalendarClock
              className="h-4 w-4 text-zinc-400 dark:text-zinc-500 shrink-0"
              aria-hidden="true"
            />
            <h2 className="truncate text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              {appointment.customer_name ?? "Appointment"}
            </h2>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium capitalize ${statusBadgeCn(
                appointment.status
              )}`}
            >
              {appointment.status.replace("_", "-")}
            </span>
            {appointment.reschedule_count > 0 && (
              <span className="text-xs text-zinc-400 dark:text-zinc-500">
                rescheduled {appointment.reschedule_count}×
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close appointment detail"
          className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Details */}
      <section className="mt-5 space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
          Details
        </h3>
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
          <Row label="Start" value={formatDateTime(appointment.start_utc, timezone)} />
          <Row label="End" value={formatDateTime(appointment.end_utc, timezone)} />
          {service && <Row label="Service" value={service.name} />}
          {appointment.resource_name && <Row label="Resource" value={appointment.resource_name} />}
          {appointment.customer_email && <Row label="Email" value={appointment.customer_email} />}
          {appointment.customer_phone && <Row label="Phone" value={appointment.customer_phone} />}
          {appointment.notes && <Row label="Notes" value={appointment.notes} />}
          {appointment.source && <Row label="Source" value={appointment.source} />}
        </div>
      </section>

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

      {/* Actions */}
      {!terminal && (
        <section className="mt-5">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
            Actions
          </h3>

          {actionView === "idle" && (
            <div className="flex flex-wrap gap-2">
              <motion.button
                {...press}
                type="button"
                onClick={() => setActionView("reschedule")}
                className="cursor-pointer rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                Reschedule
              </motion.button>
              <motion.button
                {...press}
                type="button"
                onClick={() => setActionView("complete")}
                className="cursor-pointer rounded-lg border border-emerald-200 px-3 py-1.5 text-xs font-medium text-emerald-700 transition-colors hover:bg-emerald-50 dark:border-emerald-800 dark:text-emerald-400 dark:hover:bg-emerald-950/40"
              >
                Mark completed
              </motion.button>
              <motion.button
                {...press}
                type="button"
                onClick={() => setActionView("no_show")}
                className="cursor-pointer rounded-lg border border-amber-200 px-3 py-1.5 text-xs font-medium text-amber-700 transition-colors hover:bg-amber-50 dark:border-amber-800 dark:text-amber-400 dark:hover:bg-amber-950/40"
              >
                Mark no-show
              </motion.button>
              <motion.button
                {...press}
                type="button"
                onClick={() => setActionView("cancel")}
                className="cursor-pointer rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950/40"
              >
                Cancel
              </motion.button>
            </div>
          )}

          {/* Cancel form */}
          <AnimatePresence initial={false}>
            {actionView === "cancel" && (
              <motion.div
                key="cancel-form"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: prefersReduced ? 0 : 0.22, ease: "easeOut" }}
                className="overflow-hidden"
              >
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950/30">
                  <p className="mb-2 text-xs font-medium text-red-700 dark:text-red-300">
                    Cancel this appointment?
                  </p>
                  <div className="mb-2">
                    <label className={dashboardFieldLabelCn}>Reason (optional)</label>
                    <input
                      type="text"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="e.g. Customer request"
                      className={dashboardInputCn}
                    />
                  </div>
                  <ActionButtons
                    busy={busy}
                    confirmLabel="Cancel appointment"
                    confirmCn="cursor-pointer rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                    onConfirm={() => {
                      handleAction().catch(() => {});
                    }}
                    onDismiss={cancelActionView}
                    press={press}
                  />
                </div>
              </motion.div>
            )}

            {/* Reschedule form */}
            {actionView === "reschedule" && (
              <motion.div
                key="reschedule-form"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: prefersReduced ? 0 : 0.22, ease: "easeOut" }}
                className="overflow-hidden"
              >
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
                  <p className="mb-2 text-xs font-medium text-zinc-700 dark:text-zinc-300">
                    Pick a new date &amp; slot
                  </p>
                  <div className="mb-3">
                    <label className={dashboardFieldLabelCn}>Date</label>
                    <input
                      type="date"
                      value={rescheduleDate}
                      onChange={(e) => setRescheduleDate(e.target.value)}
                      className={`${dashboardInputCn} max-w-xs`}
                    />
                  </div>
                  {slotsLoading && (
                    <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Loading slots…
                    </div>
                  )}
                  {!slotsLoading && rescheduleDate && slots.length === 0 && (
                    <p className="text-xs text-zinc-400 dark:text-zinc-500">
                      No available slots on this date.
                    </p>
                  )}
                  {!slotsLoading && slots.length > 0 && (
                    <div className="mb-3">
                      <label className={dashboardFieldLabelCn}>Slot</label>
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
                              onClick={() => setSelectedSlot(slot.start_utc)}
                              className={`cursor-pointer rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                                selectedSlot === slot.start_utc
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
                  <ActionButtons
                    busy={busy}
                    confirmLabel="Confirm reschedule"
                    confirmCn="cursor-pointer rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
                    onConfirm={() => {
                      handleAction().catch(() => {});
                    }}
                    onDismiss={cancelActionView}
                    press={press}
                  />
                </div>
              </motion.div>
            )}

            {/* Complete confirm */}
            {actionView === "complete" && (
              <motion.div
                key="complete-form"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: prefersReduced ? 0 : 0.22, ease: "easeOut" }}
                className="overflow-hidden"
              >
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-900 dark:bg-emerald-950/30">
                  <p className="mb-2 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                    Mark this appointment as completed?
                  </p>
                  <ActionButtons
                    busy={busy}
                    confirmLabel="Mark completed"
                    confirmCn="cursor-pointer rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                    onConfirm={() => {
                      handleAction().catch(() => {});
                    }}
                    onDismiss={cancelActionView}
                    press={press}
                  />
                </div>
              </motion.div>
            )}

            {/* No-show confirm */}
            {actionView === "no_show" && (
              <motion.div
                key="noshow-form"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: prefersReduced ? 0 : 0.22, ease: "easeOut" }}
                className="overflow-hidden"
              >
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/30">
                  <p className="mb-2 text-xs font-medium text-amber-700 dark:text-amber-300">
                    Mark this appointment as no-show?
                  </p>
                  <ActionButtons
                    busy={busy}
                    confirmLabel="Mark no-show"
                    confirmCn="cursor-pointer rounded-md bg-amber-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
                    onConfirm={() => {
                      handleAction().catch(() => {});
                    }}
                    onDismiss={cancelActionView}
                    press={press}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>
      )}

      {terminal && (
        <p className="mt-6 text-xs text-zinc-400 dark:text-zinc-500 italic">
          This appointment is {appointment.status} — no further actions available.
        </p>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-baseline gap-3 py-0.5 text-xs">
      <span className="w-20 shrink-0 text-zinc-500 dark:text-zinc-400">{label}</span>
      {value == null || value === "" ? (
        <span className="text-zinc-400 dark:text-zinc-600">—</span>
      ) : (
        <span className="break-words text-zinc-900 dark:text-zinc-100">{value}</span>
      )}
    </div>
  );
}

function ActionButtons({
  busy,
  confirmLabel,
  confirmCn,
  onConfirm,
  onDismiss,
  press,
}: {
  busy: boolean;
  confirmLabel: string;
  confirmCn: string;
  onConfirm: () => void;
  onDismiss: () => void;
  press: object;
}) {
  return (
    <div className="flex items-center gap-2">
      <motion.button
        {...press}
        type="button"
        onClick={onConfirm}
        disabled={busy}
        className={`inline-flex items-center gap-1.5 ${confirmCn}`}
      >
        {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        {busy ? "Working…" : confirmLabel}
      </motion.button>
      <motion.button
        {...press}
        type="button"
        onClick={onDismiss}
        disabled={busy}
        className="cursor-pointer rounded-md border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
      >
        Back
      </motion.button>
    </div>
  );
}
