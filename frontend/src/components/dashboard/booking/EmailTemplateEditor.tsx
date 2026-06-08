"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { CheckCircle, RotateCcw, Upload, X } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ArcSpinner } from "@/components/ui/ArcSpinner";
import {
  dashboardErrorBannerCn,
  dashboardFieldLabelCn,
  dashboardInputCn,
  dashboardSectionCardCn,
  dashboardSuccessBannerCn,
} from "@/lib/styles";
import * as cache from "@/lib/cache";
import { getEmailTemplate, patchSettings, uploadBookingLogo } from "./api";
import type { EmailDraft, EmailTemplateData, EmailTemplateField } from "./api";
import { EmailPreviewFrame } from "./EmailPreviewFrame";

interface Props {
  projectSlug: string;
}

type CaseKey = "confirmation" | "reschedule" | "cancellation" | "reminder";

const CASE_TABS: { key: CaseKey; label: string }[] = [
  { key: "confirmation", label: "Confirmation" },
  { key: "reschedule", label: "Reschedule" },
  { key: "cancellation", label: "Cancellation" },
  { key: "reminder", label: "Reminder" },
];

// Keys that get a single-line <input>; everything else gets <textarea>
const INPUT_KEYS = new Set([
  "confirm_subject",
  "reschedule_subject",
  "cancel_subject",
  "reminder_subject",
  "manage_cta",
  "join_cta",
  "add_cal_cta",
]);

function isMultiline(key: string): boolean {
  return !INPUT_KEYS.has(key);
}

function FieldEditor({
  field,
  value,
  onChange,
  onReset,
}: {
  field: EmailTemplateField;
  value: string;
  onChange: (v: string) => void;
  onReset: () => void;
}) {
  const hasOverride = value !== "";
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2">
        <label className={`${dashboardFieldLabelCn} mb-0`}>{field.label}</label>
        {hasOverride && (
          <button
            type="button"
            onClick={onReset}
            title="Reset to default"
            className="flex cursor-pointer items-center gap-1 text-xs text-zinc-400 transition-colors hover:text-zinc-700 dark:text-zinc-500 dark:hover:text-zinc-300"
          >
            <RotateCcw className="h-3 w-3" aria-hidden="true" />
            Reset
          </button>
        )}
      </div>
      {isMultiline(field.key) ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.default}
          rows={3}
          className={`${dashboardInputCn} resize-y`}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.default}
          className={dashboardInputCn}
        />
      )}
    </div>
  );
}

/**
 * Split-view email template editor.
 * Left: brand controls + per-case fields. Right: live preview iframe.
 */
