"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { ArrowLeft, Save, CheckCircle, AlertCircle, Languages, RefreshCw } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import * as cache from "@/lib/cache";
import { ServiceIcon } from "@/components/dashboard/ServiceIcon";
import { EDITOR_MAP } from "@/components/dashboard/editors";
import { LocaleTabs } from "@/components/dashboard/LocaleTabs";
import {
  type ServiceDetail,
  fetchServiceDetail,
  saveServiceContent,
  serviceDetailKey,
  serviceDetailPrefix,
  servicesListKey,
  projectStatusKey,
  prefetchServiceDetail,
} from "@/components/dashboard/serviceApi";
import {
  dashboardSectionCardCn,
  dashboardErrorBannerCn,
  dashboardSuccessBannerCn,
} from "@/lib/styles";

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

interface ServiceEditorProps {
  projectSlug: string;
  serviceKey: string;
  /** Returns to the CMS content grid. The editor renders inline inside the
   *  CMS section, so "back" is a state change, not a route change. */
  onBack: () => void;
  /** Reports unsaved-changes state so ancestors (section tabs, back button)
   *  can confirm before navigating the editor away. */
  onDirtyChange?: (dirty: boolean) => void;
}

/**
 * Inline service editor — rendered by CmsSection below the persistent
 * project header + section tabs, in place of the content grid. Locale
 * selection stays in the URL (`?locale=`) so deep links round-trip.
 */
