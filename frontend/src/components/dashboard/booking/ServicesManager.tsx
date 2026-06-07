"use client";

import { useState } from "react";
import { Plus, Pencil, Clock } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import { dashboardSectionCardCn } from "@/lib/styles";
import * as cache from "@/lib/cache";
import { listServices, listResources } from "./api";
import type { BookingService } from "./api";
import { ServiceFormDrawer } from "./ServiceFormDrawer";

interface Props {
  projectSlug: string;
}

/**
 * Services list + add/edit drawer — mirrors AutoFixSection (list+trigger)
 * and LeadDetailDrawer (drawer) patterns.
 */
export function ServicesManager({ projectSlug }: Props) {
  const servicesKey = `booking-services:${projectSlug}`;
  const resourcesKey = `booking-resources:${projectSlug}`;

  const { data: servicesData, loading: servicesLoading } = useQuery(
    servicesKey,
    () => listServices(projectSlug),
    { ttl: 60 * 1000 }
  );

  const { data: resourcesData } = useQuery(resourcesKey, () => listResources(projectSlug), {
    ttl: 60 * 1000,
  });

  const services = servicesData?.services ?? [];
  const resources = resourcesData?.resources ?? [];

  // null = drawer closed; undefined = "add new"; BookingService = editing
  const [drawerTarget, setDrawerTarget] = useState<BookingService | null | undefined>(undefined);
  const isDrawerOpen = drawerTarget !== undefined;

  function openAdd() {
    setDrawerTarget(null);
  }

  function openEdit(s: BookingService) {
    setDrawerTarget(s);
  }

  function handleClose() {
    setDrawerTarget(undefined);
  }

  function handleSaved() {
    cache.invalidate(servicesKey);
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Services</h2>
        <button
          type="button"
          onClick={openAdd}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-700 dark:hover:bg-zinc-600"
        >
          <Plus className="h-3.5 w-3.5" />
          Add service
        </button>
      </div>

      {servicesLoading && (
        <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
          <ArcSpinner size={20} />
          Loading services…
        </div>
      )}

      {!servicesLoading && services.length === 0 && (
        <div
          className={`${dashboardSectionCardCn} px-6 py-8 text-center text-sm text-zinc-400 dark:text-zinc-500`}
        >
          No services yet. Add one to get started.
        </div>
      )}

      {!servicesLoading && services.length > 0 && (
        <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
          {services.map((s) => (
            <div key={s.id} className="flex items-center justify-between px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  {s.color && (
                    <span
                      className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ background: s.color }}
                    />
                  )}
                  <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    {s.name}
                  </span>
                  {!(s.is_active ?? true) && (
                    <span className="rounded-full bg-zinc-100 px-1.5 py-px text-[10px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                      inactive
                    </span>
                  )}
                </div>
                {s.description && (
                  <p className="mt-0.5 truncate text-xs text-zinc-400 dark:text-zinc-500">
                    {s.description}
                  </p>
                )}
                <div className="mt-1 flex items-center gap-1 text-xs text-zinc-400 dark:text-zinc-500">
                  <Clock className="h-3 w-3" />
                  {s.duration_min} min
                </div>
              </div>
              <button
                type="button"
                onClick={() => openEdit(s)}
                aria-label={`Edit ${s.name}`}
                className="ml-3 inline-flex cursor-pointer items-center gap-1 rounded-md border border-zinc-200 px-2.5 py-1.5 text-xs text-zinc-500 transition-colors hover:border-zinc-300 hover:text-zinc-700 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-zinc-600 dark:hover:text-zinc-200"
              >
                <Pencil className="h-3 w-3" />
                Edit
              </button>
            </div>
          ))}
        </div>
      )}

      {isDrawerOpen && (
        <ServiceFormDrawer
          projectSlug={projectSlug}
          service={drawerTarget ?? null}
          resources={resources}
          onClose={handleClose}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
