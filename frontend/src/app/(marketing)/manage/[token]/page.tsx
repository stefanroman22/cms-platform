"use client";

import { use, useCallback, useEffect, useState } from "react";
import { LazyMotion, domAnimation, MotionConfig, AnimatePresence, m } from "motion/react";
import { HeroButton } from "@/components/ui/HeroButton";
import { SubmitFeedback, type SubmitStatus } from "@/components/ui/SubmitFeedback";
import { BookingCalendar } from "@/components/booking/BookingCalendar";

const EXPO = [0.16, 1, 0.3, 1] as const;
interface ManageData {
  found: boolean;
  status?: string;
  start_utc?: string;
  visitor_timezone?: string;
  name?: string;
  can_cancel?: boolean;
  can_reschedule?: boolean;
  reschedule_count?: number;
  max_reschedules?: number;
  public_slug?: string;
  service_id?: string;
}

export default function ManagePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [data, setData] = useState<ManageData | null>(null);
  const [mode, setMode] = useState<"view" | "reschedule">("view");
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [cancelPhase, setCancelPhase] = useState<SubmitStatus | "idle">("idle");

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/booking/manage/${token}`);
      setData((await res.json()) as ManageData);
    } catch {
      setData({ found: false });
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function doCancel() {
    setCancelPhase("loading");
    try {
      const res = await fetch(`/api/booking/manage/${token}/cancel`, { method: "POST" });
      const d = (await res.json()) as { success?: boolean };
      if (!res.ok || !d?.success) throw new Error("failed");
      setCancelPhase("success");
    } catch {
      setCancelPhase("error");
    }
  }

  const whenLabel = data?.start_utc
    ? new Intl.DateTimeFormat(undefined, {
        weekday: "long",
        day: "numeric",
        month: "long",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: data.visitor_timezone || "Europe/Berlin",
      }).format(new Date(data.start_utc))
    : "";

  return (
    <main className="flex min-h-dvh items-center justify-center bg-black px-6 py-20">
      <div className="w-full max-w-md">
        <LazyMotion features={domAnimation}>
          <MotionConfig reducedMotion="user">
            {data === null ? (
              <p className="text-center text-sm text-text-tertiary">Loading…</p>
            ) : !data.found ? (
              <Card>
                <h1 className="font-display text-xl font-semibold text-text-primary">
                  Link not found
                </h1>
                <p className="mt-2 text-sm text-text-secondary">
                  This management link is invalid or expired.
                </p>
              </Card>
            ) : data.status === "cancelled" ? (
              <Card>
                <h1 className="font-display text-xl font-semibold text-text-primary">
                  Booking cancelled
                </h1>
                <p className="mt-2 text-sm text-text-secondary">This call has been cancelled.</p>
              </Card>
            ) : mode === "reschedule" && data.public_slug != null && data.service_id != null ? (
              <BookingCalendar
                slug={data.public_slug}
                reschedule={{
                  token,
                  serviceId: data.service_id,
                  onDone: () => {
                    setMode("view");
                    void load();
                  },
                }}
              />
            ) : (
              <Card>
                <AnimatePresence mode="wait" initial={false}>
                  {cancelPhase !== "idle" ? (
                    <m.div
                      key="cancel"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.3, ease: EXPO }}
                    >
                      <SubmitFeedback
                        status={cancelPhase}
                        loadingText="Cancelling…"
                        successText="Your call is cancelled."
                        errorText={<>Could not cancel. Please try again or contact support.</>}
                      />
                    </m.div>
                  ) : (
                    <m.div
                      key="view"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.3, ease: EXPO }}
                    >
                      <h1 className="font-display text-xl font-semibold text-text-primary">
                        Your call
                      </h1>
                      <p className="mt-2 text-sm text-text-secondary">{whenLabel}</p>

                      <div className="mt-6 space-y-3">
                        {data.can_reschedule && (
                          <HeroButton
                            type="button"
                            variant="secondary"
                            className="w-full"
                            onClick={() => setMode("reschedule")}
                          >
                            Reschedule
                          </HeroButton>
                        )}
                        {data.can_cancel && !confirmCancel && (
                          <button
                            type="button"
                            onClick={() => setConfirmCancel(true)}
                            className="w-full text-sm font-medium text-text-secondary underline-offset-4 outline-none transition-colors hover:text-red-400 focus-visible:underline"
                          >
                            Cancel this call
                          </button>
                        )}
                        {/* Own AnimatePresence so the outer initial={false} doesn't
                            suppress this dialog's animation; also gives an exit.
                            height 0↔auto grows the card dynamically. The border/bg live
                            on THIS animating element (not an inner div) so the box is
                            always a complete rectangle — its bottom edge rides down as
                            it grows instead of being revealed last. Opacity hides the
                            collapsed sliver. */}
                        <AnimatePresence initial={false}>
                          {data.can_cancel && confirmCancel && (
                            <m.div
                              key="confirm-cancel"
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: "auto" }}
                              exit={{ opacity: 0, height: 0 }}
                              transition={{ duration: 0.32, ease: EXPO }}
                              className="overflow-hidden rounded-[10px] border border-red-500/40 bg-red-500/5"
                            >
                              <div className="p-4 text-center">
                                <p className="mb-3 text-sm text-text-secondary">
                                  Cancel this call? This cannot be undone.
                                </p>
                                <div className="flex gap-2">
                                  <button
                                    type="button"
                                    onClick={() => setConfirmCancel(false)}
                                    className="flex-1 rounded-[10px] border border-border py-2 text-sm text-text-secondary hover:border-accent/50"
                                  >
                                    Keep it
                                  </button>
                                  <button
                                    type="button"
                                    onClick={doCancel}
                                    className="flex-1 rounded-[10px] bg-red-500 py-2 text-sm font-medium text-white hover:bg-red-600"
                                  >
                                    Yes, cancel
                                  </button>
                                </div>
                              </div>
                            </m.div>
                          )}
                        </AnimatePresence>
                        {!data.can_cancel && !data.can_reschedule && (
                          <p className="text-xs text-text-tertiary">
                            {(data.reschedule_count ?? 0) >= (data.max_reschedules ?? 2)
                              ? "You've rescheduled the maximum number of times."
                              : "Changes close 24h before (cancel) and 12h before (reschedule)."}
                          </p>
                        )}
                      </div>
                    </m.div>
                  )}
                </AnimatePresence>
              </Card>
            )}
          </MotionConfig>
        </LazyMotion>
      </div>
    </main>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm sm:p-8">
      {children}
    </div>
  );
}
