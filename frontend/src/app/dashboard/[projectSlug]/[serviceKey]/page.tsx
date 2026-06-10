"use client";

import { use, useState, useCallback } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import {
  ArrowLeft,
  ChevronRight,
  Save,
  CheckCircle,
  AlertCircle,
  Languages,
  RefreshCw,
} from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ServiceIcon } from "@/components/dashboard/ServiceIcon";
import { EDITOR_MAP } from "@/components/dashboard/editors";
import { PreviewPublishBar } from "@/components/dashboard/PreviewPublishBar";
import { LocaleTabs } from "@/components/dashboard/LocaleTabs";
import {
  dashboardSectionCardCn,
  dashboardErrorBannerCn,
  dashboardSuccessBannerCn,
} from "@/lib/styles";

interface ServiceDetail {
  id: string;
  service_key: string;
  label: string | null;
  service_type_slug: string;
  service_type_name: string;
  service_type_icon: string;
  schema: Record<string, unknown>;
  content: Record<string, unknown>;
  last_updated: string | null;
  locale?: string;
  default_locale?: string;
  locales?: string[];
  translation_status?: Record<string, string> | null;
}

function fetchServiceDetail(
  projectSlug: string,
  serviceKey: string,
  locale?: string
): Promise<ServiceDetail> {
  const q = locale ? `?locale=${encodeURIComponent(locale)}` : "";
  return fetch(`/api/projects/${projectSlug}/services/${serviceKey}${q}`, {
    credentials: "include",
    cache: "no-store",
  }).then((r) => {
    if (!r.ok) throw new Error("Failed to load service.");
    return r.json();
  });
}

async function saveContent(
  projectSlug: string,
  serviceKey: string,
  content: Record<string, unknown>,
  locale?: string
): Promise<void> {
  const q = locale ? `?locale=${encodeURIComponent(locale)}` : "";
  const r = await fetch(`/api/projects/${projectSlug}/services/${serviceKey}${q}`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? "Failed to save.");
  }
}

async function uploadFile(projectSlug: string, serviceKey: string, file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`/api/projects/${projectSlug}/services/${serviceKey}/upload`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? "Upload failed.");
  }
  const data = await r.json();
  return data.url as string;
}

