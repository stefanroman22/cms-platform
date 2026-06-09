"use client";

import { useState, useCallback } from "react";
import { Plus, CalendarDays } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import { dashboardSectionCardCn, dashboardInputCn } from "@/lib/styles";
import * as cache from "@/lib/cache";
import { listAppointments, listServices, listResources } from "./api";
import type { BookingAppointment, AppointmentFilters } from "./api";
import { AppointmentDetailDrawer } from "./AppointmentDetailDrawer";
import { NewAppointmentDrawer } from "./NewAppointmentDrawer";
import { createOverviewPrefs } from "./overview/prefsStore";

interface Props {
  projectSlug: string;
}

type StatusView = "active" | "cancelled" | "all";

// Segmented status filter: default to "active" (everything except cancelled),
// with one click to reveal cancelled or all. Filtered client-side so switching
// is instant.
const STATUS_SEGMENTS: { value: StatusView; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "cancelled", label: "Cancelled" },
  { value: "all", label: "All" },
];

const STATUS_BADGE: Record<string, string> = {
  confirmed: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  cancelled: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
  no_show: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  completed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
};

function statusBadgeCn(status: string) {
  return STATUS_BADGE[status] ?? "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400";
}

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

/**
 * Appointments list with filter controls + drawers for detail/new.
 * Mirrors ServicesManager (list + cache-invalidate refresh pattern).
 */
