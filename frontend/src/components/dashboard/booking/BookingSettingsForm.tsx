"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import {
  dashboardInputCn,
  dashboardFieldLabelCn,
  dashboardSectionCardCn,
  dashboardErrorBannerCn,
  dashboardSuccessBannerCn,
} from "@/lib/styles";
import * as cache from "@/lib/cache";
import { getSettings, patchSettings } from "./api";
import type { BookingSettings } from "./api";

interface Props {
  projectSlug: string;
}

type Draft = {
  business_name: string;
  timezone: string;
  locale: string;
  public_slug: string;
  owner_notification_email: string;
  meeting_url: string;
  email_from_name: string;
  slot_granularity_min: string;
  reminders_enabled: boolean;
  reminder_offsets_min: string; // comma-separated ints
  calendar_provider: string;
  widget_color: string;
};

function settingsToDraft(s: BookingSettings): Draft {
  return {
    business_name: s.business_name ?? "",
    timezone: s.timezone ?? "Europe/Berlin",
    locale: s.locale ?? "en",
    public_slug: s.public_slug ?? "",
    owner_notification_email: s.owner_notification_email ?? "",
    meeting_url: s.meeting_url ?? "",
    email_from_name: s.email_from_name ?? "",
    slot_granularity_min: String(s.slot_granularity_min ?? 15),
    reminders_enabled: s.reminders_enabled ?? true,
    reminder_offsets_min: (s.reminder_offsets_min ?? [1440, 120]).join(", "),
    calendar_provider: s.calendar_provider ?? "none",
    widget_color: s.widget_color ?? "",
  };
}

/**
 * Booking settings form — mirrors ProjectSettingsSection pattern.
 * Draft state from getSettings; PATCH on save; success/error banner.
 */
