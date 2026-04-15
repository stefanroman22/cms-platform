"use client";

import Link from "next/link";
import { Users, ShieldCheck, ExternalLink } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { dashboardSectionCardCn } from "@/lib/styles";

interface Client {
    id: string;
    email: string;
    full_name: string | null;
    is_admin: boolean;
    is_active: boolean;
    created_at: string;
    projects_count: number;
}

function fetchClients(): Promise<Client[]> {
    return fetch("/api/admin/clients", { credentials: "include", cache: "no-store" }).then((r) => {
        if (!r.ok) throw new Error("Failed to load clients.");
        return r.json();
    });
}

export default function AdminClientsPage() {
    const { data: clients, loading, error } = useQuery<Client[]>(
        "admin:clients",
        fetchClients,
        { ttl: 60 * 1000 }
    );

    return (
        <div className="p-8">
            <PageHeader title="All Clients" description="Every registered user across the platform." />

            {error && <p className="mb-6 text-sm text-red-600 dark:text-red-400">{error}</p>}

            {loading && (
                <div className="h-48 rounded-xl border border-zinc-200 bg-white animate-pulse dark:border-zinc-800 dark:bg-zinc-900" />
            )}

            {!loading && (clients ?? []).length === 0 && (
                <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white py-16 text-center dark:border-zinc-700 dark:bg-zinc-900">
                    <Users className="h-8 w-8 text-zinc-300 mb-3 dark:text-zinc-600" />
                    <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">No clients yet.</p>
                </div>
            )}

            {!loading && (clients ?? []).length > 0 && (
                <div className={dashboardSectionCardCn}>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-zinc-100 dark:border-zinc-800">
                                <th className="px-5 py-3 text-left text-xs font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">Client</th>
                                <th className="px-5 py-3 text-left text-xs font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">Role</th>
                                <th className="px-5 py-3 text-left text-xs font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">Projects</th>
                                <th className="px-5 py-3 text-left text-xs font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">Joined</th>
                                <th className="px-5 py-3" />
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                            {(clients ?? []).map((client) => (
                                <tr key={client.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
                                    <td className="px-5 py-3.5">
                                        <p className="font-medium text-zinc-900 dark:text-zinc-100">{client.full_name ?? "—"}</p>
                                        <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-0.5">{client.email}</p>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        {client.is_admin ? (
                                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-400">
                                                <ShieldCheck className="h-3 w-3" /> Admin
                                            </span>
                                        ) : (
                                            <span className="text-xs text-zinc-400 dark:text-zinc-500">Client</span>
                                        )}
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <span className="tabular-nums text-zinc-700 dark:text-zinc-300">{client.projects_count}</span>
                                    </td>
                                    <td className="px-5 py-3.5 text-zinc-500 dark:text-zinc-400">
                                        {new Date(client.created_at).toLocaleDateString("en-GB", {
                                            day: "numeric", month: "short", year: "numeric",
                                        })}
                                    </td>
                                    <td className="px-5 py-3.5 text-right">
                                        <Link
                                            href={`/dashboard/admin/projects?user=${client.id}`}
                                            className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
                                        >
                                            <ExternalLink className="h-3.5 w-3.5" />
                                            Projects
                                        </Link>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
