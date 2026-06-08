"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { CalendarCheck2 } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import * as cache from "@/lib/cache";
import { getStats, listAppointments, listServices, listResources } from "./api";
import type { BookingAppointment } from "./api";
import { AppointmentDetailDrawer } from "./AppointmentDetailDrawer";
import { STAT_VIEWS, STAT_VIEWS_BY_ID, type OverviewWidgetCtx } from "./overview/widgetRegistry";
import { StaffScopeSelect } from "./overview/StaffScopeSelect";
import { StatViewFilter } from "./overview/StatViewFilter";
import { CalendarWidget } from "./overview/CalendarWidget";
import { createOverviewPrefs, DEFAULT_STAT_VIEW } from "./overview/prefsStore";

interface Props {
  projectSlug: string;
}

const FADE = [0.16, 1, 0.3, 1] as const;

export function OverviewPanel({ projectSlug }: Props) {
  const reduced = useReducedMotion();
  // Persisted prefs (localStorage, abstracted). One store instance per project.
  const prefs = useMemo(() => createOverviewPrefs(projectSlug), [projectSlug]);
  const [statView, setStatViewState] = useState<string>(() => prefs.getStatView());
  const [scope, setScopeState] = useState<string>(() => prefs.getScope());
  const [detailTarget, setDetailTarget] = useState<BookingAppointment | undefined>(undefined);

  // Re-hydrate when switching projects.
  useEffect(() => {
    setStatViewState(prefs.getStatView());
    setScopeState(prefs.getScope());
  }, [prefs]);

  function setStatView(next: string) {
    setStatViewState(next);
    prefs.setStatView(next);
  }

  // Staff scope is remembered per project so the owner returns to the same person.
  function setScope(next: string) {
    setScopeState(next);
    prefs.setScope(next);
  }

  const resourceId = scope === "all" ? undefined : scope;

  // Stats refetch when scope changes (key carries the scope).
  const {
    data: stats,
    loading,
    error,
  } = useQuery(
    `booking-stats:${projectSlug}:${scope}`,
    () => getStats(projectSlug, undefined, undefined, resourceId),
    { ttl: 2 * 60 * 1000 }
  );

  const { data: apptData } = useQuery(
    `booking-overview-appts:${projectSlug}`,
    () => listAppointments(projectSlug),
    { ttl: 60 * 1000 }
  );
  const { data: servicesData } = useQuery(
    `booking-services:${projectSlug}`,
    () => listServices(projectSlug),
    { ttl: 60 * 1000 }
  );
  const { data: resourcesData } = useQuery(
    `booking-resources:${projectSlug}`,
    () => listResources(projectSlug),
    { ttl: 60 * 1000 }
  );

  const services = servicesData?.services ?? [];
  const allResources = resourcesData?.resources ?? [];
  const staff = allResources.filter(
    (r) => (r.type ?? "staff") === "staff" && r.is_active !== false
  );

  // Scope-filter appointments before handing them to the calendar.
  const allAppts = useMemo(() => apptData?.appointments ?? [], [apptData]);
  const appointments = useMemo(
    () => (resourceId ? allAppts.filter((a) => a.resource_id === resourceId) : allAppts),
    [allAppts, resourceId]
  );

  const tz = cache.get<{ timezone?: string }>(`booking-settings:${projectSlug}`)?.timezone ?? null;

  if (loading) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
        <ArcSpinner size={20} />
        Loading overview…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400">
        Failed to load stats: {error}
      </div>
    );
  }

  if (!stats) return null;

  const ctx: OverviewWidgetCtx = {
    stats,
    appointments,
    services,
    staff,
    scope,
    timezone: tz,
    onSelectAppointment: (a: BookingAppointment) => setDetailTarget(a),
  };

  // Available stat views (e.g. by-staff only with 2+ staff). Fall back to the
  // default if a persisted view is no longer available.
  const availableViews = STAT_VIEWS.filter((v) => !v.available || v.available(ctx));
  const activeId = availableViews.some((v) => v.id === statView) ? statView : DEFAULT_STAT_VIEW;
  const activeView = STAT_VIEWS_BY_ID[activeId] ?? STAT_VIEWS_BY_ID[DEFAULT_STAT_VIEW];

  const noBookings = stats.kpis.total === 0 && allAppts.length === 0;

  return (
    <div className="space-y-8">
      {/* Staff scope — default "All staff", one tap to focus a single person. */}
      {staff.length > 1 && (
        <div>
          <StaffScopeSelect staff={staff} value={scope} onChange={setScope} />
        </div>
      )}

      {/* Calendar — always displayed. */}
      <CalendarWidget
        appointments={appointments}
        services={services}
        timezone={tz}
        onSelectAppointment={(a) => setDetailTarget(a)}
      />

      {/* Statistics — a single calm panel chosen via a segmented filter. */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 pb-2 dark:border-zinc-800">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
            Statistics
          </h2>
          <StatViewFilter
            views={availableViews.map((v) => ({ id: v.id, title: v.title }))}
            value={activeId}
            onChange={setStatView}
          />
        </div>

        {noBookings ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-zinc-200 bg-white px-6 py-12 text-center dark:border-zinc-800 dark:bg-zinc-900">
            <CalendarCheck2
              className="h-7 w-7 text-zinc-300 dark:text-zinc-600"
              aria-hidden="true"
            />
            <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">No bookings yet</p>
            <p className="max-w-xs text-xs text-zinc-400 dark:text-zinc-500">
              Stats and trends appear here once bookings come in.
            </p>
          </div>
        ) : (
          // Crossfade in sync mode: the incoming panel mounts immediately (interactive
          // at once) while the outgoing one fades out, absolutely positioned over this
          // relative wrapper.
          <div className="relative">
            <AnimatePresence initial={false}>
              <motion.div
                key={activeId}
                initial={reduced ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? undefined : { opacity: 0, position: "absolute", inset: 0 }}
                transition={{ duration: 0.18, ease: FADE }}
              >
                {activeView.render(ctx)}
              </motion.div>
            </AnimatePresence>
          </div>
        )}
      </section>

      {detailTarget !== undefined && (
        <AppointmentDetailDrawer
          projectSlug={projectSlug}
          appointment={detailTarget}
          services={services}
          timezone={tz}
          onClose={() => setDetailTarget(undefined)}
          onChanged={() => {
            setDetailTarget(undefined);
            cache.invalidate(`booking-overview-appts:${projectSlug}`);
            cache.invalidate(`booking-stats:${projectSlug}:${scope}`);
          }}
        />
      )}
    </div>
  );
}

// Re-export the registry so callers can introspect available views if needed.
export { STAT_VIEWS };