export function EmailTemplateEditor({ projectSlug }: Props) {
  const cacheKey = `email-template:${projectSlug}`;

  const { data, loading, error } = useQuery(cacheKey, () => getEmailTemplate(projectSlug), {
    ttl: 60 * 1000,
  });

  const [draft, setDraft] = useState<EmailDraft | null>(null);
  const [activeCase, setActiveCase] = useState<CaseKey>("confirmation");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const prefersReduced = useReducedMotion();

  // Seed draft from loaded data (only once)
  useEffect(() => {
    if (data && draft === null) {
      const emailCopy: Record<string, string> = {};
      for (const f of data.fields) {
        if (f.value) emailCopy[f.key] = f.value;
      }
      setDraft({
        logo_url: data.brand.logo_url ?? "",
        accent_color: data.brand.accent_color ?? "#18181b",
        business_name: data.brand.business_name ?? "",
        email_copy: emailCopy,
      });
    }
  }, [data, draft]);

  // The mobile preview is a full-screen opaque overlay. On mobile, Back is the
  // natural way to dismiss a full-screen view — so while the sheet is open we push a
  // sentinel history entry and close the sheet when it's popped. Without this, Back
  // leaves the opaque sheet covering the dashboard (a black screen in dark mode).
  useEffect(() => {
    if (!showPreview) return;
    window.history.pushState({ bookingEmailPreview: true }, "");
    const onPop = () => setShowPreview(false);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [showPreview]);

  // Close the sheet and, if our sentinel entry is on top, remove it so history stays
  // clean. Closing immediately keeps the UX snappy; the popstate listener is torn
  // down by the effect, so the resulting pop is a harmless no-op.
  function closePreview() {
    setShowPreview(false);
    if (typeof window !== "undefined" && window.history.state?.bookingEmailPreview) {
      window.history.back();
    }
  }

  function setField<K extends keyof EmailDraft>(k: K, v: EmailDraft[K]) {
    setDraft((d) => d && { ...d, [k]: v });
    setMsg(null);
  }

  function setCopyKey(key: string, value: string) {
    setDraft((d) => {
      if (!d) return d;
      const copy = { ...d.email_copy };
      if (value === "") {
        delete copy[key];
      } else {
        copy[key] = value;
      }
      return { ...d, email_copy: copy };
    });
    setMsg(null);
  }

  function resetCopyKey(key: string) {
    setCopyKey(key, "");
  }

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoError(null);
    setLogoUploading(true);
    try {
      const result = await uploadBookingLogo(projectSlug, file);
      setField("logo_url", result.url);
    } catch (err) {
      setLogoError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setLogoUploading(false);
      // Clear the file input so the same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function handleRemoveLogo() {
    setField("logo_url", "");
    setMsg(null);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!draft) return;
    setSaving(true);
    setMsg(null);
    try {
      await patchSettings(projectSlug, {
        logo_url: draft.logo_url || undefined,
        accent_color: draft.accent_color || undefined,
        business_name: draft.business_name || undefined,
        email_copy: draft.email_copy,
      });
      // Optimistically refresh ONLY the email-template cache with the saved
      // draft so a remount shows the saved values. Do NOT invalidate
      // `booking-settings:` — that key drives the section's "enabled" gate, and
      // cache.invalidate notifies subscribers with `null` (no refetch), which
      // would flip the whole Bookings section to the "Enable bookings" screen.
      // cache.set keeps mounted consumers populated.
      if (data) {
        const refreshed: EmailTemplateData = {
          brand: {
            logo_url: draft.logo_url || null,
            accent_color: draft.accent_color || null,
            business_name: draft.business_name || null,
          },
          fields: data.fields.map((f) => ({
            ...f,
            value: draft.email_copy?.[f.key] ?? "",
          })),
        };
        cache.set(cacheKey, refreshed);
      }
      setMsg({ type: "ok", text: "Email settings saved." });
    } catch (err) {
      setMsg({ type: "err", text: err instanceof Error ? err.message : "Save failed." });
    } finally {
      setSaving(false);
    }
  }

  if (loading && draft === null) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200 bg-white/40 px-6 py-8 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
        <ArcSpinner size={20} />
        Loading email settings…
      </div>
    );
  }

  if (error && draft === null) {
    return <div className={dashboardErrorBannerCn}>Failed to load email template: {error}</div>;
  }

  if (!draft) return null;

  // Fields for the active case tab
  const caseFields = (data?.fields ?? []).filter((f) => f.group === activeCase);
  const sharedFields = (data?.fields ?? []).filter((f) => f.group === "shared");

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Email Templates</h2>
        {/* Mobile preview toggle */}
        <button
          type="button"
          onClick={() => (showPreview ? closePreview() : setShowPreview(true))}
          className="cursor-pointer rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 lg:hidden"
        >
          {showPreview ? "Hide preview" : "Show preview"}
        </button>
      </div>

      <form onSubmit={handleSave}>
        <div className="grid gap-6 lg:grid-cols-2">
          {/* ── Left: controls (scrollable) ──────────────────────────────── */}
          <div className="space-y-5 overflow-y-auto">
            {msg && (
              <div
                className={msg.type === "ok" ? dashboardSuccessBannerCn : dashboardErrorBannerCn}
              >
                {msg.type === "ok" && (
                  <CheckCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
                )}
                {msg.text}
              </div>
            )}

            {/* Brand card */}
            <div className={`${dashboardSectionCardCn} p-4`}>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Brand
              </h3>

              {/* Logo upload */}
              <div className="mb-4">
                <label className={dashboardFieldLabelCn}>Logo</label>
                <div className="flex flex-wrap items-center gap-3">
                  {draft.logo_url && (
                    <div className="relative h-14 w-auto">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={draft.logo_url}
                        alt="Logo preview"
                        className="h-14 max-w-[120px] rounded border border-zinc-200 object-contain dark:border-zinc-700"
                      />
                      <button
                        type="button"
                        onClick={handleRemoveLogo}
                        aria-label="Remove logo"
                        className="absolute -right-2 -top-2 flex h-5 w-5 cursor-pointer items-center justify-center rounded-full bg-zinc-900 text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-700 dark:hover:bg-zinc-600"
                      >
                        <X className="h-3 w-3" aria-hidden="true" />
                      </button>
                    </div>
                  )}
                  <div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      onChange={handleLogoUpload}
                      className="sr-only"
                      id="logo-upload"
                    />
                    <label
                      htmlFor="logo-upload"
                      className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:border-zinc-400 hover:text-zinc-900 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-zinc-500 dark:hover:text-zinc-200"
                    >
                      {logoUploading ? (
                        <>
                          <ArcSpinner size={12} />
                          Uploading…
                        </>
                      ) : (
                        <>
                          <Upload className="h-3.5 w-3.5" aria-hidden="true" />
                          {draft.logo_url ? "Change logo" : "Upload logo"}
                        </>
                      )}
                    </label>
                  </div>
                </div>
                {logoError && (
                  <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">{logoError}</p>
                )}
              </div>

              {/* Email accent color (independent of the booking widget color, set
                  under Booking Settings) */}
              <div>
                <label className={dashboardFieldLabelCn}>Email accent color</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={draft.accent_color ?? "#18181b"}
                    onChange={(e) => setField("accent_color", e.target.value)}
                    className="h-8 w-10 cursor-pointer rounded border border-zinc-200 bg-transparent p-0.5 dark:border-zinc-700"
                    aria-label="Pick accent color"
                  />
                  <input
                    type="text"
                    value={draft.accent_color ?? ""}
                    onChange={(e) => setField("accent_color", e.target.value)}
                    placeholder="#18181b"
                    className={`${dashboardInputCn} w-32 font-mono`}
                  />
                </div>
              </div>
            </div>

            {/* Case selector */}
            <div>
              <div
                role="group"
                aria-label="Email case"
                className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 dark:border-zinc-700 dark:bg-zinc-800/50"
              >
                {CASE_TABS.map((tab) => {
                  const active = activeCase === tab.key;
                  return (
                    <button
                      key={tab.key}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setActiveCase(tab.key)}
                      className={`cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                        active
                          ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100"
                          : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                      }`}
                    >
                      {tab.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Case-specific fields */}
            {caseFields.length > 0 && (
              <div className={`${dashboardSectionCardCn} p-4`}>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  {CASE_TABS.find((t) => t.key === activeCase)?.label} email
                </h3>
                <div className="space-y-4">
                  {caseFields.map((field) => (
                    <FieldEditor
                      key={field.key}
                      field={field}
                      value={draft.email_copy?.[field.key] ?? ""}
                      onChange={(v) => setCopyKey(field.key, v)}
                      onReset={() => resetCopyKey(field.key)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Shared fields */}
            {sharedFields.length > 0 && (
              <div className={`${dashboardSectionCardCn} p-4`}>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  Shared (all emails)
                </h3>
                <div className="space-y-4">
                  {sharedFields.map((field) => (
                    <FieldEditor
                      key={field.key}
                      field={field}
                      value={draft.email_copy?.[field.key] ?? ""}
                      onChange={(v) => setCopyKey(field.key, v)}
                      onReset={() => resetCopyKey(field.key)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Save */}
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="cursor-pointer rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
              >
                {saving ? "Saving…" : "Save email settings"}
              </button>
            </div>
          </div>

          {/* ── Right: preview (sticky on desktop only) ────────────────── */}
          <div className="hidden lg:sticky lg:top-4 lg:block">
            <EmailPreviewFrame slug={projectSlug} caseKey={activeCase} draft={draft} />
          </div>
        </div>
      </form>

      {/* Mobile full-screen preview sheet (desktop uses the split-view above) */}
      <AnimatePresence>
        {showPreview && (
          <motion.div
            key="email-preview-sheet"
            role="dialog"
            aria-modal="true"
            aria-label="Email preview"
            initial={{ opacity: 0, y: prefersReduced ? 0 : "100%" }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: prefersReduced ? 0 : "100%" }}
            transition={{ duration: prefersReduced ? 0 : 0.28, ease: "easeOut" }}
            className="fixed inset-0 z-50 flex flex-col bg-white dark:bg-zinc-950 lg:hidden"
          >
            <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
              <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Preview</h3>
              <button
                type="button"
                onClick={closePreview}
                className="cursor-pointer rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
              >
                Done
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <EmailPreviewFrame slug={projectSlug} caseKey={activeCase} draft={draft} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
