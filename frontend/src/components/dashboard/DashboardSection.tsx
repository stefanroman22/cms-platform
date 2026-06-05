"use client";

import { BarChart3, ArrowRight } from "lucide-react";
import { dashboardSectionCardCn, dashboardPrimaryBtnCn } from "@/lib/styles";

interface DashboardSectionProps {
  onGoToCms: () => void;
}

/**
 * Default landing section. Vercel analytics aren't built yet, so this is a
 * welcoming "coming soon" empty state with a shortcut into the CMS — never a
 * dead end.
 */
export function DashboardSection({ onGoToCms }: DashboardSectionProps) {
  return (
    <div className={`${dashboardSectionCardCn} px-6 py-16`}>
      <div className="mx-auto flex max-w-md flex-col items-center text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
          <BarChart3 className="h-6 w-6" />
        </span>
        <span className="mt-4 inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-[11px] font-medium text-indigo-700 dark:border-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-300">
          Coming soon
        </span>
        <h2 className="mt-3 text-base font-semibold text-zinc-900 dark:text-zinc-50">
          Website analytics
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Visitor traffic, page views, and performance metrics from Vercel will appear here. For
          now, jump into your content to make changes.
        </p>
        <button type="button" onClick={onGoToCms} className={`${dashboardPrimaryBtnCn} mt-6`}>
          Go to CMS
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
