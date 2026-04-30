"use client";

import Link from "next/link";
import { use, useState, useEffect } from "react";
import { ArrowLeft, ChevronRight, Settings, Globe, ExternalLink } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { useUser } from "@/context/user";
import { ServiceGrid } from "@/components/dashboard/ServiceGrid";
import type { ServiceCardService } from "@/components/dashboard/ServiceCard";
import { IssueForm } from "@/components/dashboard/IssueForm";
import { IssueList } from "@/components/dashboard/IssueList";
import { PreviewPublishBar } from "@/components/dashboard/PreviewPublishBar";
import { dashboardInputCn, dashboardFieldLabelCn, dashboardSectionCardCn, dashboardErrorBannerCn } from "@/lib/styles";
import * as cache from "@/lib/cache";

interface ProjectInfo {
    name: string;
    slug: string;
    website_url?: string | null;
}

function fetchServices(projectSlug: string): Promise<ServiceCardService[]> {
    return fetch(`/api/projects/${projectSlug}/services`, {
        credentials: "include",
        cache: "no-store",
    }).then(async (r) => {
        if (!r.ok) {
            const body = await r.json().catch(() => ({}));
            throw new Error(body.detail ?? "Failed to load services.");
        }
        return r.json();
    });
}

function fetchProjects(): Promise<ProjectInfo[]> {
    return fetch(`/api/projects`, { credentials: "include", cache: "no-store" })
        .then((r) => r.json());
}

