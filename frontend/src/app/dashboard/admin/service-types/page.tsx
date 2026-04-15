"use client";

import { Puzzle } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { ServiceIcon } from "@/components/dashboard/ServiceIcon";
import { dashboardSectionCardCn } from "@/lib/styles";

interface ServiceType {
    slug: string;
    name: string;
    description: string | null;
    icon: string;
    schema: Record<string, unknown>;
}

function fetchServiceTypes(): Promise<ServiceType[]> {
    return fetch("/api/admin/service-types", { credentials: "include", cache: "no-store" }).then((r) => {
        if (!r.ok) throw new Error("Failed to load service types.");
        return r.json();
    });
}

export default function AdminServiceTypesPage() {
    const { data: types, loading, error } = useQuery<ServiceType[]>(
        "admin:service-types",
        fetchServiceTypes,
        { ttl: 5 * 60 * 1000 }
    );

    return (
        <div className="p-8">
            <PageHeader
                title="Service Types"
                description="Built-in service plugins available to all projects."
            />

            {error && <p className="mb-6 text-sm text-red-600 dark:text-red-400">{error}</p>}

            {loading && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {[...Array(6)].map((_, i) => (
                        <div key={i} className="h-28 rounded-xl border border-zinc-200 bg-white animate-pulse dark:border-zinc-800 dark:bg-zinc-900" />
                    ))}
                </div>
            )}

            {!loading && (types ?? []).length === 0 && (
                <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white py-16 text-center dark:border-zinc-700 dark:bg-zinc-900">
                    <Puzzle className="h-8 w-8 text-zinc-300 mb-3 dark:text-zinc-600" />
                    <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">No service types found.</p>
                </div>
            )}

            {!loading && (types ?? []).length > 0 && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {(types ?? []).map((st) => (
                        <div key={st.slug} className={`${dashboardSectionCardCn} p-5`}>
                            <div className="flex items-start gap-3">
                                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800">
                                    <ServiceIcon name={st.icon} className="h-4 w-4 text-zinc-600 dark:text-zinc-300" />
                                </span>
                                <div className="min-w-0">
                                    <p className="font-medium text-zinc-900 dark:text-zinc-100 leading-snug">{st.name}</p>
                                    <p className="font-mono text-[10px] text-zinc-400 dark:text-zinc-500 mt-0.5">{st.slug}</p>
                                </div>
                            </div>
                            {st.description && (
                                <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
                                    {st.description}
                                </p>
                            )}
                            <details className="mt-3">
                                <summary className="cursor-pointer text-[10px] font-medium text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors">
                                    Schema
                                </summary>
                                <pre className="mt-2 overflow-x-auto rounded-md bg-zinc-50 dark:bg-zinc-800 p-2 text-[10px] text-zinc-600 dark:text-zinc-300">
                                    {JSON.stringify(st.schema, null, 2)}
                                </pre>
                            </details>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
