"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { LazyMotion, domAnimation, MotionConfig, AnimatePresence, m } from "motion/react";
import { ChevronLeft } from "lucide-react";
import { dateKey } from "@/lib/bookingDates";
import { MonthGrid } from "@/components/booking/MonthGrid";
import { TimeSlots } from "@/components/booking/TimeSlots";
import { BookingDetailsForm, type BookingDetails } from "@/components/booking/BookingDetailsForm";
import { BookingConfirmation } from "@/components/booking/BookingConfirmation";
import { HeroButton } from "@/components/ui/HeroButton";
import { cn } from "@/lib/utils";
import { tw } from "@/components/booking/i18n";

const EXPO = [0.16, 1, 0.3, 1] as const;
const MIN_SPINNER_MS = 700;
/** Default display timezone — Central European Time. Clients can switch. */
const DEFAULT_TZ = "Europe/Berlin";
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type Step = "service" | "staff" | "date" | "time" | "confirm" | "details" | "done";
type Phase = "loading" | "success" | "error";

const detectedTz = () =>
  typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";

/** Full IANA timezone list (native browsers), with the CET default + the
 *  visitor's own zone guaranteed present. Falls back to a short list. */
function buildTzList(detected: string): string[] {
  let all: string[] = [];
  try {
    const sv = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] })
      .supportedValuesOf;
    all = sv ? sv("timeZone") : [];
  } catch {
    all = [];
  }
  if (all.length === 0) {
    all = [
      "Europe/Berlin",
      "Europe/Bucharest",
      "Europe/London",
      "Europe/Madrid",
      "America/New_York",
      "America/Los_Angeles",
      "Asia/Dubai",
      "Asia/Singapore",
    ];
  }
  const set = new Set(all);
  set.add(DEFAULT_TZ);
  if (detected) set.add(detected);
  return Array.from(set).sort();
}

interface PublicConfig {
  public_slug: string;
  business_name: string | null;
  primary_color: string | null;
  accent_color: string | null;
  widget_color: string | null;
  logo_url: string | null;
  locale: string | null;
}

interface PublicService {
  id: string;
  name: string;
  duration_min: number;
}

interface PublicResource {
  id: string;
  name: string;
  type?: string;
}

