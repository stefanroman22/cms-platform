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
import { getPolicies, patchPolicy } from "./api";
import type { BookingPolicy } from "./api";

interface Props {
  projectSlug: string;
}

type Draft = {
  allow_reschedule: boolean;
  reschedule_window_hours: string;
  max_reschedules: string;
  allow_cancel: boolean;
  cancellation_window_hours: string;
  policy_text: string;
};

function policyToDraft(p: BookingPolicy): Draft {
  return {
    allow_reschedule: p.allow_reschedule ?? true,
    reschedule_window_hours: String(p.reschedule_window_hours ?? 24),
    max_reschedules: String(p.max_reschedules ?? 2),
    allow_cancel: p.allow_cancel ?? true,
    cancellation_window_hours: String(p.cancellation_window_hours ?? 24),
    policy_text: p.policy_text ?? "",
  };
}

const defaultDraft: Draft = {
  allow_reschedule: true,
  reschedule_window_hours: "24",
  max_reschedules: "2",
  allow_cancel: true,
  cancellation_window_hours: "24",
  policy_text: "",
};

function buildPreview(draft: Draft): string {
  const parts: string[] = [];
  if (draft.allow_reschedule) {
    parts.push(
      `Rescheduling is allowed up to ${draft.reschedule_window_hours}h before the appointment (max ${draft.max_reschedules} times).`
    );
  } else {
    parts.push("Rescheduling is not allowed.");
  }
  if (draft.allow_cancel) {
    parts.push(
      `Cancellation is allowed up to ${draft.cancellation_window_hours}h before the appointment.`
    );
  } else {
    parts.push("Cancellations are not allowed.");
  }
  if (draft.policy_text.trim()) {
    parts.push(draft.policy_text.trim());
  }
  return parts.join(" ");
}

/**
 * Tenant-default policy form — mirrors ProjectSettingsSection pattern.
 * Loads via getPolicies, patches via patchPolicy (service_id = null).
 */
export function PoliciesForm({ projectSlug }: Props) {
  const cacheKey = `booking-policies:${projectSlug}`;

  const { data: raw, loading: queryLoading } = useQuery(cacheKey, () => getPolicies(projectSlug), {
    ttl: 60 * 1000,
  });

  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (raw && draft === null) {
      const tenantDefault = (raw.policies ?? []).find((p) => p.service_id == null);
      setDraft(tenantDefault ? policyToDraft(tenantDefault) : { ...defaultDraft });
    }
  }, [raw, draft]);

  const loading = queryLoading && draft === null;

  function set<K extends keyof Draft>(k: K, v: Draft[K]) {
    setDraft((d) => d && { ...d, [k]: v });
    setMsg(null);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!draft) return;
    setSaving(true);
    setMsg(null);
    try {
      await patchPolicy(projectSlug, {
        service_id: null,
        allow_reschedule: draft.allow_reschedule,
        reschedule_window_hours: parseInt(draft.reschedule_window_hours, 10) || 24,
        max_reschedules: parseInt(draft.max_reschedules, 10) || 2,
        allow_cancel: draft.allow_cancel,
        cancellation_window_hours: parseInt(draft.cancellation_window_hours, 10) || 24,
        policy_text: draft.policy_text.trim(),
      });
      setMsg({ type: "ok", text: "Policy saved." });
    } catch (err) {
      setMsg({ type: "err", text: err instanceof Error ? err.message : "Save failed." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-lg">
      <h2 className="mb-4 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        Cancellation &amp; Rescheduling Policy
      </h2>

      {loading && (
        <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
          <ArcSpinner size={20} />
          Loading policy…
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

            {/* Rescheduling */}
            <div className="flex items-center justify-between">
              <label className={`${dashboardFieldLabelCn} mb-0`}>Allow rescheduling</label>
              <button
                type="button"
                role="switch"
                aria-checked={draft.allow_reschedule}
                onClick={() => set("allow_reschedule", !draft.allow_reschedule)}
                className={`relative inline-flex h-5 w-9 cursor-pointer items-center rounded-full transition-colors ${
                  draft.allow_reschedule
                    ? "bg-zinc-900 dark:bg-zinc-100"
                    : "bg-zinc-200 dark:bg-zinc-700"
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform dark:bg-zinc-900 ${
                    draft.allow_reschedule ? "translate-x-4" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>

            {draft.allow_reschedule && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={dashboardFieldLabelCn}>Reschedule window (hours)</label>
                  <input
                    type="number"
                    min={0}
                    value={draft.reschedule_window_hours}
                    onChange={(e) => set("reschedule_window_hours", e.target.value)}
                    className={dashboardInputCn}
                  />
                </div>
                <div>
                  <label className={dashboardFieldLabelCn}>Max reschedules</label>
                  <input
                    type="number"
                    min={0}
                    value={draft.max_reschedules}
                    onChange={(e) => set("max_reschedules", e.target.value)}
                    className={dashboardInputCn}
                  />
                </div>
              </div>
            )}

            {/* Cancellation */}
            <div className="flex items-center justify-between">
              <label className={`${dashboardFieldLabelCn} mb-0`}>Allow cancellation</label>
              <button
                type="button"
                role="switch"
                aria-checked={draft.allow_cancel}
                onClick={() => set("allow_cancel", !draft.allow_cancel)}
                className={`relative inline-flex h-5 w-9 cursor-pointer items-center rounded-full transition-colors ${
                  draft.allow_cancel
                    ? "bg-zinc-900 dark:bg-zinc-100"
                    : "bg-zinc-200 dark:bg-zinc-700"
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform dark:bg-zinc-900 ${
                    draft.allow_cancel ? "translate-x-4" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>

            {draft.allow_cancel && (
              <div>
                <label className={dashboardFieldLabelCn}>Cancellation window (hours)</label>
                <input
                  type="number"
                  min={0}
                  value={draft.cancellation_window_hours}
                  onChange={(e) => set("cancellation_window_hours", e.target.value)}
                  className={dashboardInputCn}
                />
              </div>
            )}

            {/* Custom policy text */}
            <div>
              <label className={dashboardFieldLabelCn}>Custom policy text (optional)</label>
              <p className="mb-1.5 text-xs text-zinc-400 dark:text-zinc-500">
                Shown to customers alongside the auto-generated text below.
              </p>
              <textarea
                rows={3}
                value={draft.policy_text}
                onChange={(e) => set("policy_text", e.target.value)}
                placeholder="Additional terms…"
                className={`${dashboardInputCn} resize-y`}
              />
            </div>

            {/* Live preview */}
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800/50">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                Customer preview
              </p>
              <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                {buildPreview(draft)}
              </p>
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={saving}
                className="cursor-pointer rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
              >
                {saving ? "Saving…" : "Save policy"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