export default function ProjectWorkspacePage({
    params,
}: {
    params: Promise<{ projectSlug: string }>;
}) {
    const { projectSlug } = use(params);
    const { user } = useUser();
    const isAdmin = user?.is_admin ?? false;

    const servicesKey = `services:${projectSlug}`;
    const { data: services, loading: servicesLoading, error, refresh: refreshServices } = useQuery<ServiceCardService[]>(
        servicesKey,
        () => fetchServices(projectSlug),
        { ttl: 60 * 1000 }
    );

    // Shared cache key with the projects-overview page. Both pages read the
    // same array; this page derives its single project locally. Storing a
    // single object under "projects" used to overwrite the overview's array
    // and crash `.filter()` on next navigation.
    const { data: projectsList } = useQuery<ProjectInfo[]>(
        "projects",
        fetchProjects,
        { ttl: 2 * 60 * 1000 }
    );

    const project = Array.isArray(projectsList)
        ? projectsList.find((p) => p.slug === projectSlug)
        : undefined;
    const projectName = project?.name ?? projectSlug;

    // ── Project settings (admin only) ────────────────────────────────────────
    const [settings, setSettings] = useState<{ website_url: string; allowed_origins: string } | null>(null);
    const [settingsSaving, setSettingsSaving] = useState(false);
    const [settingsMsg, setSettingsMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

    useEffect(() => {
        if (!isAdmin) return;
        fetch(`/api/projects/${projectSlug}/settings`, { credentials: "include" })
            .then((r) => r.json())
            .then((d) => setSettings({
                website_url: d.website_url ?? "",
                allowed_origins: (d.allowed_origins ?? []).join("\n"),
            }))
            .catch(() => {});
    }, [isAdmin, projectSlug]);

    async function handleSaveSettings(e: React.FormEvent) {
        e.preventDefault();
        if (!settings) return;
        setSettingsSaving(true);
        setSettingsMsg(null);
        try {
            const r = await fetch(`/api/projects/${projectSlug}/settings`, {
                method: "PATCH",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    website_url: settings.website_url.trim() || null,
                    allowed_origins: settings.allowed_origins
                        .split("\n")
                        .map((s) => s.trim())
                        .filter(Boolean),
                }),
            });
            if (!r.ok) {
                const body = await r.json().catch(() => ({}));
                throw new Error(body.detail ?? "Failed to save settings.");
            }
            setSettingsMsg({ type: "ok", text: "Settings saved." });
        } catch (err) {
            setSettingsMsg({ type: "err", text: err instanceof Error ? err.message : "Save failed." });
        } finally {
            setSettingsSaving(false);
        }
    }

    const [issueRefreshKey, setIssueRefreshKey] = useState(0);

    // ── Remove service ───────────────────────────────────────────────────────
    const [removingKey, setRemovingKey] = useState<string | null>(null);

    async function handleRemoveService(serviceKey: string) {
        if (!confirm(`Remove service "${serviceKey}"? This will also delete its content.`)) return;
        setRemovingKey(serviceKey);
        try {
            await fetch(`/api/projects/${projectSlug}/services/${serviceKey}`, {
                method: "DELETE",
                credentials: "include",
            });
            cache.invalidate(servicesKey);
            refreshServices();
        } finally {
            setRemovingKey(null);
        }
    }

    return (
        <div className="p-4 md:p-8">
            <PreviewPublishBar projectSlug={projectSlug} projectName={project?.name ?? projectSlug} />
            {/* Breadcrumb */}
            <div className="mb-6 flex items-center gap-1.5 text-sm text-zinc-400 dark:text-zinc-500">
                <Link
                    href="/dashboard"
                    className="flex items-center gap-1 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors"
                >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    Projects
                </Link>
                <ChevronRight className="h-3.5 w-3.5" />
                <span className="text-zinc-700 font-medium dark:text-zinc-200">{projectName}</span>
            </div>

            <div className="mb-8">
                <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{projectName}</h1>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                    Manage content and settings for this project.
                </p>
                {(project?.website_url || settings?.website_url) && (
                    <a
                        href={(project?.website_url || settings?.website_url) as string}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-4 flex w-full max-w-xl items-start gap-3 rounded-lg border border-zinc-200 bg-white px-4 py-3 transition-colors hover:border-emerald-300 hover:bg-emerald-50/40 dark:border-zinc-800 dark:bg-zinc-900/40 dark:hover:border-emerald-800 dark:hover:bg-emerald-950/30"
                    >
                        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300">
                            <Globe className="h-3.5 w-3.5" />
                        </span>
                        <div className="min-w-0 flex-1">
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                                Live website
                            </p>
                            <p className="mt-0.5 truncate font-mono text-sm text-zinc-900 dark:text-zinc-100">
                                {((project?.website_url || settings?.website_url) as string).replace(/^https?:\/\//, "")}
                            </p>
                            <p className="mt-1 text-xs leading-snug text-zinc-500 dark:text-zinc-400">
                                This is the public website your visitors see.
                            </p>
                        </div>
                        <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-zinc-400 dark:text-zinc-500" />
                    </a>
                )}
            </div>

            {error && (
                <p className="mb-6 text-sm text-red-600 dark:text-red-400">{error}</p>
            )}

            {/* Loading skeleton */}
            {servicesLoading && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {[...Array(4)].map((_, i) => (
                        <div key={i} className="h-32 rounded-xl border border-zinc-200 bg-white animate-pulse dark:border-zinc-800 dark:bg-zinc-900" />
                    ))}
                </div>
            )}

            {/* Service grid (page-grouped + email section) */}
            {!servicesLoading && (
                <ServiceGrid
                    services={services ?? []}
                    projectSlug={projectSlug}
                    isAdmin={isAdmin}
                    removingKey={removingKey}
                    onRemove={handleRemoveService}
                />
            )}

            {/* ── Issues ────────────────────────────────────────────────────── */}
            <div className="mt-12">
                <IssueForm
                    projectSlug={projectSlug}
                    onSubmitted={() => setIssueRefreshKey((k) => k + 1)}
                />
                <IssueList
                    projectSlug={projectSlug}
                    refreshTrigger={issueRefreshKey}
                    isAdmin={isAdmin}
                    currentUserId={user?.id ?? null}
                />
            </div>

            {/* ── Admin: Project Settings ───────────────────────────────────── */}
            {isAdmin && settings !== null && (
                <div className="mt-12">
                    <h2 className="flex items-center gap-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-4">
                        <Settings className="h-4 w-4" />
                        Project Settings
                    </h2>
                    <div className={`${dashboardSectionCardCn} p-6 max-w-lg`}>
                        <form onSubmit={handleSaveSettings} className="space-y-4">
                            {settingsMsg && (
                                <div className={settingsMsg.type === "ok"
                                    ? "rounded-lg bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 px-4 py-2.5 text-sm text-green-700 dark:text-green-300"
                                    : dashboardErrorBannerCn
                                }>
                                    {settingsMsg.text}
                                </div>
                            )}

                            <div>
                                <label className={dashboardFieldLabelCn}>Website URL</label>
                                <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-1.5">
                                    The production URL of the client&apos;s website.
                                </p>
                                <input
                                    type="url"
                                    value={settings.website_url}
                                    onChange={(e) => setSettings((s) => s && ({ ...s, website_url: e.target.value }))}
                                    placeholder="https://example.com"
                                    className={dashboardInputCn}
                                />
                            </div>

                            <div>
                                <label className={dashboardFieldLabelCn}>Allowed origins</label>
                                <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-1.5">
                                    One origin per line. Form submissions from unlisted origins will be rejected.
                                    Leave empty to allow any origin.
                                </p>
                                <textarea
                                    rows={4}
                                    value={settings.allowed_origins}
                                    onChange={(e) => setSettings((s) => s && ({ ...s, allowed_origins: e.target.value }))}
                                    placeholder={"https://example.com\nhttps://www.example.com"}
                                    className={`${dashboardInputCn} font-mono text-xs resize-y`}
                                />
                            </div>

                            <div className="flex justify-end pt-1">
                                <button
                                    type="submit"
                                    disabled={settingsSaving}
                                    className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors dark:bg-zinc-700 dark:hover:bg-zinc-600 cursor-pointer"
                                >
                                    {settingsSaving ? "Saving…" : "Save settings"}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
