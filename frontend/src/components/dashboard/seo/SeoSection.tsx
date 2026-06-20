// SeoSection.tsx
"use client";
import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Search, Sparkles } from "lucide-react";
import { dashAccent } from "@/lib/dashboardTheme";
import { OverviewTab } from "./OverviewTab";
import { PlanTab } from "./PlanTab";
import { HistoryTab } from "./HistoryTab";
import { ArticlesTab } from "./ArticlesTab";
import { CompetitorsTab } from "./CompetitorsTab";
import { SettingsTab } from "./SettingsTab";

type Tab = "overview" | "plan" | "history" | "articles" | "competitors" | "settings";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "plan", label: "Plan" },
  { key: "history", label: "History" },
  { key: "articles", label: "Articles" },
  { key: "competitors", label: "Competitors" },
  { key: "settings", label: "Settings" },
];

// Shown to clients until the SEO/GEO agent is opened to them. Admins see the real section.
function SeoComingSoon() {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-300 bg-white/50 px-6 py-16 text-center dark:border-zinc-700 dark:bg-zinc-900/40">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
        <Search className="h-6 w-6" aria-hidden />
      </div>
      <span className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
        <Sparkles className="h-3 w-3" aria-hidden /> Coming soon
      </span>
      <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
        SEO &amp; GEO — work in progress
      </h3>
      <p className="mt-2 max-w-md text-sm text-zinc-500 dark:text-zinc-400">
        We&apos;re building an AI assistant that boosts your visibility on Google and on AI search
        engines like ChatGPT, Perplexity and Gemini. You&apos;ll be able to run it on your own site
        here soon — we&apos;ll let you know the moment it&apos;s ready.
      </p>
    </div>
  );
}

export function SeoSection({ projectSlug, isAdmin }: { projectSlug: string; isAdmin: boolean }) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const reduce = useReducedMotion();
  if (!isAdmin) return <SeoComingSoon />;
  return (
    <div>
      <nav
        aria-label="SEO & GEO tabs"
        className="no-scrollbar mb-6 flex gap-1 overflow-x-auto overflow-y-hidden border-b border-zinc-200 pb-px dark:border-zinc-800"
      >
        {TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              aria-current={isActive ? "page" : undefined}
              className={`relative shrink-0 cursor-pointer rounded-t-md px-3 py-2 text-sm font-medium whitespace-nowrap ${dashAccent.focusRing}`}
            >
              <span
                className={
                  "transition-colors duration-150 " +
                  (isActive
                    ? "text-zinc-900 dark:text-zinc-100"
                    : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200")
                }
              >
                {tab.label}
              </span>
              {isActive && (
                <motion.span
                  layoutId="seo-tabs-underline"
                  className={`absolute inset-x-2 -bottom-px h-[2px] rounded-full ${dashAccent.tabUnderline}`}
                  transition={
                    reduce
                      ? { duration: 0 }
                      : { type: "spring", stiffness: 480, damping: 36, mass: 0.6 }
                  }
                />
              )}
            </button>
          );
        })}
      </nav>
      {activeTab === "overview" && <OverviewTab projectSlug={projectSlug} />}
      {activeTab === "plan" && <PlanTab projectSlug={projectSlug} />}
      {activeTab === "history" && <HistoryTab projectSlug={projectSlug} />}
      {activeTab === "articles" && <ArticlesTab projectSlug={projectSlug} />}
      {activeTab === "competitors" && <CompetitorsTab projectSlug={projectSlug} />}
      {activeTab === "settings" && <SettingsTab projectSlug={projectSlug} />}
    </div>
  );
}
