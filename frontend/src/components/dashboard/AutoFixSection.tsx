"use client";

import { useState } from "react";
import { LocateFixed } from "lucide-react";
import { IssueForm } from "@/components/dashboard/IssueForm";
import { IssueList } from "@/components/dashboard/IssueList";

interface AutoFixSectionProps {
  projectSlug: string;
  isAdmin: boolean;
  currentUserId: string | null;
}

/**
 * "Auto-Fix" — the agentic solver area. Describe a problem (IssueForm); an
 * agent resolves it; progress is tracked in IssueList. Owns the refresh key
 * that re-fetches the list after a new issue is filed.
 */
export function AutoFixSection({ projectSlug, isAdmin, currentUserId }: AutoFixSectionProps) {
  const [issueRefreshKey, setIssueRefreshKey] = useState(0);

  return (
    <div>
      <div className="mb-6 flex items-start gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-100 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300">
          <LocateFixed aria-hidden="true" className="h-4 w-4" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Auto-Fix</h2>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            Describe a problem with your website and our agent will fix it automatically. Track
            progress below.
          </p>
        </div>
      </div>

      <IssueForm projectSlug={projectSlug} onSubmitted={() => setIssueRefreshKey((k) => k + 1)} />
      <IssueList
        projectSlug={projectSlug}
        refreshTrigger={issueRefreshKey}
        isAdmin={isAdmin}
        currentUserId={currentUserId}
      />
    </div>
  );
}
