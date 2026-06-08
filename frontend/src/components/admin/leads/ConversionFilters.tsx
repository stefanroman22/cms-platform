"use client";

import { dashboardFieldLabelCn, dashboardInputCn } from "@/lib/styles";
import { AnimatedSelect } from "@/components/dashboard/AnimatedSelect";
import { LEAD_TYPE_LABEL, type LeadType } from "@/lib/leadEnums";
import type { ConversionFilters as Filters } from "./types";

interface Props {
  value: Filters;
  onChange: (v: Filters) => void;
}

export function ConversionFilters({ value, onChange }: Props) {
  function set<K extends keyof Filters>(k: K, v: Filters[K]) {
    onChange({ ...value, [k]: v });
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
      <div>
        <label className={dashboardFieldLabelCn}>From month</label>
        <input
          type="month"
          className={dashboardInputCn}
          value={value.since}
          onChange={(e) => set("since", e.target.value)}
        />
      </div>
      <div>
        <label className={dashboardFieldLabelCn}>Lead type</label>
        <AnimatedSelect
          value={value.lead_type}
          onChange={(v) => set("lead_type", v as LeadType | "")}
          ariaLabel="Lead type filter"
          options={[
            { value: "", label: "All" },
            ...(Object.keys(LEAD_TYPE_LABEL) as LeadType[]).map((k) => ({
              value: k,
              label: LEAD_TYPE_LABEL[k],
            })),
          ]}
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
    </div>
  );
}
