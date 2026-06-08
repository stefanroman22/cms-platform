"use client";

import { motion } from "framer-motion";
import { Star } from "lucide-react";
import { LeadBadge } from "./LeadBadge";
import {
  LEAD_STATUS_BADGE_CN,
  LEAD_STATUS_LABEL,
  LEAD_TYPE_BADGE_CN,
  LEAD_TYPE_LABEL,
  PAYMENT_STATUS_BADGE_CN,
  PAYMENT_STATUS_LABEL,
} from "@/lib/leadEnums";
import type { Lead } from "./types";

interface Props {
  leads: Lead[];
  total: number;
  loading: boolean;
  page: number; // 0-indexed
  pageSize: number;
  onPageChange: (page: number) => void;
  onSelect: (lead: Lead) => void;
}

export function LeadsTable({
  leads,
  total,
  loading,
  page,
  pageSize,
  onPageChange,
  onSelect,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (loading) {
    return (
      <div className="mt-4 space-y-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="h-14 rounded-lg bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
        ))}
      </div>
    );
  }

  if (leads.length === 0) {
    return (
      <div className="mt-4 py-10 text-center text-sm text-zinc-500 dark:text-zinc-400">
        No leads match your filters.
      </div>
    );
  }

  return (
    <div className="mt-2">
      {/* Mobile card list */}
      <div className="md:hidden space-y-2">
        {leads.map((l) => (
          <motion.button
            key={l.id}
            layout
            type="button"
            onClick={() => onSelect(l)}
            className="w-full text-left rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
                  {l.business_name}
                </div>
                <div className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400 truncate">
                  {l.city ?? "—"} · {l.category ?? "—"}
                </div>
              </div>
              <LeadBadge
                label={LEAD_TYPE_LABEL[l.lead_type]}
                className={LEAD_TYPE_BADGE_CN[l.lead_type]}
                width="w-auto"
              />
            </div>
            <div className="mt-2 flex items-center gap-2">
              <LeadBadge
                label={LEAD_STATUS_LABEL[l.lead_status]}
                className={LEAD_STATUS_BADGE_CN[l.lead_status]}
              />
              {l.rating != null && (
                <span className="inline-flex items-center gap-0.5 text-xs text-zinc-600 dark:text-zinc-400">
                  <Star className="h-3 w-3" />
                  {l.rating.toFixed(1)}
                  {l.review_count != null && (
                    <span className="text-zinc-400 dark:text-zinc-500">({l.review_count})</span>
                  )}
                </span>
              )}
            </div>
          </motion.button>
        ))}
      </div>

      {/* Desktop table */}
      <div className="hidden md:block rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900 text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Name</th>
              <th className="text-left px-4 py-2 font-medium">City</th>
              <th className="text-left px-4 py-2 font-medium">Category</th>
              <th className="text-left px-4 py-2 font-medium">Product</th>
              <th className="text-right px-4 py-2 font-medium">★</th>
              <th className="text-right px-4 py-2 font-medium">Reviews</th>
              <th className="text-left px-4 py-2 font-medium">Status</th>
              <th className="text-left px-4 py-2 font-medium">Paid</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {leads.map((l) => (
              <motion.tr
                key={l.id}
                layout
                onClick={() => onSelect(l)}
                className="bg-white dark:bg-zinc-950 hover:bg-zinc-50 dark:hover:bg-zinc-900 cursor-pointer"
              >
                <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100 truncate max-w-xs">
                  {l.business_name}
                </td>
                <td className="px-4 py-2 text-zinc-600 dark:text-zinc-400">{l.city ?? "—"}</td>
                <td className="px-4 py-2 text-zinc-600 dark:text-zinc-400">{l.category ?? "—"}</td>
                <td className="px-4 py-2">
                  <LeadBadge
                    label={LEAD_TYPE_LABEL[l.lead_type]}
                    className={LEAD_TYPE_BADGE_CN[l.lead_type]}
                    width="w-auto"
                  />
                </td>
                <td className="px-4 py-2 text-right text-zinc-600 dark:text-zinc-400 tabular-nums">
                  {l.rating?.toFixed(1) ?? "—"}
                </td>
                <td className="px-4 py-2 text-right text-zinc-600 dark:text-zinc-400 tabular-nums">
                  {l.review_count ?? "—"}
                </td>
                <td className="px-4 py-2">
                  <LeadBadge
                    label={LEAD_STATUS_LABEL[l.lead_status]}
                    className={LEAD_STATUS_BADGE_CN[l.lead_status]}
                  />
                </td>
                <td className="px-4 py-2">
                  <LeadBadge
                    label={PAYMENT_STATUS_LABEL[l.payment_status]}
                    className={PAYMENT_STATUS_BADGE_CN[l.payment_status]}
                  />
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
        <span>
          {total} lead{total === 1 ? "" : "s"} · page {page + 1} / {totalPages}
        </span>
        <div className="flex gap-1">
          <button
            type="button"
            disabled={page === 0}
            onClick={() => onPageChange(page - 1)}
            className="px-3 py-1 rounded-md border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            ← Prev
          </button>
          <button
            type="button"
            disabled={page >= totalPages - 1}
            onClick={() => onPageChange(page + 1)}
            className="px-3 py-1 rounded-md border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