export function ServiceEditor({
  projectSlug,
  serviceKey,
  onBack,
  onDirtyChange,
}: ServiceEditorProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const localeParam = searchParams.get("locale") || "";
  const cacheKey = serviceDetailKey(projectSlug, serviceKey, localeParam || undefined);

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

  // Bumped only when content changes underneath us (re-translate, or a newer
  // server version arriving while there are no unsaved edits). Our own save
  // never remounts the editor, so focus, cursor and undo history survive it.
  const [editorRevision, setEditorRevision] = useState(0);
  const ownSaveStampRef = useRef<string | null>(null);
  const seenStampRef = useRef<{ key: string; stamp: string | null } | undefined>(undefined);
  // Counts edits so a save only clears the draft if nothing was typed meanwhile.
  const changeSeqRef = useRef(0);
  const draftRef = useRef(draft);
  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);
  const savingRef = useRef(false);

  useEffect(() => {
    if (!service) return;
    const stamp = service.last_updated;
    const seen = seenStampRef.current;
    if (seen === undefined || seen.key !== cacheKey) {
      seenStampRef.current = { key: cacheKey, stamp };
      return;
    }
    if (stamp === seen.stamp) return;
    // Only a strictly newer version counts; a stale in-flight GET must not
    // remount the editor with older content.
    // A first-ever stamp (seen null) counts as newer; unparsable stamps never do.
    const newer =
      stamp !== null && (seen.stamp === null || Date.parse(stamp) > Date.parse(seen.stamp));
    seenStampRef.current = { key: cacheKey, stamp: newer ? stamp : seen.stamp };
    if (!newer) return;
    if (stamp === ownSaveStampRef.current) return; // our own save
    if (draftRef.current !== null) return; // never clobber unsaved edits
    setEditorRevision((r) => r + 1);
  }, [service, cacheKey]);

  const isDirty = draft !== null;

  // useQuery keeps the previous key's data while a new key loads (or fails), so
  // `service` can belong to a different locale than the one requested.
  const requestedLocale = localeParam || service?.default_locale;
  const localeMismatch = !!service?.locale && service.locale !== requestedLocale;
  const busy = loading || localeMismatch;

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  // Clear the dirty flag when the editor unmounts (section switch, project
  // switch) so a stale flag can't keep guarding navigation afterwards.
  useEffect(() => {
    return () => onDirtyChange?.(false);
  }, [onDirtyChange]);

  const handleChange = useCallback((content: Record<string, unknown>) => {
    changeSeqRef.current += 1;
    setDraft(content);
    setSaveSuccess(false);
  }, []);

  const handleUpload = useCallback(
    (file: File) => uploadFile(projectSlug, serviceKey, file),
    [projectSlug, serviceKey]
  );

  async function handleSave() {
    if (!service || savingRef.current || loading || localeMismatch) return;
    const content = draft ?? service.content;
    const seqAtStart = changeSeqRef.current;
    savingRef.current = true;
    setSaving(true);
    setSaveError("");
    setSaveSuccess(false);
    try {
      const saved = await saveServiceContent(
        projectSlug,
        serviceKey,
        content,
        localeParam || undefined
      );
      ownSaveStampRef.current = saved.last_updated;
      // Other locales were re-translated server-side; the grid's dates and the
      // publish bar's unpublished count changed too.
      cache.invalidatePrefix(serviceDetailPrefix(projectSlug, serviceKey), { except: cacheKey });
      cache.set(cacheKey, saved);
      cache.invalidate(servicesListKey(projectSlug));
      cache.invalidate(projectStatusKey(projectSlug));
      setSaveSuccess(true);
      if (changeSeqRef.current === seqAtStart) setDraft(null);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  const handleSaveRef = useRef(handleSave);
  useEffect(() => {
    handleSaveRef.current = handleSave;
  });

  // Ctrl/Cmd+S saves (and never opens the browser's "Save page" dialog).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void handleSaveRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // beforeunload guard while dirty
  useEffect(() => {
    if (!isDirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [isDirty]);

  const confirmDiscard = useCallback(
    () => !isDirty || window.confirm("You have unsaved changes. Discard them?"),
    [isDirty]
  );

  const setLocale = useCallback(
    (loc: string) => {
      if (!confirmDiscard()) return;
      const params = new URLSearchParams(searchParams.toString());
      if (loc === service?.default_locale) params.delete("locale");
      else params.set("locale", loc);
      setDraft(null);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [router, pathname, searchParams, service?.default_locale, confirmDiscard]
  );

  async function handleRetranslate() {
    if (!activeLocale) return;
    if (!confirmDiscard()) return;
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
      cache.invalidate(projectStatusKey(projectSlug));
      cache.invalidate(servicesListKey(projectSlug));
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
    <div>
      {/* Back to the content grid — an inline state change, so the project
          header and section tabs above never move. */}
      <button
        type="button"
        onClick={onBack}
        aria-label="Back to content list"
        className="cursor-pointer mb-6 inline-flex items-center gap-1.5 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-600 transition-colors hover:border-zinc-300 hover:bg-zinc-50 hover:text-zinc-900 active:scale-[0.98] dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:border-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to content
      </button>

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
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {serviceLabel}
            </h2>
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
              disabled={saving || busy}
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
          onPrefetch={(loc) =>
            prefetchServiceDetail(projectSlug, serviceKey, loc === defaultLocale ? undefined : loc)
          }
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
      {!loading && error && (!service || localeMismatch) && (
        <div className={dashboardErrorBannerCn}>{error}</div>
      )}

      {/* Editor — stale-while-revalidate on locale switch: keep the current editor
          visible during the refetch (with a subtle loading veil) and cross-fade to
          the new locale's content when it arrives, so switching NL/EN is smooth and
          never blanks. Keyed on service.id + activeLocale so it re-mounts cleanly. The
          editor is inert while another locale loads, so typing can't land in the
          wrong language. */}
      {service && EditorComponent && (
        <div className="relative" data-testid="service-editor-body" inert={busy} aria-busy={busy}>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={`${service.id}:${activeLocale}`}
              initial={{ opacity: 0, y: reduce ? 0 : 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: reduce ? 0 : -6 }}
              transition={{ duration: reduce ? 0.12 : 0.2, ease: [0.2, 0, 0, 1] }}
            >
              <EditorComponent
                key={editorRevision}
                initialContent={service.content}
                onChange={handleChange}
                onUpload={handleUpload}
                richText={(service.rich_text_version ?? 0) >= 1}
                fieldFormats={service.field_formats ?? {}}
                canEditStructure={!!service.can_edit_structure}
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
