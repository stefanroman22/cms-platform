"use client";

import { useEffect, useState } from "react";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch } from "../hooks/useLeadPatch";
import { DesignPromptEditor } from "./DesignPromptEditor";

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

export function DesignPromptSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);

  const [html, setHtml] = useState(lead.design_prompt ?? "");

  useEffect(() => {
    setHtml(lead.design_prompt ?? "");
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.design_prompt]);

  async function handleSave() {
    const next = html.trim() === "" ? null : html;
    if (next === (lead.design_prompt ?? null)) return;
    await patch({ design_prompt: next });
  }

  function handleCancel() {
    setHtml(lead.design_prompt ?? "");
    clearError();
  }

  const readView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      {lead.design_prompt ? (
        <div
          className="prose prose-sm prose-zinc dark:prose-invert max-w-none"
           
          dangerouslySetInnerHTML={{ __html: lead.design_prompt }}
        />
      ) : (
        <p className="text-xs text-zinc-500 dark:text-zinc-400 italic">Not set yet.</p>
      )}
    </div>
  );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      <DesignPromptEditor value={html} onChange={setHtml} />
    </div>
  );

  return (
    <EditableSectionShell
      id="design_prompt"
      title="Design prompt"
      readView={readView}
      editView={editView}
      onSave={handleSave}
      onCancel={handleCancel}
      saving={saving}
      error={error}
      canSave={true}
    />
  );
}
