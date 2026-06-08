"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Calendar, Copy, Check } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import { dashboardSectionCardCn } from "@/lib/styles";
import * as cache from "@/lib/cache";
import { getSettings, enableBookings } from "./api";
import { BookingSettingsForm } from "./BookingSettingsForm";
import { ServicesManager } from "./ServicesManager";
import { ResourcesManager } from "./ResourcesManager";
import { HoursEditor } from "./HoursEditor";
import { PoliciesForm } from "./PoliciesForm";
import { AppointmentsManager } from "./AppointmentsManager";
import { OverviewPanel } from "./OverviewPanel";
import { EmailTemplateEditor } from "./EmailTemplateEditor";

type Tab =
  | "overview"
  | "appointments"
  | "settings"
  | "services"
  | "resources"
  | "hours"
  | "policies"
  | "emails"
  | "embed";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "appointments", label: "Appointments" },
  { key: "settings", label: "Settings" },
  { key: "services", label: "Services" },
  { key: "resources", label: "Resources" },
  { key: "hours", label: "Hours" },
  { key: "policies", label: "Policies" },
  { key: "emails", label: "Emails" },
  { key: "embed", label: "Embed" },
];

interface Props {
  projectSlug: string;
  isAdmin: boolean;
}

/**
 * Bookings section shell — shows an enable CTA (admin) or "not enabled" message,
 * or the inner tab strip of config components once enabled.
 */
export function BookingsSection({ projectSlug, isAdmin }: Props) {
  const cacheKey = `booking-settings:${projectSlug}`;

  const { data, loading } = useQuery(cacheKey, () => getSettings(projectSlug), { ttl: 60 * 1000 });

  const [enabling, setEnabling] = useState(false);
  const [enableError, setEnableError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const reduce = useReducedMotion();

  async function handleEnable() {
    setEnabling(true);
    setEnableError(null);
    try {
      await enableBookings(projectSlug);
      cache.invalidate(cacheKey);
    } catch (err) {
      setEnableError(err instanceof Error ? err.message : "Enable failed.");
    } finally {
      setEnabling(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
        <ArcSpinner size={20} />
        Loading bookings…
      </div>
    );
  }

  // Not yet enabled
  if (!data?.enabled) {
    if (isAdmin) {
      return (
        <div className={`${dashboardSectionCardCn} max-w-lg p-6`}>
          <div className="mb-4 flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
              <Calendar aria-hidden="true" className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Bookings</h2>
              <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
                Bookings isn&apos;t enabled for this project.
              </p>
            </div>
          </div>
          {enableError && (
            <div className="mb-3 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-400">
              {enableError}
            </div>
          )}
          <button
            type="button"
            onClick={() => {
              handleEnable().catch(() => {});
            }}
            disabled={enabling}
            className="cursor-pointer rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
          >
            {enabling ? "Enabling…" : "Enable bookings"}
          </button>
        </div>
      );
    }

    // Non-admin safety net (shouldn't normally be reached due to section gating)
    return (
      <div className={`${dashboardSectionCardCn} max-w-lg p-6`}>
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
            <Calendar aria-hidden="true" className="h-4 w-4" />
          </span>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Bookings aren&apos;t enabled yet — contact your administrator.
          </p>
        </div>
      </div>
    );
  }

  // Enabled — show inner tab strip + active child
  return (
    <div>
      {/* Inner tab strip */}
      <nav
        aria-label="Booking configuration tabs"
        className="mb-6 flex gap-1 overflow-x-auto border-b border-zinc-200 pb-px dark:border-zinc-800"
      >
        {TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              aria-current={isActive ? "page" : undefined}
              className="relative shrink-0 cursor-pointer rounded-t-md px-3 py-2 text-sm font-medium whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-zinc-400/40"
            >
              <span
                className={
                  "transition-colors duration-150 " +
                  (isActive
                    ? "text-zinc-900 dark:text-zinc-100"
                    : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200")
                }
              >
                {tab.label}
              </span>
              {isActive && (
                <motion.span
                  layoutId="booking-tabs-underline"
                  className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-zinc-900 dark:bg-zinc-100"
                  transition={
                    reduce
                      ? { duration: 0 }
                      : { type: "spring", stiffness: 480, damping: 36, mass: 0.6 }
                  }
                />
              )}
            </button>
          );
        })}
      </nav>

      {/* Active tab content */}
      {activeTab === "overview" && <OverviewPanel projectSlug={projectSlug} />}
      {activeTab === "appointments" && <AppointmentsManager projectSlug={projectSlug} />}
      {activeTab === "settings" && <BookingSettingsForm projectSlug={projectSlug} />}
      {activeTab === "services" && <ServicesManager projectSlug={projectSlug} />}
      {activeTab === "resources" && <ResourcesManager projectSlug={projectSlug} />}
      {activeTab === "hours" && <HoursEditor projectSlug={projectSlug} />}
      {activeTab === "policies" && <PoliciesForm projectSlug={projectSlug} />}
      {activeTab === "emails" && <EmailTemplateEditor projectSlug={projectSlug} />}
      {activeTab === "embed" && <EmbedTab publicSlug={data.public_slug} />}
    </div>
  );
}

// ── Embed tab ──────────────────────────────────────────────────────────────────

function EmbedTab({ publicSlug }: { publicSlug?: string }) {
  const [origin] = useState(() => (typeof window !== "undefined" ? window.location.origin : ""));
  const [copied, setCopied] = useState(false);

  if (!publicSlug) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Set a public slug in Settings before embedding.
      </p>
    );
  }

  const snippet = `<script src="${origin}/embed.js" data-tenant="${publicSlug}" async></script>`;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable — silently ignore
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-1 text-sm font-semibold text-zinc-900 dark:text-zinc-50">
          Embed snippet
        </h3>
        <p className="mb-3 text-sm text-zinc-500 dark:text-zinc-400">
          Paste this on any page of the client&apos;s site — the booking widget will appear
          automatically.
        </p>
        <div className="relative rounded-lg border border-zinc-200 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900">
          <pre className="overflow-x-auto px-4 py-3 pr-12 text-xs text-zinc-800 dark:text-zinc-200">
            <code>{snippet}</code>
          </pre>
          <button
            type="button"
            onClick={() => {
              void handleCopy();
            }}
            aria-label="Copy embed snippet"
            className="absolute right-2 top-2 cursor-pointer rounded-md border border-zinc-200 bg-white p-1.5 text-zinc-500 transition-colors hover:border-zinc-400 hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:border-zinc-500 dark:hover:text-zinc-100"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <Copy className="h-3.5 w-3.5" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-50">Live preview</h3>
        <iframe
          src={`/w/${publicSlug}`}
          title="Booking widget preview"
          style={{ width: "100%", border: 0, minHeight: 500 }}
          className="rounded-lg border border-zinc-200 dark:border-zinc-700"
        />
      </div>
    </div>
  );
}
