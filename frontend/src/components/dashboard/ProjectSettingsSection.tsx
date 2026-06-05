"use client";

import { useEffect, useState } from "react";
import { Settings } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import {
  dashboardInputCn,
  dashboardFieldLabelCn,
  dashboardSectionCardCn,
  dashboardErrorBannerCn,
} from "@/lib/styles";
import * as cache from "@/lib/cache";

type SettingsFromApi = { website_url: string | null; allowed_origins: string[] | null };

interface ProjectSettingsSectionProps {
  projectSlug: string;
}

/**
 * Admin-only project settings (website URL + allowed origins). Mounted only
 * for admins by the parent. Shares the `settings:<slug>` cache key with the
 * project page's live-website card; saving writes back to the cache and
 * invalidates the projects list (website_url is denormalised there).
 */
export function ProjectSettingsSection({ projectSlug }: ProjectSettingsSectionProps) {
  const settingsKey = `settings:${projectSlug}`;

  const { data: settingsRaw, loading: settingsQueryLoading } = useQuery<SettingsFromApi>(
    settingsKey,
    () =>
      fetch(`/api/projects/${projectSlug}/settings`, { credentials: "include" }).then((r) =>
        r.json()
      ),
    { ttl: 5 * 60 * 1000 }
  );

  const [settingsDraft, setSettingsDraft] = useState<{
    website_url: string;
    allowed_origins: string;
  } | null>(null);

  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (settingsRaw && settingsDraft === null) {
      setSettingsDraft({
        website_url: settingsRaw.website_url ?? "",
        allowed_origins: (settingsRaw.allowed_origins ?? []).join("\n"),
      });
    }
  }, [settingsRaw, settingsDraft]);

  const settingsLoading = settingsQueryLoading && settingsDraft === null;

  async function handleSaveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!settingsDraft) return;
    setSettingsSaving(true);
    setSettingsMsg(null);
    try {
      const r = await fetch(`/api/projects/${projectSlug}/settings`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          website_url: settingsDraft.website_url.trim() || null,
          allowed_origins: settingsDraft.allowed_origins
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail ?? "Failed to save settings.");
      }
      cache.set(settingsKey, {
        website_url: settingsDraft.website_url.trim() || null,
        allowed_origins: settingsDraft.allowed_origins
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      cache.invalidate("projects");
      setSettingsMsg({ type: "ok", text: "Settings saved." });
    } catch (err) {
      setSettingsMsg({ type: "err", text: err instanceof Error ? err.message : "Save failed." });
    } finally {
      setSettingsSaving(false);
    }
  }

  return (
    <div className="max-w-lg">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        <Settings aria-hidden="true" className="h-4 w-4" />
        Project Settings
      </h2>

      {settingsLoading && (
        <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
          <ArcSpinner size={20} />
          Loading project settings…
        </div>
      )}

      {!settingsLoading && settingsDraft !== null && (
        <div className={`${dashboardSectionCardCn} p-6`}>
          <form onSubmit={handleSaveSettings} className="space-y-4">
            {settingsMsg && (
              <div
                className={
                  settingsMsg.type === "ok"
                    ? "rounded-lg border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-300"
                    : dashboardErrorBannerCn
                }
              >
                {settingsMsg.text}
              </div>
            )}

            <div>
              <label className={dashboardFieldLabelCn}>Website URL</label>
              <p className="mb-1.5 text-xs text-zinc-400 dark:text-zinc-500">
                The production URL of the client&apos;s website.
              </p>
              <input
                type="url"
                value={settingsDraft.website_url}
                onChange={(e) =>
                  setSettingsDraft((s) => s && { ...s, website_url: e.target.value })
                }
                placeholder="https://example.com"
                className={dashboardInputCn}
              />
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>Allowed origins</label>
              <p className="mb-1.5 text-xs text-zinc-400 dark:text-zinc-500">
                One origin per line. Form submissions from unlisted origins will be rejected. Leave
                empty to allow any origin.
              </p>
              <textarea
                rows={4}
                value={settingsDraft.allowed_origins}
                onChange={(e) =>
                  setSettingsDraft((s) => s && { ...s, allowed_origins: e.target.value })
                }
                placeholder={"https://example.com\nhttps://www.example.com"}
                className={`${dashboardInputCn} resize-y font-mono text-xs`}
              />
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={settingsSaving}
                className="cursor-pointer rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
              >
                {settingsSaving ? "Saving…" : "Save settings"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
