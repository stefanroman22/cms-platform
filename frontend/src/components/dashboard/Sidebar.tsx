"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, User, PlusCircle, LogOut, Layers, Users, Puzzle, FolderKanban } from "lucide-react";
import { logout } from "@/lib/auth";
import { broadcastLogout } from "@/context/auth";
import { useLoading } from "@/context/loading";
import { useUser } from "@/context/user";

const navItems = [
    { href: "/dashboard", label: "Projects Overview", icon: LayoutGrid, exact: true },
    { href: "/dashboard/account", label: "Account Settings", icon: User, exact: false },
    { href: "/dashboard/new-project", label: "Create New Project", icon: PlusCircle, exact: false },
];

const adminItems = [
    { href: "/dashboard/admin/clients", label: "All Clients", icon: Users, exact: false },
    { href: "/dashboard/admin/projects", label: "All Projects", icon: FolderKanban, exact: false },
    { href: "/dashboard/admin/service-types", label: "Service Types", icon: Puzzle, exact: false },
];

export function Sidebar() {
    const pathname = usePathname();
    const { show } = useLoading();
    const { user } = useUser();

    async function handleSignOut() {
        show();
        await logout();

        // Notify all other tabs (root / login) to reset auth state
        broadcastLogout();

        if (window.opener && !window.opener.closed) {
            // Root tab is still alive — switch to it and close dashboard
            window.opener.focus();
            window.close();
            // Fallback: if the browser refused to close, navigate away
            window.location.href = "/";
        } else {
            // Root tab is gone — reuse this tab
            window.location.href = "/";
        }
    }

    return (
        <aside className="w-60 shrink-0 h-screen sticky top-0 flex flex-col bg-white dark:bg-zinc-950 border-r border-zinc-200 dark:border-zinc-800">
            {/* Brand */}
            <div className="flex items-center gap-2.5 px-5 py-4 border-b border-zinc-100 dark:border-zinc-800">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-zinc-900 dark:bg-zinc-800">
                    <Layers className="h-4 w-4 text-white" strokeWidth={1.5} />
                </span>
                <div className="flex flex-col leading-tight">
                    <span className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
                        Roman Technologies
                    </span>
                    <span className="text-xs text-zinc-400 dark:text-zinc-500">Client Portal</span>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
                {navItems.map(({ href, label, icon: Icon, exact }) => {
                    const isActive = exact ? pathname === href : pathname.startsWith(href);
                    return (
                        <Link
                            key={href}
                            href={href}
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive
                                    ? "bg-zinc-900 text-white dark:bg-zinc-700 dark:text-white"
                                    : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                                }`}
                        >
                            <Icon className="h-4 w-4 shrink-0" />
                            {label}
                        </Link>
                    );
                })}
            </nav>

            {/* Admin section */}
            {user?.is_admin && (
                <div className="px-3 pb-2">
                    <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                        Admin
                    </p>
                    {adminItems.map(({ href, label, icon: Icon, exact }) => {
                        const isActive = exact ? pathname === href : pathname.startsWith(href);
                        return (
                            <Link
                                key={href}
                                href={href}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive
                                        ? "bg-zinc-900 text-white dark:bg-zinc-700 dark:text-white"
                                        : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                                    }`}
                            >
                                <Icon className="h-4 w-4 shrink-0" />
                                {label}
                            </Link>
                        );
                    })}
                </div>
            )}

            {/* Sign out */}
            <div className="p-3 border-t border-zinc-100 dark:border-zinc-800">
                <button
                    onClick={handleSignOut}
                    className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-500 dark:hover:bg-zinc-800 dark:hover:text-zinc-100 transition-colors cursor-pointer"
                >
                    <LogOut className="h-4 w-4 shrink-0" />
                    Sign out
                </button>
            </div>
        </aside>
    );
}
