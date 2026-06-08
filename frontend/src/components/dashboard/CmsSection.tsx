"use client";

import { useState } from "react";
import { useQuery } from "@/hooks/useQuery";
import { ServiceGrid } from "@/components/dashboard/ServiceGrid";
import type { ServiceCardService } from "@/components/dashboard/ServiceCard";
import * as cache from "@/lib/cache";

function fetchServices(projectSlug: string): Promise<ServiceCardService[]> {
  return fetch(`/api/projects/${projectSlug}/services`, {
    credentials: "include",
    cache: "no-store",
  }).then(async (r) => {
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail ?? "Failed to load services.");
    }
    return r.json();
  });
}

interface CmsSectionProps {
  projectSlug: string;
  isAdmin: boolean;
}

/**
 * CMS editing area: page tabs + editable service cards. Owns its own services
 * fetch, loading skeleton, error display, and service removal. Extracted from
 * the project page so each section is self-contained.
 */
export function CmsSection({ projectSlug, isAdmin }: CmsSectionProps) {
  const servicesKey = `services:${projectSlug}`;
  const {
    data: services,
    loading,
    error,
    refresh,
  } = useQuery<ServiceCardService[]>(servicesKey, () => fetchServices(projectSlug), {
    ttl: 60 * 1000,
  });

  const [removingKey, setRemovingKey] = useState<string | null>(null);

  async function handleRemoveService(serviceKey: string) {
    if (!confirm(`Remove service "${serviceKey}"? This will also delete its content.`)) return;
    setRemovingKey(serviceKey);
    try {
      await fetch(`/api/projects/${projectSlug}/services/${serviceKey}`, {
        method: "DELETE",
        credentials: "include",
      });
      cache.invalidate(servicesKey);
      refresh();
    } finally {
      setRemovingKey(null);
    }
  }

  return (
    <div>
      {error && <p className="mb-6 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
            />
          ))}
        </div>
      )}

      {!loading && (
        <ServiceGrid
          services={services ?? []}
          projectSlug={projectSlug}
          isAdmin={isAdmin}
          removingKey={removingKey}
          onRemove={handleRemoveService}
        />
      )}
    </div>
  );
}
