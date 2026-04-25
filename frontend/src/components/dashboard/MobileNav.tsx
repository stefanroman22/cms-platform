"use client";

import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Layers, Menu, X } from "lucide-react";
import { SidebarPanel } from "./SidebarPanel";

interface Props {
    open: boolean;
    onOpen: () => void;
    onClose: () => void;
}

/** Mobile-only top bar (hamburger + brand) and slide-in drawer.
 *  Hidden at `md+` breakpoints — desktop uses `<Sidebar>` instead. */
export function MobileNav({ open, onOpen, onClose }: Props) {
    // Esc closes the drawer
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    // Lock body scroll while the drawer is open
    useEffect(() => {
        if (!open) return;
        const prev = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = prev;
        };
    }, [open]);

    return (
        <>
            {/* Top bar — always present on mobile, sits above the scrollable
                content area so it doesn't disappear when the user scrolls. */}
            <div className="md:hidden flex items-center justify-between border-b border-zinc-200 bg-white px-3 py-2.5 dark:border-zinc-800 dark:bg-zinc-950">
                <button
                    type="button"
                    onClick={onOpen}
                    aria-label="Open menu"
                    className="cursor-pointer inline-flex h-9 w-9 items-center justify-center rounded-md text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                >
                    <Menu className="h-5 w-5" />
                </button>

                <div className="flex items-center gap-2">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-zinc-900 dark:bg-zinc-800">
                        <Layers className="h-3.5 w-3.5 text-white" strokeWidth={1.5} />
                    </span>
                    <span className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
                        Roman Technologies
                    </span>
                </div>

                {/* Right-side spacer mirrors the hamburger button width so the
                    brand stays visually centered. */}
                <span className="h-9 w-9" aria-hidden="true" />
            </div>

            {/* Drawer + backdrop. AnimatePresence keeps both elements in DOM
                long enough to play their exit animations on close. */}
            <AnimatePresence>
                {open && (
                    <>
                        <motion.div
                            key="mobile-nav-backdrop"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.18 }}
                            onClick={onClose}
                            className="md:hidden fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px]"
                        />
                        <motion.aside
                            key="mobile-nav-drawer"
                            initial={{ x: "-100%" }}
                            animate={{ x: 0 }}
                            exit={{ x: "-100%" }}
                            transition={{ type: "spring", damping: 30, stiffness: 320 }}
                            className="md:hidden fixed inset-y-0 left-0 z-50 w-64 max-w-[80vw] flex flex-col border-r border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
                        >
                            <button
                                type="button"
                                onClick={onClose}
                                aria-label="Close menu"
                                className="cursor-pointer absolute top-3 right-3 z-10 inline-flex h-8 w-8 items-center justify-center rounded-md text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                            >
                                <X className="h-4 w-4" />
                            </button>
                            <SidebarPanel onLinkClick={onClose} />
                        </motion.aside>
                    </>
                )}
            </AnimatePresence>
        </>
    );
}
