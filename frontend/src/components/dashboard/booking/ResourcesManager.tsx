"use client";

import { useState } from "react";
import { Plus, Pencil } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import { dashboardSectionCardCn } from "@/lib/styles";
import * as cache from "@/lib/cache";
import { listResources } from "./api";
import type { BookingResource } from "./api";
import { ResourceFormDrawer } from "./ResourceFormDrawer";

interface Props {
  projectSlug: string;
}

/**
 * Staff list + add/edit drawer — mirrors ServicesManager pattern.
 * (Backed by the booking_resources table; the UI leads with people/staff.)
 */
export function ResourcesManager({ projectSlug }: Props) {
  const resourcesKey = `booking-resources:${projectSlug}`;

  const { data: resourcesData, loading } = useQuery(
    resourcesKey,
    () => listResources(projectSlug),
    { ttl: 60 * 1000 }
  );

  const resources = resourcesData?.resources ?? [];

  // undefined = closed; null = add new; BookingResource = editing
  const [drawerTarget, setDrawerTarget] = useState<BookingResource | null | undefined>(undefined);
  const isDrawerOpen = drawerTarget !== undefined;

  function handleClose() {
    setDrawerTarget(undefined);
  }

  function handleSaved() {
    cache.invalidate(resourcesKey);
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Staff</h2>
        <button
          type="button"
          onClick={() => setDrawerTarget(null)}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-700 dark:hover:bg-zinc-600"
        >
          <Plus className="h-3.5 w-3.5" />
          Add staff
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
          <ArcSpinner size={20} />
          Loading staff…
        </div>
      )}

      {!loading && resources.length === 0 && (
        <div
          className={`${dashboardSectionCardCn} px-6 py-8 text-center text-sm text-zinc-400 dark:text-zinc-500`}
        >
          No staff yet. Add someone to get started.
        </div>
      )}

      {!loading && resources.length > 0 && (
        <div className={`${dashboardSectionCardCn} divide-y divide-zinc-100 dark:divide-zinc-800`}>
          {resources.map((r) => (
            <div key={r.id} className="flex items-center justify-between px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    {r.name}
                  </span>
                  {r.type && (
                    <span className="rounded-full bg-zinc-100 px-1.5 py-px text-[10px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                      {r.type}
                    </span>
                  )}
                  {!(r.is_active ?? true) && (
                    <span className="rounded-full bg-zinc-100 px-1.5 py-px text-[10px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                      inactive
                    </span>
                  )}
                </div>
                {(r.capacity ?? 1) > 1 && (
                  <p className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">
                    Capacity: {r.capacity}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => setDrawerTarget(r)}
                aria-label={`Edit ${r.name}`}
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
        <ResourceFormDrawer
          projectSlug={projectSlug}
          resource={drawerTarget ?? null}
          onClose={handleClose}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
