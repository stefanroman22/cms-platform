"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Plus, Trash2, X } from "lucide-react";
import { fadeUp, rowAdd, staggerFast } from "@/lib/animations";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch } from "../hooks/useLeadPatch";

type Attrs = Record<string, Record<string, boolean>>;

function readAttrs(lead: Lead): Attrs {
  const e = lead.extra;
  if (e && typeof e === "object" && "attributes" in e) {
    return (e.attributes as Attrs) ?? {};
  }
  return {};
}

function attrsEqual(a: Attrs, b: Attrs): boolean {
  const ak = Object.keys(a).sort();
  const bk = Object.keys(b).sort();
  if (ak.length !== bk.length) return false;
  for (let i = 0; i < ak.length; i++) {
    if (ak[i] !== bk[i]) return false;
    const sa = a[ak[i]];
    const sb = b[bk[i]];
    const aak = Object.keys(sa).sort();
    const bbk = Object.keys(sb).sort();
    if (aak.length !== bbk.length) return false;
    for (let j = 0; j < aak.length; j++) {
      if (aak[j] !== bbk[j]) return false;
      if (sa[aak[j]] !== sb[bbk[j]]) return false;
    }
  }
  return true;
}

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

export function AboutSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);
  const [draft, setDraft] = useState<Attrs>(() => structuredClone(readAttrs(lead)));
  const [newSection, setNewSection] = useState("");
  const [newAttrPerSection, setNewAttrPerSection] = useState<Record<string, string>>({});

  useEffect(() => {
    setDraft(structuredClone(readAttrs(lead)));
    setNewSection("");
    setNewAttrPerSection({});
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.extra]);

  async function handleSave() {
    const current = readAttrs(lead);
    if (attrsEqual(draft, current)) return;
    await patch({ about_attributes: draft });
  }

  function handleCancel() {
    setDraft(structuredClone(readAttrs(lead)));
    setNewSection("");
    setNewAttrPerSection({});
    clearError();
  }

  function toggle(section: string, attr: string) {
    setDraft((d) => ({ ...d, [section]: { ...d[section], [attr]: !d[section][attr] } }));
  }

  function removeAttr(section: string, attr: string) {
    setDraft((d) => {
      const next = { ...d, [section]: { ...d[section] } };
      delete next[section][attr];
      return next;
    });
  }

  function removeSection(section: string) {
    setDraft((d) => {
      const next = { ...d };
      delete next[section];
      return next;
    });
  }

  function addAttr(section: string) {
    const label = (newAttrPerSection[section] ?? "").trim();
    if (label === "") return;
    setDraft((d) => ({ ...d, [section]: { ...d[section], [label]: false } }));
    setNewAttrPerSection((s) => ({ ...s, [section]: "" }));
  }

  function addSection() {
    const name = newSection.trim();
    if (name === "" || draft[name] !== undefined) return;
    setDraft((d) => ({ ...d, [name]: {} }));
    setNewSection("");
  }

  const readView =
    Object.keys(readAttrs(lead)).length === 0 ? (
      <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 text-xs text-zinc-500 dark:text-zinc-400 italic">
        No &quot;About&quot; data on Google Maps for this place.
      </div>
    ) : (
      <motion.div
        variants={staggerFast}
        initial="hidden"
        animate="visible"
        className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-3"
      >
        {Object.entries(readAttrs(lead)).map(([section, items]) => (
          <motion.div key={section} variants={fadeUp}>
            <div className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
              {section}
            </div>
            <ul className="space-y-0.5">
              {Object.entries(items).map(([attr, v]) => (
                <li
                  key={attr}
                  className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300"
                >
                  {v ? (
                    <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  ) : (
                    <X className="h-3.5 w-3.5 text-zinc-400 dark:text-zinc-600 shrink-0" />
                  )}
                  <span className={v ? "" : "text-zinc-500 dark:text-zinc-500 line-through"}>
                    {attr}
                  </span>
                </li>
              ))}
            </ul>
          </motion.div>
        ))}
      </motion.div>
    );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-4">
      <AnimatePresence initial={false}>
        {Object.entries(draft).map(([section, items]) => (
          <motion.div
            key={section}
            variants={rowAdd}
            initial="hidden"
            animate="visible"
            exit={{ height: 0, opacity: 0 }}
            className="group/section"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                {section}
              </span>
              <button
                type="button"
                aria-label={`Remove section ${section}`}
                onClick={() => removeSection(section)}
                className="opacity-0 group-hover/section:opacity-100 transition-opacity text-zinc-400 hover:text-red-500 cursor-pointer"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
            <ul className="space-y-1">
              <AnimatePresence initial={false}>
                {Object.entries(items).map(([attr, v]) => (
                  <motion.li
                    key={attr}
                    variants={rowAdd}
                    initial="hidden"
                    animate="visible"
                    exit={{ height: 0, opacity: 0 }}
                    className="flex items-center gap-2 group/row"
                  >
                    <button
                      type="button"
                      role="switch"
                      aria-pressed={v}
                      aria-label={`Toggle ${attr}`}
                      onClick={() => toggle(section, attr)}
                      className={`relative h-4 w-7 rounded-full transition-colors ${v ? "bg-emerald-500" : "bg-zinc-300 dark:bg-zinc-700"}`}
                    >
                      <motion.span
                        layout
                        className="absolute top-0.5 h-3 w-3 rounded-full bg-white shadow"
                        style={{ left: v ? "calc(100% - 0.875rem)" : "0.125rem" }}
                        transition={{ type: "spring", stiffness: 500, damping: 30 }}
                      />
                    </button>
                    <span className="text-sm text-zinc-700 dark:text-zinc-300 flex-1">{attr}</span>
                    <button
                      type="button"
                      aria-label={`Remove ${attr}`}
                      onClick={() => removeAttr(section, attr)}
                      className="opacity-0 group-hover/row:opacity-100 transition-opacity text-zinc-400 hover:text-red-500 cursor-pointer"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
            <div className="mt-1.5 flex items-center gap-1.5">
              <input
                type="text"
                value={newAttrPerSection[section] ?? ""}
                placeholder={`new attribute in ${section}`}
                onChange={(e) => setNewAttrPerSection((s) => ({ ...s, [section]: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addAttr(section);
                  }
                }}
                className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-2 py-1 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
              />
              <button
                type="button"
                onClick={() => addAttr(section)}
                className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 cursor-pointer"
                aria-label={`Add attribute to ${section}`}
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
      <div className="flex items-center gap-1.5 pt-2 border-t border-zinc-200 dark:border-zinc-800">
        <input
          type="text"
          value={newSection}
          placeholder="new section"
          onChange={(e) => setNewSection(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addSection();
            }
          }}
          className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-2 py-1 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
        />
        <button
          type="button"
          onClick={addSection}
          aria-label="Add section"
          className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );

  return (
    <EditableSectionShell
      id="about"
      title="About this business"
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