export function BookingSettingsForm({ projectSlug }: Props) {
  const cacheKey = `booking-settings:${projectSlug}`;

  const { data: raw, loading: queryLoading } = useQuery<BookingSettings>(
    cacheKey,
    () => getSettings(projectSlug),
    { ttl: 60 * 1000 }
  );

  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [slugError, setSlugError] = useState<string | null>(null);

  useEffect(() => {
    if (raw && draft === null) {
      setDraft(settingsToDraft(raw));
    }
  }, [raw, draft]);

  const loading = queryLoading && draft === null;

  function set<K extends keyof Draft>(k: K, v: Draft[K]) {
    setDraft((d) => d && { ...d, [k]: v });
    setMsg(null);
    if (k === "public_slug") setSlugError(null);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!draft) return;
    setSaving(true);
    setMsg(null);
    setSlugError(null);
    try {
      const offsets = draft.reminder_offsets_min
        .split(",")
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !Number.isNaN(n));

      const updated = await patchSettings(projectSlug, {
        business_name: draft.business_name.trim() || undefined,
        timezone: draft.timezone.trim() || undefined,
        locale: draft.locale.trim() || undefined,
        public_slug: draft.public_slug.trim() || undefined,
        owner_notification_email: draft.owner_notification_email.trim() || undefined,
        meeting_url: draft.meeting_url.trim() || undefined,
        email_from_name: draft.email_from_name.trim() || undefined,
        slot_granularity_min: parseInt(draft.slot_granularity_min, 10) || undefined,
        reminders_enabled: draft.reminders_enabled,
        reminder_offsets_min: offsets.length ? offsets : undefined,
        calendar_provider: draft.calendar_provider || undefined,
        widget_color: draft.widget_color.trim() || undefined,
      });
      cache.set(cacheKey, updated);
      setMsg({ type: "ok", text: "Settings saved." });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Save failed.";
      if (msg.toLowerCase().includes("public link") || msg.toLowerCase().includes("slug")) {
        setSlugError(msg);
      } else {
        setMsg({ type: "err", text: msg });
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-lg">
      <h2 className="mb-4 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        Booking Settings
      </h2>

      {loading && (
        <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
          <ArcSpinner size={20} />
          Loading settings…
        </div>
      )}

      {!loading && draft !== null && (
        <div className={`${dashboardSectionCardCn} p-6`}>
          <form onSubmit={handleSave} className="space-y-4">
            {msg && (
              <div
                className={msg.type === "ok" ? dashboardSuccessBannerCn : dashboardErrorBannerCn}
              >
                {msg.text}
              </div>
            )}

            <div>
              <label className={dashboardFieldLabelCn}>Business name</label>
              <input
                type="text"
                value={draft.business_name}
                onChange={(e) => set("business_name", e.target.value)}
                placeholder="Acme Ltd."
                className={dashboardInputCn}
              />
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>Widget accent color</label>
              <p className="mb-1.5 text-xs text-zinc-400 dark:text-zinc-500">
                Colors the public booking widget (button, dates, hover effects). Independent of the
                email accent. Leave blank to use the site default.
              </p>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={draft.widget_color || "#c9a961"}
                  onChange={(e) => set("widget_color", e.target.value)}
                  className="h-8 w-10 cursor-pointer rounded border border-zinc-200 bg-transparent p-0.5 dark:border-zinc-700"
                  aria-label="Pick widget accent color"
                />
                <input
                  type="text"
                  value={draft.widget_color}
                  onChange={(e) => set("widget_color", e.target.value)}
                  placeholder="#c9a961"
                  className={`${dashboardInputCn} w-32 font-mono`}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={dashboardFieldLabelCn}>Timezone</label>
                <input
                  type="text"
                  value={draft.timezone}
                  onChange={(e) => set("timezone", e.target.value)}
                  placeholder="Europe/Berlin"
                  className={dashboardInputCn}
                />
              </div>
              <div>
                <label className={dashboardFieldLabelCn}>Locale</label>
                <input
                  type="text"
                  value={draft.locale}
                  onChange={(e) => set("locale", e.target.value)}
                  placeholder="en"
                  className={dashboardInputCn}
                />
              </div>
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>Public booking link</label>
              <p className="mb-1.5 text-xs text-zinc-400 dark:text-zinc-500">
                Used in the public booking URL. Must be globally unique.
              </p>
              <input
                type="text"
                value={draft.public_slug}
                onChange={(e) => set("public_slug", e.target.value)}
                placeholder="acme"
                className={`${dashboardInputCn}${slugError ? " border-red-400 dark:border-red-600" : ""}`}
              />
              {slugError && (
                <p className="mt-1 text-xs text-red-600 dark:text-red-400">{slugError}</p>
              )}
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>Owner notification email</label>
              <input
                type="email"
                value={draft.owner_notification_email}
                onChange={(e) => set("owner_notification_email", e.target.value)}
                placeholder="owner@example.com"
                className={dashboardInputCn}
              />
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>Email from name</label>
              <input
                type="text"
                value={draft.email_from_name}
                onChange={(e) => set("email_from_name", e.target.value)}
                placeholder="Acme Bookings"
                className={dashboardInputCn}
              />
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>Meeting URL</label>
              <input
                type="url"
                value={draft.meeting_url}
                onChange={(e) => set("meeting_url", e.target.value)}
                placeholder="https://meet.example.com/acme"
                className={dashboardInputCn}
              />
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>Slot granularity (minutes)</label>
              <input
                type="number"
                min={5}
                step={5}
                value={draft.slot_granularity_min}
                onChange={(e) => set("slot_granularity_min", e.target.value)}
                className={dashboardInputCn}
              />
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>Calendar provider</label>
              <select
                value={draft.calendar_provider}
                onChange={(e) => set("calendar_provider", e.target.value)}
                className={dashboardInputCn}
              >
                <option value="none">None</option>
                <option value="google">Google Calendar</option>
              </select>
            </div>

            <div className="flex items-center justify-between">
              <label className={`${dashboardFieldLabelCn} mb-0`}>Enable reminders</label>
              <button
                type="button"
                role="switch"
                aria-checked={draft.reminders_enabled}
                onClick={() => set("reminders_enabled", !draft.reminders_enabled)}
                className={`relative inline-flex h-5 w-9 cursor-pointer items-center rounded-full transition-colors ${
                  draft.reminders_enabled
                    ? "bg-zinc-900 dark:bg-zinc-100"
                    : "bg-zinc-200 dark:bg-zinc-700"
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform dark:bg-zinc-900 ${
                    draft.reminders_enabled ? "translate-x-4" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>

            {draft.reminders_enabled && (
              <div>
                <label className={dashboardFieldLabelCn}>
                  Reminder offsets (minutes, comma-separated)
                </label>
                <p className="mb-1.5 text-xs text-zinc-400 dark:text-zinc-500">
                  E.g. 1440, 120 sends reminders 24h and 2h before.
                </p>
                <input
                  type="text"
                  value={draft.reminder_offsets_min}
                  onChange={(e) => set("reminder_offsets_min", e.target.value)}
                  placeholder="1440, 120"
                  className={dashboardInputCn}
                />
              </div>
            )}

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={saving}
                className="cursor-pointer rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
              >
                {saving ? "Saving…" : "Save settings"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
