"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { useQuery } from "@/hooks/useQuery";
import { ServiceGrid } from "@/components/dashboard/ServiceGrid";
import { ServiceEditor } from "@/components/dashboard/ServiceEditor";
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
  /** Mirrors the inline editor's unsaved-changes state upward so the section
   *  tabs can confirm before switching away from a dirty editor. */
  onEditorDirtyChange?: (dirty: boolean) => void;
}

/**
 * CMS editing area: page tabs + editable service cards, with the editor
 * rendered inline. Opening a service swaps only this area for its editor
 * (`?service=` in the URL, pushed so browser back returns to the grid) —
 * the project header and section tabs above never move.
 */
export function CmsSection({ projectSlug, isAdmin, onEditorDirtyChange }: CmsSectionProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeServiceKey = searchParams.get("service");

  const editorDirtyRef = useRef(false);
  const handleEditorDirtyChange = useCallback(
    (dirty: boolean) => {
      editorDirtyRef.current = dirty;
      onEditorDirtyChange?.(dirty);
    },
    [onEditorDirtyChange]
  );

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

  function closeEditor() {
    if (
      editorDirtyRef.current &&
      !confirm("You have unsaved changes. Leave the editor without saving?")
    ) {
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    params.delete("service");
    params.delete("locale");
    // replace, not push: closing the editor swaps the history entry so
    // browser Back afterwards doesn't reopen the editor the user just closed.
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={activeServiceKey ? `editor:${activeServiceKey}` : "grid"}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.18, ease: [0.32, 0.72, 0, 1] }}
      >
        {activeServiceKey ? (
          <ServiceEditor
            projectSlug={projectSlug}
            serviceKey={activeServiceKey}
            onBack={closeEditor}
            onDirtyChange={handleEditorDirtyChange}
          />
        ) : (
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
                isAdmin={isAdmin}
                removingKey={removingKey}
                onRemove={handleRemoveService}
              />
            )}
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
