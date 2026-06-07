"use client";

import { useEffect, useState } from "react";
import { Languages as LanguagesIcon, X } from "lucide-react";
import { useQuery } from "@/hooks/useQuery";
import { LANGUAGES } from "@/lib/languages";
import { dashboardSectionCardCn, dashboardInputCn, dashboardErrorBannerCn } from "@/lib/styles";
import * as cache from "@/lib/cache";

type LocalesFromApi = { default_locale: string; locales: string[] };

const NAME_BY_CODE: Record<string, string> = Object.fromEntries(
  LANGUAGES.map((l) => [l.code, l.name])
);

export function LanguagesPanel({ projectSlug }: { projectSlug: string }) {
  const localesKey = `locales:${projectSlug}`;
  const { data, loading } = useQuery<LocalesFromApi>(
    localesKey,
    () =>
      fetch(`/api/projects/${projectSlug}/locales`, { credentials: "include" }).then((r) =>
        r.json()
      ),
    { ttl: 5 * 60 * 1000 }
  );

  const [draft, setDraft] = useState<LocalesFromApi | null>(null);
  const [adding, setAdding] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (data && Array.isArray(data.locales) && draft === null) {
      setDraft({ default_locale: data.default_locale, locales: [...data.locales] });
    }
  }, [data, draft]);

  if ((loading && draft === null) || !draft) return null;

  const available = LANGUAGES.filter((l) => !draft.locales.includes(l.code));

  function addLocale() {
    if (!draft || !adding || draft.locales.includes(adding)) return;
    setDraft({ ...draft, locales: [...draft.locales, adding] });
    setAdding("");
    setMsg(null);
  }
  function removeLocale(code: string) {
    if (!draft || code === draft.default_locale) return;
    setDraft({ ...draft, locales: draft.locales.filter((c) => c !== code) });
    setMsg(null);
  }
  function makeDefault(code: string) {
    if (!draft) return;
    setDraft({ ...draft, default_locale: code });
    setMsg(null);
  }

  async function save() {
    if (!draft) return;
    setSaving(true);
    setMsg(null);
    try {
      const r = await fetch(`/api/projects/${projectSlug}/locales`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        throw new Error(b.detail ?? "Failed to save languages.");
      }
      const saved = (await r.json()) as LocalesFromApi;
      cache.set(localesKey, saved);
      setDraft({ default_locale: saved.default_locale, locales: [...saved.locales] });
      setMsg({
        type: "ok",
        text: "Languages saved. New languages were auto-translated into your content.",
      });
    } catch (e) {
      setMsg({ type: "err", text: e instanceof Error ? e.message : "Save failed." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-8 max-w-lg">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        <LanguagesIcon aria-hidden="true" className="h-4 w-4" />
        Languages
      </h2>
      <div className={`${dashboardSectionCardCn} p-6`}>
        {msg && (
          <div
            className={
              msg.type === "ok"
                ? "mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-300"
                : `${dashboardErrorBannerCn} mb-4`
            }
          >
            {msg.text}
          </div>
        )}
        <p className="mb-3 text-xs text-zinc-400 dark:text-zinc-500">
          The default language is the one you author in; other languages are auto-translated. Adding
          a language translates your content into it. Removing one deletes its content.
        </p>

        <div className="mb-4 flex flex-wrap gap-2">
          {draft.locales.map((code) => (
            <span
              key={code}
              className="inline-flex items-center gap-1.5 rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-xs text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
            >
              <span className="font-medium uppercase">{code}</span>
              <span className="text-zinc-400 dark:text-zinc-500">{NAME_BY_CODE[code] ?? code}</span>
              {code === draft.default_locale ? (
                <span className="rounded bg-zinc-200 px-1 text-[10px] text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300">
                  default
                </span>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => makeDefault(code)}
                    className="cursor-pointer text-[10px] text-sky-600 hover:underline dark:text-sky-400"
                  >
                    make default
                  </button>
                  <button
                    type="button"
                    aria-label={`Remove ${code}`}
                    onClick={() => removeLocale(code)}
                    className="cursor-pointer text-zinc-400 hover:text-red-500"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </>
              )}
            </span>
          ))}
        </div>

        <div className="flex gap-2">
          <select
            aria-label="Add a language"
            value={adding}
            onChange={(e) => setAdding(e.target.value)}
            className={dashboardInputCn}
          >
            <option value="">Add a language…</option>
            {available.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name} ({l.code})
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={addLocale}
            disabled={!adding}
            className="cursor-pointer shrink-0 rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
          >
            Add
          </button>
        </div>

        <div className="flex justify-end pt-4">
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="cursor-pointer rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-700 dark:hover:bg-zinc-600"
          >
            {saving ? "Saving…" : "Save languages"}
          </button>
        </div>
      </div>
    </div>
  );
}
