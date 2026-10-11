"use client";

import type { Lead } from "../types";

const STATUS_LABEL: Record<string, string> = {
  OPERATIONAL: "Operational",
  CLOSED_TEMPORARILY: "Closed temporarily",
  CLOSED_PERMANENTLY: "Closed permanently",
  FUTURE_OPENING: "Opening soon",
};

function humanize(v: string): string {
  const s = v.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function BusinessSection({ lead }: { lead: Lead }) {
  const google = (lead.extra?.google ?? {}) as {
    generative_summary?: { overview?: string | null; disclosure?: string | null } | null;
    import_warnings?: unknown;
  };
  const summary = google.generative_summary;
  const importNotes = Array.isArray(google.import_warnings)
    ? google.import_warnings.filter((w): w is string => typeof w === "string")
    : [];
  const shownTypes = (lead.types ?? []).filter(
    (t) => t !== lead.primary_type && t !== "point_of_interest" && t !== "establishment"
  );
  const hasAnything =
    lead.google_place_id ||
    lead.business_status ||
    lead.primary_type ||
    lead.price_level ||
    (lead.types?.length ?? 0) > 0;
  if (!hasAnything) return null;

  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
        Business
      </h3>
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-1.5 text-xs">
        <Row
          label="Status"
          value={
            lead.business_status
              ? (STATUS_LABEL[lead.business_status] ?? humanize(lead.business_status.toLowerCase()))
              : null
          }
        />
        <Row label="Type" value={lead.primary_type ? humanize(lead.primary_type) : null} />
        <Row label="Price level" value={lead.price_level ? humanize(lead.price_level) : null} />
        {shownTypes.length > 0 && (
          <div className="flex items-baseline gap-3">
            <span className="text-zinc-500 dark:text-zinc-400 w-24 shrink-0">Google types</span>
            <div className="flex flex-wrap gap-1">
              {shownTypes.map((t) => (
                <span
                  key={t}
                  className="rounded bg-zinc-200 dark:bg-zinc-800 px-1.5 py-0.5 text-[11px] text-zinc-700 dark:text-zinc-300"
                >
                  {t.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          </div>
        )}
        {summary?.overview && (
          <div className="pt-1">
            <div className="text-zinc-500 dark:text-zinc-400">Google summary</div>
            <p className="text-zinc-900 dark:text-zinc-100">{summary.overview}</p>
            {summary.disclosure && (
              <p className="italic text-zinc-400 dark:text-zinc-500">
                {summary.disclosure} — research only, never quote as the client&apos;s words.
              </p>
            )}
          </div>
        )}
        {lead.google_imported_at && (
          <div className="text-zinc-400 dark:text-zinc-500">
            Imported from Google on {new Date(lead.google_imported_at).toLocaleDateString()}
          </div>
        )}
        {importNotes.length > 0 && (
          <div className="text-amber-700 dark:text-amber-400">
            <div>Last import notes</div>
            <ul className="list-disc pl-4">
              {importNotes.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="text-zinc-500 dark:text-zinc-400 w-24 shrink-0">{label}</span>
      {value ? (
        <span className="text-zinc-900 dark:text-zinc-100">{value}</span>
      ) : (
        <span className="text-zinc-400 dark:text-zinc-600">—</span>
      )}
    </div>
  );
}
