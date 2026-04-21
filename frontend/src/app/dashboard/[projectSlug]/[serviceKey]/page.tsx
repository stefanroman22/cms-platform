"use client";

import { use, useState, useCallback } from "react";
import Link from "next/link";
import { ArrowLeft, ChevronRight, Save, CheckCircle, AlertCircle } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { ServiceIcon } from "@/components/dashboard/ServiceIcon";
import { EDITOR_MAP } from "@/components/dashboard/editors";
import { PreviewPublishBar } from "@/components/dashboard/PreviewPublishBar";
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
}

function fetchServiceDetail(projectSlug: string, serviceKey: string): Promise<ServiceDetail> {
    return fetch(`/api/projects/${projectSlug}/services/${serviceKey}`, {
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
    content: Record<string, unknown>
): Promise<void> {
    const r = await fetch(`/api/projects/${projectSlug}/services/${serviceKey}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
    });
    if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail ?? "Failed to save.");
    }
}

async function uploadFile(
    projectSlug: string,
    serviceKey: string,
    file: File
): Promise<string> {
    const form = new FormData();
    form.append("file", file);
    const r = await fetch(
        `/api/projects/${projectSlug}/services/${serviceKey}/upload`,
        { method: "POST", credentials: "include", body: form }
    );
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
    const cacheKey = `service:${projectSlug}:${serviceKey}`;

    const { data: service, loading, error, refresh } = useQuery<ServiceDetail>(
        cacheKey,
        () => fetchServiceDetail(projectSlug, serviceKey),
        { ttl: 60 * 1000 }
    );

    // draft === null means no unsaved changes
    const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState("");
    const [saveSuccess, setSaveSuccess] = useState(false);

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
            await saveContent(projectSlug, serviceKey, content);
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

    const serviceLabel = service?.label ?? serviceKey;
    const EditorComponent = service ? EDITOR_MAP[service.service_type_slug] : null;

    return (
        <div className="p-8">
            <PreviewPublishBar projectSlug={projectSlug} projectName={projectSlug} />
            {/* Breadcrumb */}
            <div className="mb-6 flex items-center gap-1.5 text-sm text-zinc-400 dark:text-zinc-500">
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
            <div className="mb-6 flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                    {service && (
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800">
                            <ServiceIcon name={service.service_type_icon} className="h-5 w-5 text-zinc-600 dark:text-zinc-300" />
                        </span>
                    )}
                    <div>
                        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{serviceLabel}</h1>
                        {service && (
                            <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{service.service_type_name}</p>
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

            {/* Feedback */}
            {saveError && <div className={`${dashboardErrorBannerCn} mb-6`}>{saveError}</div>}
            {saveSuccess && (
                <div className={`${dashboardSuccessBannerCn} mb-6`}>
                    <CheckCircle className="h-4 w-4 shrink-0" />
                    Changes saved successfully.
                </div>
            )}

            {/* Loading */}
            {loading && (
                <div className="h-64 rounded-xl border border-zinc-200 bg-white animate-pulse dark:border-zinc-800 dark:bg-zinc-900" />
            )}

            {/* Fetch error */}
            {!loading && error && (
                <div className={dashboardErrorBannerCn}>{error}</div>
            )}

            {/* Editor — keyed on service.id so it re-mounts cleanly after save */}
            {!loading && service && EditorComponent && (
                <EditorComponent
                    key={service.id}
                    initialContent={service.content}
                    onChange={handleChange}
                    onUpload={handleUpload}
                />
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
                        day: "numeric", month: "short", year: "numeric",
                        hour: "2-digit", minute: "2-digit",
                    })}
                </p>
            )}
        </div>
    );
}
