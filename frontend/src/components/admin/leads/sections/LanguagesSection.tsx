"use client";

import { useEffect, useState } from "react";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { LanguageMultiSelect } from "./LanguageMultiSelect";
import { useLeadPatch } from "../hooks/useLeadPatch";

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

/** Compares two string lists order-insensitively. */
function sameSet(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false;
  const setB = new Set(b);
  return a.every((x) => setB.has(x));
}

export function LanguagesSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);
  const [languages, setLanguages] = useState<string[]>(lead.languages ?? []);

  useEffect(() => {
    setLanguages(lead.languages ?? []);
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.languages]);

  async function handleSave() {
    if (sameSet(languages, lead.languages ?? [])) return;
    await patch({ languages });
  }

  function handleCancel() {
    setLanguages(lead.languages ?? []);
    clearError();
  }

  const readView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      {(lead.languages ?? []).length === 0 ? (
        <span className="text-xs italic text-zinc-400 dark:text-zinc-500">
          No languages selected yet
        </span>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {lead.languages.map((name) => (
            <span
              key={name}
              className="inline-flex items-center rounded-full border border-zinc-200 bg-zinc-200/70 px-2.5 py-0.5 text-xs font-medium text-zinc-800 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
            >
              {name}
            </span>
          ))}
        </div>
      )}
    </div>
  );

  const editView = <LanguageMultiSelect value={languages} onChange={setLanguages} />;

  return (
    <EditableSectionShell
      id="languages"
      title="Languages"
      readView={readView}
      editView={editView}
      onSave={handleSave}
      onCancel={handleCancel}
      saving={saving}
      error={error}
      canSave
    />
  );
}
