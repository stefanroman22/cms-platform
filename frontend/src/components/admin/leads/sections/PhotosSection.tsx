"use client";

import { ExternalLink, X } from "lucide-react";
import type { Lead } from "../types";
import { useLeadPatch } from "../hooks/useLeadPatch";

interface PhotoMeta {
  url?: string;
  owner_photo?: boolean;
  attributions?: { name?: string | null; uri?: string | null }[];
  google_maps_uri?: string | null;
}

function metaFor(lead: Lead): Map<string, PhotoMeta> {
  const google = (lead.extra?.google ?? {}) as { photos?: PhotoMeta[] };
  const map = new Map<string, PhotoMeta>();
  for (const p of google.photos ?? []) if (p.url) map.set(p.url, p);
  return map;
}

export function PhotosSection({
  lead,
  onPatched,
}: {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}) {
  const { patch, saving, error } = useLeadPatch(lead.id, onPatched);
  const meta = metaFor(lead);

  async function remove(url: string) {
    await patch({ photo_urls: lead.photo_urls.filter((u) => u !== url) }).catch(() => {});
  }

  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
        Photos{lead.photo_urls.length > 0 && ` (${lead.photo_urls.length})`}
      </h3>
      {error && (
        <div className="mb-2 rounded-md bg-red-50 dark:bg-red-950 px-3 py-1.5 text-xs text-red-700 dark:text-red-300">
          {error}
        </div>
      )}
      {lead.photo_urls.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 text-xs text-zinc-500 dark:text-zinc-400 italic">
          No photos imported.
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {lead.photo_urls.map((url) => {
            const m = meta.get(url);
            const author = m?.attributions?.[0]?.name ?? null;
            return (
              <figure
                key={url}
                className="relative rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={url}
                  alt={author ? `Photo by ${author}` : "Listing photo"}
                  className="h-28 w-full object-cover"
                  loading="lazy"
                />
                {m?.owner_photo && (
                  <span className="absolute left-1.5 top-1.5 rounded bg-emerald-600/90 px-1.5 py-0.5 text-[10px] font-medium text-white">
                    Owner
                  </span>
                )}
                <button
                  type="button"
                  aria-label="Remove photo"
                  disabled={saving}
                  onClick={() => void remove(url)}
                  className="absolute right-1.5 top-1.5 h-6 w-6 inline-flex items-center justify-center rounded-md bg-black/60 text-white hover:bg-black/80 cursor-pointer disabled:cursor-not-allowed"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
                <figcaption className="px-2 py-1 text-[11px] text-zinc-600 dark:text-zinc-300 truncate">
                  {m?.google_maps_uri ? (
                    <a
                      href={m.google_maps_uri}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 hover:underline"
                    >
                      {author ?? "View on Google Maps"}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : (
                    (author ?? "—")
                  )}
                </figcaption>
              </figure>
            );
          })}
        </div>
      )}
    </section>
  );
}
