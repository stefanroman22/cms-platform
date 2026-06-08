"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Search } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { dashboardInputCn, dashboardFieldLabelCn } from "@/lib/styles";
import { AnimatedSelect } from "@/components/dashboard/AnimatedSelect";
import { WEB_PRESENCE_LABEL, LEAD_STATUS_LABEL, LEAD_TYPE_LABEL } from "@/lib/leadEnums";
import type { LeadFiltersState } from "./types";
import { EMPTY_FILTERS } from "./types";
import type { LeadType, WebPresence, LeadStatus } from "@/lib/leadEnums";

interface Props {
  value: LeadFiltersState;
  onChange: (v: LeadFiltersState) => void;
}

export function LeadFilters({ value, onChange }: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  function set<K extends keyof LeadFiltersState>(k: K, v: LeadFiltersState[K]) {
    onChange({ ...value, [k]: v });
  }
  function toggle<T extends string>(list: T[], item: T): T[] {
    return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <label className={dashboardFieldLabelCn}>Country</label>
          <input
            type="text"
            className={dashboardInputCn}
            placeholder="e.g. NL"
            value={value.country}
            onChange={(e) => set("country", e.target.value)}
          />
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>City</label>
          <input
            type="text"
            className={dashboardInputCn}
            value={value.city}
            onChange={(e) => set("city", e.target.value)}
          />
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>Category</label>
          <input
            type="text"
            className={dashboardInputCn}
            value={value.category}
            onChange={(e) => set("category", e.target.value)}
          />
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>Search</label>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400" />
            <input
              type="text"
              className={`${dashboardInputCn} pl-8`}
              placeholder="business name…"
              value={value.search}
              onChange={(e) => set("search", e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className={dashboardFieldLabelCn}>Web presence</label>
          <div className="flex flex-wrap gap-1">
            {(Object.keys(WEB_PRESENCE_LABEL) as WebPresence[]).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => set("web_presence", toggle(value.web_presence, k))}
                className={[
                  "px-2.5 py-1 text-xs rounded-full font-medium transition-colors cursor-pointer",
                  value.web_presence.includes(k)
                    ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                    : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700",
                ].join(" ")}
              >
                {WEB_PRESENCE_LABEL[k]}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>Lead status</label>
          <div className="flex flex-wrap gap-1">
            {(Object.keys(LEAD_STATUS_LABEL) as LeadStatus[]).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => set("lead_status", toggle(value.lead_status, k))}
                className={[
                  "px-2.5 py-1 text-xs rounded-full font-medium transition-colors cursor-pointer",
                  value.lead_status.includes(k)
                    ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                    : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700",
                ].join(" ")}
              >
                {LEAD_STATUS_LABEL[k]}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className={dashboardFieldLabelCn}>Lead type</label>
          <AnimatedSelect
            value={value.lead_type}
            onChange={(v) => set("lead_type", v as LeadType | "")}
            ariaLabel="Lead type"
            options={[
              { value: "", label: "All" },
              ...(Object.keys(LEAD_TYPE_LABEL) as LeadType[]).map((k) => ({
                value: k,
                label: LEAD_TYPE_LABEL[k],
              })),
            ]}
          />
        </div>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setAdvancedOpen((o) => !o)}
          className="inline-flex items-center gap-1 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200 cursor-pointer"
        >
          {advancedOpen ? (
            <ChevronUp className="h-3.5 w-3.5" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5" />
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
                <div>
                  <label className={dashboardFieldLabelCn}>Rating min</label>
                  <input
                    type="number"
                    step="0.1"
                    className={dashboardInputCn}
                    value={value.min_rating}
                    onChange={(e) => set("min_rating", e.target.value)}
                  />
                </div>
                <div>
                  <label className={dashboardFieldLabelCn}>Rating max</label>
                  <input
                    type="number"
                    step="0.1"
                    className={dashboardInputCn}
                    value={value.max_rating}
                    onChange={(e) => set("max_rating", e.target.value)}
                  />
                </div>
                <div>
                  <label className={dashboardFieldLabelCn}>Reviews min</label>
                  <input
                    type="number"
                    className={dashboardInputCn}
                    value={value.min_reviews}
                    onChange={(e) => set("min_reviews", e.target.value)}
                  />
                </div>
                <div>
                  <label className={dashboardFieldLabelCn}>Reviews max</label>
                  <input
                    type="number"
                    className={dashboardInputCn}
                    value={value.max_reviews}
                    onChange={(e) => set("max_reviews", e.target.value)}
                  />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export { EMPTY_FILTERS };