export function AppointmentsManager({ projectSlug }: Props) {
  // Default the resource filter to the persisted staff scope (localStorage), so a
  // barber opening the dashboard sees their own appointments first. "all" → no filter.
  const initialFilters = useState<AppointmentFilters>(() => {
    const scope = createOverviewPrefs(projectSlug).getScope();
    return scope && scope !== "all" ? { resource_id: scope } : {};
  })[0];
  const [filters, setFilters] = useState<AppointmentFilters>(initialFilters);
  const [pendingFilters, setPendingFilters] = useState<AppointmentFilters>(initialFilters);

  // Build a cache key that includes the active filters
  const filterKey = JSON.stringify(filters);
  const apptKey = `booking-appointments:${projectSlug}:${filterKey}`;
  const servicesKey = `booking-services:${projectSlug}`;
  const resourcesKey = `booking-resources:${projectSlug}`;

  const {
    data: apptData,
    loading: apptLoading,
    refresh: refreshAppts,
  } = useQuery(apptKey, () => listAppointments(projectSlug, filters), { ttl: 30 * 1000 });

  const { data: servicesData } = useQuery(servicesKey, () => listServices(projectSlug), {
    ttl: 60 * 1000,
  });

  const { data: resourcesData } = useQuery(resourcesKey, () => listResources(projectSlug), {
    ttl: 60 * 1000,
  });

  const appointments = apptData?.appointments ?? [];
  const services = servicesData?.services ?? [];
  const resources = resourcesData?.resources ?? [];

  // Status view (client-side, instant). Default hides cancelled.
  const [statusView, setStatusView] = useState<StatusView>("active");
  const cancelledCount = appointments.filter((a) => a.status === "cancelled").length;
  const visibleAppointments = appointments.filter((a) =>
    statusView === "all"
      ? true
      : statusView === "cancelled"
        ? a.status === "cancelled"
        : a.status !== "cancelled"
  );

  // detail drawer: undefined=closed, BookingAppointment=open
  const [detailTarget, setDetailTarget] = useState<BookingAppointment | undefined>(undefined);
  const [newDrawerOpen, setNewDrawerOpen] = useState(false);

  const handleChanged = useCallback(() => {
    cache.invalidate(apptKey);
    refreshAppts();
  }, [apptKey, refreshAppts]);

  function applyFilters() {
    setFilters(pendingFilters);
    // Persist the staff scope so it carries across the dashboard + reloads.
    createOverviewPrefs(projectSlug).setScope(pendingFilters.resource_id ?? "all");
  }

  function resetFilters() {
    setPendingFilters({});
    setFilters({});
    createOverviewPrefs(projectSlug).setScope("all");
  }

  // Look up the settings timezone from settings cache if available
  const settingsData = cache.get<{ timezone?: string }>(`booking-settings:${projectSlug}`);
  const tz = settingsData?.timezone ?? null;

  return (
    <div>
      {/* Header row */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Appointments</h2>
        <button
          type="button"
          onClick={() => setNewDrawerOpen(true)}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-700 dark:hover:bg-zinc-600"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          New appointment
        </button>
      </div>

      {/* Status segmented control — defaults to Active (hides cancelled). */}
      <div
        role="group"
        aria-label="Filter by status"
        className="mb-4 inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 dark:border-zinc-700 dark:bg-zinc-800/50"
      >
        {STATUS_SEGMENTS.map((seg) => {
          const active = statusView === seg.value;
          return (
            <button
              key={seg.value}
              type="button"
              aria-pressed={active}
              onClick={() => setStatusView(seg.value)}
              className={`cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                active
                  ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
              }`}
            >
              {seg.label}
              {seg.value === "cancelled" && cancelledCount > 0 ? ` (${cancelledCount})` : ""}
            </button>
          );
        })}
      </div>

      {/* Filter controls */}
      <div className="mb-4 flex flex-wrap items-end gap-2">
        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1 dark:text-zinc-400">
            Service
          </label>
          <select
            value={pendingFilters.service_id ?? ""}
            onChange={(e) =>
              setPendingFilters((f) => ({
                ...f,
                service_id: e.target.value || undefined,
              }))
            }
            className={`${dashboardInputCn} w-44`}
          >
            <option value="">All services</option>
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1 dark:text-zinc-400">
            Resource
          </label>
          <select
            value={pendingFilters.resource_id ?? ""}
            onChange={(e) =>
              setPendingFilters((f) => ({
                ...f,
                resource_id: e.target.value || undefined,
              }))
            }
            className={`${dashboardInputCn} w-40`}
          >
            <option value="">All resources</option>
            {resources.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1 dark:text-zinc-400">
            From
          </label>
          <input
            type="date"
            value={pendingFilters.from ?? ""}
            onChange={(e) =>
              setPendingFilters((f) => ({
                ...f,
                from: e.target.value || undefined,
              }))
            }
            className={`${dashboardInputCn} w-36`}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1 dark:text-zinc-400">
            To
          </label>
          <input
            type="date"
            value={pendingFilters.to ?? ""}
            onChange={(e) =>
              setPendingFilters((f) => ({
                ...f,
                to: e.target.value || undefined,
              }))
            }
            className={`${dashboardInputCn} w-36`}
          />
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={applyFilters}
            className="cursor-pointer rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-700 dark:hover:bg-zinc-600"
          >
            Apply
          </button>
          <button
            type="button"
            onClick={resetFilters}
            className="cursor-pointer rounded-lg border border-zinc-200 px-3 py-2 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            Reset
          </button>
        </div>
      </div>

      {/* List */}
      {apptLoading && (
        <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
          <ArcSpinner size={20} />
          Loading appointments…
        </div>
      )}

      {!apptLoading && visibleAppointments.length === 0 && (
        <div
          className={`${dashboardSectionCardCn} flex flex-col items-center gap-2 px-6 py-12 text-center`}
        >
          <CalendarDays className="h-8 w-8 text-zinc-300 dark:text-zinc-600" aria-hidden="true" />
          <p className="text-sm text-zinc-400 dark:text-zinc-500">No appointments found.</p>
        </div>
      )}

      {!apptLoading && visibleAppointments.length > 0 && (
        <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
          {visibleAppointments.map((appt) => (
            <button
              key={appt.id}
              type="button"
              onClick={() => setDetailTarget(appt)}
              className="w-full cursor-pointer px-4 py-3 text-left transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/60"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
                      {appt.customer_name ?? "Unknown customer"}
                    </span>
                    {appt.customer_email && (
                      <span className="text-xs text-zinc-400 dark:text-zinc-500 truncate">
                        {appt.customer_email}
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                    <span>{formatDateTime(appt.start_utc, tz)}</span>
                    {appt.service_name && <span>{appt.service_name}</span>}
                    {appt.resource_name && (
                      <span className="text-zinc-400 dark:text-zinc-500">{appt.resource_name}</span>
                    )}
                  </div>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium capitalize ${statusBadgeCn(
                    appt.status
                  )}`}
                >
                  {appt.status.replace("_", "-")}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {detailTarget !== undefined && (
        <AppointmentDetailDrawer
          projectSlug={projectSlug}
          appointment={detailTarget}
          services={services}
          timezone={tz}
          onClose={() => setDetailTarget(undefined)}
          onChanged={() => {
            setDetailTarget(undefined);
            handleChanged();
          }}
        />
      )}

      {newDrawerOpen && (
        <NewAppointmentDrawer
          projectSlug={projectSlug}
          services={services}
          resources={resources}
          timezone={tz}
          onClose={() => setNewDrawerOpen(false)}
          onCreated={() => {
            setNewDrawerOpen(false);
            handleChanged();
          }}
        />
      )}
    </div>
  );
}