export default function ServiceEditorPage({
  params,
}: {
  params: Promise<{ projectSlug: string; serviceKey: string }>;
}) {
  const { projectSlug, serviceKey } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const localeParam = searchParams.get("locale") || "";
  const cacheKey = `service:${projectSlug}:${serviceKey}:${localeParam || "default"}`;

  const {
    data: service,
    loading,
    error,
    refresh,
  } = useQuery<ServiceDetail>(
    cacheKey,
    () => fetchServiceDetail(projectSlug, serviceKey, localeParam || undefined),
    {
      ttl: 60 * 1000,
    }
  );

  // draft === null means no unsaved changes
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [retranslating, setRetranslating] = useState(false);

  const isDirty = draft !== null;

  const handleChange = useCallback((content: Record<string, unknown>) => {
    setDraft(content);
    setSaveSuccess(false);
  }, []);

  const handleUpload = useCallback(
    (file: File) => uploadFile(projectSlug, serviceKey, file),
    [projectSlug, serviceKey]
  );

  async function handleSave() {
    if (!service) return;
    const content = draft ?? service.content;
    setSaving(true);
    setSaveError("");
    setSaveSuccess(false);
    try {
      await saveContent(projectSlug, serviceKey, content, localeParam || undefined);
      setSaveSuccess(true);
      setDraft(null);
      refresh();
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  const setLocale = useCallback(
    (loc: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (loc === service?.default_locale) params.delete("locale");
      else params.set("locale", loc);
      setDraft(null);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [router, pathname, searchParams, service?.default_locale]
  );

  async function handleRetranslate() {
    if (!activeLocale) return;
    setRetranslating(true);
    setSaveError("");
    try {
      const r = await fetch(
        `/api/projects/${projectSlug}/services/${serviceKey}/retranslate?locale=${encodeURIComponent(activeLocale)}`,
        { method: "POST", credentials: "include" }
      );
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        throw new Error(b.detail ?? "Re-translate failed.");
      }
      setDraft(null);
      refresh();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Re-translate failed.");
    } finally {
      setRetranslating(false);
    }
  }

  const reduce = useReducedMotion();
  const activeLocale = service?.locale ?? service?.default_locale ?? "";
  const defaultLocale = service?.default_locale ?? "";
  const locales = service?.locales ?? [];
  const isNonDefault = !!activeLocale && !!defaultLocale && activeLocale !== defaultLocale;
  const status = service?.translation_status ?? null;
  const reviewCount = status ? Object.values(status).filter((s) => s === "stale").length : 0;
  const manualCount = status ? Object.values(status).filter((s) => s === "manual").length : 0;
  const autoCount = status ? Object.values(status).filter((s) => s === "auto").length : 0;

  const serviceLabel = service?.label ?? serviceKey;
  const EditorComponent = service ? EDITOR_MAP[service.service_type_slug] : null;

  return (
    <div className="p-4 md:p-8">
      <PreviewPublishBar projectSlug={projectSlug} projectName={projectSlug} />

      {/* Back button — restores the previous page including the active
                tab via browser history. Distinct from the breadcrumb's
                project link, which always returns to the first tab. */}
      <button
        type="button"
        onClick={() => router.back()}
        aria-label="Go back to previous page"
        className="cursor-pointer mb-4 inline-flex items-center gap-1.5 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:border-zinc-300 hover:bg-zinc-50 hover:text-zinc-900 active:scale-[0.98] dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:border-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back
      </button>

      {/* Breadcrumb */}
      <div className="mb-6 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm text-zinc-400 dark:text-zinc-500">
        <Link
          href="/dashboard"
          className="hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors"
        >
          Projects
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link
          href={`/dashboard/${projectSlug}`}
          className="flex items-center gap-1 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {projectSlug}
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-zinc-700 font-medium dark:text-zinc-200">{serviceLabel}</span>
      </div>

      {/* Header */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          {service && (
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800">
              <ServiceIcon
                name={service.service_type_icon}
                className="h-5 w-5 text-zinc-600 dark:text-zinc-300"
              />
            </span>
          )}
          <div>
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
              {serviceLabel}
            </h1>
            {service && (
              <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
                {service.service_type_name}
              </p>
            )}
          </div>
        </div>

        {service && (
          <div className="flex items-center gap-3">
            {isDirty && (
              <span className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
                <AlertCircle className="h-3.5 w-3.5" />
                Unsaved changes
              </span>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer dark:bg-zinc-700 dark:hover:bg-zinc-600"
            >
              <Save className="h-4 w-4" />
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        )}
      </div>

      {/* Locale tabs */}
      {service && locales.length > 1 && (
        <LocaleTabs
          locales={locales}
          activeLocale={activeLocale}
          defaultLocale={defaultLocale}
          onSelect={setLocale}
        />
      )}

      {/* Non-default locale status banner */}
      {service && isNonDefault && (
        <div className="mb-6 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-300">
              <Languages aria-hidden="true" className="h-4 w-4" />
              <span>
                Editing <span className="font-semibold uppercase">{activeLocale}</span> —
                auto-translated from <span className="uppercase">{defaultLocale}</span>. Your edits
                become manual overrides.
              </span>
            </div>
            <button
              type="button"
              onClick={handleRetranslate}
              disabled={retranslating}
              className="cursor-pointer inline-flex items-center gap-1.5 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 transition-colors hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              <RefreshCw
                aria-hidden="true"
                className={`h-3.5 w-3.5 ${retranslating ? "animate-spin" : ""}`}
              />
              {retranslating
                ? "Re-translating…"
                : `Re-translate from ${defaultLocale.toUpperCase()}`}
            </button>
          </div>
          {status && (
            <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
              <span className="rounded bg-sky-100 px-1.5 py-0.5 text-sky-700 dark:bg-sky-950 dark:text-sky-300">
                ⚡ {autoCount} auto
              </span>
              {manualCount > 0 && (
                <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                  ✎ {manualCount} manual
                </span>
              )}
              {reviewCount > 0 && (
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                  ⚠ {reviewCount} need review
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Feedback */}
      {saveError && <div className={`${dashboardErrorBannerCn} mb-6`}>{saveError}</div>}
      {saveSuccess && (
        <div className={`${dashboardSuccessBannerCn} mb-6`}>
          <CheckCircle className="h-4 w-4 shrink-0" />
          Changes saved successfully.
        </div>
      )}

      {/* First load only — skeleton (no stale data to show yet). */}
      {loading && !service && (
        <div className="h-64 rounded-xl border border-zinc-200 bg-white animate-pulse dark:border-zinc-800 dark:bg-zinc-900" />
      )}

      {/* Fetch error (only when there's nothing to show). */}
      {!loading && error && !service && <div className={dashboardErrorBannerCn}>{error}</div>}

      {/* Editor — stale-while-revalidate on locale switch: keep the current editor
          visible during the refetch (with a subtle loading veil) and cross-fade to
          the new locale's content when it arrives, so switching NL/EN is smooth and
          never blanks. Keyed on service.id + activeLocale so it re-mounts cleanly. */}
      {service && EditorComponent && (
        <div className="relative">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={`${service.id}:${activeLocale}`}
              initial={{ opacity: 0, y: reduce ? 0 : 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: reduce ? 0 : -6 }}
              transition={{ duration: reduce ? 0.12 : 0.2, ease: [0.2, 0, 0, 1] }}
            >
              <EditorComponent
                initialContent={service.content}
                onChange={handleChange}
                onUpload={handleUpload}
              />
            </motion.div>
          </AnimatePresence>
          {loading && (
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 rounded-xl bg-white/40 backdrop-blur-[1px] dark:bg-zinc-950/40"
            />
          )}
        </div>
      )}

      {/* Unknown service type fallback */}
      {!loading && service && !EditorComponent && (
        <div className={dashboardSectionCardCn}>
          <div className="p-5">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              No editor available for service type{" "}
              <span className="font-mono text-zinc-700 dark:text-zinc-300">
                {service.service_type_slug}
              </span>
              .
            </p>
          </div>
        </div>
      )}

      {/* Last saved */}
      {service?.last_updated && (
        <p className="mt-4 text-xs text-zinc-400 dark:text-zinc-500">
          Last saved:{" "}
          {new Date(service.last_updated).toLocaleString("en-GB", {
            day: "numeric",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      )}
    </div>
  );
}
