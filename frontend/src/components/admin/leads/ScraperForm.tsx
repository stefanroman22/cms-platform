"use client";

import { useState, type FormEvent } from "react";
import { ChevronDown, ChevronRight, Plus, Send, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { FormFeedback } from "@/components/dashboard/FormFeedback";
import { dashboardFieldLabelCn, dashboardInputCn, dashboardPrimaryBtnCn } from "@/lib/styles";
import { AnimatedSelect } from "@/components/dashboard/AnimatedSelect";
import {
  LEAD_TYPE_LABEL,
  WEB_PRESENCE_LABEL,
  type LeadType,
  type WebPresence,
} from "@/lib/leadEnums";
import type { ScrapeParams } from "./types";

interface Props {
  onJobCreated: () => void;
}

const DEFAULT_PARAMS: ScrapeParams = {
  category: "",
  country: "NL",
  cities: [],
  areas: [],
  max_results_per_area: 120,
  language: "en",
  lead_type: "website",
  with_reviews: false,
  review_limit: 10,
  filters: {
    min_rating: null,
    max_rating: null,
    min_reviews: null,
    max_reviews: null,
    web_presence: ["none", "social_only"],
  },
};

export function ScraperForm({ onJobCreated }: Props) {
  const [params, setParams] = useState<ScrapeParams>(DEFAULT_PARAMS);
  const [cityInput, setCityInput] = useState("");
  const [areaInput, setAreaInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const valid = params.category.trim() !== "" && params.country.trim() !== "";

  function addChip(target: "cities" | "areas", value: string) {
    const trimmed = value.trim();
    if (!trimmed) return;
    setParams((p) => ({ ...p, [target]: [...p[target], trimmed] }));
  }

  function removeChip(target: "cities" | "areas", index: number) {
    setParams((p) => ({ ...p, [target]: p[target].filter((_, i) => i !== index) }));
  }

  function setFilter<K extends keyof ScrapeParams["filters"]>(
    key: K,
    value: ScrapeParams["filters"][K]
  ) {
    setParams((p) => ({ ...p, filters: { ...p.filters, [key]: value } }));
  }

  function toggleWebPresence(wp: WebPresence) {
    setFilter(
      "web_presence",
      params.filters.web_presence.includes(wp)
        ? params.filters.web_presence.filter((x) => x !== wp)
        : [...params.filters.web_presence, wp]
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await fetch("/api/admin/scrape-jobs", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ params }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Submit failed (${res.status})`);
      }
      setSuccess("Scrape job queued.");
      setParams(DEFAULT_PARAMS);
      onJobCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormFeedback error={error ?? undefined} success={success ?? undefined} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className={dashboardFieldLabelCn}>
            Category <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            className={dashboardInputCn}
            placeholder="e.g. restaurants"
            value={params.category}
            onChange={(e) => setParams((p) => ({ ...p, category: e.target.value }))}
          />
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>
            Country <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            className={dashboardInputCn}
            placeholder="NL"
            value={params.country}
            onChange={(e) => setParams((p) => ({ ...p, country: e.target.value.toUpperCase() }))}
          />
        </div>
      </div>

      <ChipInput
        label="Cities"
        chips={params.cities}
        value={cityInput}
        onChange={setCityInput}
        onAdd={(v) => {
          addChip("cities", v);
          setCityInput("");
        }}
        onRemove={(i) => removeChip("cities", i)}
        placeholder="e.g. Lelystad"
      />
      <ChipInput
        label="Areas (narrow inside cities)"
        chips={params.areas}
        value={areaInput}
        onChange={setAreaInput}
        onAdd={(v) => {
          addChip("areas", v);
          setAreaInput("");
        }}
        onRemove={(i) => removeChip("areas", i)}
        placeholder="e.g. Centrum"
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <label className={dashboardFieldLabelCn}>Max / area</label>
          <input
            type="number"
            className={dashboardInputCn}
            value={params.max_results_per_area}
            onChange={(e) =>
              setParams((p) => ({
                ...p,
                max_results_per_area: Math.max(1, Number(e.target.value) || 1),
              }))
            }
          />
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>Language</label>
          <input
            type="text"
            className={dashboardInputCn}
            value={params.language}
            onChange={(e) => setParams((p) => ({ ...p, language: e.target.value }))}
          />
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>Lead type</label>
          <AnimatedSelect
            value={params.lead_type}
            onChange={(v) => setParams((p) => ({ ...p, lead_type: v as LeadType }))}
            ariaLabel="Lead type"
            options={(Object.keys(LEAD_TYPE_LABEL) as LeadType[]).map((k) => ({
              value: k,
              label: LEAD_TYPE_LABEL[k],
            }))}
          />
        </div>
        <div className="flex items-end">
          <label className="inline-flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              checked={params.with_reviews}
              onChange={(e) => setParams((p) => ({ ...p, with_reviews: e.target.checked }))}
            />
            Include reviews
          </label>
        </div>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setAdvancedOpen((o) => !o)}
          className="inline-flex items-center gap-1 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200 cursor-pointer"
        >
          {advancedOpen ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          Advanced filters
        </button>
        <AnimatePresence initial={false}>
          {advancedOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
              className="overflow-hidden"
            >
              <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3">
                <FilterNumber
                  label="Rating min"
                  value={params.filters.min_rating}
                  step="0.1"
                  onChange={(v) => setFilter("min_rating", v)}
                />
                <FilterNumber
                  label="Rating max"
                  value={params.filters.max_rating}
                  step="0.1"
                  onChange={(v) => setFilter("max_rating", v)}
                />
                <FilterNumber
                  label="Reviews min"
                  value={params.filters.min_reviews}
                  onChange={(v) => setFilter("min_reviews", v)}
                />
                <FilterNumber
                  label="Reviews max"
                  value={params.filters.max_reviews}
                  onChange={(v) => setFilter("max_reviews", v)}
                />
              </div>
              <div className="mt-3">
                <label className={dashboardFieldLabelCn}>Web presence (keep only)</label>
                <div className="flex flex-wrap gap-1">
                  {(Object.keys(WEB_PRESENCE_LABEL) as WebPresence[]).map((wp) => (
                    <button
                      key={wp}
                      type="button"
                      onClick={() => toggleWebPresence(wp)}
                      className={[
                        "px-2.5 py-1 text-xs rounded-full font-medium transition-colors cursor-pointer",
                        params.filters.web_presence.includes(wp)
                          ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                          : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700",
                      ].join(" ")}
                    >
                      {WEB_PRESENCE_LABEL[wp]}
                    </button>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="pt-2">
        <button
          type="submit"
          disabled={!valid || submitting}
          className={`${dashboardPrimaryBtnCn} px-5 py-2.5`}
        >
          <Send className="h-4 w-4" />
          {submitting ? "Submitting…" : "Submit scrape"}
        </button>
      </div>
    </form>
  );
}

function ChipInput({
  label,
  chips,
  value,
  onChange,
  onAdd,
  onRemove,
  placeholder,
}: {
  label: string;
  chips: string[];
  value: string;
  onChange: (v: string) => void;
  onAdd: (v: string) => void;
  onRemove: (i: number) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className={dashboardFieldLabelCn}>{label}</label>
      <div className="flex gap-2">
        <input
          type="text"
          className={`${dashboardInputCn} flex-1`}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onAdd(value);
            }
          }}
        />
        <button
          type="button"
          onClick={() => onAdd(value)}
          className="inline-flex items-center gap-1 rounded-md border border-zinc-200 dark:border-zinc-700 px-3 py-1.5 text-sm text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-800 cursor-pointer"
        >
          <Plus className="h-4 w-4" />
          Add
        </button>
      </div>
      {chips.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {chips.map((chip, i) => (
            <span
              key={`${chip}-${i}`}
              className="inline-flex items-center gap-1 rounded-full bg-zinc-100 dark:bg-zinc-800 px-2.5 py-0.5 text-xs text-zinc-700 dark:text-zinc-300"
            >
              {chip}
              <button
                type="button"
                onClick={() => onRemove(i)}
                className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 cursor-pointer"
                aria-label={`Remove ${chip}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function FilterNumber({
  label,
  value,
  step,
  onChange,
}: {
  label: string;
  value: number | null;
  step?: string;
  onChange: (v: number | null) => void;
}) {
  return (
    <div>
      <label className={dashboardFieldLabelCn}>{label}</label>
      <input
        type="number"
        className={dashboardInputCn}
        step={step}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
      />
    </div>
  );
}