export function BookingCalendar({
  slug,
  embedded,
  reschedule,
  heading,
  subheading,
  avatarUrl,
}: {
  slug: string;
  embedded?: boolean;
  reschedule?: { token: string; serviceId: string; onDone?: () => void };
  /** Optional header overrides (e.g. the Roman Technologies /contact page). When
   *  omitted, the header is derived from the tenant's public config + service. */
  heading?: string;
  subheading?: string;
  avatarUrl?: string;
}) {
  const now = new Date();
  const [step, setStep] = useState<Step>(reschedule ? "date" : "service");
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [viewMonth, setViewMonth] = useState(now.getMonth());
  const [bookableDays, setBookableDays] = useState<Set<string>>(new Set());
  const [daysLoading, setDaysLoading] = useState(false);
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const [slots, setSlots] = useState<string[]>([]);
  // All availability for the booking horizon, preloaded once per service so
  // month switches + day picks are instant (no per-view network round-trips).
  const [slotsByDate, setSlotsByDate] = useState<Map<string, string[]>>(new Map());
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [displayTz, setDisplayTz] = useState(DEFAULT_TZ);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [services, setServices] = useState<PublicService[]>([]);
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(
    reschedule ? reschedule.serviceId : null
  );
  const [resources, setResources] = useState<PublicResource[]>([]);
  // null = not yet chosen; "" = "No preference" (auto-assign); else a barber id.
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [configError, setConfigError] = useState(false);

  const tzOptions = useMemo(() => buildTzList(detectedTz()), []);
  const canGoPrev =
    viewYear > now.getFullYear() || (viewYear === now.getFullYear() && viewMonth > now.getMonth());

  // Fetch public config + services on mount (booking mode only)
  useEffect(() => {
    if (reschedule) return; // reschedule mode: we already have serviceId, no need for config
    let cancelled = false;
    async function loadConfig() {
      try {
        const [cfgRes, svcRes] = await Promise.all([
          fetch(`/api/booking/${slug}/config`),
          fetch(`/api/booking/${slug}/services`),
        ]);
        if (!cfgRes.ok) {
          if (!cancelled) setConfigError(true);
          return;
        }
        const cfg = (await cfgRes.json()) as PublicConfig;
        const svcData = (await svcRes.json()) as { services: PublicService[] };
        if (cancelled) return;
        setConfig(cfg);
        const active = svcData.services ?? [];
        setServices(active);
        if (active.length === 1) {
          // Auto-select the only service and skip the service step; pickService
          // then loads barbers and decides whether to show the barber step.
          void pickServiceRef.current(active[0].id);
        } else if (active.length > 1) {
          setStep("service");
        } else {
          // No services → go to date anyway; availability will be empty. No
          // service means no barber step; treat as "no preference".
          setSelectedResourceId("");
          setStep("date");
        }
      } catch {
        if (!cancelled) setConfigError(true);
      }
    }
    void loadConfig();
    return () => {
      cancelled = true;
    };
  }, [slug, reschedule]);

  // Preload the whole booking horizon in ONE batched request when the service is
  // chosen. Subsequent month navigation + day selection read from the in-memory
  // cache, so they are instant (the backend availability endpoint is batched).
  const loadAllAvailability = useCallback(
    async (serviceId: string | null, resourceId: string | null) => {
      if (!serviceId) return;
      setDaysLoading(true);
      try {
        const today = new Date();
        const from = dateKey(today);
        const horizon = new Date(today);
        horizon.setDate(horizon.getDate() + 120); // covers the default max-advance
        const to = dateKey(horizon);
        // resourceId "" / null → union across all eligible barbers; a non-empty
        // id → that one barber's calendar.
        const resourceQs = resourceId ? `&resource_id=${encodeURIComponent(resourceId)}` : "";
        const res = await fetch(
          `/api/booking/${slug}/availability?service_id=${encodeURIComponent(serviceId)}&from=${from}&to=${to}${resourceQs}`
        );
        const data = (await res.json()) as {
          days?: Array<{ date: string; slots?: Array<{ start_utc: string }> }>;
        };
        const map = new Map<string, string[]>();
        const dayset = new Set<string>();
        for (const d of data.days ?? []) {
          dayset.add(d.date);
          map.set(
            d.date,
            (d.slots ?? []).map((s) => s.start_utc)
          );
        }
        setBookableDays(dayset);
        setSlotsByDate(map);
      } catch {
        setBookableDays(new Set());
        setSlotsByDate(new Map());
      } finally {
        setDaysLoading(false);
      }
    },
    [slug]
  );

  // Choose a service, then load the eligible barbers for it and advance the flow:
  // render the barber step when there's a real choice, or auto-skip it
  // (single barber → select it silently; zero → "No preference") — mirroring how
  // the service step is auto-skipped when 0/1 services exist.
  const pickService = useCallback(
    async (serviceId: string) => {
      setSelectedServiceId(serviceId);
      setSelectedResourceId(null); // reset any prior barber choice
      let active: PublicResource[] = [];
      try {
        const res = await fetch(
          `/api/booking/${slug}/resources?service_id=${encodeURIComponent(serviceId)}`
        );
        if (res.ok) {
          const data = (await res.json()) as { resources?: PublicResource[] };
          active = data.resources ?? [];
        }
      } catch {
        active = [];
      }
      setResources(active);
      if (active.length === 1) {
        setSelectedResourceId(active[0].id); // single barber → pick silently
        setStep("date");
      } else if (active.length > 1) {
        setStep("staff");
      } else {
        setSelectedResourceId(""); // no barbers → auto-assign, no preference
        setStep("date");
      }
    },
    [slug]
  );
  // Keep a stable ref so the mount-time config effect can call the latest
  // pickService without listing it as a dependency (it's declared after it).
  const pickServiceRef = useRef(pickService);
  pickServiceRef.current = pickService;

  useEffect(() => {
    if (!selectedServiceId) return;
    // Reschedule mode has no barber step — load straight away (no preference).
    // Booking mode waits until a barber decision is made (id, or "" = no pref).
    if (reschedule) {
      void loadAllAvailability(selectedServiceId, null);
    } else if (selectedResourceId !== null) {
      void loadAllAvailability(selectedServiceId, selectedResourceId);
    }
  }, [selectedServiceId, selectedResourceId, reschedule, loadAllAvailability]);

  function changeMonth(delta: number) {
    const d = new Date(viewYear, viewMonth + delta, 1);
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth());
  }

  function pickDay(day: Date) {
    // Slots are already preloaded — read them from the cache (instant).
    setSelectedDay(day);
    setSlots(slotsByDate.get(dateKey(day)) ?? []);
    setStep("time");
  }

  function pickSlot(iso: string) {
    setSelectedSlot(iso);
    setStep(reschedule ? "confirm" : "details");
  }

  // Barber chosen (a resource id, or "" for "No preference"/auto-assign). The
  // availability effect reloads for the chosen barber once this is set.
  function pickResource(resourceId: string) {
    setSelectedResourceId(resourceId);
    setStep("date");
  }

  async function submit(details: BookingDetails) {
    if (!selectedSlot) return;
    setPhase("loading");
    setStep("done");
    try {
      const [res] = await Promise.all([
        fetch(`/api/booking/${slug}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            service_id: selectedServiceId,
            // "" = no preference / auto-assign; a non-empty id = specific barber.
            resource_id: selectedResourceId ?? "",
            start_utc: selectedSlot,
            customer: {
              name: details.name.trim(),
              email: details.email.trim(),
              tz: displayTz,
            },
            note: details.note.trim(),
            website: details.website,
          }),
        }),
        sleep(MIN_SPINNER_MS),
      ]);
      const data = (await res.json()) as { success?: boolean; booking_id?: string };
      if (!res.ok || !data?.success) throw new Error("failed");
      setPhase("success");
      if (embedded && typeof window !== "undefined") {
        window.parent.postMessage({ type: "booking_completed", booking_id: data.booking_id }, "*");
      }
    } catch {
      setPhase("error");
    }
  }

  async function submitReschedule() {
    if (!selectedSlot || !reschedule) return;
    setPhase("loading");
    setStep("done");
    try {
      const [res] = await Promise.all([
        fetch(`/api/booking/manage/${reschedule.token}/reschedule`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slot_start: selectedSlot }),
        }),
        sleep(MIN_SPINNER_MS),
      ]);
      const data = (await res.json()) as { success?: boolean };
      if (!res.ok || !data?.success) throw new Error("failed");
      setPhase("success");
    } catch {
      setPhase("error");
    }
  }

  function reset(toStart: boolean) {
    setPhase("loading");
    setSelectedSlot(null);
    if (toStart) {
      setSelectedDay(null);
      setStep("date");
    } else {
      setStep("details");
    }
  }

  const dayLabel = selectedDay
    ? new Intl.DateTimeFormat(undefined, {
        weekday: "long",
        day: "numeric",
        month: "long",
        timeZone: displayTz,
      }).format(selectedDay)
    : "";
  const slotLabel = selectedSlot
    ? new Intl.DateTimeFormat(undefined, {
        weekday: "short",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: displayTz,
      }).format(new Date(selectedSlot))
    : "";

  const businessName = config?.business_name ?? null;
  const logoUrl = config?.logo_url ?? null;
  const primaryColor = config?.primary_color ?? null;
  // The widget's accent is its OWN field, independent of the email accent
  // (`accent_color`). Keeps "book a call" gold while emails can be e.g. black.
  const widgetColor = config?.widget_color ?? null;
  const locale = config?.locale ?? "en";
  // Prop avatar wins; else the tenant logo (booking mode only).
  const avatarSrc = avatarUrl ?? (!reschedule ? logoUrl : null);

  const cssVars = {
    ...(primaryColor ? { "--booking-primary": primaryColor } : {}),
    ...(widgetColor ? { "--booking-accent": widgetColor } : {}),
    // Drive the widget's accent utilities from the tenant widget color; falls back
    // to the app-global --color-accent when no widget color is configured.
    ...(widgetColor ? { "--color-accent": widgetColor } : {}),
  } as React.CSSProperties;

  if (configError) {
    return (
      <div
        className={cn("rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm sm:p-8")}
      >
        <p className="text-center text-sm text-text-secondary">{tw("en", "bookUnavailable")}</p>
      </div>
    );
  }

  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <div
          data-booking-root
          style={cssVars}
          className={cn(
            "rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm sm:p-8"
          )}
        >
          {/* Header — branding */}
          <div className="mb-6 flex flex-col items-center gap-3 border-b border-border pb-6 text-center">
            {avatarSrc && (
              <Image
                src={avatarSrc}
                alt={heading ?? businessName ?? "Booking"}
                width={96}
                height={96}
                className="h-24 w-24 rounded-full object-cover ring-1 ring-border"
              />
            )}
            <div>
              <p className="font-display text-lg font-semibold text-text-primary">
                {heading ??
                  (reschedule
                    ? tw(locale, "rescheduleHeading")
                    : businessName
                      ? tw(locale, "bookWithName").replace("{name}", businessName)
                      : tw(locale, "bookHeading"))}
              </p>
              {subheading ? (
                <p className="mt-1 text-xs text-text-secondary">{subheading}</p>
              ) : selectedServiceId && services.length > 0 ? (
                <p className="mt-1 text-xs text-text-secondary">
                  {services.find((s) => s.id === selectedServiceId)?.name ?? ""}
                </p>
              ) : null}
            </div>
          </div>

          <AnimatePresence mode="wait" initial={false}>
            <m.div
              key={step}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -24 }}
              transition={{ duration: 0.35, ease: EXPO }}
            >
              {step === "service" && (
                <div className="space-y-3">
                  <p className="mb-4 text-sm font-medium text-text-secondary">
                    {tw(locale, "selectService")}
                  </p>
                  {services.map((svc) => (
                    <button
                      key={svc.id}
                      type="button"
                      onClick={() => void pickService(svc.id)}
                      className="w-full cursor-pointer rounded-[10px] border border-border bg-surface/40 px-4 py-3 text-left text-sm outline-none transition-colors hover:border-accent/60 hover:bg-surface focus-visible:border-accent"
                    >
                      <span className="font-medium text-text-primary">{svc.name}</span>
                      <span className="ml-2 text-xs text-text-tertiary">
                        {svc.duration_min}
                        {tw(locale, "durationSuffix")}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {step === "staff" && (
                <div className="space-y-3">
                  {services.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setStep("service")}
                      className="mb-1 inline-flex items-center gap-1 text-sm text-text-secondary outline-none transition-colors hover:text-accent focus-visible:text-accent"
                    >
                      <ChevronLeft className="h-4 w-4" /> {tw(locale, "back")}
                    </button>
                  )}
                  <p className="mb-4 text-sm font-medium text-text-secondary">
                    {tw(locale, "selectStaff")}
                  </p>
                  {resources.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => pickResource(r.id)}
                      className="w-full cursor-pointer rounded-[10px] border border-border bg-surface/40 px-4 py-3 text-left text-sm outline-none transition-colors hover:border-accent/60 hover:bg-surface focus-visible:border-accent"
                    >
                      <span className="font-medium text-text-primary">{r.name}</span>
                    </button>
                  ))}
                  {/* "No preference" → auto-assign (empty resource_id). */}
                  <button
                    type="button"
                    onClick={() => pickResource("")}
                    className="w-full cursor-pointer rounded-[10px] border border-border bg-surface/40 px-4 py-3 text-left text-sm outline-none transition-colors hover:border-accent/60 hover:bg-surface focus-visible:border-accent"
                  >
                    <span className="font-medium text-text-primary">
                      {tw(locale, "noPreference")}
                    </span>
                  </button>
                </div>
              )}

              {step === "date" && (
                <>
                  {reschedule && (
                    <button
                      type="button"
                      onClick={() => reschedule.onDone?.()}
                      className="mb-3 inline-flex items-center gap-1 text-sm text-text-secondary outline-none transition-colors hover:text-accent focus-visible:text-accent"
                    >
                      <ChevronLeft className="h-4 w-4" /> {tw(locale, "back")}
                    </button>
                  )}
                  {!reschedule && (resources.length > 1 || services.length > 1) && (
                    <button
                      type="button"
                      onClick={() => setStep(resources.length > 1 ? "staff" : "service")}
                      className="mb-3 inline-flex items-center gap-1 text-sm text-text-secondary outline-none transition-colors hover:text-accent focus-visible:text-accent"
                    >
                      <ChevronLeft className="h-4 w-4" /> {tw(locale, "back")}
                    </button>
                  )}
                  <MonthGrid
                    viewYear={viewYear}
                    viewMonth={viewMonth}
                    bookableDays={bookableDays}
                    loading={daysLoading}
                    canGoPrev={canGoPrev}
                    onPrevMonth={() => changeMonth(-1)}
                    onNextMonth={() => changeMonth(1)}
                    onSelectDay={pickDay}
                    locale={locale}
                  />
                </>
              )}

              {step === "time" && (
                <TimeSlots
                  dayLabel={dayLabel}
                  slots={slots}
                  loading={false}
                  displayTz={displayTz}
                  tzOptions={tzOptions}
                  onTzChange={setDisplayTz}
                  onBack={() => setStep("date")}
                  onPick={pickSlot}
                  locale={locale}
                />
              )}

              {step === "confirm" && (
                <div className="text-center">
                  <button
                    type="button"
                    onClick={() => setStep("time")}
                    className="mb-4 inline-flex items-center gap-1 text-sm text-text-secondary outline-none transition-colors hover:text-accent focus-visible:text-accent"
                  >
                    <ChevronLeft className="h-4 w-4" /> {tw(locale, "back")}
                  </button>
                  <p className="mb-1 text-sm text-text-secondary">
                    {tw(locale, "moveAppointmentTo")}
                  </p>
                  <p className="mb-6 font-display text-lg font-semibold text-accent">{slotLabel}</p>
                  <HeroButton
                    type="button"
                    variant="primary"
                    className="w-full"
                    onClick={submitReschedule}
                  >
                    {tw(locale, "confirmNewTime")}
                  </HeroButton>
                </div>
              )}

              {step === "details" && (
                <BookingDetailsForm
                  slotLabel={slotLabel}
                  onBack={() => setStep("time")}
                  onSubmit={submit}
                  locale={locale}
                />
              )}

              {step === "done" && (
                <BookingConfirmation
                  status={phase}
                  slotLabel={slotLabel}
                  contactEmail={null}
                  locale={locale}
                  onReset={() => {
                    if (reschedule && phase === "success") {
                      reschedule.onDone?.();
                      return;
                    }
                    reset(phase === "success");
                  }}
                />
              )}
            </m.div>
          </AnimatePresence>
        </div>
      </MotionConfig>
    </LazyMotion>
  );
}
