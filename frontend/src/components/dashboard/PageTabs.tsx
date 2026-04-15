"use client";

interface PageTabsProps {
    pages: string[];
    activePage: string;
    onSelect: (page: string) => void;
}

/**
 * Horizontal tab bar for switching between CMS pages.
 * Pages are ordered as-received; "General" is always last if present.
 */
export function PageTabs({ pages, activePage, onSelect }: PageTabsProps) {
    if (pages.length <= 1) return null;

    return (
        <div className="mb-6 flex items-center gap-1 overflow-x-auto border-b border-zinc-200 dark:border-zinc-800 pb-px">
            {pages.map((page) => {
                const isActive = page === activePage;
                return (
                    <button
                        key={page}
                        onClick={() => onSelect(page)}
                        className={`
                            shrink-0 px-4 py-2 text-sm font-medium rounded-t-lg -mb-px border-b-2 transition-colors cursor-pointer
                            ${isActive
                                ? "border-zinc-900 text-zinc-900 dark:border-zinc-100 dark:text-zinc-100"
                                : "border-transparent text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
                            }
                        `}
                    >
                        {page}
                    </button>
                );
            })}
        </div>
    );
}
